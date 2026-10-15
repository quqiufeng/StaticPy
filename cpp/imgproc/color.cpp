#include <unordered_map>
// color.cpp — 模式转换 / 拆分合并 / point(LUT) / 调色板 / 量化（median cut）
#include "imgproc.h"
#include "imgproc_internal.h"

namespace {
inline uint8_t lum(int r, int g, int b) { return clamp8(0.299f * r + 0.587f * g + 0.114f * b); }

Image* as_rgba(Image* im) { return im->frames.empty() || im->frames[0].bpp == 4 ? im : to_rgba(im); }

// 简单 median-cut 量化（源：RGBA）
void median_cut(const std::vector<uint8_t>& px4, int colors, std::vector<RGB>& out) {
    struct Box { std::vector<int> idx; };
    std::vector<Box> boxes;
    Box b0; b0.idx.resize(px4.size() / 4); for (size_t i = 0; i < b0.idx.size(); ++i) b0.idx[i] = (int)i;
    boxes.push_back(b0);
    auto axis_range = [&](Box& bx, int ch, int& mn, int& mx) {
        mn = 255; mx = 0;
        for (int pi : bx.idx) { int v = px4[(size_t)pi * 4 + ch]; if (v < mn) mn = v; if (v > mx) mx = v; }
    };
    while ((int)boxes.size() < colors) {
        int best = -1, best_span = -1, best_ch = 0;
        for (size_t bi = 0; bi < boxes.size(); ++bi) {
            for (int ch = 0; ch < 3; ++ch) { int mn, mx; axis_range(boxes[bi], ch, mn, mx); if (mx - mn > best_span) { best_span = mx - mn; best = (int)bi; best_ch = ch; } }
        }
        if (best < 0 || best_span <= 0) break;
        Box& bx = boxes[best];
        std::sort(bx.idx.begin(), bx.idx.end(), [&](int a, int b) { return px4[(size_t)a * 4 + best_ch] < px4[(size_t)b * 4 + best_ch]; });
        size_t mid = bx.idx.size() / 2;
        Box b1, b2;
        b1.idx.assign(bx.idx.begin(), bx.idx.begin() + mid);
        b2.idx.assign(bx.idx.begin() + mid, bx.idx.end());
        if (b1.idx.empty() || b2.idx.empty()) break;
        boxes[best] = b1; boxes.push_back(b2);
    }
    out.clear();
    for (auto& bx : boxes) {
        if (bx.idx.empty()) continue;
        long sR = 0, sG = 0, sB = 0;
        for (int pi : bx.idx) { sR += px4[(size_t)pi * 4]; sG += px4[(size_t)pi * 4 + 1]; sB += px4[(size_t)pi * 4 + 2]; }
        int k = (int)bx.idx.size();
        out.push_back({(uint8_t)(sR / k), (uint8_t)(sG / k), (uint8_t)(sB / k)});
    }
    if (out.empty()) out.push_back({0, 0, 0});
}
inline int nearest_pal(const std::vector<RGB>& pal, int r, int g, int b) {
    int best = 0; long bd = 1L << 30;
    for (size_t i = 0; i < pal.size(); ++i) {
        long dr = r - pal[i].r, dg = g - pal[i].g, db = b - pal[i].b;
        long d = dr * dr + dg * dg + db * db;
        if (d < bd) { bd = d; best = (int)i; }
    }
    return best;
}
Image* quantize_to_P(Image* im, int colors, const std::vector<RGB>* forced) {
    Image* rg = as_rgba(im);
    std::vector<uint8_t> px4;
    px4.reserve(npx(rg) * 4);
    for (size_t i = 0; i < rg->frames[0].data.size(); i += 4) if (rg->frames[0].data[i + 3] >= 128) for (int c = 0; c < 3; ++c) px4.push_back(rg->frames[0].data[i + c]);
    std::vector<RGB> pal;
    if (forced && !forced->empty()) pal = *forced;
    else { std::vector<uint8_t> all; all.reserve(npx(rg) * 4); for (size_t i = 0; i < rg->frames[0].data.size(); i += 4) for (int c = 0; c < 4; ++c) all.push_back(rg->frames[0].data[i + c]); median_cut(all, colors, pal); }
    Image* o = new Image(); o->w = rg->w; o->h = rg->h; o->n = rg->n; o->loop = rg->loop; o->mode = "P";
    o->frames.resize(rg->n);
    for (int f = 0; f < rg->n; ++f) {
        Frame& d = o->frames[f]; d.bpp = 1; d.hasPalette = true; d.palette = pal; d.delay = rg->frames[f].delay;
        d.data.assign(npx(rg), 0);
        uint8_t* sp = rg->frames[f].data.data();
        for (int i = 0; i < (int)npx(rg); ++i) d.data[i] = (uint8_t)nearest_pal(pal, sp[i * 4], sp[i * 4 + 1], sp[i * 4 + 2]);
    }
    if (rg != im) delete rg;
    return o;
}
}  // namespace

extern "C" {

// Pillow 的 "browser" 调色板：索引 0..9 黑，10..225 = 6x6x6 立方（b/g/r 步长 51）
static std::vector<RGB> browser_palette() {
    std::vector<RGB> pal(226, RGB{0, 0, 0});
    int i = 10;
    for (int b = 0; b < 256; b += 51) for (int g = 0; g < 256; g += 51) for (int r = 0; r < 256; r += 51) pal[i++] = {(uint8_t)r, (uint8_t)g, (uint8_t)b};
    return pal;
}
static inline int nearest_sq(const std::vector<RGB>& pal, int r, int g, int b) {
    int best = 0; long bd = 1L << 30;
    for (size_t i = 0; i < pal.size(); ++i) { int dr = r - pal[i].r, dg = g - pal[i].g, db = b - pal[i].b; long d = (long)dr * dr + (long)dg * dg + (long)db * db; if (d < bd) { bd = d; best = (int)i; } }
    return best;
}
// Pillow ImagingPaletteCacheUpdate 的精确移植（Heckbert 盒搜索）：
// 按 (r>>2,g>>2,b>>2) 桶，首次用当时精确 RGB 填满所在 8x8x8 盒
static inline int DIST(int a, int b, int s) { int d = a - b; return d * d * s; }
static void cache_update(const std::vector<RGB>& pal, std::vector<int>& cache, int r, int g, int b) {
    int r0 = r & 0xe0, r1 = r0 + 0x1f, rc = (r0 + r1) / 2;
    int g0 = g & 0xe0, g1 = g0 + 0x1f, gc = (g0 + g1) / 2;
    int b0 = b & 0xe0, b1 = b0 + 0x1f, bc = (b0 + b1) / 2;
    std::vector<unsigned int> dmin(pal.size());
    unsigned int dmax = ~0u;
    for (size_t i = 0; i < pal.size(); ++i) {
        int pr = pal[i].r, pg = pal[i].g, pb = pal[i].b;
        unsigned int tmin = (pr < r0) ? DIST(pr, r0, 1) : (pr > r1) ? DIST(pr, r1, 1) : 0;
        unsigned int tmax = (pr <= rc) ? DIST(pr, r1, 1) : DIST(pr, r0, 1);
        tmin += (pg < g0) ? DIST(pg, g0, 1) : (pg > g1) ? DIST(pg, g1, 1) : 0;
        tmax += (pg <= gc) ? DIST(pg, g1, 1) : DIST(pg, g0, 1);
        tmin += (pb < b0) ? DIST(pb, b0, 1) : (pb > b1) ? DIST(pb, b1, 1) : 0;
        tmax += (pb <= bc) ? DIST(pb, b1, 1) : DIST(pb, b0, 1);
        dmin[i] = tmin;
        if (tmax < dmax) dmax = tmax;
    }
    const int BOX = 8, VOL = 512, RSTEP = 4, GSTEP = 4, BSTEP = 4;
    std::vector<unsigned int> d(VOL, ~0u);
    std::vector<unsigned char> c(VOL, 0);
    for (size_t i = 0; i < pal.size(); ++i) {
        if (dmin[i] <= dmax) {
            int ri = (r0 - pal[i].r), gi = (g0 - pal[i].g), bi = (b0 - pal[i].b);
            int rd = ri * ri + gi * gi + bi * bi;
            ri = ri * (2 * RSTEP) + RSTEP * RSTEP; gi = gi * (2 * GSTEP) + GSTEP * GSTEP; bi = bi * (2 * BSTEP) + BSTEP * BSTEP;
            int rx = ri, j = 0;
            for (int rr = 0; rr < BOX; ++rr) {
                int gd = rd, gx = gi;
                for (int gg = 0; gg < BOX; ++gg) {
                    int bd = gd, bx = bi;
                    for (int bb = 0; bb < BOX; ++bb) {
                        if ((unsigned)bd < d[j]) { d[j] = (unsigned)bd; c[j] = (unsigned char)i; }
                        bd += bx; bx += 2 * BSTEP * BSTEP; j++;
                    }
                    gd += gx; gx += 2 * GSTEP * GSTEP;
                }
                rd += rx; rx += 2 * RSTEP * RSTEP;
            }
        }
    }
    int j = 0;
    for (int rr = r0; rr < r1; rr += 4) for (int gg = g0; gg < g1; gg += 4) for (int bb = b0; bb < b1; bb += 4)
        cache[(rr >> 2) + (gg >> 2) * 64 + (bb >> 2) * 64 * 64] = c[j++];
}
static inline int nearest_cached(const std::vector<RGB>& pal, std::vector<int>& cache, int r, int g, int b) {
    int bkt = (r >> 2) + (g >> 2) * 64 + (b >> 2) * 64 * 64;
    if (cache[bkt] == 0x100) cache_update(pal, cache, r, g, b);
    return cache[bkt];
}
static inline int clip8c(int v) { return v < 0 ? 0 : (v > 255 ? 255 : v); }

// 对齐 Pillow Convert.c 的 topalette：默认 browser 调色板 + 可选 Floyd-Steinberg 抖动
void* img_convert_p(void* p, int dither) {
    Image* im = (Image*)p; if (!im) return nullptr;
    Image* rg = as_rgba(im);
    std::vector<RGB> pal = browser_palette();
    Image* o = new Image(); o->w = rg->w; o->h = rg->h; o->n = rg->n; o->loop = rg->loop; o->mode = "P";
    o->frames.resize(rg->n);
    int W = rg->w, H = rg->h;
    for (int f = 0; f < rg->n; ++f) {
        Frame& d = o->frames[f]; d.bpp = 1; d.hasPalette = true; d.palette = pal; d.delay = rg->frames[f].delay;
        d.data.assign((size_t)W * H, 0);
        uint8_t* in = rg->frames[f].data.data(); uint8_t* out = d.data.data();
        std::vector<int> cache(64 * 64 * 64, 0x100);
        if (!dither) {
            for (int i = 0; i < W * H; ++i) out[i] = (uint8_t)nearest_cached(pal, cache, in[i * 4], in[i * 4 + 1], in[i * 4 + 2]);
        } else {
            std::vector<int> errors((W + 1) * 3, 0);
            for (int y = 0; y < H; ++y) {
                int* e = errors.data();
                int r, r0 = 0, r1 = 0, g, g0 = 0, g1 = 0, b, b0 = 0, b1 = 0, b2 = 0;
                r = 0; g = 0; b = 0;
                uint8_t* row = in + (size_t)y * W * 4;
                for (int x = 0; x < W; ++x, row += 4) {
                    r = clip8c(row[0] + (r + e[3 + 0]) / 16);
                    g = clip8c(row[1] + (g + e[3 + 1]) / 16);
                    b = clip8c(row[2] + (b + e[3 + 2]) / 16);
                    int idx = nearest_cached(pal, cache, r, g, b);
                    out[(size_t)y * W + x] = (uint8_t)idx;
                    r -= pal[idx].r; g -= pal[idx].g; b -= pal[idx].b;
                    { int r2 = r, d2 = r + r; r += d2; e[0] = r + r0; r += d2; r0 = r + r1; r1 = r2; r += d2; }
                    { int g2 = g, d2 = g + g; g += d2; e[1] = g + g0; g += d2; g0 = g + g1; g1 = g2; g += d2; }
                    { int b2 = b, d2 = b + b; b += d2; e[2] = b + b0; b += d2; b0 = b + b1; b1 = b2; b += d2; }
                    e += 3;
                }
                e[0] = b0; e[1] = b1; e[2] = b2;
            }
        }
    }
    if (rg != im) delete rg;
    return o;
}

void* img_convert(void* p, const char* mode) {
    Image* im = (Image*)p; if (!im || !mode) return nullptr;
    std::string m = mode;
    Image* rg = as_rgba(im);
    if (m == "RGBA") { if (rg == im) return dup_img(im); return rg; }
    if (m == "RGB") {
        Image* o = new Image(); o->w = rg->w; o->h = rg->h; o->n = rg->n; o->loop = rg->loop; o->mode = "RGB"; o->frames.resize(rg->n);
        for (int f = 0; f < rg->n; ++f) { Frame& d = o->frames[f]; d.bpp = 4; d.delay = rg->frames[f].delay; d.data.resize(npx(rg) * 4); uint8_t* s = rg->frames[f].data.data(); for (size_t i = 0; i < npx(rg); ++i) { d.data[i * 4] = s[i * 4]; d.data[i * 4 + 1] = s[i * 4 + 1]; d.data[i * 4 + 2] = s[i * 4 + 2]; d.data[i * 4 + 3] = 255; } }
        if (rg != im) delete rg; return o;
    }
    if (m == "L" || m == "LA") {
        Image* o = new Image(); o->w = rg->w; o->h = rg->h; o->n = rg->n; o->loop = rg->loop; o->mode = m; o->frames.resize(rg->n);
        for (int f = 0; f < rg->n; ++f) { Frame& d = o->frames[f]; d.bpp = 4; d.delay = rg->frames[f].delay; d.data.resize(npx(rg) * 4); uint8_t* s = rg->frames[f].data.data(); for (size_t i = 0; i < npx(rg); ++i) { uint8_t l = lum(s[i * 4], s[i * 4 + 1], s[i * 4 + 2]); d.data[i * 4] = d.data[i * 4 + 1] = d.data[i * 4 + 2] = l; d.data[i * 4 + 3] = (m == "LA") ? s[i * 4 + 3] : 255; } }
        if (rg != im) delete rg; return o;
    }
    if (m == "P") { if (rg != im) delete rg; return img_convert_p(im, 0); }
    if (rg == im) return dup_img(im);
    return rg;
}

void* img_split(void* p, int channel) {
    Image* im = (Image*)p; if (!im) return nullptr;
    Image* rg = as_rgba(im);
    Image* o = new Image(); o->w = rg->w; o->h = rg->h; o->n = rg->n; o->loop = rg->loop; o->mode = "L"; o->frames.resize(rg->n);
    for (int f = 0; f < rg->n; ++f) { Frame& d = o->frames[f]; d.bpp = 4; d.delay = rg->frames[f].delay; d.data.resize(npx(rg) * 4); uint8_t* s = rg->frames[f].data.data(); for (size_t i = 0; i < npx(rg); ++i) { uint8_t v = s[i * 4 + clampi(channel, 0, 3)]; d.data[i * 4] = d.data[i * 4 + 1] = d.data[i * 4 + 2] = v; d.data[i * 4 + 3] = 255; } }
    if (rg != im) delete rg; return o;
}

void* img_merge_rgb(void* rp, void* gp, void* bp) {
    Image* r = (Image*)rp; Image* g = (Image*)gp; Image* b = (Image*)bp;
    if (!r || !g || !b || r->w != g->w || r->w != b->w) return nullptr;
    Image* rr = as_rgba(r); Image* gg = as_rgba(g); Image* bb = as_rgba(b);
    Image* o = new_rgba(r->w, r->h, r->n); o->mode = "RGB";
    for (int f = 0; f < r->n; ++f) { uint8_t* pr = rr->frames[f].data.data(); uint8_t* pg = gg->frames[f].data.data(); uint8_t* pb = bb->frames[f].data.data(); uint8_t* d = o->frames[f].data.data(); for (size_t i = 0; i < npx(r); ++i) { d[i * 4] = pr[i * 4]; d[i * 4 + 1] = pg[i * 4]; d[i * 4 + 2] = pb[i * 4]; d[i * 4 + 3] = 255; } }
    if (rr != r) delete rr; if (gg != g) delete gg; if (bb != b) delete bb;
    return o;
}

void* img_point(void* p, int channel, const char* lut_csv) {
    Image* im = (Image*)p; if (!im || !lut_csv) return nullptr;
    std::vector<int> lu = parse_csv_ints(lut_csv);
    if (lu.size() != 256) return nullptr;
    Image* o = dup_img(im);
    Image* rg = as_rgba(o);
    bool all = (channel < 0);
    for (int f = 0; f < rg->n; ++f) { uint8_t* s = rg->frames[f].data.data(); for (size_t i = 0; i < npx(rg); ++i) { if (all) for (int c = 0; c < 3; ++c) s[i * 4 + c] = (uint8_t)clampi(lu[s[i * 4 + c]], 0, 255); else if (channel < 4) s[i * 4 + channel] = (uint8_t)clampi(lu[s[i * 4 + channel]], 0, 255); } }
    if (rg != o) { *o = *rg; delete rg; }
    return o;
}


int img_putpalette(void* p, const char* rgb_csv) {
    Image* im = (Image*)p; if (!im || !rgb_csv) return -1;
    std::vector<int> v = parse_csv_ints(rgb_csv);
    std::vector<RGB> pal; for (size_t i = 0; i + 2 < v.size(); i += 3) pal.push_back({(uint8_t)v[i], (uint8_t)v[i + 1], (uint8_t)v[i + 2]});
    if (pal.empty()) return -1;
    Image* o = quantize_to_P(im, (int)pal.size(), &pal);
    *im = *o; delete o; return 0;
}

// Image.getcolors：返回 (count,r,g,b) 列表（按颜色排序），超 maxcolors 返回空
int img_getcolors(void* p, int maxcolors, char* out, int outlen) {
    Image* im = (Image*)p; if (!im || !out) return -1;
    Image* rg = as_rgba(im);
    std::vector<std::pair<uint32_t, int>> cnt;
    std::unordered_map<uint32_t, int> idx;
    for (size_t i = 0; i < npx(rg); ++i) {
        uint8_t* q = rg->frames[0].data.data() + i * 4;
        uint32_t k = ((uint32_t)q[0] << 16) | ((uint32_t)q[1] << 8) | q[2];
        auto it = idx.find(k);
        if (it == idx.end()) { idx[k] = (int)cnt.size(); cnt.push_back({k, 1}); if ((int)cnt.size() > maxcolors) { if (rg != im) delete rg; out[0] = 0; return 1; } }
        else cnt[it->second].second++;
    }
    if (rg != im) delete rg;
    std::sort(cnt.begin(), cnt.end(), [](const std::pair<uint32_t, int>& a, const std::pair<uint32_t, int>& b) { return a.first < b.first; });
    std::string s;
    for (auto& e : cnt) { char b[48]; snprintf(b, 48, "%d,%d,%d,%d;", e.second, (e.first >> 16) & 0xFF, (e.first >> 8) & 0xFF, e.first & 0xFF); s += b; }
    if ((int)s.size() >= outlen) s.resize(outlen - 1);
    strcpy(out, s.c_str()); return 0;
}

// Image.remap_palette：按 data 重排 P 图索引
void* img_remap_palette(void* p, const char* data_csv) {
    Image* im = (Image*)p; if (!im || !data_csv) return nullptr;
    std::vector<int> d = parse_csv_ints(data_csv);
    if (d.empty()) return nullptr;
    Image* o = dup_img(im);
    for (auto& fr : o->frames) {
        if (fr.bpp != 1) continue;
        for (auto& v : fr.data) v = (uint8_t)clampi(d[v % d.size()], 0, 255);
    }
    return o;
}

int img_getpalette(void* p, char* out, int outlen) {
    Image* im = (Image*)p; if (!im || !out) return -1;
    std::string s;
    for (auto& f : im->frames) if (f.bpp == 1 && f.hasPalette) {
        for (size_t i = 0; i < f.palette.size(); ++i) { char buf[16]; snprintf(buf, 16, "%d,%d,%d,", f.palette[i].r, f.palette[i].g, f.palette[i].b); s += buf; }
        break;
    }
    if ((int)s.size() >= outlen) s.resize(outlen - 1);
    strcpy(out, s.c_str()); return 0;
}

// ImageColor.getrgb：hex / rgb() / 常用命名色
static bool color_named(const std::string& n, int& r, int& g, int& b) {
    static const struct { const char* nm; int r, g, b; } T[] = {
        {"black",0,0,0},{"white",255,255,255},{"red",255,0,0},{"green",0,128,0},{"lime",0,255,0},
        {"blue",0,0,255},{"yellow",255,255,0},{"cyan",0,255,255},{"aqua",0,255,255},{"magenta",255,0,255},
        {"fuchsia",255,0,255},{"gray",128,128,128},{"grey",128,128,128},{"silver",192,192,192},
        {"maroon",128,0,0},{"olive",128,128,0},{"navy",0,0,128},{"teal",0,128,128},{"purple",128,0,128},
        {"orange",255,165,0},{"pink",255,192,203},{"brown",165,42,42},{"gold",255,215,0},
    };
    for (auto& t : T) if (n == t.nm) { r = t.r; g = t.g; b = t.b; return true; }
    return false;
}
int img_color_getrgb(const char* color, char* out, int outlen) {
    if (!color || !out) return -1;
    std::string c = color;
    int r = 0, g = 0, b = 0;
    if (!c.empty() && c[0] == '#') {
        std::string h = c.substr(1);
        if (h.size() == 3) { r = strtol(std::string(1, h[0]).c_str(), 0, 16) * 17; g = strtol(std::string(1, h[1]).c_str(), 0, 16) * 17; b = strtol(std::string(1, h[2]).c_str(), 0, 16) * 17; }
        else if (h.size() >= 6) { r = strtol(h.substr(0, 2).c_str(), 0, 16); g = strtol(h.substr(2, 2).c_str(), 0, 16); b = strtol(h.substr(4, 2).c_str(), 0, 16); }
        else return -1;
    } else if (c.rfind("rgb", 0) == 0) {
        std::vector<int> v = parse_csv_ints(c.substr(c.find('(') + 1).c_str());
        if (v.size() < 3) return -1; r = v[0]; g = v[1]; b = v[2];
    } else if (!color_named(c, r, g, b)) return -1;
    snprintf(out, outlen, "%d,%d,%d", clampi(r, 0, 255), clampi(g, 0, 255), clampi(b, 0, 255));
    return 0;
}

}  // extern "C"
