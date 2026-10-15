# difftest.py — cvops 差分：OpenCV(cv2) vs 我们（灰度形态学/阈值/梯度）
import ctypes as C, numpy as np, cv2, os, sys, tempfile
from PIL import Image
lib = C.CDLL(os.environ.get("CVOPS_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "cvops", "build", "libcvops.so")))
for fn in ["cvo_erode","cvo_dilate","cvo_open","cvo_close"]: getattr(lib,fn).argtypes=[C.c_char_p,C.c_char_p,C.c_int]
lib.cvo_threshold_otsu.argtypes=[C.c_char_p,C.c_char_p,C.c_int]
lib.cvo_sobel.argtypes=[C.c_char_p,C.c_char_p,C.c_int,C.c_int]
tmp=tempfile.mkdtemp(); g=os.path.join(tmp,"g.png")
a=np.random.default_rng(5).integers(0,256,(48,64),dtype=np.uint8); Image.fromarray(a,"L").save(g)
def our(fn,out,*args): getattr(lib,fn)(g.encode(),out.encode(),*args); return np.array(Image.open(out))
fails=0
def chk(name,x,y):
    global fails; d=int(np.abs(x.astype(int)-y.astype(int)).max()); ok=d==0; fails+=0 if ok else 1; print(f"{name:12}{'PASS' if ok else 'DIFF'} maxΔ={d}")
k=3; ker=np.ones((k,k),np.uint8)
chk("erode", our("cvo_erode",tmp+"/e.png",k), cv2.erode(a,ker,borderType=cv2.BORDER_REPLICATE))
chk("dilate", our("cvo_dilate",tmp+"/d.png",k), cv2.dilate(a,ker,borderType=cv2.BORDER_REPLICATE))
chk("open", our("cvo_open",tmp+"/o.png",k), cv2.morphologyEx(a,cv2.MORPH_OPEN,ker,borderType=cv2.BORDER_REPLICATE))
chk("close", our("cvo_close",tmp+"/c.png",k), cv2.morphologyEx(a,cv2.MORPH_CLOSE,ker,borderType=cv2.BORDER_REPLICATE))
_,t=cv2.threshold(a,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU); chk("otsu", our("cvo_threshold_otsu",tmp+"/t.png",0), t)
gx=cv2.Sobel(a,cv2.CV_32F,1,0,ksize=3,borderType=cv2.BORDER_REPLICATE); chk("sobel", our("cvo_sobel",tmp+"/s.png",1,0), np.clip(np.abs(gx),0,255).astype(np.uint8))
print(f"\n{6-fails}/6 通过"); sys.exit(1 if fails else 0)
