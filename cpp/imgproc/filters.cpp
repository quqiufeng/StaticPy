// filters.cpp — ImageFilter（对齐 Pillow kernel/公式）+ ImageStat
#include "imgproc.h"
#include "imgproc_internal.h"

namespace {
Image* as_rgba(Image* im) { return im->frames.empty() || im->frames[0].bpp == 4 ? im : to_rgba(im); }

// 通用 NxN 卷积。严格对齐 Pillow ImagingFilter.c：
//   - 边界像素复制原值（不参与卷积）
//   - 浮点累加：ss = (offset+0.5) + Σ kernel*px/scale，截断到 [0,255]
//   - 3x3 的行方向对 kernel 做垂直翻转（Pillow 的既有行为）；5x5 不翻
Image* convolve(Image* rg, const int* k, int kw, int kh, int scale, int offset) {
    Image* o = new_rgba(rg->w, rg->h, rg->n); o->loop = rg->loop;
    int W = rg->w, H = rg->h, rx = kw / 2, ry = kh / 2;
    const float off = offset + 0.5f;
    for (int f = 0; f < rg->n; ++f) {
        uint8_t* s = rg->frames[f].data.data(); uint8_t* d = o->frames[f].data.data();
        // 先整帧复制，再只算内部区域（等价于 Pillow 的边界复制）
        memcpy(d, s, (size_t)W * H * 4);
        for (int y = ry; y < H - ry; ++y) for (int x = rx; x < W - rx; ++x) {
            for (int c = 0; c < 3; ++c) {
                float ss = off;
                for (int j = 0; j < kh; ++j) {
                    int yy = (kh == 3) ? (y + ry - j) : (y + j - ry);
                    for (int i = 0; i < kw; ++i) {
                        int xx = x + i - rx;
                        ss += (float)k[j * kw + i] * (float)s[((size_t)yy * W + xx) * 4 + c] / (float)scale;
                    }
                }
                d[((size_t)y * W + x) * 4 + c] = (uint8_t)(ss < 0 ? 0 : (ss > 255 ? 255 : ss));
            }
        }
    }
    return o;
}

// Pillow BoxBlur.c 精确移植：分数半径滑窗盒模糊（uint32 定点 + 边界复制）
static double gauss_box_radius(double radius, int passes) {
    double sigma2 = radius * radius / passes;
    double L = sqrt(12.0 * sigma2 + 1.0);
    double l = floor((L - 1.0) / 2.0);
    double a = (2 * l + 1) * (l * (l + 1) - 3 * sigma2);
    a /= 6 * (sigma2 - (l + 1) * (l + 1));
    return l + a;
}

static Image* horiz_box_blur(Image* rg, double floatRadius) {
    int W = rg->w, H = rg->h;
    Image* o = new_rgba(W, H, rg->n); o->loop = rg->loop;
    int radius = (int)floatRadius;
    uint32_t ww = (uint32_t)((double)(1u << 24) / (floatRadius * 2.0 + 1.0));
    uint32_t fw = (uint32_t)(((double)(1u << 24) - (double)(radius * 2 + 1) * (double)ww) / 2.0);
    int lastx = W - 1;
    int edgeA = std::min(radius + 1, W);
    int edgeB = std::max(W - radius - 1, 0);
    for (int f = 0; f < rg->n; ++f) {
        const uint8_t* base = rg->frames[f].data.data(); uint8_t* ob = o->frames[f].data.data();
        for (int y = 0; y < H; ++y) {
            const uint8_t* in = base + (size_t)y * W * 4; uint8_t* out = ob + (size_t)y * W * 4;
            uint32_t acc[4];
            for (int c = 0; c < 4; ++c) acc[c] = (uint32_t)in[c] * (radius + 1);
            for (int x = 0; x < edgeA - 1; ++x) for (int c = 0; c < 4; ++c) acc[c] += in[x * 4 + c];
            for (int c = 0; c < 4; ++c) acc[c] += (uint32_t)in[lastx * 4 + c] * (uint32_t)(radius - edgeA + 1);
            uint32_t bulk[4];
            auto move = [&](int sub, int add) { for (int c = 0; c < 4; ++c) acc[c] += in[add * 4 + c] - in[sub * 4 + c]; };
            auto addfar = [&](int left, int right) { for (int c = 0; c < 4; ++c) bulk[c] = acc[c] * ww + (uint32_t)(in[left * 4 + c] + in[right * 4 + c]) * fw; };
            auto save = [&](int x) { for (int c = 0; c < 4; ++c) out[x * 4 + c] = (uint8_t)((bulk[c] + (1u << 23)) >> 24); };
            if (edgeA <= edgeB) {
                for (int x = 0; x < edgeA; ++x) { move(0, x + radius); addfar(0, x + radius + 1); save(x); }
                for (int x = edgeA; x < edgeB; ++x) { move(x - radius - 1, x + radius); addfar(x - radius - 1, x + radius + 1); save(x); }
                for (int x = edgeB; x <= lastx; ++x) { move(x - radius - 1, lastx); addfar(x - radius - 1, lastx); save(x); }
            } else {
                for (int x = 0; x < edgeB; ++x) { move(0, x + radius); addfar(0, x + radius + 1); save(x); }
                for (int x = edgeB; x < edgeA; ++x) { move(0, lastx); addfar(0, lastx); save(x); }
                for (int x = edgeA; x <= lastx; ++x) { move(x - radius - 1, lastx); addfar(x - radius - 1, lastx); save(x); }
            }
        }
    }
    return o;
}

static Image* box_blur_exact(Image* rg, double xr, double yr, int n) {
    Image* cur = dup_img(rg);
    if (xr != 0) for (int i = 0; i < n; ++i) { Image* nx = horiz_box_blur(cur, xr); delete cur; cur = nx; }
    if (yr != 0) {
        Image* tr = (Image*)img_transpose(cur, 5);   // TRANSPOSE
        for (int i = 0; i < n; ++i) { Image* nx = horiz_box_blur(tr, yr); delete tr; tr = nx; }
        Image* back = (Image*)img_transpose(tr, 5);
        delete tr; delete cur; cur = back;
    }
    return cur;
}

static Image* gaussian_blur_r(Image* rg, float radius) {
    if (radius <= 0) return dup_img(rg);
    double r = gauss_box_radius(radius, 3);
    return box_blur_exact(rg, r, r, 3);
}

Image* rank_filter(Image* rg, int size, int mode) {
    int W = rg->w, H = rg->h, r = size / 2;
    Image* o = new_rgba(W, H, rg->n); o->loop = rg->loop;
    int rank = size * size / 2;
    std::vector<int> vals;
    for (int f = 0; f < rg->n; ++f) {
        uint8_t* s = rg->frames[f].data.data(); uint8_t* d = o->frames[f].data.data();
        for (int y = 0; y < H; ++y) for (int x = 0; x < W; ++x) {
            for (int c = 0; c < 3; ++c) {
                vals.clear();
                for (int j = -r; j <= r; ++j) for (int i = -r; i <= r; ++i) { int xx = clampi(x + i, 0, W - 1), yy = clampi(y + j, 0, H - 1); vals.push_back(s[((size_t)yy * W + xx) * 4 + c]); }
                std::sort(vals.begin(), vals.end());
                int v;
                if (mode == 0) v = vals.front();
                else if (mode == 1) v = vals.back();
                else if (mode == 4) v = vals[std::min(rank, (int)vals.size() - 1)];
                else if (mode == 3) { int best = vals[0], bc = 0, cur = vals[0], cc = 0; for (int t : vals) { if (t == cur) cc++; else { if (cc > bc) { bc = cc; best = cur; } cur = t; cc = 1; } } if (cc > bc) best = cur; v = best; }
                else v = vals[vals.size() / 2];
                d[((size_t)y * W + x) * 4 + c] = (uint8_t)v;
            }
            d[((size_t)y * W + x) * 4 + 3] = s[((size_t)y * W + x) * 4 + 3];
        }
    }
    return o;
}
}  // namespace

extern "C" {

void* img_filter(void* p, const char* name, float r1, float r2, int i1) {
    Image* im = (Image*)p; if (!im || !name) return nullptr;
    std::string n = name;
    Image* rg = as_rgba(im);
    Image* out = nullptr;
    static const int BLUR[25] = {1,1,1,1,1, 1,0,0,0,1, 1,0,0,0,1, 1,0,0,0,1, 1,1,1,1,1};
    static const int SMOOTH[9] = {1,1,1, 1,5,1, 1,1,1};
    static const int SMOOTH_MORE[25] = {1,1,1,1,1, 1,5,5,5,1, 1,5,44,5,1, 1,5,5,5,1, 1,1,1,1,1};
    static const int DETAIL[9] = {0,-1,0, -1,10,-1, 0,-1,0};
    static const int SHARPEN[9] = {-2,-2,-2, -2,32,-2, -2,-2,-2};
    static const int EE[9] = {-1,-1,-1, -1,10,-1, -1,-1,-1};
    static const int EEM[9] = {-1,-1,-1, -1,9,-1, -1,-1,-1};
    static const int FE[9] = {-1,-1,-1, -1,8,-1, -1,-1,-1};
    static const int EMB[9] = {-1,0,0, 0,1,0, 0,0,0};
    if (n == "BLUR") out = convolve(rg, BLUR, 5, 5, 16, 0);
    else if (n == "SMOOTH") out = convolve(rg, SMOOTH, 3, 3, 13, 0);
    else if (n == "SMOOTH_MORE") out = convolve(rg, SMOOTH_MORE, 5, 5, 100, 0);
    else if (n == "DETAIL") out = convolve(rg, DETAIL, 3, 3, 6, 0);
    else if (n == "SHARPEN") out = convolve(rg, SHARPEN, 3, 3, 16, 0);
    else if (n == "EDGE_ENHANCE") out = convolve(rg, EE, 3, 3, 2, 0);
    else if (n == "EDGE_ENHANCE_MORE") out = convolve(rg, EEM, 3, 3, 1, 0);
    else if (n == "FIND_EDGES") out = convolve(rg, FE, 3, 3, 1, 0);
    else if (n == "CONTOUR") out = convolve(rg, FE, 3, 3, 1, 255);
    else if (n == "EMBOSS") out = convolve(rg, EMB, 3, 3, 1, 128);
    else if (n == "BoxBlur") out = box_blur_exact(rg, r1 > 0 ? r1 : 1.0, r1 > 0 ? r1 : 1.0, 1);
    else if (n == "GaussianBlur") out = gaussian_blur_r(rg, r1 > 0 ? r1 : 2);
    else if (n == "UnsharpMask") {
        float radius = r1 > 0 ? r1 : 2, percent = r2 > 0 ? r2 : 150; int threshold = i1;
        Image* bl = gaussian_blur_r(rg, radius);
        out = dup_img(rg);
        for (int f = 0; f < out->n; ++f) { uint8_t* s = out->frames[f].data.data(); uint8_t* b = bl->frames[f].data.data(); for (size_t i = 0; i < npx(rg); ++i) for (int c = 0; c < 3; ++c) { int diff = s[i * 4 + c] - b[i * 4 + c]; if (abs(diff) * 100 / 255 < threshold) continue; s[i * 4 + c] = clamp8(s[i * 4 + c] + diff * percent / 100.0f); } }
        delete bl;
    }
    else if (n == "MedianFilter") out = rank_filter(rg, i1 > 0 ? i1 : 3, 2);
    else if (n == "MinFilter") out = rank_filter(rg, i1 > 0 ? i1 : 3, 0);
    else if (n == "MaxFilter") out = rank_filter(rg, i1 > 0 ? i1 : 3, 1);
    else if (n == "ModeFilter") out = rank_filter(rg, i1 > 0 ? i1 : 3, 3);
    else if (n == "RankFilter") out = rank_filter(rg, i1 > 0 ? i1 : 3, 4);
    else out = convolve(rg, SMOOTH, 3, 3, 13, 0);
    if (rg != im) delete rg;
    return out;
}

int img_stat(void* p, const char* what, char* out, int outlen) {
    Image* im = (Image*)p; if (!im || !what || !out) return -1;
    std::string w = what;
    Image* rg = as_rgba(im);
    std::string s;
    for (int c = 0; c < 4; ++c) {
        std::vector<int> vals;
        for (size_t i = 0; i < npx(rg); ++i) vals.push_back(rg->frames[0].data[i * 4 + c]);
        double res = 0;
        if (w == "mean") { long t = 0; for (int v : vals) t += v; res = (double)t / vals.size(); }
        else if (w == "sum") { long t = 0; for (int v : vals) t += v; res = (double)t; }
        else if (w == "median") { std::sort(vals.begin(), vals.end()); res = vals[vals.size() / 2]; }
        else if (w == "extrema") { auto mm = std::minmax_element(vals.begin(), vals.end()); res = *mm.first; }
        else if (w == "stddev") { double m = 0; for (int v : vals) m += v; m /= vals.size(); double ss = 0; for (int v : vals) ss += (v - m) * (v - m); res = sqrt(ss / vals.size()); }
        char buf[64];
        if (w == "mean" || w == "stddev") snprintf(buf, 64, "%.6f", res); else snprintf(buf, 64, "%d", (int)(res + 0.5));
        if (c) s += ","; s += buf;
    }
    if (rg != im) delete rg;
    if ((int)s.size() >= outlen) s.resize(outlen - 1);
    strcpy(out, s.c_str()); return 0;
}

int img_getextrema(void* p, char* out, int outlen) {
    Image* im = (Image*)p; if (!im || !out) return -1;
    Image* rg = as_rgba(im);
    int mn[4] = {255, 255, 255, 255}, mx[4] = {0, 0, 0, 0};
    for (size_t i = 0; i < npx(rg); ++i) for (int c = 0; c < 4; ++c) { int v = rg->frames[0].data[i * 4 + c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
    if (rg != im) delete rg;
    snprintf(out, outlen, "%d,%d,%d,%d,%d,%d,%d,%d", mn[0], mx[0], mn[1], mx[1], mn[2], mx[2], mn[3], mx[3]);
    return 0;
}

}  // extern "C"
