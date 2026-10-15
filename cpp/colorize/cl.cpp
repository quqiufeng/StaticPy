// cl.cpp — DDColor 上色（ORT），输入灰度→ab→Lab→RGB
#include "cl.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <array>
#include <cmath>
#include <cstdlib>

namespace {
const char* model() { if (const char* m = std::getenv("DDCOLOR_MODEL")) return m; return "/data/models/image/ddcolor-fp16.onnx"; }
inline double finv(double t) { double t3 = t*t*t; return t3 > 0.008856 ? t3 : (t - 16.0/116.0) / 7.787; }
inline unsigned char g(double v) { v = v <= 0.0031308 ? 12.92*v : 1.055*std::pow(v, 1.0/2.4) - 0.055; int x = (int)(v*255+0.5); return (unsigned char)(x<0?0:x>255?255:x); }
}
extern "C" int cl_colorize(const char* in, const char* out) {
    int W, H, C; unsigned char* d = stbi_load(in, &W, &H, &C, 3);
    if (!d) return -1;
    int S = 256;
    std::vector<unsigned char> img((size_t)S*S*3);
    stbir_resize_uint8(d, W, H, 0, img.data(), S, S, 0, 3);
    stbi_image_free(d);
    std::vector<float> input((size_t)3*S*S);
    std::vector<float> L((size_t)S*S);
    for (int y = 0; y < S; ++y) for (int x = 0; x < S; ++x) {
        unsigned char* p = &img[((size_t)y*S+x)*3];
        float l = (0.299f*p[0] + 0.587f*p[1] + 0.114f*p[2]) / 255.f;
        L[(size_t)y*S+x] = l;
        for (int c = 0; c < 3; ++c) input[(size_t)c*S*S + (size_t)y*S+x] = l;
    }
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "cl");
    Ort::SessionOptions so; so.SetIntraOpNumThreads(6);
    so.SetGraphOptimizationLevel(ORT_DISABLE_ALL);   // 规避 fp16 LayerNorm 融合 bug
    Ort::Session sess(env, model(), so);
    Ort::AllocatorWithDefaultOptions alloc;
    auto in0 = sess.GetInputNameAllocated(0, alloc); auto out0 = sess.GetOutputNameAllocated(0, alloc);
    Ort::MemoryInfo mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::array<int64_t,4> sh{1,3,S,S};
    Ort::Value tx = Ort::Value::CreateTensor<float>(mi, input.data(), input.size(), sh.data(), 4);
    const char* inn[] = {in0.get()}; const char* on[] = {out0.get()};
    auto outs = sess.Run(Ort::RunOptions{nullptr}, inn, &tx, 1, on, 1);
    float* ab = outs[0].GetTensorMutableData<float>();   // [1,2,S,S]
    std::vector<unsigned char> rgb((size_t)S*S*3);
    for (int y = 0; y < S; ++y) for (int x = 0; x < S; ++x) {
        double l = L[(size_t)y*S+x] * 100.0;
        double a = ab[(size_t)y*S+x] * 128.0;
        double b = ab[(size_t)S*S + (size_t)y*S+x] * 128.0;
        double fy = (l + 16) / 116.0, fx = fy + a/500.0, fz = fy - b/200.0;
        double X = 0.95047*finv(fx), Y = finv(fy), Z = 1.08883*finv(fz);
        double r =  3.2406*X - 1.5372*Y - 0.4986*Z;
        double gg= -0.9689*X + 1.8758*Y + 0.0415*Z;
        double bb=  0.0557*X - 0.2040*Y + 1.0570*Z;
        unsigned char* o = &rgb[((size_t)y*S+x)*3];
        o[0]=g(r); o[1]=g(gg); o[2]=g(bb);
    }
    return stbi_write_png(out, S, S, 3, rgb.data(), S*3) ? 0 : -1;
}
