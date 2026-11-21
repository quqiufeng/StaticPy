# 字符串：切分/去空白/查找/大小写/切片/关系/重复——守住 str 方法落到预置过程的名字与语义。
def main():
    s = "  Hello, StaticPy  "
    print(s.strip())
    print(s.upper())
    print(s.lower())
    print("a,b,,c".split(","))
    print("-".join(["x", "y", "z"]))
    t = "hello world"
    print(t[0], t[-1], t[0:5], t[6:], t[:5])
    print(len(t), "world" in t, "nope" in t)
    print(t.find("world"), t.replace("world", "there"))
    print("abc" * 3, "ab" < "b", "Ab" == "ab")
    print(str(7) + "-x")   # %-格式化尚未支持（构建期响亮报错），这里走 str()+拼接
    for ch in "abc":
        print(ch)
