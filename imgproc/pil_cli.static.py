from pil_lib import (img_open, img_save, img_free, img_copy, img_convert, img_convert_p, img_resize, img_scale, img_thumbnail, img_crop, img_rotate, img_transpose, img_mirror, img_pad, img_fit, img_contain, img_ops_pad, img_invert, img_grayscale, img_posterize, img_solarize, img_autocontrast, img_equalize, img_expand, img_chop_const, img_chop_offset, img_enhance, img_filter, img_quantize, img_split, img_effect_mandelbrot, img_draw_line, img_draw_rectangle, img_draw_ellipse)
from pil_lib import a, ai

def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 3:
        print("usage: pil <op> IN OUT [args...]")
        exit_program(1)
    op: str = a(args, "1")
    im = img_open(a(args, "2"))
    if im is None:
        print("open failed: " + a(args, "2"))
        exit_program(1)
    n: int = py_list_length(args)
    out = im

    if op == "convert":
        out = img_convert(im, a(args, "4"))
    elif op == "convert_p":
        out = img_convert_p(im, 0)
    elif op == "resize":
        rs: str = "lanczos"
        if n > 6:
            rs = a(args, "6")
        out = img_resize(im, ai(args, "4"), ai(args, "5"), rs)
    elif op == "scale":
        out = img_scale(im, string_to_float(a(args, "4")), string_to_float(a(args, "5")), "lanczos")
    elif op == "thumbnail":
        out = img_thumbnail(im, ai(args, "4"), ai(args, "5"))
    elif op == "crop":
        out = img_crop(im, ai(args, "4"), ai(args, "5"), ai(args, "6"), ai(args, "7"))
    elif op == "rotate":
        out = img_rotate(im, string_to_float(a(args, "4")), 1, 0)
    elif op == "transpose":
        out = img_transpose(im, ai(args, "4"))
    elif op == "mirror":
        out = img_mirror(im)
    elif op == "pad":
        out = img_pad(im, ai(args, "4"), ai(args, "5"), ai(args, "6"), ai(args, "7"), ai(args, "8"))
    elif op == "fit":
        out = img_fit(im, ai(args, "4"), ai(args, "5"), "lanczos", 0.5, 0.5, 0)
    elif op == "contain":
        out = img_contain(im, ai(args, "4"), ai(args, "5"), "lanczos", 0)
    elif op == "ops_pad":
        out = img_ops_pad(im, ai(args, "4"), ai(args, "5"), "lanczos", ai(args, "6"), 0.5, 0.5)
    elif op == "invert":
        out = img_invert(im)
    elif op == "grayscale":
        out = img_grayscale(im)
    elif op == "posterize":
        out = img_posterize(im, ai(args, "4"))
    elif op == "solarize":
        out = img_solarize(im, ai(args, "4"))
    elif op == "autocontrast":
        out = img_autocontrast(im, 0)
    elif op == "equalize":
        out = img_equalize(im)
    elif op == "expand":
        out = img_expand(im, ai(args, "4"), ai(args, "5"))
    elif op == "chop_const":
        out = img_chop_const(im, a(args, "4"), ai(args, "5"))
    elif op == "chop_offset":
        out = img_chop_offset(im, ai(args, "4"), ai(args, "5"))
    elif op == "enhance":
        out = img_enhance(im, a(args, "4"), string_to_float(a(args, "5")))
    elif op == "filter":
        out = img_filter(im, a(args, "4"), 0.0, 0.0, 0)
    elif op == "gaussian":
        out = img_filter(im, "GaussianBlur", 2.0, 0.0, 0)
    elif op == "quantize":
        out = img_quantize(im, ai(args, "4"), 0)
    elif op == "split":
        out = img_split(im, ai(args, "4"))
    elif op == "mandelbrot":
        out = img_effect_mandelbrot(ai(args, "4"), ai(args, "5"), -2.0, -1.5, 1.0, 1.5, 32)
    elif op == "draw_line":
        out = img_copy(im)
        img_draw_line(out, ai(args, "4"), ai(args, "5"), ai(args, "6"), ai(args, "7"), ai(args, "8"), 1)
    elif op == "draw_rect":
        out = img_copy(im)
        img_draw_rectangle(out, ai(args, "4"), ai(args, "5"), ai(args, "6"), ai(args, "7"), ai(args, "8"), 1, 0)
    elif op == "draw_ellipse":
        out = img_copy(im)
        img_draw_ellipse(out, ai(args, "4"), ai(args, "5"), ai(args, "6"), ai(args, "7"), ai(args, "8"), 0)
    else:
        print("unknown op: " + op)
        exit_program(1)

    rc: int = img_save(out, a(args, "3"))
    if out != im:
        img_free(out)
    img_free(im)
    if rc != 0:
        print("save failed rc=" + string_of_int(rc))
        exit_program(1)
    print(op + ": " + a(args, "2") + " -> " + a(args, "3"))
