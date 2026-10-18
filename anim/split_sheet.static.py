# split_sheet.static.py — 把「多姿势精灵表」按列等分切成帧（StaticPy，编成 ELF）
#
# 用法:
#   split_sheet OUTDIR COLS SHEET.png
#     把 SHEET 按水平方向等分 COLS 列，输出 f00.png … fNN.png

def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 4:
        print("usage: split_sheet OUTDIR COLS SHEET.png")
        exit_program(1)
    outdir: str = py_list_ref(args, 1)
    cols: int = string_to_int(py_list_ref(args, 2))
    src: str = py_list_ref(args, 3)
    os_mkdir(outdir)
    im = img_open(src)
    if im is None:
        print("imgproc: cannot open " + src)
        exit_program(1)
    w: int = img_width(im)
    h: int = img_height(im)
    cw: int = int(w / cols)
    i: int = 0
    while i < cols:
        c = img_crop(im, i * cw, 0, cw, h)
        if i < 10:
            nm: str = "f0" + string_of_int(i) + ".png"
        else:
            nm: str = "f" + string_of_int(i) + ".png"
        img_save(c, outdir + "/" + nm)
        img_free(c)
        i = i + 1
    img_free(im)
    print("split " + string_of_int(cols) + " -> " + outdir)
