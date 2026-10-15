#include "warp3d.h"
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"
#include <vector>
#include <string>
#include <cmath>
#include <cstdlib>

namespace {
struct Img { int w, h, c; std::vector<uint8_t> p; };
bool load(const char* path, Img& im, int ch) {
    int c; unsigned char* d = stbi_load(path, &im.w, &im.h, &c, ch);
    if (!d) return false; im.c = ch; im.p.assign(d, d + (size_t)im.w * im.h * ch); stbi_image_free(d); return true;
}
inline uint8_t *at(Img& im, int x, int y) { return im.p.data() + ((size_t)y * im.w + x) * im.c; }

// 双线性采样，越界返回 bg
void sample(const Img& im, double sx, double sy, int bg, uint8_t* out) {
    int x0 = (int)std::floor(sx), y0 = (int)std::floor(sy);
    double tx = sx - x0, ty = sy - y0;
    for (int c = 0; c < im.c; ++c) {
        double v = 0;
        for (int j = 0; j < 2; ++j) for (int i = 0; i < 2; ++i) {
            int xx = x0 + i, yy = y0 + j;
            double w = (i ? tx : 1 - tx) * (j ? ty : 1 - ty);
            double val = (xx < 0 || xx >= im.w || yy < 0 || yy >= im.h) ? bg
                       : im.p[((size_t)yy * im.w + xx) * im.c + c];
            v += w * val;
        }
        out[c] = (uint8_t)std::lround(v);
    }
}

// 透视 warp：dst(x,y) -> src via H
int do_warp(const Img& im, const char* out, const double H[8], int ow, int oh, int bg) {
    Img o; o.w = ow; o.h = oh; o.c = im.c; o.p.assign((size_t)ow * oh * im.c, 0);
    for (int y = 0; y < oh; ++y) for (int x = 0; x < ow; ++x) {
        double w = H[6] * x + H[7] * y + 1.0;
        double sx = (H[0] * x + H[1] * y + H[2]) / w;
        double sy = (H[3] * x + H[4] * y + H[5]) / w;
        sample(im, sx, sy, bg, at(o, x, y));
    }
    return stbi_write_png(out, ow, oh, im.c, o.p.data(), ow * im.c) ? 0 : -1;
}

// 4 点求单应（从 (dx,dy) 到 (sx,sy)），8x8 高斯消元
bool homography(const double d[4][2], const double s[4][2], double H[8]) {
    double a[8][9];
    for (int i = 0; i < 4; ++i) {
        double dx = d[i][0], dy = d[i][1], sx = s[i][0], sy = s[i][1];
        a[i * 2]     [0]=dx; a[i*2][1]=dy; a[i*2][2]=1; a[i*2][3]=0; a[i*2][4]=0; a[i*2][5]=0; a[i*2][6]=-dx*sx; a[i*2][7]=-dy*sx; a[i*2][8]=sx;
        a[i * 2 + 1] [0]=0;  a[i*2+1][1]=0; a[i*2+1][2]=0; a[i*2+1][3]=dx; a[i*2+1][4]=dy; a[i*2+1][5]=1; a[i*2+1][6]=-dx*sy; a[i*2+1][7]=-dy*sy; a[i*2+1][8]=sy;
    }
    for (int col = 0; col < 8; ++col) {
        int piv = col; for (int r = col + 1; r < 8; ++r) if (std::fabs(a[r][col]) > std::fabs(a[piv][col])) piv = r;
        if (std::fabs(a[piv][col]) < 1e-12) return false;
        for (int k = 0; k < 9; ++k) std::swap(a[col][k], a[piv][k]);
        double dv = a[col][col];
        for (int k = col; k < 9; ++k) a[col][k] /= dv;
        for (int r = 0; r < 8; ++r) if (r != col) { double f = a[r][col]; for (int k = col; k < 9; ++k) a[r][k] -= f * a[col][k]; }
    }
    for (int i = 0; i < 8; ++i) H[i] = a[i][8];
    return true;
}
}

extern "C" {

int w3d_perspective(const char* in, const char* out, const char* h_csv, int ow, int oh, int bg) {
    Img im; if (!load(in, im, 4)) return -1;
    double H[8]; const char* p = h_csv;
    for (int i = 0; i < 8; ++i) { H[i] = strtod(p, (char**)&p); while (*p == ',' || *p == ' ') ++p; }
    return do_warp(im, out, H, ow, oh, bg);
}

int w3d_rotate(const char* in, const char* out, float yaw, float pitch, float roll,
               float dist, float f, int ow, int oh, int bg) {
    Img im; if (!load(in, im, 4)) return -1;
    double cy = std::cos(yaw * M_PI / 180), sy = std::sin(yaw * M_PI / 180);
    double cp = std::cos(pitch * M_PI / 180), sp = std::sin(pitch * M_PI / 180);
    double cr = std::cos(roll * M_PI / 180), sr = std::sin(roll * M_PI / 180);
    // R = Rz * Ry * Rx
    auto rot = [&](double X, double Y, double Z, double& ox, double& oy, double& oz) {
        double x1 = X, y1 = cr * Y - sr * Z, z1 = sr * Y + cr * Z;          // Rx
        double x2 = cy * x1 + sy * z1, y2 = y1, z2 = -sy * x1 + cy * z1;    // Ry
        ox = cp * x2 - sp * y2; oy = sp * x2 + cp * y2; oz = z2;            // Rz(with pitch)
    };
    double hw = im.w / 2.0, hh = im.h / 2.0;
    double src[4][2] = {{0,0},{hw*2,0},{hw*2,hh*2},{0,hh*2}};
    double dst[4][2];
    double cx = ow / 2.0, cyy = oh / 2.0;
    for (int i = 0; i < 4; ++i) {
        double X = src[i][0] - hw, Y = src[i][1] - hh, Z = 0;
        double rx, ry, rz; rot(X, Y, Z, rx, ry, rz);
        double Zc = rz + dist;
        dst[i][0] = cx + f * rx / Zc; dst[i][1] = cyy + f * ry / Zc;
    }
    double H[8]; if (!homography(dst, src, H)) return -2;
    return do_warp(im, out, H, ow, oh, bg);
}

}  // extern "C"
