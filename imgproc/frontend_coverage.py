#!/usr/bin/env python3
"""frontend_coverage.py — 用 PIL 自省清单核对我们的覆盖面。

把 PIL 顶层函数/类/方法 映射到 libimgproc 的 C ABI 名（MAP 表），
统计已实现 / 未实现，输出覆盖率报告（markdown）。

用法: /data/venv/bin/python imgproc/frontend_coverage.py
"""
import inspect
import importlib

# PIL 名 -> libimgproc C ABI 名（None = 已知未覆盖）
MAP = {
    ("Image", "new"): "img_new", ("Image", "open"): "img_open", ("Image", "blend"): "img_blend",
    ("Image", "composite"): "img_chops_composite", ("Image", "alpha_composite"): "img_alpha_composite_at",
    ("Image", "frombytes"): "img_frombytes", ("Image", "merge"): "img_merge_rgb",
    ("Image", "effect_mandelbrot"): "img_effect_mandelbrot", ("Image", "effect_noise"): "img_effect_noise",
    ("Image", "linear_gradient"): "img_linear_gradient",
    ("Image", "eval"): "pil_eval(需编译器 lambda 支持)", ("Image", "frombuffer"): "img_frombytes", ("Image", "radial_gradient"): "img_radial_gradient",
    ("Image", "effect_spread"): None, ("Image", "getmodebands"): "pil_getmodebands", ("Image", "getmodebase"): "pil_getmodebase",
    ("ImageOps", "autocontrast"): "img_autocontrast", ("ImageOps", "colorize"): "img_colorize",
    ("ImageOps", "contain"): "img_contain", ("ImageOps", "equalize"): "img_equalize",
    ("ImageOps", "expand"): "img_expand", ("ImageOps", "fit"): "img_fit", ("ImageOps", "flip"): "img_transpose",
    ("ImageOps", "grayscale"): "img_grayscale", ("ImageOps", "invert"): "img_invert",
    ("ImageOps", "mirror"): "img_mirror", ("ImageOps", "pad"): "img_ops_pad",
    ("ImageOps", "posterize"): "img_posterize", ("ImageOps", "scale"): "img_scale",
    ("ImageOps", "solarize"): "img_solarize", ("ImageOps", "exif_transpose"): "pil_exif_transpose",
    ("ImageOps", "deform"): "pil_ops_deform(逆向映射)", ("ImageOps", "crop"): "img_crop",
    ("ImageChops", "add"): "img_chop", ("ImageChops", "subtract"): "img_chop",
    ("ImageChops", "difference"): "img_chop", ("ImageChops", "multiply"): "img_chop",
    ("ImageChops", "screen"): "img_chop", ("ImageChops", "darker"): "img_chop",
    ("ImageChops", "lighter"): "img_chop", ("ImageChops", "add_modulo"): "img_chop",
    ("ImageChops", "subtract_modulo"): "img_chop", ("ImageChops", "soft_light"): "img_chop",
    ("ImageChops", "hard_light"): "img_chop", ("ImageChops", "overlay"): "img_chop",
    ("ImageChops", "logical_and"): "img_chop", ("ImageChops", "logical_or"): "img_chop",
    ("ImageChops", "logical_xor"): "img_chop", ("ImageChops", "invert"): "img_invert",
    ("ImageChops", "constant"): "img_new", ("ImageChops", "blend"): "img_blend",
    ("ImageChops", "composite"): "img_chops_composite", ("ImageChops", "offset"): "img_chop_offset",
    ("ImageFilter", "BLUR"): "img_filter", ("ImageFilter", "CONTOUR"): "img_filter",
    ("ImageFilter", "DETAIL"): "img_filter", ("ImageFilter", "EDGE_ENHANCE"): "img_filter",
    ("ImageFilter", "EDGE_ENHANCE_MORE"): "img_filter", ("ImageFilter", "EMBOSS"): "img_filter",
    ("ImageFilter", "FIND_EDGES"): "img_filter", ("ImageFilter", "SHARPEN"): "img_filter",
    ("ImageFilter", "SMOOTH"): "img_filter", ("ImageFilter", "SMOOTH_MORE"): "img_filter",
    ("ImageFilter", "BoxBlur"): "img_filter", ("ImageFilter", "GaussianBlur"): "img_filter",
    ("ImageFilter", "UnsharpMask"): "img_filter", ("ImageFilter", "MedianFilter"): "img_filter",
    ("ImageFilter", "MinFilter"): "img_filter", ("ImageFilter", "MaxFilter"): "img_filter",
    ("ImageFilter", "ModeFilter"): "img_filter", ("ImageFilter", "RankFilter"): "img_filter",
    ("ImageFilter", "Color3DLUT"): "img_lut3d", ("ImageFilter", "GaussianBlur"): "img_filter",
    ("ImageEnhance", "Color"): "img_enhance", ("ImageEnhance", "Contrast"): "img_enhance",
    ("ImageEnhance", "Brightness"): "img_enhance", ("ImageEnhance", "Sharpness"): "img_enhance",
    ("ImageStat", "Stat"): "img_stat",
    ("ImageDraw", "Draw"): "img_draw_*",
    ("ImageFont", "truetype"): "img_font_load", ("ImageFont", "load_default"): "img_font_load",
    ("ImageColor", "getrgb"): "img_color_getrgb", ("ImageColor", "getcolor"): "img_color_getrgb",
    ("ImageSequence", "Iterator"): "img_frame",
    # Image.Image 方法（走对应 C ABI）
    ("Image.Image", "convert"): "img_convert", ("Image.Image", "resize"): "img_resize",
    ("Image.Image", "crop"): "img_crop", ("Image.Image", "rotate"): "img_rotate",
    ("Image.Image", "transpose"): "img_transpose", ("Image.Image", "paste"): "img_paste",
    ("Image.Image", "thumbnail"): "img_thumbnail", ("Image.Image", "quantize"): "img_quantize(Quant.c 精确)",
    ("Image.Image", "getpixel"): "img_getpixel", ("Image.Image", "putpixel"): "img_putpixel",
    ("Image.Image", "split"): "img_split", ("Image.Image", "getbbox"): "img_getbbox4",
    ("Image.Image", "getcolors"): "img_getcolors", ("Image.Image", "getchannel"): "img_getchannel",
    ("Image.Image", "putalpha"): "img_putalpha", ("Image.Image", "tobytes"): "img_tobytes",
    ("Image.Image", "save"): "img_save", ("Image.Image", "getpalette"): "img_getpalette",
    ("Image.Image", "putpalette"): "img_putpalette", ("Image.Image", "getextrema"): "img_getextrema",
    ("Image.Image", "convert"): "img_convert",
}

MODULES = [("Image", "PIL.Image"), ("ImageOps", "PIL.ImageOps"), ("ImageChops", "PIL.ImageChops"),
           ("ImageFilter", "PIL.ImageFilter"), ("ImageEnhance", "PIL.ImageEnhance"),
           ("ImageStat", "PIL.ImageStat"), ("ImageDraw", "PIL.ImageDraw"), ("ImageFont", "PIL.ImageFont"),
           ("ImageColor", "PIL.ImageColor"), ("ImageSequence", "PIL.ImageSequence")]


def names(mod):
    out = []
    for n in dir(mod):
        if n.startswith("_"):
            continue
        o = getattr(mod, n, None)
        if inspect.isclass(o) or inspect.isfunction(o) or inspect.isbuiltin(o):
            out.append(n)
    return sorted(out)


def main():
    covered = 0; total = 0; missing = []
    print("# PIL 覆盖面核对（自省生成）\n")
    print("| 模块 | 名字 | 我们的实现 |")
    print("|---|---|---|")
    for short, modname in MODULES:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for n in names(mod):
            key = (short, n)
            if key in MAP:
                total += 1
                if MAP[key]:
                    covered += 1
                    print(f"| {short} | `{n}` | `{MAP[key]}` |")
                else:
                    missing.append(f"{short}.{n}")
                    print(f"| {short} | `{n}` | — (待做) |")
    # Image.Image 方法
    try:
        from PIL import Image
        for n in sorted(x for x in dir(Image.Image) if not x.startswith("_")):
            key = ("Image.Image", n)
            if key in MAP:
                total += 1
                if MAP[key]:
                    covered += 1
                    print(f"| Image.Image | `{n}` | `{MAP[key]}` |")
                else:
                    missing.append(f"Image.Image.{n}")
    except Exception:
        pass
    print(f"\n**覆盖 {covered}/{total}（{100*covered//max(total,1)}%）**")
    if missing:
        print("\n待做：" + ", ".join(missing))


main()
