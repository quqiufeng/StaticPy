# list(x) 必须给可增长的表：曾经发 (as_list x) 造不可变 vector，
# 随后的 insert/pop 静默失效（返回 None，表还是原样）
def main():
    a = list([1, 2])
    a.insert(0, 0)
    a.append(3)
    a.pop()
    print(len(a), a[0], a[1], a[2])
    b = list("abc")
    b.insert(1, "X")
    print(b)
    c = list()
    c.append(1)
    print(c)
