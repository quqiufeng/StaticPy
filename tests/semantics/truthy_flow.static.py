def main():
    x = None
    # 条件真值：None 为假（bool() 显式求真值；条件表达式本身要 bool）
    if bool(x):
        print("x 真")
    else:
        print("x 假")

    # 空串/0/空列表/空字典/None 都是假，非空都是真
    empties = ["", 0, [], {}, None, "非空", 1]
    for v in empties:
        print(bool(v))

    # 布尔 and / or：None 参与时按 CPython 真值
    print(bool(x) or bool("非空"))
    print(bool(x) and bool("非空"))
    print(not x)
    print(x is None)
