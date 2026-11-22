# 枚举成员存进变量后取 .name / .value：编译期反向查表（不落 ir-field，运行期不崩）
from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3


def main():
    c = Color.GREEN
    print(c.value, c.name)
    d = Color.RED
    print(d.value, d.name)
    print(second_hand())


def second_hand() -> int:
    a = Color.BLUE
    b = a
    print(b.name, b.value)
    return 0
