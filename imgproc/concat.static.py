# concat.static.py — 把若干 .static.py 合并成一个 bundle（StaticPy 自举版）
#
# 用法: concat OUT.static.py IN1.static.py IN2.static.py ...
# 规则：去掉 `import` / `from ... import ...` 行（名字由合并后同一作用域提供）；
#      只应有一个文件定义 main()。作为库被集成时把它当构建工具用。

def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 3:
        print("usage: concat OUT IN1 IN2 ...")
        exit_program(1)
    out_path: str = py_list_ref(args, 1)
    bundle: str = ""
    i: int = 2
    while i < n:
        f: str = py_list_ref(args, i)
        fp = file_open(f, "r")
        if fp is not None:
            s: str = file_read_all(fp)
            file_close(fp)
            lines = str_split(s, "\n")
            kept: str = ""
            j: int = 0
            ln_total: int = list_length(lines)
            while j < ln_total:
                ln: str = list_ref(lines, j)
                t: str = str_trim(ln)
                if not (str_starts_with(t, "from ") or str_starts_with(t, "import ")):
                    kept = kept + ln + "\n"
                j = j + 1
            bundle = bundle + "# ==== " + f + " ====\n" + kept + "\n\n"
        i = i + 1
    fpw = file_open(out_path, "w")
    file_write(fpw, bundle)
    file_close(fpw)
    print("concat -> " + out_path)
