# parse_dump.static.py — 解析器自检夹具：源文件 -> AST 规范 dump
# 与 staticpy/parse_diff.py（CPython ast 版）逐字节比对（见 check_parse.sh）

def dump_file(path: str) -> int:
    fp = file_open(path, "r")
    src: str = file_read_all(fp)
    file_close(fp)
    toks = tokenize(src)
    tree = parse_module(toks)
    print(show_node(tree))
    return 0

def main() -> int:
    args = argv()
    return dump_file(list_ref(args, 1))
