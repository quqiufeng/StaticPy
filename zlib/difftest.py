# difftest.py — zlib 差分：Python zlib/gzip vs libzlib（逐字节）
import ctypes as C, zlib, gzip, os, sys, subprocess, tempfile
lib = C.CDLL(os.environ.get("ZLIB_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "zlib", "build", "libzlib.so")))
for fn, rt, at in [("zl_compress", C.c_int, [C.c_char_p, C.c_char_p, C.c_int]),
                   ("zl_gzip", C.c_int, [C.c_char_p, C.c_char_p, C.c_int]),
                   ("zl_decompress", C.c_int, [C.c_char_p, C.c_char_p]),
                   ("zl_crc32", C.c_ulong, [C.c_char_p]), ("zl_adler32", C.c_ulong, [C.c_char_p])]:
    f = getattr(lib, fn); f.restype = rt; f.argtypes = at
tmp = tempfile.mkdtemp()
inp = os.path.join(tmp, "in.bin")
data = (b"hello zlib "*1000) + os.urandom(5000)
open(inp, "wb").write(data)
fails = 0
def check(name, ok, extra=""):
    global fails
    print(f"{name:14} {'PASS' if ok else 'DIFF'}  {extra}")
    fails += 0 if ok else 1

# compress
cz = os.path.join(tmp, "c.z"); lib.zl_compress(inp.encode(), cz.encode(), 6)
check("compress", open(cz, "rb").read() == zlib.compress(data, 6))
# decompress（解 Python 产出的流）
pyz = os.path.join(tmp, "py.z"); open(pyz, "wb").write(zlib.compress(data, 6))
out = os.path.join(tmp, "out.bin"); lib.zl_decompress(pyz.encode(), out.encode())
check("decompress", open(out, "rb").read() == data)
# gzip
gz = os.path.join(tmp, "c.gz"); lib.zl_gzip(inp.encode(), gz.encode(), 6)
check("gzip", open(gz, "rb").read() == gzip.compress(data, 6, mtime=0))
# crc32 / adler32
check("crc32", lib.zl_crc32(inp.encode()) == (zlib.crc32(data) & 0xffffffff))
check("adler32", lib.zl_adler32(inp.encode()) == (zlib.adler32(data) & 0xffffffff))
print(f"\n{5-fails}/5 通过")
sys.exit(1 if fails else 0)
