// cf.h — CodeFormer 人脸修复/高清修复（ONNX, ORT），C ABI
#ifndef CF_H
#define CF_H
#ifdef __cplusplus
extern "C" {
#endif
int cf_restore(const char* in, const char* out, double w);   // 输入→512→修复→输出512
#ifdef __cplusplus
}
#endif
#endif
