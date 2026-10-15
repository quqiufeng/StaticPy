# pil.static.py — StaticPy 版 Pillow 前端（对标自省清单，函数式 API）
#
# Pillow 是类/方法式；StaticPy 无继承，故这里用「函数式」API：第一参数是图像句柄。
# 用法（CLI 分发）: pil <op> IN OUT [args...]
#   作为库用：本文件可与其他 .static.py 一起被 concat 进同一 ELF。
#
# 覆盖自省清单里的核心算子；底层能力来自运行时加载的 libimgproc.so。

extern fn img_open(path: str) -> ptr from "imgproc"
extern fn img_save(im: ptr, path: str) -> int from "imgproc"
extern fn img_free(im: ptr) -> int from "imgproc"
extern fn img_copy(im: ptr) -> ptr from "imgproc"
extern fn img_width(im: ptr) -> int from "imgproc"
extern fn img_height(im: ptr) -> int from "imgproc"
extern fn img_count(im: ptr) -> int from "imgproc"
extern fn img_mode(im: ptr) -> str from "imgproc"
extern fn img_convert(im: ptr, mode: str) -> ptr from "imgproc"
extern fn img_convert_p(im: ptr, dither: int) -> ptr from "imgproc"
extern fn img_resize(im: ptr, w: int, h: int, rs: str) -> ptr from "imgproc"
extern fn img_scale(im: ptr, fx: float, fy: float, rs: str) -> ptr from "imgproc"
extern fn img_thumbnail(im: ptr, w: int, h: int) -> ptr from "imgproc"
extern fn img_crop(im: ptr, x: int, y: int, w: int, h: int) -> ptr from "imgproc"
extern fn img_rotate(im: ptr, deg: float, expand: int, fill: int) -> ptr from "imgproc"
extern fn img_transpose(im: ptr, m: int) -> ptr from "imgproc"
extern fn img_mirror(im: ptr) -> ptr from "imgproc"
extern fn img_pad(im: ptr, l: int, t: int, r: int, b: int, rgba: int) -> ptr from "imgproc"
extern fn img_warp(im: ptr, w: int, h: int, coords_csv: str, resample: str) -> ptr from "imgproc"
extern fn img_fit(im: ptr, w: int, h: int, rs: str, cx: float, cy: float, fill: int) -> ptr from "imgproc"
extern fn img_contain(im: ptr, w: int, h: int, rs: str, fill: int) -> ptr from "imgproc"
extern fn img_ops_pad(im: ptr, w: int, h: int, rs: str, rgba: int, cx: float, cy: float) -> ptr from "imgproc"
extern fn img_invert(im: ptr) -> ptr from "imgproc"
extern fn img_grayscale(im: ptr) -> ptr from "imgproc"
extern fn img_posterize(im: ptr, bits: int) -> ptr from "imgproc"
extern fn img_solarize(im: ptr, thr: int) -> ptr from "imgproc"
extern fn img_autocontrast(im: ptr, cutoff: int) -> ptr from "imgproc"
extern fn img_equalize(im: ptr) -> ptr from "imgproc"
extern fn img_colorize(im: ptr, black: int, white: int, mid_csv: str) -> ptr from "imgproc"
extern fn img_expand(im: ptr, border: int, rgba: int) -> ptr from "imgproc"
extern fn img_chop(a: ptr, b: ptr, op: str) -> ptr from "imgproc"
extern fn img_chop_const(im: ptr, op: str, v: int) -> ptr from "imgproc"
extern fn img_chop_offset(im: ptr, dx: int, dy: int) -> ptr from "imgproc"
extern fn img_chops_composite(a: ptr, b: ptr, mask: ptr) -> ptr from "imgproc"
extern fn img_enhance(im: ptr, kind: str, factor: float) -> ptr from "imgproc"
extern fn img_filter(im: ptr, name: str, r1: float, r2: float, i1: int) -> ptr from "imgproc"
extern fn img_point(im: ptr, ch: int, lut_csv: str) -> ptr from "imgproc"
extern fn img_quantize(im: ptr, colors: int, method: int) -> ptr from "imgproc"
extern fn img_split(im: ptr, ch: int) -> ptr from "imgproc"
extern fn img_putalpha(im: ptr, alpha: ptr) -> ptr from "imgproc"
extern fn img_effect_mandelbrot(w: int, h: int, x0: float, y0: float, x1: float, y1: float, q: int) -> ptr from "imgproc"
extern fn img_stat(im: ptr, what: str, out: str, n: int) -> int from "imgproc"
extern fn img_getcolors(im: ptr, mx: int, out: str, n: int) -> int from "imgproc"
extern fn img_blend(a: ptr, b: ptr, alpha: float) -> ptr from "imgproc"
extern fn img_alpha_composite_at(base: ptr, over: ptr, x: int, y: int) -> ptr from "imgproc"
extern fn img_font_load(path: str, px: float) -> ptr from "imgproc"
extern fn img_draw_text(im: ptr, x: int, y: int, s: str, font: ptr, rgba: int) -> int from "imgproc"
extern fn img_draw_line(im: ptr, x0: int, y0: int, x1: int, y1: int, rgba: int, w: int) -> int from "imgproc"
extern fn img_draw_rectangle(im: ptr, x0: int, y0: int, x1: int, y1: int, rgba: int, w: int, fill: int) -> int from "imgproc"
extern fn img_draw_ellipse(im: ptr, x0: int, y0: int, x1: int, y1: int, rgba: int, fill: int) -> int from "imgproc"


def a(args, i: str) -> str:
    return py_list_ref(args, string_to_int(i))


def ai(args, i: str) -> int:
    return string_to_int(py_list_ref(args, string_to_int(i)))



# ---- Pillow 模块级辅助（纯函数）----
def pil_getmodebands(mode: str) -> int:
    if mode == "1" or mode == "L" or mode == "P" or mode == "I" or mode == "F":
        return 1
    if mode == "LA" or mode == "PA":
        return 2
    if mode == "RGB" or mode == "YCbCr" or mode == "HSV" or mode == "CMYK":
        return 3
    if mode == "RGBA" or mode == "RGBX" or mode == "CMYK;I":
        return 4
    return 0


def pil_getmodebase(mode: str) -> str:
    if mode == "1" or mode == "L" or mode == "P" or mode == "I" or mode == "F" or mode == "LA" or mode == "PA":
        return "L"
    if mode == "RGB" or mode == "RGBA" or mode == "RGBX" or mode == "YCbCr" or mode == "HSV":
        return "RGB"
    return ""


def pil_exif_transpose(im: ptr) -> ptr:
    # 未解析 EXIF orientation，等价于原样返回（无 EXIF 时 Pillow 亦然）
    return img_copy(im)


def pil_eval(im: ptr, fn) -> ptr:
    # 对齐 Pillow Image.eval：对每个通道套用 fn（对 0..255 建 LUT 后 point）
    lut: str = ""
    v: int = 0
    while v < 256:
        if v > 0:
            lut = lut + ","
        lut = lut + string_of_int(fn(v))
        v = v + 1
    return img_point(im, -1, lut)


def pil_ops_deform(im: ptr, fnx, fny) -> ptr:
    # ImageOps.deform 的逆向映射用法：fnx/fny(x,y)->源坐标
    w: int = img_width(im)
    h: int = img_height(im)
    csv: str = ""
    y: int = 0
    while y < h:
        x: int = 0
        while x < w:
            if x > 0 or y > 0:
                csv = csv + ","
            csv = csv + format_float(fnx(x, y), 4) + "," + format_float(fny(x, y), 4)
            x = x + 1
        y = y + 1
    return img_warp(im, w, h, csv, "bilinear")
