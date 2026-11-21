# lambda / 一等函数：赋值、传参、回调、列表里存函数、for 迭代调用。
def apply1(f, x: int) -> int:
    return f(x)

def compose(f, g, x: int) -> int:
    return f(g(x))

def main():
    inc = lambda v: v + 1
    dbl = lambda v: v * 2
    print(inc(4), dbl(4), apply1(inc, 10))
    print(compose(inc, dbl, 5))
    fs = [inc, dbl]
    for f in fs:
        print(f(100))
    print(fs[0](7), fs[1](7))
