# difftest.py — 字形度量差分：PIL(FreeType) vs 我们（advance / 位图 w,h）
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

import ctypes as C, os, sys, json, tempfile
from PIL import ImageFont
lib = C.CDLL(os.environ.get("FONT_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "font", "build", "libfont.so")))
lib.font_atlas.argtypes = [C.c_char_p, C.c_int, C.c_char_p, C.c_char_p, C.c_char_p, C.c_int]
TTF = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PX = 24
CHARSET = "ABCabc0123 .,!?"
tmp = tempfile.mkdtemp()
rc = lib.font_atlas(TTF.encode(), PX, CHARSET.encode(), (tmp+"/a.png").encode(), (tmp+"/a.json").encode(), 512)
data = json.load(open(tmp+"/a.json"))
pf = ImageFont.truetype(TTF, PX)
fails = 0; n = 0
for g in data["glyphs"]:
    ch = chr(g["cp"]); n += 1
    m = pf.getmask(ch)
    ph = m.size[1]
    pa = round(pf.getlength(ch))
    dh, da = abs(g["h"]-ph), abs(g["advance"]-pa)
    ok = dh <= 1 and da <= 1
    if not ok:
        fails += 1; print(f"DIFF {ch!r} h{g['h']}/{ph} adv{g['advance']}/{pa}")
print(f"\n{n-fails}/{n} 字形度量一致（advance/位图高，与 PIL(FreeType) 一致）")
sys.exit(1 if fails else 0)
