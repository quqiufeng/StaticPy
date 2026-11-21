# expect: build-error f-string 的格式说明
# {x:>5} / {x:.2f} 尚未实现 —— 必须构建期响亮失败，不许静默丢掉格式说明
def main():
    n = 42
    print(f"[{n:>5}]")
