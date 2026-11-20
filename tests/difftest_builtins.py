#!/usr/bin/env python3
"""difftest_builtins.py — 内建函数差分夹具：CPython vs StaticPy。

判据与 imgproc 一致：同一段源码分别跑 Python 与我们的 AOT ELF，逐行比对 stdout。
语料按「一族内建」分组：sum/min/max、sorted、enumerate/zip、any/all、tuple 显示。

用法:
    python3 tests/difftest_builtins.py          # 全量，摘要 + 失败明细
    python3 tests/difftest_builtins.py -v       # 每条用例都打印
    python3 tests/difftest_builtins.py sorted   # 只跑某组（子串匹配组名）
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISO = os.path.expanduser("~/iso_gen")
os.makedirs(ISO, exist_ok=True)

# 每组: (组名, [语句源码])；语句原样进 main()，print 的输出来比对
GROUPS = [
    ("sum-min-max", [
        "xs = [3, 1, 4, 1, 5]\nprint(sum(xs), min(xs), max(xs))",
        "print(sum([1.5, 2.5]), sum([]), sum([1, 2], 10))",
        "print(min([2.5, 1]), max([2.5, 1]))",
        "print(max(3, 9, 2), min(3, 9, 2))",
        "print(max('abc'), min('abc'))",
        "print(abs(-7), abs(-2.5), abs(0))",
    ]),
    ("sorted", [
        "print(sorted([3, 1, 2]))",
        "print(sorted([3, 1, 2], reverse=True))",
        "print(sorted(['bb', 'a', 'ccc'], key=len))",
        "print(sorted(['banana', 'Apple', 'cherry'], key=str.lower))",
        "print(sorted([]), sorted('cab'))",
        "xs = [3, 1]\nprint(sorted(xs), xs)",
    ]),
    ("enumerate-zip", [
        "for i, v in enumerate('abc'):\n    print(i, v)",
        "for i, v in enumerate([10, 20], 5):\n    print(i, v)",
        "for a, b in zip([1, 2], ['x', 'y']):\n    print(a, b)",
        "print(list(zip([1, 2, 3], 'ab')))",
        "print(list(enumerate([])))",
    ]),
    ("any-all", [
        "print(any([0, 1]), all([1, 2]))",
        "print(any([]), all([]))",
        "print(any([0, '']), all([1, 'x']))",
    ]),
    ("tuple-repr", [
        "t = (1, 2)\nprint(t, t[0], len(t))",
        "print((1,), (), (1, (2, 3)))",
        "print([(1, 2), [3, 4]])",
        "a, b = (7, 8)\nprint(a, b)",
        "print(max((3, 9)), sum((1, 2, 3)))",
    ]),
    # 位运算：翻译器兜底 str_lower(Op) 会发 bitand/bitor/bitxor/lshift/rshift/Invert，
    # 这些名字由 static_prelude.scm 映射到 R6RS bitwise-*。语料覆盖负数与 bignum
    # （Python int 任意精度，算术右移 -8>>1 = -4，~x = -(x+1)）。
    ("bitwise", [
        "a = 6\nb = 3\nprint(a & b, a | b, a ^ b, a << b, a >> b)",
        "print(~6, ~0, ~-1)",
        "print(-8 >> 1, -1 & 255, -1 | 0, -1 ^ 0)",
        "print(1 << 62, (1 << 62) >> 60)",
        "print(255 & 0xF0, 0x0F | 0xF0, 0xFF ^ 0x0F)",
        "x = 0b1011\nprint(x & 0b0110, x | 0b0100, x ^ 0b1111)",
    ]),
]

VERBOSE = "-v" in sys.argv
FILTER = next((a for a in sys.argv[1:] if not a.startswith("-")), None)


def run_python(src):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=ISO) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True)
        return r.stdout.splitlines(), r.stderr.strip()
    finally:
        os.unlink(path)


def run_staticpy(src):
    name = os.path.join(ISO, "builtins_difftest_case")
    with open(name + ".static.py", "w") as f:
        f.write(src)
    r = subprocess.run(
        [sys.executable, "-m", "kernel", "run", name + ".static.py"],
        capture_output=True, text=True, cwd=ROOT)
    out = []
    for line in r.stdout.splitlines():
        if line.startswith(">>>") or line.startswith("  ->") \
                or line.startswith("=== built") or line.startswith("    "):
            continue
        out.append(line)
    err = [l for l in r.stderr.splitlines() if l and not l.startswith(">>>")]
    return out, "\n".join(err)


def main():
    total = fails = 0
    failures = []
    for gname, stmts in GROUPS:
        if FILTER and FILTER not in gname:
            continue
        gfail = 0
        for stmt in stmts:
            src = "def main() -> int:\n"
            for line in stmt.splitlines():
                src += "    " + line + "\n"
            src += "    return 0\n"
            py, py_err = run_python("\n".join(stmt.splitlines()) + "\n")
            sp, sp_err = run_staticpy(src)
            total += 1
            ok = py == sp
            if not ok:
                fails += 1
                gfail += 1
                failures.append((gname, stmt, py, sp, sp_err))
            if VERBOSE:
                print("%-13s %-50s %s" % (gname, stmt.splitlines()[-1][:50],
                                          "PASS" if ok else "DIFF"))
        print("%-13s %d/%d" % (gname, len(stmts) - gfail, len(stmts)))

    if failures:
        print("\n=== 失败明细 ===")
        for gname, stmt, py, sp, sp_err in failures:
            print("  [%s] %s" % (gname, stmt.replace("\n", " / ")))
            print("      CPython  : %s" % py)
            print("      StaticPy : %s" % sp)
            if sp_err:
                print("      stderr   : %s" % sp_err.splitlines()[0])
    print("\n共 %d 项，失败 %d 项" % (total, fails))
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
