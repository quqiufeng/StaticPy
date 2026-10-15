# up.static.py — 像素画高清放大（Scale2x）
# 用法: up 2x IN OUT
extern fn up_scale2x(a: str, b: str) -> int from "upscale"


def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 4:
        print("usage: up 2x IN OUT"); exit_program(1)
    rc: int = up_scale2x(py_list_ref(args, 2), py_list_ref(args, 3))
    if rc != 0:
        print("failed rc=" + string_of_int(rc)); exit_program(1)
    print("up 2x: " + py_list_ref(args, 2) + " -> " + py_list_ref(args, 3))
