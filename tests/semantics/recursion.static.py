# 递归：阶乘/斐波那契/互递归/深度累加，守住尾调用与栈行为一致。
def fact(n: int) -> int:
    if n <= 1:
        return 1
    return n * fact(n - 1)

def fib(n: int) -> int:
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

def is_even(n: int) -> bool:
    if n == 0:
        return True
    return is_odd(n - 1)

def is_odd(n: int) -> bool:
    if n == 0:
        return False
    return is_even(n - 1)

def main():
    print(fact(10))
    print(fib(15))
    print(is_even(10), is_odd(10))
    s = 0
    for i in range(100):
        s = s + i
    print(s)
