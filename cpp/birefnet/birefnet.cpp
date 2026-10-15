// birefnet.cpp — BiRefNet background removal core (ONNX Runtime, C++).
//
// Model: onnx-community/BiRefNet_lite-ONNX (Swin backbone, ViTFeatureExtractor)
//   input  input_image  [1,3,1024,1024] f32  (resize 1024^2, /255, imagenet norm)
//   output output_image [1,1,1024,1024] f32  (raw logits -> sigmoid = alpha matte)
#include "birefnet.hpp"

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
#include <cstring>
#include <stdexcept>
#include <vector>

namespace bref {
namespace {

constexpr int kSize = 1024;
const float kMean[3] = {0.485f, 0.456f, 0.406f};
const float kStd[3] = {0.229f, 0.224f, 0.225f};

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

}  // namespace

struct BgRemover::Impl {
    Ort::Env env;
    Ort::SessionOptions so;
    std::unique_ptr<Ort::Session> session;
    Ort::MemoryInfo mi;
    std::string input_name;
    std::string output_name;
    std::string provider = "CPU";

    Impl(const std::string& model_path, bool use_cuda)
        : env(ORT_LOGGING_LEVEL_ERROR, "birefnet"), mi(Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault)) {
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
        session = std::make_unique<Ort::Session>(env, model_path.c_str(), so);
        Ort::AllocatorWithDefaultOptions alloc;
        input_name = session->GetInputNameAllocated(0, alloc).get();
        output_name = session->GetOutputNameAllocated(0, alloc).get();
    }
};

BgRemover::BgRemover(const std::string& model_path, bool use_cuda)
    : impl_(std::make_unique<Impl>(model_path, use_cuda)) {}

BgRemover::~BgRemover() = default;

const std::string& BgRemover::provider() const { return impl_->provider; }

void BgRemover::Process(const std::string& in_path, const std::string& out_path,
                        const std::string& mask_path, int mode, int r, int g, int b) {
    Impl& im = *impl_;
    Image img = LoadRgb(in_path);

    // ---- preprocess: resize 1024^2, /255, normalize, CHW ----
    std::vector<unsigned char> resized(static_cast<size_t>(kSize) * kSize * 3);
    stbir_resize_uint8(img.rgb.data(), img.w, img.h, 0, resized.data(), kSize, kSize, 0, 3);
    std::vector<float> pix(static_cast<size_t>(3) * kSize * kSize);
    const int plane = kSize * kSize;
    for (int i = 0; i < plane; ++i) {
        for (int c = 0; c < 3; ++c) {
            float v = resized[static_cast<size_t>(i) * 3 + c] / 255.0f;
            pix[static_cast<size_t>(c) * plane + i] = (v - kMean[c]) / kStd[c];
        }
    }

    // ---- run ----
    std::vector<int64_t> shape{1, 3, kSize, kSize};
    Ort::Value in = Ort::Value::CreateTensor<float>(im.mi, pix.data(), pix.size(), shape.data(), shape.size());
    const char* in_names[] = {im.input_name.c_str()};
    const char* out_names[] = {im.output_name.c_str()};
    auto outs = im.session->Run(Ort::RunOptions{nullptr}, in_names, &in, 1, out_names, 1);
    const float* logits = outs[0].GetTensorData<float>();
    size_t n = outs[0].GetTensorTypeAndShapeInfo().GetElementCount();
    if (n != static_cast<size_t>(plane)) throw std::runtime_error("unexpected BiRefNet output size");

    // ---- sigmoid matte at 1024 ----
    std::vector<float> small(plane);
    for (int i = 0; i < plane; ++i) small[i] = 1.0f / (1.0f + std::exp(-logits[i]));

    // ---- resize matte to original size ----
    std::vector<float> matte(static_cast<size_t>(img.w) * img.h);
    stbir_resize_float(small.data(), kSize, kSize, 0, matte.data(), img.w, img.h, 0, 1);

    const int W = img.w, H = img.h;
    auto clamp8 = [](float v) {
        int x = static_cast<int>(std::lround(v * 255.0f));
        return static_cast<unsigned char>(std::min(255, std::max(0, x)));
    };

    // ---- optional standalone grayscale matte ----
    if ((mode != MODE_MASK) && !mask_path.empty()) {
        std::vector<unsigned char> gray(static_cast<size_t>(W) * H);
        for (size_t i = 0; i < gray.size(); ++i) gray[i] = clamp8(matte[i]);
        stbi_write_png(mask_path.c_str(), W, H, 1, gray.data(), W);
    }

    if (mode == MODE_MASK) {
        std::vector<unsigned char> gray(static_cast<size_t>(W) * H);
        for (size_t i = 0; i < gray.size(); ++i) gray[i] = clamp8(matte[i]);
        stbi_write_png(out_path.c_str(), W, H, 1, gray.data(), W);
        return;
    }

    if (mode == MODE_TRANSPARENT) {
        std::vector<unsigned char> rgba(static_cast<size_t>(W) * H * 4);
        for (size_t i = 0; i < static_cast<size_t>(W) * H; ++i) {
            rgba[i * 4 + 0] = img.rgb[i * 3 + 0];
            rgba[i * 4 + 1] = img.rgb[i * 3 + 1];
            rgba[i * 4 + 2] = img.rgb[i * 3 + 2];
            rgba[i * 4 + 3] = clamp8(matte[i]);
        }
        stbi_write_png(out_path.c_str(), W, H, 4, rgba.data(), W * 4);
        return;
    }

    if (mode == MODE_CHECKER) {
        // Baked checkerboard (matches the usual "transparent" backdrop look).
        const int sq = 64;
        const unsigned char c1 = 200, c2 = 150;
        std::vector<unsigned char> out(static_cast<size_t>(W) * H * 3);
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                size_t i = static_cast<size_t>(y) * W + x;
                float a = matte[i];
                unsigned char bg = (((x / sq) + (y / sq)) % 2 == 0) ? c1 : c2;
                out[i * 3 + 0] = clamp8(img.rgb[i * 3 + 0] * a + bg * (1.0f - a));
                out[i * 3 + 1] = clamp8(img.rgb[i * 3 + 1] * a + bg * (1.0f - a));
                out[i * 3 + 2] = clamp8(img.rgb[i * 3 + 2] * a + bg * (1.0f - a));
            }
        }
        stbi_write_png(out_path.c_str(), W, H, 3, out.data(), W * 3);
        return;
    }

    if (mode == MODE_WHITE) { r = 255; g = 255; b = 255; }
    else if (mode == MODE_BLACK) { r = 0; g = 0; b = 0; }
    else if (mode == MODE_GREEN) { r = 0; g = 255; b = 0; }

    std::vector<unsigned char> out(static_cast<size_t>(W) * H * 3);
    for (size_t i = 0; i < static_cast<size_t>(W) * H; ++i) {
        float a = matte[i];
        out[i * 3 + 0] = clamp8(img.rgb[i * 3 + 0] * a + r * (1.0f - a));
        out[i * 3 + 1] = clamp8(img.rgb[i * 3 + 1] * a + g * (1.0f - a));
        out[i * 3 + 2] = clamp8(img.rgb[i * 3 + 2] * a + b * (1.0f - a));
    }
    stbi_write_png(out_path.c_str(), W, H, 3, out.data(), W * 3);
}

}  // namespace bref
