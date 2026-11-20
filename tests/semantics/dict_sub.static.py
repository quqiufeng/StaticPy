# 下标语义差分：dict（int/str 键、缺失、覆盖、del）/ list（负数、越界）/ str / tuple-ish
# 目的：守住 py-get / py-set! / py-del! 的"一条 cond 到底"快路与 prelude 原实现等价。


def main():
    d = {}
    for i in range(8):
        d[i] = i * i
    for i in range(8):
        print(i, d[i])

    # 覆盖 + 删除 + 重新插入
    d[3] = -1
    del d[3]
    print("after del:", d.get(3, "gone"))
    d[3] = 999
    print("re-add:", d[3])

    # 字符串键（走 intern id 快路）
    s = {}
    keys = ["alpha", "beta", "gamma", "delta"]
    for k in keys:
        s[k] = len(k)
    for k in keys:
        print(k, s[k])
    del s["beta"]
    print("missing str:", s.get("beta", "gone"), "len:", len(s))

    # 混合：int 键与 str 键共存
    m = {}
    m[1] = "one"
    m["1"] = "uno"
    m[2] = "two"
    print(m[1], m["1"], m[2], len(m))

    # .get 默认值
    print(s.get("gamma", -1), s.get("nope", -1), d.get(4, -1), d.get(99, -1))

    # list：负数/越界/mutation
    a = [10, 20, 30, 40]
    print(a[0], a[3], a[-1], a[-4])
    a[1] = 21
    print(a[1], len(a))
    # 越界下标：Python 抛 IndexError，StaticPy 返回 None（既有分歧，此处不比对）

    # 字符串下标
    t = "staticpy"
    print(t[0], t[-1])

    # 判存在
    print(3 in d, 33 in d, "gamma" in s, "beta" in s)

    # 嵌套结构
    nest = {"rows": [{"v": 1}, {"v": 2}]}
    print(nest["rows"][1]["v"], nest["rows"][0]["v"])

    # 迭代键（顺序敏感：dict 保插入序）
    ks = []
    for k in s:
        ks.append(k)
    print(ks)

    return 0
