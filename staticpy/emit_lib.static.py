# emit_lib.static.py — 第 2 环：AST（parse_lib 的 dict 形） -> Scheme IR
#
# 与 staticpy/static_translate.py 的代码生成一一对应：
#   translate_block / translate_function / translate_stmt / translate_expr
#   translate_binop / translate_compare / infer_expr_type ...
#
# 判据：同一输入，本文件产出的 IR 与旧版（CPython ast 版）一致
#       先过「规范化」比对（去注释/压空白），再向逐字节逼近。
#       见 staticpy/check_translate.sh
#
# 本文件是「纯函数库」（无 main），可被 concat 进 static_translate.static.py。

# parse_lib 的"无值"哨兵（asname 没有 `as` 时就是它）
PY_NONE = "\x00N"

RESERVED = (" if else let let* letrec cond case when unless define lambda quote "
            "set! begin do and or not vector make-vector call/cc guard "
            "dynamic-wind delay quasiquote unquote syntax-rules library import "
            "export parameters assert void eq? eqv? equal? null? pair? values ")

# 代码生成期类型环境：变量名（已 mangle）-> 类型串（"int"/"float"/"list[float]"）
TYPE_ENV = make_dict()
STATE = make_dict()
# 函数名 -> 返回类型串
SIGS = make_dict()
# from ... import 的裸名 -> 模块（这些名字是"别人的函数"，调用不加 static_ 前缀；
# 对齐旧版 IMPORTED_NAMES。库拆分（pil_lib + CLI）靠它：CLI 里 img_open(...)
# 必须发成 (img_open ...)，而不是 (static_img_open ...)）
IMPORTED = make_dict()
# 当前函数形参（参数是函数值时调用不加 static_ 前缀）
PARAMS = make_dict()

# ========== 运行时预置函数（不走 static_ 前缀） ==========
# 与 static_translate.py 的 PRELUDE_FUNCTIONS + scheme_name 对齐：
# 命中表里的名字直接生成 Scheme 运行时调用；py_list 这类再经 scheme_name 变成 py-list。

BOOL_METHODS = (
    " startswith endswith isdigit isalpha isalnum "
    "isspace isupper islower isnumeric isidentifier "
)

# 容器方法：dict/list 统一走运行时泛型分派 py-m-*（与旧版一致）
CONTAINER_METHODS = (
    " get keys items values pop setdefault update clear copy "
    "sort append extend insert remove index count reverse "
)

PRELUDE_NAMES = (
    "abs acos argv asin atan atan2 ceil char_code "
    "clock cos cosh csv_encode csv_parse cuda_axpy cuda_copy cuda_dot "
    "cuda_gemm cuda_gemm_tn dict_get dict_get_or_empty dict_set e exit exit_program "
    "exp file_close file_exists file_open file_read_all file_write float_array_free float_array_ref "
    "float_array_set float_fixed floor fmod format_float format_time http_get http_get_simple "
    "int_array_ref int_array_set integer_to_char json_dumps list_append_str list_length list_ref list_to_py_list "
    "log log10 log2 make_dict make_float_array make_int_array now_ts os_cwd "
    "os_delete_file os_file_exists os_file_size os_getcwd os_getenv os_list_dir os_mkdir os_move_file "
    "os_rmdir os_shell parse_json pi pow py_iter_to_list py_list py_list_append "
    "py_list_concat py_list_length py_list_ref py_list_slice py_unpack random_choice random_float random_int "
    "random_range random_seed random_uniform re_match re_search round sin sinh "
    "sleep sqrt str_contains str_ends_with str_join str_length str_lower str_replace "
    "str_slice str_split str_starts_with str_trim str_upper string_of_int string_to_float string_to_int "
    "py_float_repr tan tanh tuple_ref vec_ref "
)

def scheme_name(nm: str) -> str:
    """Python 运行时辅助名 -> Scheme 预置原语名"""
    if nm == "py_list":
        return "py-list"
    if nm == "py_list_append":
        return "py-list-append"
    if nm == "py_list_concat":
        return "py-list-concat"
    if nm == "py_list_ref":
        return "py-list-ref"
    if nm == "py_list_length":
        return "py-list-length"
    if nm == "list_to_py_list":
        return "list->py-list"
    if nm == "dict_copy":
        return "dict-copy"
    if nm == "py_iter_to_list":
        return "py-iter->list"
    if nm == "py_list_slice":
        return "py-list-slice"
    if nm == "py_unpack":
        return "py-unpack"
    return nm

def is_prelude_fn(nm: str) -> bool:
    return str_contains(PRELUDE_NAMES, " " + nm + " ")

def mangle_name(nm: str) -> str:
    """Python 变量名 -> 合法 Scheme 标识符（保留字加 _py 后缀）"""
    if str_contains(RESERVED, " " + nm + " "):
        return nm + "_py"
    return nm

# ========== 节点访问 ==========

def nt(n) -> str:
    """节点类型；非 dict 返回空串"""
    if n is None:
        return ""
    if isinstance(n, str) or isinstance(n, int) or isinstance(n, float):
        return ""
    if n is None:
        return ""
    return dict_get(n, "_t")

def nx(n, k):
    """节点字段；缺失 -> None"""
    return dict_get(n, k)

def tenv_frames():
    """类型环境帧栈（等价于旧版 per-function copy/restore）"""
    fr = dict_get(STATE, "frames")
    if fr is None:
        fr = py_list()
        dict_set(STATE, "frames", fr)
    return fr

def tenv_push() -> int:
    """进入函数：压入新帧（旧版 saved_env = TYPE_ENV.copy()）"""
    dict_set(STATE, "frames", py_list_append(tenv_frames(), make_dict()))
    return 0

def tenv_pop() -> int:
    """离开函数：弹帧（旧版 TYPE_ENV = saved_env）"""
    fr = tenv_frames()
    n = py_list_length(fr)
    if n > 0:
        dict_set(STATE, "frames", py_list_slice(fr, 0, n - 1))
    return 0

# ---- 形参集合（调用形参：`fn(x)` -> `(fn x)`，不加 static_ 前缀）----
def pset_list():
    v = dict_get(STATE, "psets")
    if v is None:
        v = py_list()
        dict_set(STATE, "psets", v)
    return v

def param_push(names) -> int:
    fr = make_dict()
    i: int = 0
    while i < py_list_length(names):
        dict_set(fr, mangle_name(py_list_ref(names, i)), 1)
        i = i + 1
    dict_set(STATE, "psets", py_list_append(pset_list(), fr))
    return 0

def param_pop() -> int:
    fr = pset_list()
    n: int = py_list_length(fr)
    if n > 0:
        dict_set(STATE, "psets", py_list_slice(fr, 0, n - 1))
    return 0

def alias_asname(al) -> str:
    """alias 的 asname；没有 `as` 时 parse_lib 填的是哨兵 "\x00N"（不是 None）"""
    v = dict_get(al, "asname")
    if v is None:
        return ""
    if v == PY_NONE:
        return ""
    return v

def imported_has(nm: str) -> bool:
    """from-import 进来的名字（不归本文件定义，调用不加 static_ 前缀）"""
    return dict_get(IMPORTED, nm) is not None

def is_param(nm: str) -> bool:
    fr = pset_list()
    k: str = mangle_name(nm)
    j: int = py_list_length(fr) - 1
    while j >= 0:
        if dict_get(py_list_ref(fr, j), k) is not None:
            return True
        j = j - 1
    return False

def param_names(n):
    """FunctionDef/Lambda -> 形参名列表"""
    ps = dict_get(dict_get(n, "args"), "args")
    out = py_list()
    i: int = 0
    while i < py_list_length(ps):
        out = py_list_append(out, dict_get(py_list_ref(ps, i), "arg"))
        i = i + 1
    return out

def tenv_get(nm: str) -> str:
    fr = tenv_frames()
    k = mangle_name(nm)
    j = py_list_length(fr) - 1
    while j >= 0:
        v = dict_get(py_list_ref(fr, j), k)
        if v is not None:
            return v
        j = j - 1
    return ""

def tenv_set(nm: str, t: str) -> int:
    fr = tenv_frames()
    n = py_list_length(fr)
    if n == 0:
        dict_set(STATE, "frames", py_list_append(fr, make_dict()))
        fr = dict_get(STATE, "frames")
        n = py_list_length(fr)
    dict_set(py_list_ref(fr, n - 1), mangle_name(nm), t)
    return 0

# ========== 类型标注 / 类型推断 ==========

def ann_str(ann) -> str:
    """ast 类型标注 -> 类型串（"int"、"list[float]" ...）"""
    t = nt(ann)
    if t == "":
        return ""
    if t == "Name":
        return dict_get(ann, "id")
    if t == "Constant":
        v = dict_get(ann, "value")
        if isinstance(v, str):
            return v
        return ""
    if t == "Subscript":
        return ann_str(dict_get(ann, "value")) + "[" + ann_str(dict_get(ann, "slice")) + "]"
    if t == "Tuple":
        out: str = ""
        elts = dict_get(ann, "elts")
        i: int = 0
        while i < py_list_length(elts):
            if i > 0:
                out = out + ","
            out = out + ann_str(py_list_ref(elts, i))
            i = i + 1
        return out
    return ""

def binop_type(lt: str, rt: str, op: str) -> str:
    """逐条镜像旧版 infer_expr_type 的 BinOp 分支（顺序也要一致）：
    任一侧是 list → 那个 list 类型；int+int → int（含真除法，旧版即如此）；
    两侧都在 int/float 里 → float；任一侧 str → str；否则未知（""）。
    注意：这里必须比"能算 float 就算 float"更保守——旧版对 `LEGX * 130.0`
    这种"未知全局 * float"返回 None，于是外层退化到通用 + / *。
    宽松一点就会多出 fl+ / fl/，IR 与旧版分叉。"""
    if str_starts_with(lt, "list") or str_starts_with(rt, "list"):
        if lt != "":
            return lt
        return rt
    if lt == "int" and rt == "int":
        return "int"
    if (lt == "int" or lt == "float") and (rt == "int" or rt == "float"):
        return "float"
    if lt == "str" or rt == "str":
        return "str"
    return ""

def sig_ret(name: str) -> str:
    v = dict_get(SIGS, name)
    if v is None:
        return ""
    return v

def builtin_ret(name: str) -> str:
    """预置函数返回类型（与旧版 infer_expr_type 的 Call 分支同表）"""
    if name == "int" or name == "len":
        return "int"
    if name == "float":
        return "float"
    if name == "bool":
        return "bool"
    if name == "make_float_array":
        return "list[float]"
    if name in ("str_slice", "str_join", "str_replace", "str_trim", "str_lower",
                "str_upper", "string_of_int", "format_float", "json_dumps",
                "os_getenv", "os_cwd", "http_get_simple", "integer_to_char"):
        return "str"
    if name == "str_split" or name == "os_list_dir":
        return "list[str]"
    if name in ("str_length", "string_to_int", "list_length", "os_file_size"):
        return "int"
    if name in ("string_to_float", "now_ts"):
        return "float"
    if name in ("str_contains", "str_starts_with", "str_ends_with", "os_file_exists"):
        return "bool"
    return ""

def infer_expr_type(n) -> str:
    """表达式静态类型（只为选 fx+/fl+/string-append 这类特化算子）"""
    t = nt(n)
    if t == "":
        return ""
    if t == "Name":
        return tenv_get(dict_get(n, "id"))
    if t == "Constant":
        k = dict_get(n, "_k")
        if k == "int" or k == "float" or k == "str" or k == "bool":
            return k
        return ""
    if t == "BinOp":
        return binop_type(infer_expr_type(dict_get(n, "left")),
                          infer_expr_type(dict_get(n, "right")),
                          nt(dict_get(n, "op")))
    if t == "Compare" or t == "BoolOp":
        return "bool"
    if t == "UnaryOp":
        if nt(dict_get(n, "op")) == "Not":
            return "bool"
        return infer_expr_type(dict_get(n, "operand"))
    if t == "Call":
        f = dict_get(n, "func")
        if nt(f) == "Name":
            nm = dict_get(f, "id")
            bt = builtin_ret(nm)
            if bt != "":
                return bt
            return sig_ret(nm)
        return ""
    if t == "IfExp":
        a = infer_expr_type(dict_get(n, "body"))
        b = infer_expr_type(dict_get(n, "orelse"))
        if a == b:
            return a
        return ""
    return ""

# ========== 结构扫描 ==========

def collect_function_types(n, src: str) -> int:
    """形参标注 + 函数体内 AnnAssign 的类型进 TYPE_ENV"""
    args = dict_get(dict_get(n, "args"), "args")
    i: int = 0
    while i < py_list_length(args):
        a = py_list_ref(args, i)
        t = ann_str(dict_get(a, "annotation"))
        if t != "":
            tenv_set(dict_get(a, "arg"), t)
        i = i + 1
    scan_types(dict_get(n, "body"), src)
    return 0

def scan_types(stmts, src: str) -> int:
    i: int = 0
    while i < py_list_length(stmts):
        s = py_list_ref(stmts, i)
        t = nt(s)
        if t == "AnnAssign":
            tgt = dict_get(s, "target")
            if nt(tgt) == "Name":
                a = ann_str(dict_get(s, "annotation"))
                if a != "":
                    tenv_set(dict_get(tgt, "id"), a)
        elif t == "FunctionDef":
            collect_function_types(s, src)
        elif t == "While" or t == "For":
            scan_types(dict_get(s, "body"), src)
        elif t == "If":
            scan_types(dict_get(s, "body"), src)
            scan_types(dict_get(s, "orelse"), src)
        i = i + 1
    return 0

def list_has(l, v: str) -> bool:
    i: int = 0
    while i < py_list_length(l):
        if py_list_ref(l, i) == v:
            return True
        i = i + 1
    return False

def names_add(out, nm: str):
    if list_has(out, nm):
        return out
    return py_list_append(out, nm)

def names_merge(a, b):
    i: int = 0
    while i < py_list_length(b):
        a = names_add(a, py_list_ref(b, i))
        i = i + 1
    return a

def names_of_target(names, tg):
    t = nt(tg)
    if t == "Name":
        return names_add(names, dict_get(tg, "id"))
    if t == "Tuple":
        elts = dict_get(tg, "elts")
        k: int = 0
        while k < py_list_length(elts):
            e = py_list_ref(elts, k)
            if nt(e) == "Name":
                names = names_add(names, dict_get(e, "id"))
            k = k + 1
    return names

def collect_assigned_names(stmts):
    """递归收集被赋值变量名（不展开嵌套函数定义）"""
    names = py_list()
    i: int = 0
    while i < py_list_length(stmts):
        s = py_list_ref(stmts, i)
        t = nt(s)
        if t == "AnnAssign":
            names = names_of_target(names, dict_get(s, "target"))
        elif t == "Assign":
            tgts = dict_get(s, "targets")
            j: int = 0
            while j < py_list_length(tgts):
                names = names_of_target(names, py_list_ref(tgts, j))
                j = j + 1
        elif t == "AugAssign":
            names = names_of_target(names, dict_get(s, "target"))
        elif t == "For":
            names = names_of_target(names, dict_get(s, "target"))
            names = names_merge(names, collect_assigned_names(dict_get(s, "body")))
            names = names_merge(names, collect_assigned_names(dict_get(s, "orelse")))
        elif t == "While" or t == "If":
            names = names_merge(names, collect_assigned_names(dict_get(s, "body")))
            names = names_merge(names, collect_assigned_names(dict_get(s, "orelse")))
        i = i + 1
    return names

def has_return(stmts) -> bool:
    i: int = 0
    while i < py_list_length(stmts):
        s = py_list_ref(stmts, i)
        t = nt(s)
        if t == "Return":
            return True
        if t == "If":
            if has_return(dict_get(s, "body")) or has_return(dict_get(s, "orelse")):
                return True
        if t == "For" or t == "While" or t == "With":
            if has_return(dict_get(s, "body")):
                return True
        i = i + 1
    return False

def has_direct_control(stmts, kind: str) -> bool:
    """块内是否有 break/continue（不进入嵌套循环）"""
    i: int = 0
    while i < py_list_length(stmts):
        st = py_list_ref(stmts, i)
        t = nt(st)
        if t == kind:
            return True
        if t == "While" or t == "For":
            i = i + 1
            continue
        if t == "If":
            if has_direct_control(dict_get(st, "body"), kind):
                return True
            if has_direct_control(dict_get(st, "orelse"), kind):
                return True
        i = i + 1
    return False

def str_lt(a: str, b: str) -> bool:
    return a < b

def sort_names(names):
    """按字符串升序（等价 CPython sorted(list[str])；插入排序，表很短）"""
    out = py_list()
    i: int = 0
    while i < py_list_length(names):
        v = py_list_ref(names, i)
        ins = py_list()
        j: int = 0
        done: int = 0
        while j < py_list_length(out):
            w = py_list_ref(out, j)
            if done == 0 and str_lt(v, w):
                ins = py_list_append(ins, v)
                done = 1
            ins = py_list_append(ins, w)
            j = j + 1
        if done == 0:
            ins = py_list_append(ins, v)
        out = ins
        i = i + 1
    return out

def str_lit(s: str) -> str:
    """Python 字符串 -> Scheme 字符串字面量（与旧版 replace 链同序）"""
    t = str_replace(s, "\\", "\\\\")
    t = str_replace(t, "\"", "\\\"")
    t = str_replace(t, "\n", "\\n")
    t = str_replace(t, "\t", "\\t")
    t = str_replace(t, "\r", "\\r")
    return "\"" + t + "\""

# ========== 表达式 ==========

def const_text(n) -> str:
    k = dict_get(n, "_k")
    v = dict_get(n, "value")
    if k == "bool":
        # IR 里 True/False 存的是 1/0（parse_lib.mk_const）
        if v == 0:
            return "#f"
        return "#t"
    if k == "none":
        return "py-none"
    if k == "str":
        return str_lit(v)
    if k == "bytes":
        return str_lit(v)
    if k == "float":
        return py_float_repr(v)
    return f"{v}"

def translate_subscript(n) -> str:
    """a[i] / a[i:j] -> 按 value 类型选 accessor / 切片（同旧版 Subscript 分支）"""
    value = translate_expr(dict_get(n, "value"))
    slc = dict_get(n, "slice")
    vt = infer_expr_type(dict_get(n, "value"))
    if nt(slc) == "Slice":
        start: str = "0"
        if dict_get(slc, "lower") is not None:
            start = translate_expr(dict_get(slc, "lower"))
        end: str = ""
        if dict_get(slc, "upper") is None:
            if vt == "str":
                end = "(string-length " + value + ")"
            elif str_starts_with(vt, "list["):
                end = "(tagged-array-len " + value + ")"
            else:
                end = "(vector-length " + value + ")"
        else:
            end = translate_expr(dict_get(slc, "upper"))
        if vt == "str":
            return "(slice-string " + value + " " + start + " " + end + ")"
        if str_starts_with(vt, "list["):
            return "(make-tagged-array (slice-array (tagged-array-data " + value + ") " + start + " " + end + ") (- " + end + " " + start + "))"
        return "(if (string? " + value + ") (slice-string " + value + " " + start + " " + end + ") (slice-array " + value + " " + start + " " + end + "))"
    idx = translate_expr(slc)
    if nt(slc) == "Constant" and dict_get(slc, "_k") == "str":
        return "(py-get " + value + " " + idx + ")"
    if vt == "list[float]":
        return "(float_array_ref " + value + " " + idx + ")"
    if vt == "tuple":
        return "(vector-ref " + value + " " + idx + ")"
    if vt == "list":
        return "(py-list-ref " + value + " " + idx + ")"
    if str_starts_with(vt, "vector["):
        return "(vector-ref " + value + " " + idx + ")"
    if str_starts_with(vt, "list["):
        return "(vector-ref " + value + " " + idx + ")"
    if vt == "str":
        return "(slice-string " + value + " " + idx + " (fx+ " + idx + " 1))"
    return "(py-get " + value + " " + idx + ")"

def elems_text(elts) -> str:
    """元素表 -> 空格分隔的表达式串"""
    ps = py_list()
    i: int = 0
    while i < py_list_length(elts):
        ps = py_list_append(ps, translate_expr(py_list_ref(elts, i)))
        i = i + 1
    return jn(ps)

def translate_joined(n) -> str:
    """f-string -> (string-append ...)，插值用 (format "~a" e)（与旧版一致）"""
    vs = dict_get(n, "values")
    ps = py_list()
    j: int = 0
    while j < py_list_length(vs):
        e = py_list_ref(vs, j)
        if nt(e) == "FormattedValue":
            ps = py_list_append(ps, "(format \"~a\" " + translate_expr(dict_get(e, "value")) + ")")
        elif nt(e) == "Constant":
            ps = py_list_append(ps, translate_expr(e))
        else:
            ps = py_list_append(ps, "\"\"")
        j = j + 1
    if py_list_length(ps) == 1:
        return py_list_ref(ps, 0)
    return "(string-append " + jn(ps) + ")"

def translate_expr(n) -> str:
    t = nt(n)
    if t == "":
        return "#f"
    if t == "Constant":
        return const_text(n)
    if t == "Name":
        return mangle_name(dict_get(n, "id"))
    if t == "BinOp":
        return translate_binop(nt(dict_get(n, "op")),
                               dict_get(n, "left"), dict_get(n, "right"))
    if t == "Compare":
        return translate_compare(dict_get(n, "ops"), dict_get(n, "left"),
                                 dict_get(n, "comparators"))
    if t == "Call":
        return translate_call(n)
    if t == "UnaryOp":
        return translate_unary(n)
    if t == "IfExp":
        return f"(if {translate_expr(dict_get(n, 'test'))} {translate_expr(dict_get(n, 'body'))} {translate_expr(dict_get(n, 'orelse'))})"
    if t == "Subscript":
        return translate_subscript(n)
    if t == "Tuple":
        # 与种子一致：Tuple 表达式是 Python tuple（记录类型，repr 为 (..)），不是 vector
        return "(py-tuple " + elems_text(dict_get(n, "elts")) + ")"
    if t == "List":
        return "(py-list " + elems_text(dict_get(n, "elts")) + ")"
    if t == "Dict":
        ks = dict_get(n, "keys")
        vs = dict_get(n, "values")
        if py_list_length(ks) == 0:
            return "(make-dict)"
        items: str = ""
        i: int = 0
        while i < py_list_length(ks):
            items = items + f"(dict-set! d {translate_expr(py_list_ref(ks, i))} {translate_expr(py_list_ref(vs, i))}) "
            i = i + 1
        return "(let ((d (make-dict))) " + items + "d)"
    if t == "JoinedStr":
        return translate_joined(n)
    if t == "BoolOp":
        op: str = "or"
        if nt(dict_get(n, "op")) == "And":
            op = "and"
        vs = dict_get(n, "values")
        ps = py_list()
        j: int = 0
        while j < py_list_length(vs):
            ps = py_list_append(ps, translate_expr(py_list_ref(vs, j)))
            j = j + 1
        return "(" + op + " " + jn(ps) + ")"
    if t == "Lambda":
        return translate_lambda(n)
    return ";; " + t + " (untranslated)"

def translate_binop(op: str, ln, rn) -> str:
    """按操作数类型生成特化算子（fx+/fl+/string-append）"""
    left = translate_expr(ln)
    right = translate_expr(rn)
    lt = infer_expr_type(ln)
    rt = infer_expr_type(rn)
    is_int: int = 0
    is_float: int = 0
    if lt == "int" and rt == "int":
        is_int = 1
    if (lt == "int" or lt == "float") and (rt == "int" or rt == "float"):
        is_float = 1
    if op == "Add":
        if str_starts_with(lt, "list") and str_starts_with(rt, "list"):
            return f"(py-list-concat {left} {right})"
        if str_starts_with(lt, "list") or str_starts_with(rt, "list"):
            return f"(py-list-append {left} {right})"
    if is_int == 1 and op == "Div":
        return f"(py-truediv {left} {right})"
    if is_int == 1:
        if op == "Add":
            return f"(fx+ {left} {right})"
        if op == "Sub":
            return f"(fx- {left} {right})"
        if op == "Mult":
            return f"(fx* {left} {right})"
        if op == "FloorDiv":
            return f"(fxdiv {left} {right})"
        if op == "Mod":
            return f"(fxmod {left} {right})"
        if op == "Pow":
            return f"(fxexpt {left} {right})"
    if is_float == 1:
        if op == "Add":
            return f"(fl+ {left} {right})"
        if op == "Sub":
            return f"(fl- {left} {right})"
        if op == "Mult":
            return f"(fl* {left} {right})"
        if op == "Div":
            return f"(fl/ {left} {right})"
        if op == "FloorDiv":
            return f"(fldiv {left} {right})"
        if op == "Mod":
            return f"(flmod {left} {right})"
        if op == "Pow":
            return f"(flexpt {left} {right})"
    if (lt == "str" or rt == "str") and op == "Add":
        return f"(string-append {left} {right})"
    if op == "Add":
        return f"(+ {left} {right})"
    if op == "Sub":
        return f"(- {left} {right})"
    if op == "Mult":
        return f"(* {left} {right})"
    if op == "Div":
        return f"(/ {left} {right})"
    if op == "FloorDiv":
        return f"(quotient {left} {right})"
    if op == "Mod":
        return f"(mod {left} {right})"
    if op == "Pow":
        return f"(expt {left} {right})"
    return f"({str_lower(op)} {left} {right})"

def translate_compare(ops, ln, coms) -> str:
    """按类型生成特化比较；只用 ops[0]/comparators[0]（同旧版）"""
    op = nt(py_list_ref(ops, 0))
    rn = py_list_ref(coms, 0)
    if op == "Is" or op == "IsNot":
        expr = ""
        if nt(rn) == "Constant" and dict_get(rn, "_k") == "none":
            expr = f"(py-none? {translate_expr(ln)})"
        elif nt(ln) == "Constant" and dict_get(ln, "_k") == "none":
            expr = f"(py-none? {translate_expr(rn)})"
        else:
            expr = f"(eq? {translate_expr(ln)} {translate_expr(rn)})"
        if op == "IsNot":
            return f"(not {expr})"
        return expr
    if op == "In" or op == "NotIn":
        expr = f"(py-contains? {translate_expr(ln)} {translate_expr(rn)})"
        if op == "NotIn":
            return f"(not {expr})"
        return expr
    if op == "NotEq":
        return f"(not {translate_compare_eq(ln, rn)})"
    return translate_cmp_typed(op, ln, rn)
def cmp_sym(op: str) -> str:
    if op == "Lt":
        return "<"
    if op == "LtE":
        return "<="
    if op == "Gt":
        return ">"
    if op == "GtE":
        return ">="
    if op == "Eq":
        return "="
    return ""

def translate_compare_eq(ln, rn) -> str:
    return translate_cmp_typed("Eq", ln, rn)

def translate_cmp_typed(op: str, ln, rn) -> str:
    left = translate_expr(ln)
    right = translate_expr(rn)
    lt = infer_expr_type(ln)
    rt = infer_expr_type(rn)
    sym = cmp_sym(op)
    if sym == "":
        return f"(equal? {left} {right})"
    if lt == "int" and rt == "int":
        return f"(fx{sym} {left} {right})"
    if (lt == "int" or lt == "float") and (rt == "int" or rt == "float"):
        return f"(fl{sym} {left} {right})"
    if lt == "str" or rt == "str":
        return f"(string{sym}? {left} {right})"
    if op == "Eq":
        return f"(equal? {left} {right})"
    return f"({sym} {left} {right})"

def expr_is_bool(n) -> int:
    """启发式：表达式是否已产出 #t/#f（旧版 expr_is_bool 的移植）"""
    if n is None:
        return 0
    t = nt(n)
    if t == "Compare" or t == "BoolOp":
        return 1
    if t == "UnaryOp" and nt(dict_get(n, "op")) == "Not":
        return 1
    if t == "Constant" and dict_get(n, "_k") == "bool":
        return 1
    if t == "Call":
        f = dict_get(n, "func")
        ft = nt(f)
        if ft == "Name":
            nm = dict_get(f, "id")
            if nm == "bool" or nm == "isinstance" or nm == "all" or nm == "any":
                return 1
        if ft == "Attribute":
            a = dict_get(f, "attr")
            if str_contains(BOOL_METHODS, " " + a + " "):
                return 1
    return 0

def translate_unary(n) -> str:
    op = nt(dict_get(n, "op"))
    e = dict_get(n, "operand")
    if op == "Not":
        # 操作数本身是布尔时免去 py-truthy（与旧版 expr_is_bool 一致）
        if expr_is_bool(e) == 1:
            return "(not " + translate_expr(e) + ")"
        return "(not (py-truthy " + translate_expr(e) + "))"
    if op == "USub":
        return f"(- {translate_expr(e)})"
    if op == "UAdd":
        return translate_expr(e)
    return f"(not {translate_expr(e)})"

def translate_lambda(n) -> str:
    ps = dict_get(dict_get(n, "args"), "args")
    out: str = ""
    i: int = 0
    while i < py_list_length(ps):
        if i > 0:
            out = out + " "
        out = out + mangle_name(dict_get(py_list_ref(ps, i), "arg"))
        i = i + 1
    param_push(param_names(n))
    body: str = translate_expr(dict_get(n, "body"))
    param_pop()
    return f"(lambda ({out}) {body})"

def call_args(args_l) -> str:
    out: str = ""
    i: int = 0
    while i < py_list_length(args_l):
        if i > 0:
            out = out + " "
        out = out + translate_expr(py_list_ref(args_l, i))
        i = i + 1
    return out

def translate_call(n) -> str:
    f = dict_get(n, "func")
    a = call_args(dict_get(n, "args"))
    if nt(f) == "Attribute":
        at = dict_get(f, "attr")
        rv = dict_get(f, "value")
        al = dict_get(n, "args")
        # 不可变 list 模型：lst.append(x) -> (set! lst (py-list-append lst x))
        if at == "append" and nt(rv) == "Name" and py_list_length(al) == 1:
            vn = mangle_name(dict_get(rv, "id"))
            return f"(set! {vn} (py-list-append {vn} {a}))"
        if str_contains(CONTAINER_METHODS, " " + at + " "):
            return f"(py-m-{at} {translate_expr(rv)} {a})"
        return f"({translate_expr(f)} {a})"
    if nt(f) != "Name":
        return f"({translate_expr(f)} {a})"
    nm = dict_get(f, "id")
    if nm == "print":
        return f"(print {a})"
    if nm == "len":
        return f"(py-len {a})"
    if nm == "str":
        return f"(py-str {a})"
    if nm == "list":
        if py_list_length(dict_get(n, "args")) == 0:
            return "(new_list)"
        return f"(as_list {a})"
    if nm == "dict":
        if py_list_length(dict_get(n, "args")) == 0:
            return "(new_dict)"
        return f"(as_dict {a})"
    if nm == "range":
        return f"({a})"
    if nm == "int":
        return f"(exact (round {a}))"
    if nm == "float":
        return f"(inexact {a})"
    if nm == "bool":
        return f"(py-truthy {a})"
    if nm == "abs":
        return f"(abs {a})"
    if nm == "isinstance":
        al = dict_get(n, "args")
        if py_list_length(al) == 2:
            c = py_list_ref(al, 1)
            x0 = translate_expr(py_list_ref(al, 0))
            if nt(c) == "Name":
                return f"(ir-tag? {x0} '{dict_get(c, 'id')})"
            return f"(ir-tag? {x0} {translate_expr(c)})"
        return f"(ir-tag? {a})"
    if is_prelude_fn(nm):
        return f"({scheme_name(nm)} {a})"
    if is_param(nm):
        return f"({mangle_name(nm)} {a})"
    if tenv_get(nm) != "":
        return f"({mangle_name(nm)} {a})"
    if extern_has(nm):
        # extern fn：直接调 foreign-procedure，不加 static_ 前缀
        return f"({mangle_name(nm)} {a})"
    if imported_has(nm):
        # from <lib> import fn：裸名直调（同旧版 resolve_imported_name）
        return f"({mangle_name(nm)} {a})"
    return f"(static_{nm} {a})"

# ========== 语句块 ==========

def jn(l) -> str:
    out: str = ""
    i: int = 0
    while i < py_list_length(l):
        if i > 0:
            out = out + " "
        out = out + py_list_ref(l, i)
        i = i + 1
    return out

def block_assign(exprs, s, t: str):
    tg = dict_get(s, "target")
    if t == "Assign":
        tl = dict_get(s, "targets")
        if py_list_length(tl) != 1:
            return py_list_append(exprs, ";; " + t)
        tg = py_list_ref(tl, 0)
    v = dict_get(s, "value")
    if v is None:
        return py_list_append(exprs, ";; " + t)
    if nt(tg) == "Name":
        nm = dict_get(tg, "id")
        iv = infer_expr_type(v)
        if iv != "":
            tenv_set(nm, iv)
        return py_list_append(exprs, f"(set! {mangle_name(nm)} {translate_expr(v)})")
    if nt(tg) == "Subscript":
        # d[k] = v -> (dict-set! d k v)
        return py_list_append(exprs, f"(dict-set! {translate_expr(dict_get(tg, 'value'))} {translate_expr(dict_get(tg, 'slice'))} {translate_expr(v)})")
    return py_list_append(exprs, ";; " + t)

def translate_block(stmts, lvl: int):
    exprs = py_list()
    i: int = 0
    while i < py_list_length(stmts):
        s = py_list_ref(stmts, i)
        t = nt(s)
        if t == "Assign" or t == "AnnAssign":
            exprs = block_assign(exprs, s, t)
        elif t == "Expr":
            exprs = py_list_append(exprs, translate_expr(dict_get(s, "value")))
        elif t == "Return":
            v: str = "#f"
            if dict_get(s, "value") is not None:
                v = translate_expr(dict_get(s, "value"))
            exprs = py_list_append(exprs, f"(__return__ {v})")
        elif t == "Pass":
            exprs = py_list_append(exprs, "(void)")
        elif t == "Break":
            exprs = py_list_append(exprs, "(__break__ #f)")
        elif t == "Continue":
            exprs = py_list_append(exprs, "(__continue__ #f)")
        elif t == "If":
            merged: int = 0
            nxt = s
            if lvl == 1 and i + 1 < py_list_length(stmts):
                nxt = py_list_ref(stmts, i + 1)
                merged = if_merge_tail(s, nxt)
            if merged == 1:
                # 优化（与旧版一致）：if cond: return a / return b  ->  (if cond a b)
                exprs = py_list_append(exprs, block_if_tail(s, nxt))
                i = i + 1
            else:
                exprs = py_list_append(exprs, block_if(s))
        elif t == "While":
            exprs = py_list_append(exprs, block_while(s))
        elif t == "For":
            exprs = py_list_append(exprs, block_for(s, lvl))
        else:
            exprs = py_list_append(exprs, ";; " + t)
        i = i + 1
    return exprs

def block_if_merge_ok(s, nxt) -> bool:
    """if 无 else、if 体以 return 结尾、且下一条语句是 return -> 可合并"""
    if py_list_length(dict_get(s, "orelse")) != 0:
        return False
    bd = dict_get(s, "body")
    if py_list_length(bd) == 0:
        return False
    if nt(py_list_ref(bd, py_list_length(bd) - 1)) != "Return":
        return False
    if nt(nxt) != "Return":
        return False
    return True

def if_merge_tail(s, nxt) -> int:
    if block_if_merge_ok(s, nxt):
        return 1
    return 0

def block_if_tail(s, nxt) -> str:
    test = translate_expr(dict_get(s, "test"))
    th = jn(translate_block(dict_get(s, "body"), 0))
    nv: str = "#f"
    if dict_get(nxt, "value") is not None:
        nv = translate_expr(dict_get(nxt, "value"))
    return f"(if {test}\n    (begin {th})\n    {nv})"

def block_if(s) -> str:
    test = translate_expr(dict_get(s, "test"))
    th = jn(translate_block(dict_get(s, "body"), 0))
    el = dict_get(s, "orelse")
    if py_list_length(el) > 0:
        eb = jn(translate_block(el, 0))
        return f"(if {test}\n        (begin {th})\n        (begin {eb}))"
    return f"(if {test}\n        (begin {th}))"

def block_while(s) -> str:
    test = translate_expr(dict_get(s, "test"))
    body = dict_get(s, "body")
    bs = jn(translate_block(body, 0))
    if has_direct_control(body, "Break") or has_direct_control(body, "Continue"):
        inner = bs
        if has_direct_control(body, "Continue"):
            inner = f"(call/cc (lambda (__continue__) {inner}))"
        return f"(let loop () (call/cc (lambda (__break__) (if {test} (begin {inner} (loop))))))"
    return f"(let loop () (if {test} (begin {bs} (loop))))"

def block_for(s, lvl: int) -> str:
    tg = dict_get(s, "target")
    nm: str = "i"
    if nt(tg) == "Name":
        nm = mangle_name(dict_get(tg, "id"))
    it = dict_get(s, "iter")
    bs = jn(translate_block(dict_get(s, "body"), 0))
    if is_range(it):
        ra = dict_get(it, "args")
        n = py_list_length(ra)
        if n == 1:
            return f"(do (({nm} 0 (+ {nm} 1))) ((>= {nm} {translate_expr(py_list_ref(ra, 0))})) {bs})"
        if n == 2:
            return f"(do (({nm} {translate_expr(py_list_ref(ra, 0))} (+ {nm} 1))) ((>= {nm} {translate_expr(py_list_ref(ra, 1))})) {bs})"
        if n == 3:
            return f"(do (({nm} {translate_expr(py_list_ref(ra, 0))} (+ {nm} {translate_expr(py_list_ref(ra, 2))}))) ((>= {nm} {translate_expr(py_list_ref(ra, 1))})) {bs})"
    if nt(it) == "List" or nt(it) == "ListComp" or nt(it) == "Tuple":
        return f"(let* ((__iter {translate_expr(it)}) (__n (vector-length __iter))) (do ((__i 0 (+ __i 1))) ((>= __i __n)) (let (({nm} (vector-ref __iter __i))) {bs})))"
    if nt(it) == "Constant" and dict_get(it, "_k") == "str":
        return f"(let* ((__iter {translate_expr(it)}) (__n (string-length __iter))) (do ((__i 0 (+ __i 1))) ((>= __i __n)) (let (({nm} (string-ref __iter __i))) {bs})))"
    if nt(it) == "Name":
        iname = mangle_name(dict_get(it, "id"))
        if lvl == 1:
            return f"(let* ((__iter (py-iter-seq {iname})) (__n (vector-length __iter))) (do ((__i 0 (+ __i 1))) ((>= __i __n)) (let (({nm} (vector-ref __iter __i))) {bs})))"
        return (f"(let* ((__iter {iname}) (__n (if (tagged-array? __iter) (tagged-array-len __iter) "
                f"(if (string? __iter) (string-length __iter) (vector-length __iter))))) "
                f"(do ((__i 0 (+ __i 1))) ((>= __i __n)) "
                f"(let (({nm} (if (tagged-array? __iter) (float-array-ref (tagged-array-data __iter) __i) "
                f"(if (string? __iter) (string-ref __iter __i) (vector-ref __iter __i))))) {bs})))")
    return ";; for loop (untranslated)"

def is_range(it) -> bool:
    if nt(it) != "Call":
        return False
    f = dict_get(it, "func")
    if nt(f) != "Name":
        return False
    return dict_get(f, "id") == "range"

# ========== 函数 ==========

def jnl(l) -> str:
    out: str = ""
    i: int = 0
    while i < py_list_length(l):
        if i > 0:
            out = out + "\n    "
        out = out + py_list_ref(l, i)
        i = i + 1
    return out

def params_of(n) -> str:
    ps = dict_get(dict_get(n, "args"), "args")
    out: str = ""
    i: int = 0
    while i < py_list_length(ps):
        if i > 0:
            out = out + " "
        out = out + mangle_name(dict_get(py_list_ref(ps, i), "arg"))
        i = i + 1
    return out

def locals_of(n):
    """函数体内被赋值的局部变量（去形参，按名字升序）"""
    names = collect_assigned_names(dict_get(n, "body"))
    ps = dict_get(dict_get(n, "args"), "args")
    out = py_list()
    i: int = 0
    while i < py_list_length(names):
        nm = py_list_ref(names, i)
        j: int = 0
        # 注意：别叫 is_param——旧翻译器的 TYPE_ENV 会跨函数漏变量名，
        # 与同名函数 is_param 撞车会把它当函数值裸调用。
        is_par: int = 0
        while j < py_list_length(ps):
            if dict_get(py_list_ref(ps, j), "arg") == nm:
                is_par = 1
            j = j + 1
        if is_par == 0:
            out = py_list_append(out, nm)
        i = i + 1
    return sort_names(out)

def body_text(exprs) -> str:
    if py_list_length(exprs) == 1:
        return "  " + py_list_ref(exprs, 0)
    return "  (begin\n    " + jnl(exprs) + "\n  )"

# ========== 源码行号注释 ==========
# 与旧版 debug_annotation 一一对应：每条「顶层语句」前输出 `;; file:line`。
# 只有函数体的顶层语句带注释（嵌套块不带），与 static_translate.py 一致。

SRCBOX = make_dict()

def src_set(s: str) -> int:
    dict_set(SRCBOX, "src", s)
    return 0

def src_get() -> str:
    v = dict_get(SRCBOX, "src")
    if v is None:
        return "<input>"
    return v

def ann_of(s) -> str:
    ln = dict_get(s, "lineno")
    if ln is None:
        return ""
    return ";; " + src_get() + ":" + f"{ln}"

def annotate_block(stmts):
    """语句表 -> 带注释的表达式表（注释与表达式交替，与旧版 annotated_exprs 一致）"""
    exprs = translate_block(stmts, 1)
    out = py_list()
    i: int = 0
    while i < py_list_length(stmts):
        a = ann_of(py_list_ref(stmts, i))
        if a != "":
            out = py_list_append(out, a)
        if i < py_list_length(exprs):
            out = py_list_append(out, py_list_ref(exprs, i))
        i = i + 1
    return out

def translate_function(n, src: str) -> str:
    """函数体 -> (define (static_x ..) ..)；类型环境逐函数压栈/弹栈（与旧版一致）"""
    tenv_push()
    param_push(param_names(n))
    src_set(src)
    collect_function_types(n, src)
    nm = dict_get(n, "name")
    dict_set(SIGS, nm, ann_str(dict_get(n, "returns")))
    body = dict_get(n, "body")
    txt = body_text(annotate_block(body))
    lv = locals_of(n)
    if py_list_length(lv) > 0:
        bs: str = ""
        i: int = 0
        while i < py_list_length(lv):
            if i > 0:
                bs = bs + " "
            bs = bs + "(" + mangle_name(py_list_ref(lv, i)) + " #f)"
            i = i + 1
        txt = "  (let (" + bs + ")\n" + txt + "\n  )"
    if has_return(body):
        txt = "  (call/cc (lambda (__return__)\n" + txt + "\n  ))"
    hdr: str = ""
    fa = ann_of(n)
    if fa != "":
        hdr = fa + "\n"
    tenv_pop()
    param_pop()
    return hdr + f"(define (static_{nm} {params_of(n)})\n{txt})"

def top_level_define(s, t: str) -> str:
    """模块级赋值 -> (define name value)（与旧版 translate_module 一致）"""
    tg = dict_get(s, "target")
    if t == "Assign":
        tl = dict_get(s, "targets")
        if py_list_length(tl) != 1:
            return ""
        tg = py_list_ref(tl, 0)
    v = dict_get(s, "value")
    if nt(tg) != "Name" or v is None:
        return ""
    return f"(define {mangle_name(dict_get(tg, 'id'))} {translate_expr(v)})"

# ========== extern fn -> foreign-procedure（对应 generate_extern_ffi） ==========
# 类型表与 static_translate.py 的 TYPE_MAP 对齐；list[...] 一律是 C 指针。
FFI_TYPES = make_dict()
dict_set(FFI_TYPES, "int", "int")
dict_set(FFI_TYPES, "float", "float")
dict_set(FFI_TYPES, "double", "double")
dict_set(FFI_TYPES, "bool", "boolean")
dict_set(FFI_TYPES, "str", "string")
dict_set(FFI_TYPES, "ptr", "void*")

def ffi_type(t: str) -> str:
    # list[...] / 未知类型在 C ABI 上一律按指针
    if t in FFI_TYPES:
        return dict_get(FFI_TYPES, t)
    return "void*"

# 逻辑库名 -> soname：环境变量 STATICPY_LIB_<LIB> 优先，否则 lib<lib>.so
# （旧版还会查插件清单的 libs 映射；自举链路里插件清单不进 emit，故只保留这两条）
def ffi_soname(lib: str) -> str:
    env: str = os_getenv("STATICPY_LIB_" + str_upper(lib))
    if env != "":
        return env
    return "lib" + lib + ".so"

def emit_extern_ffi() -> str:
    n: int = extern_count()
    if n == 0:
        return ""
    out: str = ""
    loaded = py_list()
    i: int = 0
    while i < n:
        d = extern_get(i)
        lib: str = dict_get(d, "lib")
        if lib not in loaded:
            out = out + "\n(load-shared-object \"" + ffi_soname(lib) + "\")"
            loaded = py_list_append(loaded, lib)
        types: str = ""
        params = dict_get(d, "params")
        j: int = 0
        while j < py_list_length(params):
            pd = py_list_ref(params, j)
            if j > 0:
                types = types + " "
            types = types + ffi_type(dict_get(pd, "t"))
            j = j + 1
        out = out + "\n(define " + dict_get(d, "name") + "\n  (foreign-procedure \"" + dict_get(d, "name") + "\" (" + types + ") " + ffi_type(dict_get(d, "ret")) + "))"
        i = i + 1
    return out

# ========== 模块 ==========

def collect_sigs(body) -> int:
    """预扫描顶层函数签名（返回类型），供前向引用的类型推断使用（同旧版 collect_function_signatures）"""
    i: int = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        if nt(s) == "FunctionDef":
            dict_set(SIGS, dict_get(s, "name"), ann_str(dict_get(s, "returns")))
        i = i + 1
    return 0

def collect_imports(body) -> int:
    """预扫描 from ... import：登记裸名 -> 模块（同旧版 parse_imports）"""
    i: int = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        if nt(s) == "ImportFrom":
            mod: str = dict_get(s, "module")
            names = dict_get(s, "names")
            j: int = 0
            while j < py_list_length(names):
                al = py_list_ref(names, j)
                nm: str = dict_get(al, "name")
                if nm != "*":
                    asn = alias_asname(al)
                    if asn == "":
                        dict_set(IMPORTED, nm, mod)
                    else:
                        dict_set(IMPORTED, asn, mod)
                j = j + 1
        i = i + 1
    return 0

def emit_module(tree, src: str, lib_mode: int) -> str:
    src_set(src)
    out: str = ";; Source: " + src + "\n\n;; StaticPy functions"
    ffi: str = emit_extern_ffi()
    if ffi != "":
        out = ";; extern FFI functions" + ffi + "\n\n" + out
    body = dict_get(tree, "body")
    collect_sigs(body)
    collect_imports(body)
    i: int = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        t = nt(s)
        if t == "FunctionDef":
            out = out + "\n" + translate_function(s, src)
        elif t == "Assign" or t == "AnnAssign":
            d = top_level_define(s, t)
            if d != "":
                out = out + "\n" + d
        elif t == "Expr":
            out = out + "\n" + translate_expr(dict_get(s, "value"))
        i = i + 1
    if lib_mode == 1:
        return out + "\n\n;; Library mode: no (static_main) entry point"
    return out + "\n\n;; Entry point\n(static_main)"
