# 比较与布尔：链式比较只求值一次、and/or 返回操作数（不是 bool）、not 优先于 and/or。
# 守住点：Python 的 and/or 是短路并返回**操作数**；翻成 Scheme 的 and/or 后返回值类型要一致。
def main():
    x = 5
    print(1 < x < 10, 1 < x < 3, x == 5, x != 5)
    print(1 <= x <= 5, 5 >= x >= 1)
    print(True and False, True or False, not True, not 0)
    print(0 or 7, 3 and 4, "" or "dflt", None or "x")
    print(1 and 2 and 3, 0 and 2 and 3, 0 or 0 or 5)
    print(not (1 and 0) or 1)
    a = 3
    b = 3
    print(a is b, a == b, a is not b)
    print(2 in [1, 2], 5 in [1, 2], "a" in {"a": 1}, "z" not in {"a": 1})
