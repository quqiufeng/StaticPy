# difftest.py — atlas 打包校验：不变量（在界内 / 无重叠 / 全打进去）
import ctypes as C, os, sys, json, random
lib = C.CDLL(os.environ.get("ATLAS_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "atlas", "build", "libatlas.so")))
lib.atlas_pack_json.restype = C.c_char_p; lib.atlas_pack_json.argtypes = [C.c_char_p, C.c_int, C.c_int]

def overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

random.seed(11); fails = 0; trials = 60
for t in range(trials):
    sw, sh = 256, 256
    n = random.randint(4, 30)
    sizes = [(random.randint(8, 64), random.randint(8, 64)) for _ in range(n)]
    csv = ";".join(f"{w},{h}" for w, h in sizes)
    r = json.loads(lib.atlas_pack_json(csv.encode(), sw, sh).decode())
    pl = r["placements"]
    ok = True
    for (x, y, w, h) in pl:
        if x < 0 or y < 0 or x + w > sw or y + h > sh: ok = False
    for i in range(len(pl)):
        for j in range(i + 1, len(pl)):
            if overlap(pl[i], pl[j]): ok = False
    # 若总面积小于 sheet 且单块都放得下，期望全打进去
    area = sum(w * h for w, h in sizes)
    if area <= sw * sh * 0.75 and all(w <= sw and h <= sh for w, h in sizes):
        if r["packed"] != r["total"]: ok = False
    if not ok:
        fails += 1; print(f"FAIL t={t} packed={r['packed']}/{r['total']} area={area}")
print(f"\n{trials-fails}/{trials} 通过（在界内 + 无重叠 + 全打包）")
sys.exit(1 if fails else 0)
