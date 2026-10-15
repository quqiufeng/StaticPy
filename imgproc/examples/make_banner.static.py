# 示例：把 pil_lib 当库用（不是 CLI）——打开→转灰度→缩放→加白边→画红线→保存
from pil_lib import img_open, img_save, img_free, img_grayscale, img_resize, img_pad, img_copy, img_draw_line

def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 3:
        print("usage: make_banner IN OUT")
        exit_program(1)
    fin: str = py_list_ref(args, 1)
    fout: str = py_list_ref(args, 2)
    im = img_open(fin)
    g = img_grayscale(im)
    r = img_resize(g, 120, 90, "lanczos")
    p = img_pad(r, 8, 8, 8, 8, 0xFFFFFFFF)
    out = img_copy(p)
    img_draw_line(out, 8, 8, 128, 98, 0xFF0000FF, 2)
    img_save(out, fout)
    img_free(im); img_free(g); img_free(r); img_free(p); img_free(out)
    print("make_banner: " + fin + " -> " + fout)
