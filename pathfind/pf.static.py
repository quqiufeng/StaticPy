# pf.static.py — StaticPy 版网格 A* 寻路
# 用法: pf GRIDFILE W H SX SY EX EY [DIAG]   （GRIDFILE: w*h 个 0/1，逗号或空白分隔）
extern fn pf_find_json(grid: str, w: int, h: int, sx: int, sy: int, ex: int, ey: int, diag: int) -> str from "pathfind"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 8:
        print("usage: pf GRIDFILE W H SX SY EX EY [DIAG]")
        exit_program(1)
    fp = file_open(py_list_ref(args, 1), "r")
    grid: str = file_read_all(fp)
    file_close(fp)
    diag: int = 0
    if n >= 9:
        diag = string_to_int(py_list_ref(args, 8))
    print(pf_find_json(grid, string_to_int(py_list_ref(args, 2)), string_to_int(py_list_ref(args, 3)),
                       string_to_int(py_list_ref(args, 4)), string_to_int(py_list_ref(args, 5)),
                       string_to_int(py_list_ref(args, 6)), string_to_int(py_list_ref(args, 7)), diag))
