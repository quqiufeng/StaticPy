// cvops.cpp — 自实现经典算法（不依赖 OpenCV）
#include "cvops.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <vector>
#include <cstdint>
#include <algorithm>

namespace {
struct Gray { int w, h; std::vector<uint8_t> p; };
bool load_gray(const char* path, Gray& g) {
    int w, h, c; unsigned char* d = stbi_load(path, &w, &h, &c, 1);
    if (!d) return false;
    g.w = w; g.h = h; g.p.assign(d, d + (size_t)w * h);
    stbi_image_free(d); return true;
}
bool load_rgb(const char* path, int& w, int& h, std::vector<uint8_t>& px) {
    int c; unsigned char* d = stbi_load(path, &w, &h, &c, 3);
    if (!d) return false;
    px.assign(d, d + (size_t)w * h * 3); stbi_image_free(d); return true;
}
int save_gray(const char* path, const Gray& g) { return stbi_write_png(path, g.w, g.h, 1, g.p.data(), g.w) ? 0 : -1; }

Gray morph(const Gray& in, int k, bool dilate) {
    Gray out; out.w = in.w; out.h = in.h; out.p.assign(in.p.size(), 0);
    int r = k / 2;
    for (int y = 0; y < in.h; ++y) for (int x = 0; x < in.w; ++x) {
        uint8_t best = dilate ? 0 : 255;
        for (int j = -r; j <= r; ++j) for (int i = -r; i <= r; ++i) {
            int xx = x + i, yy = y + j; if (xx < 0 || xx >= in.w || yy < 0 || yy >= in.h) continue;
            uint8_t v = in.p[(size_t)yy * in.w + xx];
            best = dilate ? std::max(best, v) : std::min(best, v);
        }
        out.p[(size_t)y * in.w + x] = best;
    }
    return out;
}
}

extern "C" {

int cvo_erode(const char* in, const char* out, int k) { Gray g; if (!load_gray(in, g)) return -1; return save_gray(out, morph(g, k, false)); }
int cvo_dilate(const char* in, const char* out, int k) { Gray g; if (!load_gray(in, g)) return -1; return save_gray(out, morph(g, k, true)); }
int cvo_open(const char* in, const char* out, int k) { Gray g; if (!load_gray(in, g)) return -1; Gray e = morph(g, k, false); return save_gray(out, morph(e, k, true)); }
int cvo_close(const char* in, const char* out, int k) { Gray g; if (!load_gray(in, g)) return -1; Gray d = morph(g, k, true); return save_gray(out, morph(d, k, false)); }

int cvo_threshold_otsu(const char* in, const char* out, int inv) {
    Gray g; if (!load_gray(in, g)) return -1;
    long hist[256] = {0}; for (uint8_t v : g.p) hist[v]++;
    long total = (long)g.p.size();
    double sum = 0; for (int i = 0; i < 256; ++i) sum += (double)i * hist[i];
    double sumB = 0; long wB = 0; double maxVar = -1; int thr = 0;
    for (int t = 0; t < 256; ++t) {
        wB += hist[t]; if (!wB) continue; long wF = total - wB; if (!wF) break;
        sumB += (double)t * hist[t];
        double mB = sumB / wB, mF = (sum - sumB) / wF;
        double var = (double)wB * wF * (mB - mF) * (mB - mF);
        if (var > maxVar) { maxVar = var; thr = t; }
    }
    Gray o = g;
    for (auto& v : o.p) { bool hi = v > thr; if (inv) hi = !hi; v = hi ? 255 : 0; }
    return save_gray(out, o);
}

int cvo_sobel(const char* in, const char* out, int dx, int dy) {
    Gray g; if (!load_gray(in, g)) return -1;
    Gray o = g;
    for (int y = 0; y < g.h; ++y) for (int x = 0; x < g.w; ++x) {
        int gx = 0, gy = 0;
        auto at = [&](int xx, int yy) { xx = std::clamp(xx, 0, g.w - 1); yy = std::clamp(yy, 0, g.h - 1); return (int)g.p[(size_t)yy * g.w + xx]; };
        if (dx) { gx = (at(x+1,y-1)+2*at(x+1,y)+at(x+1,y+1)) - (at(x-1,y-1)+2*at(x-1,y)+at(x-1,y+1)); }
        if (dy) { gy = (at(x-1,y+1)+2*at(x,y+1)+at(x+1,y+1)) - (at(x-1,y-1)+2*at(x,y-1)+at(x+1,y-1)); }
        int mag = (int)std::lround(std::sqrt((double)gx*gx + (double)gy*gy));
        o.p[(size_t)y * g.w + x] = (uint8_t)std::min(255, mag);
    }
    return save_gray(out, o);
}

int cvo_erode_rgb(const char* in, const char* out, int k) {
    int w, h; std::vector<uint8_t> px; if (!load_rgb(in, w, h, px)) return -1;
    int r = k / 2; std::vector<uint8_t> o(px.size(), 0);
    for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) for (int c = 0; c < 3; ++c) {
        uint8_t best = 255;
        for (int j = -r; j <= r; ++j) for (int i = -r; i <= r; ++i) { int xx = std::clamp(x+i,0,w-1), yy = std::clamp(y+j,0,h-1); best = std::min(best, px[((size_t)yy*w+xx)*3+c]); }
        o[((size_t)y*w+x)*3+c] = best;
    }
    return stbi_write_png(out, w, h, 3, o.data(), w*3) ? 0 : -1;
}
int cvo_dilate_rgb(const char* in, const char* out, int k) {
    int w, h; std::vector<uint8_t> px; if (!load_rgb(in, w, h, px)) return -1;
    int r = k / 2; std::vector<uint8_t> o(px.size(), 0);
    for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) for (int c = 0; c < 3; ++c) {
        uint8_t best = 0;
        for (int j = -r; j <= r; ++j) for (int i = -r; i <= r; ++i) { int xx = std::clamp(x+i,0,w-1), yy = std::clamp(y+j,0,h-1); best = std::max(best, px[((size_t)yy*w+xx)*3+c]); }
        o[((size_t)y*w+x)*3+c] = best;
    }
    return stbi_write_png(out, w, h, 3, o.data(), w*3) ? 0 : -1;
}

}  // extern "C"
