// warp3d.h — 单应(透视)warp + 2D 图像的 3D 旋转，C ABI。文件进文件出。
#ifndef WARP3D_H
#define WARP3D_H
#ifdef __cplusplus
extern "C" {
#endif
// 透视：h_csv 为 8 个系数（dst->src，行主序 h11..h32），对齐 cv2.warpPerspective 的 M(3x3)
int w3d_perspective(const char* in, const char* out, const char* h_csv, int outw, int outh, int bg);
// 3D 旋转（yaw/pitch/roll 度，绕图像中心，dist=相机距离，f=焦距像素）；输出 outw×outh
int w3d_rotate(const char* in, const char* out, float yaw, float pitch, float roll,
               float dist, float f, int outw, int outh, int bg);
#ifdef __cplusplus
}
#endif
#endif
