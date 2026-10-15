#ifndef DET_H
#define DET_H
#ifdef __cplusplus
extern "C" {
#endif
const char* det_json(const char* in, float thresh);      // [{"label","score","box":[x0,y0,x1,y1]}]
int det_draw(const char* in, const char* out, float thresh);
#ifdef __cplusplus
}
#endif
#endif
