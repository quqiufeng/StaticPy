# sprof.static.py — Scheme 层热点报告：把 Chez 的表达式计数并回 Python 源行
#
# 数据来自 STATICPY_PROFILE=source 构建时 Chez 插入的计数器：
#   编译期 (compile-profile 'source) 给每个表达式插计数；
#   运行期 static_prof.scm 的 (static-prof-report) 把计数落成 TSV。
# 计数行号指向 merged.ss（prelude+stdlib+你的程序拼成的文件），
# 翻译器在每条语句前写了 `;; <你的.py>:<行号>` 注释——
# sprof 靠这条注释把 Scheme 行号折回 Python 行号。
#
# 用法：
#   sprof [<prof 文件>] [--top=N] [--ss=路径] [--fn-only]
#   默认读 $HOME/iso_gen/prof/ 下最新的 .prof
#
# 判据：hits 最高的那条 Python 语句就是"该改的那一行"；改完重编重跑，
#       hits 不变而总耗时下降 = 真的优化了（计数只数次数，不数时间）。


def read_text(path: str) -> str:
    if not file_exists(path):
        return ""
    fp: int = file_open(path, "r")
    if fp == 0:
        return ""
    s: str = file_read_all(fp)
    file_close(fp)
    return s


def split_nl(s: str) -> list:
    out: list = py_list()
    cur: str = ""
    i: int = 0
    n: int = str_length(s)
    while i < n:
        c: str = str_slice(s, i, i + 1)
        if c == "\n":
            out = py_list_append(out, cur)
            cur = ""
        else:
            cur = cur + c
        i = i + 1
    if str_length(cur) > 0:
        out = py_list_append(out, cur)
    return out


def find_sub(s: str, sub: str) -> int:
    n: int = str_length(s)
    m: int = str_length(sub)
    i: int = 0
    if m == 0:
        return 0
    while i + m <= n:
        if str_slice(s, i, i + m) == sub:
            return i
        i = i + 1
    return -1


def is_digit_str(s: str) -> bool:
    if str_length(s) == 0:
        return False
    i: int = 0
    while i < str_length(s):
        c: str = str_slice(s, i, i + 1)
        if c < "0" or c > "9":
            return False
        i = i + 1
    return True


def pad_left(s: str, w: int) -> str:
    out: str = s
    while str_length(out) < w:
        out = " " + out
    return out


def pad_right(s: str, w: int) -> str:
    out: str = s
    while str_length(out) < w:
        out = out + " "
    return out


# ---------- merged.ss 扫描：每行的归属（py 文件:行 + 所属函数） ----------

def comment_label(t: str) -> str:
    """`;; /path/foo.static.py:123` → `/path/foo.static.py:123`，其它返回空串"""
    if not str_starts_with(t, ";;"):
        return ""
    body: str = str_trim(str_slice(t, 2, str_length(t)))
    u: int = find_sub(body, ".py:")
    if u < 0:
        return ""
    j: int = u + 4
    k: int = j
    while k < str_length(body):
        c: str = str_slice(body, k, k + 1)
        if c < "0" or c > "9":
            break
        k = k + 1
    if k == j:
        return ""
    return str_slice(body, 0, k)


def def_name(t: str) -> str:
    """`(define (static_foo a b)` → `foo`；不是函数定义返回空串"""
    tt: str = str_trim(t)
    h: str = "(define (static_"
    if not str_starts_with(tt, h):
        return ""
    rest: str = str_slice(tt, str_length(h), str_length(tt))
    k: int = 0
    while k < str_length(rest):
        c: str = str_slice(rest, k, k + 1)
        if c == " " or c == ")" or c == "(":
            break
        k = k + 1
    return str_slice(rest, 0, k)


def scan_labels(ss_text: str) -> list:
    """返回 (labels, fns)：labels[i] = 第 i+1 行的 py 位置，fns[i] = 所属函数名"""
    lines: list = split_nl(ss_text)
    labels: list = py_list()
    fns: list = py_list()
    cur: str = ""
    curfn: str = ""
    pending: str = ""
    i: int = 0
    n: int = py_list_length(lines)
    while i < n:
        t: str = py_list_ref(lines, i)
        lab: str = comment_label(str_trim(t))
        fn: str = def_name(t)
        if str_length(lab) > 0:
            cur = lab
            pending = lab
            # 注意：**不清空** curfn —— 语句注释属于当前函数
        elif str_length(fn) > 0:
            curfn = fn
            if str_length(pending) > 0:
                curfn = fn + "  (" + pending + ")"
        labels = py_list_append(labels, cur)
        fns = py_list_append(fns, curfn)
        i = i + 1
    return py_list_append(py_list_append(py_list(), labels), fns)


# ---------- 计数聚合（不可变 py_list + 可变 dict） ----------

def bump(d: dict, names: list, key: str, add: int) -> list:
    old: str = dict_get_or_empty(d, key)
    if str_length(old) == 0:
        dict_set(d, key, string_of_int(add))
        return py_list_append(names, key)
    dict_set(d, key, string_of_int(string_to_int(old) + add))
    return names


def pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "  0.0%"
    sh: int = (part * 1000) // whole
    return pad_left(string_of_int(sh // 10) + "." + string_of_int(sh % 10), 6) + "%"


def top_rows(d: dict, names: list, limit: int) -> list:
    """按计数降序取前 limit 条，元素为 'key\tcount'"""
    out: list = py_list()
    used: dict = make_dict()
    total: int = py_list_length(names)
    got: int = 0
    while got < limit and got < total:
        best: str = ""
        bestv: int = -1
        i: int = 0
        while i < total:
            k: str = py_list_ref(names, i)
            if str_length(dict_get_or_empty(used, k)) == 0:
                v: int = string_to_int(dict_get_or_empty(d, k))
                if v > bestv:
                    bestv = v
                    best = k
            i = i + 1
        if str_length(best) == 0:
            got = limit
        else:
            dict_set(used, best, "1")
            out = py_list_append(out, best + "\t" + string_of_int(bestv))
            got = got + 1
    return out


# ---------- Python 源码行回显 ----------

def split_label(lab: str) -> list:
    """'/p/x.static.py:123' -> ['/p/x.static.py', '123']"""
    u: int = find_sub(lab, ".py:")
    if u < 0:
        return py_list_append(py_list_append(py_list(), lab), "0")
    return py_list_append(py_list_append(py_list(), str_slice(lab, 0, u + 3)),
                          str_slice(lab, u + 4, str_length(lab)))


def src_line(cache: dict, pyfile: str, lineno: int) -> str:
    txt: str = dict_get_or_empty(cache, pyfile)
    if str_length(txt) == 0:
        txt = read_text(pyfile)
        dict_set(cache, pyfile, txt)
    if str_length(txt) == 0 or lineno <= 0:
        return ""
    lines: list = split_nl(txt)
    if lineno > py_list_length(lines):
        return ""
    return str_trim(py_list_ref(lines, lineno - 1))


# ---------- 报告 ----------

def report(prof_path: str, ss_override: str, limit: int, fn_only: bool) -> None:
    txt: str = read_text(prof_path)
    if str_length(txt) == 0:
        print("sprof: 读不到 prof 文件: " + prof_path)
        print("  先做一次剖析构建: STATICPY_PROFILE=source bash staticpy/static_build_comfycli.sh <x.static.py> <out>")
        return
    lines: list = split_nl(txt)
    ss_path: str = ss_override
    mode: str = "?"
    rows: list = py_list()
    i: int = 0
    while i < py_list_length(lines):
        ln: str = py_list_ref(lines, i)
        if str_starts_with(ln, "#ss "):
            if str_length(ss_path) == 0:
                ss_path = str_slice(ln, 4, str_length(ln))
        elif str_starts_with(ln, "#mode "):
            mode = str_slice(ln, 6, str_length(ln))
        elif str_starts_with(ln, "#"):
            lines = lines
        elif str_length(str_trim(ln)) > 0:
            rows = py_list_append(rows, ln)
        i = i + 1
    ss_path = str_trim(ss_path)
    ss_text: str = read_text(ss_path)
    if str_length(ss_text) == 0:
        print("sprof: 读不到 Scheme 源: " + ss_path)
        print("  merged.ss 在 ~/iso_gen/staticpy-cache/，清理缓存后会消失；用 --ss= 指定")
        return
    packed: list = scan_labels(ss_text)
    labels: list = py_list_ref(packed, 0)
    fns: list = py_list_ref(packed, 1)
    stmt_d: dict = make_dict()
    stmt_n: list = py_list()
    fn_d: dict = make_dict()
    fn_n: list = py_list()
    total: int = 0
    runtime: int = 0
    i = 0
    while i < py_list_length(rows):
        flds: list = split_ws_tab(py_list_ref(rows, i))
        if py_list_length(flds) >= 3:
            cnt: int = string_to_int(py_list_ref(flds, 0))
            ln: int = string_to_int(py_list_ref(flds, 2))
            total = total + cnt
            lab: str = ""
            fn: str = ""
            if ln >= 1 and ln <= py_list_length(labels):
                lab = py_list_ref(labels, ln - 1)
                fn = py_list_ref(fns, ln - 1)
            if str_length(lab) == 0:
                runtime = runtime + cnt
            else:
                stmt_n = bump(stmt_d, stmt_n, lab, cnt)
                if str_length(fn) > 0:
                    fn_n = bump(fn_d, fn_n, fn, cnt)
        i = i + 1



    print("sprof — Scheme 层热点（mode=" + mode + "）")
    print("  prof: " + prof_path)
    print("  ss  : " + ss_path)
    print("  总计 " + string_of_int(total) + " hits，其中 "
          + string_of_int(runtime) + " 落在运行时（prelude/stdlib，无 py 归属）")
    if not fn_only:
        print("")
        print("  函数级（按计入的表达式 hits 排序）")
        print("   hits      占比  函数")
        tl: list = top_rows(fn_d, fn_n, limit)
        k: int = 0
        while k < py_list_length(tl):
            pair: list = split_ws_tab(py_list_ref(tl, k))
            nm: str = py_list_ref(pair, 0)
            v: int = string_to_int(py_list_ref(pair, 1))
            print("  " + pad_left(string_of_int(v), 9) + "  " + pct(v, total) + "  " + nm)
            k = k + 1
    print("")
    print("  语句级（hits 最高的 py 行 = 最该改的那一行）")
    print("   hits      占比  位置")
    cache: dict = make_dict()
    tl2: list = top_rows(stmt_d, stmt_n, limit)
    k2: int = 0
    while k2 < py_list_length(tl2):
        pair: list = split_ws_tab(py_list_ref(tl2, k2))
        lab: str = py_list_ref(pair, 0)
        v: int = string_to_int(py_list_ref(pair, 1))
        parts: list = split_label(lab)
        pyf: str = py_list_ref(parts, 0)
        ln: int = string_to_int(py_list_ref(parts, 1))
        print("  " + pad_left(string_of_int(v), 9) + "  " + pct(v, total) + "  "
              + pyf + ":" + string_of_int(ln))
        snip: str = src_line(cache, pyf, ln)
        if str_length(snip) > 0:
            print("             | " + snip)
        k2 = k2 + 1


def split_ws_tab(s: str) -> list:
    out: list = py_list()
    cur: str = ""
    i: int = 0
    while i < str_length(s):
        c: str = str_slice(s, i, i + 1)
        if c == "\t":
            out = py_list_append(out, cur)
            cur = ""
        else:
            cur = cur + c
        i = i + 1
    return py_list_append(out, cur)


def usage() -> None:
    print("sprof.static.py — Scheme 层热点报告")
    print("  sprof [PROF] [--top=N] [--ss=路径] [--fn-only]")
    print("  PROF 省略时读 $HOME/iso_gen/prof/ 下最新的 .prof")


def last_prof() -> str:
    """static-prof-report 会把最近一次 dump 的路径写进 ~/iso_gen/prof/last.txt"""
    home: str = os_getenv("HOME")
    p: str = str_trim(read_text(home + "/iso_gen/prof/last.txt"))
    if str_length(p) > 0:
        return p
    return home + "/iso_gen/prof/static.prof"


def main() -> None:
    args: list = list_to_py_list(argv())
    n: int = py_list_length(args)
    prof: str = ""
    ss: str = ""
    limit: int = 20
    fn_only: bool = False
    i: int = 1
    while i < n:
        a: str = py_list_ref(args, i)
        if str_starts_with(a, "--top="):
            limit = string_to_int(str_slice(a, 6, str_length(a)))
        elif str_starts_with(a, "--ss="):
            ss = str_slice(a, 5, str_length(a))
        elif a == "--fn-only":
            fn_only = True
        elif a == "-h" or a == "--help":
            usage()
            return
        else:
            prof = a
        i = i + 1
    if str_length(prof) == 0:
        prof = last_prof()
    report(prof, ss, limit, fn_only)


if __name__ == "__main__":
    main()
