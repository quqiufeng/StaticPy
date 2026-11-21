# str.format：{} {n} {name} {:spec} 与 f-string 共用同一套格式说明
def main():
    print("{:>5}|{:.2f}|{name}|{}".format(42, 1.5, "x", name="kw"))
    print("{} {} {}".format(1, "b", 3))
    print("{1}{0}{1}".format("a", "b"))
    print("{{}} {{{}}}".format(42))
    print("{:,.2f}".format(1234.5678))
    print("{name!r:>8}".format(name="hi"))
