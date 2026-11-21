# expect: runtime-error 不支持的 %-格式符
# 不认识的转换符必须响亮失败，不能静默原样吐出
def main():
    print("%z" % 1)
