# emit_dump.static.py — 自举翻译器的自检夹具：源文件 -> Scheme IR
# 与 staticpy/static_translate.py（CPython ast 版）逐字节/规范化比对（check_translate.sh）
#
# 用法：emit_dump.static.py <src> [lib]
#       第二个参数给 "lib" 时按库模式输出（不生成 (static_main) 入口），
#       对应 static_translate.py --lib。

def emit_file(path: str, lib_mode: int) -> int:
    fp = file_open(path, "r")
    src: str = file_read_all(fp)
    file_close(fp)
    toks = tokenize(src)
    tree = parse_module(toks)
    print(emit_module(tree, path, lib_mode))
    return 0

def main() -> int:
    args = argv()
    lib_mode: int = 0
    if list_length(args) > 2 and list_ref(args, 2) == "lib":
        lib_mode = 1
    return emit_file(list_ref(args, 1), lib_mode)
