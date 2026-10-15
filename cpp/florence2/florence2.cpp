// florence2.cpp — Florence-2 image captioning core (ONNX Runtime, C++).
#include "florence2.hpp"

#include <onnxruntime_cxx_api.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <numeric>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>

namespace flo {
namespace {

constexpr int kNImg = 577;
constexpr int kBos = 0;
constexpr int kEos = 2;
constexpr int kPad = 1;
constexpr int kNLayers = 6;
constexpr int kHeads = 12;
constexpr int kHeadDim = 64;
constexpr int kImgSize = 768;

const float kMean[3] = {0.485f, 0.456f, 0.406f};
const float kStd[3] = {0.229f, 0.224f, 0.225f};

struct KV {
    std::vector<float> data;
    std::vector<int64_t> shape;
};

using KVList = std::vector<KV>;

float g_dummy = 0.0f;

Ort::Value MakeF32(Ort::MemoryInfo& mi, const std::vector<float>& data, const std::vector<int64_t>& shape) {
    size_t n = 1;
    for (auto d : shape) n *= static_cast<size_t>(d);
    float* p = data.empty() ? &g_dummy : const_cast<float*>(data.data());
    return Ort::Value::CreateTensor<float>(mi, p, n, shape.data(), shape.size());
}

Ort::Value MakeI64(Ort::MemoryInfo& mi, const std::vector<int64_t>& data, const std::vector<int64_t>& shape) {
    size_t n = 1;
    for (auto d : shape) n *= static_cast<size_t>(d);
    return Ort::Value::CreateTensor<int64_t>(mi, const_cast<int64_t*>(data.data()), n, shape.data(), shape.size());
}

KV CopyOut(const Ort::Value& v) {
    auto info = v.GetTensorTypeAndShapeInfo();
    KV kv;
    kv.shape = info.GetShape();
    const float* p = v.GetTensorData<float>();
    size_t n = info.GetElementCount();
    kv.data.assign(p, p + n);
    return kv;
}

std::vector<float> PreprocessImage(const std::string& path, int& out_w, int& out_h) {
    int w = 0, h = 0, ch = 0;
    unsigned char* data = stbi_load(path.c_str(), &w, &h, &ch, 3);  // force RGB
    if (!data) throw std::runtime_error("cannot read image: " + path);
    out_w = w;
    out_h = h;
    std::vector<unsigned char> resized(static_cast<size_t>(3) * kImgSize * kImgSize);
    stbir_resize_uint8(data, w, h, 0, resized.data(), kImgSize, kImgSize, 0, 3);
    stbi_image_free(data);

    std::vector<float> pix(static_cast<size_t>(3) * kImgSize * kImgSize);
    const int plane = kImgSize * kImgSize;
    for (int i = 0; i < plane; ++i) {
        for (int c = 0; c < 3; ++c) {
            float v = resized[static_cast<size_t>(i) * 3 + c] / 255.0f;
            pix[static_cast<size_t>(c) * plane + i] = (v - kMean[c]) / kStd[c];
        }
    }
    return pix;
}

class Vocab {
  public:
    void Load(const std::string& path) {
        std::ifstream f(path, std::ios::binary);
        if (!f) throw std::runtime_error("cannot open vocab: " + path + " (run build.sh)");
        uint32_t n = 0;
        f.read(reinterpret_cast<char*>(&n), 4);
        toks_.resize(n);
        for (uint32_t i = 0; i < n; ++i) {
            uint32_t len = 0;
            f.read(reinterpret_cast<char*>(&len), 4);
            toks_[i].resize(len);
            if (len) f.read(&toks_[i][0], len);
        }
    }
    std::string Decode(const std::vector<int64_t>& ids) const {
        std::string out;
        for (int64_t id : ids) {
            if (id < 0 || id >= static_cast<int64_t>(toks_.size())) continue;
            if (id == kBos || id == kEos || id == kPad) continue;
            out += toks_[id];
        }
        return out;
    }

  private:
    std::vector<std::string> toks_;
};

}  // namespace

struct Florence2::Impl {
    Ort::Env env;
    Ort::SessionOptions so;
    std::unique_ptr<Ort::Session> emb, vis, enc, dec;
    Ort::MemoryInfo mi;
    std::vector<std::string> dec_in_names, dec_out_names;
    std::unordered_map<std::string, size_t> out_idx;
    Vocab vocab;
    std::string provider = "CPU";

    Impl(const std::string& model_dir, bool use_cuda)
        : env(ORT_LOGGING_LEVEL_ERROR, "florence2"), mi(Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault)) {
        so.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        so.SetLogSeverityLevel(ORT_LOGGING_LEVEL_ERROR);
        if (use_cuda) {
            try {
                OrtCUDAProviderOptions cuda_options{};
                cuda_options.device_id = 0;
                so.AppendExecutionProvider_CUDA(cuda_options);
                provider = "CUDA";
            } catch (const std::exception&) {
                provider = "CPU";
            }
        }
        const std::string p = model_dir + "/onnx/";
        emb = std::make_unique<Ort::Session>(env, (p + "embed_tokens.onnx").c_str(), so);
        vis = std::make_unique<Ort::Session>(env, (p + "vision_encoder.onnx").c_str(), so);
        enc = std::make_unique<Ort::Session>(env, (p + "encoder_model.onnx").c_str(), so);
        dec = std::make_unique<Ort::Session>(env, (p + "decoder_model_merged.onnx").c_str(), so);

        Ort::AllocatorWithDefaultOptions alloc;
        for (size_t i = 0; i < dec->GetInputCount(); ++i)
            dec_in_names.push_back(dec->GetInputNameAllocated(i, alloc).get());
        for (size_t i = 0; i < dec->GetOutputCount(); ++i)
            dec_out_names.push_back(dec->GetOutputNameAllocated(i, alloc).get());
        for (size_t i = 0; i < dec_out_names.size(); ++i) out_idx[dec_out_names[i]] = i;

        vocab.Load(model_dir + "/vocab.bin");
    }

    struct Step {
        std::vector<float> logits;  // last position row, size vocab
        int64_t vocab = 0;
        KVList dk, dv, ek, ev;
    };

    std::vector<float> Embed(const std::vector<int64_t>& ids) {
        std::vector<int64_t> shape{1, static_cast<int64_t>(ids.size())};
        std::vector<Ort::Value> in;
        in.push_back(MakeI64(mi, ids, shape));
        const char* names[] = {"input_ids"};
        const char* onames[] = {"inputs_embeds"};
        auto out = emb->Run(Ort::RunOptions{nullptr}, names, in.data(), 1, onames, 1);
        size_t n = out[0].GetTensorTypeAndShapeInfo().GetElementCount();
        return std::vector<float>(out[0].GetTensorData<float>(), out[0].GetTensorData<float>() + n);
    }

    Step Decode(int64_t token, const KVList& dk, const KVList& dv, const KVList& ek, const KVList& ev,
                const std::vector<float>& enc_hidden, int64_t enc_len, const std::vector<int64_t>& attn) {
        bool first = dk[0].shape.size() < 3 || dk[0].shape[2] == 0;
        std::vector<float> de = Embed({token});
        std::vector<int64_t> de_shape = {1, 1, 768};

        std::vector<Ort::Value> fvals;
        std::vector<std::string> name_store;
        std::vector<const char*> fnames;
        bool ucb = !first;
        std::vector<int64_t> attn_shape{1, enc_len};
        std::vector<int64_t> enc_shape{1, enc_len, 768};
        int64_t bshape = 1;

        name_store.reserve(dec_in_names.size());
        fvals.reserve(dec_in_names.size());
        fnames.reserve(dec_in_names.size());
        for (const std::string& n : dec_in_names) {
            name_store.push_back(n);
            if (n == "encoder_attention_mask") {
                fvals.push_back(MakeI64(mi, attn, attn_shape));
            } else if (n == "encoder_hidden_states") {
                fvals.push_back(MakeF32(mi, enc_hidden, enc_shape));
            } else if (n == "inputs_embeds") {
                fvals.push_back(MakeF32(mi, de, de_shape));
            } else if (n == "use_cache_branch") {
                fvals.push_back(Ort::Value::CreateTensor<bool>(mi, &ucb, 1, &bshape, 1));
            } else {
                int layer = n[16] - '0';
                bool is_decoder = n.find("decoder") != std::string::npos;
                bool is_key = n.compare(n.size() - 4, 4, ".key") == 0;
                const KV& kv = is_decoder ? (is_key ? dk[layer] : dv[layer])
                                          : (is_key ? ek[layer] : ev[layer]);
                fvals.push_back(MakeF32(mi, kv.data, kv.shape));
            }
            fnames.push_back(name_store.back().c_str());
        }

        std::vector<const char*> onames;
        onames.reserve(dec_out_names.size());
        for (auto& s : dec_out_names) onames.push_back(s.c_str());
        auto outs = dec->Run(Ort::RunOptions{nullptr}, fnames.data(), fvals.data(), fvals.size(),
                             onames.data(), onames.size());

        Step st;
        const Ort::Value& logits = outs[out_idx.at("logits")];
        auto linfo = logits.GetTensorTypeAndShapeInfo();
        st.vocab = linfo.GetShape().back();
        int64_t rows = linfo.GetElementCount() / st.vocab;
        const float* last = logits.GetTensorData<float>() + (rows - 1) * st.vocab;
        st.logits.assign(last, last + st.vocab);

        st.dk.resize(kNLayers);
        st.dv.resize(kNLayers);
        st.ek.resize(kNLayers);
        st.ev.resize(kNLayers);
        for (int i = 0; i < kNLayers; ++i) {
            std::string pre = "present." + std::to_string(i) + ".";
            st.dk[i] = CopyOut(outs[out_idx.at(pre + "decoder.key")]);
            st.dv[i] = CopyOut(outs[out_idx.at(pre + "decoder.value")]);
            if (first) {
                st.ek[i] = CopyOut(outs[out_idx.at(pre + "encoder.key")]);
                st.ev[i] = CopyOut(outs[out_idx.at(pre + "encoder.value")]);
            } else {
                st.ek[i] = ek[i];
                st.ev[i] = ev[i];
            }
        }
        return st;
    }
};

Florence2::Florence2(const std::string& model_dir, bool use_cuda)
    : impl_(std::make_unique<Impl>(model_dir, use_cuda)) {}

Florence2::~Florence2() = default;

const std::string& Florence2::provider() const { return impl_->provider; }

std::string Florence2::Caption(const std::string& image_path, const Options& opt, int* out_w, int* out_h) {
    Impl& im = *impl_;
    auto& mi = im.mi;

    int iw = 0, ih = 0;
    std::vector<float> pix = PreprocessImage(image_path, iw, ih);
    if (out_w) *out_w = iw;
    if (out_h) *out_h = ih;

    // ---- vision ----
    std::vector<int64_t> pix_shape{1, 3, kImgSize, kImgSize};
    std::vector<Ort::Value> vis_in;
    vis_in.push_back(MakeF32(mi, pix, pix_shape));
    const char* vis_in_names[] = {"pixel_values"};
    const char* vis_out_names[] = {"image_features"};
    auto vis_out = im.vis->Run(Ort::RunOptions{nullptr}, vis_in_names, vis_in.data(), 1, vis_out_names, 1);
    auto ifs = vis_out[0].GetTensorTypeAndShapeInfo().GetShape();
    size_t ifn = vis_out[0].GetTensorTypeAndShapeInfo().GetElementCount();
    if (ifs.size() != 3 || ifs[1] != kNImg)
        throw std::runtime_error("unexpected image_features shape");
    std::vector<float> ifeat(vis_out[0].GetTensorData<float>(), vis_out[0].GetTensorData<float>() + ifn);

    // ---- task token ids (fixed, no-input tasks) ----
    static const std::unordered_map<std::string, std::vector<int64_t>> kTasks = {
        {"<CAPTION>", {2264, 473, 5, 2274, 6190, 116}},
        {"<DETAILED_CAPTION>", {47066, 21700, 11, 4617, 99, 16, 2343, 11, 5, 2274, 4}},
        {"<MORE_DETAILED_CAPTION>", {47066, 21700, 19, 10, 17818, 99, 16, 2343, 11, 5, 2274, 4}},
        {"<OCR>", {2264, 16, 5, 2788, 11, 5, 2274, 116}},
    };
    auto it = kTasks.find(opt.task);
    if (it == kTasks.end()) throw std::runtime_error("unknown task: " + opt.task);
    const std::vector<int64_t>& task_ids = it->second;

    // ---- text embedding + concat ----
    std::vector<int64_t> text_ids;
    text_ids.push_back(kBos);
    text_ids.insert(text_ids.end(), task_ids.begin(), task_ids.end());
    text_ids.push_back(kEos);
    std::vector<float> temb = im.Embed(text_ids);
    std::vector<float> seq(ifeat);
    seq.insert(seq.end(), temb.begin(), temb.end());
    int64_t enc_len = kNImg + static_cast<int64_t>(text_ids.size());
    std::vector<int64_t> seq_shape{1, enc_len, 768};
    std::vector<int64_t> attn(static_cast<size_t>(enc_len), 1);

    std::vector<Ort::Value> enc_in;
    enc_in.push_back(MakeI64(mi, attn, {1, enc_len}));
    enc_in.push_back(MakeF32(mi, seq, seq_shape));
    const char* enc_in_names[] = {"attention_mask", "inputs_embeds"};
    const char* enc_out_names[] = {"last_hidden_state"};
    auto enc_out = im.enc->Run(Ort::RunOptions{nullptr}, enc_in_names, enc_in.data(), 2, enc_out_names, 1);
    size_t enc_n = enc_out[0].GetTensorTypeAndShapeInfo().GetElementCount();
    std::vector<float> enc_hidden(enc_out[0].GetTensorData<float>(),
                                  enc_out[0].GetTensorData<float>() + enc_n);

    // ---- beam search ----
    struct Beam {
        std::vector<int64_t> seq;
        double score = 0.0;
        KVList dk, dv, ek, ev;
        int64_t next = kEos;
        bool done = false;
    };
    auto empty_caches = [&]() {
        KVList dk(kNLayers), dv(kNLayers), ek(kNLayers), ev(kNLayers);
        for (int i = 0; i < kNLayers; ++i) {
            dk[i].shape = dv[i].shape = {1, kHeads, 0, kHeadDim};
            ek[i].shape = ev[i].shape = {1, kHeads, 0, kHeadDim};
        }
        return std::make_tuple(dk, dv, ek, ev);
    };

    int beams = std::max(1, opt.num_beams);
    std::vector<Beam> active, finished;
    {
        Beam root;
        std::tie(root.dk, root.dv, root.ek, root.ev) = empty_caches();
        active.push_back(std::move(root));
    }

    for (int step = 0; step < opt.max_new_tokens; ++step) {
        std::vector<Beam> cand;
        for (const Beam& b : active) {
            Impl::Step r = im.Decode(b.next, b.dk, b.dv, b.ek, b.ev, enc_hidden, enc_len, attn);
            // log-softmax
            double m = -std::numeric_limits<double>::infinity();
            for (float x : r.logits) m = std::max(m, static_cast<double>(x));
            double se = 0.0;
            for (float x : r.logits) se += std::exp(static_cast<double>(x) - m);
            double logZ = m + std::log(se);
            // top-k tokens by logit
            int K = std::min<int>(beams, static_cast<int>(r.logits.size()));
            std::vector<int64_t> idx(r.logits.size());
            std::iota(idx.begin(), idx.end(), 0);
            std::partial_sort(idx.begin(), idx.begin() + K, idx.end(),
                              [&](int64_t a, int64_t b) { return r.logits[a] > r.logits[b]; });
            for (int k = 0; k < K; ++k) {
                int64_t t = idx[k];
                Beam c = b;  // copies seq + caches (caches overwritten below)
                c.seq.push_back(t);
                c.score += static_cast<double>(r.logits[t]) - logZ;
                c.dk = r.dk;
                c.dv = r.dv;
                c.ek = r.ek;
                c.ev = r.ev;
                c.next = t;
                c.done = (t == kEos);
                cand.push_back(std::move(c));
            }
        }
        std::sort(cand.begin(), cand.end(), [](const Beam& a, const Beam& b) { return a.score > b.score; });

        std::vector<Beam> new_active;
        for (Beam& c : cand) {
            if (c.done) {
                finished.push_back(std::move(c));
            } else if (static_cast<int>(new_active.size()) < beams) {
                new_active.push_back(std::move(c));
            }
        }
        active = std::move(new_active);
        if (active.empty()) break;
    }

    // Length-normalized score (average log-prob) so long captions are not penalized
    // against early EOS candidates.
    auto norm = [](const Beam& b) {
        return b.seq.empty() ? -1e18 : b.score / static_cast<double>(b.seq.size());
    };
    const Beam* best = nullptr;
    for (const Beam& b : finished) {
        if (!best || norm(b) > norm(*best)) best = &b;
    }
    if (!best) {
        for (const Beam& b : active) {
            if (!best || norm(b) > norm(*best)) best = &b;
        }
    }
    std::vector<int64_t> out_ids;
    if (best) out_ids = best->seq;
    return im.vocab.Decode(out_ids);
}

}  // namespace flo
