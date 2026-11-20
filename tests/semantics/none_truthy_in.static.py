def main():
    x = None
    print(bool(x))
    print(x is None)
    print(not x)
    print(bool(0))
    print(bool(""))
    d = {"a": 1, "b": 2}
    print("a" in d)
    print("z" in d)
    print("z" not in d)
    print(1 in [1, 2, 3])
    print(5 in [1, 2, 3])
    print(5 not in [1, 2, 3])
    print("ell" in "hello")
    print("xyz" in "hello")
