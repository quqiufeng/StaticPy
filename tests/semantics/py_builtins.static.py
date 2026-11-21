def main():
    print(pow(2, 10), pow(2, 10, 100), pow(2, -1), pow(3, 0, 7))
    print(round(2.675, 2), round(0.5), round(1.5), round(25.0, -1), round(5))
    print(divmod(7, 2), divmod(-7, 2), divmod(7, -2))
    print("%s" % [1, 2], "%s" % (1,), "%d/%s" % (3, "x"))
    print(abs(-3), abs(-2.5), abs(0))
