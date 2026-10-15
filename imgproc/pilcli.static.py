# pilcli.static.py — StaticPy 版图像处理 CLI（对标 Pillow 的常用操作）
#
# 用法: pilcli <op> IN OUT [args...]
#   convert   IN OUT MODE
#   resize    IN OUT W H [nearest|bilinear|bicubic|lanczos]
#   crop      IN OUT X Y W H
#   transpose IN OUT N            # 0 FLIP_LR 1 FLIP_TB 2 ROT90 3 ROT180 4 ROT270 5 TRANSPOSE 6 TRANSVERSE
#   rotate    IN OUT DEG [expand]
#   invert|grayscale|posterize(bits)|solarize(thr)|autocontrast|mirror  IN OUT [...]
#   filter    IN OUT NAME
#   pad       IN OUT L T R B RGBA
#
# 编解码/几何/颜色等底层能力来自运行时加载的 libimgproc.so。

extern fn img_open(path: str) -> ptr from "imgproc"
extern fn img_save(im: ptr, path: str) -> int from "imgproc"
extern fn img_free(im: ptr) -> int from "imgproc"
extern fn img_convert(im: ptr, mode: str) -> ptr from "imgproc"
extern fn img_resize(im: ptr, w: int, h: int, rs: str) -> ptr from "imgproc"
extern fn img_crop(im: ptr, x: int, y: int, w: int, h: int) -> ptr from "imgproc"
extern fn img_transpose(im: ptr, m: int) -> ptr from "imgproc"
extern fn img_mirror(im: ptr) -> ptr from "imgproc"
extern fn img_rotate(im: ptr, deg: float, expand: int, fill_rgba: int) -> ptr from "imgproc"
extern fn img_invert(im: ptr) -> ptr from "imgproc"
extern fn img_grayscale(im: ptr) -> ptr from "imgproc"
extern fn img_posterize(im: ptr, bits: int) -> ptr from "imgproc"
extern fn img_solarize(im: ptr, thr: int) -> ptr from "imgproc"
extern fn img_autocontrast(im: ptr, cutoff: int) -> ptr from "imgproc"
extern fn img_filter(im: ptr, name: str, r1: float, r2: float, i1: int) -> ptr from "imgproc"
extern fn img_pad(im: ptr, l: int, t: int, r: int, b: int, rgba: int) -> ptr from "imgproc"


def arg(args, i: str) -> str:
    return py_list_ref(args, string_to_int(i))


def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 3:
        print("usage: pilcli <op> IN OUT [args...]")
        exit_program(1)
    op: str = arg(args, "1")
    fin: str = arg(args, "2")
    fout: str = arg(args, "3")
    im = img_open(fin)
    if im is None:
        print("open failed: " + fin)
        exit_program(1)

    out = im
    if op == "convert":
        out = img_convert(im, arg(args, "4"))
    elif op == "resize":
        rs: str = "lanczos"
        if py_list_length(args) > 6:
            rs = arg(args, "6")
        out = img_resize(im, string_to_int(arg(args, "4")), string_to_int(arg(args, "5")), rs)
    elif op == "crop":
        out = img_crop(im, string_to_int(arg(args, "4")), string_to_int(arg(args, "5")), string_to_int(arg(args, "6")), string_to_int(arg(args, "7")))
    elif op == "transpose":
        out = img_transpose(im, string_to_int(arg(args, "4")))
    elif op == "mirror":
        out = img_mirror(im)
    elif op == "rotate":
        ex: int = 0
        if py_list_length(args) > 5:
            ex = string_to_int(arg(args, "5"))
        out = img_rotate(im, string_to_float(arg(args, "4")), ex, 0)
    elif op == "invert":
        out = img_invert(im)
    elif op == "grayscale":
        out = img_grayscale(im)
    elif op == "posterize":
        out = img_posterize(im, string_to_int(arg(args, "4")))
    elif op == "solarize":
        out = img_solarize(im, string_to_int(arg(args, "4")))
    elif op == "autocontrast":
        out = img_autocontrast(im, 0)
    elif op == "filter":
        out = img_filter(im, arg(args, "4"), 0.0, 0.0, 0)
    elif op == "pad":
        out = img_pad(im, string_to_int(arg(args, "4")), string_to_int(arg(args, "5")), string_to_int(arg(args, "6")), string_to_int(arg(args, "7")), string_to_int(arg(args, "8")))
    else:
        print("unknown op: " + op)
        exit_program(1)

    rc: int = img_save(out, fout)
    img_free(im)
    if out != im:
        img_free(out)
    if rc != 0:
        print("save failed rc=" + string_of_int(rc))
        exit_program(1)
    print(op + ": " + fin + " -> " + fout)
