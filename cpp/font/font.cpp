// font.cpp — FreeType 光栅化 + shelf 打包（对齐 Pillow 的 FreeType 度量）
#include "font.h"
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <vector>
#include <string>
#include <cstdio>

namespace {
struct Glyph { int cp; int x, y, w, h, bx, by, adv; };
int decode_utf8(const unsigned char*& p) {
    int c = *p; int len = 1, cp = c;
    if (c >= 0xF0) { cp = ((p[0]&7)<<18)|((p[1]&63)<<12)|((p[2]&63)<<6)|(p[3]&63); len = 4; }
    else if (c >= 0xE0) { cp = ((p[0]&15)<<12)|((p[1]&63)<<6)|(p[2]&63); len = 3; }
    else if (c >= 0xC0) { cp = ((p[0]&31)<<6)|(p[1]&63); len = 2; }
    p += len; return cp;
}
}

extern "C" {

int font_atlas(const char* ttf, int px, const char* charset,
               const char* out_png, const char* out_json, int atlas_w) {
    FT_Library lib; if (FT_Init_FreeType(&lib)) return -1;
    FT_Face face; if (FT_New_Face(lib, ttf, 0, &face)) { FT_Done_FreeType(lib); return -1; }
    FT_Size_RequestRec req; req.type = FT_SIZE_REQUEST_TYPE_NOMINAL;
    req.width = (FT_Long)px * 64; req.height = (FT_Long)px * 64; req.horiResolution = 0; req.vertResolution = 0;
    FT_Request_Size(face, &req);

    std::vector<Glyph> glyphs;
    std::vector<std::vector<unsigned char>> bitmaps;
    const unsigned char* p = (const unsigned char*)charset;
    while (*p) {
        int cp = decode_utf8(p);
        FT_UInt idx = FT_Get_Char_Index(face, cp);
        if (!FT_Load_Glyph(face, idx, FT_LOAD_DEFAULT | FT_LOAD_RENDER)) {
            FT_Bitmap& bm = face->glyph->bitmap;
            Glyph g; g.cp = cp; g.w = (int)bm.width; g.h = (int)bm.rows;
            g.bx = face->glyph->bitmap_left; g.by = face->glyph->bitmap_top;
            g.adv = face->glyph->advance.x >> 6;
            std::vector<unsigned char> b((size_t)g.w * g.h, 0);
            for (int yy = 0; yy < g.h; ++yy) for (int xx = 0; xx < g.w; ++xx)
                b[(size_t)yy * g.w + xx] = bm.buffer != nullptr ? bm.buffer[yy * bm.pitch + xx] : 0;
            glyphs.push_back(g); bitmaps.push_back(std::move(b));
        }
    }
    FT_Done_Face(face); FT_Done_FreeType(lib);

    // shelf 打包
    int W = atlas_w > 0 ? atlas_w : 512;
    int x = 0, y = 0, shelfH = 0;
    for (auto& g : glyphs) {
        if (g.w == 0 || g.h == 0) { g.x = 0; g.y = 0; continue; }
        if (x + g.w > W) { x = 0; y += shelfH + 1; shelfH = 0; }
        g.x = x; g.y = y; x += g.w + 1; shelfH = (shelfH > g.h) ? shelfH : g.h;
    }
    int H = y + shelfH + 1; if (H < 1) H = 1;
    std::vector<unsigned char> atlas((size_t)W * H, 0);
    for (size_t i = 0; i < glyphs.size(); ++i) {
        Glyph& g = glyphs[i]; if (g.w == 0 || g.h == 0) continue;
        for (int yy = 0; yy < g.h; ++yy) for (int xx = 0; xx < g.w; ++xx)
            atlas[(size_t)(g.y + yy) * W + (g.x + xx)] = bitmaps[i][(size_t)yy * g.w + xx];
    }
    if (!stbi_write_png(out_png, W, H, 1, atlas.data(), W)) return -2;

    // 度量 JSON
    std::string js = "{\"size\":" + std::to_string(px) + ",\"width\":" + std::to_string(W) + ",\"height\":" + std::to_string(H) + ",\"glyphs\":[";
    char buf[256];
    for (size_t i = 0; i < glyphs.size(); ++i) {
        Glyph& g = glyphs[i];
        snprintf(buf, sizeof buf,
            "%s{\"cp\":%d,\"x\":%d,\"y\":%d,\"w\":%d,\"h\":%d,\"bx\":%d,\"by\":%d,\"advance\":%d}",
            i ? "," : "", g.cp, g.x, g.y, g.w, g.h, g.bx, g.by, g.adv);
        js += buf;
    }
    js += "]}";
    FILE* f = fopen(out_json, "wb"); if (!f) return -3;
    fwrite(js.data(), 1, js.size(), f); fclose(f);
    return 0;
}

}  // extern "C"
