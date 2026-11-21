# f-string 转换符：!r 走 repr、!s 走 str、`{x=}` 自文档（CPython 的 = 就是 !r）
def main():
    s = "a"
    n = 42
    f = 1.5
    print(f"{s!r} {s!s}")
    print(f"{n!r}")
    print(f"{f!r}")
    print(f"{s=} {n=}")
    print(f"{[1, 2]!r}")
    print(f"{None} {True}")
