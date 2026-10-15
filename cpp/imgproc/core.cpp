// core.cpp — 图像模型 / 编解码 / 生命周期 / 像素访问
#include "imgproc.h"
#include "imgproc_internal.h"

#define STB_IMAGE_IMPLEMENTATION
#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STB_TRUETYPE_IMPLEMENTATION
#include "stb_image.h"
#include "stb_image_write.h"
#include "stb_truetype.h"
#include <webp/decode.h>
#include <webp/encode.h>
#include <tiffio.h>

// ---------------- 模型工具 ----------------
Image* new_rgba(int w, int h, int n) {
    Image* im = new Image();
    im->w = w; im->h = h; im->n = n;
    im->frames.resize(n);
    for (auto& f : im->frames) { f.bpp = 4; f.data.assign((size_t)w * h * 4, 0); }
    return im;
}

void idx_to_rgba(const Frame& fr, int w, int h, std::vector<uint8_t>& out) {
    out.assign((size_t)w * h * 4, 0);
    for (int p = 0; p < w * h; ++p) {
        int idx = fr.data[p]; size_t o = (size_t)p * 4;
        if (idx == fr.transparent) { out[o + 3] = 0; continue; }
        if (idx >= 0 && idx < (int)fr.palette.size()) {
            out[o] = fr.palette[idx].r; out[o + 1] = fr.palette[idx].g;
            out[o + 2] = fr.palette[idx].b; out[o + 3] = 255;
        }
    }
}

Image* to_rgba(Image* im) {
    Image* out = new Image();
    out->w = im->w; out->h = im->h; out->n = im->n; out->loop = im->loop; out->mode = "RGBA";
    out->frames.resize(im->n);
    for (int i = 0; i < im->n; ++i) {
        const Frame& s = im->frames[i]; Frame& d = out->frames[i];
        d.bpp = 4; d.delay = s.delay; d.transparent = -1;
        if (s.bpp == 4) d.data = s.data; else idx_to_rgba(s, im->w, im->h, d.data);
    }
    return out;
}

bool ends_with(const char* s, const char* suf) {
    size_t ls = strlen(s), lf = strlen(suf);
    if (lf > ls) return false;
    for (size_t i = 0; i < lf; ++i) if (tolower((unsigned char)s[ls - lf + i]) != tolower((unsigned char)suf[i])) return false;
    return true;
}

std::vector<int> parse_csv_ints(const char* s) {
    std::vector<int> v;
    if (!s) return v;
    const char* p = s;
    while (*p) {
        while (*p && (*p == ',' || *p == ' ' || *p == '\n' || *p == '\t')) ++p;
        if (!*p) break;
        char* e = nullptr; long x = strtol(p, &e, 10);
        if (e == p) break; v.push_back((int)x); p = e;
    }
    return v;
}
std::vector<float> parse_csv_floats(const char* s) {
    std::vector<float> v;
    if (!s) return v;
    const char* p = s;
    while (*p) {
        while (*p && (*p == ',' || *p == ' ' || *p == '\n' || *p == '\t')) ++p;
        if (!*p) break;
        char* e = nullptr; double x = strtod(p, &e);
        if (e == p) break; v.push_back((float)x); p = e;
    }
    return v;
}

// ---------------- GIF 编解码 ----------------
Image* decode_gif(const char* path) {
    int err = 0;
    GifFileType* g = DGifOpenFileName(path, &err);
    if (!g) return nullptr;
    if (DGifSlurp(g) != GIF_OK) { DGifCloseFile(g, &err); return nullptr; }
    int W = g->SWidth, H = g->SHeight, N = g->ImageCount;
    if (W <= 0 || H <= 0 || N <= 0) { DGifCloseFile(g, &err); return nullptr; }
    Image* im = new Image();
    im->w = W; im->h = H; im->n = N; im->mode = "RGBA"; im->loop = 0;
    im->frames.resize(N);
    std::vector<uint8_t> canvas((size_t)W * H * 4, 0);
    for (int i = 0; i < N; ++i) {
        SavedImage* si = &g->SavedImages[i];
        GraphicsControlBlock gcb; gcb.DisposalMode = DISPOSAL_UNSPECIFIED; gcb.UserInputFlag = false;
        gcb.DelayTime = 0; gcb.TransparentColor = NO_TRANSPARENT_COLOR;
        DGifSavedExtensionToGCB(g, i, &gcb);
        Frame& fr = im->frames[i];
        fr.delay = gcb.DelayTime * 10;
        int fw = si->ImageDesc.Width > 0 ? si->ImageDesc.Width : W;
        int fh = si->ImageDesc.Height > 0 ? si->ImageDesc.Height : H;
        int L = si->ImageDesc.Left, T = si->ImageDesc.Top;
        ColorMapObject* cm = si->ImageDesc.ColorMap ? si->ImageDesc.ColorMap : g->SColorMap;
        bool full = (L == 0 && T == 0 && fw == W && fh == H);
        if (full && cm) {
            fr.bpp = 1; fr.transparent = gcb.TransparentColor; fr.hasPalette = true;
            fr.palette.resize(cm->ColorCount);
            for (int k = 0; k < cm->ColorCount; ++k) fr.palette[k] = {cm->Colors[k].Red, cm->Colors[k].Green, cm->Colors[k].Blue};
            fr.data.assign((size_t)W * H, 0);
            for (int y = 0; y < H; ++y) for (int x = 0; x < W; ++x) fr.data[(size_t)y * W + x] = (uint8_t)si->RasterBits[y * fw + x];
        } else {
            fr.bpp = 4; fr.data.assign((size_t)W * H * 4, 0);
            std::vector<uint8_t> before = canvas;
            for (int y = 0; y < fh; ++y) for (int x = 0; x < fw; ++x) {
                int idx = si->RasterBits[y * fw + x];
                int pxx = L + x, pyy = T + y;
                if (idx == gcb.TransparentColor || !cm || idx >= cm->ColorCount) continue;
                if (pxx < 0 || pxx >= W || pyy < 0 || pyy >= H) continue;
                GifColorType c = cm->Colors[idx];
                size_t o = ((size_t)pyy * W + pxx) * 4;
                canvas[o] = c.Red; canvas[o + 1] = c.Green; canvas[o + 2] = c.Blue; canvas[o + 3] = 255;
            }
            fr.data = canvas;
            if (gcb.DisposalMode == DISPOSE_PREVIOUS) canvas = before;
        }
    }
    DGifCloseFile(g, &err);
    return im;
}

int encode_gif(Image* im, const char* path) {
    int W = im->w, H = im->h, N = im->n;
    int err = 0;
    GifFileType* g = EGifOpenFileName(path, false, &err);
    if (!g) return -1;
    EGifSetGifVersion(g, true);
    std::vector<GifColorType> gpal; bool anyPal = false;
    for (auto& f : im->frames) if (f.bpp == 1 && f.hasPalette && !f.palette.empty()) { anyPal = true; for (auto& c : f.palette) gpal.push_back({c.r, c.g, c.b}); break; }
    if (!anyPal) for (int r = 0; r < 8; ++r) for (int gg = 0; gg < 8; ++gg) for (int b = 0; b < 4; ++b) gpal.push_back({(uint8_t)(r * 36), (uint8_t)(gg * 36), (uint8_t)(b * 85)});
    int cc = 2; while (cc < (int)gpal.size()) cc <<= 1;
    std::vector<GifColorType> gpad = gpal; gpad.resize(cc, {0, 0, 0});
    ColorMapObject* gcmo = GifMakeMapObject(cc, gpad.data());
    if (!gcmo || EGifPutScreenDesc(g, W, H, 8, 0, gcmo) == GIF_ERROR) {
        if (gcmo) GifFreeMapObject(gcmo); EGifCloseFile(g, &err); return -2;
    }
    std::vector<GifPixelType> row(W);
    for (int i = 0; i < N; ++i) {
        Frame& fr = im->frames[i];
        int tIdx = (fr.bpp == 1) ? fr.transparent : -1;
        bool hasT = (tIdx != NO_TRANSPARENT_COLOR);
        unsigned char ext[4];
        ext[0] = (unsigned char)((DISPOSE_DO_NOT << 2) | (hasT ? 0x01 : 0));
        ext[1] = (unsigned char)((fr.delay / 10) & 0xFF);
        ext[2] = (unsigned char)(((fr.delay / 10) >> 8) & 0xFF);
        ext[3] = (unsigned char)(hasT ? tIdx : 0);
        EGifPutExtension(g, GRAPHICS_EXT_FUNC_CODE, 4, ext);
        ColorMapObject* local = nullptr; std::vector<GifColorType> lpad;
        if (fr.bpp == 1 && fr.hasPalette && !fr.palette.empty()) {
            for (auto& c : fr.palette) lpad.push_back({c.r, c.g, c.b});
            int lc = 2; while (lc < (int)lpad.size()) lc <<= 1;
            lpad.resize(lc, {0, 0, 0}); local = GifMakeMapObject(lc, lpad.data());
        }
        if (EGifPutImageDesc(g, 0, 0, W, H, false, local) == GIF_ERROR) {
            if (local) GifFreeMapObject(local); GifFreeMapObject(gcmo); EGifCloseFile(g, &err); return -3;
        }
        if (fr.bpp == 1) {
            for (int y = 0; y < H; ++y) EGifPutLine(g, (GifPixelType*)(fr.data.data() + (size_t)y * W), W);
        } else {
            for (int y = 0; y < H; ++y) {
                for (int x = 0; x < W; ++x) { uint8_t* p = fr.data.data() + ((size_t)y * W + x) * 4; row[x] = (uint8_t)(((p[0] >> 5) << 5) | ((p[1] >> 5) << 2) | (p[2] >> 6)); }
                EGifPutLine(g, row.data(), W);
            }
        }
        if (local) GifFreeMapObject(local);
    }
    GifFreeMapObject(gcmo);
    return EGifCloseFile(g, &err) == GIF_OK ? 0 : -4;
}

Image* dup_img(Image* im) { return new Image(*im); }

// ---------------- C ABI：生命周期 ----------------
extern "C" {

void* img_open(const char* path) {
    if (!path) return nullptr;
    FILE* fp = fopen(path, "rb"); if (!fp) return nullptr;
    unsigned char sig[6] = {0}; size_t rd = fread(sig, 1, 6, fp); fclose(fp);
    if (rd == 6 && (memcmp(sig, "GIF87a", 6) == 0 || memcmp(sig, "GIF89a", 6) == 0)) return decode_gif(path);
    // WebP（RIFF....WEBP）
    {
        FILE* fp2 = fopen(path, "rb"); unsigned char riff[12] = {0};
        if (fp2) { size_t _r = fread(riff, 1, 12, fp2); (void)_r; fclose(fp2); }
        if (memcmp(riff, "RIFF", 4) == 0 && memcmp(riff + 8, "WEBP", 4) == 0) {
            FILE* f3 = fopen(path, "rb"); fseek(f3, 0, SEEK_END); long sz = ftell(f3); fseek(f3, 0, SEEK_SET);
            std::vector<uint8_t> buf(sz); if (fread(buf.data(), 1, sz, f3) != (size_t)sz) { fclose(f3); return nullptr; } fclose(f3);
            int w = 0, h = 0;
            uint8_t* rgba = WebPDecodeRGBA(buf.data(), sz, &w, &h);
            if (!rgba) return nullptr;
            Image* im = new_rgba(w, h, 1);
            memcpy(im->frames[0].data.data(), rgba, (size_t)w * h * 4);
            WebPFree(rgba);
            return im;
        }
    }
    // TIFF（II*\0 / MM\0*）
    if ((sig[0] == 0x49 && sig[1] == 0x49 && sig[2] == 42) || (sig[0] == 0x4D && sig[1] == 0x4D && sig[2] == 0)) {
        TIFF* tif = TIFFOpen(path, "r");
        if (!tif) return nullptr;
        uint32_t tw = 0, th = 0;
        TIFFGetField(tif, TIFFTAG_IMAGEWIDTH, &tw);
        TIFFGetField(tif, TIFFTAG_IMAGELENGTH, &th);
        if (tw == 0 || th == 0) { TIFFClose(tif); return nullptr; }
        std::vector<uint32_t> raster((size_t)tw * th);
        if (!TIFFReadRGBAImageOriented(tif, tw, th, raster.data(), ORIENTATION_TOPLEFT, 0)) { TIFFClose(tif); return nullptr; }
        TIFFClose(tif);
        Image* im = new_rgba(tw, th, 1);
        uint8_t* o = im->frames[0].data.data();
        for (size_t i = 0; i < (size_t)tw * th; ++i) {
            uint32_t v = raster[i];
            o[i * 4] = TIFFGetR(v); o[i * 4 + 1] = TIFFGetG(v); o[i * 4 + 2] = TIFFGetB(v); o[i * 4 + 3] = TIFFGetA(v);
        }
        return im;
    }
    int w, h, ch; unsigned char* d = stbi_load(path, &w, &h, &ch, 4);
    if (!d) return nullptr;
    Image* im = new_rgba(w, h, 1);
    memcpy(im->frames[0].data.data(), d, (size_t)w * h * 4);
    stbi_image_free(d);
    return im;
}

void* img_new(int w, int h) { return (w > 0 && h > 0) ? new_rgba(w, h, 1) : nullptr; }
void* img_new_mode(int w, int h, const char* mode) { if (w <= 0 || h <= 0) return nullptr; Image* im = new_rgba(w, h, 1); if (mode) im->mode = mode; return im; }
void* img_copy(void* p) { Image* im = (Image*)p; return im ? new Image(*im) : nullptr; }
int img_free(void* p) { Image* im = (Image*)p; if (im) delete im; return 0; }

int img_width(void* p) { Image* im = (Image*)p; return im ? im->w : -1; }
int img_height(void* p) { Image* im = (Image*)p; return im ? im->h : -1; }
int img_count(void* p) { Image* im = (Image*)p; return im ? im->n : -1; }
const char* img_mode(void* p) { Image* im = (Image*)p; return im ? im->mode.c_str() : ""; }
int img_delay(void* p, int i) { Image* im = (Image*)p; return (im && i >= 0 && i < im->n) ? im->frames[i].delay : 0; }
int img_set_delay(void* p, int i, int ms) { Image* im = (Image*)p; if (!im || i < 0 || i >= im->n) return -1; im->frames[i].delay = ms; return 0; }
int img_loop(void* p) { Image* im = (Image*)p; return im ? im->loop : 0; }
int img_set_loop(void* p, int l) { Image* im = (Image*)p; if (!im) return -1; im->loop = l; return 0; }

int img_save(void* p, const char* path) {
    Image* im = (Image*)p; if (!im || !path) return -1;
    if (ends_with(path, ".gif") && im->frames[0].bpp == 1) return encode_gif(im, path);
    Image* rg = (im->frames[0].bpp == 4) ? im : to_rgba(im);
    int ok = 0;
    if (ends_with(path, ".png")) ok = stbi_write_png(path, rg->w, rg->h, 4, rg->frames[0].data.data(), rg->w * 4);
    else if (ends_with(path, ".jpg") || ends_with(path, ".jpeg")) ok = stbi_write_jpg(path, rg->w, rg->h, 4, rg->frames[0].data.data(), 95);
    else if (ends_with(path, ".bmp")) ok = stbi_write_bmp(path, rg->w, rg->h, 4, rg->frames[0].data.data());
    else if (ends_with(path, ".tga")) ok = stbi_write_tga(path, rg->w, rg->h, 4, rg->frames[0].data.data());
    else if (ends_with(path, ".tif") || ends_with(path, ".tiff")) {
        TIFF* tif = TIFFOpen(path, "w");
        if (tif) {
            TIFFSetField(tif, TIFFTAG_IMAGEWIDTH, rg->w);
            TIFFSetField(tif, TIFFTAG_IMAGELENGTH, rg->h);
            TIFFSetField(tif, TIFFTAG_SAMPLESPERPIXEL, 4);
            TIFFSetField(tif, TIFFTAG_BITSPERSAMPLE, 8);
            TIFFSetField(tif, TIFFTAG_ORIENTATION, ORIENTATION_TOPLEFT);
            TIFFSetField(tif, TIFFTAG_PLANARCONFIG, PLANARCONFIG_CONTIG);
            TIFFSetField(tif, TIFFTAG_PHOTOMETRIC, PHOTOMETRIC_RGB);
            uint16_t es = EXTRASAMPLE_ASSOCALPHA;
            TIFFSetField(tif, TIFFTAG_EXTRASAMPLES, 1, &es);
            TIFFSetField(tif, TIFFTAG_ROWSPERSTRIP, TIFFDefaultStripSize(tif, rg->w * 4));
            ok = 1;
            for (int y = 0; y < rg->h; ++y) if (TIFFWriteScanline(tif, rg->frames[0].data.data() + (size_t)y * rg->w * 4, y, 0) < 0) { ok = 0; break; }
            TIFFClose(tif);
        }
    }
    else if (ends_with(path, ".webp")) {
        uint8_t* out = nullptr; size_t len = WebPEncodeRGBA(rg->frames[0].data.data(), rg->w, rg->h, rg->w * 4, 80.0f, &out);
        if (len) { FILE* f = fopen(path, "wb"); if (f) { fwrite(out, 1, len, f); fclose(f); ok = 1; } WebPFree(out); }
    }
    else if (ends_with(path, ".gif")) ok = encode_gif(im, path) == 0;
    else ok = stbi_write_png(path, rg->w, rg->h, 4, rg->frames[0].data.data(), rg->w * 4);
    if (rg != im) delete rg;
    return ok ? 0 : -2;
}

int img_save_frame(void* p, const char* path, int frame) {
    Image* im = (Image*)p; if (!im || frame < 0 || frame >= im->n) return -1;
    Image tmp; tmp.w = im->w; tmp.h = im->h; tmp.n = 1; tmp.frames.push_back(im->frames[frame]);
    return img_save(&tmp, path);
}

int img_frame_bpp(void* p, int i) { Image* im = (Image*)p; return (im && i >= 0 && i < im->n) ? im->frames[i].bpp : 0; }
unsigned char* img_frame_ptr(void* p, int i) { Image* im = (Image*)p; if (!im || i < 0 || i >= im->n) return nullptr; return im->frames[i].data.data(); }
unsigned char* img_pixels(void* p, int i) { return img_frame_ptr(p, i); }

int img_getpixel(void* p, int x, int y) {
    Image* im = (Image*)p; if (!im || x < 0 || x >= im->w || y < 0 || y >= im->h) return 0;
    Image* rg = (im->frames[0].bpp == 4) ? im : to_rgba(im);
    uint8_t* q = px(rg, 0, x, y); int v = pack_rgba(q[0], q[1], q[2], q[3]);
    if (rg != im) delete rg; return v;
}
int img_putpixel(void* p, int x, int y, int rgba) {
    Image* im = (Image*)p; if (!im || x < 0 || x >= im->w || y < 0 || y >= im->h) return -1;
    if (im->frames[0].bpp != 4) { Image* rg = to_rgba(im); im->frames = rg->frames; im->mode = "RGBA"; delete rg; }
    uint8_t* q = px(im, 0, x, y); q[0] = CH_R(rgba); q[1] = CH_G(rgba); q[2] = CH_B(rgba); q[3] = CH_A(rgba); return 0;
}
int img_fill(void* p, int rgba) {
    Image* im = (Image*)p; if (!im) return -1;
    if (im->frames[0].bpp != 4) { Image* rg = to_rgba(im); im->frames = rg->frames; im->mode = "RGBA"; delete rg; }
    for (auto& f : im->frames) for (size_t i = 0; i < f.data.size(); i += 4) { f.data[i] = CH_R(rgba); f.data[i + 1] = CH_G(rgba); f.data[i + 2] = CH_B(rgba); f.data[i + 3] = CH_A(rgba); }
    return 0;
}
unsigned int img_u8_get(void* p, long off) { return *(const unsigned char*)((const char*)p + off); }
int img_u8_set(void* p, long off, int v) { *((char*)p + off) = (char)v; return 0; }
unsigned int img_u32_get(void* p, long off) { unsigned int v; memcpy(&v, (const char*)p + off, 4); return v; }
void img_u32_set(void* p, long off, unsigned int v) { memcpy((char*)p + off, &v, 4); }

unsigned char* img_data_ptr(void* p, int i) { return img_frame_ptr(p, i); }

void* img_frame(void* p, int i) {
    Image* im = (Image*)p; if (!im || i < 0 || i >= im->n) return nullptr;
    Image* o = new Image(); o->w = im->w; o->h = im->h; o->n = 1; o->loop = 0; o->mode = im->mode;
    o->frames.push_back(im->frames[i]);
    return o;
}
int img_set_frame(void* p, int i, void* fp) {
    Image* im = (Image*)p; Image* f = (Image*)fp;
    if (!im || !f || f->n < 1 || i < 0 || i >= im->n) return -1;
    im->frames[i] = f->frames[0];
    return 0;
}
void* img_append_frame(void* p, void* fp) {
    Image* im = (Image*)p; Image* f = (Image*)fp;
    if (!im || !f || f->n < 1) return nullptr;
    Image* o = new Image(*im);
    o->frames.push_back(f->frames[0]);
    o->n = (int)o->frames.size();
    return o;
}

void* img_frombytes(const char* mode, int w, int h, void* data, int len) {
    if (!mode || w <= 0 || h <= 0 || !data) return nullptr;
    std::string m = mode;
    Image* im = new_rgba(w, h, 1);
    const uint8_t* s = (const uint8_t*)data; uint8_t* d = im->frames[0].data.data();
    size_t n = (size_t)w * h;
    if (m == "RGBA") { if (len < (int)(n * 4)) { delete im; return nullptr; } memcpy(d, s, n * 4); }
    else if (m == "RGB") { if (len < (int)(n * 3)) { delete im; return nullptr; } for (size_t i = 0; i < n; ++i) { d[i * 4] = s[i * 3]; d[i * 4 + 1] = s[i * 3 + 1]; d[i * 4 + 2] = s[i * 3 + 2]; d[i * 4 + 3] = 255; } }
    else if (m == "L") { if (len < (int)n) { delete im; return nullptr; } for (size_t i = 0; i < n; ++i) { d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = s[i]; d[i * 4 + 3] = 255; } }
    else if (m == "LA") { if (len < (int)(n * 2)) { delete im; return nullptr; } for (size_t i = 0; i < n; ++i) { d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = s[i * 2]; d[i * 4 + 3] = s[i * 2 + 1]; } }
    else { delete im; return nullptr; }
    im->mode = m;
    return im;
}

int img_tobytes(void* p, int frame, const char* mode, void* out, int outlen) {
    Image* im = (Image*)p; if (!im || frame < 0 || frame >= im->n || !mode || !out) return -1;
    Image* rg = (im->frames[frame].bpp == 4) ? im : to_rgba(im);
    std::string m = mode; size_t n = (size_t)im->w * im->h;
    uint8_t* s = rg->frames[frame].data.data(); uint8_t* o = (uint8_t*)out;
    if (m == "RGBA") { if (outlen < (int)(n * 4)) { if (rg != im) delete rg; return -2; } memcpy(o, s, n * 4); }
    else if (m == "RGB") { if (outlen < (int)(n * 3)) { if (rg != im) delete rg; return -2; } for (size_t i = 0; i < n; ++i) { o[i * 3] = s[i * 4]; o[i * 3 + 1] = s[i * 4 + 1]; o[i * 3 + 2] = s[i * 4 + 2]; } }
    else if (m == "L") { if (outlen < (int)n) { if (rg != im) delete rg; return -2; } for (size_t i = 0; i < n; ++i) o[i] = s[i * 4]; }
    else { if (rg != im) delete rg; return -1; }
    if (rg != im) delete rg;
    return 0;
}

void* img_getchannel(void* p, int ch) {
    Image* im = (Image*)p; if (!im) return nullptr;
    return img_split(p, clampi(ch, 0, 3));
}

}  // extern "C"
