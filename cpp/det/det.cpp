// det.cpp — YOLOv8 目标检测（ORT）
#include "det.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <array>
#include <string>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace {
const char* model(){ if(const char* m=std::getenv("DET_MODEL")) return m; return "/data/models/image/yolov8n.onnx"; }
const char* NAMES[]={"person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light","fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow","elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch","potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone","microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear","hair drier","toothbrush"};
struct Box{ int cls; float s, x0,y0,x1,y1; };
thread_local std::string g_json;

bool run(const char* in, float thresh, int& W, int& H, float& s, float& ox, float& oy, std::vector<Box>& out){
    int C; unsigned char* d=stbi_load(in,&W,&H,&C,3); if(!d) return false;
    int S=640; s=std::min((float)S/W,(float)S/H); int nw=(int)(W*s),nh=(int)(H*s); ox=(S-nw)/2.0f; oy=(S-nh)/2.0f;
    std::vector<float> input((size_t)3*S*S,0.f);
    for(int y=0;y<nh;++y)for(int x=0;x<nw;++x){int sx=(int)(x/s),sy=(int)(y/s); if(sx>=W)sx=W-1; if(sy>=H)sy=H-1; for(int c=0;c<3;++c) input[(size_t)c*S*S+(size_t)(y+(int)oy)*S+(x+(int)ox)]=d[((size_t)sy*W+sx)*3+c]/255.f;}
    stbi_image_free(d);
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"det"); Ort::SessionOptions so; so.SetIntraOpNumThreads(6);
    Ort::Session sess(env,model(),so); Ort::AllocatorWithDefaultOptions alloc;
    auto i0=sess.GetInputNameAllocated(0,alloc); auto o0=sess.GetOutputNameAllocated(0,alloc);
    Ort::MemoryInfo mi=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
    std::array<int64_t,4> sh{1,3,S,S}; Ort::Value tx=Ort::Value::CreateTensor<float>(mi,input.data(),input.size(),sh.data(),4);
    const char* inn[]={i0.get()}; const char* on[]={o0.get()};
    auto outs=sess.Run(Ort::RunOptions{nullptr},inn,&tx,1,on,1); float* o=outs[0].GetTensorMutableData<float>(); // [1,84,8400]
    const int NA=8400, NC=80;
    std::vector<Box> cands;
    for(int i=0;i<NA;++i){ float best=0; int bc=0; for(int c=0;c<NC;++c){ float v=o[(size_t)(4+c)*NA+i]; if(v>best){best=v;bc=c;} } if(best<thresh) continue; Box b; b.cls=bc;b.s=best; float cx=o[i],cy=o[NA+i],w=o[2*NA+i],h=o[3*NA+i]; b.x0=(cx-w/2-ox)/s;b.y0=(cy-h/2-oy)/s;b.x1=(cx+w/2-ox)/s;b.y1=(cy+h/2-oy)/s; cands.push_back(b); }
    std::sort(cands.begin(),cands.end(),[](const Box&a,const Box&b){return a.s>b.s;});
    std::vector<Box> keep;
    for(auto& p:cands){ bool ok=true; for(auto& q:keep){ if(p.cls!=q.cls)continue; float ix=std::max(0.f,std::min(p.x1,q.x1)-std::max(p.x0,q.x0)),iy=std::max(0.f,std::min(p.y1,q.y1)-std::max(p.y0,q.y0)); float u=(p.x1-p.x0)*(p.y1-p.y0)+(q.x1-q.x0)*(q.y1-q.y0)-ix*iy; if(u>0&&ix*iy/u>0.45f){ok=false;break;} } if(ok) keep.push_back(p); }
    out=keep; return true;
}
void draw_box(std::vector<unsigned char>& im,int W,int H,float x0,float y0,float x1,float y1,int cl){
    int c[3]={ (cl*53)%256,(cl*97)%256,(cl*191)%256 };
    auto px=[&](int x,int y){ if(x<0||x>=W||y<0||y>=H)return; unsigned char* q=&im[((size_t)y*W+x)*3]; q[0]=c[0];q[1]=c[1];q[2]=c[2]; };
    for(int x=(int)x0;x<=(int)x1;++x){ for(int t=0;t<2;++t){ px(x,(int)y0+t); px(x,(int)y1-t);} }
    for(int y=(int)y0;y<=(int)y1;++y){ for(int t=0;t<2;++t){ px((int)x0+t,y); px((int)x1-t,y);} }
}
}
extern "C" {
const char* det_json(const char* in, float thresh){
    int W,H; float s,ox,oy; std::vector<Box> b;
    if(!run(in,thresh,W,H,s,ox,oy,b)){ g_json="[]"; return g_json.c_str(); }
    g_json="["; char buf[160];
    for(size_t i=0;i<b.size();++i){ Box& q=b[i]; snprintf(buf,sizeof buf,"%s{\"label\":\"%s\",\"score\":%.2f,\"box\":[%.0f,%.0f,%.0f,%.0f]}",i?",":"",NAMES[q.cls],q.s,q.x0,q.y0,q.x1,q.y1); g_json+=buf; }
    g_json+="]"; return g_json.c_str();
}
int det_draw(const char* in, const char* out, float thresh){
    int W,H; float s,ox,oy; std::vector<Box> b;
    if(!run(in,thresh,W,H,s,ox,oy,b)) return -1;
    int C; unsigned char* d=stbi_load(in,&W,&H,&C,3); if(!d) return -1;
    std::vector<unsigned char> im(d,d+(size_t)W*H*3); stbi_image_free(d);
    for(auto& q:b) draw_box(im,W,H,q.x0,q.y0,q.x1,q.y1,q.cls);
    return stbi_write_png(out,W,H,3,im.data(),W*3) ? (int)b.size() : -1;
}
}
