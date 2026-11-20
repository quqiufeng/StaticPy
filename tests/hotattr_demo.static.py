# hotattr_demo.static.py — hotattr 自测：长跑循环，供外部采样归因


def burn(n: int) -> int:
    a: int = 0
    i: int = 0
    while i < n:
        a = a + (i * 8 + i) % 7919
        i = i + 1
    return a


def main() -> None:
    total: int = 0
    r: int = 0
    while r < 200:
        total = total + burn(3000000)
        r = r + 1
    print(str(total))
