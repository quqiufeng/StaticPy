// face.cpp — Face detect (SCRFD) / align-crop / parse (BiSeNet) via ONNX Runtime.
#include "face.hpp"

#include <onnxruntime_cxx_api.h>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace face {
namespace {

struct Image {
    int w = 0, h = 0;
    std::vector<unsigned char> rgb;  // w*h*3
};

Image LoadRgb(const std::string& path) {
    int w = 0, h = 0, c = 0;
    unsigned char* d = stbi_load(path.c_str(), &w, &h, &c, 3);
    if (!d) throw std::runtime_error("cannot read image: " + path);
    Image im;
    im.w = w;
    im.h = h;
    im.rgb.assign(d, d + static_cast<size_t>(w) * h * 3);
    stbi_image_free(d);
    return im;
}

// arcface 5-point template (112×112)
const float kTemplate[10] = {38.2946f, 51.6963f, 73.5318f, 51.5014f,
                             56.0252f, 71.7366f, 41.5493f, 92.3655f, 70.7299f, 92.2041f};

float IoU(const float* a, const float* b) {
    float x1 = std::max(a[0], b[0]), y1 = std::max(a[1], b[1]);
    float x2 = std::min(a[2], b[2]), y2 = std::min(a[3], b[3]);
    float w = std::max(0.0f, x2 - x1), h = std::max(0.0f, y2 - y1);
    float inter = w * h;
    float ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
    return ua > 0 ? inter / ua : 0.0f;
}

unsigned char Clamp8(float v) {
    int x = static_cast<int>(std::lround(v));
    return static_cast<unsigned char>(std::min(255, std::max(0, x)));
}

}  // namespace

struct FaceEngine::Impl {
    Options opt;
    Ort::Env env;
    Ort::SessionOptions so;
    std::unique_ptr<Ort::Session> det, parse;
    Ort::MemoryInfo mi;
    std::string provider = "CPU";

    Impl(const Options& o, bool use_cuda)
        : opt(o), env(ORT_LOGGING_LEVEL_ERROR, "face"), mi(Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault)) {
        so.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        so.SetLogSeverityLevel(ORT_LOGGING_LEVEL_ERROR);
        if (use_cuda) {
            try {
                OrtCUDAProviderOptions c{};
                c.device_id = 0;
                so.AppendExecutionProvider_CUDA(c);
                provider = "CUDA";
            } catch (const std::exception&) {
                provider = "CPU";
            }
        }
        det = std::make_unique<Ort::Session>(env, opt.det_model.c_str(), so);
        parse = std::make_unique<Ort::Session>(env, opt.parse_model.c_str(), so);
    }
};

FaceEngine::FaceEngine(const Options& opt, bool use_cuda) : impl_(std::make_unique<Impl>(opt, use_cuda)) {}
FaceEngine::~FaceEngine() = default;
const std::string& FaceEngine::provider() const { return impl_->provider; }

std::vector<Face> FaceEngine::Detect(const std::string& image_path) const {
    Impl& im = *impl_;
    Image img = LoadRgb(image_path);
    const int W = img.w, H = img.h;

    float r = std::min(1.0f, static_cast<float>(im.opt.det_size) / std::max(W, H));
    int dw = std::max(32, (static_cast<int>(W * r) / 32) * 32);
    int dh = std::max(32, (static_cast<int>(H * r) / 32) * 32);

    std::vector<unsigned char> rsz(static_cast<size_t>(dw) * dh * 3);
    stbir_resize_uint8(img.rgb.data(), W, H, 0, rsz.data(), dw, dh, 0, 3);

    std::vector<float> inp(static_cast<size_t>(3) * dh * dw);
    for (size_t i = 0; i < static_cast<size_t>(dh) * dw; ++i)
        for (int c = 0; c < 3; ++c) inp[static_cast<size_t>(c) * dh * dw + i] = (rsz[i * 3 + c] - 127.5f) / 128.0f;

    std::vector<int64_t> shape{1, 3, dh, dw};
    Ort::Value t = Ort::Value::CreateTensor<float>(im.mi, inp.data(), inp.size(), shape.data(), shape.size());
    const char* in_names[] = {"input.1"};
    // SCRFD det_10g: input name is "input.1"; fall back to actual name.
    Ort::AllocatorWithDefaultOptions alloc;
    std::string det_in = im.det->GetInputNameAllocated(0, alloc).get();
    in_names[0] = det_in.c_str();
    std::vector<std::string> oname_store;
    std::vector<const char*> onames;
    for (size_t i = 0; i < im.det->GetOutputCount(); ++i) oname_store.push_back(im.det->GetOutputNameAllocated(i, alloc).get());
    for (auto& s : oname_store) onames.push_back(s.c_str());
    auto outs = im.det->Run(Ort::RunOptions{nullptr}, in_names, &t, 1, onames.data(), onames.size());

    const int strides[3] = {8, 16, 32};
    const int anchors = 2;
    std::vector<Face> faces;
    const float scale = static_cast<float>(W) / dw;
    for (int si = 0; si < 3; ++si) {
        const float* sc = outs[si].GetTensorData<float>();
        const float* bb = outs[3 + si].GetTensorData<float>();
        const float* kp = outs[6 + si].GetTensorData<float>();
        int st = strides[si];
        int fh = dh / st, fw = dw / st;
        int idx = 0;
        for (int y = 0; y < fh; ++y) {
            for (int x = 0; x < fw; ++x) {
                for (int a = 0; a < anchors; ++a, ++idx) {
                    float s = sc[idx];
                    if (s < im.opt.det_thresh) continue;
                    float cx = x * st, cy = y * st;
                    Face f;
                    f.score = s;
                    f.box[0] = (cx - bb[idx * 4 + 0] * st) * scale;
                    f.box[1] = (cy - bb[idx * 4 + 1] * st) * scale;
                    f.box[2] = (cx + bb[idx * 4 + 2] * st) * scale;
                    f.box[3] = (cy + bb[idx * 4 + 3] * st) * scale;
                    for (int k = 0; k < 5; ++k) {
                        f.kps[k * 2 + 0] = (cx + kp[idx * 10 + k * 2 + 0] * st) * scale;
                        f.kps[k * 2 + 1] = (cy + kp[idx * 10 + k * 2 + 1] * st) * scale;
                    }
                    faces.push_back(f);
                }
            }
        }
    }
    std::sort(faces.begin(), faces.end(), [](const Face& a, const Face& b) { return a.score > b.score; });

    // NMS
    std::vector<Face> keep;
    std::vector<char> removed(faces.size(), 0);
    for (size_t i = 0; i < faces.size(); ++i) {
        if (removed[i]) continue;
        keep.push_back(faces[i]);
        for (size_t j = i + 1; j < faces.size(); ++j)
            if (!removed[j] && IoU(faces[i].box, faces[j].box) > im.opt.nms_thresh) removed[j] = 1;
    }
    return keep;
}

bool FaceEngine::CropLargest(const std::string& image_path, const std::string& out_path, int size) const {
    auto faces = Detect(image_path);
    if (faces.empty()) return false;
    Image img = LoadRgb(image_path);
    const Face& f = faces[0];

    // similarity transform: kps -> template*scale
    float sc = static_cast<float>(size) / 112.0f;
    float mdx = 0, mdy = 0, msx = 0, msy = 0;
    for (int k = 0; k < 5; ++k) {
        msx += f.kps[k * 2]; msy += f.kps[k * 2 + 1];
        mdx += kTemplate[k * 2] * sc; mdy += kTemplate[k * 2 + 1] * sc;
    }
    msx /= 5; msy /= 5; mdx /= 5; mdy /= 5;
    float denom = 0, num_a = 0, num_b = 0;
    for (int k = 0; k < 5; ++k) {
        float sx = f.kps[k * 2] - msx, sy = f.kps[k * 2 + 1] - msy;
        float dx = kTemplate[k * 2] * sc - mdx, dy = kTemplate[k * 2 + 1] * sc - mdy;
        denom += sx * sx + sy * sy;
        num_a += sx * dx + sy * dy;
        num_b += sx * dy - sy * dx;
    }
    float a = denom > 0 ? num_a / denom : 1.0f;
    float b = denom > 0 ? num_b / denom : 0.0f;
    float tx = mdx - (a * msx - b * msy);
    float ty = mdy - (b * msx + a * msy);
    // inverse: src = M^-1 (dst - t), M = [[a,-b],[b,a]], M^-1 = 1/d [[a,b],[-b,a]]
    float d = a * a + b * b;
    d = d > 1e-12f ? d : 1.0f;

    std::vector<unsigned char> out(static_cast<size_t>(size) * size * 3);
    for (int y = 0; y < size; ++y) {
        for (int x = 0; x < size; ++x) {
            float ux = x - tx, uy = y - ty;
            float sx = (a * ux + b * uy) / d;
            float sy = (-b * ux + a * uy) / d;
            int x0 = static_cast<int>(std::floor(sx)), y0 = static_cast<int>(std::floor(sy));
            float fx = sx - x0, fy = sy - y0;
            for (int c = 0; c < 3; ++c) {
                float v = 0;
                for (int jj = 0; jj < 2; ++jj)
                    for (int ii = 0; ii < 2; ++ii) {
                        int xx = std::min(img.w - 1, std::max(0, x0 + ii));
                        int yy = std::min(img.h - 1, std::max(0, y0 + jj));
                        float w = (ii ? fx : 1 - fx) * (jj ? fy : 1 - fy);
                        v += img.rgb[(static_cast<size_t>(yy) * img.w + xx) * 3 + c] * w;
                    }
                out[(static_cast<size_t>(y) * size + x) * 3 + c] = Clamp8(v);
            }
        }
    }
    return stbi_write_png(out_path.c_str(), size, size, 3, out.data(), size * 3) != 0;
}

bool FaceEngine::Parse(const std::string& image_path, const std::string& out_path, const std::string& mode) const {
    Impl& im = *impl_;
    Image img = LoadRgb(image_path);
    const int S = 512;
    std::vector<unsigned char> rsz(static_cast<size_t>(S) * S * 3);
    stbir_resize_uint8(img.rgb.data(), img.w, img.h, 0, rsz.data(), S, S, 0, 3);
    const float mean[3] = {0.485f, 0.456f, 0.406f}, std[3] = {0.229f, 0.224f, 0.225f};
    std::vector<float> inp(static_cast<size_t>(3) * S * S);
    for (size_t i = 0; i < static_cast<size_t>(S) * S; ++i)
        for (int c = 0; c < 3; ++c)
            inp[static_cast<size_t>(c) * S * S + i] = (rsz[i * 3 + c] / 255.0f - mean[c]) / std[c];

    std::vector<int64_t> shape{1, 3, S, S};
    Ort::Value t = Ort::Value::CreateTensor<float>(im.mi, inp.data(), inp.size(), shape.data(), shape.size());
    Ort::AllocatorWithDefaultOptions alloc;
    std::string p_in = im.parse->GetInputNameAllocated(0, alloc).get();
    std::string p_out = im.parse->GetOutputNameAllocated(0, alloc).get();
    const char* in_names[] = {p_in.c_str()};
    const char* out_names[] = {p_out.c_str()};
    auto outs = im.parse->Run(Ort::RunOptions{nullptr}, in_names, &t, 1, out_names, 1);
    const float* logits = outs[0].GetTensorData<float>();  // [1,19,512,512]
    const int C = 19;
    const int plane = S * S;

    // argmax per pixel
    auto label_at = [&](int i) {
        int best = 0; float bv = logits[i];
        for (int c = 1; c < C; ++c) {
            float v = logits[static_cast<size_t>(c) * plane + i];
            if (v > bv) { bv = v; best = c; }
        }
        return best;
    };

    // palette (19)
    static const unsigned char pal[19][3] = {
        {0,0,0},{204,0,0},{76,153,0},{0,204,0},{0,0,255},{255,255,255},{255,204,204},
        {51,51,255},{51,255,51},{204,204,0},{204,0,204},{0,204,204},{255,153,0},{255,204,0},
        {255,0,0},{255,255,204},{153,102,0},{102,0,153},{0,0,0}};
    // face region = skin(1)+brows(2,3)+eyes(4,5)+nose(10)+mouth(11)+lips(12,13)
    auto is_face = [](int c) { return c==1||c==2||c==3||c==4||c==5||c==10||c==11||c==12||c==13; };

    std::vector<unsigned char> small(static_cast<size_t>(S) * S * 3, 0);
    std::vector<unsigned char> smallgray(static_cast<size_t>(S) * S, 0);
    bool colorize = (mode == "color");
    for (int i = 0; i < plane; ++i) {
        int lb = label_at(i);
        if (colorize) {
            small[i*3] = pal[lb][0]; small[i*3+1] = pal[lb][1]; small[i*3+2] = pal[lb][2];
        } else {
            unsigned char v = 0;
            if (mode == "face") v = is_face(lb) ? 255 : 0;
            else if (mode == "skin") v = (lb == 1) ? 255 : 0;
            else if (mode == "hair") v = (lb == 17) ? 255 : 0;
            smallgray[i] = v;
        }
    }

    // resize back to original
    if (colorize) {
        std::vector<unsigned char> full(static_cast<size_t>(img.w) * img.h * 3);
        stbir_resize_uint8(small.data(), S, S, 0, full.data(), img.w, img.h, 0, 3);
        return stbi_write_png(out_path.c_str(), img.w, img.h, 3, full.data(), img.w * 3) != 0;
    }
    std::vector<unsigned char> full(static_cast<size_t>(img.w) * img.h);
    stbir_resize_uint8(smallgray.data(), S, S, 0, full.data(), img.w, img.h, 0, 1);
    return stbi_write_png(out_path.c_str(), img.w, img.h, 1, full.data(), img.w) != 0;
}

}  // namespace face
