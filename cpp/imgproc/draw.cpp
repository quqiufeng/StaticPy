// draw.cpp — ImageDraw（点/线/矩形/圆角矩形/椭圆/多边形/弧）+ ImageFont（stb_truetype）
#include "imgproc.h"
#include "imgproc_internal.h"
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H

namespace {
void ensure_rgba(Image* im) { if (im->frames[0].bpp != 4) { Image* t = to_rgba(im); *im = *t; delete t; } }

void blend_px(Image* im, int x, int y, int rgba) {
    if (x < 0 || x >= im->w || y < 0 || y >= im->h) return;
    float a = CH_A(rgba) / 255.0f;
    uint8_t* p = px(im, 0, x, y);
    p[0] = clamp8(p[0] * (1 - a) + CH_R(rgba) * a);
    p[1] = clamp8(p[1] * (1 - a) + CH_G(rgba) * a);
    p[2] = clamp8(p[2] * (1 - a) + CH_B(rgba) * a);
    p[3] = clamp8((p[3] / 255.0f + a - p[3] / 255.0f * a) * 255);
}

void stamp_disc(Image* im, int cx, int cy, int r, int rgba) {
    for (int y = -r; y <= r; ++y) for (int x = -r; x <= r; ++x) if (x * x + y * y <= r * r) blend_px(im, cx + x, cy + y, rgba);
}

void line_w(Image* im, int x0, int y0, int x1, int y1, int rgba, int width) {
    int dx = abs(x1 - x0), dy = -abs(y1 - y0);
    int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1, err = dx + dy;
    int r = std::max(0, width / 2);
    for (;;) {
        if (r == 0) blend_px(im, x0, y0, rgba); else stamp_disc(im, x0, y0, r, rgba);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

void ellipse_outline(Image* im, int x0, int y0, int x1, int y1, int rgba, int width) {
    float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f, rx = (x1 - x0) / 2.0f, ry = (y1 - y0) / 2.0f;
    if (rx <= 0 || ry <= 0) return;
    int steps = (int)(2 * M_PI * std::max(rx, ry)) + 8;
    int px0 = x0, py0 = (int)cy;
    for (int i = 1; i <= steps; ++i) {
        float t = 2 * M_PI * i / steps;
        int x = (int)std::round(cx + rx * cos(t)), y = (int)std::round(cy + ry * sin(t));
        line_w(im, px0, py0, x, y, rgba, width); px0 = x; py0 = y;
    }
}
void ellipse_fill(Image* im, int x0, int y0, int x1, int y1, int rgba) {
    float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f, rx = (x1 - x0) / 2.0f, ry = (y1 - y0) / 2.0f;
    if (rx <= 0 || ry <= 0) return;
    for (int y = y0; y <= y1; ++y) for (int x = x0; x <= x1; ++x) {
        float nx = (x - cx) / rx, ny = (y - cy) / ry;
        if (nx * nx + ny * ny <= 1.0f) blend_px(im, x, y, rgba);
    }
}
}

extern "C" {

int img_draw_point(void* p, int x, int y, int rgba) { Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im); blend_px(im, x, y, rgba); return 0; }

int img_draw_line(void* p, int x0, int y0, int x1, int y1, int rgba, int width) { Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im); line_w(im, x0, y0, x1, y1, rgba, std::max(1, width)); return 0; }

int img_draw_rectangle(void* p, int x0, int y0, int x1, int y1, int rgba, int width, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (x1 < x0) std::swap(x0, x1); if (y1 < y0) std::swap(y0, y1);
    if (CH_A(fill_rgba)) for (int y = y0; y <= y1; ++y) for (int x = x0; x <= x1; ++x) blend_px(im, x, y, fill_rgba);
    if (CH_A(rgba)) { int w = std::max(1, width); for (int t = 0; t < w; ++t) { for (int x = x0; x <= x1; ++x) { blend_px(im, x, y0 + t, rgba); blend_px(im, x, y1 - t, rgba); } for (int y = y0; y <= y1; ++y) { blend_px(im, x0 + t, y, rgba); blend_px(im, x1 - t, y, rgba); } } }
    return 0;
}

int img_draw_rounded_rect(void* p, int x0, int y0, int x1, int y1, int radius, int rgba, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (x1 < x0) std::swap(x0, x1); if (y1 < y0) std::swap(y0, y1);
    int r = clampi(radius, 0, std::min(x1 - x0, y1 - y0) / 2);
    if (CH_A(fill_rgba)) for (int y = y0; y <= y1; ++y) for (int x = x0; x <= x1; ++x) {
        int cxo = x < x0 + r ? x0 + r : (x > x1 - r ? x1 - r : x);
        int cyo = y < y0 + r ? y0 + r : (y > y1 - r ? y1 - r : y);
        int dx = x - cxo, dy = y - cyo;
        if (dx * dx + dy * dy <= r * r) blend_px(im, x, y, fill_rgba);
    }
    if (CH_A(rgba)) { img_draw_line(im, x0 + r, y0, x1 - r, y0, rgba, 1); img_draw_line(im, x0 + r, y1, x1 - r, y1, rgba, 1); img_draw_line(im, x0, y0 + r, x0, y1 - r, rgba, 1); img_draw_line(im, x1, y0 + r, x1, y1 - r, rgba, 1); ellipse_outline(im, x0, y0, x0 + 2 * r, y0 + 2 * r, rgba, 1); ellipse_outline(im, x1 - 2 * r, y0, x1, y0 + 2 * r, rgba, 1); ellipse_outline(im, x0, y1 - 2 * r, x0 + 2 * r, y1, rgba, 1); ellipse_outline(im, x1 - 2 * r, y1 - 2 * r, x1, y1, rgba, 1); }
    return 0;
}

int img_draw_ellipse(void* p, int x0, int y0, int x1, int y1, int rgba, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (x1 < x0) std::swap(x0, x1); if (y1 < y0) std::swap(y0, y1);
    if (CH_A(fill_rgba)) ellipse_fill(im, x0, y0, x1, y1, fill_rgba);
    if (CH_A(rgba)) ellipse_outline(im, x0, y0, x1, y1, rgba, 1);
    return 0;
}

int img_draw_polygon(void* p, const char* xy_csv, int rgba, int fill_rgba) {
    Image* im = (Image*)p; if (!im || !xy_csv) return -1; ensure_rgba(im);
    std::vector<int> v = parse_csv_ints(xy_csv);
    int n = (int)v.size() / 2; if (n < 2) return -1;
    if (CH_A(fill_rgba)) {
        int miny = im->h, maxy = -1; for (int i = 0; i < n; ++i) { miny = std::min(miny, v[i * 2 + 1]); maxy = std::max(maxy, v[i * 2 + 1]); }
        for (int y = std::max(0, miny); y <= std::min(im->h - 1, maxy); ++y) {
            std::vector<int> xs;
            for (int i = 0; i < n; ++i) {
                int j = (i + 1) % n; int y0 = v[i * 2 + 1], y1 = v[j * 2 + 1];
                if ((y0 <= y && y1 > y) || (y1 <= y && y0 > y)) { int x0 = v[i * 2], x1 = v[j * 2]; xs.push_back(x0 + (int)((double)(y - y0) / (y1 - y0) * (x1 - x0))); }
            }
            std::sort(xs.begin(), xs.end());
            for (size_t k = 0; k + 1 < xs.size(); k += 2) for (int x = xs[k]; x <= xs[k + 1]; ++x) blend_px(im, x, y, fill_rgba);
        }
    }
    if (CH_A(rgba)) for (int i = 0; i < n; ++i) { int j = (i + 1) % n; img_draw_line(im, v[i * 2], v[i * 2 + 1], v[j * 2], v[j * 2 + 1], rgba, 1); }
    return 0;
}

int img_draw_arc(void* p, int x0, int y0, int x1, int y1, float start, float end, int rgba, int width) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (x1 < x0) std::swap(x0, x1); if (y1 < y0) std::swap(y0, y1);
    float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f, rx = (x1 - x0) / 2.0f, ry = (y1 - y0) / 2.0f;
    int steps = (int)(fabs(end - start) * std::max(rx, ry) / 30) + 8;
    int px0 = 0, py0 = 0;
    for (int i = 0; i <= steps; ++i) { float t = (start + (end - start) * i / steps) * M_PI / 180.0f; int x = (int)std::round(cx + rx * cos(t)), y = (int)std::round(cy + ry * sin(t)); if (i) line_w(im, px0, py0, x, y, rgba, std::max(1, width)); px0 = x; py0 = y; }
    return 0;
}

static void sector_fill(Image* im, int x0, int y0, int x1, int y1, float start, float end, int rgba, bool chord) {
    if (x1 < x0) std::swap(x0, x1); if (y1 < y0) std::swap(y0, y1);
    float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f, rx = (x1 - x0) / 2.0f, ry = (y1 - y0) / 2.0f;
    if (rx <= 0 || ry <= 0) return;
    float s = start, e = end; while (e < s) e += 360;
    // 弦端点（chord 时用于判断在弧一侧）
    float a1 = s * M_PI / 180.0f, a2 = e * M_PI / 180.0f;
    float px1 = cx + rx * cos(a1), py1 = cy + ry * sin(a1);
    float px2 = cx + rx * cos(a2), py2 = cy + ry * sin(a2);
    for (int y = std::max(0, y0); y <= std::min(im->h - 1, y1); ++y) for (int x = std::max(0, x0); x <= std::min(im->w - 1, x1); ++x) {
        float nx = (x - cx) / rx, ny = (y - cy) / ry;
        if (nx * nx + ny * ny > 1.0f) continue;
        float ang = atan2(ny, nx) * 180.0f / M_PI; if (ang < 0) ang += 360; float a = ang; while (a < s) a += 360;
        if (a > e) continue;
        if (chord) {
            // 必须在弦的弧一侧（叉积同号）
            float cross = (px2 - px1) * (y - py1) - (py2 - py1) * (x - px1);
            float mid = (s + e) / 2.0f * M_PI / 180.0f;
            float mx = cx + rx * cos(mid), my = cy + ry * sin(mid);
            float cross2 = (px2 - px1) * (my - py1) - (py2 - py1) * (mx - px1);
            if ((cross > 0) != (cross2 > 0)) continue;
        }
        blend_px(im, x, y, rgba);
    }
}

int img_draw_pieslice(void* p, int x0, int y0, int x1, int y1, float s, float e, int rgba, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (CH_A(fill_rgba)) sector_fill(im, x0, y0, x1, y1, s, e, fill_rgba, false);
    if (CH_A(rgba)) { float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f; img_draw_line(im, (int)cx, (int)cy, (int)(cx + (x1 - x0) / 2.0 * cos(s * M_PI / 180)), (int)(cy + (y1 - y0) / 2.0 * sin(s * M_PI / 180)), rgba, 1); img_draw_line(im, (int)cx, (int)cy, (int)(cx + (x1 - x0) / 2.0 * cos(e * M_PI / 180)), (int)(cy + (y1 - y0) / 2.0 * sin(e * M_PI / 180)), rgba, 1); img_draw_arc(im, x0, y0, x1, y1, s, e, rgba, 1); }
    return 0;
}

int img_draw_chord(void* p, int x0, int y0, int x1, int y1, float s, float e, int rgba, int fill_rgba) {
    Image* im = (Image*)p; if (!im) return -1; ensure_rgba(im);
    if (CH_A(fill_rgba)) sector_fill(im, x0, y0, x1, y1, s, e, fill_rgba, true);
    if (CH_A(rgba)) { float cx = (x0 + x1) / 2.0f, cy = (y0 + y1) / 2.0f, rxx = (x1 - x0) / 2.0f, ryy = (y1 - y0) / 2.0f; img_draw_line(im, (int)(cx + rxx * cos(s * M_PI / 180)), (int)(cy + ryy * sin(s * M_PI / 180)), (int)(cx + rxx * cos(e * M_PI / 180)), (int)(cy + ryy * sin(e * M_PI / 180)), rgba, 1); img_draw_arc(im, x0, y0, x1, y1, s, e, rgba, 1); }
    return 0;
}

// ---------------- ImageFont（FreeType，运行时链接 libfreetype.so.6，对齐 Pillow）----------------
#define FT_PIXEL(x) ((((x) + 32) & -64) >> 6)
static FT_Library g_ft = nullptr;
static void ft_init() { if (!g_ft) FT_Init_FreeType(&g_ft); }

void* img_font_load(const char* ttf_path, float pxsz) {
    if (!ttf_path) return nullptr;
    ft_init();
    FT_Face face;
    if (FT_New_Face(g_ft, ttf_path, 0, &face)) return nullptr;
    FT_Size_RequestRec req;
    req.type = FT_SIZE_REQUEST_TYPE_NOMINAL;
    req.width = (FT_Long)(pxsz * 64);
    req.height = (FT_Long)(pxsz * 64);
    req.horiResolution = 0; req.vertResolution = 0;
    FT_Request_Size(face, &req);
    Font* f = new Font();
    f->info = face;
    f->px = pxsz;
    f->ascent = FT_PIXEL(face->size->metrics.ascender);
    f->descent = FT_PIXEL(face->size->metrics.descender);
    return f;
}
int img_font_free(void* fp) { Font* f = (Font*)fp; if (f) { FT_Done_Face((FT_Face)f->info); delete f; } return 0; }
int img_font_text_height(void* fp) { Font* f = (Font*)fp; if (!f) return 0; FT_Face face = (FT_Face)f->info; long a = FT_PIXEL(face->size->metrics.ascender), d = FT_PIXEL(face->size->metrics.descender); return (int)(a - d); }

int img_font_text_width(void* fp, const char* s) {
    Font* f = (Font*)fp; if (!f || !s) return 0;
    FT_Face face = (FT_Face)f->info;
    long pos = 0;
    for (const unsigned char* p = (const unsigned char*)s; *p;) {
        int cp = *p; int len = 1;
        if (cp >= 0xF0) { cp = ((p[0] & 7) << 18) | ((p[1] & 63) << 12) | ((p[2] & 63) << 6) | (p[3] & 63); len = 4; }
        else if (cp >= 0xE0) { cp = ((p[0] & 15) << 12) | ((p[1] & 63) << 6) | (p[2] & 63); len = 3; }
        else if (cp >= 0xC0) { cp = ((p[0] & 31) << 6) | (p[1] & 63); len = 2; }
        FT_UInt idx = FT_Get_Char_Index(face, cp);
        if (FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT)) { p += len; continue; }
        pos += face->glyph->metrics.horiAdvance;
        p += len;
    }
    return (int)FT_PIXEL(pos);
}

// 字体文字 bbox：对齐 Pillow FreeTypeFont.getbbox（CBox 累加）
int img_font_bbox(void* fp, const char* s, char* out, int outlen) {
    Font* f = (Font*)fp; if (!f || !s || !out) return -1;
    FT_Face face = (FT_Face)f->info;
    long position = 0;
    int x_min = 0, x_max = 0, y_min = 0, y_max = 0;
    for (const unsigned char* p = (const unsigned char*)s; *p;) {
        int cp = *p; int len = 1;
        if (cp >= 0xF0) { cp = ((p[0] & 7) << 18) | ((p[1] & 63) << 12) | ((p[2] & 63) << 6) | (p[3] & 63); len = 4; }
        else if (cp >= 0xE0) { cp = ((p[0] & 15) << 12) | ((p[1] & 63) << 6) | (p[2] & 63); len = 3; }
        else if (cp >= 0xC0) { cp = ((p[0] & 31) << 6) | (p[1] & 63); len = 2; }
        FT_UInt idx = FT_Get_Char_Index(face, cp);
        int px = (int)FT_PIXEL(position), py = 0;
        if (!FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT)) {
            FT_Glyph glyph;
            if (!FT_Get_Glyph(face->glyph, &glyph)) {
                FT_BBox bb; FT_Glyph_Get_CBox(glyph, FT_GLYPH_BBOX_PIXELS, &bb);
                if (bb.xMax + px > x_max) x_max = bb.xMax + px;
                if (bb.xMin + px < x_min) x_min = bb.xMin + px;
                if (bb.yMax + py > y_max) y_max = bb.yMax + py;
                if (bb.yMin + py < y_min) y_min = bb.yMin + py;
                FT_Done_Glyph(glyph);
            }
            position += face->glyph->advance.x;
            int adv = (int)FT_PIXEL(position);
            if (adv > x_max) x_max = adv;
        }
        p += len;
    }
    long y_anchor = FT_PIXEL(face->size->metrics.ascender);
    snprintf(out, outlen, "%d,%d,%d,%d", x_min, (int)(y_anchor - y_max), x_max, (int)(y_anchor - y_min));
    return 0;
}

// 多行文字（行距 = ascent - descent + spacing）
int img_draw_multiline_text(void* ip, int x, int y, const char* s, void* fp, int rgba, int spacing) {
    Font* f = (Font*)fp; if (!ip || !f || !s) return -1;
    FT_Face face = (FT_Face)f->info;
    long lineh = FT_PIXEL(face->size->metrics.ascender) - FT_PIXEL(face->size->metrics.descender) + spacing;
    int ly = y;
    std::string line;
    for (const char* p = s;; ++p) {
        if (*p == '\n' || *p == '\0') {
            if (!line.empty()) img_draw_text(ip, x, ly, line.c_str(), fp, rgba);
            line.clear();
            if (*p == '\0') break;
            ly += (int)lineh;
        } else line += *p;
    }
    return 0;
}

int img_draw_text(void* ip, int x, int y, const char* s, void* fp, int rgba) {
    Image* im = (Image*)ip; Font* f = (Font*)fp; if (!im || !f || !s) return -1; ensure_rgba(im);
    FT_Face face = (FT_Face)f->info;
    long ascent = FT_PIXEL(face->size->metrics.ascender);
    long baseline = y + ascent;   // anchor "la"：ascender 在 y
    long pos = 0;
    for (const unsigned char* p = (const unsigned char*)s; *p;) {
        int cp = *p; int len = 1;
        if (cp >= 0xF0) { cp = ((p[0] & 7) << 18) | ((p[1] & 63) << 12) | ((p[2] & 63) << 6) | (p[3] & 63); len = 4; }
        else if (cp >= 0xE0) { cp = ((p[0] & 15) << 12) | ((p[1] & 63) << 6) | (p[2] & 63); len = 3; }
        else if (cp >= 0xC0) { cp = ((p[0] & 31) << 6) | (p[1] & 63); len = 2; }
        FT_UInt idx = FT_Get_Char_Index(face, cp);
        if (!FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT | FT_LOAD_RENDER)) {
            int px = (int)FT_PIXEL(pos);
            FT_Bitmap& bm = face->glyph->bitmap;
            int left = face->glyph->bitmap_left, top = face->glyph->bitmap_top;
            for (unsigned by = 0; by < bm.rows; ++by) for (unsigned bx = 0; bx < bm.width; ++bx) {
                int cov = bm.pixel_mode == FT_PIXEL_MODE_GRAY ? bm.buffer[by * bm.pitch + bx] : (bm.buffer[by * bm.pitch + (bx >> 3)] & (0x80 >> (bx & 7)) ? 255 : 0);
                if (!cov) continue;
                blend_px(im, x + px + left + (int)bx, (int)baseline - top + (int)by, pack_rgba(CH_R(rgba), CH_G(rgba), CH_B(rgba), CH_A(rgba) * cov / 255));
            }
            pos += face->glyph->advance.x;
        }
        p += len;
    }
    return 0;
}

}  // extern "C"
