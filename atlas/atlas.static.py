# atlas.static.py — StaticPy 版精灵图集打包
# 用法: atlas SIZEFILE W H     （SIZEFILE: 每行 "w,h"，或分号分隔；输出布局 JSON）
extern fn atlas_pack_json(sizes: str, sw: int, sh: int) -> str from "atlas"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 4:
        print("usage: atlas SIZEFILE W H")
        exit_program(1)
    fp = file_open(py_list_ref(args, 1), "r")
    s: str = file_read_all(fp)
    file_close(fp)
    # 归一化：换行 -> 分号，逗号保留
    s = str_replace(s, "\n", ";")
    print(atlas_pack_json(s, string_to_int(py_list_ref(args, 2)), string_to_int(py_list_ref(args, 3))))
