# __init__ 里的局部变量：必须和普通函数体一样绑成 let 局部变量
# （旧实现一条条 translate_stmt：`k = 2.5` 只发一个裸名 (set! k 2.5)，
#  局部绑定列表被丢掉 → 后续引用 k 就是未绑定变量，构建期才炸）
class Base:
    tag: str

    def __init__(self, tag: str):
        self.tag = tag


class Kid(Base):
    v: float
    n: int

    def __init__(self, seed: float):
        super().__init__("kid")
        k: float = 2.5
        acc = 0.0
        i: int = 0
        while i < 3:
            acc = acc + k
            i = i + 1
        self.v = acc * seed
        self.n = i

    def label(self) -> str:
        m: float = 1.5
        return self.tag + ":" + str(self.v) + "/" + str(self.n) + "/" + str(m)


def main():
    a: Kid = Kid(2.0)
    print(a.tag, a.v, a.n)
    print(a.label())
