# FFI 往返基准：每次迭代 = 一次 foreign-procedure 调用（StaticPy → libm → 回）
# 用途：把「跨 C ABI 的调用开销」变成可复现的数字，防止 FFI 层劣化无人发现。
# 跑法：STATICPY_LIB_M=libm.so.6 bash staticpy/static_build.sh 本文件 ffi_bench
extern fn sqrt(x: float) -> float from "m"

N = 2000000

def main():
    i: int = 0
    s: float = 0.0
    while i < N:
        s = s + sqrt(2.0)
        i = i + 1
    print(s)
