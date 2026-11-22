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
BUILD = os.path.join(ROOT, "staticpy", "static_build.sh")
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


def build_staticpy(src, name):
    """AOT 编译成 ELF；返回 (elf 路径或 None, 构建输出尾部, 原始输出全文)"""
    env = dict(os.environ, STATICPY_OUTDIR=OUTDIR)
    b = subprocess.run(["bash", BUILD, src, name], capture_output=True, text=True,
                       env=env, timeout=600, cwd=ROOT)
    elf = os.path.join(OUTDIR, name)
    full = (b.stdout or "") + (b.stderr or "")
    if b.returncode != 0 or not os.path.exists(elf):
        tail = full.strip().splitlines()[-6:]
        return None, "构建失败:\n    " + "\n    ".join(tail), full
    return elf, "", full


def run_elf(elf):
    r = subprocess.run([elf], capture_output=True, text=True, timeout=120)
    return r.stdout, r.returncode, r.stderr


def run_staticpy(src, name, tmpdir):
    """AOT 编译成 ELF 再执行"""
    elf, err, _ = build_staticpy(src, name)
    if elf is None:
        return None, None, err
    return run_elf(elf)


def expect_of(src):
    """用例头部的响亮失败声明：`# expect: build-error 子串` / `# expect: runtime-error 子串`

    这两种用例测的不是输出值，而是**不支持的东西必须响**（VISION：静默降级=bug）。
    """
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("# expect:"):
                continue
            body = line[len("# expect:"):].strip()
            kind, _, needle = body.partition(" ")
            return kind.strip(), needle.strip()
    return "", ""


def check_loud(case, src, name, kind, needle, verbose=False):
    """响亮失败用例：不支持的东西必须在**构建期或运行期**报出 needle（非零退出）"""
    elf, build_err, build_full = build_staticpy(src, name)
    if kind == "build-error":
        if elf is not None:
            print(f"LOUD  {case}: 期望构建期报错，但构建成功了")
            return False
        ok = (needle == "") or (needle in build_full)
        print(("PASS  " if ok else "LOUD  ") + f"{case}  (构建期响亮失败)")
        if not ok:
            print(f"    期望报错信息含 {needle!r}，实际：\n    {build_err}")
        elif verbose:
            print("".join(f"    | {l}\n" for l in build_full.strip().splitlines()[-4:]))
        return ok
    if elf is None:
        print(f"LOUD  {case}: 期望运行期报错，但构建就失败了\n    {build_err}")
        return False
    out, rc, err = run_elf(elf)
    loud = rc != 0
    ok = loud and ((needle == "") or (needle in err or needle in out))
    tail = (out + err).strip().splitlines()
    print(("PASS  " if ok else "LOUD  ") + f"{case}  (运行期响亮失败 rc={rc})")
    if not ok:
        print(f"    期望：rc≠0 且信息含 {needle!r}；实际 rc={rc}")
    if verbose or not ok:
        print("".join(f"    | {l}\n" for l in tail[-4:]))
    return ok


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
        kind, needle = expect_of(src)
        if kind in ("build-error", "runtime-error"):
            fails += 0 if check_loud(c, src, name, kind, needle, verbose) else 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            py_out, py_rc, py_err = run_cpython(src, tmp)
        if py_rc != 0:
            # 参考端自己就崩了：用例写错，而不是我们不对 —— 别让「两边都空」混过
            fails += 1
            tail = py_err.strip().splitlines()[-1] if py_err.strip() else ""
            print(f"BAD   {c}  CPython 侧非零退出 rc={py_rc}: {tail}")
            continue
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
