// ocr.cpp — PaddleOCR PP-OCRv4 (DBNet det + CRNN rec) via ONNX Runtime.
//
// Recipe (validated against /opt/my-agent/wechat-ocr + PP-OCRv4 onnx):
//   det: resize max-side 960 with dims multiple of 32, /255, BGR CHW ->
//        prob map -> threshold 0.3 -> connected components -> bbox -> unclip 1.6
//   rec: crop -> height 48 (/255, BGR CHW) -> argmax -> CTC (blank=0, dict[idx-1])
#include "ocr.hpp"

#include <onnxruntime_cxx_api.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace ocr {
namespace {

constexpr int kDetMaxSide = 960;
constexpr float kDetThresh = 0.3f;
constexpr float kUnclipRatio = 1.6f;
constexpr int kRecHeight = 48;

struct Image {
    int w = 0, h = 0;
    std::vector<unsigned char> bgr;  // w*h*3
};

Image LoadBgr(const std::string& path) {
    int w = 0, h = 0, c = 0;
    unsigned char* rgb = stbi_load(path.c_str(), &w, &h, &c, 3);
    if (!rgb) throw std::runtime_error("cannot read image: " + path);
    Image im;
    im.w = w;
    im.h = h;
    im.bgr.resize(static_cast<size_t>(w) * h * 3);
    for (size_t i = 0; i < im.bgr.size(); i += 3) {
        im.bgr[i + 0] = rgb[i + 2];
        im.bgr[i + 1] = rgb[i + 1];
        im.bgr[i + 2] = rgb[i + 0];
    }
    stbi_image_free(rgb);
    return im;
}

std::vector<std::string> LoadDict(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open dict: " + path);
    std::vector<std::string> dict;
    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        dict.push_back(line);  // may be empty for space in some dicts; keep aligned
    }
    return dict;
}

}  // namespace

struct Ocr::Impl {
    Ort::Env env;
    Ort::SessionOptions so;
    std::unique_ptr<Ort::Session> det, rec;
    Ort::MemoryInfo mi;
    std::vector<std::string> dict;
    std::string det_in, det_out, rec_in, rec_out;
    std::string provider = "CPU";

    Impl(const std::string& det_path, const std::string& rec_path, const std::string& dict_path, bool use_cuda)
        : env(ORT_LOGGING_LEVEL_ERROR, "ocr"),
          mi(Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault)) {
        dict = LoadDict(dict_path);
        so.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        so.SetLogSeverityLevel(ORT_LOGGING_LEVEL_ERROR);
        so.SetIntraOpNumThreads(4);
        if (use_cuda) {
            try {
                OrtCUDAProviderOptions o{};
                o.device_id = 0;
                so.AppendExecutionProvider_CUDA(o);
                provider = "CUDA";
            } catch (const std::exception&) {
                provider = "CPU";
            }
        }
        det = std::make_unique<Ort::Session>(env, det_path.c_str(), so);
        rec = std::make_unique<Ort::Session>(env, rec_path.c_str(), so);
        Ort::AllocatorWithDefaultOptions a;
        det_in = det->GetInputNameAllocated(0, a).get();
        det_out = det->GetOutputNameAllocated(0, a).get();
        rec_in = rec->GetInputNameAllocated(0, a).get();
        rec_out = rec->GetOutputNameAllocated(0, a).get();
    }

    // Run a single-input/single-output model with CHW float input.
    std::vector<float> RunCHW(Ort::Session* s, const std::string& in_name, const std::string& out_name,
                              const std::vector<float>& data, const std::vector<int64_t>& shape,
                              std::vector<int64_t>& out_shape) {
        Ort::Value t = Ort::Value::CreateTensor<float>(mi, const_cast<float*>(data.data()), data.size(),
                                                       shape.data(), shape.size());
        const char* in_names[] = {in_name.c_str()};
        const char* out_names[] = {out_name.c_str()};
        auto outs = s->Run(Ort::RunOptions{nullptr}, in_names, &t, 1, out_names, 1);
        auto info = outs[0].GetTensorTypeAndShapeInfo();
        out_shape = info.GetShape();
        size_t n = info.GetElementCount();
        const float* p = outs[0].GetTensorData<float>();
        return std::vector<float>(p, p + n);
    }
};

Ocr::Ocr(const std::string& det_model, const std::string& rec_model, const std::string& dict, bool use_cuda)
    : impl_(std::make_unique<Impl>(det_model, rec_model, dict, use_cuda)) {}

Ocr::~Ocr() = default;

const std::string& Ocr::provider() const { return impl_->provider; }

std::vector<TextBox> Ocr::Run(const std::string& image_path) {
    Impl& im = *impl_;
    Image img = LoadBgr(image_path);
    const int W = img.w, H = img.h;

    // ---- detection input (resize, multiple of 32, /255, BGR CHW) ----
    float ratio = std::min(1.0f, static_cast<float>(kDetMaxSide) / std::max(W, H));
    int rw = std::max(32, (static_cast<int>(W * ratio) / 32) * 32);
    int rh = std::max(32, (static_cast<int>(H * ratio) / 32) * 32);

    std::vector<unsigned char> rsz(static_cast<size_t>(rw) * rh * 3);
    stbir_resize_uint8(img.bgr.data(), W, H, 0, rsz.data(), rw, rh, 0, 3);
    std::vector<float> det_input(static_cast<size_t>(3) * rw * rh);
    for (size_t i = 0; i < static_cast<size_t>(rw) * rh; ++i) {
        for (int c = 0; c < 3; ++c) det_input[static_cast<size_t>(c) * rw * rh + i] = rsz[i * 3 + c] / 255.0f;
    }
    std::vector<int64_t> det_shape{1, 3, rh, rw}, prob_shape;
    std::vector<float> prob = im.RunCHW(im.det.get(), im.det_in, im.det_out, det_input, det_shape, prob_shape);
    // prob_shape: [1,1,ph,pw]
    int ph = static_cast<int>(prob_shape[2]);
    int pw = static_cast<int>(prob_shape[3]);

    // Resize prob map to (rw, rh) in resized coords.
    std::vector<float> prob_rw(static_cast<size_t>(rw) * rh);
    if (ph == rh && pw == rw) {
        prob_rw = prob;
    } else {
        stbir_resize_float(prob.data(), pw, ph, 0, prob_rw.data(), rw, rh, 0, 1);
    }

    // ---- threshold + connected components (BFS) -> boxes in resized coords ----
    std::vector<uint8_t> bin(static_cast<size_t>(rw) * rh, 0);
    for (size_t i = 0; i < bin.size(); ++i) bin[i] = prob_rw[i] > kDetThresh ? 1 : 0;

    std::vector<int> stack;
    std::vector<uint8_t> seen(bin.size(), 0);
    std::vector<TextBox> boxes;  // boxes in original coords
    const float sx = static_cast<float>(W) / rw;
    const float sy = static_cast<float>(H) / rh;

    for (int y0 = 0; y0 < rh; ++y0) {
        for (int x0 = 0; x0 < rw; ++x0) {
            size_t idx = static_cast<size_t>(y0) * rw + x0;
            if (!bin[idx] || seen[idx]) continue;
            // BFS
            int minx = x0, maxx = x0, miny = y0, maxy = y0;
            stack.clear();
            stack.push_back(static_cast<int>(idx));
            seen[idx] = 1;
            size_t count = 0;
            while (!stack.empty()) {
                int cur = stack.back();
                stack.pop_back();
                ++count;
                int cy = cur / rw, cx = cur % rw;
                minx = std::min(minx, cx);
                maxx = std::max(maxx, cx);
                miny = std::min(miny, cy);
                maxy = std::max(maxy, cy);
                const int nb[4][2] = {{cx - 1, cy}, {cx + 1, cy}, {cx, cy - 1}, {cx, cy + 1}};
                for (auto& n : nb) {
                    int nx = n[0], ny = n[1];
                    if (nx < 0 || ny < 0 || nx >= rw || ny >= rh) continue;
                    size_t ni = static_cast<size_t>(ny) * rw + nx;
                    if (bin[ni] && !seen[ni]) {
                        seen[ni] = 1;
                        stack.push_back(static_cast<int>(ni));
                    }
                }
            }
            if (count < 6) continue;

            // unclip (expand by area*ratio/perimeter), in resized coords
            float bw = maxx - minx + 1, bh = maxy - miny + 1;
            float dd = (bw * bh * kUnclipRatio) / (2.0f * (bw + bh));
            int ox0 = std::max(0, static_cast<int>(minx - dd));
            int oy0 = std::max(0, static_cast<int>(miny - dd));
            int ox1 = std::min(rw - 1, static_cast<int>(maxx + dd));
            int oy1 = std::min(rh - 1, static_cast<int>(maxy + dd));

            // map back to original coords
            TextBox tb;
            tb.x = static_cast<int>(ox0 * sx);
            tb.y = static_cast<int>(oy0 * sy);
            tb.w = std::max(1, static_cast<int>((ox1 - ox0 + 1) * sx));
            tb.h = std::max(1, static_cast<int>((oy1 - oy0 + 1) * sy));
            tb.x = std::max(0, std::min(tb.x, W - 1));
            tb.y = std::max(0, std::min(tb.y, H - 1));
            tb.w = std::min(tb.w, W - tb.x);
            tb.h = std::min(tb.h, H - tb.y);
            boxes.push_back(tb);
        }
    }

    std::sort(boxes.begin(), boxes.end(), [](const TextBox& a, const TextBox& b) {
        if (std::abs(a.y - b.y) > 8) return a.y < b.y;
        return a.x < b.x;
    });

    // ---- recognition ----
    for (TextBox& tb : boxes) {
        // crop from original BGR, resize to h=48
        int ww = std::max(8, static_cast<int>(tb.w * static_cast<float>(kRecHeight) / tb.h));
        std::vector<unsigned char> crop(static_cast<size_t>(ww) * kRecHeight * 3);
        // manual bilinear-ish: use stb on the sub-rect via a temp image
        std::vector<unsigned char> sub(static_cast<size_t>(tb.w) * tb.h * 3);
        for (int y = 0; y < tb.h; ++y) {
            const unsigned char* src = &img.bgr[(static_cast<size_t>(tb.y + y) * W + tb.x) * 3];
            std::copy(src, src + static_cast<size_t>(tb.w) * 3, &sub[static_cast<size_t>(y) * tb.w * 3]);
        }
        stbir_resize_uint8(sub.data(), tb.w, tb.h, 0, crop.data(), ww, kRecHeight, 0, 3);

        std::vector<float> rec_input(static_cast<size_t>(3) * ww * kRecHeight);
        for (size_t i = 0; i < static_cast<size_t>(ww) * kRecHeight; ++i) {
            for (int c = 0; c < 3; ++c) rec_input[static_cast<size_t>(c) * ww * kRecHeight + i] = crop[i * 3 + c] / 255.0f;
        }
        std::vector<int64_t> rec_shape{1, 3, kRecHeight, ww}, out_shape;
        std::vector<float> out = im.RunCHW(im.rec.get(), im.rec_in, im.rec_out, rec_input, rec_shape, out_shape);
        // out_shape: [1, T, C]
        int T = static_cast<int>(out_shape[1]);
        int C = static_cast<int>(out_shape[2]);
        std::string text;
        int prev = -1;
        float score_sum = 0;
        int score_n = 0;
        for (int t = 0; t < T; ++t) {
            const float* row = &out[static_cast<size_t>(t) * C];
            int best = 0;
            float bv = row[0];
            for (int c = 1; c < C; ++c) {
                if (row[c] > bv) {
                    bv = row[c];
                    best = c;
                }
            }
            if (best == 0) {
                prev = best;
                continue;
            }
            if (best != prev) {
                int ci = best - 1;
                if (ci >= 0 && ci < static_cast<int>(im.dict.size())) text += im.dict[ci];
                score_sum += bv;
                ++score_n;
            }
            prev = best;
        }
        tb.text = text;
        tb.score = score_n ? score_sum / score_n : 0.0f;
    }

    // drop empties
    std::vector<TextBox> out;
    for (auto& b : boxes)
        if (!b.text.empty()) out.push_back(b);
    return out;
}

}  // namespace ocr
