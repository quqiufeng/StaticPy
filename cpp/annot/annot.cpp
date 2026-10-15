// annot.cpp — ControlNet 标注器（depth-anything / HED / MLSD），ORT
#include "annot.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#define STB_IMAGE_RESIZE_IMPLEMENTATION
#include "stb_image_resize.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace {
const char* M(const char* env, const char* def){ const char* e=std::getenv(env); return e?e:def; }
struct Model { Ort::Env env; Ort::Session sess; Ort::AllocatorWithDefaultOptions alloc; };
// 通用：读图→(预处理)→跑→取 out idx→归一→写灰图
int run(const char* in, const char* out, const char* modelpath, int size, const float* mean, const float* std, int norm255, int invert, int outidx, int raw255) {
    int W,H,C; unsigned char* d=stbi_load(in,&W,&H,&C,3); if(!d) return -1;
    int S=size;
    std::vector<unsigned char> img((size_t)S*S*3);
    stbir_resize_uint8(d,W,H,0,img.data(),S,S,0,3); stbi_image_free(d);
    std::vector<float> input((size_t)3*S*S);
    for(int i=0;i<S*S;++i) for(int c=0;c<3;++c){ float v=raw255? (float)img[i*3+c] : img[i*3+c]/255.f; if(mean) v=(v-mean[c])/std[c]; input[(size_t)c*S*S+i]=v; }
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"an"); Ort::SessionOptions so; so.SetIntraOpNumThreads(6);
    Ort::Session sess(env,modelpath,so); Ort::AllocatorWithDefaultOptions alloc;
    auto i0=sess.GetInputNameAllocated(0,alloc); auto o0=sess.GetOutputNameAllocated(outidx,alloc);
    Ort::MemoryInfo mi=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
    std::array<int64_t,4> sh{1,3,S,S}; Ort::Value tx=Ort::Value::CreateTensor<float>(mi,input.data(),input.size(),sh.data(),4);
    const char* inn[]={i0.get()}; const char* on[]={o0.get()};
    auto outs=sess.Run(Ort::RunOptions{nullptr},inn,&tx,1,on,1);
    float* o=outs[0].GetTensorMutableData<float>();
    auto os=outs[0].GetTensorTypeAndShapeInfo().GetShape(); int OH=(int)os[os.size()-2], OW=(int)os[os.size()-1];
    float lo=1e30f,hi=-1e30f; for(int i=0;i<OW*OH;++i){ lo=std::min(lo,o[i]); hi=std::max(hi,o[i]); }
    std::vector<unsigned char> gray((size_t)OW*OH);
    for(int i=0;i<OW*OH;++i){ float t = norm255 ? std::min(1.f,std::max(0.f,o[i])) : (hi>lo?(o[i]-lo)/(hi-lo):0.f); if(invert) t=1-t; gray[i]=(unsigned char)(t*255+0.5f); }
    // 还原到原图尺寸
    std::vector<unsigned char> big((size_t)W*H);
    stbir_resize_uint8(gray.data(),OW,OH,0,big.data(),W,H,0,1);
    return stbi_write_png(out,W,H,1,big.data(),W) ? 0 : -1;
}
}
extern "C" {
int an_depth(const char* in, const char* out){
    static const float mean[3]={0.485f,0.456f,0.406f}, stdv[3]={0.229f,0.224f,0.225f};
    return run(in,out,M("DEPTH_MODEL","/data/models/image/depth_anything_v2_small/model.onnx"),518,mean,stdv,0,1,0,0);
}
int an_hed(const char* in, const char* out){
    // HED(ControlNet annotators)：输入 0..1，取 out0
    return run(in,out,M("HED_MODEL","/data/models/image/annotators/hed.onnx"),512,nullptr,nullptr,0,0,0,1);
}

}
