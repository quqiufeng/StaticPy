# 条件表达式（三元）：任意位置可用，且分支类型可以不同（不要求两边同型）。
def pick(n: int) -> str:
    return "big" if n > 10 else "small"


def main():
    for n in [0, 5, 11, 100]:
        print(n, pick(n))
    x = 1 if True else 2
    print(x)
    y = 1 if False else 2
    print(y)
    z = 3 if 0 else 4 if 0 else 5
    print(z)
    print(["even", "odd"][3 % 2])
    m = 7
    print(m if m % 2 else -m)
