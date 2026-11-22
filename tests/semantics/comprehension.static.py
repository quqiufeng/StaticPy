# 推导式：list / dict / set，单层 + 多层 for + if 过滤（对齐 CPython 顺序）
def squares(n: int) -> list[int]:
    return [i * i for i in range(n)]


def evens(n: int) -> list[int]:
    return [i for i in range(n) if i % 2 == 0]


def pairs(n: int) -> list[int]:
    return [a * 10 + b for a in range(n) for b in range(2)]


def main():
    print(squares(5))
    print(evens(7))
    print(pairs(3))
    d = {k: k * 2 for k in range(4)}
    print(d[0], d[3])
    s = sorted({x % 3 for x in range(10)})
    print(s)
