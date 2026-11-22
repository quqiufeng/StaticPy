# 回归：for 头的四种可迭代形态（曾静默丢循环 / 静默给错值）
#   1) for ch in "abc"  -> 元素是「1 字符 str」，可拼接、可比较
#   2) for k in {"x": 1} -> 字面量 dict 迭代键（曾整体消失）
#   3) for k in d        -> dict 变量迭代键（曾按长度循环但每轮给 None）
#   4) for v in f()      -> 任意表达式结果走 py-items

def keys_of(d) -> str:
    s = ""
    for k in d:
        s = s + k
    return s

def main():
    s = ""
    for ch in "py!":
        s = s + ch
    print("1) concat:", s, len(s))

    hits = 0
    for ch in "banana":
        if ch == "a":
            hits = hits + 1
    print("2) a count:", hits)

    lit = ""
    for k in {"x": 1, "y": 2}:
        lit = lit + k
    print("3) literal dict keys:", lit, len(lit))

    d = {"p": 1, "q": 2, "r": 3}
    print("4) var dict keys:", keys_of(d), len(keys_of(d)))

    total = 0
    for v in sorted([3, 1, 2]):
        total = total + v
    print("5) sum(sorted):", total)

    nested = ""
    for row in [[1, 2], [3]]:
        for cell in row:
            nested = nested + str(cell)
    print("6) nested:", nested)

