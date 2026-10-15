# cv.static.py — StaticPy 版经典图像处理（形态学/阈值/梯度）
# 用法: cv <erode|dilate|open|close> IN OUT K
#       cv otsu IN OUT [inv]
#       cv sobel IN OUT DX DY
extern fn cvo_erode(a: str, b: str, k: int) -> int from "cvops"
extern fn cvo_dilate(a: str, b: str, k: int) -> int from "cvops"
extern fn cvo_open(a: str, b: str, k: int) -> int from "cvops"
extern fn cvo_close(a: str, b: str, k: int) -> int from "cvops"
extern fn cvo_threshold_otsu(a: str, b: str, inv: int) -> int from "cvops"
extern fn cvo_sobel(a: str, b: str, dx: int, dy: int) -> int from "cvops"
extern fn cvo_bilateral(a: str, b: str, d: int, sc: float, ss: float) -> int from "cvops"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 4:
        print("usage: cv <erode|dilate|open|close|otsu|sobel> IN OUT [args]")
        exit_program(1)
    op: str = py_list_ref(args, 1)
    inp: str = py_list_ref(args, 2)
    out: str = py_list_ref(args, 3)
    rc: int = 0
    if op == "erode":
        rc = cvo_erode(inp, out, string_to_int(py_list_ref(args, 4)))
    elif op == "dilate":
        rc = cvo_dilate(inp, out, string_to_int(py_list_ref(args, 4)))
    elif op == "open":
        rc = cvo_open(inp, out, string_to_int(py_list_ref(args, 4)))
    elif op == "close":
        rc = cvo_close(inp, out, string_to_int(py_list_ref(args, 4)))
    elif op == "otsu":
        inv: int = 0
        if n >= 5:
            inv = string_to_int(py_list_ref(args, 4))
        rc = cvo_threshold_otsu(inp, out, inv)
    elif op == "bilateral":
        d: int = 9; sc: float = 75.0; ss: float = 75.0
        if n >= 5: d = string_to_int(py_list_ref(args, 4))
        if n >= 6: sc = string_to_float(py_list_ref(args, 5))
        if n >= 7: ss = string_to_float(py_list_ref(args, 6))
        rc = cvo_bilateral(inp, out, d, sc, ss)
    elif op == "sobel":
        rc = cvo_sobel(inp, out, string_to_int(py_list_ref(args, 4)), string_to_int(py_list_ref(args, 5)))
    else:
        print("unknown op: " + op)
        exit_program(1)
    if rc != 0:
        print("failed rc=" + string_of_int(rc))
        exit_program(1)
    print(op + ": " + inp + " -> " + out)
