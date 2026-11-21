# expect: build-error !a
# f-string 的 !a（ascii）转换尚未实现 —— 响亮失败
def main():
    s = "a"
    print(f"{s!a}")
