# 元组：构造/解包/交换/下标/切片/长度/默认返回多值。
def pair(x: int) -> tuple:
    return (x, x * x)

def main():
    t = (1, "two", 3.5)
    print(t, len(t), t[0], t[2])
    a, b = 1, 2
    a, b = b, a
    print(a, b)
    x, y = pair(7)
    print(x, y)
    q, r = divmod(17, 5)
    print(q, r)
    print((1, 2) == (1, 2), (1, 2) < (1, 3))
