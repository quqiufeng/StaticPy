# expect: runtime-error 不支持的 %-格式符
# %e 尚未实现 —— 宁可运行期报错，也不要静默算错
def main():
    print("%e" % 1.5)
