// upscale.h — 像素画高清放大（Scale2x/3x，EPX），C ABI
#ifndef UPSCALE_H
#define UPSCALE_H
#ifdef __cplusplus
extern "C" {
#endif
int up_scale2x(const char* in, const char* out);   // 2x
#ifdef __cplusplus
}
#endif
#endif
