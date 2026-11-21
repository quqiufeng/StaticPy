# %-格式化：CPython 语义（%s/%r/%d/%f/%x/%o、宽度、精度、标志、%%）。
def main():
    a = 7
    b = "ok"
    print("%d-%s" % (a, b))
    print("%05d|%-5d|%5d|" % (42, 42, 42))
    print("%.2f %s %x" % (3.14159, "y", 255))
    print("%s" % "abc", "%r" % "q")
    print("%+d % d" % (5, 5))
    print("%3.1f|%.3s|%o|%X" % (2.0, "abcdef", 8, 255))
    print("100%% done %s" % b)
    print("%s" % 3.5, "%d" % 3.9, "%f" % 1)
    s = "n=%d" % a
    print(s, len(s))
