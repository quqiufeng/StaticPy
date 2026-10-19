# sheet_align.static.py — 透明精灵表按透明缝隙切 N 帧，按脚底对齐到统一画布
# usage: sheet_align IN.png OUTDIR COLS

extern fn img_new(w: int, h: int) -> ptr from "imgproc"
extern fn img_getpixel(im: ptr, x: int, y: int) -> int from "imgproc"
extern fn img_putpixel(im: ptr, x: int, y: int, rgba: int) -> int from "imgproc"
extern fn img_fill(im: ptr, rgba: int) -> int from "imgproc"


def main():
    args = list_to_py_list(argv())
    nf: int = py_list_length(args)
    if nf < 4:
        print("usage: sheet_align IN.png OUTDIR COLS")
        exit_program(1)
    src: str = py_list_ref(args, 1)
    outdir: str = py_list_ref(args, 2)
    cols: int = string_to_int(py_list_ref(args, 3))
    os_mkdir(outdir)
    im = img_open(src)
    if im is None:
        print("cannot open " + src)
        exit_program(1)
    im = img_convert(im, "RGBA")
    w: int = img_width(im)
    h: int = img_height(im)
    cw: int = int(w / cols)

    empty = img_new(w, 1)
    x: int = 0
    while x < w:
        e: int = 1
        y: int = 0
        while y < h:
            if img_getpixel(im, x, y) % 256 > 10:
                e = 0
                y = h
            else:
                y = y + 1
        img_putpixel(empty, x, 0, e)
        x = x + 1

    splits = py_list()
    run_start: int = -1
    x = 0
    while x < w:
        e: int = img_getpixel(empty, x, 0)
        if e == 1:
            if run_start < 0:
                run_start = x
        else:
            if run_start >= 0:
                if x - run_start >= 4:
                    splits = py_list_append(splits, int((run_start + x - 1) / 2))
                run_start = -1
        x = x + 1
    if run_start >= 0 and w - run_start >= 4:
        splits = py_list_append(splits, int((run_start + w - 1) / 2))

    nseg: int = py_list_length(splits) + 1
    print("segments=" + string_of_int(nseg))
    segs = py_list()
    if nseg == cols:
        prev: int = 0
        k: int = 0
        while k < py_list_length(splits):
            segs = py_list_append(segs, prev)
            segs = py_list_append(segs, py_list_ref(splits, k))
            prev = py_list_ref(splits, k)
            k = k + 1
        segs = py_list_append(segs, prev)
        segs = py_list_append(segs, w)
    else:
        print("gap mismatch -> equal content columns")
        nseg = cols
        gmnx: int = w
        gmxx: int = 0
        y: int = 0
        while y < h:
            x: int = 0
            while x < w:
                if img_getpixel(im, x, y) % 256 > 10:
                    if x < gmnx:
                        gmnx = x
                    if x > gmxx:
                        gmxx = x
                x = x + 1
            y = y + 1
        cw2: int = int((gmxx - gmnx + 1) / cols)
        k = 0
        while k < cols:
            segs = py_list_append(segs, gmnx + k * cw2)
            segs = py_list_append(segs, gmnx + (k + 1) * cw2)
            k = k + 1

    bx = img_new(nseg, 1)
    by = img_new(nseg, 1)
    bw = img_new(nseg, 1)
    bh = img_new(nseg, 1)
    maxw: int = 0
    maxh: int = 0
    i: int = 0
    while i < nseg:
        x0: int = py_list_ref(segs, i * 2)
        x1: int = py_list_ref(segs, i * 2 + 1)
        if x1 > w:
            x1 = w
        mnx: int = x1
        mxx: int = x0
        mny: int = h
        mxy: int = 0
        y = 0
        while y < h:
            x = x0
            while x < x1:
                if img_getpixel(im, x, y) % 256 > 10:
                    if x < mnx:
                        mnx = x
                    if x > mxx:
                        mxx = x
                    if y < mny:
                        mny = y
                    if y > mxy:
                        mxy = y
                x = x + 1
            y = y + 1
        if mxx < mnx:
            mnx = x0
            mxx = x0
            mny = 0
            mxy = 0
        img_putpixel(bx, i, 0, mnx)
        img_putpixel(by, i, 0, mny)
        img_putpixel(bw, i, 0, mxx - mnx + 1)
        img_putpixel(bh, i, 0, mxy - mny + 1)
        if mxx - mnx + 1 > maxw:
            maxw = mxx - mnx + 1
        if mxy - mny + 1 > maxh:
            maxh = mxy - mny + 1
        i = i + 1

    CW: int = maxw + 20
    CH: int = maxh + 20
    stk = img_new(CW * CH, 1)
    lab = img_new(CW, CH)
    i = 0
    while i < nseg:
        x0 = img_getpixel(bx, i, 0)
        y0 = img_getpixel(by, i, 0)
        bwv: int = img_getpixel(bw, i, 0)
        bhv: int = img_getpixel(bh, i, 0)
        canv = img_new(CW, CH)
        img_fill(canv, 0)
        img_fill(lab, 0)
        ox: int = int((CW - bwv) / 2)
        oy: int = CH - bhv - 10
        y = 0
        while y < bhv:
            x = 0
            while x < bwv:
                px: int = img_getpixel(im, x0 + x, y0 + y)
                if px % 256 > 0:
                    img_putpixel(canv, ox + x, oy + y, px)
                x = x + 1
            y = y + 1
        best_id: int = 0
        best_size: int = 0
        cid: int = 0
        y = 0
        while y < CH:
            x = 0
            while x < CW:
                if (img_getpixel(canv, x, y) % 256) > 10 and img_getpixel(lab, x, y) == 0:
                    cid = cid + 1
                    img_putpixel(lab, x, y, cid)
                    sp: int = 1
                    img_putpixel(stk, 0, 0, y * CW + x)
                    cnt: int = 0
                    while sp > 0:
                        sp = sp - 1
                        p: int = img_getpixel(stk, sp, 0)
                        qx: int = p % CW
                        qy: int = int(p / CW)
                        cnt = cnt + 1
                        if qx > 0:
                            if (img_getpixel(canv, qx - 1, qy) % 256) > 10 and img_getpixel(lab, qx - 1, qy) == 0:
                                img_putpixel(lab, qx - 1, qy, cid)
                                img_putpixel(stk, sp, 0, p - 1)
                                sp = sp + 1
                        if qx + 1 < CW:
                            if (img_getpixel(canv, qx + 1, qy) % 256) > 10 and img_getpixel(lab, qx + 1, qy) == 0:
                                img_putpixel(lab, qx + 1, qy, cid)
                                img_putpixel(stk, sp, 0, p + 1)
                                sp = sp + 1
                        if qy > 0:
                            if (img_getpixel(canv, qx, qy - 1) % 256) > 10 and img_getpixel(lab, qx, qy - 1) == 0:
                                img_putpixel(lab, qx, qy - 1, cid)
                                img_putpixel(stk, sp, 0, p - CW)
                                sp = sp + 1
                        if qy + 1 < CH:
                            if (img_getpixel(canv, qx, qy + 1) % 256) > 10 and img_getpixel(lab, qx, qy + 1) == 0:
                                img_putpixel(lab, qx, qy + 1, cid)
                                img_putpixel(stk, sp, 0, p + CW)
                                sp = sp + 1
                    if cnt > best_size:
                        best_size = cnt
                        best_id = cid
                x = x + 1
            y = y + 1
        y = 0
        while y < CH:
            x = 0
            while x < CW:
                if img_getpixel(lab, x, y) != best_id:
                    img_putpixel(canv, x, y, 0)
                x = x + 1
            y = y + 1
        if i < 10:
            nm: str = "f0" + string_of_int(i) + ".png"
        else:
            nm: str = "f" + string_of_int(i) + ".png"
        img_save(canv, outdir + "/" + nm)
        print(nm + " " + string_of_int(bwv) + "x" + string_of_int(bhv))
        img_free(canv)
        i = i + 1
    print("canvas " + string_of_int(CW) + "x" + string_of_int(CH))
    print("done")


main()
