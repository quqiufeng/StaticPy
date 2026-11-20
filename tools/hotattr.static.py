# hotattr.static.py — 热偏移归因：把 trace 里的 `[anon]+0x…` 变成"能改的那段代码"
#
# 问题：Chez AOT 出来的代码落在匿名可执行区，perf 只能给 `[anon]+0x1234`；
#       而且这个偏移每次运行会漂移（±0x2000），所以坐标必须**在当次进程里**取。
#
# 用法（每步都只是读 /proc + 写 /tmp/perf-<pid>.map）：
#   hotattr.s diff  TRACE.json...                多轮采集聚合（0x400 桶），看谁是真热块
#   hotattr.s map   PID [GRAN]                   匿名可执行区按 GRAN 切块打标签 → 采一轮拿热块
#   hotattr.s drill PID RELOFF [WIN] [GRAN]      只在该偏移 ±WIN 内按 GRAN 细标 → 再采一轮拿指令组
#   hotattr.s bytes PID RELOFF [LEN]             读那段机器码（hex + objdump 反汇编）
#
# 典型循环：
#   ./hotattr.s map  $PID            # 采 2s → trace 里出现 A0_1e000 这样的块名
#   ./hotattr.s drill $PID 0x1e000   # 采 2s → 出现 A0_d1e040 这样的 64B 块名
#   ./hotattr.s bytes $PID 0x1e040   # 看指令 → 对照 .ss / static_translate 的产物改代码
#
# 判据永远是：改完重编、重跑差分/微基准，热块消失即有效。

HEXDIG: str = "0123456789abcdef"
TOPPATH: str = "/tmp/perf-"
GRAN_DEF: int = 4096


def die(msg: str) -> None:
    print("error: " + msg)
    exit(2)


def hexval(c: str) -> int:
    i: int = 0
    while i < 16:
        if str_slice(HEXDIG, i, i + 1) == c:
            return i
        i = i + 1
    return -1


def hex_to_int(s: str) -> int:
    t: str = str_lower(str_trim(s))
    if str_starts_with(t, "0x"):
        t = str_slice(t, 2, str_length(t))
    v: int = 0
    i: int = 0
    n: int = str_length(t)
    while i < n:
        d: int = hexval(str_slice(t, i, i + 1))
        if d < 0:
            return v
        v = v * 16 + d
        i = i + 1
    return v


def parse_num(s: str) -> int:
    t: str = str_lower(str_trim(s))
    if str_starts_with(t, "0x"):
        return hex_to_int(t)
    if str_starts_with(t, "a") and find_sub(t, "_") > 0:
        # 接受 trace 里直接抄下来的块名：A0_59000 / A0_d59100
        u: int = find_sub(t, "_")
        rest: str = str_slice(t, u + 1, str_length(t))
        if str_starts_with(rest, "d_"):
            rest = str_slice(rest, 2, str_length(rest))
        return hex_to_int(rest)
    return string_to_int(t)


def to_hex(v: int) -> str:
    if v <= 0:
        return "0"
    out: str = ""
    x: int = v
    while x > 0:
        out = str_slice(HEXDIG, x % 16, x % 16 + 1) + out
        x = x // 16
    return out


def pad_right(s: str, w: int) -> str:
    out: str = s
    while str_length(out) < w:
        out = out + " "
    return out


def pad_left(s: str, w: int) -> str:
    out: str = s
    while str_length(out) < w:
        out = " " + out
    return out


def find_sub(s: str, sub: str) -> int:
    n: int = str_length(s)
    m: int = str_length(sub)
    i: int = 0
    while i + m <= n:
        if str_slice(s, i, i + m) == sub:
            return i
        i = i + 1
    return -1


def split_ws(line: str) -> list:
    parts: list = py_list()
    cur: str = ""
    i: int = 0
    n: int = str_length(line)
    while i < n:
        c: str = str_slice(line, i, i + 1)
        if c == " " or c == "\t":
            if str_length(cur) > 0:
                parts = py_list_append(parts, cur)
                cur = ""
        else:
            cur = cur + c
        i = i + 1
    if str_length(cur) > 0:
        parts = py_list_append(parts, cur)
    return parts


def read_text(path: str) -> str:
    if not file_exists(path):
        return ""
    fp: int = file_open(path, "r")
    if fp == 0:
        return ""
    s: str = file_read_all(fp)
    file_close(fp)
    return s


# ---------- maps 解析 ----------

def check_pid(pid: str) -> None:
    if str_length(pid) == 0:
        die("缺 pid")
    i: int = 0
    while i < str_length(pid):
        if str_slice(pid, i, i + 1) < "0" or str_slice(pid, i, i + 1) > "9":
            die("pid 只能是数字，收到 \"" + pid + "\"")
        i = i + 1


def load_regions(pid: str) -> list:
    """[start, end, idx] —— 匿名可执行区（AOT/JIT 代码 + 我们写的 C helper）"""
    txt: str = read_text("/proc/" + pid + "/maps")
    if str_length(txt) == 0:
        die("/proc/" + pid + "/maps 读不到（进程不存在，或需要权限）")
    regs: list = py_list()
    lines: list = str_split(txt, "\n")
    i: int = 0
    n: int = py_list_length(lines)
    while i < n:
        line: str = str_trim(py_list_ref(lines, i))
        i = i + 1
        if str_length(line) == 0:
            continue
        f: list = split_ws(line)
        if py_list_length(f) < 2:
            continue
        perms: str = py_list_ref(f, 1)
        if find_sub(perms, "x") < 0:
            continue
        # 有路径名的（.so / ELF）perf 自己能符号化，不要抢
        if py_list_length(f) >= 6:
            continue
        rng: str = py_list_ref(f, 0)
        dash: int = find_sub(rng, "-")
        if dash < 0:
            continue
        start: int = hex_to_int(str_slice(rng, 0, dash))
        end: int = hex_to_int(str_slice(rng, dash + 1, str_length(rng)))
        if end - start < 4096:
            continue
        regs = py_list_append(regs, py_list(start, end))
    return regs


def write_perfmap(pid: str, entries: list) -> None:
    path: str = TOPPATH + pid + ".map"
    fp: int = file_open(path, "w")
    if fp == 0:
        die("写不了 " + path)
    i: int = 0
    n: int = py_list_length(entries)
    while i < n:
        e: list = py_list_ref(entries, i)
        file_write(fp, to_hex(py_list_ref(e, 0)) + " " + to_hex(py_list_ref(e, 1)) + " " + py_list_ref(e, 2) + "\n")
        i = i + 1
    file_close(fp)
    print("→ " + path + "  (" + string_of_int(n) + " 条标签)")


def legend(regs: list) -> None:
    i: int = 0
    n: int = py_list_length(regs)
    while i < n:
        r: list = py_list_ref(regs, i)
        s: int = py_list_ref(r, 0)
        e: int = py_list_ref(r, 1)
        print("  A" + string_of_int(i) + "  " + to_hex(s) + "-" + to_hex(e)
              + "  size=" + to_hex(e - s))
        i = i + 1


# ---------- ① map：整区按 GRAN 切块 ----------

def cmd_map(pid: str, gran: int) -> None:
    regs: list = load_regions(pid)
    if py_list_length(regs) == 0:
        die("没有匿名可执行区：AOT 代码可能还没加载（先让进程跑起来）")
    print("匿名可执行区：")
    legend(regs)
    entries: list = py_list()
    ri: int = 0
    nr: int = py_list_length(regs)
    while ri < nr:
        r: list = py_list_ref(regs, ri)
        s: int = py_list_ref(r, 0)
        e: int = py_list_ref(r, 1)
        off: int = 0
        while off < e - s:
            entries = py_list_append(entries, py_list(s + off, gran, "A" + string_of_int(ri) + "_" + to_hex(off)))
            off = off + gran
        ri = ri + 1
    write_perfmap(pid, entries)
    print("下一步：采一轮（trace oncpu），看哪个 A*_* 块最热，再 `hotattr.s drill " + pid + " 0x<off>`")


# ---------- ② drill：只在一个窗口内细标 ----------

def cmd_drill(pid: str, reloff: int, win: int, gran: int) -> None:
    regs: list = load_regions(pid)
    if py_list_length(regs) == 0:
        die("没有匿名可执行区")
    entries: list = py_list()
    ri: int = 0
    nr: int = py_list_length(regs)
    while ri < nr:
        r: list = py_list_ref(regs, ri)
        s: int = py_list_ref(r, 0)
        e: int = py_list_ref(r, 1)
        size: int = e - s
        if reloff < size:
            lo: int = reloff - win
            if lo < 0:
                lo = 0
            hi: int = reloff + win
            if hi > size:
                hi = size
            off: int = lo - (lo % gran)
            while off < hi:
                entries = py_list_append(entries, py_list(s + off, gran, "A" + string_of_int(ri) + "_d_" + to_hex(off)))
                off = off + gran
        ri = ri + 1
    write_perfmap(pid, entries)
    print("下一步：再采一轮，热块会收窄到 " + string_of_int(gran) + "B；")
    print("        然后 `hotattr.s bytes " + pid + " 0x" + to_hex(reloff) + "`")


# ---------- ③ bytes：读机器码 ----------

def cmd_bytes(pid: str, reloff: int, ln: int) -> None:
    regs: list = load_regions(pid)
    if py_list_length(regs) == 0:
        die("没有匿名可执行区")
    # 取最大的那块（AOT 代码区通常最大），够装 reloff 的优先
    best: list = py_list_ref(regs, 0)
    ri: int = 0
    nr: int = py_list_length(regs)
    while ri < nr:
        r: list = py_list_ref(regs, ri)
        cur: int = py_list_ref(best, 1) - py_list_ref(best, 0)
        nw: int = py_list_ref(r, 1) - py_list_ref(r, 0)
        if nw > cur and reloff < nw:
            best = r
        ri = ri + 1
    if reloff >= py_list_ref(best, 1) - py_list_ref(best, 0):
        die("reloff 超出最大匿名区（" + to_hex(py_list_ref(best, 1) - py_list_ref(best, 0)) + "）")
    addr: int = py_list_ref(best, 0) + reloff
    out: str = "/root/iso_gen/hotattr-" + pid + "-" + to_hex(reloff) + ".bin"
    home: str = os_getenv("HOME")
    if str_length(home) > 0:
        out = home + "/iso_gen/hotattr-" + pid + "-" + to_hex(reloff) + ".bin"
    cmd: str = ("dd if=/proc/" + pid + "/mem of=" + out + " bs=1 skip=" + string_of_int(addr)
                + " count=" + string_of_int(ln) + " 2>/dev/null; echo ---; od -An -tx1 -v -w16 " + out)
    print("addr=0x" + to_hex(addr) + "  (" + string_of_int(ln) + " 字节 → " + out + ")")
    os_shell(cmd)
    print("反汇编： objdump -D -b binary -m i386:x86-64 --adjust-vma=0x" + to_hex(addr) + " " + out)


# ---------- ④ diff：多轮采集聚合 ----------

def stack_leaf_anon(stack: str) -> int:
    """栈里最内层那帧 `[anon]+0x…` 的偏移；没有 → -1"""
    frames: list = str_split(stack, ";")
    i: int = 0
    n: int = py_list_length(frames)
    while i < n:
        fr: str = str_trim(py_list_ref(frames, i))
        if str_starts_with(fr, "[anon]+0x"):
            return hex_to_int(str_slice(fr, 7, str_length(fr)))
        i = i + 1
    return -1


def sort_desc(keys: list, totals: dict) -> list:
    remaining: list = keys
    out: list = py_list()
    while py_list_length(remaining) > 0:
        n: int = py_list_length(remaining)
        bi: int = 0
        bv: int = dict_get(totals, py_list_ref(remaining, 0))
        i: int = 1
        while i < n:
            v: int = dict_get(totals, py_list_ref(remaining, i))
            if v > bv:
                bv = v
                bi = i
            i = i + 1
        out = py_list_append(out, py_list_ref(remaining, bi))
        # 去掉第 bi 个
        left: list = py_list()
        j: int = 0
        while j < n:
            if j != bi:
                left = py_list_append(left, py_list_ref(remaining, j))
            j = j + 1
        remaining = left
    return out


def cmd_diff(files: list, gran: int, limit: int) -> None:
    nf: int = py_list_length(files)
    if nf == 0:
        die("需要至少一个 trace json")
    totals: dict = make_dict()
    anon_total: dict = make_dict()
    events: dict = make_dict()
    keys: list = py_list()
    fi: int = 0
    while fi < nf:
        path: str = py_list_ref(files, fi)
        txt: str = read_text(path)
        if str_length(txt) == 0:
            die("读不到 " + path)
        obj: dict = parse_json(txt)
        ev: int = dict_get(obj, "events")
        if ev is None:
            ev = 0
        events[fi] = ev
        anon_total[fi] = 0
        top: list = dict_get(obj, "top")
        if top is not None:
            ti: int = 0
            tn: int = py_list_length(top)
            while ti < tn:
                e: dict = py_list_ref(top, ti)
                cnt: int = dict_get(e, "count")
                st: str = dict_get_or_empty(e, "stack")
                off: int = stack_leaf_anon(st)
                if off >= 0 and cnt is not None:
                    b: int = off - (off % gran)
                    kb: str = string_of_int(b)
                    if dict_get(totals, kb) is None:
                        keys = py_list_append(keys, kb)
                        totals[kb] = 0
                    totals[kb] = dict_get(totals, kb) + cnt
                    anon_total[fi] = anon_total[fi] + cnt
                    kf: str = string_of_int(fi) + ":" + kb
                    old: int = 0
                    if dict_get(totals, kf) is not None:
                        old = dict_get(totals, kf)
                    totals[kf] = old + cnt
                ti = ti + 1
        fi = fi + 1
    print("文件:")
    fi = 0
    while fi < nf:
        print("  #" + string_of_int(fi) + " " + py_list_ref(files, fi)
              + "  events=" + string_of_int(events[fi])
              + "  anon=" + string_of_int(anon_total[fi]))
        fi = fi + 1
    print("")
    head: str = pad_right("block", 14)
    fi = 0
    while fi < nf:
        head = head + pad_left("#" + string_of_int(fi), 7)
        fi = fi + 1
    head = head + pad_left("anon%", 8) + pad_left("Δ", 7)
    print(head)
    ordered: list = sort_desc(keys, totals)
    i: int = 0
    n: int = py_list_length(ordered)
    rows: int = 0
    while i < n:
        if rows >= limit:
            break
        kb: str = py_list_ref(ordered, i)
        line: str = pad_right("+0x" + to_hex(string_to_int(kb) // 16 * 16), 14)
        fi = 0
        first: int = 0
        last: int = 0
        while fi < nf:
            kf: str = string_of_int(fi) + ":" + kb
            c: int = 0
            if dict_get(totals, kf) is not None:
                c = dict_get(totals, kf)
            line = line + pad_left(string_of_int(c), 7)
            if fi == 0:
                first = c
            last = c
            fi = fi + 1
        at: int = anon_total[nf - 1]
        pct: float = 0.0
        if at > 0:
            pct = last / at * 100.0
        line = line + pad_left(format_float(pct, 1) + "%", 8)
        line = line + pad_left(string_of_int(last - first), 7)
        print(line)
        rows = rows + 1
        i = i + 1
    print("")
    print("（桶 = 0x" + to_hex(gran) + "；anon% 按最后一轮的匿名样本计；Δ = 最后一轮 − 第一轮）")


def usage() -> None:
    print("hotattr.static.py — 热偏移归因")
    print("  diff  TRACE.json...                    多轮聚合（默认桶 0x400）")
    print("  map   PID [GRAN]                       匿名可执行区按 GRAN 切块打标签（默认 4096）")
    print("  drill PID RELOFF [WIN] [GRAN]          ±WIN 内细标（默认 WIN=0x800 GRAN=0x40）")
    print("  bytes PID RELOFF [LEN]                 读机器码 + 反汇编命令（默认 LEN=128）")


def main() -> None:
    args: list = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 2:
        usage()
        return
    cmd: str = py_list_ref(args, 1)
    if cmd == "diff":
        gran: int = 1024
        limit: int = 20
        rest: list = py_list()
        i: int = 2
        while i < n:
            a: str = py_list_ref(args, i)
            if str_starts_with(a, "--gran="):
                gran = parse_num(str_slice(a, 7, str_length(a)))
            elif str_starts_with(a, "--top="):
                limit = string_to_int(str_slice(a, 6, str_length(a)))
            else:
                rest = py_list_append(rest, a)
            i = i + 1
        cmd_diff(rest, gran, limit)
        return
    if cmd == "map":
        if n < 3:
            usage()
            return
        pid: str = py_list_ref(args, 2)
        check_pid(pid)
        gran: int = GRAN_DEF
        if n >= 4:
            gran = parse_num(py_list_ref(args, 3))
        cmd_map(pid, gran)
        return
    if cmd == "drill":
        if n < 4:
            usage()
            return
        pid = py_list_ref(args, 2)
        check_pid(pid)
        reloff: int = parse_num(py_list_ref(args, 3))
        win: int = 2048
        gran = 64
        if n >= 5:
            win = parse_num(py_list_ref(args, 4))
        if n >= 6:
            gran = parse_num(py_list_ref(args, 5))
        cmd_drill(pid, reloff, win, gran)
        return
    if cmd == "bytes":
        if n < 4:
            usage()
            return
        pid = py_list_ref(args, 2)
        check_pid(pid)
        reloff = parse_num(py_list_ref(args, 3))
        ln: int = 128
        if n >= 5:
            ln = string_to_int(py_list_ref(args, 4))
        cmd_bytes(pid, reloff, ln)
        return
    usage()
