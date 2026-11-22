# parse_lib.static.py — 第 2 环：tokens -> AST（dict，键与 CPython ast 对齐）
#
# 与 staticpy/static_translate.py 的 ast 用法一一对应：
#   节点 = dict：{"_t": "Name", "id": "x", "ctx": <Load>}
#   None 字段用哨兵 NONE（dump 时还原成 None）
#   Constant 额外带 "_k"：int/float/str/bytes/bool/none/ellipsis（dump 决定字面量形状）
#
# 判据：同一输入，本解析器 dump 出的树与 CPython ast.dump 的规范形逐字节一致
#       （见 staticpy/parse_diff.py / check_parse.sh）。
#
# 约定：本文件是「纯函数库」（无 main），可被 concat 进 static_translate.static.py。

NONE = "\x00N"

# 当前 token 行号槽（1 元素 int 数组）
# 用数组而非普通变量：函数内 `x = ...` 会被翻译成局部 let 绑定，遮蔽模块级全局，
# 于是「在函数里给全局赋值」根本不生效。数组元素变异没有这个问题。
LINE_P = make_int_array(1)

# ========== 节点构造 ==========

def cline() -> int:
    """当前解析位置所在行号（1 起）"""
    return int_array_ref(LINE_P, 0)

def cline_set(v: int) -> int:
    int_array_set(LINE_P, 0, v)
    return 0

def an(t: str):
    d = make_dict()
    dict_set(d, "_t", t)
    # lineno 供代码生成输出 `;; file:line` 注释（与 CPython ast 的 lineno 对应）
    dict_set(d, "lineno", cline())
    return d

def af(d, k: str, v) -> int:
    dict_set(d, k, v)
    return 0

def an0(t: str):
    return an(t)

def a_load():
    return an("Load")

def a_store():
    return an("Store")

def a_del():
    return an("Del")

# ========== token 游标（pos 是 1 元素 int 数组，可原地改） ==========

def tpos_new() -> int:
    p = make_int_array(1)
    int_array_set(p, 0, 0)
    return p

def tcount(toks) -> int:
    return py_list_length(toks)

def tget(toks, p, k: int):
    i: int = int_array_ref(p, 0) + k
    n: int = py_list_length(toks)
    if i >= n:
        i = n - 1
    if i < 0:
        i = 0
    tk = py_list_ref(toks, i)
    if k == 0:
        # 「当前 token」被看一眼就刷新解析位置行号（lookahead 不算）
        int_array_set(LINE_P, 0, tok_line(tk))
    return tk

def tty(toks, p) -> str:
    return tok_type(tget(toks, p, 0))

def tv(toks, p) -> str:
    return tok_value(tget(toks, p, 0))

def tty_at(toks, p, k: int) -> str:
    return tok_type(tget(toks, p, k))

def tv_at(toks, p, k: int) -> str:
    return tok_value(tget(toks, p, k))

def tadv(p) -> int:
    int_array_set(p, 0, int_array_ref(p, 0) + 1)
    return 0

def tpos(p) -> int:
    return int_array_ref(p, 0)

def tset(p, v: int) -> int:
    int_array_set(p, 0, v)
    return 0

def perr(toks, p, msg: str) -> int:
    t = tget(toks, p, 0)
    print("parse error: " + msg + " at line " + string_of_int(tok_line(t)) +
          " col " + string_of_int(tok_col(t)) + " near '" + tok_value(t) + "'")
    exit_program(1)
    return 0

def want_op(toks, p, s: str) -> int:
    tk = tget(toks, p, 0)
    if tok_type(tk) == "OP" and tok_value(tk) == s:
        tadv(p)
        return 0
    perr(toks, p, "expected '" + s + "'")
    return 0

def want_kw(toks, p, s: str) -> int:
    tk = tget(toks, p, 0)
    if tok_type(tk) == "KEYWORD" and tok_value(tk) == s:
        tadv(p)
        return 0
    perr(toks, p, "expected keyword '" + s + "'")
    return 0

def is_op(toks, p, s: str) -> bool:
    tk = tget(toks, p, 0)
    return tok_type(tk) == "OP" and tok_value(tk) == s

def is_kw(toks, p, s: str) -> bool:
    tk = tget(toks, p, 0)
    return tok_type(tk) == "KEYWORD" and tok_value(tk) == s

def is_op_at(toks, p, k: int, s: str) -> bool:
    tk = tget(toks, p, k)
    return tok_type(tk) == "OP" and tok_value(tk) == s

def is_kw_at(toks, p, k: int, s: str) -> bool:
    tk = tget(toks, p, k)
    return tok_type(tk) == "KEYWORD" and tok_value(tk) == s

def skip_newlines(toks, p) -> int:
    while tty(toks, p) == "NEWLINE":
        tadv(p)
    return 0

# ========== 常量 ==========

def mk_const(kind: str, val):
    d = an("Constant")
    af(d, "_k", kind)
    af(d, "value", val)
    af(d, "kind", NONE)
    return d

def mk_const_int(v: int):
    return mk_const("int", v)

def mk_const_str(s: str):
    return mk_const("str", s)

# 数字字面量 -> Constant
def mk_num(text: str):
    t: str = strip_underscores(text)
    low = str_lower(t)
    last = ch(low, str_length(low) - 1)
    if last == "j":
        d = an("Constant")
        af(d, "_k", "complex")
        af(d, "value", sl(low, 0, str_length(low) - 1))
        af(d, "kind", NONE)
        return d
    if number_is_float(t):
        return mk_const("float", string_to_float(t))
    return mk_const_int(number_value(t, False))

# 字符串字面量（相邻拼接在 atom 里处理）
def mk_str_const(val: str):
    return mk_const("str", val)

def mk_bytes_const(val: str):
    return mk_const("bytes", val)

# ========== 表达式：优先级链 ==========
# expr := lambda | ternary
# ternary := or_test ['if' or_test 'else' expr]
# or_test := and_test ('or' and_test)*
# and_test := not_test ('and' not_test)*
# not_test := 'not' not_test | comparison
# comparison := bitor (comp_op bitor)*

def parse_expr(toks, p):
    if is_kw(toks, p, "lambda"):
        return parse_lambda(toks, p)
    return parse_ternary(toks, p)

def parse_lambda(toks, p):
    want_kw(toks, p, "lambda")
    args = parse_lambda_params(toks, p)
    want_op(toks, p, ":")
    body = parse_ternary(toks, p)
    d = an("Lambda")
    af(d, "args", args)
    af(d, "body", body)
    return d

def parse_lambda_params(toks, p):
    pos = py_list()
    defaults = py_list()
    while True:
        if is_op(toks, p, ":"):
            break
        if is_op(toks, p, "/"):
            tadv(p)
            continue
        if is_op(toks, p, "*"):
            tadv(p)
            continue
        if is_op(toks, p, "**"):
            tadv(p)
            tadv(p)
            continue
        if tty(toks, p) == "NAME":
            nm = tv(toks, p)
            tadv(p)
            if is_op(toks, p, "="):
                tadv(p)
                defaults = py_list_append(defaults, parse_ternary(toks, p))
            pos = py_list_append(pos, mk_arg(nm, NONE))
        else:
            break
        if is_op(toks, p, ","):
            tadv(p)
            continue
        break
    d = an("arguments")
    af(d, "posonlyargs", py_list())
    af(d, "args", pos)
    af(d, "vararg", NONE)
    af(d, "kwonlyargs", py_list())
    af(d, "kw_defaults", py_list())
    af(d, "kwarg", NONE)
    af(d, "defaults", defaults)
    return d

def mk_arg(nm: str, ann):
    d = an("arg")
    af(d, "arg", nm)
    af(d, "annotation", ann)
    af(d, "type_comment", NONE)
    return d

def parse_ternary(toks, p):
    body = parse_or(toks, p)
    if is_kw(toks, p, "if"):
        tadv(p)
        test = parse_or(toks, p)
        want_kw(toks, p, "else")
        orelse = parse_expr(toks, p)
        d = an("IfExp")
        af(d, "test", test)
        af(d, "body", body)
        af(d, "orelse", orelse)
        return d
    return body

def parse_or(toks, p):
    first = parse_and(toks, p)
    vals = py_list()
    if is_kw(toks, p, "or"):
        vals = py_list_append(vals, first)
        while is_kw(toks, p, "or"):
            tadv(p)
            vals = py_list_append(vals, parse_and(toks, p))
        d = an("BoolOp")
        af(d, "op", an("Or"))
        af(d, "values", vals)
        return d
    return first

def parse_and(toks, p):
    first = parse_not(toks, p)
    vals = py_list()
    if is_kw(toks, p, "and"):
        vals = py_list_append(vals, first)
        while is_kw(toks, p, "and"):
            tadv(p)
            vals = py_list_append(vals, parse_not(toks, p))
        d = an("BoolOp")
        af(d, "op", an("And"))
        af(d, "values", vals)
        return d
    return first

def parse_not(toks, p):
    if is_kw(toks, p, "not"):
        tadv(p)
        d = an("UnaryOp")
        af(d, "op", an("Not"))
        af(d, "operand", parse_not(toks, p))
        return d
    return parse_cmp(toks, p)

# 比较运算符：返回操作数名字，非比较返回 ""
def cmp_op_at(toks, p) -> str:
    t = tty(toks, p)
    if t == "OP":
        v = tv(toks, p)
        if v == "==":
            return "Eq"
        if v == "!=":
            return "NotEq"
        if v == "<":
            return "Lt"
        if v == "<=":
            return "LtE"
        if v == ">":
            return "Gt"
        if v == ">=":
            return "GtE"
        return ""
    if t == "KEYWORD":
        v = tv(toks, p)
        if v == "in":
            return "In"
        if v == "is":
            if is_kw_at(toks, p, 1, "not"):
                return "IsNot"
            return "Is"
        if v == "not":
            if is_kw_at(toks, p, 1, "in"):
                return "NotIn"
            return ""
    return ""

def parse_cmp(toks, p):
    left = parse_bitor(toks, p)
    ops = py_list()
    rhs = py_list()
    while True:
        nm = cmp_op_at(toks, p)
        if nm == "":
            break
        if nm == "IsNot" or nm == "NotIn":
            tadv(p)
            tadv(p)
        else:
            tadv(p)
        ops = py_list_append(ops, an(nm))
        rhs = py_list_append(rhs, parse_bitor(toks, p))
    if py_list_length(ops) > 0:
        d = an("Compare")
        af(d, "left", left)
        af(d, "ops", ops)
        af(d, "comparators", rhs)
        return d
    return left

def parse_binop_left(toks, p, level: int):
    # level: 0=bor '|', 1=bxor '^', 2=band '&', 3=shift, 4=arith, 5=term
    left = parse_binop_sub(toks, p, level)
    while True:
        tk = tget(toks, p, 0)
        v = tok_value(tk)
        opname = ""
        if tok_type(tk) == "OP":
            if level == 0 and v == "|":
                opname = "BitOr"
            elif level == 1 and v == "^":
                opname = "BitXor"
            elif level == 2 and v == "&":
                opname = "BitAnd"
            elif level == 3:
                if v == "<<":
                    opname = "LShift"
                elif v == ">>":
                    opname = "RShift"
            elif level == 4:
                if v == "+":
                    opname = "Add"
                elif v == "-":
                    opname = "Sub"
            elif level == 5:
                if v == "*":
                    opname = "Mult"
                elif v == "/":
                    opname = "Div"
                elif v == "//":
                    opname = "FloorDiv"
                elif v == "%":
                    opname = "Mod"
                elif v == "@":
                    opname = "MatMult"
        if opname == "":
            break
        tadv(p)
        right = parse_binop_sub(toks, p, level)
        d = an("BinOp")
        af(d, "left", left)
        af(d, "op", an(opname))
        af(d, "right", right)
        left = d
    return left

def parse_binop_sub(toks, p, level: int):
    if level == 0:
        return parse_bitxor(toks, p)
    if level == 1:
        return parse_bitand(toks, p)
    if level == 2:
        return parse_shift(toks, p)
    if level == 3:
        return parse_arith(toks, p)
    if level == 4:
        return parse_term(toks, p)
    return parse_factor(toks, p)

def parse_bitor(toks, p):
    return parse_binop_left(toks, p, 0)

def parse_bitxor(toks, p):
    return parse_binop_left(toks, p, 1)

def parse_bitand(toks, p):
    return parse_binop_left(toks, p, 2)

def parse_shift(toks, p):
    return parse_binop_left(toks, p, 3)

def parse_arith(toks, p):
    return parse_binop_left(toks, p, 4)

def parse_term(toks, p):
    return parse_binop_left(toks, p, 5)

def parse_factor(toks, p):
    if tty(toks, p) == "OP":
        v = tv(toks, p)
        if v == "+" or v == "-" or v == "~":
            tadv(p)
            nm = "UAdd"
            if v == "-":
                nm = "USub"
            elif v == "~":
                nm = "Invert"
            d = an("UnaryOp")
            af(d, "op", an(nm))
            af(d, "operand", parse_factor(toks, p))
            return d
    return parse_power(toks, p)

def parse_power(toks, p):
    base = parse_await(toks, p)
    if is_op(toks, p, "**"):
        tadv(p)
        d = an("BinOp")
        af(d, "left", base)
        af(d, "op", an("Pow"))
        af(d, "right", parse_factor(toks, p))
        return d
    return base

def parse_await(toks, p):
    if is_kw(toks, p, "await"):
        tadv(p)
        d = an("Await")
        af(d, "value", parse_await(toks, p))
        return d
    return parse_primary(toks, p)

# ========== 表达式：primary / atom ==========

def parse_primary(toks, p):
    e = parse_atom(toks, p)
    while True:
        if is_op(toks, p, "("):
            tadv(p)
            d = an("Call")
            af(d, "func", e)
            got = parse_call_args(toks, p)
            af(d, "args", dict_get(got, "args"))
            af(d, "keywords", dict_get(got, "keywords"))
            e = d
            continue
        if is_op(toks, p, "["):
            tadv(p)
            idx = parse_subscript(toks, p)
            d = an("Subscript")
            af(d, "value", e)
            af(d, "slice", idx)
            af(d, "ctx", a_load())
            e = d
            continue
        if is_op(toks, p, "."):
            tadv(p)
            nm = tv(toks, p)
            tadv(p)
            d = an("Attribute")
            af(d, "value", e)
            af(d, "attr", nm)
            af(d, "ctx", a_load())
            e = d
            continue
        break
    return e

def parse_call_args(toks, p):
    args = py_list()
    kws = py_list()
    while not is_op(toks, p, ")"):
        if is_op(toks, p, "*"):
            tadv(p)
            d = an("Starred")
            af(d, "value", parse_expr(toks, p))
            af(d, "ctx", a_load())
            args = py_list_append(args, d)
        elif is_op(toks, p, "**"):
            tadv(p)
            k = an("keyword")
            af(k, "arg", NONE)
            af(k, "value", parse_expr(toks, p))
            kws = py_list_append(kws, k)
        elif is_call_keyword(toks, p):
            nm = tv(toks, p)
            tadv(p)
            tadv(p)
            k = an("keyword")
            af(k, "arg", nm)
            af(k, "value", parse_expr(toks, p))
            kws = py_list_append(kws, k)
        else:
            e0 = parse_expr(toks, p)
            if is_kw(toks, p, "for"):
                g = an("GeneratorExp")
                af(g, "elt", e0)
                af(g, "generators", parse_comp_clauses(toks, p))
                args = py_list_append(args, g)
                break
            args = py_list_append(args, e0)
        if is_op(toks, p, ","):
            tadv(p)
            continue
        break
    want_op(toks, p, ")")
    d = make_dict()
    dict_set(d, "args", args)
    dict_set(d, "keywords", kws)
    return d

def is_call_keyword(toks, p) -> bool:
    if tty(toks, p) != "NAME":
        return False
    return is_op_at(toks, p, 1, "=")

# 下标：a[1] / a[1:2] / a[1:2:3] / a[i, j]
def parse_subscript(toks, p):
    elts = py_list()
    while True:
        elts = py_list_append(elts, parse_sub_one(toks, p))
        if is_op(toks, p, ","):
            tadv(p)
            if is_op(toks, p, "]"):
                break
            continue
        break
    want_op(toks, p, "]")
    if py_list_length(elts) == 1:
        return py_list_ref(elts, 0)
    d = an("Tuple")
    af(d, "elts", elts)
    af(d, "ctx", a_load())
    return d

def parse_sub_one(toks, p):
    lower = NONE
    upper = NONE
    step = NONE
    has_slice = False
    if not is_op(toks, p, ":"):
        lower = parse_expr(toks, p)
    if is_op(toks, p, ":"):
        has_slice = True
        tadv(p)
        if not is_op(toks, p, "]") and not is_op(toks, p, ",") and not is_op(toks, p, ":"):
            upper = parse_expr(toks, p)
        if is_op(toks, p, ":"):
            tadv(p)
            if not is_op(toks, p, "]") and not is_op(toks, p, ","):
                step = parse_expr(toks, p)
    if has_slice:
        d = an("Slice")
        af(d, "lower", lower)
        af(d, "upper", upper)
        af(d, "step", step)
        return d
    if lower == NONE:
        return mk_const("none", NONE)
    return lower

def parse_atom(toks, p):
    t = tty(toks, p)
    v = tv(toks, p)
    if t == "NUMBER":
        tadv(p)
        return mk_num(v)
    if t == "STRING":
        return parse_string_group(toks, p)
    if t == "BYTES":
        return parse_bytes_group(toks, p)
    if t == "FSTRING":
        return parse_fstring_group(toks, p)
    if t == "NAME":
        tadv(p)
        d = an("Name")
        af(d, "id", v)
        af(d, "ctx", a_load())
        return d
    if t == "KEYWORD":
        if v == "True":
            tadv(p)
            return mk_const("bool", 1)
        if v == "False":
            tadv(p)
            return mk_const("bool", 0)
        if v == "None":
            tadv(p)
            return mk_const("none", NONE)
        perr(toks, p, "unexpected keyword in expression")
        return NONE
    if t == "OP":
        if v == "(":
            return parse_paren(toks, p)
        if v == "[":
            return parse_list_display(toks, p)
        if v == "{":
            return parse_dict_display(toks, p)
        if v == "...":
            tadv(p)
            return mk_const("ellipsis", NONE)
    perr(toks, p, "unexpected token in expression")
    return NONE

# ---- 相邻字符串字面量拼接 ----
def parse_string_group(toks, p):
    s = ""
    while tty(toks, p) == "STRING":
        s = s + tv(toks, p)
        tadv(p)
    if tty(toks, p) == "FSTRING":
        # 混合拼接：转成 JoinedStr
        return parse_fstring_mixed(toks, p, mk_const_str(s))
    return mk_str_const(s)

def parse_bytes_group(toks, p):
    s = ""
    while tty(toks, p) == "BYTES":
        s = s + tv(toks, p)
        tadv(p)
    return mk_bytes_const(s)

# ---- 括号：() / (x) / (x, y) / genexp ----
def parse_paren(toks, p):
    want_op(toks, p, "(")
    if is_op(toks, p, ")"):
        tadv(p)
        d = an("Tuple")
        af(d, "elts", py_list())
        af(d, "ctx", a_load())
        return d
    if is_op(toks, p, "yield"):
        perr(toks, p, "yield not supported")
    first = parse_star_or_expr(toks, p)
    if is_kw(toks, p, "for"):
        gens = parse_comp_clauses(toks, p)
        want_op(toks, p, ")")
        d = an("GeneratorExp")
        af(d, "elt", first)
        af(d, "generators", gens)
        return d
    if is_op(toks, p, ","):
        elts = py_list()
        elts = py_list_append(elts, first)
        while is_op(toks, p, ","):
            tadv(p)
            if is_op(toks, p, ")"):
                break
            elts = py_list_append(elts, parse_star_or_expr(toks, p))
        want_op(toks, p, ")")
        d = an("Tuple")
        af(d, "elts", elts)
        af(d, "ctx", a_load())
        return d
    want_op(toks, p, ")")
    return first

def parse_star_or_expr(toks, p):
    if is_op(toks, p, "*"):
        tadv(p)
        d = an("Starred")
        af(d, "value", parse_expr(toks, p))
        af(d, "ctx", a_load())
        return d
    return parse_expr(toks, p)

# ---- 列表显示 / 列表推导 ----
def parse_list_display(toks, p):
    want_op(toks, p, "[")
    if is_op(toks, p, "]"):
        tadv(p)
        d = an("List")
        af(d, "elts", py_list())
        af(d, "ctx", a_load())
        return d
    first = parse_star_or_expr(toks, p)
    if is_kw(toks, p, "for"):
        gens = parse_comp_clauses(toks, p)
        want_op(toks, p, "]")
        d = an("ListComp")
        af(d, "elt", first)
        af(d, "generators", gens)
        return d
    elts = py_list()
    elts = py_list_append(elts, first)
    while is_op(toks, p, ","):
        tadv(p)
        if is_op(toks, p, "]"):
            break
        elts = py_list_append(elts, parse_star_or_expr(toks, p))
    want_op(toks, p, "]")
    d = an("List")
    af(d, "elts", elts)
    af(d, "ctx", a_load())
    return d

# ---- 字典 / 集合显示，字典/集合推导 ----
def parse_dict_display(toks, p):
    want_op(toks, p, "{")
    if is_op(toks, p, "}"):
        tadv(p)
        d = an("Dict")
        af(d, "keys", py_list())
        af(d, "values", py_list())
        return d
    if is_op(toks, p, "**"):
        tadv(p)
        keys = py_list()
        vals = py_list()
        keys = py_list_append(keys, NONE)
        vals = py_list_append(vals, parse_expr(toks, p))
        while is_op(toks, p, ","):
            tadv(p)
            if is_op(toks, p, "}"):
                break
            if is_op(toks, p, "**"):
                tadv(p)
                keys = py_list_append(keys, NONE)
            else:
                keys = py_list_append(keys, parse_expr(toks, p))
                want_op(toks, p, ":")
            vals = py_list_append(vals, parse_expr(toks, p))
        want_op(toks, p, "}")
        d = an("Dict")
        af(d, "keys", keys)
        af(d, "values", vals)
        return d
    first = parse_star_or_expr(toks, p)
    if is_op(toks, p, ":"):
        tadv(p)
        fval = parse_expr(toks, p)
        if is_kw(toks, p, "for"):
            gens = parse_comp_clauses(toks, p)
            want_op(toks, p, "}")
            d = an("DictComp")
            af(d, "key", first)
            af(d, "value", fval)
            af(d, "generators", gens)
            return d
        keys = py_list()
        vals = py_list()
        keys = py_list_append(keys, first)
        vals = py_list_append(vals, fval)
        while is_op(toks, p, ","):
            tadv(p)
            if is_op(toks, p, "}"):
                break
            if is_op(toks, p, "**"):
                tadv(p)
                keys = py_list_append(keys, NONE)
            else:
                keys = py_list_append(keys, parse_expr(toks, p))
                want_op(toks, p, ":")
            vals = py_list_append(vals, parse_expr(toks, p))
        want_op(toks, p, "}")
        d = an("Dict")
        af(d, "keys", keys)
        af(d, "values", vals)
        return d
    if is_kw(toks, p, "for"):
        gens = parse_comp_clauses(toks, p)
        want_op(toks, p, "}")
        d = an("SetComp")
        af(d, "elt", first)
        af(d, "generators", gens)
        return d
    elts = py_list()
    elts = py_list_append(elts, first)
    while is_op(toks, p, ","):
        tadv(p)
        if is_op(toks, p, "}"):
            break
        elts = py_list_append(elts, parse_star_or_expr(toks, p))
    want_op(toks, p, "}")
    d = an("Set")
    af(d, "elts", elts)
    return d

# ---- 推导子句：for tgt in iter [if cond]* （可多段） ----
def parse_comp_clauses(toks, p):
    gens = py_list()
    while is_kw(toks, p, "for"):
        tadv(p)
        tgt = parse_target_list(toks, p)
        want_kw(toks, p, "in")
        it = parse_or(toks, p)
        ifs = py_list()
        while is_kw(toks, p, "if"):
            tadv(p)
            ifs = py_list_append(ifs, parse_or(toks, p))
        d = an("comprehension")
        af(d, "target", tgt)
        af(d, "iter", it)
        af(d, "ifs", ifs)
        af(d, "is_async", 0)
        gens = py_list_append(gens, d)
    return gens

# ========== 赋值目标（Store/Del ctx） ==========

def set_ctx(e, kind: str) -> int:
    tn = dict_get(e, "_t")
    if tn == "Name" or tn == "Attribute" or tn == "Subscript":
        if kind == "D":
            dict_set(e, "ctx", a_del())
        else:
            dict_set(e, "ctx", a_store())
        return 0
    if tn == "Tuple" or tn == "List":
        elts = dict_get(e, "elts")
        i: int = 0
        while i < py_list_length(elts):
            set_ctx(py_list_ref(elts, i), kind)
            i = i + 1
        dict_set(e, "ctx", a_store())
        return 0
    if tn == "Starred":
        set_ctx(dict_get(e, "value"), kind)
        dict_set(e, "ctx", a_store())
        return 0
    return 0

# 目标列表：a, b / (a, b) / [a, b] / a
# 目标原子：不含二元/比较运算（'for b in B' 里的 in 不能被当成比较运算符）
def parse_target_atom(toks, p):
    if is_op(toks, p, "*"):
        tadv(p)
        d = an("Starred")
        af(d, "value", to_target(parse_primary(toks, p)))
        af(d, "ctx", a_store())
        return d
    return to_target(parse_primary(toks, p))

def parse_target_list(toks, p):
    first = parse_target_atom(toks, p)
    if is_op(toks, p, ","):
        elts = py_list()
        elts = py_list_append(elts, first)
        while is_op(toks, p, ","):
            tadv(p)
            if is_target_end(toks, p):
                break
            elts = py_list_append(elts, parse_target_atom(toks, p))
        d = an("Tuple")
        af(d, "elts", elts)
        af(d, "ctx", a_store())
        return d
    return first

def is_target_end(toks, p) -> bool:
    if is_kw(toks, p, "in"):
        return True
    if tty(toks, p) == "NEWLINE":
        return True
    if is_op(toks, p, ":"):
        return True
    if is_op(toks, p, "="):
        return True
    if is_op(toks, p, ")"):
        return True
    return False

def to_target(e):
    set_ctx(e, "S")
    return e

# ========== f-string ==========

def parse_fstring_group(toks, p):
    parts = py_list()
    while tty(toks, p) == "STRING" or tty(toks, p) == "FSTRING":
        if tty(toks, p) == "STRING":
            parts = add_fconst(parts, tv(toks, p))
        else:
            parts = parse_fbody_into(parts, tv(toks, p))
        tadv(p)
    d = an("JoinedStr")
    af(d, "values", parts)
    return d

def parse_fstring_mixed(toks, p, prefix_const):
    parts = py_list()
    parts = py_list_append(parts, prefix_const)
    return parse_fstring_group(toks, p)

def add_fconst(parts, s: str):
    if s == "":
        return parts
    n: int = py_list_length(parts)
    if n > 0:
        last = py_list_ref(parts, n - 1)
        if dict_get(last, "_t") == "Constant":
            merged = dict_get(last, "value") + s
            dict_set(last, "value", merged)
            return parts
    return py_list_append(parts, mk_const_str(s))

# 把 f-string 正文拆成 Constant / FormattedValue 片段
def parse_fbody_into(parts, body: str):
    n: int = str_length(body)
    i: int = 0
    lit: str = ""
    while i < n:
        c = ch(body, i)
        if c == "{":
            if ch(body, i + 1) == "{":
                lit = lit + "{"
                i = i + 2
                continue
            if lit != "":
                parts = add_fconst(parts, lit)
                lit = ""
            j = find_fbrace_end(body, i + 1, n)
            inner = sl(body, i + 1, j)
            sub = parse_fvalue(inner)
            k2: int = 0
            while k2 < py_list_length(sub):
                el = py_list_ref(sub, k2)
                # `f"{x=} {y=}"`：自文档那段 Constant 要与前面的字面量合并成一段，
                # CPython 的 ast 里就是 Constant(" y=") 而不是 Constant(" ") + Constant("y=")
                if dict_get(el, "_t") == "Constant":
                    parts = add_fconst(parts, dict_get(el, "value"))
                else:
                    parts = py_list_append(parts, el)
                k2 = k2 + 1
            i = j + 1
            continue
        if c == "}":
            if ch(body, i + 1) == "}":
                lit = lit + "}"
                i = i + 2
                continue
            i = i + 1
            continue
        lit = lit + c
        i = i + 1
    if lit != "":
        parts = add_fconst(parts, lit)
    return parts

# 从表达式正文里找到配对的 '}'（跳过嵌套括号与字符串）
def find_fbrace_end(body: str, i: int, n: int) -> int:
    depth: int = 0
    q: str = ""
    j: int = i
    while j < n:
        c = ch(body, j)
        if q != "":
            if c == "\\":
                j = j + 2
                continue
            if c == q:
                q = ""
            j = j + 1
            continue
        if c == "\"" or c == "'":
            q = c
            j = j + 1
            continue
        if c == "(" or c == "[" or c == "{":
            depth = depth + 1
            j = j + 1
            continue
        if c == ")" or c == "]" or c == "}":
            if depth == 0 and c == "}":
                return j
            depth = depth - 1
            j = j + 1
            continue
        j = j + 1
    return n

# 单个 {expr[!conv][:spec]} 正文 -> FormattedValue
def parse_fvalue(inner: str):
    expr_text = inner
    conv: int = -1
    spec = NONE
    selfdoc: str = ""
    # 顶层找 '!' 和 ':'（跳过括号/字符串）
    cut = find_ftop(inner)
    if cut >= 0:
        expr_text = sl(inner, 0, cut)
        rest = sl(inner, cut, str_length(inner))
        c0 = ch(rest, 0)
        if c0 == "!":
            cv = ch(rest, 1)
            if cv == "s":
                conv = 115
            elif cv == "r":
                conv = 114
            elif cv == "a":
                conv = 97
            rest = sl(rest, 2, str_length(rest))
        if str_starts_with(rest, ":"):
            spec = build_spec(sl(rest, 1, str_length(rest)))
    if str_ends_with(expr_text, "="):
        # `f"{x=}"` 自文档：CPython 的 ast 把源码原文（含 '='，含空白）放进 Constant，
        # 即 Constant("x=") + FormattedValue(x, conversion=114)；不能再补一个 '='
        selfdoc = expr_text
        expr_text = sl(expr_text, 0, str_length(expr_text) - 1)
        if conv < 0:
            conv = 114

    e = parse_expr_text(expr_text)
    d = an("FormattedValue")
    af(d, "value", e)
    af(d, "conversion", conv)
    af(d, "format_spec", spec)
    out = py_list()
    if selfdoc != "":
        out = py_list_append(out, mk_const_str(selfdoc))
    out = py_list_append(out, d)
    return out

def build_spec(text: str):
    parts = py_list()
    parts = parse_fbody_into(parts, text)
    d = an("JoinedStr")
    af(d, "values", parts)
    return d

# 返回顶层 '!' 或 ':' 的下标，没有返回 -1
def find_ftop(s: str) -> int:
    n: int = str_length(s)
    depth: int = 0
    q: str = ""
    i: int = 0
    while i < n:
        c = ch(s, i)
        if q != "":
            if c == "\\":
                i = i + 2
                continue
            if c == q:
                q = ""
            i = i + 1
            continue
        if c == "\"" or c == "'":
            q = c
            i = i + 1
            continue
        if c == "(" or c == "[" or c == "{":
            depth = depth + 1
            i = i + 1
            continue
        if c == ")" or c == "]" or c == "}":
            depth = depth - 1
            i = i + 1
            continue
        if c == "!" and ch(s, i + 1) == "=":
            i = i + 2
            continue
        if depth == 0 and (c == "!" or c == ":"):
            return i
        i = i + 1
    return -1

# 源码片段 -> 表达式节点
def parse_expr_text(text: str):
    toks = tokenize(text + "\n")
    p = tpos_new()
    skip_newlines(toks, p)
    if tty(toks, p) == "INDENT":
        tadv(p)
    e = parse_testlist(toks, p)
    return e

# 表达式列表（元组可省括号）：a, b, c
def parse_testlist(toks, p):
    first = parse_star_or_expr(toks, p)
    if is_op(toks, p, ","):
        elts = py_list()
        elts = py_list_append(elts, first)
        while is_op(toks, p, ","):
            tadv(p)
            if is_testlist_end(toks, p):
                break
            elts = py_list_append(elts, parse_star_or_expr(toks, p))
        d = an("Tuple")
        af(d, "elts", elts)
        af(d, "ctx", a_load())
        return d
    return first

def is_testlist_end(toks, p) -> bool:
    t = tty(toks, p)
    if t == "NEWLINE" or t == "ENDMARKER" or t == "DEDENT":
        return True
    if is_op(toks, p, "="):
        return True
    if is_op(toks, p, ")"):
        return True
    if is_op(toks, p, "]"):
        return True
    if is_op(toks, p, "}"):
        return True
    if is_op(toks, p, ":"):
        return True
    return False

# ========== extern fn 声明（FFI 绑定，非 Python 语法） ==========
#   extern fn <名字>(<参数: 类型>) -> <返回类型> from "<库名>"
# 旧翻译器（static_translate.py:parse_extern_functions）先用正则把这类行剥掉，
# 再交给 CPython ast。自举前端在 token 层做同样的事：整条声明被跳过（不产生
# 语句，行号不变），声明本身记进 EXTERN_DECLS，供 emit_lib 生成
# `load-shared-object` + `foreign-procedure`（对应 generate_extern_ffi）。
EXTERN_DECLS = make_dict()
dict_set(EXTERN_DECLS, "_n", 0)

def extern_count() -> int:
    return dict_get(EXTERN_DECLS, "_n")

def extern_get(i: int):
    return dict_get(EXTERN_DECLS, "d" + string_of_int(i))

def extern_has(name: str) -> bool:
    """name 是 extern fn 声明过的外部函数吗（命中则调用不加 static_ 前缀）"""
    return dict_get(EXTERN_DECLS, ":" + name) != None

def extern_add(name: str, ret: str, lib: str, params) -> int:
    n: int = dict_get(EXTERN_DECLS, "_n")
    d = make_dict()
    dict_set(d, "name", name)
    dict_set(d, "ret", ret)
    dict_set(d, "lib", lib)
    dict_set(d, "params", params)
    dict_set(EXTERN_DECLS, "d" + string_of_int(n), d)
    dict_set(EXTERN_DECLS, ":" + name, n)
    dict_set(EXTERN_DECLS, "_n", n + 1)
    return 0

def is_extern_at(toks, p) -> bool:
    """当前位置是 extern fn 声明吗（extern 不是 Python 关键字，token 类型是 NAME）"""
    return tv_at(toks, p, 0) == "extern" and tv_at(toks, p, 1) == "fn"

# 跳过一段类型标注（NAME 或 list[...] 之类的泛型下标），返回归一化后的类型名
def skip_ffi_type(toks, p) -> str:
    t: str = tv(toks, p)
    tadv(p)
    if tty(toks, p) == "OP" and tv(toks, p) == "[":
        depth: int = 0
        while tty(toks, p) != "ENDMARKER":
            if is_op(toks, p, "["):
                depth = depth + 1
            elif is_op(toks, p, "]"):
                depth = depth - 1
                tadv(p)
                if depth == 0:
                    return "list"
                continue
            tadv(p)
        return "list"
    return t

def parse_extern_decl(toks, p):
    tadv(p)  # extern
    tadv(p)  # fn
    name: str = tv(toks, p)
    tadv(p)
    want_op(toks, p, "(")
    params = py_list()
    while tty(toks, p) != "ENDMARKER" and not is_op(toks, p, ")"):
        pn: str = tv(toks, p)
        tadv(p)
        pt: str = "float"  # 无标注时的历史默认值（与 parse_extern_functions 一致）
        if is_op(toks, p, ":"):
            tadv(p)
            pt = skip_ffi_type(toks, p)
        pd = make_dict()
        dict_set(pd, "n", pn)
        dict_set(pd, "t", pt)
        params = py_list_append(params, pd)
        if is_op(toks, p, ","):
            tadv(p)
            continue
        break
    want_op(toks, p, ")")
    ret: str = "void"
    if is_op(toks, p, "->"):
        tadv(p)
        ret = skip_ffi_type(toks, p)
    lib: str = ""
    if tv(toks, p) == "from":
        tadv(p)
        lib = tv(toks, p)  # STRING token 的值已去引号
        tadv(p)
    extern_add(name, ret, lib, params)
    if tty(toks, p) == "NEWLINE":
        tadv(p)
    return py_list()

# ========== 语句 ==========

def parse_module(toks):
    p = tpos_new()
    body = py_list()
    skip_newlines(toks, p)
    while tty(toks, p) != "ENDMARKER":
        sts = parse_stmt(toks, p)
        body = py_list_concat(body, sts)
        skip_newlines(toks, p)
    d = an("Module")
    af(d, "body", body)
    af(d, "type_ignores", py_list())
    return d

# 复合语句返回单元素列表，简单语句行可能返回多条（`a = 1; b = 2`）
def parse_stmt(toks, p):
    if is_op(toks, p, "@"):
        return parse_decorated(toks, p)
    if is_extern_at(toks, p):
        return parse_extern_decl(toks, p)
    t = tty(toks, p)
    v = tv(toks, p)
    out = py_list()
    if t == "KEYWORD":
        if v == "if":
            out = py_list_append(out, parse_if(toks, p, 1))
            return out
        if v == "while":
            out = py_list_append(out, parse_while(toks, p))
            return out
        if v == "for":
            out = py_list_append(out, parse_for(toks, p))
            return out
        if v == "def":
            out = py_list_append(out, parse_def(toks, p, py_list()))
            return out
        if v == "class":
            out = py_list_append(out, parse_class(toks, p, py_list()))
            return out
        if v == "try":
            out = py_list_append(out, parse_try(toks, p))
            return out
        if v == "with":
            out = py_list_append(out, parse_with(toks, p))
            return out
        if v == "async":
            perr(toks, p, "async not supported")
    return parse_simple_line(toks, p)

def parse_decorated(toks, p):
    decs = py_list()
    while is_op(toks, p, "@"):
        tadv(p)
        decs = py_list_append(decs, parse_expr(toks, p))
        if tty(toks, p) == "NEWLINE":
            tadv(p)
        skip_newlines(toks, p)
    out = py_list()
    if is_kw(toks, p, "def"):
        out = py_list_append(out, parse_def(toks, p, decs))
    elif is_kw(toks, p, "class"):
        out = py_list_append(out, parse_class(toks, p, decs))
    else:
        perr(toks, p, "expected def/class after decorator")
    return out

def parse_simple_line(toks, p):
    out = py_list()
    out = py_list_append(out, parse_simple_stmt(toks, p))
    while is_op(toks, p, ";"):
        tadv(p)
        if tty(toks, p) == "NEWLINE" or tty(toks, p) == "ENDMARKER":
            break
        out = py_list_append(out, parse_simple_stmt(toks, p))
    if tty(toks, p) == "NEWLINE":
        tadv(p)
    return out

def parse_block(toks, p):
    want_op(toks, p, ":")
    body = py_list()
    if tty(toks, p) == "NEWLINE":
        tadv(p)
        if tty(toks, p) != "INDENT":
            perr(toks, p, "expected INDENT")
        tadv(p)
        skip_newlines(toks, p)
        while tty(toks, p) != "DEDENT" and tty(toks, p) != "ENDMARKER":
            sts = parse_stmt(toks, p)
            body = py_list_concat(body, sts)
            skip_newlines(toks, p)
        if tty(toks, p) == "DEDENT":
            tadv(p)
        return body
    return parse_simple_line(toks, p)

# ---- 简单语句 ----
def parse_simple_stmt(toks, p):
    t = tty(toks, p)
    v = tv(toks, p)
    if t == "KEYWORD":
        if v == "pass":
            tadv(p)
            return an("Pass")
        if v == "break":
            tadv(p)
            return an("Break")
        if v == "continue":
            tadv(p)
            return an("Continue")
        if v == "return":
            tadv(p)
            d = an("Return")
            if tty(toks, p) == "NEWLINE" or is_op(toks, p, ";"):
                af(d, "value", NONE)
            else:
                af(d, "value", parse_testlist(toks, p))
            return d
        if v == "raise":
            tadv(p)
            exc = NONE
            cause = NONE
            if tty(toks, p) != "NEWLINE" and not is_op(toks, p, ";"):
                exc = parse_expr(toks, p)
                if is_kw(toks, p, "from"):
                    tadv(p)
                    cause = parse_expr(toks, p)
            d = an("Raise")
            af(d, "exc", exc)
            af(d, "cause", cause)
            return d
        if v == "assert":
            tadv(p)
            test = parse_expr(toks, p)
            msg = NONE
            if is_op(toks, p, ","):
                tadv(p)
                msg = parse_expr(toks, p)
            d = an("Assert")
            af(d, "test", test)
            af(d, "msg", msg)
            return d
        if v == "global" or v == "nonlocal":
            tadv(p)
            names = py_list()
            names = py_list_append(names, tv(toks, p))
            tadv(p)
            while is_op(toks, p, ","):
                tadv(p)
                names = py_list_append(names, tv(toks, p))
                tadv(p)
            d = an("Global")
            if v == "nonlocal":
                d = an("Nonlocal")
            af(d, "names", names)
            return d
        if v == "del":
            tadv(p)
            tgts = py_list()
            e = parse_expr(toks, p)
            set_ctx(e, "D")
            tgts = py_list_append(tgts, e)
            while is_op(toks, p, ","):
                tadv(p)
                e = parse_expr(toks, p)
                set_ctx(e, "D")
                tgts = py_list_append(tgts, e)
            d = an("Delete")
            af(d, "targets", tgts)
            return d
        if v == "import":
            return parse_import(toks, p)
        if v == "from":
            return parse_import_from(toks, p)
        if v == "yield":
            perr(toks, p, "yield not supported")
    return parse_expr_stmt(toks, p)

AUG_OPS = ["**=", "//=", ">>=", "<<=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "@="]
AUG_NAMES = ["Pow", "FloorDiv", "RShift", "LShift", "Add", "Sub", "Mult", "Div", "Mod", "BitAnd", "BitOr", "BitXor", "MatMult"]

def aug_index(v: str) -> int:
    i: int = 0
    while i < 13:
        if AUG_OPS[i] == v:
            return i
        i = i + 1
    return -1

def parse_expr_stmt(toks, p):
    first = parse_testlist(toks, p)
    if is_op(toks, p, ":"):
        tadv(p)
        ann = parse_expr(toks, p)
        val = NONE
        has_val: int = 0
        if is_op(toks, p, "="):
            tadv(p)
            val = parse_testlist(toks, p)
            has_val = 1
        simple: int = 0
        if dict_get(first, "_t") == "Name":
            simple = 1
        d = an("AnnAssign")
        af(d, "target", to_target(first))
        af(d, "annotation", ann)
        af(d, "value", val)
        af(d, "simple", simple)
        return d
    if tty(toks, p) == "OP":
        ai = aug_index(tv(toks, p))
        if ai >= 0:
            tadv(p)
            d = an("AugAssign")
            af(d, "target", to_target(first))
            af(d, "op", an(AUG_NAMES[ai]))
            af(d, "value", parse_testlist(toks, p))
            return d
    if is_op(toks, p, "="):
        raws = py_list()
        raws = py_list_append(raws, first)
        while is_op(toks, p, "="):
            tadv(p)
            raws = py_list_append(raws, parse_testlist(toks, p))
        n: int = py_list_length(raws)
        tgts = py_list()
        i: int = 0
        while i < n - 1:
            tgts = py_list_append(tgts, to_target(py_list_ref(raws, i)))
            i = i + 1
        d = an("Assign")
        af(d, "targets", tgts)
        af(d, "value", py_list_ref(raws, n - 1))
        return d
    d = an("Expr")
    af(d, "value", first)
    return d

def parse_import(toks, p):
    want_kw(toks, p, "import")
    names = py_list()
    names = py_list_append(names, parse_alias(toks, p))
    while is_op(toks, p, ","):
        tadv(p)
        names = py_list_append(names, parse_alias(toks, p))
    d = an("Import")
    af(d, "names", names)
    return d

def parse_alias(toks, p):
    nm = tv(toks, p)
    tadv(p)
    while is_op(toks, p, "."):
        tadv(p)
        nm = nm + "." + tv(toks, p)
        tadv(p)
    asname = NONE
    if is_kw(toks, p, "as"):
        tadv(p)
        asname = tv(toks, p)
        tadv(p)
    d = an("alias")
    af(d, "name", nm)
    af(d, "asname", asname)
    return d

def parse_import_from(toks, p):
    want_kw(toks, p, "from")
    level: int = 0
    dots: str = ""
    while is_op(toks, p, ".") or is_op(toks, p, "..."):
        v = tv(toks, p)
        if v == "...":
            level = level + 3
        else:
            level = level + 1
        dots = dots + v
        tadv(p)
    mod = NONE
    has_mod: int = 0
    if tty(toks, p) == "NAME":
        mod = tv(toks, p)
        has_mod = 1
        tadv(p)
        while is_op(toks, p, "."):
            tadv(p)
            mod = mod + "." + tv(toks, p)
            tadv(p)
    want_kw(toks, p, "import")
    names = py_list()
    if is_op(toks, p, "*"):
        tadv(p)
        a = an("alias")
        af(a, "name", "*")
        af(a, "asname", NONE)
        names = py_list_append(names, a)
    elif is_op(toks, p, "("):
        tadv(p)
        while not is_op(toks, p, ")"):
            names = py_list_append(names, parse_alias(toks, p))
            if is_op(toks, p, ","):
                tadv(p)
        want_op(toks, p, ")")
    else:
        names = py_list_append(names, parse_alias(toks, p))
        while is_op(toks, p, ","):
            tadv(p)
            names = py_list_append(names, parse_alias(toks, p))
    d = an("ImportFrom")
    af(d, "module", mod)
    af(d, "names", names)
    af(d, "level", level)
    return d

# ---- 复合语句 ----
def parse_if(toks, p, consume_kw: int):
    if consume_kw == 1:
        want_kw(toks, p, "if")
    test = parse_namedexpr(toks, p)
    body = parse_block(toks, p)
    orelse = py_list()
    if is_kw(toks, p, "elif"):
        tadv(p)
        sub = parse_if(toks, p, 0)
        orelse = py_list_append(orelse, sub)
    elif is_kw(toks, p, "else"):
        tadv(p)
        orelse = parse_block(toks, p)
    d = an("If")
    af(d, "test", test)
    af(d, "body", body)
    af(d, "orelse", orelse)
    return d

# 海象运算符 := （顶层）
def parse_namedexpr(toks, p):
    e = parse_expr(toks, p)
    if is_op(toks, p, ":="):
        tadv(p)
        d = an("NamedExpr")
        af(d, "target", to_target(e))
        af(d, "value", parse_expr(toks, p))
        return d
    return e

def parse_while(toks, p):
    want_kw(toks, p, "while")
    test = parse_namedexpr(toks, p)
    body = parse_block(toks, p)
    orelse = py_list()
    if is_kw(toks, p, "else"):
        tadv(p)
        orelse = parse_block(toks, p)
    d = an("While")
    af(d, "test", test)
    af(d, "body", body)
    af(d, "orelse", orelse)
    return d

def parse_for(toks, p):
    want_kw(toks, p, "for")
    tgt = parse_target_list(toks, p)
    want_kw(toks, p, "in")
    it = parse_testlist(toks, p)
    body = parse_block(toks, p)
    orelse = py_list()
    if is_kw(toks, p, "else"):
        tadv(p)
        orelse = parse_block(toks, p)
    d = an("For")
    af(d, "target", tgt)
    af(d, "iter", it)
    af(d, "body", body)
    af(d, "orelse", orelse)
    af(d, "type_comment", NONE)
    return d

def parse_arg_node(toks, p):
    nm = tv(toks, p)
    tadv(p)
    ann = NONE
    if is_op(toks, p, ":"):
        tadv(p)
        ann = parse_expr(toks, p)
    return mk_arg(nm, ann)

def parse_def(toks, p, decs):
    want_kw(toks, p, "def")
    nm = tv(toks, p)
    tadv(p)
    want_op(toks, p, "(")
    args = parse_params(toks, p)
    want_op(toks, p, ")")
    ret = NONE
    if is_op(toks, p, "->"):
        tadv(p)
        ret = parse_expr(toks, p)
    body = parse_block(toks, p)
    d = an("FunctionDef")
    af(d, "name", nm)
    af(d, "args", args)
    af(d, "body", body)
    af(d, "decorator_list", decs)
    af(d, "returns", ret)
    af(d, "type_comment", NONE)
    af(d, "type_params", py_list())
    return d

def parse_params(toks, p):
    a_pos = py_list()
    a_ann = py_list()
    a_has = py_list()
    a_def = py_list()
    kwonly = py_list()
    kwann = py_list()
    kwdef = py_list()
    kw_has = py_list()
    vararg = NONE
    kwarg = NONE
    slash_at: int = -1
    star_seen: int = 0
    while True:
        if is_op(toks, p, ")"):
            break
        if is_op(toks, p, "/"):
            tadv(p)
            slash_at = py_list_length(a_pos)
            if is_op(toks, p, ","):
                tadv(p)
            continue
        if is_op(toks, p, "*"):
            tadv(p)
            star_seen = 1
            if tty(toks, p) == "NAME":
                vararg = parse_arg_node(toks, p)
            if is_op(toks, p, ","):
                tadv(p)
            continue
        if is_op(toks, p, "**"):
            tadv(p)
            kwarg = parse_arg_node(toks, p)
            if is_op(toks, p, ","):
                tadv(p)
            continue
        nm = tv(toks, p)
        tadv(p)
        ann = NONE
        if is_op(toks, p, ":"):
            tadv(p)
            ann = parse_expr(toks, p)
        has: int = 0
        dflt = NONE
        if is_op(toks, p, "="):
            tadv(p)
            dflt = parse_expr(toks, p)
            has = 1
        if star_seen == 1:
            kwonly = py_list_append(kwonly, mk_arg(nm, ann))
            kwdef = py_list_append(kwdef, dflt)
            kw_has = py_list_append(kw_has, has)
        else:
            a_pos = py_list_append(a_pos, mk_arg(nm, ann))
            a_def = py_list_append(a_def, dflt)
            a_has = py_list_append(a_has, has)
        if is_op(toks, p, ","):
            tadv(p)
            continue
        break
    total: int = py_list_length(a_pos)
    if slash_at < 0:
        slash_at = 0
    posonly = py_list_slice(a_pos, 0, slash_at)
    args = py_list_slice(a_pos, slash_at, total)
    defaults = tail_defaults(a_def, a_has, slash_at, total)
    d = an("arguments")
    af(d, "posonlyargs", posonly)
    af(d, "args", args)
    af(d, "vararg", vararg)
    af(d, "kwonlyargs", kwonly)
    af(d, "kw_defaults", kwdef)
    af(d, "kwarg", kwarg)
    af(d, "defaults", defaults)
    return d

# 取从第一个有默认值起、到末尾的默认值子列表
def tail_defaults(vals, has, start: int, total: int):
    first: int = total
    i: int = start
    while i < total:
        if py_list_ref(has, i) == 1:
            first = i
            break
        i = i + 1
    if first >= total:
        return py_list()
    return py_list_slice(vals, first, total)

def parse_class(toks, p, decs):
    want_kw(toks, p, "class")
    nm = tv(toks, p)
    tadv(p)
    bases = py_list()
    kws = py_list()
    if is_op(toks, p, "("):
        tadv(p)
        got = parse_call_args(toks, p)
        bases = dict_get(got, "args")
        kws = dict_get(got, "keywords")
    body = parse_block(toks, p)
    d = an("ClassDef")
    af(d, "name", nm)
    af(d, "bases", bases)
    af(d, "keywords", kws)
    af(d, "body", body)
    af(d, "decorator_list", decs)
    af(d, "type_params", py_list())
    return d

def parse_try(toks, p):
    want_kw(toks, p, "try")
    body = parse_block(toks, p)
    handlers = py_list()
    orelse = py_list()
    finalbody = py_list()
    while is_kw(toks, p, "except"):
        tadv(p)
        typ = NONE
        nm = NONE
        if not is_op(toks, p, ":"):
            typ = parse_expr(toks, p)
            if is_kw(toks, p, "as"):
                tadv(p)
                nm = tv(toks, p)
                tadv(p)
        hbody = parse_block(toks, p)
        h = an("ExceptHandler")
        af(h, "type", typ)
        af(h, "name", nm)
        af(h, "body", hbody)
        handlers = py_list_append(handlers, h)
    if is_kw(toks, p, "else") and py_list_length(handlers) > 0:
        tadv(p)
        orelse = parse_block(toks, p)
    if is_kw(toks, p, "finally"):
        tadv(p)
        finalbody = parse_block(toks, p)
    d = an("Try")
    af(d, "body", body)
    af(d, "handlers", handlers)
    af(d, "orelse", orelse)
    af(d, "finalbody", finalbody)
    return d

def parse_with(toks, p):
    want_kw(toks, p, "with")
    items = py_list()
    if is_op(toks, p, "(") and not is_op_at(toks, p, 1, ")"):
        # 括号形式：with (a as x, b as y):
        save: int = tpos(p)
        tadv(p)
        tadv(p)
        if is_with_item(toks, p):
            item = parse_with_item(toks, p)
            items = py_list_append(items, item)
            while is_op(toks, p, ","):
                tadv(p)
                if is_op(toks, p, ")"):
                    break
                items = py_list_append(items, parse_with_item(toks, p))
            want_op(toks, p, ")")
            body = parse_block(toks, p)
            d = an("With")
            af(d, "items", items)
            af(d, "body", body)
            af(d, "type_comment", NONE)
            return d
        tset(p, save)
    items = py_list_append(items, parse_with_item(toks, p))
    while is_op(toks, p, ","):
        tadv(p)
        items = py_list_append(items, parse_with_item(toks, p))
    body = parse_block(toks, p)
    d = an("With")
    af(d, "items", items)
    af(d, "body", body)
    af(d, "type_comment", NONE)
    return d

def parse_with_item(toks, p):
    ctx = parse_expr(toks, p)
    v = NONE
    if is_kw(toks, p, "as"):
        tadv(p)
        v = to_target(parse_expr(toks, p))
    d = an("withitem")
    af(d, "context_expr", ctx)
    af(d, "optional_vars", v)
    return d

def is_with_item(toks, p) -> bool:
    return True

# ========== AST 规范 dump（与 staticpy/parse_diff.py 逐字节对齐） ==========
#
# 形如：Module(body=[Expr(value=Constant(value=1, kind=None))], type_ignores=[])
# 字段顺序 = CPython ast 的 _fields 顺序；kind 表：s 字符串 / i 整数 / b 布尔
# n 节点 / on 可选节点 / nl 节点表 / sl 字符串表 / os 可选字符串 / x 恒 None / v 常量值

DUMP_ROWS = [
    "Module|body:nl,type_ignores:nl",
    "FunctionDef|name:s,args:n,body:nl,decorator_list:nl,returns:on,type_comment:x,type_params:nl",
    "ClassDef|name:s,bases:nl,keywords:nl,body:nl,decorator_list:nl,type_params:nl",
    "Return|value:on",
    "Delete|targets:nl",
    "Assign|targets:nl,value:n",
    "AugAssign|target:n,op:n,value:n",
    "AnnAssign|target:n,annotation:n,value:on,simple:i",
    "For|target:n,iter:n,body:nl,orelse:nl,type_comment:x",
    "While|test:n,body:nl,orelse:nl",
    "If|test:n,body:nl,orelse:nl",
    "With|items:nl,body:nl,type_comment:x",
    "withitem|context_expr:n,optional_vars:on",
    "Raise|exc:on,cause:on",
    "Try|body:nl,handlers:nl,orelse:nl,finalbody:nl",
    "ExceptHandler|type:on,name:os,body:nl",
    "Assert|test:n,msg:on",
    "Import|names:nl",
    "ImportFrom|module:os,names:nl,level:i",
    "alias|name:s,asname:os",
    "Global|names:sl",
    "Nonlocal|names:sl",
    "Pass|",
    "Break|",
    "Continue|",
    "Expr|value:n",
    "BoolOp|op:n,values:nl",
    "BinOp|left:n,op:n,right:n",
    "UnaryOp|op:n,operand:n",
    "Lambda|args:n,body:n",
    "IfExp|test:n,body:n,orelse:n",
    "Dict|keys:nl,values:nl",
    "Set|elts:nl",
    "ListComp|elt:n,generators:nl",
    "SetComp|elt:n,generators:nl",
    "DictComp|key:n,value:n,generators:nl",
    "GeneratorExp|elt:n,generators:nl",
    "comprehension|target:n,iter:n,ifs:nl,is_async:i",
    "Compare|left:n,ops:nl,comparators:nl",
    "Call|func:n,args:nl,keywords:nl",
    "keyword|arg:os,value:n",
    "FormattedValue|value:n,conversion:i,format_spec:on",
    "JoinedStr|values:nl",
    "Constant|value:v,kind:x",
    "Attribute|value:n,attr:s,ctx:n",
    "Subscript|value:n,slice:n,ctx:n",
    "Starred|value:n,ctx:n",
    "Name|id:s,ctx:n",
    "List|elts:nl,ctx:n",
    "Tuple|elts:nl,ctx:n",
    "Slice|lower:on,upper:on,step:on",
    "arg|arg:s,annotation:on,type_comment:x",
    "arguments|posonlyargs:nl,args:nl,vararg:on,kwonlyargs:nl,kw_defaults:nl,kwarg:on,defaults:nl",
    "Load|",
    "Store|",
    "Del|",
    "And|",
    "Or|",
    "Add|",
    "Sub|",
    "Mult|",
    "MatMult|",
    "Div|",
    "Mod|",
    "Pow|",
    "LShift|",
    "RShift|",
    "BitOr|",
    "BitXor|",
    "BitAnd|",
    "FloorDiv|",
    "Invert|",
    "Not|",
    "UAdd|",
    "USub|",
    "Eq|",
    "NotEq|",
    "Lt|",
    "LtE|",
    "Gt|",
    "GtE|",
    "Is|",
    "IsNot|",
    "In|",
    "NotIn|",
    "Await|value:n",
    "NamedExpr|target:n,value:n",
]

def dump_row(tn: str) -> str:
    i: int = 0
    n: int = py_list_length(DUMP_ROWS)
    while i < n:
        row = py_list_ref(DUMP_ROWS, i)
        c = list_to_py_list(str_split(row, "|"))
        if py_list_ref(c, 0) == tn:
            return py_list_ref(c, 1)
        i = i + 1
    return "?"

# 字符串转义（与 parse_diff.py 同规则）
ASCII_TABLE = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~\x7f"

def char_index_of(c: str) -> int:
    return char_code(c)

def hex2(v: int) -> str:
    digits = "0123456789abcdef"
    hi: int = 0
    t: int = v
    while t >= 16:
        t = t - 16
        hi = hi + 1
    return sl(digits, hi, hi + 1) + sl(digits, t, t + 1)

def hex4(v: int) -> str:
    return hex2(v // 256) + hex2(v - (v // 256) * 256)

def dq(s: str) -> str:
    out: str = "'"
    i: int = 0
    n: int = str_length(s)
    while i < n:
        c = ch(s, i)
        if c == "\\":
            out = out + "\\\\"
        elif c == "'":
            out = out + "\\'"
        elif c == "\n":
            out = out + "\\n"
        elif c == "\r":
            out = out + "\\r"
        elif c == "\t":
            out = out + "\\t"
        else:
            cn: int = char_code(c)
            if cn >= 32 and cn <= 126:
                out = out + c
            elif cn < 256:
                out = out + "\\x" + hex2(cn)
            else:
                out = out + "\\u" + hex4(cn)
        i = i + 1
    return out + "'"

def show_float(v) -> str:
    # 与 parse_diff.py 一致的定点表示（%.17f 后去尾零）
    s = float_fixed(v, 17)
    if str_contains(s, "."):
        while str_ends_with(s, "0") and not str_ends_with(s, ".0"):
            s = sl(s, 0, str_length(s) - 1)
    return s

def show_const(v) -> str:
    k = dict_get(v, "_k")
    if k == "none":
        return "Constant(value=None, kind=None)"
    if k == "bool":
        if dict_get(v, "value") == 1:
            return "Constant(value=True, kind=None)"
        return "Constant(value=False, kind=None)"
    if k == "ellipsis":
        return "Constant(value=Ellipsis, kind=None)"
    if k == "str":
        return "Constant(value=" + dq(dict_get(v, "value")) + ", kind=None)"
    if k == "bytes":
        return "Constant(value=" + dq(dict_get(v, "value")) + ", kind=None)"
    if k == "float":
        return "Constant(value=" + show_float(dict_get(v, "value")) + ", kind=None)"
    if k == "complex":
        return "Constant(value=" + dq(dict_get(v, "value")) + ", kind=None)"
    return "Constant(value=" + string_of_int(dict_get(v, "value")) + ", kind=None)"

def show_list(vals, kind: str) -> str:
    out: str = "["
    i: int = 0
    n: int = py_list_length(vals)
    while i < n:
        if i > 0:
            out = out + ", "
        out = out + show_val(py_list_ref(vals, i), kind)
        i = i + 1
    return out + "]"

def show_val(v, kind: str) -> str:
    if kind == "s":
        return dq(v)
    if kind == "i":
        return string_of_int(v)
    if kind == "b":
        if v == 1:
            return "True"
        return "False"
    if kind == "x":
        return "None"
    if kind == "sl":
        return show_list(v, "s")
    if kind == "n":
        return show_node(v)
    if kind == "nl":
        return show_list(v, "n")
    if kind == "on":
        if v == NONE:
            return "None"
        return show_node(v)
    if kind == "os":
        if v == NONE:
            return "None"
        return dq(v)
    if kind == "v":
        return show_const(v)
    return "?"

def show_node(v) -> str:
    tn = dict_get(v, "_t")
    if tn == "Constant":
        return show_const(v)
    spec = dump_row(tn)
    if spec == "?":
        return tn + "<UNKNOWN>"
    if spec == "":
        return tn + "()"
    fields = list_to_py_list(str_split(spec, ","))
    out: str = tn + "("
    i: int = 0
    while i < py_list_length(fields):
        fd = list_to_py_list(str_split(py_list_ref(fields, i), ":"))
        if i > 0:
            out = out + ", "
        nmm = py_list_ref(fd, 0)
        knd = py_list_ref(fd, 1)
        out = out + nmm + "=" + show_val(dict_get(v, nmm), knd)
        i = i + 1
    return out + ")"
