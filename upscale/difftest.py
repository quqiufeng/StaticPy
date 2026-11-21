# difftest.py — Scale2x 差分：独立 Python 实现 vs libupscale
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

import ctypes as C, numpy as np, os, sys, tempfile
from PIL import Image
lib=C.CDLL(os.environ.get("UPSCALE_SO", os.path.join(os.path.dirname(__file__),"..","cpp","upscale","build","libupscale.so")))
lib.up_scale2x.argtypes=[C.c_char_p,C.c_char_p]
def py_scale2x(a):
    h,w,_=a.shape; o=np.zeros((h*2,w*2,4),np.uint8)
    def P(x,y): return a[min(max(y,0),h-1), min(max(x,0),w-1)]
    for y in range(h):
        for x in range(w):
            p=P(x,y);A=P(x,y-1);B=P(x+1,y);Cc=P(x-1,y);D=P(x,y+1)
            o[2*y,2*x]=A if (np.array_equal(Cc,A) and not np.array_equal(Cc,D) and not np.array_equal(A,B)) else p
            o[2*y,2*x+1]=B if (np.array_equal(A,B) and not np.array_equal(A,Cc) and not np.array_equal(B,D)) else p
            o[2*y+1,2*x]=Cc if (np.array_equal(D,Cc) and not np.array_equal(D,B) and not np.array_equal(Cc,A)) else p
            o[2*y+1,2*x+1]=D if (np.array_equal(B,D) and not np.array_equal(B,A) and not np.array_equal(D,Cc)) else p
    return o
tmp=tempfile.mkdtemp(); fails=0; N=20
for t in range(N):
    a=np.random.default_rng(t).integers(0,4,(6,7,4),dtype=np.uint8)*80
    Image.fromarray(a,"RGBA").save(tmp+"/s.png")
    lib.up_scale2x((tmp+"/s.png").encode(),(tmp+"/o.png").encode())
    o=np.array(Image.open(tmp+"/o.png").convert("RGBA"))
    if not np.array_equal(o,py_scale2x(a)): fails+=1
print(f"{N-fails}/{N} 与独立 Scale2x 实现一致")
sys.exit(1 if fails else 0)
