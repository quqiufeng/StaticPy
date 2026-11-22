# for 迭代源统一：函数体顶层（lvl=1）曾走 py-iter-seq（py-glist 先整表拷成 vector），
# 现与嵌套块同一条 py-seq-len / py-seq-ref 路径 —— 语义必须完全一致。
def main():
    xs = []
    for i in range(3):
        xs.append(i * 10)
    total = 0
    for v in xs:                 # py-glist 迭代（lvl=1）
        total = total + v
    print(total, xs, len(xs))
    n: int = 0
    for ch in "py!":             # str 常量迭代（另一分支）
        n = n + 1
    print("str-count", n)
    for row in [[1, 2], [3]]:    # 字面 list 迭代 + 内层 Name 迭代
        for v in row:
            print("cell", v)
    ys = []
    for i in range(2):
        ys.append(i)
    acc: int = 0
    for v in ys:                 # 空表之后的 glist 迭代
        acc = acc + v + 1
    print("acc", acc, ys)
