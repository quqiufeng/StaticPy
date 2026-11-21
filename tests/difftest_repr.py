#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

"""difftest_repr.py — 显示层（print/repr/str）差分夹具：CPython vs StaticPy。

判据与 imgproc 一致：同一段源码分别跑 Python 与我们的 kernel，逐行比对 stdout。
语料按「已知的表示层分歧类别」分组，红了就能一眼看出是哪一类没对齐。

用法:
    python3 tests/difftest_repr.py          # 全量，摘要 + 失败明细
    python3 tests/difftest_repr.py -v       # 每条用例都打印
    python3 tests/difftest_repr.py none     # 只跑某组（子串匹配组名）
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO = os.path.expanduser("~/iso_gen")
os.makedirs(ISO, exist_ok=True)

# 每组: (组名, [表达式源码])；表达式写成「一个 Python 值表达式」，
# 夹具自动拼成 print(<expr>) —— 只测显示层，不测语义。
GROUPS = [
    ("basic", [
        "1", "-0", "123456789012345678", "True", "False",
        "'plain'", "''", "'it\\'s'", "'say \"hi\"'",
        "1.0", "0.0", "-0.0", "2.5", "0.1", "1e21", "1e-7", "100.0",
    ]),

    # None 与 False：已知分歧（None 编译成 #f，两者显示不可区分）
    ("none-false", [
        "None", "False", "True", "[None]", "[False, None]",
        "(None,)", "(False,)", "1 if False else None",
        "[x for x in [1, 2, 3] if x > 5]",
    ]),

    # tuple 与 list：已知分歧（tuple 也编译成 vector，显示同 list）
    ("tuple-list", [
        "[]", "[1, 2]", "[1, [2, 3]]",
        "()", "(1,)", "(1, 2)", "(1, (2, 3))",
        "[(1, 2), [3, 4]]", "((),)", "([],)",
    ]),

    # dict：已知分歧（Chez hashtable 无序，CPython 保插入序）
    ("dict", [
        "{'k': 1}",
        "{'a': 1, 'b': 2}",
        "{'b': 2, 'a': 1}",
        "{1: 'a', 2: 'b', 3: 'c'}",
        "{'nested': {'x': [1, (2, 3)]}}",
        "{}",
    ]),

    # 嵌套/混合：最能暴露「一类错了全串错」
    ("nested", [
        "[{'a': [1, (2, None)]}, 'b', 3.5, True]",
        "({'k': [1, 2]},)",
        "[1.0, [2.5, (3.5,)]]",
    ]),

    # 字符串转义细节
    ("escaping", [
        "'\\x00\\x01\\x1f'", "'\\x7f'", "'\\n'", "'\\t'", "'\\\\'",
        "'中文'", "['a\\tb', 'c\\nd']",
    ]),

    # 浮点极值
    ("float-edge", [
        "5e-324", "1e-320", "1.7976931348623157e308", "1234.5678",
        "9.999999999999999e15", "1e16", "1e17", "6.02e23", "-1e-5",
        "0.3333333333333333", "5.1047400000000005",
    ]),
]

VERBOSE = "-v" in sys.argv
FILTER = next((a for a in sys.argv[1:] if not a.startswith("-")), None)


def run_python(exprs):
    src = "\n".join("print(%s)" % e for e in exprs) + "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=ISO) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True)
        return r.stdout.splitlines(), r.stderr.strip()
    finally:
        os.unlink(path)


def run_staticpy(exprs):
    body = "\n".join("    print(%s)" % e for e in exprs)
    src = "def main() -> int:\n%s\n    return 0\n" % body
    name = os.path.join(ISO, "repr_difftest_case")
    with open(name + ".static.py", "w") as f:
        f.write(src)
    r = subprocess.run(
        [sys.executable, "-m", "kernel", "run", name + ".static.py"],
        capture_output=True, text=True, cwd=ROOT)
    out, err = [], []
    for line in r.stdout.splitlines():
        if line.startswith(">>>") or line.startswith("  ->") \
                or line.startswith("=== built") or line.startswith("    /"):
            continue
        out.append(line)
    if r.stderr.strip():
        err.append(r.stderr.strip())
    return out, "\n".join(err)


def main():
    total = fails = 0
    groups_report = []
    failures = []

    for gname, exprs in GROUPS:
        if FILTER and FILTER not in gname:
            continue
        py, py_err = run_python(exprs)
        sp, sp_err = run_staticpy(exprs)
        if py_err:
            print("!! CPython 语料自身有错（%s）: %s" % (gname, py_err))
            return 2
        gfail = 0
        for i, expr in enumerate(exprs):
            total += 1
            want = py[i] if i < len(py) else "<缺行>"
            got = sp[i] if i < len(sp) else "<缺行>"
            ok = want == got
            if not ok:
                fails += 1
                gfail += 1
                failures.append((gname, expr, want, got))
            if VERBOSE:
                print("%-11s %-34s %s  want=%r got=%r"
                      % (gname, expr, "PASS" if ok else "DIFF", want, got))
        if sp_err:
            print("!! StaticPy 报错（%s）: %s" % (gname, sp_err.splitlines()[0]))
        groups_report.append((gname, len(exprs), gfail))

    print("\n=== 分组 ===")
    for gname, n, gfail in groups_report:
        print("  %-11s %2d/%2d %s" % (gname, n - gfail, n, "" if not gfail else "  <-- 红了"))

    if failures:
        print("\n=== 失败明细 ===")
        for gname, expr, want, got in failures:
            print("  [%s] %s\n      CPython : %s\n      StaticPy: %s" % (gname, expr, want, got))

    print("\n共 %d 项，失败 %d 项（%d 组）" % (total, fails, len(set(f[0] for f in failures))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
