# w3d.static.py — 2D 图像的 3D 旋转 / 透视变换
# 用法: w3d rotate IN OUT YAW PITCH ROLL [DIST] [F] [OUTW] [OUTH]
#       w3d persp  IN OUT H8_CSV OUTW OUTH [BG]
extern fn w3d_rotate(a: str, b: str, yaw: float, pitch: float, roll: float, dist: float, f: float, ow: int, oh: int, bg: int) -> int from "warp3d"
extern fn w3d_perspective(a: str, b: str, h: str, ow: int, oh: int, bg: int) -> int from "warp3d"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 3:
        print("usage: w3d rotate IN OUT YAW PITCH ROLL [DIST F OUTW OUTH] | w3d persp IN OUT H8 OUTW OUTH [BG]")
        exit_program(1)
    op: str = py_list_ref(args, 1); inp: str = py_list_ref(args, 2); out: str = py_list_ref(args, 3)
    rc: int = 0
    if op == "rotate":
        yaw: float = string_to_float(py_list_ref(args, 4)); pitch: float = string_to_float(py_list_ref(args, 5)); roll: float = string_to_float(py_list_ref(args, 6))
        dist: float = 800.0; f: float = 800.0; ow: int = 256; oh: int = 256
        if n >= 7: dist = string_to_float(py_list_ref(args, 7))
        if n >= 8: f = string_to_float(py_list_ref(args, 8))
        if n >= 9: ow = string_to_int(py_list_ref(args, 9))
        if n >= 10: oh = string_to_int(py_list_ref(args, 10))
        rc = w3d_rotate(inp, out, yaw, pitch, roll, dist, f, ow, oh, 0)
    elif op == "persp":
        ow: int = string_to_int(py_list_ref(args, 5)); oh: int = string_to_int(py_list_ref(args, 6))
        bg: int = 0
        if n >= 8: bg = string_to_int(py_list_ref(args, 7))
        rc = w3d_perspective(inp, out, py_list_ref(args, 4), ow, oh, bg)
    else:
        print("unknown op: " + op); exit_program(1)
    if rc != 0:
        print("failed rc=" + string_of_int(rc)); exit_program(1)
    print(op + ": " + inp + " -> " + out)
