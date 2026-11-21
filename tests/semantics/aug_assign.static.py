# 增强赋值：+= -= *= //= %= **= &= |= ^= <<= >>=，以及作用在 list/dict/str 上。
# 守住点：翻译成 set! 时右侧必须用原值，且字符串 += 要复制而非原地（不可变）。
def main():
    a = 10
    a += 5
    print(a)
    a -= 3
    print(a)
    a *= 2
    print(a)
    a //= 4
    print(a)
    a %= 4
    print(a)
    a **= 3
    print(a)
    b = 6
    b &= 3
    print(b)
    b |= 8
    print(b)
    b ^= 1
    print(b)
    c = 1
    c <<= 10
    print(c)
    c >>= 4
    print(c)

    s = "ab"
    s += "cd"
    print(s)
    lst = [1]
    lst += [2, 3]
    print(lst)
    d = {}
    d["n"] = 1
    d["n"] += 41
    print(d["n"])
    i = 0
    while i < 5:
        i += 1
    print(i)
