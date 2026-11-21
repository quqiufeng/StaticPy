# expect: build-error 不支持的顶层 For
# 顶层 for/while/if/try 没有静态语义：必须构建期响亮失败，不能静默丢弃。
def main():
    print("hi")


for i in range(3):
    print(i)
