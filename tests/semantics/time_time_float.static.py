# time.time() 语义：CPython 返回带小数的 float 秒（曾实现成整型秒，fl- 会直接抛异常）
import time


def main():
    t1: float = time.time()
    t2: float = time.time()
    print(t1 > 1700000000.0)
    print(t2 >= t1)
    time.sleep(0.05)
    t3: float = time.time()
    print(t3 - t1 > 0.0)
    print(t2 - t1 >= 0.0)
