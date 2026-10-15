// easing.h — Penner 缓动函数，C ABI
#ifndef EASING_H
#define EASING_H
#ifdef __cplusplus
extern "C" {
#endif
double ease(const char* name, double t);   // 未知名称返回 t（linear）
int    ease_known(const char* name);       // 1=支持
#ifdef __cplusplus
}
#endif
#endif
