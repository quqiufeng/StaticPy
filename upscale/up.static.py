# up.static.py — 图像放大：2x 像素画(Scale2x)，4x 照片/精灵(Real-ESRGAN)
# 用法: up 2x IN OUT      # Scale2x，硬边不糊（像素画）
#       up 4x IN OUT      # Real-ESRGAN x4 模型（/data/models/image/realesr-general-x4v3.onnx）
#       up esrgan IN OUT  # 同 4x
extern fn up_scale2x(a: str, b: str) -> int from "upscale"
extern fn sr_upscale(a: str, b: str) -> int from "sr"


def main():
    args = list_to_py_list(argv())
    if py_list_length(args) < 4:
        print("usage: up 2x|4x|esrgan IN OUT"); exit_program(1)
    mode: str = py_list_ref(args, 1)
    inp: str = py_list_ref(args, 2)
    outp: str = py_list_ref(args, 3)
    rc: int = 0
    if mode == "4x" or mode == "esrgan":
        rc = sr_upscale(inp, outp)
    elif mode == "2x":
        rc = up_scale2x(inp, outp)
    else:
        print("usage: up 2x|4x|esrgan IN OUT"); exit_program(1)
    if rc != 0:
        print("failed rc=" + string_of_int(rc)); exit_program(1)
    print("up " + mode + ": " + inp + " -> " + outp)
