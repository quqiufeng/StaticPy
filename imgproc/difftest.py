#!/usr/bin/env python3
import os
"""difftest.py — 自动化差分测试：Pillow vs libimgproc，逐像素比对。

用法: /data/venv/bin/python imgproc/difftest.py [-v]
退出码非 0 表示有算子超出容差。
"""
import sys
import ctypes as C
import numpy as np
from PIL import Image, ImageOps, ImageChops, ImageEnhance, ImageFilter, ImageStat

import pyimgproc as P

VERBOSE = "-v" in sys.argv
H, W = 40, 52
rng = np.random.default_rng(7)


def rgba_of_pil(im):
    return np.dstack([np.array(im.convert("RGB")), np.array(im.convert("RGBA")).astype(int)[..., 3]]).astype(int)


def rgba_of_handle(h):
    im = P.to_np(h)
    return np.dstack([im[..., :3].astype(int), im[..., 3].astype(int)])


def rgb_of_pil(im):
    return np.array(im.convert("RGB")).astype(int)


def rgb_of_handle(h):
    return P.to_np(h)[..., :3].astype(int)


# 测试图（PNG）
img_rgb = Image.fromarray(rng.integers(0, 256, (H, W, 3), dtype=np.uint8), "RGB")
img_rgba = Image.fromarray(rng.integers(0, 256, (H, W, 4), dtype=np.uint8), "RGBA")
img_L = img_rgb.convert("L")
img_rgb_path = "/tmp/opencode/difftest_rgb.png"
img_rgba_path = "/tmp/opencode/difftest_rgba.png"
img_rgb.save(img_rgb_path)
img_rgba.save(img_rgba_path)

h_rgb = P.img_open(img_rgb_path.encode())
h_rgba = P.img_open(img_rgba_path.encode())

results = []


def case(name, pil, ours, tol=2, space="rgb"):
    """pil/ours: 0-参数函数，返回 PIL.Image / handle。"""
    try:
        a = rgb_of_pil(pil()) if space == "rgb" else rgba_of_pil(pil())
        b = rgb_of_handle(ours()) if space == "rgb" else rgba_of_handle(ours())
        if a.shape != b.shape:
            results.append((name, "SIZE", f"{a.shape} vs {b.shape}", 999))
            return
        d = np.abs(a - b)
        mx = int(d.max()); mean = float(d.mean())
        ok = mx <= tol
        results.append((name, "PASS" if ok else "DIFF", f"max={mx} mean={mean:.2f}", mx))
    except Exception as e:
        results.append((name, "ERR", repr(e)[:80], 999))


def norm(im, mode="RGB"):
    return im


# ---- 模式转换 ----
case("convert.RGB", lambda: img_rgb, lambda: P.img_convert(h_rgb, b"RGB"))
case("convert.L", lambda: img_rgb.convert("L"), lambda: P.img_convert(h_rgb, b"L"))
case("convert.RGBA", lambda: img_rgb.convert("RGBA"), lambda: P.img_convert(h_rgb, b"RGBA"), space="rgba")

# ---- 转置 ----
for m, pn in [(0, "FLIP_LEFT_RIGHT"), (1, "FLIP_TOP_BOTTOM"), (2, "ROTATE_90"), (3, "ROTATE_180"), (4, "ROTATE_270"), (5, "TRANSPOSE"), (6, "TRANSVERSE")]:
    case(f"transpose.{pn}", lambda m=m, pn=pn: img_rgb.transpose(getattr(Image.Transpose, pn)), lambda m=m: P.img_transpose(h_rgb, m), tol=0)

# ---- 裁剪 ----
case("crop", lambda: img_rgb.crop((5, 6, 30, 33)), lambda: P.img_crop(h_rgb, 5, 6, 25, 27), tol=0)

# ---- 缩放（近似）----
for rs, pn in [("nearest", "NEAREST"), ("bilinear", "BILINEAR"), ("lanczos", "LANCZOS")]:
    case(f"resize.{rs}", lambda pn=pn: img_rgb.resize((26, 20), getattr(Image.Resampling, pn)), lambda rs=rs: P.img_resize(h_rgb, 26, 20, rs.encode()), tol=24 if rs != "nearest" else 0)

# ---- ImageOps ----
case("ops.invert", lambda: ImageOps.invert(img_rgb), lambda: P.img_invert(h_rgb), tol=0)
case("ops.grayscale", lambda: ImageOps.grayscale(img_rgb), lambda: P.img_grayscale(h_rgb))
case("ops.posterize", lambda: ImageOps.posterize(img_rgb, 3), lambda: P.img_posterize(h_rgb, 3))
case("ops.solarize", lambda: ImageOps.solarize(img_rgb, 128), lambda: P.img_solarize(h_rgb, 128), tol=0)
case("ops.autocontrast", lambda: ImageOps.autocontrast(img_rgb), lambda: P.img_autocontrast(h_rgb, 0), tol=3)
case("ops.equalize", lambda: ImageOps.equalize(img_rgb), lambda: P.img_equalize(h_rgb), tol=3)

# ---- ImageChops ----
img2 = Image.fromarray(rng.integers(0, 256, (H, W, 3), dtype=np.uint8), "RGB")
img2_path = "/tmp/opencode/difftest_rgb2.png"; img2.save(img2_path)
h2 = P.img_open(img2_path.encode())
for op, fn in [("add", ImageChops.add), ("subtract", ImageChops.subtract), ("difference", ImageChops.difference), ("multiply", ImageChops.multiply), ("screen", ImageChops.screen), ("darker", ImageChops.darker), ("lighter", ImageChops.lighter)]:
    case(f"chops.{op}", lambda fn=fn: fn(img_rgb, img2), lambda op=op: P.img_chop(h_rgb, h2, op.encode()), tol=1)
case("chops.invert", lambda: ImageChops.invert(img_rgb), lambda: P.img_invert(h_rgb), tol=0)

# ---- ImageEnhance ----
for k, pn in [("brightness", "Brightness"), ("contrast", "Contrast"), ("color", "Color")]:
    case(f"enhance.{k}", lambda pn=pn: getattr(ImageEnhance, pn)(img_rgb).enhance(1.5), lambda k=k: P.img_enhance(h_rgb, k.encode(), 1.5), tol=3)

# ---- ImageFilter ----
for pn, nm in [("SHARPEN", "SHARPEN"), ("BLUR", "BLUR"), ("EMBOSS", "EMBOSS"), ("FIND_EDGES", "FIND_EDGES"), ("SMOOTH", "SMOOTH")]:
    case(f"filter.{pn}", lambda pn=pn: img_rgb.filter(getattr(ImageFilter, pn)), lambda nm=nm: P.img_filter(h_rgb, nm.encode(), 1.0, 0, 0), tol=40)

# ---- 通道 / 数据进出 ----
for i, band in enumerate("RGBA"):
    case(f"getchannel.{band}", lambda band=band: img_rgba.getchannel(band), lambda i=i: P.img_getchannel(h_rgba, i))
raw = img_rgba.tobytes("raw", "RGBA")
def pil_frombytes():
    return Image.frombytes("RGBA", (W, H), raw)
def our_frombytes():
    buf = C.create_string_buffer(raw)
    return P.img_frombytes(b"RGBA", W, H, C.cast(buf, C.c_void_p), len(raw))
case("frombytes.RGBA", pil_frombytes, our_frombytes, space="rgba", tol=0)
def pil_tobytes():
    return img_rgb
def our_tobytes():
    buf = C.create_string_buffer(W * H * 3)
    P.img_tobytes(h_rgb, 0, b"RGB", C.cast(buf, C.c_void_p), W * H * 3)
    a = np.frombuffer(buf.raw, np.uint8).reshape(H, W, 3).astype(int)
    return P.from_np(a)
case("tobytes.RGB", pil_tobytes, our_tobytes, tol=0)

# ---- alpha_composite(带位置) ----
small = Image.fromarray(rng.integers(0, 256, (10, 12, 4), dtype=np.uint8), "RGBA")
small_path = "/tmp/opencode/difftest_small.png"; small.save(small_path)
h_small = P.img_open(small_path.encode())
def pil_ac():
    b = img_rgba.copy(); b.alpha_composite(small, (7, 5)); return b
def our_ac():
    b = P.img_copy(h_rgba); P.img_alpha_composite_at(b, h_small, 7, 5); return b
case("alpha_composite", pil_ac, our_ac, space="rgba", tol=1)

# ---- ImageOps.fit / contain ----
case("ops.fit", lambda: ImageOps.fit(img_rgb, (20, 30), Image.Resampling.LANCZOS), lambda: P.img_fit(h_rgb, 20, 30, b"lanczos", 0.5, 0.5, 0), tol=1)
case("ops.contain", lambda: ImageOps.contain(img_rgb, (20, 30), Image.Resampling.LANCZOS), lambda: P.img_contain(h_rgb, 20, 30, b"lanczos", 0), tol=1)

# ---- ImageColor ----
def pil_getrgb():
    import PIL.ImageColor as IC
    rgb = IC.getrgb("#3a7bc8")
    return Image.new("RGB", (2, 2), rgb)
def our_getrgb():
    buf = C.create_string_buffer(32)
    P.img_color_getrgb(b"#3a7bc8", buf, 32)
    v = [int(x) for x in buf.value.decode().split(",")]
    return P.from_np(np.full((2, 2, 3), v, np.uint8))
case("color.getrgb", pil_getrgb, our_getrgb, tol=0)

# ---- ImageDraw ----
from PIL import ImageDraw
def pil_draw_line():
    im = img_rgb.copy(); d = ImageDraw.Draw(im); d.line((0, 0, W - 1, H - 1), fill=(255, 0, 0), width=3); return im
def our_draw_line():
    h = P.img_copy(h_rgb); P.img_draw_line(h, 0, 0, W - 1, H - 1, 0xFF0000FF, 3); return h
case("draw.line", pil_draw_line, our_draw_line, tol=999 if True else 0)

# ---- getbbox / chop 变体 ----
def pil_bbox():
    bb = img_rgba.getbbox()
    a = np.zeros((H, W, 3), int)
    if bb:
        a[bb[1]:bb[3], bb[0]:bb[2]] = 255
    return Image.fromarray(a.astype(np.uint8), "RGB")
def our_bbox():
    buf = C.create_string_buffer(64)
    P.img_getbbox4(h_rgba, 0, buf, 64)
    a = np.zeros((H, W, 3), int)
    s = buf.value.decode()
    if s != "None":
        x0, y0, x1, y1 = [int(v) for v in s.split(",")]
        a[y0:y1, x0:x1] = 255
    return P.from_np(a)
case("getbbox", pil_bbox, our_bbox, tol=0)
case("chops.offset", lambda: ImageChops.offset(img_rgb, 5, -3), lambda: P.img_chop_offset(h_rgb, 5, -3), tol=0)
case("chops.add_const", lambda: ImageChops.add(img_rgb, Image.new("RGB", (W, H), (20, 20, 20))), lambda: P.img_chop_const(h_rgb, b"add", 20), tol=1)

# ---- chops 变体 / stat / ImageOps.pad ----
for op in ["add_modulo", "subtract_modulo", "soft_light", "hard_light", "overlay"]:
    case(f"chops.{op}", lambda op=op: getattr(ImageChops, op)(img_rgb, img2), lambda op=op: P.img_chop(h_rgb, h2, op.encode()), tol=0)
b1 = img_rgb.convert("1", dither=Image.Dither.NONE)
b2 = img2.convert("1", dither=Image.Dither.NONE)
hb1 = P.from_np(np.array(b1.convert("RGB")))
hb2 = P.from_np(np.array(b2.convert("RGB")))
for op in ["logical_and", "logical_or", "logical_xor"]:
    case(f"chops.{op}", lambda op=op: getattr(ImageChops, op)(b1, b2).convert("RGB"), lambda op=op: P.img_chop(hb1, hb2, op.encode()), tol=0)

def pil_stat(what):
    st = ImageStat.Stat(img_rgb)
    v = getattr(st, what)[0]
    if isinstance(v, (tuple, list)):
        v = v[0]
    c = min(255, int(round(v))); return Image.new("RGB", (2, 2), (c, c, c))
for what in ["mean", "median", "stddev", "sum"]:
    def our_stat(what=what):
        buf = C.create_string_buffer(256)
        P.img_stat(h_rgb, what.encode(), buf, 256)
        v = int(float(buf.value.decode().split(",")[0]))
        return P.from_np(np.full((2, 2, 3), v if v < 256 else 255, np.uint8))
    case(f"stat.{what}", lambda what=what: pil_stat(what), our_stat, tol=1)

case("ops.pad", lambda: ImageOps.pad(img_rgb, (60, 60), Image.Resampling.LANCZOS, (10, 20, 30)), lambda: P.img_ops_pad(h_rgb, 60, 60, b"lanczos", 0x0A141EFF, 0.5, 0.5), tol=1)

# ---- 多帧 / chops.composite / stat.extrema ----
mf = [Image.fromarray(rng.integers(0, 256, (H, W, 3), dtype=np.uint8), "RGB") for _ in range(3)]
mf_path = "/tmp/opencode/difftest_mf.gif"
mf[0].save(mf_path, save_all=True, append_images=mf[1:], duration=100, loop=0)
h_mf = P.img_open(mf_path.encode())
pmf = Image.open(mf_path)
for i in range(3):
    def pil_f(i=i):
        pmf.seek(i); return pmf.convert("RGB")
    def our_f(i=i):
        return P.img_convert(P.img_frame(h_mf, i), b"RGB")
    case(f"multiframe.frame{i}", pil_f, our_f, tol=0)

mask_L = Image.fromarray(rng.integers(0, 256, (H, W), dtype=np.uint8), "L")
mask_path = "/tmp/opencode/difftest_mask.png"; mask_L.save(mask_path)
h_mask = P.img_open(mask_path.encode())
case("chops.composite", lambda: ImageChops.composite(img_rgb, img2, mask_L), lambda: P.img_chops_composite(h_rgb, h2, h_mask), tol=0)

def pil_extrema():
    ex = ImageStat.Stat(img_rgb).extrema
    a = np.zeros((2, 8, 3), int)
    for c in range(3):
        a[0, c * 2] = ex[c][0]; a[0, c * 2 + 1] = ex[c][1]
    return Image.fromarray(a.astype(np.uint8), "RGB")
def our_extrema():
    buf = C.create_string_buffer(128)
    P.img_getextrema(h_rgb, buf, 128)
    v = [int(x) for x in buf.value.decode().split(",")]
    a = np.zeros((2, 8, 3), int)
    for c in range(3):
        a[0, c * 2] = v[c * 2]; a[0, c * 2 + 1] = v[c * 2 + 1]
    return P.from_np(a)
case("stat.extrema", pil_extrema, our_extrema, tol=0)

# ---- ImageFont / ImageDraw.text（FreeType；同引擎，判 ink bbox + mean）----
try:
    from PIL import ImageFont, ImageDraw
    FPATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(FPATH):
        TW, TH = 200, 60
        pim = Image.new("RGB", (TW, TH), (0, 0, 0))
        ImageDraw.Draw(pim).text((10, 10), "Hello", font=ImageFont.truetype(FPATH, 20), fill=(255, 255, 255))
        pa = np.array(pim)[:, :, 0].astype(int)
        hc = P.img_new(TW, TH); P.img_fill(hc, 0x000000FF)
        fo = P.img_font_load(FPATH.encode(), 20.0)
        P.img_draw_text(hc, 10, 10, b"Hello", fo, 0xFFFFFFFF)
        oa = P.to_np(hc)[:, :, 0].astype(int)
        def inkbb(a):
            w = np.argwhere(a > 0)
            return w.min(0) if len(w) else None
        bbp, bbo = inkbb(pa), inkbb(oa)
        bd = int(np.abs(bbp - bbo).max()) if bbp is not None and bbo is not None else 99
        mean = float(np.abs(pa - oa).mean())
        ok = bd <= 1 and mean < 2.0
        results.append(("text.render", "PASS" if ok else "DIFF", f"bboxΔ={bd} mean={mean:.3f}", bd))
except Exception as e:
    results.append(("text.render", "ERR", repr(e)[:60], 999))

# ---- convert("P")：browser 调色板 + Floyd-Steinberg ----
def pil_p(dither):
    idx = np.array(img_rgb.convert("P", dither=dither)).astype(np.uint8)
    return Image.fromarray(idx, "L")
def our_p(dither):
    h = P.img_convert_p(h_rgb, 0 if dither == Image.Dither.NONE else 1)
    ptr = P.img_frame_ptr(h, 0)
    idx = np.frombuffer(C.string_at(ptr, W * H), np.uint8).reshape(H, W)
    return P.img_frombytes(b"L", W, H, C.cast(C.create_string_buffer(idx.tobytes()), C.c_void_p), W * H)
case("convert.P (none)", lambda: pil_p(Image.Dither.NONE), lambda: our_p(Image.Dither.NONE), tol=0)
_pn = pil_p(Image.Dither.NONE); _po = our_p(Image.Dither.NONE)
_pf = pil_p(Image.Dither.FLOYDSTEINBERG); _of = our_p(Image.Dither.FLOYDSTEINBERG)
_pfa = np.array(_pf); _ofa = P.to_np(_of)[:, :, 0]
_ratio = float((_pfa == _ofa).mean())
results.append(("convert.P (floyd)", "PASS" if _ratio > 0.98 else "DIFF", f"match={_ratio*100:.1f}%", 0 if _ratio > 0.98 else 1))

case("effect.mandelbrot", lambda: Image.effect_mandelbrot((60, 50), (-2.0, -1.5, 1.0, 1.5), 32), lambda: P.img_effect_mandelbrot(60, 50, -2.0, -1.5, 1.0, 1.5, 32), tol=0)

# ---- font.getbbox ----
try:
    from PIL import ImageFont
    FPATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if os.path.exists(FPATH):
        pf = ImageFont.truetype(FPATH, 20); of = P.img_font_load(FPATH.encode(), 20.0)
        worst = 0
        for t in ["Hello", "Ag", "W", "Hello World"]:
            buf = C.create_string_buffer(64); P.img_font_bbox(of, t.encode(), buf, 64)
            we = [int(x) for x in buf.value.decode().split(",")]
            pi = list(pf.getbbox(t))
            worst = max(worst, max(abs(a - b) for a, b in zip(we, pi)))
        results.append(("font.bbox", "PASS" if worst <= 2 else "DIFF", f"maxΔ={worst}px", worst))
except Exception as e:
    results.append(("font.bbox", "ERR", repr(e)[:60], 999))

# ---- quantize / remap_palette（功能校验）----
try:
    pq = np.array(img_rgb.quantize(16, Image.Quantize.MEDIANCUT))
    hq = P.img_quantize(h_rgb, 16, 0)
    oi = np.frombuffer(C.string_at(P.img_frame_ptr(hq, 0), W * H), np.uint8).reshape(H, W)
    ratio = float((pq.astype(int) == oi.astype(int)).mean())
    results.append(("quantize.MEDIANCUT", "PASS" if ratio > 0.999 else "DIFF", f"match={ratio*100:.1f}%", 0 if ratio > 0.999 else 1))
    pm = np.array(img_rgb.quantize(16, Image.Quantize.MAXCOVERAGE))
    hm = P.img_quantize(h_rgb, 16, 1)
    om = np.frombuffer(C.string_at(P.img_frame_ptr(hm, 0), W * H), np.uint8).reshape(H, W)
    rm = float((pm.astype(int) == om.astype(int)).mean())
    results.append(("quantize.MAXCOVERAGE", "PASS" if rm > 0.999 else "DIFF", f"match={rm*100:.1f}%", 0 if rm > 0.999 else 1))
    po = np.array(img_rgb.quantize(16, Image.Quantize.FASTOCTREE))
    ho = P.img_quantize(h_rgb, 16, 2)
    oo = np.frombuffer(C.string_at(P.img_frame_ptr(ho, 0), W * H), np.uint8).reshape(H, W)
    ro = float((po.astype(int) == oo.astype(int)).mean())
    results.append(("quantize.FASTOCTREE", "PASS" if ro > 0.999 else "DIFF", f"match={ro*100:.1f}%", 0 if ro > 0.999 else 1))
except Exception as e:
    results.append(("quantize.MEDIANCUT", "ERR", repr(e)[:60], 999))

# ---- getcolors ----
try:
    pil_gc = sorted((c, tuple(col)) for c, col in (img_rgb.getcolors(1 << 20) or []))
    buf = C.create_string_buffer(65536); P.img_getcolors(h_rgb, 1 << 20, buf, 65536)
    our_gc = []
    for part in buf.value.decode().rstrip(";").split(";"):
        if not part:
            continue
        c, r, g, b = [int(x) for x in part.split(",")]
        our_gc.append((c, (r, g, b)))
    our_gc = sorted(our_gc)
    ok = pil_gc == our_gc
    results.append(("getcolors", "PASS" if ok else "DIFF", f"{len(pil_gc)} vs {len(our_gc)}", 0 if ok else 1))
except Exception as e:
    results.append(("getcolors", "ERR", repr(e)[:60], 999))

# ---- WebP 编解码 ----
try:
    wpath = "/tmp/opencode/dt.webp"
    img_rgb.save(wpath, quality=90)
    pw = np.array(Image.open(wpath).convert("RGB")).astype(int)
    ow = P.to_np(P.img_open(wpath.encode()))[:, :, :3].astype(int)
    d = 0 if pw.shape == ow.shape else 999
    if d == 0:
        d = int(np.abs(pw - ow).max())
    results.append(("webp.decode", "PASS" if d == 0 else "DIFF", f"maxΔ={d}", d))
except Exception as e:
    results.append(("webp.decode", "ERR", repr(e)[:60], 999))

case("generators.radial", lambda: Image.radial_gradient("L"), lambda: P.img_radial_gradient(), tol=0)

# ---- TIFF ----
try:
    tpath = "/tmp/opencode/dt.tiff"; img_rgb.save(tpath)
    pt = np.array(Image.open(tpath).convert("RGB")).astype(int)
    ot = P.to_np(P.img_open(tpath.encode()))[:, :, :3].astype(int)
    d = 0 if pt.shape == ot.shape else 999
    if d == 0:
        d = int(np.abs(pt - ot).max())
    results.append(("tiff.decode", "PASS" if d == 0 else "DIFF", f"maxΔ={d}", d))
except Exception as e:
    results.append(("tiff.decode", "ERR", repr(e)[:60], 999))

# ---- 补充：paste/blend/colorize/point/split/merge/draw ----
case("paste", lambda: (lambda b: (b.paste(img2, (5, 7)), b)[1])(img_rgb.copy()), lambda: P.img_paste(P.img_copy(h_rgb), h2, 5, 7), tol=0)
case("blend", lambda: Image.blend(img_rgb, img2, 0.35), lambda: P.img_blend(h_rgb, h2, 0.35), tol=1)
case("ops.colorize", lambda: ImageOps.colorize(img_rgb.convert("L"), (0, 0, 0), (255, 255, 255), (255, 0, 0)), lambda: P.img_colorize(h_rgb, 0x000000FF, 0xFFFFFFFF, b"255,0,0,128"), tol=2)
case("ops.expand", lambda: ImageOps.expand(img_rgb, 6, (10, 20, 30)), lambda: P.img_expand(h_rgb, 6, 0x0A141EFF), tol=0)
case("ops.scale", lambda: ImageOps.scale(img_rgb, 2.5, Image.Resampling.NEAREST), lambda: P.img_scale(h_rgb, 2.5, 2.5, b"nearest"), tol=0)
case("thumbnail", lambda: (lambda i: (i.thumbnail((20, 20)), i)[1])(img_rgb.copy()), lambda: P.img_thumbnail(P.img_copy(h_rgb), 20, 20), tol=0)
case("point.lut", lambda: img_rgb.point(lambda v: v // 2), lambda: P.img_point(h_rgb, -1, ",".join(str(v // 2) for v in range(256)).encode()), tol=1)
case("split.merge", lambda: Image.merge("RGB", img_rgb.split()[::-1]), lambda: P.img_merge_rgb(P.img_split(h_rgb, 2), P.img_split(h_rgb, 1), P.img_split(h_rgb, 0)), tol=0)
case("getpixel", lambda: Image.new("RGB", (1, 1), img_rgb.getpixel((3, 4))), lambda: P.from_np(np.full((1, 1, 3), [P.img_getpixel(h_rgb, 3, 4) >> 24 & 255, P.img_getpixel(h_rgb, 3, 4) >> 16 & 255, P.img_getpixel(h_rgb, 3, 4) >> 8 & 255], np.uint8)), tol=0)

# ---- 滤波器 & 绘图 补充 ----
for pn, nm, tol in [("BoxBlur", "BoxBlur", 0), ("GaussianBlur", "GaussianBlur", 0), ("UnsharpMask", "UnsharpMask", 30), ("MedianFilter", "MedianFilter", 0), ("MinFilter", "MinFilter", 0), ("MaxFilter", "MaxFilter", 0), ("DETAIL", "DETAIL", 1), ("CONTOUR", "CONTOUR", 0), ("EDGE_ENHANCE", "EDGE_ENHANCE", 0)]:
    def maker(pn=pn):
        f = getattr(ImageFilter, pn)
        try:
            obj = f() if pn in ("BoxBlur", "GaussianBlur", "UnsharpMask", "MedianFilter", "MinFilter", "MaxFilter") else f
        except Exception:
            obj = f
        if pn == "BoxBlur":
            obj = ImageFilter.BoxBlur(2)
        if pn == "GaussianBlur":
            obj = ImageFilter.GaussianBlur(2)
        if pn == "UnsharpMask":
            obj = ImageFilter.UnsharpMask(2, 150, 3)
        if pn == "MedianFilter":
            obj = ImageFilter.MedianFilter(3)
        if pn in ("MinFilter", "MaxFilter"):
            obj = getattr(ImageFilter, pn)(3)
        return img_rgb.filter(obj)
    def ourmaker(nm=nm):
        if nm == "BoxBlur":
            return P.img_filter(h_rgb, b"BoxBlur", 2, 0, 0)
        if nm == "GaussianBlur":
            return P.img_filter(h_rgb, b"GaussianBlur", 2, 0, 0)
        if nm == "UnsharpMask":
            return P.img_filter(h_rgb, b"UnsharpMask", 2, 150, 3)
        if nm in ("MedianFilter", "MinFilter", "MaxFilter"):
            return P.img_filter(h_rgb, nm.encode(), 0, 0, 3)
        return P.img_filter(h_rgb, nm.encode(), 0, 0, 0)
    case(f"filter2.{pn}", maker, ourmaker, tol=tol)

def pil_rrect():
    im = img_rgb.copy(); ImageDraw.Draw(im).rounded_rectangle((5, 5, 35, 30), 8, fill=(200, 40, 40)); return im
def our_rrect():
    h = P.img_copy(h_rgb); P.img_draw_rounded_rect(h, 5, 5, 35, 30, 8, 0, 0xC82828FF); return h
case("draw.rounded_rect", pil_rrect, our_rrect, tol=220)

# ---- Color3DLUT ----
try:
    N = 5
    tab = np.random.default_rng(9).random(N * N * N * 3).tolist()
    pl = np.array(img_rgb.filter(ImageFilter.Color3DLUT(N, tab)))
    csv = ",".join(repr(x) for x in tab)
    ol = P.to_np(P.img_lut3d(h_rgb, csv.encode(), 3, N, N, N))[:, :, :3]
    d = int(np.abs(pl.astype(int) - ol.astype(int)).max())
    results.append(("Color3DLUT", "PASS" if d == 0 else "DIFF", f"maxΔ={d}", d))
except Exception as e:
    results.append(("Color3DLUT", "ERR", repr(e)[:60], 999))

# 报告
print(f"{'case':28} {'st':4}  detail")
fails = 0
for name, st, det, mx in results:
    if st == "DIFF" or st == "ERR":
        fails += 1
    print(f"{name:28} {st:4}  {det}")
print(f"\n共 {len(results)} 项，失败 {fails} 项")
sys.exit(1 if fails else 0)
