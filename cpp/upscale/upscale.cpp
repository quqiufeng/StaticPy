#include "upscale.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <vector>
#include <cstdint>
#include <cstring>

namespace {
struct Img { int w, h; std::vector<uint8_t> p; };  // RGBA
bool load(const char* path, Img& im) {
    int w, h, c; unsigned char* d = stbi_load(path, &w, &h, &c, 4);
    if (!d) return false; im.w = w; im.h = h; im.p.assign(d, d + (size_t)w * h * 4); stbi_image_free(d); return true;
}
inline const uint8_t* px(const Img& im, int x, int y) {
    x = x < 0 ? 0 : (x >= im.w ? im.w - 1 : x); y = y < 0 ? 0 : (y >= im.h ? im.h - 1 : y);
    return im.p.data() + ((size_t)y * im.w + x) * 4;
}
inline bool eq(const uint8_t* a, const uint8_t* b) { return memcmp(a, b, 4) == 0; }
}

extern "C" {

int up_scale2x(const char* in, const char* out) {
    Img im; if (!load(in, im)) return -1;
    int W = im.w * 2, H = im.h * 2;
    std::vector<uint8_t> o((size_t)W * H * 4, 0);
    for (int y = 0; y < im.h; ++y) for (int x = 0; x < im.w; ++x) {
        const uint8_t* P = px(im, x, y);
        const uint8_t* A = px(im, x, y - 1);   // up
        const uint8_t* B = px(im, x + 1, y);   // right
        const uint8_t* C = px(im, x - 1, y);   // left
        const uint8_t* D = px(im, x, y + 1);   // down
        const uint8_t* E0 = (eq(C, A) && !eq(C, D) && !eq(A, B)) ? A : P;
        const uint8_t* E1 = (eq(A, B) && !eq(A, C) && !eq(B, D)) ? B : P;
        const uint8_t* E2 = (eq(D, C) && !eq(D, B) && !eq(C, A)) ? C : P;
        const uint8_t* E3 = (eq(B, D) && !eq(B, A) && !eq(D, C)) ? D : P;
        auto put = [&](int nx, int ny, const uint8_t* s) { memcpy(o.data() + ((size_t)ny * W + nx) * 4, s, 4); };
        put(x * 2, y * 2, E0); put(x * 2 + 1, y * 2, E1);
        put(x * 2, y * 2 + 1, E2); put(x * 2 + 1, y * 2 + 1, E3);
    }
    return stbi_write_png(out, W, H, 4, o.data(), W * 4) ? 0 : -1;
}

}  // extern "C"
