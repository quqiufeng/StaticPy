# parse: seed-only  （match 只有种子通道能翻；自举解析器还没这个语法）
# match/case：字面量 / 通配 / 捕获 / | / guard / 序列（含 *rest）/ 映射
# 块内的 match（if/while/for 体里）曾整段编译成注释（静默少跑一段逻辑），一并回归。
def classify(v) -> str:
    match v:
        case 0:
            return "zero"
        case 1 | 2:
            return "small"
        case n if n < 0:
            return "negative"
        case n:
            return "big:" + str(n)
    return "?"


def shape(v) -> str:
    match v:
        case [a, b]:
            return "pair " + str(a) + "," + str(b)
        case [a, *rest]:
            return "head " + str(a) + " rest " + str(len(rest))
        case _:
            return "other"


def main():
    print(classify(0), classify(1), classify(2), classify(-5), classify(9))
    print(shape([1, 2]), shape([1, 2, 3]), shape([]))
    total = 0
    for v in [1, 5, 9]:
        match v:
            case 1:
                total = total + 100
            case _:
                total = total + v
    print(total)
