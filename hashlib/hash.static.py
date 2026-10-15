# hash.static.py — StaticPy 版 hashlib：算文件摘要
# 用法: hash [ALGO] FILE   （默认 sha256；无参数时列出可用算法）
extern fn hl_file_hex(algo: str, path: str) -> str from "hashlib"
extern fn hl_algos() -> str from "hashlib"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 2:
        print("usage: hash [ALGO] FILE")
        print("algos: " + hl_algos())
        exit_program(1)
    if n >= 3:
        algo: str = py_list_ref(args, 1)
        path: str = py_list_ref(args, 2)
    else:
        algo: str = "sha256"
        path: str = py_list_ref(args, 1)
    print(hl_file_hex(algo, path))
