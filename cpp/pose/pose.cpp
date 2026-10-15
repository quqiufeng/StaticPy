// pose.cpp — YOLOv8-pose 推理（ORT），画骨架 / 输出关键点
#include "pose.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <onnxruntime_cxx_api.h>
#include <vector>
#include <array>
#include <string>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <algorithm>

namespace {
const char* model(){ if(const char* m=std::getenv("POSE_MODEL")) return m; return "/data/models/image/yolov8n-pose.onnx"; }
const int EDGES[][2] = {{0,1},{0,2},{1,3},{2,4},{5,6},{5,7},{7,9},{6,8},{8,10},{5,11},{6,12},{11,12},{11,13},{13,15},{12,14},{14,16}};
const int COLORS[][3] = {{255,0,0},{255,85,0},{255,170,0},{255,255,0},{170,255,0},{85,255,0},{0,255,0},{0,255,85},{0,255,170},{0,255,255},{0,170,255},{0,85,255},{0,0,255},{85,0,255},{170,0,255},{255,0,255}};
struct KP { float x, y, s; };
struct Person { float score; float x0,y0,x1,y1; std::vector<KP> kp; };
thread_local std::string g_json;

// 运行推理，返回最优人物（原图坐标）；letterbox 缩放 s、偏移 ox/oy
bool infer(const char* in, float thresh, int& W, int& H, Person& best, float& s, float& ox, float& oy) {
    int C; unsigned char* d = stbi_load(in, &W, &H, &C, 3);
    if (!d) return false;
    int S = 640;
    s = std::min((float)S / W, (float)S / H);
    int nw = (int)(W * s), nh = (int)(H * s);
    ox = (S - nw) / 2.0f; oy = (S - nh) / 2.0f;
    std::vector<float> input((size_t)3*S*S, 0.f);
    for (int y = 0; y < nh; ++y) for (int x = 0; x < nw; ++x) {
        int sx = (int)(x / s), sy = (int)(y / s); if (sx >= W) sx = W-1; if (sy >= H) sy = H-1;
        for (int c = 0; c < 3; ++c) input[(size_t)c*S*S + (size_t)(y+(int)oy)*S + (x+(int)ox)] = d[((size_t)sy*W+sx)*3+c]/255.f;
    }
    stbi_image_free(d);
    Ort::Env env(ORT_LOGGING_LEVEL_WARNING,"pose");
    Ort::SessionOptions so; so.SetIntraOpNumThreads(6);
    Ort::Session sess(env, model(), so);
    Ort::AllocatorWithDefaultOptions alloc;
    auto in0=sess.GetInputNameAllocated(0,alloc); auto out0=sess.GetOutputNameAllocated(0,alloc);
    Ort::MemoryInfo mi=Ort::MemoryInfo::CreateCpu(OrtArenaAllocator,OrtMemTypeDefault);
    std::array<int64_t,4> sh{1,3,S,S};
    Ort::Value tx=Ort::Value::CreateTensor<float>(mi,input.data(),input.size(),sh.data(),4);
    const char* inn[]={in0.get()}; const char* on[]={out0.get()};
    auto outs=sess.Run(Ort::RunOptions{nullptr},inn,&tx,1,on,1);
    float* o=outs[0].GetTensorMutableData<float>();  // [1,56,8400]
    const int NA=8400;
    std::vector<Person> cands;
    for (int i=0;i<NA;++i){
        float conf=o[(size_t)4*NA+i];
        if(conf<thresh) continue;
        Person p; p.score=conf;
        float cx=o[i],cy=o[NA+i],w=o[2*NA+i],h=o[3*NA+i];
        p.x0=cx-w/2;p.y0=cy-h/2;p.x1=cx+w/2;p.y1=cy+h/2;
        for(int k=0;k<17;++k){ KP q; q.x=o[(size_t)(5+3*k)*NA+i]; q.y=o[(size_t)(5+3*k+1)*NA+i]; q.s=o[(size_t)(5+3*k+2)*NA+i]; p.kp.push_back(q);} 
        cands.push_back(std::move(p));
    }
    // 简单 NMS（IoU>0.5 抑制）
    std::sort(cands.begin(),cands.end(),[](const Person&a,const Person&b){return a.score>b.score;});
    std::vector<Person> keep;
    for(auto& p:cands){ bool ok=true; for(auto& q:keep){ float ix=std::max(0.f,std::min(p.x1,q.x1)-std::max(p.x0,q.x0)), iy=std::max(0.f,std::min(p.y1,q.y1)-std::max(p.y0,q.y0)); float inter=ix*iy; float ua=(p.x1-p.x0)*(p.y1-p.y0)+(q.x1-q.x0)*(q.y1-q.y0)-inter; if(ua>0 && inter/ua>0.5f){ok=false;break;} } if(ok) keep.push_back(p); }
    if(keep.empty()) return false;
    best=keep[0];
    // 原图坐标：减 pad、除 s
    for(auto& q:best.kp){ q.x=(q.x-ox)/s; q.y=(q.y-oy)/s; }
    return true;
}
}

extern "C" {
int pose_draw(const char* in, const char* out, float thresh) {
    int W,H; Person p; float s,ox,oy;
    bool ok=infer(in,thresh,W,H,p,s,ox,oy);
    int OW=W,OH=H;
    std::vector<unsigned char> img((size_t)OW*OH*3,0);
    if(ok){
        auto line=[&](float x1,float y1,float x2,float y2,const int c[3]){
            int n=(int)std::max(std::fabs(x1-x2),std::fabs(y1-y2)); if(n<1)n=1;
            for(int t=0;t<=n;++t){ float x=x1+(x2-x1)*t/n, y=y1+(y2-y1)*t/n; if(x<0||x>=OW||y<0||y>=OH)continue; for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx){int xx=(int)x+dx,yy=(int)y+dy; if(xx<0||xx>=OW||yy<0||yy>=OH)continue; unsigned char* q=&img[((size_t)yy*OW+xx)*3]; q[0]=c[0];q[1]=c[1];q[2]=c[2];} }
        };
        for(int e=0;e<16;++e){ const KP&a=p.kp[EDGES[e][0]]; const KP&b=p.kp[EDGES[e][1]]; if(a.s>0.3f&&b.s>0.3f) line(a.x,a.y,b.x,b.y,COLORS[e]); }
        for(int k=0;k<17;++k){ const KP&q=p.kp[k]; if(q.s<=0.3f)continue; for(int dy=-3;dy<=3;++dy)for(int dx=-3;dx<=3;++dx){int xx=(int)q.x+dx,yy=(int)q.y+dy; if(xx<0||xx>=OW||yy<0||yy>=OH)continue; unsigned char* r=&img[((size_t)yy*OW+xx)*3]; r[0]=r[1]=r[2]=255;} }
    }
    return stbi_write_png(out,OW,OH,3,img.data(),OW*3) ? (ok?1:0) : -1;
}
const char* pose_keypoints_json(const char* in, float thresh){
    int W,H; Person p; float s,ox,oy;
    bool ok=infer(in,thresh,W,H,p,s,ox,oy);
    if(!ok){ g_json="[]"; return g_json.c_str(); }
    g_json="[{\"score\":"+std::to_string(p.score)+",\"keypoints\":[";
    char buf[80];
    for(int k=0;k<17;++k){ snprintf(buf,sizeof buf,"%s[%.1f,%.1f,%.2f]",k?",":"",p.kp[k].x,p.kp[k].y,p.kp[k].s); g_json+=buf; }
    g_json+="]}]";
    return g_json.c_str();
}
}  // extern "C"
