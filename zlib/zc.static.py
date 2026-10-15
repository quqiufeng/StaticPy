# zc.static.py — StaticPy 版 zlib：压缩/解压/校验和
# 用法: zc <compress|gzip|decompress> IN OUT [level]
#       zc <crc32|adler32> FILE
extern fn zl_compress(a: str, b: str, level: int) -> int from "zlib"
extern fn zl_gzip(a: str, b: str, level: int) -> int from "zlib"
extern fn zl_decompress(a: str, b: str) -> int from "zlib"
extern fn zl_crc32(path: str) -> int from "zlib"
extern fn zl_adler32(path: str) -> int from "zlib"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 3:
        print("usage: zc <compress|gzip|decompress> IN OUT [level] | zc <crc32|adler32> FILE")
        exit_program(1)
    op: str = py_list_ref(args, 1)
    a: str = py_list_ref(args, 2)
    if op == "crc32":
        print(string_of_int(zl_crc32(a)))
    elif op == "adler32":
        print(string_of_int(zl_adler32(a)))
    elif n >= 4:
        b: str = py_list_ref(args, 3)
        level: int = 6
        if n >= 5:
            level = string_to_int(py_list_ref(args, 4))
        rc: int = 0
        if op == "compress":
            rc = zl_compress(a, b, level)
        elif op == "gzip":
            rc = zl_gzip(a, b, level)
        elif op == "decompress":
            rc = zl_decompress(a, b)
        else:
            print("unknown op: " + op)
            exit_program(1)
        if rc != 0:
            print("failed rc=" + string_of_int(rc))
            exit_program(1)
        print(op + ": " + a + " -> " + b)
    else:
        print("missing OUT")
        exit_program(1)
