# enum：编译成顶层常量（Color.RED -> Color_RED）
# 成员取值、.name / .value、相等比较都能对齐；`print(Color.RED)` 与把成员存进变量后
# 再取 .name 是已知偏差（详见 docs/LANGUAGE.md），用例只钉住编译期可解析的形态。
from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


def main():
    print(Color.RED.name, Color.RED.value)
    print(Color.GREEN.name, Color.GREEN.value)
    print(Color.RED == Color.RED, Color.RED == Color.GREEN)
    print(Color.BLUE.value * 10)
    if Color.RED.value == 1:
        print("one")
    print(via_var())


def via_var() -> int:
    c = Color.GREEN
    return c.value
