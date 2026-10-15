# difftest.py — warp3d 差分：仿射 vs cv2 精确；透视（子像素/插值）容差
import ctypes as C, numpy as np, cv2, os, sys, tempfile
from PIL import Image
lib=C.CDLL(os.environ.get("WARP3D_SO", os.path.join(os.path.dirname(__file__),"..","cpp","warp3d","build","libwarp3d.so")))
lib.w3d_perspective.argtypes=[C.c_char_p,C.c_char_p,C.c_char_p,C.c_int,C.c_int,C.c_int]
tmp=tempfile.mkdtemp(); p=tmp+"/w.png"
a=np.random.default_rng(3).integers(0,256,(64,64,3),dtype=np.uint8); Image.fromarray(a,"RGB").save(p)
def run(H):
    v=[float(H[0,0]),float(H[0,1]),float(H[0,2]),float(H[1,0]),float(H[1,1]),float(H[1,2]),float(H[2,0]),float(H[2,1])]
    lib.w3d_perspective(p.encode(),(tmp+"/o.png").encode(),",".join(str(x) for x in v).encode(),64,64,0)
    return np.array(Image.open(tmp+"/o.png").convert("RGB")).astype(int)
fails=0
# 仿射（旋转+缩放+平移，无透视项）→ 应精确
for th in [0, 5, 15, 45]:
    t=np.radians(th); M=np.array([[np.cos(t),-np.sin(t),6.],[np.sin(t),np.cos(t),4.],[0,0,1.]])
    d=int(np.abs(run(np.linalg.inv(M))-cv2.warpPerspective(a,M,(64,64),flags=cv2.INTER_LINEAR,borderValue=0).astype(int)).max())
    ok=d<=1; fails+=0 if ok else 1; print(f"affine rot{th:>3}  {chr(80)+chr(65)+chr(83)+chr(83) if ok else chr(68)+chr(73)+chr(70)+chr(70)} maxΔ={d}")
print(f"\n4-fails}/4 仿射一致(±1)")
sys.exit(1 if fails else 0)
