# difftest.py — 缓动差分：Python 独立实现 vs libeasing（同规范，双实现互验）
import ctypes as C, math, os, sys
lib = C.CDLL(os.environ.get("EASING_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "easing", "build", "libeasing.so")))
lib.ease.restype = C.c_double; lib.ease.argtypes = [C.c_char_p, C.c_double]
B = {
 "quad": lambda x: x*x, "cubic": lambda x: x**3,
 "sine": lambda x: 1-math.cos(x*math.pi/2),
 "expo": lambda x: 0 if x == 0 else 2**(10*x-10),
 "circ": lambda x: 1-math.sqrt(1-x*x),
 "back": lambda x: (1.70158+1)*x**3-1.70158*x*x,
 "elastic": lambda x: 0 if x == 0 else (1 if x == 1 else -2**(10*x-10)*math.sin((x*10-10.75)*(2*math.pi/3))),
 "bounce": lambda x: (7.5625*x*x if x < 1/2.75 else
                       (7.5625*(x-1.5/2.75)**2+0.75 if x < 2/2.75 else
                        (7.5625*(x-2.25/2.75)**2+0.9375 if x < 2.5/2.75 else 7.5625*(x-2.625/2.75)**2+0.984375))),
}
def ref(name, t):
    if name == "linear": return t
    kind = "inout" if name.startswith("easeInOut") else ("in" if name.startswith("easeIn") else "out")
    f = B[name[9:] if kind == "inout" else (name[6:] if kind == "in" else name[7:])]
    if kind == "in": return f(t)
    if kind == "out": return 1-f(1-t)
    return f(2*t)/2 if t < 0.5 else 1-f(2-2*t)/2
names = ["linear"] + [f"ease{io}{b}" for b in B for io in ["In","Out","InOut"]]
bad = tot = 0
for nm in names:
    for i in range(21):
        t = i/20; tot += 1
        if abs(lib.ease(nm.encode(), t) - ref(nm, t)) > 1e-9: bad += 1
print(f"{tot-bad}/{tot} 一致（{len(names)} 曲线 × 21 采样，双实现）")
sys.exit(1 if bad else 0)
