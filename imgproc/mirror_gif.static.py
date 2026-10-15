# mirror_gif.static.py — 把 GIF 逐帧水平镜像（PIL-free）
#
# 用法: mirror_gif IN.gif OUT.gif
#
# 编解码在运行时加载的 C++ 底层库 libimgproc.so（内部动态链接 libgif.so.7）；
# 镜像 = img_transpose(im, 0)：对 GIF 保留「索引 + 调色板」帧做转置，无损。

extern fn img_open(path: str) -> ptr from "imgproc"
extern fn img_transpose(im: ptr, method: int) -> ptr from "imgproc"
extern fn img_save(im: ptr, path: str) -> int from "imgproc"
extern fn img_free(im: ptr) -> int from "imgproc"


def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 3:
        print("usage: mirror_gif IN.gif OUT.gif")
        exit_program(1)
    fin: str = py_list_ref(args, 1)
    fout: str = py_list_ref(args, 2)

    im = img_open(fin)
    if im is None:
        print("imgproc: cannot open " + fin)
        exit_program(1)

    out = img_transpose(im, 0)
    rc: int = img_save(out, fout)
    img_free(im)
    img_free(out)
    if rc != 0:
        print("imgproc: save failed rc=" + string_of_int(rc))
        exit_program(1)
    print("mirrored " + fin + " -> " + fout)
