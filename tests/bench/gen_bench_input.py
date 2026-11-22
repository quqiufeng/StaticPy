#!/usr/bin/env python3
# [自举豁免 · 宿主] 只生成基准输入，不产出 IR，不进产物（AGENTS §0/§4）。
"""tests/bench/gen_bench_input.py — 生成**确定性**的基准输入（大小固定、内容固定）

为什么不用仓库外的大文件当基准：基准换输入就没法比较了。这里按固定模板重复
生成 ~1.1 MB 的 StaticPy 源码（形状接近真实翻译器的规模分布：大量函数、
局部变量、字符串、条件、循环、算符），任何机器上 `python3 bench.sh` 得到同一份输入。

用法：
  python3 tests/bench/gen_bench_input.py [输出路径] [函数个数]
"""
import sys

TMPL = '''
def fn_{i}(a: int, b: int, s: str) -> int:
    """第 {i} 个样本函数"""
    c: int = a + b * {i}
    if c > {i}:
        c = c - {i}
    elif c < 0:
        c = -c
    else:
        c = c + 1
    t: str = s + "_{i}"
    if t == "x_{i}":
        c = c + len(t)
    d: dict = {{"k": c, "v": {i}}}
    e: int = 0
    for ch in t:
        if ch == "_":
            e = e + 1
    j: int = 0
    while j < 4:
        c = c + j * {i}
        j = j + 1
    return c + e + len(d)
'''


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "bench_input.static.py"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2200
    parts = ["# 自动生成，勿手改：tests/bench/gen_bench_input.py\n"]
    for i in range(n):
        parts.append(TMPL.format(i=i))
    parts.append("\ndef main():\n    total: int = 0\n")
    for i in range(0, n, 100):
        parts.append(f"    total = total + fn_{i}(1, 2, \"a\")\n")
    parts.append("    print(total)\n")
    text = "".join(parts)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{out}: {len(text)} 字符 / {n} 个函数")


if __name__ == "__main__":
    main()
