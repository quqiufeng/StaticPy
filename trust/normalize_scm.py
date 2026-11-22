#!/usr/bin/env python3
"""normalize_scm.py — Scheme IR 规范化：去注释 + 去空白，只留 token 序列。

为什么不是 `sed 's/;.*//' | tr -s`：字符串字面量里可以含 `;`、`"`、空格，
行级正则会把 `"a;b"` 截断、把 `"a  b"` 折叠 —— 那会把「不同的 IR」误判成「相同」。
所以这里做正经的 token 化：字符串/字符字面量原样保留，其余按 token 比较。

用法：
    python3 trust/normalize_scm.py IN.scm > OUT.norm
    python3 trust/normalize_scm.py --eq A.scm B.scm      # 相等则退出码 0
"""
import sys


def tokens(text):
    """返回 token 列表。

    刻意不用生成器：本文件同时是判据的参考实现，也要求能被 StaticPy 前端解析。
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n\f":
            i += 1
            continue
        if c == ";":                      # 行注释
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == '"':                      # 字符串：含转义，原样输出
            j = i + 1
            buf = ['"']
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j:j + 2]); j += 2; continue
                buf.append(text[j])
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            out.append("".join(buf))
            i = j
            continue
        if c == "#" and i + 1 < n and text[i + 1] == "\\":   # 字符字面量 #\x
            j = i + 2
            while j < n and not text[j].isspace():
                j += 1
            out.append(text[i:j])
            i = j
            continue
        if c in "()[]":
            out.append("(" if c in "([" else ")")
            i += 1
            continue
        if c == "'":                      # quote
            out.append("'")
            i += 1
            continue
        j = i
        while j < n and text[j] not in ' \t\r\n\f()[]";':
            j += 1
        if j == i:                        # 兜底，防死循环
            j = i + 1
        out.append(text[i:j])
        i = j

    return out


def norm(text):
    return " ".join(tokens(text))


def main(argv):
    args = argv[1:]
    if args and args[0] == "--eq":
        if len(args) != 3:
            print("用法: normalize_scm.py --eq A B", file=sys.stderr)
            return 2
        a = norm(open(args[1], encoding="utf-8", errors="replace").read())
        b = norm(open(args[2], encoding="utf-8", errors="replace").read())
        if a == b:
            return 0
        ta, tb = a.split(" "), b.split(" ")
        for k, (x, y) in enumerate(zip(ta, tb)):
            if x != y:
                print("首个差异 token #%d: %r != %r" % (k, x, y), file=sys.stderr)
                break
        else:
            print("前缀相同，长度不同: %d vs %d token" % (len(ta), len(tb)), file=sys.stderr)
        return 1
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.write(norm(open(args[0], encoding="utf-8", errors="replace").read()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
