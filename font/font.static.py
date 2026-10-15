# font.static.py — TTF → 字形图集 PNG + 度量 JSON（游戏位图字体）
# 用法: font TTF PX CHARSET OUT.png [OUT.json] [ATLAS_W]
extern fn font_atlas(ttf: str, px: int, charset: str, out_png: str, out_json: str, aw: int) -> int from "font"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 5:
        print("usage: font TTF PX CHARSET OUT.png [OUT.json] [ATLAS_W]")
        exit_program(1)
    json_path: str = py_list_ref(args, 4) + ".json"
    if n >= 6:
        json_path = py_list_ref(args, 5)
    aw: int = 512
    if n >= 7:
        aw = string_to_int(py_list_ref(args, 6))
    rc: int = font_atlas(py_list_ref(args, 1), string_to_int(py_list_ref(args, 2)), py_list_ref(args, 3),
                         py_list_ref(args, 4), json_path, aw)
    if rc != 0:
        print("font_atlas failed rc=" + string_of_int(rc))
        exit_program(1)
    print("atlas: " + py_list_ref(args, 4) + "  metrics: " + json_path)
