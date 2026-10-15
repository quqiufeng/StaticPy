"""pyimgproc — libimgproc.so 的 ctypes 绑定（镜像 C ABI）。

用途：自动化差分测试（对比 Pillow）用，迭代快。生产走 imgproc/*.static.py（StaticPy ELF）。
"""
import ctypes as C
import os

_SO = os.environ.get("IMGPROC_SO", "/opt/static_comfyui/cpp/imgproc/build/libimgproc.so")
L = C.CDLL(_SO)
_P = C.c_void_p


def _sig(name, ret, args):
    f = getattr(L, name)
    f.restype = ret
    f.argtypes = args
    return f


_p = _P
_ci = C.c_int
_cf = C.c_float
_cs = C.c_char_p

img_open = _sig("img_open", _p, [_cs])
img_new = _sig("img_new", _p, [_ci, _ci])
img_free = _sig("img_free", _ci, [_p])
img_copy = _sig("img_copy", _p, [_p])
img_width = _sig("img_width", _ci, [_p])
img_height = _sig("img_height", _ci, [_p])
img_count = _sig("img_count", _ci, [_p])
img_mode = _sig("img_mode", C.c_char_p, [_p])
img_save = _sig("img_save", _ci, [_p, _cs])
img_fill = _sig("img_fill", _ci, [_p, _ci])
img_set_delay = _sig("img_set_delay", _ci, [_p, _ci, _ci])

img_crop = _sig("img_crop", _p, [_p, _ci, _ci, _ci, _ci])
img_scale = _sig("img_scale", _p, [_p, _cf, _cf, _cs])
img_resize = _sig("img_resize", _p, [_p, _ci, _ci, _cs])
img_rotate = _sig("img_rotate", _p, [_p, _cf, _ci, _ci])
img_transpose = _sig("img_transpose", _p, [_p, _ci])
img_pad = _sig("img_pad", _p, [_p, _ci, _ci, _ci, _ci, _ci])
img_paste = _sig("img_paste", _p, [_p, _p, _ci, _ci])
img_paste_mask = _sig("img_paste_mask", _p, [_p, _p, _ci, _ci, _p])
img_composite = _sig("img_composite", _p, [_p, _p])
img_blend = _sig("img_blend", _p, [_p, _p, _cf])
img_getbbox4 = _sig("img_getbbox4", _ci, [_p, _ci, C.c_char_p, _ci])

img_convert = _sig("img_convert", _p, [_p, _cs])
img_convert_p = _sig("img_convert_p", _p, [_p, _ci])
img_split = _sig("img_split", _p, [_p, _ci])
img_merge_rgb = _sig("img_merge_rgb", _p, [_p, _p, _p])
img_point = _sig("img_point", _p, [_p, _ci, _cs])
img_quantize = _sig("img_quantize", _p, [_p, _ci, _ci])
img_remap_palette = _sig("img_remap_palette", _p, [_p, _cs])
img_getpalette = _sig("img_getpalette", _ci, [_p, C.c_char_p, _ci])
img_getcolors = _sig("img_getcolors", _ci, [_p, _ci, C.c_char_p, _ci])

img_invert = _sig("img_invert", _p, [_p])
img_grayscale = _sig("img_grayscale", _p, [_p])
img_posterize = _sig("img_posterize", _p, [_p, _ci])
img_solarize = _sig("img_solarize", _p, [_p, _ci])
img_autocontrast = _sig("img_autocontrast", _p, [_p, _ci])
img_equalize = _sig("img_equalize", _p, [_p])
img_colorize = _sig("img_colorize", _p, [_p, _ci, _ci, _cs])
img_expand = _sig("img_expand", _p, [_p, _ci, _ci])
img_mirror = _sig("img_mirror", _p, [_p])

img_chop = _sig("img_chop", _p, [_p, _p, _cs])
img_chop_const = _sig("img_chop_const", _p, [_p, _cs, _ci])
img_chop_offset = _sig("img_chop_offset", _p, [_p, _ci, _ci])
img_enhance = _sig("img_enhance", _p, [_p, _cs, _cf])
img_filter = _sig("img_filter", _p, [_p, _cs, _cf, _cf, _ci])
img_stat = _sig("img_stat", _ci, [_p, _cs, C.c_char_p, _ci])

img_frame_ptr = _sig("img_frame_ptr", _p, [_p, _ci])
img_frame_bpp = _sig("img_frame_bpp", _ci, [_p, _ci])

img_draw_point = _sig("img_draw_point", _ci, [_p, _ci, _ci, _ci])
img_draw_line = _sig("img_draw_line", _ci, [_p, _ci, _ci, _ci, _ci, _ci, _ci])
img_draw_rectangle = _sig("img_draw_rectangle", _ci, [_p, _ci, _ci, _ci, _ci, _ci, _ci, _ci])
img_draw_rounded_rect = _sig("img_draw_rounded_rect", _ci, [_p, _ci, _ci, _ci, _ci, _ci, _ci, _ci])
img_draw_ellipse = _sig("img_draw_ellipse", _ci, [_p, _ci, _ci, _ci, _ci, _ci, _ci])
img_draw_polygon = _sig("img_draw_polygon", _ci, [_p, _cs, _ci, _ci])
img_draw_arc = _sig("img_draw_arc", _ci, [_p, _ci, _ci, _ci, _ci, _cf, _cf, _ci, _ci])

img_data_ptr = _sig("img_data_ptr", _p, [_p, _ci])
img_frame = _sig("img_frame", _p, [_p, _ci])
img_set_frame = _sig("img_set_frame", _ci, [_p, _ci, _p])
img_append_frame = _sig("img_append_frame", _p, [_p, _p])
img_chops_composite = _sig("img_chops_composite", _p, [_p, _p, _p])
img_getextrema = _sig("img_getextrema", _ci, [_p, C.c_char_p, _ci])
img_frombytes = _sig("img_frombytes", _p, [_cs, _ci, _ci, _p, _ci])
img_tobytes = _sig("img_tobytes", _ci, [_p, _ci, _cs, _p, _ci])
img_getchannel = _sig("img_getchannel", _p, [_p, _ci])
img_alpha_composite_at = _sig("img_alpha_composite_at", _p, [_p, _p, _ci, _ci])
img_fit = _sig("img_fit", _p, [_p, _ci, _ci, _cs, _cf, _cf, _ci])
img_ops_pad = _sig("img_ops_pad", _p, [_p, _ci, _ci, _cs, _ci, _cf, _cf])
img_contain = _sig("img_contain", _p, [_p, _ci, _ci, _cs, _ci])
img_color_getrgb = _sig("img_color_getrgb", _ci, [_cs, C.c_char_p, _ci])
img_effect_mandelbrot = _sig("img_effect_mandelbrot", _p, [_ci, _ci, _cf, _cf, _cf, _cf, _ci])
img_effect_noise = _sig("img_effect_noise", _p, [_ci, _ci, _cf])
img_linear_gradient = _sig("img_linear_gradient", _p, [])
img_radial_gradient = _sig("img_radial_gradient", _p, [])
img_draw_chord = _sig("img_draw_chord", _ci, [_p, _ci, _ci, _ci, _ci, _cf, _cf, _ci, _ci])
img_draw_pieslice = _sig("img_draw_pieslice", _ci, [_p, _ci, _ci, _ci, _ci, _cf, _cf, _ci, _ci])

img_font_load = _sig("img_font_load", _p, [_cs, _cf])
img_font_free = _sig("img_font_free", _ci, [_p])
img_font_text_width = _sig("img_font_text_width", _ci, [_p, _cs])
img_font_bbox = _sig("img_font_bbox", _ci, [_p, _cs, C.c_char_p, _ci])
img_draw_multiline_text = _sig("img_draw_multiline_text", _ci, [_p, _ci, _ci, _cs, _p, _ci, _ci])
img_putalpha = _sig("img_putalpha", _p, [_p, _p])
img_draw_text = _sig("img_draw_text", _ci, [_p, _ci, _ci, _cs, _p, _ci])


# ---- numpy 便捷层（测试用；从 RGBA8 缓冲读回）----
def to_np(handle):
    import numpy as np
    w, h = img_width(handle), img_height(handle)
    ptr = img_frame_ptr(handle, 0)
    buf = C.string_at(ptr, w * h * 4)
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4).copy()


def from_np(arr):
    import numpy as np
    h, w = arr.shape[:2]
    im = img_new(w, h)
    if arr.shape[2] == 3:
        rgba = np.dstack([arr, np.full((h, w, 1), 255, np.uint8)]).astype(np.uint8)
    else:
        rgba = arr.astype(np.uint8)
    C.memmove(img_frame_ptr(im, 0), rgba.tobytes(), w * h * 4)
    return im


def open_np(path):
    return to_np(img_open(path))

img_thumbnail = _sig("img_thumbnail", _p, [_p, _ci, _ci])
img_getpixel = _sig("img_getpixel", _ci, [_p, _ci, _ci])
img_putpixel = _sig("img_putpixel", _ci, [_p, _ci, _ci, _ci])
img_lut3d = _sig("img_lut3d", _p, [_p, _cs, _ci, _ci, _ci, _ci])
img_warp = _sig("img_warp", _p, [_p, _ci, _ci, _cs, _cs])
