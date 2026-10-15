// imgproc.h — 独立图像处理底层库（C ABI），对标 Pillow 的 C 核心 libImaging + 编解码
//
// 供 StaticPy 经 FFI 运行时加载（imgproc/imgproc_ffi.scm）。与推理栈无关。
//
// 覆盖目标（对齐 Pillow 模块）：
//   Image 核心 / 编解码（GIF·PNG·JPEG·BMP·TGA·PPM）/ 几何 / 模式转换 / 调色板
//   ImageOps / ImageChops / ImageEnhance / ImageFilter / ImageStat / ImageDraw / ImageFont
//
// 约定：像素统一 RGBA8；坐标 (x,y)，颜色打包为 0xRRGGBBAA（int）。
// 多值参数（点列、LUT、调色板）用 CSV 字符串传（FFI 不擅长数组）。
// 返回新图像的函数返回 handle（失败返回 NULL）；就地函数返回 int(0=成功)。
#ifndef IMGPROC_H
#define IMGPROC_H

#ifdef __cplusplus
extern "C" {
#endif

/* ============================ 生命周期 ============================ */
void*       img_open(const char* path);                       // 解码（GIF 多帧，其余单帧）
void*       img_new(int w, int h);                            // RGBA 透明底
void*       img_new_mode(int w, int h, const char* mode);
void*       img_copy(void* im);
int         img_free(void* im);

int         img_width(void* im);
int         img_height(void* im);
int         img_count(void* im);                              // 帧数
const char* img_mode(void* im);                               // "RGBA"/"RGB"/"L"/"LA"/"P"
int         img_delay(void* im, int i);
int         img_set_delay(void* im, int i, int ms);
int         img_loop(void* im);
int         img_set_loop(void* im, int loop);

/* ============================ 编解码 ============================ */
int         img_save(void* im, const char* path);             // 按扩展名（.gif/.png/.jpg/.bmp/.tga/.ppm）
int         img_save_frame(void* im, const char* path, int frame);

/* ============================ 像素访问 ============================ */
int         img_frame_bpp(void* im, int i);                   // 1=索引 4=RGBA（兼容）
unsigned char* img_frame_ptr(void* im, int i);
unsigned char* img_pixels(void* im, int i);                   // 同 frame_ptr（兼容旧名）
int         img_getpixel(void* im, int x, int y);             // 0xRRGGBBAA
int         img_putpixel(void* im, int x, int y, int rgba);
int         img_fill(void* im, int rgba);
unsigned int img_u8_get(void* p, long off);
int          img_u8_set(void* p, long off, int v);
unsigned int img_u32_get(void* p, long off);
void         img_u32_set(void* p, long off, unsigned int v);

/* ============================ 几何 ============================ */
void*       img_crop(void* im, int x, int y, int w, int h);
void*       img_resize(void* im, int w, int h, const char* resample);      // nearest/bilinear/bicubic/lanczos
void*       img_resize_ex(void* im, int w, int h, const char* resample, float bx0, float by0, float bx1, float by1);
void*       img_thumbnail(void* im, int w, int h);                          // 就地缩放到 fit
void*       img_rotate(void* im, float deg, int expand, int fill_rgba);
void*       img_transpose(void* im, int method);   // 0 FLIP_LR 1 FLIP_TB 2 ROT90 3 ROT180 4 ROT270 5 TRANSPOSE 6 TRANSVERSE
void*       img_pad(void* im, int l, int t, int r, int b, int rgba);
void*       img_scale(void* im, float fx, float fy, const char* resample);
void*       img_paste(void* base, void* src, int x, int y);                 // 覆盖（不含 alpha）
void*       img_paste_mask(void* base, void* src, int x, int y, void* mask); // 按 mask 的 L 值混合
void*       img_composite(void* base, void* over);                          // alpha 合成（同尺寸）
void*       img_blend(void* a, void* b, float alpha);                       // a*(1-a)+b*a
void*       img_getbbox(void* im, int rgba);                                // 非背景包围盒
void*       img_warp(void* im, int w, int h, const char* coords_csv, const char* resample);
int         img_getbbox4(void* im, int rgba, char* out_csv, int out_len);   // "x0,y0,x1,y1"

/* ============================ 颜色 / 模式 / 调色板 ============================ */
void*       img_convert(void* im, const char* mode);
void*       img_convert_p(void* im, int dither);
void*       img_split(void* im, int channel);                               // -> L
void*       img_merge_rgb(void* r, void* g, void* b);
void*       img_point(void* im, int channel, const char* lut_csv);          // 256 项 LUT
void*       img_quantize(void* im, int colors, int method);                 // 0 median,1 maxcov,2 fastoctree
int         img_putpalette(void* im, const char* rgb_csv);
void*       img_remap_palette(void* im, const char* data_csv);
int         img_getcolors(void* im, int maxcolors, char* out_csv, int outlen);
int         img_getpalette(void* im, char* out_csv, int out_len);

/* ============================ ImageOps ============================ */
void*       img_invert(void* im);
void*       img_grayscale(void* im);
void*       img_posterize(void* im, int bits);
void*       img_solarize(void* im, int threshold);
void*       img_autocontrast(void* im, int cutoff);
void*       img_equalize(void* im);
void*       img_colorize(void* im, int black, int white, const char* mid_csv);
void*       img_mirror(void* im);       // = transpose FLIP_LR
void*       img_expand(void* im, int border, int rgba);

/* ============================ ImageChops ============================ */
void*       img_chop(void* a, void* b, const char* op);  // add/subtract/difference/multiply/screen/darker/lighter/blend/soft_light/hard_light/logical_and/logical_or/logical_xor
void*       img_chop_const(void* im, const char* op, int v);
void*       img_chop_offset(void* im, int dx, int dy);

/* ============================ ImageEnhance ============================ */
void*       img_enhance(void* im, const char* kind, float factor);  // color/contrast/brightness/sharpness

/* ============================ ImageFilter ============================ */
void*       img_filter(void* im, const char* name, float r1, float r2, int i1);

/* ============================ ImageStat ============================ */
int         img_stat(void* im, const char* what, char* out_csv, int out_len); // mean/median/extrema/stddev/sum

/* ============================ ImageDraw（就地画） ============================ */
int         img_draw_point(void* im, int x, int y, int rgba);
int         img_draw_line(void* im, int x0, int y0, int x1, int y1, int rgba, int width);
int         img_draw_rectangle(void* im, int x0, int y0, int x1, int y1, int rgba, int width, int fill_rgba);
int         img_draw_rounded_rect(void* im, int x0, int y0, int x1, int y1, int radius, int rgba, int fill_rgba);
int         img_draw_ellipse(void* im, int x0, int y0, int x1, int y1, int rgba, int fill_rgba);
int         img_draw_polygon(void* im, const char* xy_csv, int rgba, int fill_rgba);
int         img_draw_arc(void* im, int x0, int y0, int x1, int y1, float start, float end, int rgba, int width);

/* ==================== 数据进出 / 通道 / 更多 Ops ==================== */
unsigned char* img_data_ptr(void* im, int frame);                            // 原始像素首地址
void*       img_frame(void* im, int i);                                      // 取单帧 -> 新图
int         img_set_frame(void* im, int i, void* frame);
void*       img_append_frame(void* im, void* frame);                         // 追加一帧
void*       img_chops_composite(void* a, void* b, void* mask);               // a*(1-mask)+b*mask
int         img_getextrema(void* im, char* out_csv, int outlen);             // rmin,rmax,gmin,gmax,...
void*       img_frombytes(const char* mode, int w, int h, void* data, int len);
int         img_tobytes(void* im, int frame, const char* mode, void* out, int outlen);
void*       img_getchannel(void* im, int ch);                                // -> L 图（0R1G2B3A）
void*       img_alpha_composite_at(void* base, void* over, int x, int y);    // 就地
void*       img_fit(void* im, int w, int h, const char* resample, float cx, float cy, int fill_rgba);
void*       img_contain(void* im, int w, int h, const char* resample, int fill_rgba);
void*       img_ops_pad(void* im, int w, int h, const char* resample, int color_rgba, float cx, float cy);
int         img_color_getrgb(const char* color, char* out_csv, int outlen);  // ImageColor.getrgb
void*       img_effect_mandelbrot(int w, int h, float x0, float y0, float x1, float y1, int quality);
void*       img_effect_noise(int w, int h, float sigma);
void*       img_linear_gradient(void);
void*       img_radial_gradient(void);
void*       img_lut3d(void* im, const char* table_csv, int channels, int s1, int s2, int s3);
int         img_draw_chord(void* im, int x0, int y0, int x1, int y1, float s, float e, int rgba, int fill_rgba);
int         img_draw_pieslice(void* im, int x0, int y0, int x1, int y1, float s, float e, int rgba, int fill_rgba);

/* ============================ ImageFont / 文字 ============================ */
void*       img_font_load(const char* ttf_path, float px);
int         img_font_free(void* font);
int         img_font_text_width(void* font, const char* utf8);
int         img_font_text_height(void* font);
int         img_draw_text(void* im, int x, int y, const char* utf8, void* font, int rgba);
int         img_font_bbox(void* font, const char* utf8, char* out_csv, int outlen);
int         img_draw_multiline_text(void* im, int x, int y, const char* utf8, void* font, int rgba, int spacing);
void*       img_putalpha(void* im, void* alpha);

#ifdef __cplusplus
}
#endif

#endif  // IMGPROC_H
