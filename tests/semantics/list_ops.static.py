# list 容器：append/pop/insert/extend/sort/reverse/index/count + 切片 + 迭代 + 嵌套。
def main():
    a = [3, 1, 2]
    a.append(9)
    print(a)
    a.sort()
    print(a)
    a.reverse()
    print(a)
    print(a.pop(), a)
    a.insert(1, 5)
    print(a, a.index(5), a.count(2))
    a.extend([7, 7])
    print(a, len(a))
    b = a[1:3]
    print(b)
    c = []
    for x in [1, 2, 3]:
        c.append(x * x)
    print(c, sum(c), min(c), max(c), sorted(c, reverse=True))
    d = [[1, 2], [3, 4]]
    print(d[1][0], len(d))
    e = [x * 2 for x in range(4)]
    print(e)
    f = list()
    f.append(2)
    f.append(1)
    f.sort()
    print(f, len(f), f == [1, 2], f == [])
    g = list([4, 5])
    g.insert(0, 3)
    print(g, g.pop(0), g)
    h = list()
    h.extend("ab")
    h += ["c"]
    print(h, h.count("a"))
