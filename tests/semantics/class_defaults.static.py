class Q:
    kind: int = 7
    tag = "hi"

    def __init__(self, n: int):
        self.n = n

    def label(self) -> str:
        return self.tag


class R:
    size = 3


class A:
    k: int = 1

    def who(self) -> str:
        return "A"


class B(A):
    k: int = 2

    def who(self) -> str:
        return "B"


def main():
    q = Q(3)
    print(q.n, q.kind, q.tag, q.label())
    r = R()
    print(r.size)
    b = B()
    a = A()
    print(b.k, b.who(), a.k, a.who())
