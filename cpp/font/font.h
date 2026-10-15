// font.h — TTF → 字形图集 + 度量（游戏用位图字体），C ABI
#ifndef FONTX_H
#define FONTX_H
#ifdef __cplusplus
extern "C" {
#endif
// ttf: 字体文件; px: 像素字号; charset: 需烘焙的字符串(UTF-8);
// 输出 out_png(灰度图集) 与 out_json(度量)。返回 0 成功。
int font_atlas(const char* ttf, int px, const char* charset,
               const char* out_png, const char* out_json, int atlas_w);
#ifdef __cplusplus
}
#endif
#endif
