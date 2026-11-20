# normalize_scm.static.py — IR token 规范化的 StaticPy 版
#
# 为什么要这一份：原来的判据是 Python 脚本，于是「校验信任链」这件事本身
# 还要求目标机器有 CPython。判据应当能用被校验的东西自己跑。
#
# 语义与 trust/normalize_scm.py 逐字节一致：同样的 token 序列、同样的
# 分隔（单个空格）、同样以换行结尾。字符串字面量和 #\ 字符字面量原样保留
# ——正是它们让 `sed 's/;.*//'` 那种做法会把「不同 IR」误判成「相同」。
#
# 用法:
#   normalize_scm IN.scm > OUT.norm
#   normalize_scm --eq A.scm B.scm      # 相等则退出码 0

def is_space(c: str) -> bool:
    if c == " " or c == "\t" or c == "\r" or c == "\n":
        return True
    if c == "\v" or c == "\f":
        return True
    return False


def is_delim(c: str) -> bool:
    if is_space(c):
        return True
    if c == "(" or c == ")" or c == "[" or c == "]":
        return True
    if c == '"' or c == ";":
        return True
    return False


def ch(s: str, i: int) -> str:
    return str_slice(s, i, i + 1)


def norm(text: str) -> str:
    n: int = str_length(text)
    i: int = 0
    out: str = ""
    while i < n:
        c: str = ch(text, i)
        if is_space(c):
            i = i + 1
        elif c == ";":
            while i < n and ch(text, i) != "\n":
                i = i + 1
        elif c == '"':
            j: int = i + 1
            buf: str = '"'
            while j < n:
                tj: str = ch(text, j)
                if tj == "\\" and j + 1 < n:
                    buf = buf + str_slice(text, j, j + 2)
                    j = j + 2
                else:
                    buf = buf + tj
                    j = j + 1
                    if tj == '"':
                        break
            out = out + buf + " "
            i = j
        elif c == "#" and i + 1 < n and ch(text, i + 1) == "\\":
            j: int = i + 2
            while j < n and not is_space(ch(text, j)):
                j = j + 1
            out = out + str_slice(text, i, j) + " "
            i = j
        elif c == "(" or c == "[":
            out = out + "( "
            i = i + 1
        elif c == ")" or c == "]":
            out = out + ") "
            i = i + 1
        elif c == "'":
            out = out + "' "
            i = i + 1
        else:
            j: int = i
            while j < n and not is_delim(ch(text, j)):
                j = j + 1
            if j == i:
                j = i + 1
            out = out + str_slice(text, i, j) + " "
            i = j
    m: int = str_length(out)
    if m > 0:
        out = str_slice(out, 0, m - 1)
    return out


def norm_file(path: str) -> str:
    fp = file_open(path, "r")
    if fp is None:
        print("无法打开: " + path)
        exit_program(2)
    s: str = file_read_all(fp)
    file_close(fp)
    return norm(s)


def arg_at(args, k: int) -> str:
    return py_list_ref(args, k)


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    a1: str = ""
    if n > 1:
        a1 = arg_at(args, 1)
    if a1 == "--eq":
        if n != 4:
            print("用法: normalize_scm --eq A B")
            exit_program(2)
        a: str = norm_file(arg_at(args, 2))
        b: str = norm_file(arg_at(args, 3))
        if a == b:
            exit_program(0)
        ta = str_split(a, " ")
        tb = str_split(b, " ")
        la: int = list_length(ta)
        lb: int = list_length(tb)
        k: int = 0
        kmax: int = la
        if lb < la:
            kmax = lb
        shown: int = 0
        while k < kmax:
            x: str = list_ref(ta, k)
            y: str = list_ref(tb, k)
            if x != y:
                print("首个差异 token #" + string_of_int(k) + ": " + x + " != " + y)
                shown = 1
                break
            k = k + 1
        if shown == 0:
            print("前缀相同，长度不同: " + string_of_int(la) + " vs " + string_of_int(lb))
        exit_program(1)
    if n != 2:
        print("用法: normalize_scm IN.scm | --eq A B")
        exit_program(2)
    print(norm_file(a1))
