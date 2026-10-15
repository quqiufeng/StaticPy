// cvops.h — 经典图像处理/优化算法（形态学/阈值/梯度），C ABI。文件进文件出。
#ifndef CVOPS_H
#define CVOPS_H
#ifdef __cplusplus
extern "C" {
#endif
int cvo_erode(const char* in, const char* out, int k);      // 灰度腐蚀，k×k 矩形核
int cvo_dilate(const char* in, const char* out, int k);     // 膨胀
int cvo_open(const char* in, const char* out, int k);       // 开运算
int cvo_close(const char* in, const char* out, int k);      // 闭运算
int cvo_threshold_otsu(const char* in, const char* out, int inv);   // Otsu 二值化
int cvo_sobel(const char* in, const char* out, int dx, int dy);     // Sobel 梯度（|G|）
int cvo_erode_rgb(const char* in, const char* out, int k);
int cvo_dilate_rgb(const char* in, const char* out, int k);
#ifdef __cplusplus
}
#endif
#endif
