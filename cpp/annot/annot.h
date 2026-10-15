#ifndef ANNOT_H
#define ANNOT_H
#ifdef __cplusplus
extern "C" {
#endif
int an_depth(const char* in, const char* out);   // 深度图（越近越亮）
int an_hed(const char* in, const char* out);      // HED 软边缘
#ifdef __cplusplus
}
#endif
#endif
