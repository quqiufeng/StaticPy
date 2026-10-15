// cf.cpp — CodeFormer 推理（ONNX Runtime C++），文件进文件出（内部 resize 到 512）
#include "cf.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <cstdlib>
#include <string>
#include <array>

namespace {
const char* model() {
    if (const char* m = std::getenv("CODEFORMER_MODEL")) return m;
    return "/data/models/image/codeformer.onnx";
}
}
extern "C" int cf_restore(const char* in, const char* out, double w) {
    int W, H, C; unsigned char* d = stbi_load(in, &W, &H, &C, 3);
    if (!d) return -1;
    int S = 512;
    std::vector<unsigned char> img((size_t)S * S * 3);
    stbir_resize_uint8(d, W, H, 0, img.data(), S, S, 0, 3);
    stbi_image_free(d);
    std::vector<float> input((size_t)3 * S * S);
    for (int y = 0; y < S; ++y) for (int x = 0; x < S; ++x) for (int c = 0; c < 3; ++c)
        input[(size_t)c * S * S + (size_t)y * S + x] = img[((size_t)y * S + x) * 3 + c] / 255.f;

    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "cf");
    Ort::SessionOptions so; so.SetIntraOpNumThreads(6);
    Ort::Session sess(env, model(), so);
    Ort::AllocatorWithDefaultOptions alloc;
    auto in0 = sess.GetInputNameAllocated(0, alloc);   // x
    auto in1 = sess.GetInputNameAllocated(1, alloc);   // w
    auto out0 = sess.GetOutputNameAllocated(0, alloc);  // y
    Ort::MemoryInfo mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::array<int64_t,4> sh{1,3,S,S};
    Ort::Value tx = Ort::Value::CreateTensor<float>(mi, input.data(), input.size(), sh.data(), 4);
    std::array<int64_t,0> wsh{};
    Ort::Value tw = Ort::Value::CreateTensor<double>(mi, &w, 1, wsh.data(), 0);
    const char* inn[] = {in0.get(), in1.get()};
    Ort::Value tins[] = {std::move(tx), std::move(tw)};
    const char* on[] = {out0.get()};
    auto outs = sess.Run(Ort::RunOptions{nullptr}, inn, tins, 2, on, 1);
    float* o = outs[0].GetTensorMutableData<float>();
    auto os = outs[0].GetTensorTypeAndShapeInfo().GetShape();
    int OW = (int)os[3], OH = (int)os[2];
    std::vector<unsigned char> res((size_t)OW * OH * 3);
    for (int y = 0; y < OH; ++y) for (int x = 0; x < OW; ++x) for (int c = 0; c < 3; ++c) {
        float v = o[(size_t)c * OH * OW + (size_t)y * OW + x] * 255.f;
        res[((size_t)y * OW + x) * 3 + c] = (unsigned char)(v < 0 ? 0 : v > 255 ? 255 : v + 0.5f);
    }
    return stbi_write_png(out, OW, OH, 3, res.data(), OW * 3) ? 0 : -1;
}
