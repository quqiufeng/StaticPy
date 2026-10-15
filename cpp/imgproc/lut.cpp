// lut.cpp — Pillow ColorLUT.c 的 3D LUT 精确移植（ImagingColorLUT3D_linear，定点三线性）
#include "imgproc.h"
#include "imgproc_internal.h"

extern "C" {

void* img_lut3d(void* p, const char* table_csv, int channels, int s1, int s2, int s3) {
    Image* im = (Image*)p; if (!im || !table_csv || channels < 3 || channels > 4) return nullptr;
    std::vector<float> t = parse_csv_floats(table_csv);
    size_t need = (size_t)channels * s1 * s2 * s3;
    if (t.size() < need) return nullptr;
    const int PB = 6;
    const double sc = (double)(255 << PB);
    std::vector<int16_t> tab(need);
    for (size_t i = 0; i < need; ++i) {
        double item = t[i];
        if (item >= (0x7fff - 0.5) / sc) tab[i] = 0x7fff;
        else if (item <= (-0x8000 + 0.5) / sc) tab[i] = (int16_t)-0x8000;
        else tab[i] = (int16_t)(item < 0 ? item * sc - 0.5 : item * sc + 0.5);
    }
    Image* rg = (im->frames[0].bpp == 4) ? im : to_rgba(im);
    int W = rg->w, H = rg->h;
    Image* o = new_rgba(W, H, rg->n); o->loop = rg->loop;
    const int SB = 32 - 8 - 6, SHIFT = 16 - 1, SMASK = (1 << SB) - 1;
    uint32_t scale1 = (uint32_t)((double)(s1 - 1) / 255.0 * (1 << SB));
    uint32_t scale2 = (uint32_t)((double)(s2 - 1) / 255.0 * (1 << SB));
    uint32_t scale3 = (uint32_t)((double)(s3 - 1) / 255.0 * (1 << SB));
    int s1_2 = s1 * s2;
    auto clip8 = [](int in) { int v = (in + 32) >> 6; return (uint8_t)(v < 0 ? 0 : (v > 255 ? 255 : v)); };
    auto interp = [&](int16_t out[], const int16_t a[], const int16_t b[], int shift, int ch) {
        for (int c = 0; c < ch; ++c) out[c] = (int16_t)((a[c] * ((1 << SHIFT) - shift) + b[c] * shift) >> SHIFT);
    };
    for (int f = 0; f < rg->n; ++f) {
        uint8_t* in = rg->frames[f].data.data(); uint8_t* out = o->frames[f].data.data();
        for (long i = 0; i < (long)W * H; ++i) {
            uint8_t* px = in + i * 4; uint8_t* d = out + i * 4;
            uint32_t i1 = px[0] * scale1, i2 = px[1] * scale2, i3 = px[2] * scale3;
            int sh1 = (SMASK & i1) >> (SB - SHIFT), sh2 = (SMASK & i2) >> (SB - SHIFT), sh3 = (SMASK & i3) >> (SB - SHIFT);
            int idx = channels * ((int)(i1 >> SB) + (int)(i2 >> SB) * s1 + (int)(i3 >> SB) * s1_2);
            int16_t leftleft[4], leftright[4], left[4], rightleft[4], rightright[4], right[4], res[4];
            const int16_t* T = tab.data();
            interp(leftleft, &T[idx], &T[idx + channels], sh1, channels);
            interp(leftright, &T[idx + s1 * channels], &T[idx + s1 * channels + channels], sh1, channels);
            interp(left, leftleft, leftright, sh2, channels);
            interp(rightleft, &T[idx + s1_2 * channels], &T[idx + s1_2 * channels + channels], sh1, channels);
            interp(rightright, &T[idx + s1_2 * channels + s1 * channels], &T[idx + s1_2 * channels + s1 * channels + channels], sh1, channels);
            interp(right, rightleft, rightright, sh2, channels);
            interp(res, left, right, sh3, channels);
            d[0] = clip8(res[0]); d[1] = clip8(res[1]); d[2] = clip8(res[2]);
            d[3] = (channels == 4) ? clip8(res[3]) : px[3];
        }
    }
    if (rg != im) delete rg;
    return o;
}

}  // extern "C"
