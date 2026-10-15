// sr.cpp — Real-ESRGAN x4 推理（ONNX Runtime C++），文件进文件出
#include "sr.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <cstdlib>
#include <cstring>
#include <string>

namespace {
const char* model_path() {
    if (const char* m = std::getenv("SR_MODEL")) return m;
    return "/data/models/image/realesr-general-x4v3.onnx";
}
int pad_to(int v, int m) { return ((v + m - 1) / m) * m; }
}

extern "C" int sr_upscale(const char* in, const char* out) {
    int W, H, C; unsigned char* data = stbi_load(in, &W, &H, &C, 3);
    if (!data) return -1;
    int PW = pad_to(W, 32), PH = pad_to(H, 32);
    std::vector<float> input((size_t)3 * PH * PW, 0.f);
    for (int y = 0; y < PH; ++y) for (int x = 0; x < PW; ++x) {
        int sx = x < W ? x : W - 1, sy = y < H ? y : H - 1;
        for (int c = 0; c < 3; ++c) input[(size_t)c * PH * PW + (size_t)y * PW + x] = data[((size_t)sy * W + sx) * 3 + c] / 255.f;
    }
    stbi_image_free(data);

    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "sr");
    Ort::SessionOptions so; so.SetIntraOpNumThreads(4);
    Ort::Session sess(env, model_path(), so);
    Ort::AllocatorWithDefaultOptions alloc;
    auto in_name = sess.GetInputNameAllocated(0, alloc); auto out_name = sess.GetOutputNameAllocated(0, alloc);
    std::array<int64_t, 4> shape{1, 3, PH, PW};
    Ort::MemoryInfo mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value tin = Ort::Value::CreateTensor<float>(mi, input.data(), input.size(), shape.data(), 4);
    const char* in_names[] = {in_name.get()}; const char* out_names[] = {out_name.get()};
    auto outs = sess.Run(Ort::RunOptions{nullptr}, in_names, &tin, 1, out_names, 1);
    float* o = outs[0].GetTensorMutableData<float>();
    auto oshape = outs[0].GetTensorTypeAndShapeInfo().GetShape();
    int OW = (int)oshape[3], OH = (int)oshape[2];
    std::vector<unsigned char> img((size_t)OW * OH * 3);
    for (int y = 0; y < OH; ++y) for (int x = 0; x < OW; ++x) for (int c = 0; c < 3; ++c) {
        float v = o[(size_t)c * OH * OW + (size_t)y * OW + x] * 255.f;
        img[((size_t)y * OW + x) * 3 + c] = (unsigned char)(v < 0 ? 0 : v > 255 ? 255 : v + 0.5f);
    }
    return stbi_write_png(out, OW, OH, 3, img.data(), OW * 3) ? 0 : -1;
}
