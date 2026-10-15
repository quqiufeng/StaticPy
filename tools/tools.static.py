# tools.static.py — StaticPy 前端：人脸 / 背景去除(扣图) / OCR / 图像反推
# 用法:
#   tools detect  IN.png                        人脸检测（JSON）
#   tools crop    IN.png OUT.png [size]         检测最大脸→对齐裁剪
#   tools parse   IN.png OUT.png [color|face|skin|hair]   人脸解析（分割）
#   tools remove  IN.png OUT.png [mode] [color] 背景去除/扣图（mode0=透明RGBA）
#   tools ocr     IN.png                        文字识别（JSON）
#   tools caption IN.png [task] [beams]         图像反推（Florence-2 描述）
extern fn face_detect(path: str) -> str from "face"
extern fn face_crop(path: str, out: str, size: int) -> int from "face"
extern fn face_parse(path: str, out: str, mode: str) -> int from "face"
extern fn birefnet_remove(inp: str, outp: str, mask: str, mode: int, color: str) -> int from "birefnet"
extern fn ocr_image_json(path: str) -> str from "ocr"
extern fn florence2_caption(path: str, task: str, beams: int) -> str from "florence2"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 3:
        print("usage: tools <detect|crop|parse|remove|ocr|caption> IN [OUT|task] ...")
        exit_program(1)
    op: str = py_list_ref(args, 1)
    inp: str = py_list_ref(args, 2)
    if op == "detect":
        print(face_detect(inp))
    elif op == "crop":
        size: int = 512
        if n >= 5:
            size = string_to_int(py_list_ref(args, 4))
        rc: int = face_crop(inp, py_list_ref(args, 3), size)
        print("crop rc=" + string_of_int(rc))
    elif op == "parse":
        mode: str = "color"
        if n >= 5:
            mode = py_list_ref(args, 4)
        rc: int = face_parse(inp, py_list_ref(args, 3), mode)
        print("parse rc=" + string_of_int(rc))
    elif op == "remove":
        mode: int = 0
        color: str = ""
        if n >= 5:
            mode = string_to_int(py_list_ref(args, 4))
        rc: int = birefnet_remove(inp, py_list_ref(args, 3), "", mode, color)
        print("remove rc=" + string_of_int(rc))
    elif op == "ocr":
        print(ocr_image_json(inp))
    elif op == "caption":
        task: str = "<MORE_DETAILED_CAPTION>"
        beams: int = 3
        if n >= 4:
            task = py_list_ref(args, 3)
        if n >= 5:
            beams = string_to_int(py_list_ref(args, 4))
        print(florence2_caption(inp, task, beams))
    else:
        print("unknown op: " + op)
        exit_program(1)
