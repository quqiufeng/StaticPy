# FFI 往返基准：每次迭代 = 一次 foreign-procedure 调用（StaticPy → libm → 回）
# 走的是**预置名 sqrt**（prelude 里的 libm foreign-procedure），也就是用户实际付的那条路径；
# 不自己写 extern fn sqrt —— 那会与预置名撞名，等于两条 ABI 抢同一个符号。
# 用途：把「跨 C ABI 的调用开销」变成可复现的数字，防止 FFI 层劣化无人发现。
# 跑法：bash tools/bench.sh ffi
N = 2000000

def main():
    i: int = 0
    s: float = 0.0
    while i < N:
        s = s + sqrt(2.0)
        i = i + 1
    print(s)
