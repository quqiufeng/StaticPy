// cl.h — 图像上色（DDColor ONNX），C ABI
#ifndef CL_H
#define CL_H
#ifdef __cplusplus
extern "C" {
#endif
int cl_colorize(const char* in, const char* out);   // 灰度→彩色
#ifdef __cplusplus
}
#endif
#endif
