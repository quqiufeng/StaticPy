# difftest.py — hashlib 差分测试：Python hashlib vs libhashlib
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

import ctypes as C, hashlib, os, sys
lib = C.CDLL(os.environ.get("HASHLIB_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "hashlib", "build", "libhashlib.so")))
lib.hl_file_hex.restype = C.c_char_p; lib.hl_file_hex.argtypes = [C.c_char_p, C.c_char_p]
ALGOS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]
# 夹具：默认在 ~/iso_gen 造一份确定性二进制（仓库约定：临时文件不进 /tmp）。
# 覆盖全 256 字节值 + 非 4 的倍数长度（SHA 分块边界的经典坑）。
def _fixture():
    d = os.path.expanduser("~/iso_gen")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "hashlib_difftest_fixture.bin")
    want = bytes(range(256)) * 97 + bytes(range(37))
    if not os.path.exists(path) or open(path, "rb").read() != want:
        open(path, "wb").write(want)
    return path

p = sys.argv[1] if len(sys.argv) > 1 else _fixture()
data = open(p, "rb").read()
fails = 0
for a in ALGOS:
    py = hashlib.new(a, data).hexdigest()
    ours = lib.hl_file_hex(a.encode(), p.encode()).decode()
    ok = py == ours
    fails += 0 if ok else 1
    print(f"{a:8} {'PASS' if ok else 'DIFF'}  {ours[:16]}...")
print(f"\n{len(ALGOS)-fails}/{len(ALGOS)} 通过")
sys.exit(1 if fails else 0)
