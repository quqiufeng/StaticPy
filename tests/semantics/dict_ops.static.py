# dict：赋值/取值/缺键默认/键值项遍历/删除/嵌套/长度。
def main():
    d = {}
    d["a"] = 1
    d["b"] = 2
    print(len(d), d["a"])
    print(d.get("a"), d.get("zz"), d.get("zz", -1))
    d["a"] = 10
    print(d["a"])
    keys = sorted(d.keys())
    print(keys)
    for k in keys:
        print(k, d[k])
    e = {"x": [1, 2], "y": {"z": 3}}
    print(e["x"][1], e["y"]["z"])
    print("a" in d, "q" in d)
    del d["b"]
    print(len(d), sorted(d.keys()))
