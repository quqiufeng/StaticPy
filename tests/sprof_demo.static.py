# phtest.static.py — sprof 自测：一个热循环 + 一个冷函数


def hot_loop(n: int) -> int:
    a: int = 0
    i: int = 0
    while i < n:
        a = a + i
        i = i + 1
    return a


def cold_tail(n: int) -> int:
    return n + 1


def main() -> None:
    a: int = 0
    k: int = 0
    while k < 300:
        a = a + cold_tail(k)
        k = k + 1
    print(str(hot_loop(400000)))
    print(str(a))
