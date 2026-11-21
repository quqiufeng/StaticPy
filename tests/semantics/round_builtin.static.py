# round()：Python 3 是**四舍六入五取偶**（banker's rounding），且 round(x) 返回 int。
# 守住点：C 的 round() 是远离零取整，2.5 -> 3 是错的；此处逐值钉住。
def main():
    print(round(2.5), round(3.5), round(-2.5), round(-3.5))
    print(round(0.5), round(1.5), round(4.5))
    print(round(2.4), round(2.6), round(-2.4), round(-2.6))
    print(abs(-3), abs(3), abs(-2.5), abs(0))
    print(min(3, 1), max(3, 1), min([4, 2, 9]), max([4, 2, 9]))
    print(sum([1, 2, 3]), sum([1.5, 2.5]), sum([]))
    print(min("abd", "abc"), max("abd", "abc"))
