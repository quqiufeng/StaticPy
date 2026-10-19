# cutout.static.py — 洪泛抠图：从四边填背景，保留 8 个角色（StaticPy + imgproc）
# usage: cutout IN.png OUTDIR SIZE_TH

extern fn img_new(w: int, h: int) -> ptr from "imgproc"
extern fn img_getpixel(im: ptr, x: int, y: int) -> int from "imgproc"
extern fn img_putpixel(im: ptr, x: int, y: int, rgba: int) -> int from "imgproc"
extern fn img_fill(im: ptr, rgba: int) -> int from "imgproc"


def is_bg(px: int) -> int:
    if px < 0:
        px = px + 4294967296
    r: int = int(px / 16777216) % 256
    g: int = int(px / 65536) % 256
    b: int = int(px / 256) % 256
    mn: int = r
    if g < mn:
        mn = g
    if b < mn:
        mn = b
    if mn >= 185 and b >= r - 12:
        return 1
    return 0


def push(stk, sp: int, v: int) -> int:
    img_putpixel(stk, sp, 0, v)
    return sp + 1


def main():
    args = list_to_py_list(argv())
    nf: int = py_list_length(args)
    if nf < 3:
        print("usage: cutout IN.png OUTDIR [SIZE_TH]")
        exit_program(1)
    src: str = py_list_ref(args, 1)
    outdir: str = py_list_ref(args, 2)
    th: int = 1500
    if nf > 3:
        th = string_to_int(py_list_ref(args, 3))
    os_mkdir(outdir)
    im = img_open(src)
    if im is None:
        print("cannot open " + src)
        exit_program(1)
    im = img_convert(im, "RGBA")
    w: int = img_width(im)
    h: int = img_height(im)
    n: int = w * h
    print("size " + string_of_int(w) + "x" + string_of_int(h))

    mask = img_new(w, h)
    img_fill(mask, 0)
    stk = img_new(n, 1)
    sp: int = 0

    x: int = 0
    while x < w:
        if is_bg(img_getpixel(im, x, 0)) == 1:
            img_putpixel(mask, x, 0, 1)
            sp = push(stk, sp, x)
        if is_bg(img_getpixel(im, x, h - 1)) == 1:
            img_putpixel(mask, x, h - 1, 1)
            sp = push(stk, sp, (h - 1) * w + x)
        x = x + 1
    y: int = 0
    while y < h:
        if is_bg(img_getpixel(im, 0, y)) == 1:
            img_putpixel(mask, 0, y, 1)
            sp = push(stk, sp, y * w)
        if is_bg(img_getpixel(im, w - 1, y)) == 1:
            img_putpixel(mask, w - 1, y, 1)
            sp = push(stk, sp, y * w + (w - 1))
        y = y + 1

    while sp > 0:
        sp = sp - 1
        p: int = img_getpixel(stk, sp, 0)
        px: int = p % w
        py: int = int(p / w)
        if px > 0:
            if (img_getpixel(mask, px - 1, py) % 256) == 0 and is_bg(img_getpixel(im, px - 1, py)) == 1:
                img_putpixel(mask, px - 1, py, 1)
                sp = push(stk, sp, p - 1)
        if px + 1 < w:
            if (img_getpixel(mask, px + 1, py) % 256) == 0 and is_bg(img_getpixel(im, px + 1, py)) == 1:
                img_putpixel(mask, px + 1, py, 1)
                sp = push(stk, sp, p + 1)
        if py > 0:
            if (img_getpixel(mask, px, py - 1) % 256) == 0 and is_bg(img_getpixel(im, px, py - 1)) == 1:
                img_putpixel(mask, px, py - 1, 1)
                sp = push(stk, sp, p - w)
        if py + 1 < h:
            if (img_getpixel(mask, px, py + 1) % 256) == 0 and is_bg(img_getpixel(im, px, py + 1)) == 1:
                img_putpixel(mask, px, py + 1, 1)
                sp = push(stk, sp, p + w)

    y = 0
    while y < h:
        x = 0
        while x < w:
            if (img_getpixel(mask, x, y) % 256) == 0 and is_bg(img_getpixel(im, x, y)) == 1:
                img_putpixel(mask, x, y, 2)
                sp = push(stk, 0, y * w + x)
                hcnt: int = 0
                while sp > 0:
                    sp = sp - 1
                    p: int = img_getpixel(stk, sp, 0)
                    qx: int = p % w
                    qy: int = int(p / w)
                    hcnt = hcnt + 1
                    if qx > 0:
                        if (img_getpixel(mask, qx - 1, qy) % 256) == 0 and is_bg(img_getpixel(im, qx - 1, qy)) == 1:
                            img_putpixel(mask, qx - 1, qy, 2)
                            sp = push(stk, sp, p - 1)
                    if qx + 1 < w:
                        if (img_getpixel(mask, qx + 1, qy) % 256) == 0 and is_bg(img_getpixel(im, qx + 1, qy)) == 1:
                            img_putpixel(mask, qx + 1, qy, 2)
                            sp = push(stk, sp, p + 1)
                    if qy > 0:
                        if (img_getpixel(mask, qx, qy - 1) % 256) == 0 and is_bg(img_getpixel(im, qx, qy - 1)) == 1:
                            img_putpixel(mask, qx, qy - 1, 2)
                            sp = push(stk, sp, p - w)
                    if qy + 1 < h:
                        if (img_getpixel(mask, qx, qy + 1) % 256) == 0 and is_bg(img_getpixel(im, qx, qy + 1)) == 1:
                            img_putpixel(mask, qx, qy + 1, 2)
                            sp = push(stk, sp, p + w)
                if hcnt < 300:
                    img_putpixel(mask, x, y, 0)
                    sp = push(stk, 0, y * w + x)
                    while sp > 0:
                        sp = sp - 1
                        p: int = img_getpixel(stk, sp, 0)
                        qx: int = p % w
                        qy: int = int(p / w)
                        if qx > 0:
                            if (img_getpixel(mask, qx - 1, qy) % 256) == 2:
                                img_putpixel(mask, qx - 1, qy, 0)
                                sp = push(stk, sp, p - 1)
                        if qx + 1 < w:
                            if (img_getpixel(mask, qx + 1, qy) % 256) == 2:
                                img_putpixel(mask, qx + 1, qy, 0)
                                sp = push(stk, sp, p + 1)
                        if qy > 0:
                            if (img_getpixel(mask, qx, qy - 1) % 256) == 2:
                                img_putpixel(mask, qx, qy - 1, 0)
                                sp = push(stk, sp, p - w)
                        if qy + 1 < h:
                            if (img_getpixel(mask, qx, qy + 1) % 256) == 2:
                                img_putpixel(mask, qx, qy + 1, 0)
                                sp = push(stk, sp, p + w)
            x = x + 1
        y = y + 1

    print("bg filled, fg label...")

    lab = img_new(w, h)
    img_fill(lab, 0)
    cap: int = 20000
    sizes = img_new(cap, 1)
    bx0 = img_new(cap, 1)
    bx1 = img_new(cap, 1)
    by0 = img_new(cap, 1)
    by1 = img_new(cap, 1)
    cid: int = 0

    y = 0
    while y < h:
        x = 0
        while x < w:
            if (img_getpixel(mask, x, y) % 256) == 0 and img_getpixel(lab, x, y) == 0:
                cid = cid + 1
                img_putpixel(lab, x, y, cid)
                sp = push(stk, 0, y * w + x)
                cnt: int = 0
                mnx: int = x
                mxx: int = x
                mny: int = y
                mxy: int = y
                while sp > 0:
                    sp = sp - 1
                    p: int = img_getpixel(stk, sp, 0)
                    qx: int = p % w
                    qy: int = int(p / w)
                    cnt = cnt + 1
                    if qx < mnx:
                        mnx = qx
                    if qx > mxx:
                        mxx = qx
                    if qy < mny:
                        mny = qy
                    if qy > mxy:
                        mxy = qy
                    if qx > 0:
                        if (img_getpixel(mask, qx - 1, qy) % 256) == 0 and img_getpixel(lab, qx - 1, qy) == 0:
                            img_putpixel(lab, qx - 1, qy, cid)
                            sp = push(stk, sp, p - 1)
                    if qx + 1 < w:
                        if (img_getpixel(mask, qx + 1, qy) % 256) == 0 and img_getpixel(lab, qx + 1, qy) == 0:
                            img_putpixel(lab, qx + 1, qy, cid)
                            sp = push(stk, sp, p + 1)
                    if qy > 0:
                        if (img_getpixel(mask, qx, qy - 1) % 256) == 0 and img_getpixel(lab, qx, qy - 1) == 0:
                            img_putpixel(lab, qx, qy - 1, cid)
                            sp = push(stk, sp, p - w)
                    if qy + 1 < h:
                        if (img_getpixel(mask, qx, qy + 1) % 256) == 0 and img_getpixel(lab, qx, qy + 1) == 0:
                            img_putpixel(lab, qx, qy + 1, cid)
                            sp = push(stk, sp, p + w)
                if cid < cap:
                    img_putpixel(sizes, cid, 0, cnt)
                    img_putpixel(bx0, cid, 0, mnx)
                    img_putpixel(bx1, cid, 0, mxx)
                    img_putpixel(by0, cid, 0, mny)
                    img_putpixel(by1, cid, 0, mxy)
            x = x + 1
        y = y + 1

    print("components=" + string_of_int(cid))

    out = img_new(w, h)
    img_fill(out, 0)
    y = 0
    while y < h:
        x = 0
        while x < w:
            c: int = img_getpixel(lab, x, y)
            keep: int = 0
            if c > 0 and c < cap:
                if img_getpixel(sizes, c, 0) >= th:
                    keep = 1
            if keep == 1:
                px: int = img_getpixel(im, x, y)
                img_putpixel(out, x, y, int(px / 256) * 256 + 255)
            x = x + 1
        y = y + 1
    img_save(out, outdir + "/aura_cut.png")

    kc = py_list()
    c = 1
    while c <= cid and c < cap:
        if img_getpixel(sizes, c, 0) >= th:
            kc = py_list_append(kc, c)
        c = c + 1
    print("kept=" + string_of_int(py_list_length(kc)))

    remaining = kc
    idx: int = 0
    while py_list_length(remaining) > 0:
        ln: int = py_list_length(remaining)
        mi: int = 0
        mv: int = img_getpixel(bx0, py_list_ref(remaining, 0), 0)
        k: int = 1
        while k < ln:
            v: int = img_getpixel(bx0, py_list_ref(remaining, k), 0)
            if v < mv:
                mv = v
                mi = k
            k = k + 1
        cc: int = py_list_ref(remaining, mi)
        nx0: int = img_getpixel(bx0, cc, 0) - 3
        ny0: int = img_getpixel(by0, cc, 0) - 3
        nx1: int = img_getpixel(bx1, cc, 0) + 4
        ny1: int = img_getpixel(by1, cc, 0) + 4
        if nx0 < 0:
            nx0 = 0
        if ny0 < 0:
            ny0 = 0
        if nx1 > w:
            nx1 = w
        if ny1 > h:
            ny1 = h
        cw2: int = nx1 - nx0
        ch2: int = ny1 - ny0
        ccimg = img_crop(out, nx0, ny0, cw2, ch2)
        yy: int = 0
        while yy < ch2:
            xx: int = 0
            while xx < cw2:
                if img_getpixel(lab, nx0 + xx, ny0 + yy) != cc:
                    img_putpixel(ccimg, xx, yy, 0)
                xx = xx + 1
            yy = yy + 1
        if idx < 10:
            nm: str = "f0" + string_of_int(idx) + ".png"
        else:
            nm: str = "f" + string_of_int(idx) + ".png"
        img_save(ccimg, outdir + "/" + nm)
        print(nm + " cid=" + string_of_int(cc) + " size=" + string_of_int(img_getpixel(sizes, cc, 0)))
        img_free(ccimg)
        rest = py_list()
        j: int = 0
        while j < ln:
            if j != mi:
                rest = py_list_append(rest, py_list_ref(remaining, j))
            j = j + 1
        remaining = rest
        idx = idx + 1

    print("done -> " + outdir)


main()
