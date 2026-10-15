// atlas.h — 精灵图集打包（MaxRects-BSSF），C ABI
#ifndef ATLAS_H
#define ATLAS_H
#ifdef __cplusplus
extern "C" {
#endif
// sizes_csv: 每张图 "w,h;"（分号分隔）。返回 JSON:
// {"packed":N,"total":M,"sheet":[sw,sh],"placements":[[x,y,w,h],...]}（静态缓冲）
const char* atlas_pack_json(const char* sizes_csv, int sw, int sh);
#ifdef __cplusplus
}
#endif
#endif
