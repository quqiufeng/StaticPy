// sr.h — 超分/高清放大（Real-ESRGAN x4 ONNX，ORT 推理），C ABI
#ifndef SRN_H
#define SRN_H
#ifdef __cplusplus
extern "C" {
#endif
int sr_upscale(const char* in, const char* out);   // 4x
#ifdef __cplusplus
}
#endif
#endif
