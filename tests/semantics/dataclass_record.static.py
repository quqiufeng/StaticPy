# dataclass：编译成 record（字段访问 + 构造 + 不可变字段语义）
# 注意：`p == q` 是 record 身份比较（CPython 是逐字段），`print(p)` 是 record 形式，
# 两条已知偏差写在 docs/LANGUAGE.md；用例只钉住可对齐的部分。
from dataclasses import dataclass


@dataclass
class Point:
    x: int
    y: int


@dataclass
class Rect:
    w: int
    h: int


def area(r: Rect) -> int:
    return r.w * r.h


def main():
    p = Point(3, 4)
    print(p.x, p.y)
    print(p.x * p.x + p.y * p.y)
    r = Rect(2, 5)
    print(area(r))
    r.w = 10
    print(area(r))
