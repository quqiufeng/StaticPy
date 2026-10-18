# pack_sprites.static.py — 透明帧序列 → 精灵表(PNG) + manifest(JSON)
#
# 用法:
#   pack_sprites OUT.png MANIFEST.json CROP_W CROP_H SRC_X SRC_Y CELL_W CELL_H COLS FLIP NAME f1.png f2.png ...
#     CROP/SRC: 从每张输入图里先裁 (SRC_X,SRC_Y,CROP_W,CROP_H) 再做统一画布（固定裁切即可对齐）
#     CELL_W/H : 每个精灵格尺寸；COLS: 每行列数；FLIP=1 → 每帧水平镜像（出“朝右”）
#     NAME     : 动画名（写进 manifest）
#
# 仅补 pil_lib 未声明的 extern（其余复用 pil_lib，构建时 concat）

extern fn img_new(w: int, h: int) -> ptr from "imgproc"
extern fn img_fill(im: ptr, rgba: int) -> int from "imgproc"


def ceil_div(a: int, b: int) -> int:
    q: int = 0
    t: int = a
    while t > 0:
        t = t - b
        q = q + 1
    return q


def put_json_str(fp, key: str, val: str, comma: int) -> int:
    s: str = "  \"" + key + "\": \"" + val + "\""
    if comma == 1:
        s = s + ","
    s = s + "\n"
    file_write(fp, s)
    return 0


def put_json_int(fp, key: str, val: int, comma: int) -> int:
    s: str = "  \"" + key + "\": " + string_of_int(val)
    if comma == 1:
        s = s + ","
    s = s + "\n"
    file_write(fp, s)
    return 0


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 13:
        print("usage: pack_sprites OUT.png MANIFEST.json CROP_W CROP_H SRC_X SRC_Y CELL_W CELL_H COLS FLIP NAME f1.png ...")
        exit_program(1)
    out_png: str = py_list_ref(args, 1)
    out_json: str = py_list_ref(args, 2)
    cw: int = string_to_int(py_list_ref(args, 3))
    ch: int = string_to_int(py_list_ref(args, 4))
    sx: int = string_to_int(py_list_ref(args, 5))
    sy: int = string_to_int(py_list_ref(args, 6))
    cellw: int = string_to_int(py_list_ref(args, 7))
    cellh: int = string_to_int(py_list_ref(args, 8))
    cols: int = string_to_int(py_list_ref(args, 9))
    flip: int = string_to_int(py_list_ref(args, 10))
    name: str = py_list_ref(args, 11)
    nframes: int = n - 12
    rows: int = ceil_div(nframes, cols)

    sheet = img_new(cols * cellw, rows * cellh)
    if sheet is None:
        print("imgproc: img_new failed")
        exit_program(1)
    img_fill(sheet, 0)

    i: int = 0
    while i < nframes:
        fn: str = py_list_ref(args, 12 + i)
        im = img_open(fn)
        if im is not None:
            cr = img_crop(im, sx, sy, cw, ch)
            rz = img_resize(cr, cellw, cellh, "lanczos")
            row: int = 0
            col: int = i
            while col >= cols:
                col = col - cols
                row = row + 1
            if flip == 1:
                m = img_transpose(rz, 0)
                img_alpha_composite_at(sheet, m, col * cellw, row * cellh)
                img_free(m)
                img_free(rz)
            else:
                img_alpha_composite_at(sheet, rz, col * cellw, row * cellh)
                img_free(rz)
            img_free(cr)
            img_free(im)
        i = i + 1

    rc: int = img_save(sheet, out_png)
    img_free(sheet)
    if rc != 0:
        print("imgproc: save sheet failed")
        exit_program(1)

    fp = file_open(out_json, "w")
    if fp is not None:
        file_write(fp, "{\n")
        put_json_str(fp, "name", name, 1)
        put_json_str(fp, "image", out_png, 1)
        put_json_int(fp, "frameWidth", cellw, 1)
        put_json_int(fp, "frameHeight", cellh, 1)
        put_json_int(fp, "columns", cols, 1)
        put_json_int(fp, "rows", rows, 1)
        put_json_int(fp, "frameCount", nframes, 1)
        anim: str = "  \"animations\": { \"" + name + "\": { \"from\": 0, \"to\": " + string_of_int(nframes - 1) + ", \"fps\": 8, \"loop\": true } }\n"
        file_write(fp, anim)
        file_write(fp, "}\n")
        file_close(fp)

    print("packed " + string_of_int(nframes) + " frames (" + string_of_int(cols) + "x" + string_of_int(rows) + ") -> " + out_png)
