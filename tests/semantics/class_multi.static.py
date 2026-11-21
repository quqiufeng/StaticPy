class A:
    def __init__(self, n: int):
        self.n = n

    def who(self) -> str:
        return "A"


class B:
    def hi(self) -> str:
        return "B"

    def num(self) -> int:
        return 42


class C(A, B):
    def both(self) -> str:
        return self.hi()


class Named:
    tag: str = "tag"

    def label(self) -> str:
        return self.tag


class Counted:
    def count(self) -> int:
        return 42


class Item(Named, Counted):
    def __init__(self, a: int):
        super().__init__()
        self.a = a


class Base:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class Kid(Base):
    def __init__(self, x: int):
        super().__init__(x, x + 1)
        self.z = 0


def main():
    c = C(5)
    print(c.n, c.who(), c.both(), c.num())
    it = Item(5)
    print(it.a, it.tag, it.label(), it.count())
    k = Kid(4)
    print(k.x, k.y, k.z)
