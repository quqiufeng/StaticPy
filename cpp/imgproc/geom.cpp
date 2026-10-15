// geom.cpp — 几何：crop/resize/thumbnail/rotate/transpose/pad/scale/paste/composite/blend/getbbox
#include "imgproc.h"
#include "imgproc_internal.h"

namespace {
Image* as_rgba(Image* im) { return im->frames.empty() || im->frames[0].bpp == 4 ? im : to_rgba(im); }

inline float cubic(float v) {
    v = (float)fabs(v);
    if (v < 1) return 1.5f * v * v * v - 2.5f * v * v + 1;
    if (v < 2) return -0.5f * v * v * v + 2.5f * v * v - 4 * v + 2;
    return 0;
}
inline float lanczos(float x) {
    if (x == 0) return 1; float a = 3; x = (float)fabs(x);
    if (x >= a) return 0;
    return (float)(a * sin(M_PI * x) * sin(M_PI * x / a) / (M_PI * M_PI * x * x));
}
}  // namespace

extern "C" {

void* img_crop(void* p, int x, int y, int w, int h) {
    Image* im = (Image*)p; if (!im || w <= 0 || h <= 0) return nullptr;
    Image* o = new Image(); o->w = w; o->h = h; o->n = im->n; o->loop = im->loop; o->mode = im->mode;
    o->frames.resize(im->n);
    for (int f = 0; f < im->n; ++f) {
        const Frame& s = im->frames[f]; Frame& d = o->frames[f];
        d.bpp = s.bpp; d.delay = s.delay; d.transparent = s.transparent; d.palette = s.palette; d.hasPalette = s.hasPalette;
        int b = s.bpp; d.data.assign((size_t)w * h * b, 0);
        for (int yy = 0; yy < h; ++yy) for (int xx = 0; xx < w; ++xx) {
            int sx = x + xx, sy = y + yy;
            if (sx < 0 || sx >= im->w || sy < 0 || sy >= im->h) continue;
            for (int c = 0; c < b; ++c) d.data[((size_t)yy * w + xx) * b + c] = s.data[((size_t)sy * im->w + sx) * b + c];
        }
    }
    return o;
}

// ---- Pillow ImagingResample 精确移植（定点系数 + 两趟 separable）----
static double rf_box(double x) { return (x > -0.5 && x <= 0.5) ? 1.0 : 0.0; }
static double rf_bilinear(double x) { x = fabs(x); return x < 1.0 ? 1.0 - x : 0.0; }
static double rf_hamming(double x) { x = fabs(x); if (x == 0.0) return 1.0; if (x >= 1.0) return 0.0; x *= M_PI; return sin(x) / x * (0.54 + 0.46 * cos(x)); }
static double rf_bicubic(double x) { const double a = -0.5; x = fabs(x); if (x < 1.0) return ((a + 2.0) * x - (a + 3.0)) * x * x + 1; if (x < 2.0) return (((x - 5) * x + 8) * x - 4) * a; return 0.0; }
static double rf_sinc(double x) { if (x == 0.0) return 1.0; x *= M_PI; return sin(x) / x; }
static double rf_lanczos(double x) { if (x >= -3.0 && x < 3.0) return rf_sinc(x) * rf_sinc(x / 3); return 0.0; }

struct RSFilter { double (*fn)(double); double support; };
static const int PREC = 22;  // PRECISION_BITS = 32-8-2

struct Coeffs { int ksize = 1; std::vector<int> bounds; std::vector<int> k; };
static Coeffs precompute(int inSize, double in0, double in1, int outSize, const RSFilter& flt) {
    Coeffs c;
    double scale = (in1 - in0) / outSize, fscale = scale < 1.0 ? 1.0 : scale;
    double support = flt.support * fscale;
    int ksize = (int)ceil(support) * 2 + 1;
    c.ksize = ksize; c.bounds.assign(outSize * 2, 0); std::vector<double> kd(outSize * ksize, 0.0);
    double inv = 1.0 / fscale;
    for (int xx = 0; xx < outSize; ++xx) {
        double center = in0 + (xx + 0.5) * scale, ww = 0.0;
        int xmin = (int)(center - support + 0.5); if (xmin < 0) xmin = 0;
        int xmax = (int)(center + support + 0.5); if (xmax > inSize) xmax = inSize;
        xmax -= xmin;
        double* k = &kd[xx * ksize];
        for (int x = 0; x < xmax; ++x) { double w = flt.fn((x + xmin - center + 0.5) * inv); k[x] = w; ww += w; }
        if (ww != 0.0) for (int x = 0; x < xmax; ++x) k[x] /= ww;
        for (int x = xmax; x < ksize; ++x) k[x] = 0.0;
        c.bounds[xx * 2] = xmin; c.bounds[xx * 2 + 1] = xmax;
    }
    c.k.assign(outSize * ksize, 0);
    for (size_t i = 0; i < kd.size(); ++i) c.k[i] = (int)((kd[i] < 0 ? -0.5 : 0.5) + kd[i] * (1 << PREC));
    return c;
}
static inline uint8_t clip8_fx(int in) { int v = in >> PREC; return v < 0 ? 0 : (v > 255 ? 255 : (uint8_t)v); }

void* img_resize_ex(void* p, int nw, int nh, const char* resample, float bx0, float by0, float bx1, float by1) {
    Image* im = (Image*)p; if (!im || nw <= 0 || nh <= 0) return nullptr;
    std::string s = resample ? resample : "bilinear";
    Image* rg = as_rgba(im);
    const int W = rg->w, H = rg->h;
    if (bx1 <= bx0) { bx0 = 0; bx1 = (float)W; }
    if (by1 <= by0) { by0 = 0; by1 = (float)H; }
    if (s == "nearest") {
        // 对齐 Pillow ImagingScaleAffine：double 增量累加（xo += a0）
        Image* o = new_rgba(nw, nh, rg->n); o->loop = rg->loop;
        double a0 = (bx1 - bx0) / (double)nw, a4 = (by1 - by0) / (double)nh;
        std::vector<int> xtab(nw), ytab(nh);
        double xo = bx0 + a0 * 0.5;
        for (int x = 0; x < nw; ++x) { xtab[x] = clampi((int)xo, 0, W - 1); xo += a0; }
        double yo = by0 + a4 * 0.5;
        for (int y = 0; y < nh; ++y) { ytab[y] = clampi((int)yo, 0, H - 1); yo += a4; }
        for (int f = 0; f < rg->n; ++f) { o->frames[f].delay = rg->frames[f].delay; const uint8_t* sp = rg->frames[f].data.data(); uint8_t* dp = o->frames[f].data.data();
            for (int y = 0; y < nh; ++y) for (int x = 0; x < nw; ++x) memcpy(dp + ((size_t)y * nw + x) * 4, sp + ((size_t)ytab[y] * W + xtab[x]) * 4, 4); }
        if (rg != im) delete rg; return o;
    }
    RSFilter flt = {rf_bilinear, 1.0};
    if (s == "box") flt = {rf_box, 0.5};
    else if (s == "hamming") flt = {rf_hamming, 1.0};
    else if (s == "bicubic") flt = {rf_bicubic, 2.0};
    else if (s == "lanczos") flt = {rf_lanczos, 3.0};

    Coeffs ch, cv;
    bool need_h = (nw != W) || (bx0 != 0) || (bx1 != W), need_v = (nh != H) || (by0 != 0) || (by1 != H);
    if (need_h) ch = precompute(W, bx0, bx1, nw, flt);
    if (need_v) cv = precompute(H, by0, by1, nh, flt);

    Image* o = new_rgba(nw, nh, rg->n); o->loop = rg->loop;
    for (int f = 0; f < rg->n; ++f) {
        o->frames[f].delay = rg->frames[f].delay;
        const uint8_t* src = rg->frames[f].data.data();
        int curw = W;
        std::vector<uint8_t> hbuf, vbuf;
        if (need_h) {
            hbuf.assign((size_t)nw * H * 4, 0);
            for (int y = 0; y < H; ++y) for (int xx = 0; xx < nw; ++xx) {
                int xmin = ch.bounds[xx * 2], xmax = ch.bounds[xx * 2 + 1]; const int* k = &ch.k[xx * ch.ksize];
                for (int c = 0; c < 4; ++c) { int ss = 1 << (PREC - 1); for (int x = 0; x < xmax; ++x) ss += src[((size_t)y * W + xmin + x) * 4 + c] * k[x]; hbuf[((size_t)y * nw + xx) * 4 + c] = clip8_fx(ss); }
            }
            src = hbuf.data(); curw = nw;
        }
        const uint8_t* out;
        if (need_v) {
            vbuf.assign((size_t)nw * nh * 4, 0);
            for (int yy = 0; yy < nh; ++yy) {
                int ymin = cv.bounds[yy * 2], ymax = cv.bounds[yy * 2 + 1]; const int* k = &cv.k[yy * cv.ksize];
                for (int x = 0; x < nw; ++x) for (int c = 0; c < 4; ++c) { int ss = 1 << (PREC - 1); for (int y = 0; y < ymax; ++y) ss += src[((size_t)(ymin + y) * curw + x) * 4 + c] * k[y]; vbuf[((size_t)yy * nw + x) * 4 + c] = clip8_fx(ss); }
            }
            out = vbuf.data();
        } else {
            out = hbuf.data();
        }
        memcpy(o->frames[f].data.data(), out, (size_t)nw * nh * 4);
    }
    if (rg != im) delete rg;
    return o;
}

void* img_resize(void* p, int nw, int nh, const char* resample) {
    return img_resize_ex(p, nw, nh, resample, 0, 0, 0, 0);
}

static Image* reduce_box(Image* im, int fx, int fy, int b0, int b1, int b2, int b3) {
    Image* rg = (im->frames[0].bpp == 4) ? im : to_rgba(im);
    int bw = b2 - b0, bh = b3 - b1;
    int ow = (bw + fx - 1) / fx, oh = (bh + fy - 1) / fy;
    Image* o = new_rgba(ow, oh, rg->n); o->loop = rg->loop;
    for (int f = 0; f < rg->n; ++f) {
        uint8_t* s = rg->frames[f].data.data(); uint8_t* d = o->frames[f].data.data();
        for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
            long sr = 0, sg = 0, sb = 0, sa = 0, cnt = 0;
            for (int j = 0; j < fy; ++j) for (int i = 0; i < fx; ++i) {
                int sy = b1 + y * fy + j, sx = b0 + x * fx + i;
                if (sx < 0 || sx >= rg->w || sy < 0 || sy >= rg->h) continue;
                uint8_t* q = s + ((size_t)sy * rg->w + sx) * 4; sr += q[0]; sg += q[1]; sb += q[2]; sa += q[3]; cnt++;
            }
            uint8_t* dd = d + ((size_t)y * ow + x) * 4;
            if (cnt) { dd[0] = (uint8_t)(sr / cnt); dd[1] = (uint8_t)(sg / cnt); dd[2] = (uint8_t)(sb / cnt); dd[3] = (uint8_t)(sa / cnt); }
        }
    }
    if (rg != im) delete rg;
    return o;
}

// 对齐 Pillow Image.thumbnail（含 reducing_gap 两步优化 + round_aspect + _get_safe_box）
void* img_thumbnail(void* p, int sw, int sh) {
    Image* im = (Image*)p; if (!im) return nullptr;
    int W = im->w, H = im->h;
    int px = sw, py = sh;
    if (px >= W && py >= H) return im;
    double aspect = (double)W / H;
    if ((double)px / py >= aspect) {
        double num = py * aspect; int nf = (int)floor(num), nc = (int)ceil(num);
        double kf = fabs(aspect - nf / (double)py), kc = fabs(aspect - nc / (double)py);
        px = std::max(kf <= kc ? nf : nc, 1);
    } else {
        double num = px / aspect; int nf = (int)floor(num), nc = (int)ceil(num);
        auto ky = [&](int n) { return n == 0 ? 0.0 : fabs(aspect - px / (double)n); };
        py = std::max(ky(nf) <= ky(nc) ? nf : nc, 1);
    }
    int finalW = px, finalH = py;
    const double support = 2.0;  // BICUBIC
    double scale_x = (double)W / finalW, scale_y = (double)H / finalH;
    double sup_x = (support - 0.5) * scale_x, sup_y = (support - 0.5) * scale_y;
    int fx = (int)((double)W / finalW / 2.0) ? (int)((double)W / finalW / 2.0) : 1;
    int fy = (int)((double)H / finalH / 2.0) ? (int)((double)H / finalH / 2.0) : 1;
    Image* base = im; Image* tmp = nullptr;
    double bx0 = 0, by0 = 0, bx1 = W, by1 = H;
    if (fx > 1 || fy > 1) {
        int rb0 = std::max(0, (int)(0 - sup_x));
        int rb1 = std::max(0, (int)(0 - sup_y));
        int rb2 = std::min(W, (int)ceil(W + sup_x));
        int rb3 = std::min(H, (int)ceil(H + sup_y));
        tmp = reduce_box(im, fx, fy, rb0, rb1, rb2, rb3);
        bx0 = (0 - (double)rb0) / fx; by0 = (0 - (double)rb1) / fy;
        bx1 = ((double)W - rb0) / fx; by1 = ((double)H - rb1) / fy;
        base = tmp;
    }
    Image* r = (Image*)img_resize_ex(base, finalW, finalH, "bicubic", (float)bx0, (float)by0, (float)bx1, (float)by1);
    if (tmp) delete tmp;
    // 就地替换
    *im = *r; delete r; return im;
}

void* img_scale(void* p, float fx, float fy, const char* resample) {
    Image* im = (Image*)p; if (!im) return nullptr;
    return img_resize(im, std::max(1, (int)(im->w * fx)), std::max(1, (int)(im->h * fy)), resample);
}

void* img_transpose(void* p, int m) {
    Image* im = (Image*)p; if (!im) return nullptr;
    bool swap = (m == 2 || m == 4 || m == 5 || m == 6);
    int nw = swap ? im->h : im->w, nh = swap ? im->w : im->h;
    Image* o = new Image(); o->w = nw; o->h = nh; o->n = im->n; o->loop = im->loop; o->mode = im->mode;
    o->frames.resize(im->n);
    for (int f = 0; f < im->n; ++f) {
        const Frame& s = im->frames[f]; Frame& d = o->frames[f];
        d.bpp = s.bpp; d.delay = s.delay; d.transparent = s.transparent; d.palette = s.palette; d.hasPalette = s.hasPalette;
        int b = s.bpp; d.data.assign((size_t)nw * nh * b, 0);
        for (int y = 0; y < im->h; ++y) for (int x = 0; x < im->w; ++x) {
            int nx, ny;
            switch (m) {
                case 0: nx = im->w - 1 - x; ny = y; break;
                case 1: nx = x; ny = im->h - 1 - y; break;
                case 2: nx = y; ny = im->w - 1 - x; break;
                case 3: nx = im->w - 1 - x; ny = im->h - 1 - y; break;
                case 4: nx = im->h - 1 - y; ny = x; break;
                case 5: nx = y; ny = x; break;
                default: nx = im->h - 1 - y; ny = im->w - 1 - x; break;
            }
            for (int c = 0; c < b; ++c) d.data[((size_t)ny * nw + nx) * b + c] = s.data[((size_t)y * im->w + x) * b + c];
        }
    }
    return o;
}

void* img_mirror(void* p) { return img_transpose(p, 0); }

void* img_pad(void* p, int l, int t, int r, int b, int rgba) {
    Image* im = (Image*)p; if (!im) return nullptr;
    Image* rg = as_rgba(im);
    Image* o = new_rgba(rg->w + l + r, rg->h + t + b, rg->n); o->loop = rg->loop;
    img_fill(o, rgba);
    for (int f = 0; f < rg->n; ++f) {
        o->frames[f].delay = rg->frames[f].delay;
        uint8_t* sp = rg->frames[f].data.data(); uint8_t* dp = o->frames[f].data.data();
        for (int y = 0; y < rg->h; ++y) for (int x = 0; x < rg->w; ++x)
            memcpy(dp + ((size_t)(y + t) * o->w + (x + l)) * 4, sp + ((size_t)y * rg->w + x) * 4, 4);
    }
    if (rg != im) delete rg;
    return o;
}

void* img_rotate(void* p, float deg, int expand, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return nullptr;
    Image* rg = as_rgba(im);
    double rad = deg * M_PI / 180.0, cs = cos(rad), sn = sin(rad);
    int W = rg->w, H = rg->h, nw = W, nh = H;
    if (expand) { nw = (int)ceil(fabs(W * cs) + fabs(H * sn)); nh = (int)ceil(fabs(W * sn) + fabs(H * cs)); }
    Image* o = new_rgba(nw, nh, rg->n); img_fill(o, fill_rgba);
    double cx = W / 2.0, cy = H / 2.0, ncx = nw / 2.0, ncy = nh / 2.0;
    for (int f = 0; f < rg->n; ++f) {
        o->frames[f].delay = rg->frames[f].delay;
        uint8_t* sp = rg->frames[f].data.data(); uint8_t* dp = o->frames[f].data.data();
        for (int y = 0; y < nh; ++y) for (int x = 0; x < nw; ++x) {
            double dx = x - ncx, dy = y - ncy;
            double sx = cs * dx + sn * dy + cx, sy = -sn * dx + cs * dy + cy;
            if (sx < -1 || sy < -1 || sx > W || sy > H) continue;
            int ix = (int)floor(sx), iy = (int)floor(sy); double tx = sx - ix, ty = sy - iy;
            uint8_t* d = dp + ((size_t)y * nw + x) * 4;
            for (int c = 0; c < 4; ++c) {
                float v = 0;
                for (int j = 0; j < 2; ++j) for (int i = 0; i < 2; ++i) {
                    int xx = clampi(ix + i, 0, W - 1), yy = clampi(iy + j, 0, H - 1);
                    v += (i ? tx : 1 - tx) * (j ? ty : 1 - ty) * sp[((size_t)yy * W + xx) * 4 + c];
                }
                d[c] = clamp8(v);
            }
        }
    }
    if (rg != im) delete rg;
    return o;
}

static void paste_into(Image* base, Image* src, int x, int y, Image* mask) {
    if (base->frames[0].bpp != 4) { Image* t = to_rgba(base); *base = *t; delete t; }
    Image* s = (src->frames[0].bpp == 4) ? src : to_rgba(src);
    for (int f = 0; f < base->n && f < s->n; ++f) {
        uint8_t* dp = base->frames[f].data.data(); uint8_t* sp2 = s->frames[f].data.data();
        uint8_t* mp = mask ? mask->frames[0].data.data() : nullptr;
        for (int sy = 0; sy < s->h; ++sy) for (int sx = 0; sx < s->w; ++sx) {
            int bx = x + sx, by = y + sy;
            if (bx < 0 || bx >= base->w || by < 0 || by >= base->h) continue;
            uint8_t* d = dp + ((size_t)by * base->w + bx) * 4;
            uint8_t* spr = sp2 + ((size_t)sy * s->w + sx) * 4;
            if (mp && mask->w == s->w && mask->h == s->h) {
                float a = mp[((size_t)sy * s->w + sx) * 4] / 255.0f;
                for (int c = 0; c < 4; ++c) d[c] = clamp8(d[c] * (1 - a) + spr[c] * a);
            } else memcpy(d, spr, 4);
        }
    }
    if (s != src) delete s;
}

void* img_paste(void* bp, void* sp, int x, int y) {
    Image* base = (Image*)bp; Image* src = (Image*)sp;
    if (!base || !src) return nullptr; paste_into(base, src, x, y, nullptr); return base;
}
void* img_paste_mask(void* bp, void* sp, int x, int y, void* mp) {
    Image* base = (Image*)bp; Image* src = (Image*)sp; Image* mask = (Image*)mp;
    if (!base || !src) return nullptr; paste_into(base, src, x, y, mask); return base;
}

void* img_composite(void* bp, void* op) {
    Image* base = (Image*)bp; Image* over = (Image*)op;
    if (!base || !over || base->w != over->w || base->h != over->h) return nullptr;
    if (base->frames[0].bpp != 4) { Image* t = to_rgba(base); *base = *t; delete t; }
    Image* o = to_rgba(over);
    for (int f = 0; f < base->n; ++f) {
        uint8_t* a = base->frames[f].data.data(); uint8_t* b = o->frames[f].data.data();
        for (int i = 0; i < base->w * base->h; ++i) {
            float sa = b[i * 4 + 3] / 255.0f, da = a[i * 4 + 3] / 255.0f;
            float oa = sa + da * (1 - sa);
            if (oa <= 0) { a[i * 4 + 3] = 0; continue; }
            for (int c = 0; c < 3; ++c) a[i * 4 + c] = clamp8((b[i * 4 + c] * sa + a[i * 4 + c] * da * (1 - sa)) / oa);
            a[i * 4 + 3] = clamp8(oa * 255);
        }
    }
    delete o; return base;
}

void* img_blend(void* ap, void* bp, float alpha) {
    Image* a = (Image*)ap; Image* b = (Image*)bp;
    if (!a || !b || a->w != b->w || a->h != b->h) return nullptr;
    Image* ra = to_rgba(a); Image* rb = to_rgba(b);
    for (int f = 0; f < ra->n; ++f) {
        uint8_t* pa = ra->frames[f].data.data(); uint8_t* pb = rb->frames[f].data.data();
        for (size_t i = 0; i < ra->frames[f].data.size(); ++i) pa[i] = clamp8(pa[i] * (1 - alpha) + pb[i] * alpha);
    }
    delete rb; return ra;
}

int img_getbbox4(void* p, int rgba, char* out, int outlen) {
    Image* im = (Image*)p; if (!im) return -1;
    Image* rg = as_rgba(im);
    int x0 = im->w, y0 = im->h, x1 = -1, y1 = -1;
    for (int y = 0; y < rg->h; ++y) for (int x = 0; x < rg->w; ++x) {
        uint8_t* q = rg->frames[0].data.data() + ((size_t)y * rg->w + x) * 4;
        int v = pack_rgba(q[0], q[1], q[2], q[3]);
        if (v != rgba) { if (x < x0) x0 = x; if (y < y0) y0 = y; if (x > x1) x1 = x; if (y > y1) y1 = y; }
    }
    if (rg != im) delete rg;
    if (x1 < 0) { snprintf(out, outlen, "None"); return 0; }
    snprintf(out, outlen, "%d,%d,%d,%d", x0, y0, x1 + 1, y1 + 1);
    return 0;
}
void* img_getbbox(void* p, int rgba) { (void)p; (void)rgba; return nullptr; }

// img_warp：按给定每像素源坐标（CSV:"sx,sy,..."）逆向采样（对称 deform 的基本能力）
void* img_warp(void* p, int nw, int nh, const char* coords_csv, const char* resample) {
    Image* im = (Image*)p; if (!im) return nullptr;
    std::vector<float> co = parse_csv_floats(coords_csv);
    if ((int)co.size() < nw * nh * 2) return nullptr;
    std::string rs = resample ? resample : "bilinear";
    Image* rg = (im->frames[0].bpp == 4) ? im : to_rgba(im);
    int W = rg->w, H = rg->h;
    Image* o = new_rgba(nw, nh, rg->n); o->loop = rg->loop;
    for (int f = 0; f < rg->n; ++f) {
        uint8_t* sp = rg->frames[f].data.data(); uint8_t* dp = o->frames[f].data.data();
        for (int y = 0; y < nh; ++y) for (int x = 0; x < nw; ++x) {
            float sx = co[(y * nw + x) * 2], sy = co[(y * nw + x) * 2 + 1];
            uint8_t* d = dp + ((size_t)y * nw + x) * 4;
            if (rs == "nearest") { int ix = clampi((int)floor(sx + 0.5f), 0, W - 1), iy = clampi((int)floor(sy + 0.5f), 0, H - 1); memcpy(d, sp + ((size_t)iy * W + ix) * 4, 4); continue; }
            int x0 = (int)floor(sx), y0 = (int)floor(sy); float tx = sx - x0, ty = sy - y0;
            for (int c = 0; c < 4; ++c) {
                float v = 0;
                for (int j = 0; j < 2; ++j) for (int i = 0; i < 2; ++i) {
                    int xx = clampi(x0 + i, 0, W - 1), yy = clampi(y0 + j, 0, H - 1);
                    v += (i ? tx : 1 - tx) * (j ? ty : 1 - ty) * sp[((size_t)yy * W + xx) * 4 + c];
                }
                d[c] = clamp8(v);
            }
        }
    }
    if (rg != im) delete rg;
    return o;
}


void* img_alpha_composite_at(void* bp, void* op, int x, int y) {
    Image* base = (Image*)bp; Image* over = (Image*)op;
    if (!base || !over) return nullptr;
    if (base->frames[0].bpp != 4) { Image* t = to_rgba(base); *base = *t; delete t; }
    Image* o = to_rgba(over);
    for (int f = 0; f < base->n && f < o->n; ++f) {
        uint8_t* a = base->frames[f].data.data(); uint8_t* b = o->frames[f].data.data();
        for (int oy = 0; oy < o->h; ++oy) for (int ox = 0; ox < o->w; ++ox) {
            int bx = x + ox, by = y + oy;
            if (bx < 0 || bx >= base->w || by < 0 || by >= base->h) continue;
            size_t bi = ((size_t)by * base->w + bx) * 4, oi = ((size_t)oy * o->w + ox) * 4;
            float sa = b[oi + 3] / 255.0f, da = a[bi + 3] / 255.0f;
            float oa = sa + da * (1 - sa);
            if (oa <= 0) { a[bi + 3] = 0; continue; }
            for (int c = 0; c < 3; ++c) a[bi + c] = clamp8((b[oi + c] * sa + a[bi + c] * da * (1 - sa)) / oa);
            a[bi + 3] = clamp8(oa * 255);
        }
    }
    delete o; return base;
}

// ImageOps.contain：等比缩放到能放进 (w,h)，返回缩放后的图（不补边）
void* img_contain(void* p, int w, int h, const char* resample, int fill_rgba) {
    (void)fill_rgba;
    Image* im = (Image*)p; if (!im) return nullptr;
    float s = std::min((float)w / im->w, (float)h / im->h);
    int nw = std::max(1, (int)round(im->w * s)), nh = std::max(1, (int)round(im->h * s));
    return img_resize(im, nw, nh, resample);
}

// ImageOps.fit：按 Pillow 算法算 crop box，再用「带 box 的 resize」一步出
void* img_fit(void* p, int w, int h, const char* resample, float cx, float cy, int fill_rgba) {
    (void)fill_rgba;
    Image* im = (Image*)p; if (!im || w <= 0 || h <= 0) return nullptr;
    float sw = (float)im->w, sh = (float)im->h;
    float out_ratio = (float)w / h, live_ratio = sw / sh;
    float crop_w, crop_h;
    if (live_ratio == out_ratio) { crop_w = sw; crop_h = sh; }
    else if (live_ratio >= out_ratio) { crop_w = out_ratio * sh; crop_h = sh; }
    else { crop_w = sw; crop_h = sw / out_ratio; }
    float left = (sw - crop_w) * cx, top = (sh - crop_h) * cy;
    return img_resize_ex(im, w, h, resample, left, top, left + crop_w, top + crop_h);
}

}  // extern "C"
