# f-string 格式说明：与 PyPI 无关，逐字符对齐 CPython 的 format(v, spec)
def main():
    n = 42
    x = 1.5
    print(f"[{n:>5}]")
    print(f"[{n:<5}][{n:^9}][{n:05}][{n:=+8}]")
    print(f"[{n:#x}][{n:#o}][{n:#b}][{n:,}][{n:_b}]")
    print(f"[{x:.2f}][{x:8.3f}][{x:.0e}][{x:g}][{x:%}]")
    print(f"[{'ab':<6}][{'ab':*>8}][{n!r:>6}]")
    print(f"[{n:}]")
    print(f"[{n!s:>4}]")
