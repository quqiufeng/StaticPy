# pose_walk.static.py — OpenPose(COCO-18) 走路骨架帧（StaticPy 版，编成 ELF）
#
# 用法: OUTDIR=dir [LEGX=1.0] [ARMX=1.0] [YUP=0] [HAND=1] pose_walk
#   OUTDIR: 输出目录（f00.png … f15.png + preview_contact/passing.png）
#   LEGX  : 步幅（腿横向压缩）；ARMX: 摆臂放大；YUP: 整体上移(底部留白)；HAND: 画 OpenPose 手 21 点
#
# 仅补 pil_lib 未声明的 extern

extern fn img_new(w: int, h: int) -> ptr from "imgproc"
extern fn img_fill(im: ptr, rgba: int) -> int from "imgproc"


W = 512
H = 768
CX = 256
PI = 3.141592653589793

LEGX = 1.0
ARMX = 1.0
YUP = 0
HAND = 1


def envf(name: str, dflt: str) -> float:
    v: str = os_getenv(name)
    if v == "":
        return string_to_float(dflt)
    return string_to_float(v)


def envi(name: str, dflt: str) -> int:
    v: str = os_getenv(name)
    if v == "":
        return string_to_int(dflt)
    return string_to_int(v)


def rint(x: float) -> int:
    return int(round(x))


def deg2rad(d: float) -> float:
    return d * PI / 180.0


def rcol(r: int, g: int, b: int) -> int:
    return r * 16777216 + g * 65536 + b * 256 + 255


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ---- 手 21 关键点（局部：前向 f, 侧向 s；单位=手长）----
HOFF_F = py_list(0.0, 0.16, 0.34, 0.52, 0.68, 0.26, 0.62, 0.90, 1.10, 0.22, 0.64, 0.94, 1.16, 0.22, 0.62, 0.90, 1.08, 0.20, 0.52, 0.74, 0.90)
HOFF_S = py_list(0.0, -0.34, -0.52, -0.60, -0.64, -0.20, -0.26, -0.26, -0.24, 0.0, 0.0, 0.0, 0.0, 0.20, 0.26, 0.28, 0.28, 0.40, 0.50, 0.56, 0.60)
HCOL = py_list(0xFF00FFFF, 0xFF00C8FF, 0xE600FFFF, 0xFF3CFFFF, 0xC800E6FF)
HEA = py_list(0, 1, 2, 3, 0, 5, 6, 7, 0, 9, 10, 11, 0, 13, 14, 15, 0, 17, 18, 19, 5, 9, 13)
HEB = py_list(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 9, 13, 17)


def finger(i: int) -> int:
    if i <= 4:
        return 0
    if i <= 8:
        return 1
    if i <= 12:
        return 2
    if i <= 16:
        return 3
    return 4


def draw_hand(im: ptr, ex: float, ey: float, wx: float, wy: float, length: float) -> int:
    dx: float = wx - ex
    dy: float = wy - ey
    ln: float = sqrt(dx * dx + dy * dy)
    if ln < 0.0001:
        ln = 1.0
    ux: float = dx / ln
    uy: float = dy / ln
    px: float = -uy
    py: float = ux
    XS = py_list()
    YS = py_list()
    k: int = 0
    while k < 21:
        f: float = py_list_ref(HOFF_F, k)
        s: float = py_list_ref(HOFF_S, k)
        XS = py_list_append(XS, wx + ux * f * length + px * s * length)
        YS = py_list_append(YS, wy + uy * f * length + py * s * length)
        k = k + 1
    # 连边（23 条：指纹 + 掌）
    e: int = 0
    while e < 23:
        a: int = py_list_ref(HEA, e)
        b: int = py_list_ref(HEB, e)
        xa: float = py_list_ref(XS, a)
        ya: float = py_list_ref(YS, a)
        xb: float = py_list_ref(XS, b)
        yb: float = py_list_ref(YS, b)
        img_draw_line(im, rint(xa), rint(ya), rint(xb), rint(yb), py_list_ref(HCOL, finger(b)), 2)
        e = e + 1
    j: int = 0
    while j < 21:
        px0: int = rint(py_list_ref(XS, j)) - 2
        py0: int = rint(py_list_ref(YS, j)) - 2
        img_draw_ellipse(im, px0, py0, px0 + 4, py0 + 4, 0, 0xFFFFFFFF)
        j = j + 1
    return 0


def leg(hipd: float, kneed: float, ankled: float, dx: float):
    hx: float = 256.0 + dx
    hx1: float = hx + LEGX * 140.0 * sin(deg2rad(hipd))
    hy1: float = 460.0 + 140.0 * cos(deg2rad(hipd))
    sd: float = hipd - kneed
    hx2: float = hx1 + LEGX * 140.0 * sin(deg2rad(sd))
    hy2: float = hy1 + 140.0 * cos(deg2rad(sd))
    fx: float = hx2 + LEGX * 26.0 * sin(deg2rad(sd + ankled))
    fy: float = hy2 + 15.0
    if fy > 738.0:
        fy = 738.0
    return py_list(hx, 460.0, hx1, hy1, hx2, hy2, fx, fy)


def arm(shod: float, elbd: float, dx: float):
    sx: float = 256.0 + dx
    sx1: float = sx + ARMX * 95.0 * sin(deg2rad(shod))
    sy1: float = 258.0 + 95.0 * cos(deg2rad(shod))
    fd: float = shod - elbd
    sx2: float = sx1 + ARMX * 95.0 * sin(deg2rad(fd))
    sy2: float = sy1 + 95.0 * cos(deg2rad(fd))
    return py_list(sx, 258.0, sx1, sy1, sx2, sy2)


def shift_up(im: ptr, dy: int) -> ptr:
    if dy <= 0:
        return im
    return img_pad(im, 0, 0, 0, dy, 255)


def save(im: ptr, path: str) -> int:
    rc: int = img_save(im, path)
    img_free(im)
    return rc


def kf0():
    return py_list(22.0, 8.0, 5.0, -22.0, 20.0, 12.0, -26.0, 38.0, 26.0, 42.0)


def kf1():
    return py_list(5.0, 5.0, 0.0, -5.0, 38.0, 16.0, -8.0, 34.0, 8.0, 44.0)


def kf2():
    return py_list(-22.0, 20.0, 12.0, 22.0, 8.0, 5.0, 26.0, 42.0, -26.0, 38.0)


def kf3():
    return py_list(-5.0, 38.0, 16.0, 5.0, 5.0, 0.0, 8.0, 44.0, -8.0, 34.0)


def blend(k0, k1, t: float):
    out = py_list()
    i: int = 0
    while i < 10:
        out = py_list_append(out, lerp(py_list_ref(k0, i), py_list_ref(k1, i), t))
        i = i + 1
    return out


def draw_dots(im: ptr, lst, cnt: int) -> int:
    k: int = 0
    while k < cnt:
        x0: int = rint(py_list_ref(lst, k * 2)) - 4
        y0: int = rint(py_list_ref(lst, k * 2 + 1)) - 4
        img_draw_ellipse(im, x0, y0, x0 + 8, y0 + 8, 0, 0xFFFFFFFF)
        k = k + 1
    return 0


def draw_frame(a) -> ptr:
    im = img_new(W, H)
    img_fill(im, 255)

    Lleg = leg(py_list_ref(a, 0), py_list_ref(a, 1), py_list_ref(a, 2), -10.0)
    Rleg = leg(py_list_ref(a, 3), py_list_ref(a, 4), py_list_ref(a, 5), 12.0)
    Larm = arm(py_list_ref(a, 6), py_list_ref(a, 7), -12.0)
    Rarm = arm(py_list_ref(a, 8), py_list_ref(a, 9), 14.0)

    # 主干
    img_draw_line(im, CX, 180, CX, 250, rcol(255, 0, 0), 6)
    # 右臂（近）
    img_draw_line(im, CX, 250, rint(py_list_ref(Rarm, 0)), rint(py_list_ref(Rarm, 1)), rcol(255, 85, 0), 6)
    img_draw_line(im, rint(py_list_ref(Rarm, 0)), rint(py_list_ref(Rarm, 1)), rint(py_list_ref(Rarm, 2)), rint(py_list_ref(Rarm, 3)), rcol(255, 170, 0), 6)
    img_draw_line(im, rint(py_list_ref(Rarm, 2)), rint(py_list_ref(Rarm, 3)), rint(py_list_ref(Rarm, 4)), rint(py_list_ref(Rarm, 5)), rcol(255, 255, 0), 6)
    # 左臂（远）
    img_draw_line(im, CX, 250, rint(py_list_ref(Larm, 0)), rint(py_list_ref(Larm, 1)), rcol(170, 255, 0), 6)
    img_draw_line(im, rint(py_list_ref(Larm, 0)), rint(py_list_ref(Larm, 1)), rint(py_list_ref(Larm, 2)), rint(py_list_ref(Larm, 3)), rcol(85, 255, 0), 6)
    img_draw_line(im, rint(py_list_ref(Larm, 2)), rint(py_list_ref(Larm, 3)), rint(py_list_ref(Larm, 4)), rint(py_list_ref(Larm, 5)), rcol(0, 255, 0), 6)
    # 右腿
    img_draw_line(im, CX, 250, rint(py_list_ref(Rleg, 0)), rint(py_list_ref(Rleg, 1)), rcol(0, 255, 85), 6)
    img_draw_line(im, rint(py_list_ref(Rleg, 0)), rint(py_list_ref(Rleg, 1)), rint(py_list_ref(Rleg, 2)), rint(py_list_ref(Rleg, 3)), rcol(0, 255, 170), 6)
    img_draw_line(im, rint(py_list_ref(Rleg, 2)), rint(py_list_ref(Rleg, 3)), rint(py_list_ref(Rleg, 4)), rint(py_list_ref(Rleg, 5)), rcol(0, 255, 255), 6)
    img_draw_line(im, rint(py_list_ref(Rleg, 4)), rint(py_list_ref(Rleg, 5)), rint(py_list_ref(Rleg, 6)), rint(py_list_ref(Rleg, 7)), rcol(0, 255, 255), 6)
    # 左腿
    img_draw_line(im, CX, 250, rint(py_list_ref(Lleg, 0)), rint(py_list_ref(Lleg, 1)), rcol(0, 170, 255), 6)
    img_draw_line(im, rint(py_list_ref(Lleg, 0)), rint(py_list_ref(Lleg, 1)), rint(py_list_ref(Lleg, 2)), rint(py_list_ref(Lleg, 3)), rcol(0, 85, 255), 6)
    img_draw_line(im, rint(py_list_ref(Lleg, 2)), rint(py_list_ref(Lleg, 3)), rint(py_list_ref(Lleg, 4)), rint(py_list_ref(Lleg, 5)), rcol(0, 0, 255), 6)
    img_draw_line(im, rint(py_list_ref(Lleg, 4)), rint(py_list_ref(Lleg, 5)), rint(py_list_ref(Lleg, 6)), rint(py_list_ref(Lleg, 7)), rcol(0, 0, 255), 6)

    # 关键点白点
    headp = py_list(256.0, 180.0, 256.0, 250.0, 264.0, 174.0, 248.0, 178.0)
    draw_dots(im, headp, 4)
    draw_dots(im, Rarm, 3)
    draw_dots(im, Larm, 3)
    draw_dots(im, Rleg, 3)
    draw_dots(im, Lleg, 3)

    if HAND == 1:
        draw_hand(im, py_list_ref(Rarm, 2), py_list_ref(Rarm, 3), py_list_ref(Rarm, 4), py_list_ref(Rarm, 5), 22.0)
        draw_hand(im, py_list_ref(Larm, 2), py_list_ref(Larm, 3), py_list_ref(Larm, 4), py_list_ref(Larm, 5), 22.0)
    return im


def fname(i: int) -> str:
    if i < 10:
        return "f0" + string_of_int(i) + ".png"
    return "f" + string_of_int(i) + ".png"


LEGX = envf("LEGX", "1.0")
ARMX = envf("ARMX", "1.0")
YUP = envi("YUP", "0")
HAND = envi("HAND", "1")


def main():
    outdir: str = os_getenv("OUTDIR")
    if outdir == "":
        outdir = "walk6"
    os_mkdir(outdir)
    k0 = kf0()
    k1 = kf1()
    k2 = kf2()
    k3 = kf3()
    N: int = 16
    i: int = 0
    while i < N:
        f: float = (float(i) * 4.0) / 16.0
        j: int = int(f)
        t: float = f - float(j)
        if j == 0:
            a = blend(k0, k1, t)
        elif j == 1:
            a = blend(k1, k2, t)
        elif j == 2:
            a = blend(k2, k3, t)
        else:
            a = blend(k3, k0, t)
        save(shift_up(draw_frame(a), YUP), outdir + "/" + fname(i))
        i = i + 1
    save(shift_up(draw_frame(k0), YUP), outdir + "/preview_contact.png")
    save(shift_up(draw_frame(k1), YUP), outdir + "/preview_passing.png")
    print("pose_walk: " + string_of_int(N) + " frames -> " + outdir)
