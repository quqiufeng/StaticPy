# 枚举成员存进变量后取 .name：需要反向查表，构建期大声失败（不静默出 (ir-field …) 崩）
# expect: build-error 枚举成员变量取 .name 尚未支持
from enum import Enum


class Color(Enum):
    RED = 1


def main():
    c = Color.RED
    print(c.name)
