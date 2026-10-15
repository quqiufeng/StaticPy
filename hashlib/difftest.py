# difftest.py — hashlib 差分测试：Python hashlib vs libhashlib
import ctypes as C, hashlib, os, sys
lib = C.CDLL(os.environ.get("HASHLIB_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "hashlib", "build", "libhashlib.so")))
lib.hl_file_hex.restype = C.c_char_p; lib.hl_file_hex.argtypes = [C.c_char_p, C.c_char_p]
ALGOS = ["md5", "sha1", "sha224", "sha256", "sha384", "sha512"]
p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/pk.png"
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
