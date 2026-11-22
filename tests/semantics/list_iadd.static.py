# lst += [x] 是原地 extend（py-list-iadd）：走 concat 会每次整体拷贝，
# 且把 [x] 当成单个元素塞进去（[1, [2]]）
def main():
    acc = sorted([3, 1, 2])
    acc += [9]
    print(acc)
    h = list()
    for ch in "ab":
        h += [ch]
    h += h[0:1]
    print(h)
    n = 0
    xs = [0]
    xs += [1, 2]
    for v in xs:
        n += v
    print(n)
