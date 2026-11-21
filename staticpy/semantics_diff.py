#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

"""semantics_diff.py — 翻译器语义差分：CPython 输出 vs StaticPy ELF 输出。

tokenize_diff.py / parse_diff.py 只守住**前端形状**，守不住"翻过去了但语义跑偏"。
这一层补的就是那个空白：同一份 `.static.py`，一边 CPython 跑，一边 AOT 编译成
ELF 跑，**逐行 diff stdout**。判据仍是机器给的（VISION：对不对交给机器报）。

用例约定（tests/semantics/*.static.py）：
  - 只写 `def main():`，**不要在顶层调用**（StaticPy 会自动调；CPython 侧由本脚本补）。
  - 需要非零退出码时，用返回码参与比对（CPython 的 main() 返回值本脚本不取，只比 stdout）。

用法：
  python3 staticpy/semantics_diff.py            # 跑全部用例
  python3 staticpy/semantics_diff.py -v         # 打印每次调用的输出
  python3 staticpy/semantics_diff.py none_in    # 只跑名字含 none_in 的用例
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "tests", "semantics")
BUILD = os.path.join(ROOT, "staticpy", "static_build_comfycli.sh")
OUTDIR = os.path.join(ROOT, "dist", "semantics")


def run_cpython(src, tmpdir):
    """补一行 main() 调用，用 CPython 跑出参考输出"""
    py = os.path.join(tmpdir, os.path.basename(src).replace(".static.py", "_py.py"))
    with open(src, encoding="utf-8") as f:
        body = f.read()
    with open(py, "w", encoding="utf-8") as f:
        f.write(body + "\n\nmain()\n")
    r = subprocess.run([sys.executable, py], capture_output=True, text=True, timeout=120)
    return r.stdout, r.returncode, r.stderr


def run_staticpy(src, name, tmpdir):
    """AOT 编译成 ELF 再执行"""
    env = dict(os.environ, STATICPY_OUTDIR=OUTDIR)
    b = subprocess.run(["bash", BUILD, src, name], capture_output=True, text=True,
                       env=env, timeout=600, cwd=ROOT)
    elf = os.path.join(OUTDIR, name)
    if b.returncode != 0 or not os.path.exists(elf):
        tail = (b.stderr or b.stdout).strip().splitlines()[-6:]
        return None, None, "构建失败:\n    " + "\n    ".join(tail)
    r = subprocess.run([elf], capture_output=True, text=True, timeout=120)
    return r.stdout, r.returncode, r.stderr


def main():
    verbose = "-v" in sys.argv
    filters = [a for a in sys.argv[1:] if not a.startswith("-")]
    cases = sorted(f for f in os.listdir(CASES) if f.endswith(".static.py"))
    if filters:
        cases = [c for c in cases if any(k in c for k in filters)]
    if not cases:
        print("没有用例（tests/semantics/*.static.py）")
        return 1

    os.makedirs(OUTDIR, exist_ok=True)
    fails = 0
    for c in cases:
        src = os.path.join(CASES, c)
        name = "sem_" + c.replace(".static.py", "")
        with tempfile.TemporaryDirectory() as tmp:
            py_out, py_rc, py_err = run_cpython(src, tmp)
        sp_out, sp_rc, sp_err = run_staticpy(src, name, OUTDIR)

        if sp_out is None:
            fails += 1
            print(f"BUILD {c}\n    {sp_err}")
            continue
        if py_out == sp_out:
            print(f"PASS  {c}  ({len(py_out.splitlines())} 行一致)")
            if verbose:
                print("".join(f"    | {l}\n" for l in sp_out.splitlines()))
        else:
            fails += 1
            print(f"DIFF  {c}")
            py_lines, sp_lines = py_out.splitlines(), sp_out.splitlines()
            for i in range(max(len(py_lines), len(sp_lines))):
                a = py_lines[i] if i < len(py_lines) else "<缺行>"
                b = sp_lines[i] if i < len(sp_lines) else "<缺行>"
                if a != b:
                    print(f"    行{i+1}: CPython={a!r}  我们={b!r}")
            if sp_err.strip():
                print(f"    stderr: {sp_err.strip().splitlines()[-1]}")

    print(f"\n共 {len(cases)} 项，失败 {fails} 项")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
