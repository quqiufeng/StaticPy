// effects.cpp — 图像效果 / 生成器（对齐 Pillow Effects.c）
#include "imgproc.h"
#include "imgproc_internal.h"
#include <cstdlib>

namespace {
Image* new_L(int w, int h) {
    Image* im = new Image(); im->w = w; im->h = h; im->n = 1; im->mode = "L";
    im->frames.resize(1); im->frames[0].bpp = 4; im->frames[0].data.assign((size_t)w * h * 4, 0);
    for (size_t i = 0; i < (size_t)w * h; ++i) im->frames[0].data[i * 4 + 3] = 255;
    return im;
}
inline void setL(Image* im, int x, int y, int v) { uint8_t* p = im->frames[0].data.data() + ((size_t)y * im->w + x) * 4; p[0] = p[1] = p[2] = (uint8_t)v; p[3] = 255; }
}

extern "C" {

// ImagingEffectMandelbrot
void* img_effect_mandelbrot(int xsize, int ysize, float x0, float y0, float x1, float y1, int quality) {
    double width = x1 - x0, height = y1 - y0;
    if (width < 0.0 || height < 0.0 || quality < 2 || xsize < 1 || ysize < 1) return nullptr;
    Image* im = new_L(xsize, ysize);
    double dr = width / (xsize - 1), di = height / (ysize - 1), radius = 100.0;
    for (int y = 0; y < ysize; ++y) for (int x = 0; x < xsize; ++x) {
        double x1v = 0, y1v = 0, xi2 = 0, yi2 = 0;
        double cr = x * dr + x0, ci = y * di + y0;
        int v = 0;
        for (int k = 1;; ++k) {
            y1v = 2 * x1v * y1v + ci;
            x1v = xi2 - yi2 + cr;
            xi2 = x1v * x1v; yi2 = y1v * y1v;
            if ((xi2 + yi2) > radius) { v = k * 255 / quality; break; }
            if (k > quality) { v = 0; break; }
        }
        setL(im, x, y, v);
    }
    return im;
}

// ImagingEffectNoise（Gaussian 居中 128；C rand() 不可复现，仅功能等价）
void* img_effect_noise(int xsize, int ysize, float sigma) {
    Image* im = new_L(xsize, ysize);
    double next = 0; int nextok = 0;
    for (int y = 0; y < ysize; ++y) for (int x = 0; x < xsize; ++x) {
        double thisv;
        if (nextok) { thisv = next; nextok = 0; }
        else {
            double v1, v2, r;
            do { v1 = rand() * (2.0 / RAND_MAX) - 1.0; v2 = rand() * (2.0 / RAND_MAX) - 1.0; r = v1 * v1 + v2 * v2; } while (r >= 1.0);
            double f = sqrt(-2.0 * log(r) / r);
            thisv = f * v1; next = f * v2; nextok = 1;
        }
        setL(im, x, y, clamp8(128 + sigma * thisv));
    }
    return im;
}

// Image.linear_gradient（纯 Python 版）：256x256 纵向 0..255
void* img_linear_gradient(void) {
    Image* im = new_L(256, 256);
    for (int y = 0; y < 256; ++y) for (int x = 0; x < 256; ++x) setL(im, x, y, y);
    return im;
}

}  // extern "C"

extern "C" {
// Image.radial_gradient：256x256，中心黑到边缘白
void* img_radial_gradient(void) {
    Image* im = new_L(256, 256);
    for (int y = 0; y < 256; ++y) for (int x = 0; x < 256; ++x) {
        int dx = x - 128, dy = y - 128;
        int d = (int)sqrt((double)(dx * dx + dy * dy) * 2.0);
        setL(im, x, y, d >= 255 ? 255 : d);
    }
    return im;
}
}
