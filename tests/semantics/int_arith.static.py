# 整数算术：// % / 的负数行为（Python 是向下取整/取模跟随除数符号）、**、精确大整数。
# 守住的核心点：StaticPy 若用 fx/ 或 C 的截断除法，-7//2 会出 -3（Python 是 -4）。
def main():
    print(7 // 2, 7 % 2, 7 / 2)
    print(-7 // 2, -7 % 2)
    print(7 // -2, 7 % -2)
    print(-7 // -2, -7 % -2)
    for a in [-9, -4, -1, 0, 1, 4, 9]:
        for b in [-3, -2, 3]:
            print(a, b, a // b, a % b)
    print(2 ** 10, 2 ** 0, 3 ** 5)
    print(2 ** 70, 10 ** 20, -(2 ** 64))
    print((2 ** 70) // (2 ** 63), (2 ** 70) % 7)
    print(divmod(17, 5) if False else (17 // 5, 17 % 5))
