// imgproc_internal.h — 库内部共享：图像模型 + 公共工具（不对 StaticPy 暴露）
#pragma once
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cctype>
#include <string>
#include <vector>
#include <algorithm>

#include "gif_lib.h"

struct RGB { uint8_t r, g, b; };

struct Frame {
    int bpp = 4;                          // 4=RGBA, 1=索引
    int delay = 100;                      // 毫秒
    int transparent = NO_TRANSPARENT_COLOR;
    std::vector<uint8_t> data;            // w*h*bpp
    std::vector<RGB> palette;             // bpp==1
    bool hasPalette = false;
};

struct Image {
    int w = 0, h = 0, n = 0, loop = 0;
    std::string mode = "RGBA";
    std::vector<Frame> frames;
};

struct Font {
    std::vector<unsigned char> ttf;
    void* info = nullptr;                 // stbtt_fontinfo*
    float px = 16, scale = 1, ascent = 0, descent = 0, linegap = 0;
    const unsigned char* data = nullptr;  // ttf.data()
};

// ---------- 数值工具 ----------
inline int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline uint8_t clamp8(float v) { return (uint8_t)(v < 0 ? 0 : (v > 255 ? 255 : v + 0.5f)); }

inline int pack_rgba(int r, int g, int b, int a) {
    return ((r & 0xFF) << 24) | ((g & 0xFF) << 16) | ((b & 0xFF) << 8) | (a & 0xFF);
}
inline int CH_R(int c) { return (c >> 24) & 0xFF; }
inline int CH_G(int c) { return (c >> 16) & 0xFF; }
inline int CH_B(int c) { return (c >> 8) & 0xFF; }
inline int CH_A(int c) { return c & 0xFF; }

// ---------- 图像构造 / 转换 ----------
Image* new_rgba(int w, int h, int n = 1);
Image* to_rgba(Image* im);                 // 返回新的 RGBA 图（调用者释放）
Image* dup_img(Image* im);                 // 深拷贝
void   idx_to_rgba(const Frame& fr, int w, int h, std::vector<uint8_t>& out);
inline uint8_t* px(Image* im, int f, int x, int y) {
    return im->frames[f].data.data() + ((size_t)y * im->w + x) * 4;
}
inline size_t npx(Image* im) { return (size_t)im->w * im->h; }

// ---------- 编解码 ----------
Image* decode_gif(const char* path);
int    encode_gif(Image* im, const char* path);
bool   ends_with(const char* s, const char* suf);

// ---------- 解析参数 ----------
std::vector<int> parse_csv_ints(const char* s);      // "1,2,3"
std::vector<float> parse_csv_floats(const char* s);
