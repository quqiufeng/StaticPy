# ease.static.py — StaticPy 版缓动曲线
# 用法: ease NAME T            单点求值
#       ease NAME              采样 0..1（21 点）打印曲线
extern fn ease(name: str, t: double) -> double from "easing"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 2:
        print("usage: ease NAME [T]")
        exit_program(1)
    name: str = py_list_ref(args, 1)
    if n >= 3:
        print(format_float(ease(name, string_to_float(py_list_ref(args, 2))), 6))
    else:
        i: int = 0
        while i <= 20:
            print(format_float(ease(name, i / 20.0), 6))
            i = i + 1
