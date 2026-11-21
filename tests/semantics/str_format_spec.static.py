# expect: runtime-error 暂不支持格式字段
# str.format 的格式说明（:>5 / :.2f）尚未实现 —— 响亮失败
def main():
    print("{:>5}".format(42))
