# static_translate.static.py — StaticPy 翻译器的自持版本（用 StaticPy 子集写的编译器）
#
# 目标：把 `static_translate.py`（CPython + ast 模块版）等价重写为 StaticPy 子集程序，
#       从而彻底去掉「翻译器依赖 CPython 前端」这一环。
#
# 结构与旧版一一对应：
#   1) 词法器   tokenize(src)          -> token 列表（缩进敏感，生成 NEWLINE/INDENT/DEDENT）
#   2) 解析器   parse(tokens)          -> AST（dict 表示，节点键与 CPython ast 对齐）
#   3) 类型系统 同旧版（type_from_str / infer_expr_type / common_supertype ...）
#   4) 代码生成 同旧版（emit_expr / emit_stmt / emit_program）
#
# 判据：同一输入，新翻译器产出的 Scheme IR 与旧版逐字节一致（见 selfcheck）。
#
# ========== 常量 ==========

KEYWORDS = [
    "False", "None", "True", "and", "as", "assert", "async", "await",
    "break", "class", "continue", "def", "del", "elif", "else", "except",
    "finally", "for", "from", "global", "if", "import", "in", "is",
    "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
    "while", "with", "yield",
]

def build_kwset():
    d = make_dict()
    for k in KEYWORDS:
        d[k] = 1
    return d

# 关键字集合在模块加载时建一次；in_keywords 由 35 次线性 string=? 降到一次哈希查找
KWSET = build_kwset()

def in_keywords(word: str) -> bool:
    return word in KWSET

# 多字符运算符，长的放前面（前缀匹配）
OPS3 = ["**=", "//=", ">>=", "<<=", "..."]
OPS2 = ["==", "!=", "<=", ">=", "**", "//", "<<", ">>", "+=", "-=", "*=",
        "/=", "%=", "&=", "|=", "^=", "->", ":="]
OPS1 = "+-*/%<>=&|^~(){}[],:.;@"

# ========== 字符工具 ==========

def sl(s: str, a: int, b: int) -> str:
    """安全切片：负下标夹到 0，越界交给 str_slice 截断（省一次 str_length）"""
    if a < 0:
        a = 0
    if b < 0:
        b = 0
    return str_slice(s, a, b)

def ch(s: str, i: int) -> str:
    if i < 0:
        return ""
    if i >= str_length(s):
        return ""
    return str_slice(s, i, i + 1)

def is_digit(c: str) -> bool:
    return str_length(c) == 1 and c >= "0" and c <= "9"

def is_alpha(c: str) -> bool:
    if str_length(c) != 1:
        return False
    if c >= "a" and c <= "z":
        return True
    if c >= "A" and c <= "Z":
        return True
    return c == "_"

def is_alnum(c: str) -> bool:
    return is_alpha(c) or is_digit(c)

def is_space(c: str) -> bool:
    return c == " " or c == "\t" or c == "\r" or c == "\f" or c == "\v"

# ========== token 构造 ==========

def tok(t: str, v: str, line: int, col: int):
    # token = 定长 4 元 vector (类型, 值, 行, 列)：下标取比字符串键 hashtable 便宜一个量级
    return py_list(t, v, line, col)

def tok_type(t):
    return py_list_ref(t, 0)

def tok_value(t):
    return py_list_ref(t, 1)

def tok_line(t):
    return py_list_ref(t, 2)

def tok_col(t):
    return py_list_ref(t, 3)

def tok_startswith(t, prefix: str) -> bool:
    return str_starts_with(tok_value(t), prefix)

def tok_is_op(t, s: str) -> bool:
    return tok_type(t) == "OP" and tok_value(t) == s

def tok_is_name(t, s: str) -> bool:
    return tok_type(t) == "NAME" and tok_value(t) == s
def char_index(c: str) -> int:
    if c == "0":
        return 0
    if c == "1":
        return 1
    if c == "2":
        return 2
    if c == "3":
        return 3
    if c == "4":
        return 4
    if c == "5":
        return 5
    if c == "6":
        return 6
    if c == "7":
        return 7
    if c == "8":
        return 8
    if c == "9":
        return 9
    return -1

def hex_value(c: str) -> int:
    d = char_index(c)
    if d >= 0:
        return d
    low = str_lower(c)
    if low == "a":
        return 10
    if low == "b":
        return 11
    if low == "c":
        return 12
    if low == "d":
        return 13
    if low == "e":
        return 14
    if low == "f":
        return 15
    return -1

def strip_underscores(s: str) -> str:
    return str_replace(s, "_", "")

def parse_int_base(s: str, base: int) -> int:
    v: int = 0
    i: int = 0
    n: int = str_length(s)
    while i < n:
        c = ch(s, i)
        d = hex_value(c)
        if d >= 0 and d < base:
            v = v * base + d
        else:
            # 遇到非法字符（如 0x 后的 'x' 已剥离，这里不会命中非法的）
            pass
        i = i + 1
    return v

def number_value(text: str, isfloat: bool):
    s = strip_underscores(text)
    if isfloat:
        return string_to_float(s)
    if str_length(s) > 2 and s[0:1] == "0":
        p = str_lower(sl(s, 1, 2))
        if p == "x":
            return parse_int_base(sl(s, 2, str_length(s)), 16)
        if p == "o":
            return parse_int_base(sl(s, 2, str_length(s)), 8)
        if p == "b":
            return parse_int_base(sl(s, 2, str_length(s)), 2)
    return string_to_int(s)

# ========== 词法扫描：数字 ==========

def scan_number(src: str, i: int, n: int) -> int:
    """返回数字字面量结束位置。"""
    if i + 1 < n and ch(src, i) == "0":
        p = str_lower(ch(src, i + 1))
        if p == "x" or p == "o" or p == "b":
            j = i + 2
            while j < n and (is_alnum(ch(src, j)) or ch(src, j) == "_"):
                j = j + 1
            return j
    j = i
    while j < n and (is_digit(ch(src, j)) or ch(src, j) == "_"):
        j = j + 1
    if j < n and ch(src, j) == ".":
        if j + 1 < n and is_digit(ch(src, j + 1)):
            j = j + 1
            while j < n and (is_digit(ch(src, j)) or ch(src, j) == "_"):
                j = j + 1
        elif j + 1 >= n or not is_alpha(ch(src, j + 1)):
            j = j + 1
    if j < n and (ch(src, j) == "e" or ch(src, j) == "E"):
        k = j + 1
        if k < n and (ch(src, k) == "+" or ch(src, k) == "-"):
            k = k + 1
        if k < n and is_digit(ch(src, k)):
            j = k
            while j < n and (is_digit(ch(src, j)) or ch(src, j) == "_"):
                j = j + 1
    return j

def number_is_float(text: str) -> bool:
    if str_contains(text, "."):
        return True
    low = str_lower(text)
    if str_contains(low, "e") and not str_starts_with(low, "0x"):
        return True
    return False

# ========== 词法扫描：字符串 ==========

def scan_string(src: str, i: int, n: int) -> int:
    """i 指向开引号；返回闭引号之后的位置（容错到行尾/文件尾）。"""
    q = ch(src, i)
    triple = False
    if i + 2 < n and ch(src, i + 1) == q and ch(src, i + 2) == q:
        triple = True
        j = i + 3
    else:
        j = i + 1
    while j < n:
        c = ch(src, j)
        if c == "\\":
            j = j + 2
        else:
            if triple == True:
                if c == q and j + 2 < n and ch(src, j + 1) == q and ch(src, j + 2) == q:
                    return j + 3
                j = j + 1
            else:
                if c == q:
                    return j + 1
                if c == "\n":
                    return j
                j = j + 1
    return n

def string_body(src: str, i: int, j: int) -> str:
    """取 [i,j) 之间的引号内正文。"""
    q = ch(src, i)
    triple = False
    if i + 2 < j and ch(src, i + 1) == q and ch(src, i + 2) == q:
        triple = True
        start = i + 3
    else:
        start = i + 1
    if triple == True:
        if str_length(src) >= j and j >= 3 and ch(src, j - 1) == q and ch(src, j - 2) == q and ch(src, j - 3) == q:
            end = j - 3
        else:
            end = j
    else:
        if j > start and ch(src, j - 1) == q:
            end = j - 1
        else:
            end = j
    return sl(src, start, end)

def read_hex4(s: str, start: int) -> int:
    v: int = 0
    k: int = 0
    while k < 4:
        d = hex_value(ch(s, start + k))
        if d < 0:
            return v
        v = v * 16 + d
        k = k + 1
    return v

def decode_escapes(s: str) -> str:
    out = ""
    i: int = 0
    n: int = str_length(s)
    while i < n:
        c = ch(s, i)
        if c == "\\" and i + 1 < n:
            e = ch(s, i + 1)
            if e == "n":
                out = out + "\n"
                i = i + 2
            elif e == "t":
                out = out + "\t"
                i = i + 2
            elif e == "r":
                out = out + "\r"
                i = i + 2
            elif e == "a":
                out = out + integer_to_char(7)
                i = i + 2
            elif e == "b":
                out = out + integer_to_char(8)
                i = i + 2
            elif e == "f":
                out = out + integer_to_char(12)
                i = i + 2
            elif e == "v":
                out = out + integer_to_char(11)
                i = i + 2
            elif e == "\\":
                out = out + "\\"
                i = i + 2
            elif e == "'":
                out = out + "'"
                i = i + 2
            elif e == "\"":
                out = out + "\""
                i = i + 2
            elif e == "0":
                out = out + integer_to_char(0)
                i = i + 2
            elif e == "x" and i + 3 < n and hex_value(ch(s, i + 2)) >= 0 and hex_value(ch(s, i + 3)) >= 0:
                hv = hex_value(ch(s, i + 2)) * 16 + hex_value(ch(s, i + 3))
                out = out + integer_to_char(hv)
                i = i + 4
            elif e == "u" and i + 5 < n:
                out = out + integer_to_char(read_hex4(s, i + 2))
                i = i + 6
            elif e == "\n":
                i = i + 2
            else:
                # 未知转义：CPython 保留反斜杠（只发 DeprecationWarning）
                out = out + "\\" + e
                i = i + 2
        else:
            out = out + c
            i = i + 1
    return out

def prefix_is_raw(p: str) -> bool:
    low = str_lower(p)
    return str_contains(low, "r")

def prefix_is_fstring(p: str) -> bool:
    low = str_lower(p)
    return str_contains(low, "f")

def prefix_is_bytes(p: str) -> bool:
    low = str_lower(p)
    return str_contains(low, "b")

def is_string_prefix(p: str) -> bool:
    low = str_lower(p)
    if low == "r" or low == "b" or low == "f" or low == "u":
        return True
    if low == "rb" or low == "br" or low == "fr" or low == "rf":
        return True
    return False
# ========== 缩进宽度（tab 展开到 8 的倍数） ==========

def indent_width(src: str, start: int, stop: int) -> int:
    w: int = 0
    i: int = start
    while i < stop:
        c = ch(src, i)
        if c == "\t":
            w = w - (w % 8) + 8
        else:
            w = w + 1
        i = i + 1
    return w

def count_newlines(s: str) -> int:
    cnt: int = 0
    i: int = 0
    n: int = str_length(s)
    while i < n:
        if ch(s, i) == "\n":
            cnt = cnt + 1
        i = i + 1
    return cnt

def index_after_last_newline(src: str, start: int, stop: int) -> int:
    last: int = -1
    i: int = start
    while i < stop:
        if ch(src, i) == "\n":
            last = i
        i = i + 1
    if last < 0:
        return -1
    return last + 1

def list_drop_last(l):
    return py_list_slice(l, 0, list_length(l) - 1)

def last_token_type(toks) -> str:
    if list_length(toks) == 0:
        return ""
    return tok_type(list_ref(toks, list_length(toks) - 1))

# ========== 词法器主循环 ==========

def tokenize(src: str):
    toks = py_list()
    n: int = str_length(src)
    i: int = 0
    line: int = 1
    line_start: int = 0
    pending_newline: bool = False
    need_indent: bool = True
    depth: int = 0
    indents = py_list()
    indents = py_list_append(indents, 0)

    while i < n:
        c = ch(src, i)

        if c == "\n":
            if depth == 0:
                pending_newline = True
            i = i + 1
            line = line + 1
            line_start = i
            continue

        if is_space(c):
            i = i + 1
            continue

        if c == "#":
            while i < n and ch(src, i) != "\n":
                i = i + 1
            continue

        if c == "\\" and i + 1 < n and ch(src, i + 1) == "\n":
            i = i + 2
            line = line + 1
            line_start = i
            continue

        # ---- 到这里是逻辑行的第一个有效字符：处理 NEWLINE / INDENT / DEDENT ----
        if depth == 0:
            if pending_newline:
                if list_length(toks) > 0:
                    lt = last_token_type(toks)
                    if lt != "NEWLINE" and lt != "INDENT":
                        toks = py_list_append(toks, tok("NEWLINE", "", line, 0))
                pending_newline = False
                need_indent = True
            if need_indent and list_length(toks) > 0:
                w: int = indent_width(src, line_start, i)
                top = list_ref(indents, list_length(indents) - 1)
                if w > top:
                    indents = py_list_append(indents, w)
                    toks = py_list_append(toks, tok("INDENT", string_of_int(w), line, 0))
                else:
                    while list_length(indents) > 1 and list_ref(indents, list_length(indents) - 1) > w:
                        indents = list_drop_last(indents)
                        toks = py_list_append(toks, tok("DEDENT", "", line, 0))
            # 关键：首个 token（toks 为空）之后也必须清掉 need_indent，否则同一行内会误发 INDENT
            need_indent = False

        col: int = i - line_start

        # ---- 标识符 / 关键字 / 带前缀的字符串 ----
        if is_alpha(c):
            j = i
            while j < n and is_alnum(ch(src, j)):
                j = j + 1
            word = sl(src, i, j)
            if j < n and (ch(src, j) == "\"" or ch(src, j) == "'") and is_string_prefix(word):
                k = scan_string(src, j, n)
                body = string_body(src, j, k)
                val = body
                if not prefix_is_raw(word):
                    val = decode_escapes(body)
                kind = "STRING"
                if prefix_is_fstring(word):
                    kind = "FSTRING"
                elif prefix_is_bytes(word):
                    kind = "BYTES"
                toks = py_list_append(toks, tok(kind, val, line, col))
                nl = count_newlines(sl(src, j, k))
                if nl > 0:
                    line = line + nl
                    after = index_after_last_newline(src, j, k)
                    if after >= 0:
                        line_start = after
                        col = k - line_start
                i = k
            else:
                tk = "NAME"
                if in_keywords(word):
                    tk = "KEYWORD"
                toks = py_list_append(toks, tok(tk, word, line, col))
                i = j
            continue

        # ---- 数字 ----
        if is_digit(c) or (c == "." and i + 1 < n and is_digit(ch(src, i + 1))):
            j = scan_number(src, i, n)
            text = sl(src, i, j)
            if j < n and is_alpha(ch(src, j)):
                # 数字后紧跟字母：吞掉（如 1j、0x1f 已处理）
                while j < n and is_alnum(ch(src, j)):
                    j = j + 1
                text = sl(src, i, j)
            toks = py_list_append(toks, tok("NUMBER", text, line, col))
            i = j
            continue

        # ---- 字符串字面量（无前缀） ----
        if c == "\"" or c == "'":
            k = scan_string(src, i, n)
            body = string_body(src, i, k)
            toks = py_list_append(toks, tok("STRING", decode_escapes(body), line, col))
            nl = count_newlines(sl(src, i, k))
            if nl > 0:
                line = line + nl
                after = index_after_last_newline(src, i, k)
                if after >= 0:
                    line_start = after
                    col = k - line_start
            i = k
            continue

        # ---- 运算符 / 定界符 ----
        matched = ""
        three = sl(src, i, i + 3)
        for op3 in OPS3:
            if three == op3:
                matched = op3
        if matched == "":
            two = sl(src, i, i + 2)
            for op2 in OPS2:
                if two == op2:
                    matched = op2
        if matched == "":
            one = ch(src, i)
            if str_contains(OPS1, one):
                matched = one
        if matched == "":
            # 未知字符（如 \f、BOM）：跳过
            i = i + 1
            continue
        if matched == "(" or matched == "[" or matched == "{":
            depth = depth + 1
        elif matched == ")" or matched == "]" or matched == "}":
            if depth > 0:
                depth = depth - 1
        toks = py_list_append(toks, tok("OP", matched, line, col))
        i = i + str_length(matched)

    # ---- 收尾 ----
    if pending_newline and list_length(toks) > 0:
        lt = last_token_type(toks)
        if lt != "NEWLINE" and lt != "INDENT":
            toks = py_list_append(toks, tok("NEWLINE", "", line, 0))
    while list_length(indents) > 1:
        indents = list_drop_last(indents)
        toks = py_list_append(toks, tok("DEDENT", "", line, 0))
    toks = py_list_append(toks, tok("ENDMARKER", "", line, 0))
    return toks
