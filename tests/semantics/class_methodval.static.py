class P:
    k: int

    def __init__(self, x: int):
        self.x = x

    def twice(self) -> int:
        return self.x * 2

    def plus(self, d: int) -> int:
        return self.x + d


def apply1(fn, p: P) -> int:
    return fn(p)


def apply2(fn, p: P, d: int) -> int:
    return fn(p, d)


def main():
    p: P = P(3)
    # 方法当值：值是「裸函数」，调用时显式传 self（与 CPython 的 P.twice 一致）
    f = P.twice
    print(f(p))
    # 高阶函数：方法当值传参，形参 fn 不走 static_ 前缀
    print(apply1(P.twice, p))
    print(apply2(P.plus, p, 4))
    # 经类名再取一次（同一份裸函数）：变量类型记 fn，调用点不加 static_ 前缀
    g = P.plus
    print(g(p, 4))
