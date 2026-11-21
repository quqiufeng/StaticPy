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

RESERVED = ("and apply assoc assq assv begin boolean? call-with-current-continuation "
            "call-with-values call/cc case char? complex? cond define delay do dynamic-wind else "
            "eq? equal? eqv? eval exists filter fold-left fold-right for for-each force if integer? "
            "lambda let let* letrec letrec* list? map member memq memv not null? number? or pair? "
            "procedure? quasiquote quote real? set! string? symbol? then unless unquote "
            "unquote-splicing until values vector? when while ")

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
    if nm == "py_float_repr":
        return "py-float-repr"
    return nm

def is_prelude_fn(nm: str) -> bool:
    # 文件自己定义的同名函数优先（同种子：name not in FUNCTION_SIGS）
    if dict_get(SIGS, nm) is not None:
        return False
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

def ir_present(v) -> int:
    """IR 可选项是否存在：None 和哨兵 "\x00N" 都算「没有」"""
    if v is None:
        return 0
    if isinstance(v, str) and v == PY_NONE:
        return 0
    return 1

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

def tenv_set_ann(nm: str, t: str) -> int:
    """标注（AnnAssign/形参）写类型，并记为「标注得来」"""
    tenv_set(nm, t)
    fr = tenv_frames()
    n = py_list_length(fr)
    if n > 0:
        dict_set(py_list_ref(fr, n - 1), "_ann:" + mangle_name(nm), 1)
    return 0

def tenv_is_ann(nm: str) -> int:
    """这个变量的类型是不是标注给的（标注才不许被推断覆盖，同种子 TYPE_ENV）"""
    fr = tenv_frames()
    k: str = "_ann:" + mangle_name(nm)
    j = py_list_length(fr) - 1
    while j >= 0:
        if dict_get(py_list_ref(fr, j), k) is not None:
            return 1
        j = j - 1
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
    if dict_get(SIGS, name) is not None:
        return ""
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
    if t == "List" or t == "ListComp" or t == "SetComp" or t == "GeneratorExp":
        return "list"
    if t == "DictComp":
        return "dict"
    if t == "Subscript":
        vt = infer_expr_type(dict_get(n, "value"))
        if vt == "list":
            return "Any"
        if str_starts_with(vt, "list["):
            return str_slice(vt, 5, str_length(vt) - 1)
        if str_starts_with(vt, "vector["):
            return str_slice(vt, 7, str_length(vt) - 1)
        if vt == "str":
            return "str"
        return ""
    if t == "Tuple":
        elts = dict_get(n, "elts")
        all_list: int = 1
        any_list: int = 0
        any_type: int = 0
        i: int = 0
        while i < py_list_length(elts):
            et = infer_expr_type(py_list_ref(elts, i))
            if et != "":
                any_type = 1
            if str_starts_with(et, "list"):
                any_list = 1
            else:
                all_list = 0
            i = i + 1
        if all_list == 1:
            return "list"
        if any_list == 1:
            return "tuple"
        if any_type == 1:
            return "tuple"
        return ""
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
            if class_known(nm) == 1:
                return nm
            return sig_ret(nm)
        if nt(f) == "Attribute":
            return module_ret(module_call_name(dict_get(f, "value"), dict_get(f, "attr")))
        return ""
    if t == "Attribute":
        # 方法当值（`f = p.twice` / `P.twice`）：类型记 "fn"，调用点据此不加 static_ 前缀
        recv = dict_get(n, "value")
        owner = ""
        if nt(recv) == "Name" and class_known(dict_get(recv, "id")) == 1:
            owner = dict_get(recv, "id")
        else:
            owner = resolve_expr_class(recv)
        if owner != "" and member_hit(owner, dict_get(n, "attr")) is not None:
            return "fn"
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
            tenv_set_ann(dict_get(a, "arg"), t)
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
                    tenv_set_ann(dict_get(tgt, "id"), a)
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
            # 与旧版一致：for 目标只登记裸 Name（元组目标由 for-each 的 lambda 绑定）
            if nt(dict_get(s, "target")) == "Name":
                names = names_add(names, dict_get(dict_get(s, "target"), "id"))
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
        lo = dict_get(slc, "lower")
        if lo is not None and nt(lo) != "":
            start = translate_expr(lo)
        up = dict_get(slc, "upper")
        end: str = ""
        if up is None or nt(up) == "":
            if vt == "str":
                end = "(string-length " + value + ")"
            elif str_starts_with(vt, "list["):
                end = "(tagged-array-len " + value + ")"
            else:
                end = "(vector-length " + value + ")"
        else:
            end = translate_expr(up)
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
        # tuple 是独立记录类型（repr 为 (..)），下标统一走 py-get
        return "(py-get " + value + " " + idx + ")"
    if vt == "list":
        return "(py-list-ref " + value + " " + idx + ")"
    if str_starts_with(vt, "vector["):
        return "(vector-ref " + value + " " + idx + ")"
    if str_starts_with(vt, "list["):
        return "(vector-ref " + value + " " + idx + ")"
    if vt == "str":
        # 单下标取字符：不能展开成 slice-string（负下标会被算成 (fx+ -1 1)=0）
        return "(py-str-ref " + value + " " + idx + ")"
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
    """f-string -> (string-append ...)，插值用 (py-str e)（同旧版：CPython f-string 走 str()）"""
    vs = dict_get(n, "values")
    ps = py_list()
    j: int = 0
    while j < py_list_length(vs):
        e = py_list_ref(vs, j)
        if nt(e) == "FormattedValue":
            ps = py_list_append(ps, "(py-str " + translate_expr(dict_get(e, "value")) + ")")
        elif nt(e) == "Constant":
            ps = py_list_append(ps, translate_expr(e))
        else:
            ps = py_list_append(ps, "\"\"")
        j = j + 1
    if py_list_length(ps) == 1:
        return py_list_ref(ps, 0)
    return "(string-append " + jn(ps) + ")"

IR_FIELDS = (
    " value name operand func args "
    "cond_expr then_body else_body var stop body "
    "params param_types ret op left right ty "
)

COMP_STATE = {"uid": 0}

def comp_next_uid() -> int:
    """推导式唯一编号（同种子 itertools.count(1)）"""
    COMP_STATE["uid"] = COMP_STATE["uid"] + 1
    return COMP_STATE["uid"]

def comp_bind(target, elt: str) -> str:
    """解包绑定串：[(name, expr), ...] -> "(a e) (b (py-unpack e 1))" """
    out: str = ""
    if nt(target) == "Name":
        return "(" + mangle_name(dict_get(target, "id")) + " " + elt + ")"
    if nt(target) == "Tuple" or nt(target) == "List":
        elts = dict_get(target, "elts")
        i: int = 0
        while i < py_list_length(elts):
            e = py_list_ref(elts, i)
            if nt(e) == "Name":
                if out != "":
                    out = out + " "
                out = out + "(" + mangle_name(dict_get(e, "id")) + " (py-unpack " + elt + " " + str(i) + "))"
            i = i + 1
    return out

def translate_comprehension(gens, elt: str, kind: str) -> str:
    """[e for ...] / {k:v for ...} / {e for ...} / (e for ...)

    嵌套 named-let，累加器 __acc 逐层显式传递；迭代源统一走 py-iter->list。
    """
    n_gen: int = py_list_length(gens)
    if n_gen == 0:
        return "(py-list " + elt + ")"
    uid: int = comp_next_uid()
    us: str = str(uid)
    body: str = "(cons " + elt + " __acc)"
    idx: int = n_gen - 1
    while idx >= 0:
        g = py_list_ref(gens, idx)
        isx: str = str(idx)
        it: str = "__it" + us + "_" + isx
        nn: str = "__n" + us + "_" + isx
        ii: str = "__i" + us + "_" + isx
        el: str = "__e" + us + "_" + isx
        nm: str = "loop" + us + "_" + isx
        adv: str = "(" + nm + " (+ " + ii + " 1) __acc)"
        cur: str = "(" + nm + " (+ " + ii + " 1) " + body + ")"
        ifs = dict_get(g, "ifs")
        k: int = py_list_length(ifs) - 1
        while k >= 0:
            cur = "(if " + translate_expr(py_list_ref(ifs, k)) + " " + cur + " " + adv + ")"
            k = k - 1
        binds: str = "(" + el + " (list-ref " + it + " " + ii + "))"
        extra: str = comp_bind(dict_get(g, "target"), el)
        if extra != "":
            binds = binds + " " + extra
        acc: str = "__acc"
        if idx == 0:
            acc = "'()"
        body = ("(let* ((" + it + " (py-iter->list " + translate_expr(dict_get(g, "iter")) + "))"
                + " (" + nn + " (length " + it + ")))"
                + " (let " + nm + " ((" + ii + " 0) (__acc " + acc + "))"
                + " (if (>= " + ii + " " + nn + ") __acc"
                + " (let* (" + binds + ") " + cur + "))))")
        idx = idx - 1
    if kind == "dict":
        return ("(let* ((__pairs" + us + " (reverse " + body + ")) (__d" + us + " (make-dict)))"
                + " (for-each (lambda (__p) (dict-set! __d" + us + " (car __p) (cdr __p)))"
                + " __pairs" + us + ")"
                + " __d" + us + ")")
    if kind == "set":
        return ("(list->py-list (reverse (fold-left"
                + " (lambda (__a __x) (if (member __x __a) __a (cons __x __a)))"
                + " '() (reverse " + body + "))))")
    if kind == "gen":
        return "(list->vector (reverse " + body + "))"
    return "(list->py-list (reverse " + body + "))"

def tensor_attr_fn(at: str) -> str:
    """张量无参属性 -> 运行时查询（同旧版 TENSOR_ATTR_FN）"""
    if at == "dtype":
        return "torch-tensor-dtype"
    if at == "shape":
        return "torch-tensor-shape"
    if at == "ndim":
        return "torch-tensor-ndim"
    if at == "T":
        return "torch-tensor-transpose-all"
    return ""

def translate_attribute(n) -> str:
    """x.attr 当值用（顺序与旧版 Attribute 分支一致；class/张量分支这里没有）"""
    at = dict_get(n, "attr")
    rv = dict_get(n, "value")
    # 模块常量/函数取值：math.pi -> (pi)，time.time -> (clock)
    mv: str = module_value_name(n)
    if mv != "":
        # 模块常量/一等函数取值：math.pi -> pi（裸名，同旧版直接返回表值）
        return mv
    # 张量无参属性：a.shape -> (torch-tensor-shape a)
    ta: str = tensor_attr_fn(at)
    if ta != "":
        return "(" + ta + " " + translate_expr(rv) + ")"
    if nt(rv) == "Name":
        vn = mangle_name(dict_get(rv, "id"))
        if at == "append":
            return "(py-list-append " + vn
        if at == "length":
            return "(py-list-length " + vn + ")"
        if at == "ref" or at == "__getitem__":
            return "(py-list-ref " + vn
        if at == "isinstance":
            return "(ir-tag? " + vn
    if nt(rv) == "Name":
        vt = tenv_get(dict_get(rv, "id"))
        if class_known(vt) == 1:
            own = class_field_owner(vt, at)
            if own != "":
                return "(" + own + "-" + at + " " + mangle_name(dict_get(rv, "id")) + ")"
            # 方法当值用：p.twice -> static_Owner_twice（同种子 _member_hit）
            mh = member_hit(vt, at)
            if mh is not None:
                return "static_" + dict_get(mh, "owner") + "_" + at
        # self.x -> (Owner-x self)，Owner 为字段所属类（含继承链）；同种子 try_class_attr
        if dict_get(rv, "id") == "self" and class_known(cur_class_get()) == 1:
            own = class_field_owner(cur_class_get(), at)
            if own != "":
                return "(" + own + "-" + at + " self)"
            mh2 = member_hit(cur_class_get(), at)
            if mh2 is not None:
                return "static_" + dict_get(mh2, "owner") + "_" + at
        # 类名取值：P.twice -> static_Owner_twice
        if class_known(dict_get(rv, "id")) == 1:
            mh3 = member_hit(dict_get(rv, "id"), at)
            if mh3 is not None:
                return "static_" + dict_get(mh3, "owner") + "_" + at
    value = translate_expr(rv)
    # 推断类接收者的方法当值用（同种子 try_class_attr 第三段）
    rc: str = resolve_expr_class(rv)
    if rc != "":
        ow2 = class_field_owner(rc, at)
        if ow2 != "":
            return "(" + ow2 + "-" + at + " " + value + ")"
        mh4 = member_hit(rc, at)
        if mh4 is not None:
            return "static_" + dict_get(mh4, "owner") + "_" + at
    if at == "copy":
        return "(dict-copy " + value + ")"
    # IR 节点字段：expr.value -> (ir-field expr 'value)
    if str_contains(IR_FIELDS, " " + at + " "):
        return "(ir-field " + value + " '" + at + ")"
    return "(" + at + " " + value + ")"

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
    if t == "List" or t == "Set":
        return "(py-list " + elems_text(dict_get(n, "elts")) + ")"
    if t == "ListComp" or t == "SetComp" or t == "GeneratorExp":
        kind2: str = "list"
        if t == "SetComp":
            kind2 = "set"
        if t == "GeneratorExp":
            kind2 = "gen"
        return translate_comprehension(dict_get(n, "generators"), translate_expr(dict_get(n, "elt")), kind2)
    if t == "DictComp":
        pair: str = "(cons " + translate_expr(dict_get(n, "key")) + " " + translate_expr(dict_get(n, "value")) + ")"
        return translate_comprehension(dict_get(n, "generators"), pair, "dict")
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
    if t == "Attribute":
        return translate_attribute(n)
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
    if py_list_length(ops) > 1 or py_list_length(coms) > 1:
        # 链式比较：旧版就发这个占位形（bug-for-bug 对齐）
        return f"(and {translate_expr(ln)} ... cmp)"
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
    # 其余（Invert / UAdd …）与旧版一致：<OpName> 直译，不做语义改写
    return f"({op} {translate_expr(e)})"

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
        # class 成员调用优先（同种子：try_class_call 在容器方法之前）
        cc: str = try_class_call(n)
        if cc != "":
            return cc
        # 模块函数：random.seed(7) -> (random_seed 7)；os.path.join -> (join ..)
        mfn: str = module_call_name(rv, at)
        if mfn != "":
            kw: str = ""
            kws = dict_get(n, "keywords")
            if kws is not None:
                ki: int = 0
                while ki < py_list_length(kws):
                    k = py_list_ref(kws, ki)
                    if dict_get(k, "arg") is not None:
                        if kw != "":
                            kw = kw + " "
                        kw = kw + translate_expr(dict_get(k, "value"))
                    ki = ki + 1
            if kw != "":
                if a != "":
                    return "(" + mfn + " " + a + " " + kw + ")"
                return "(" + mfn + " " + kw + ")"
            return "(" + mfn + " " + a + ")"
        mfbn: str = module_fallback_name(rv, at)
        if mfbn != "":
            # 兜底路径丢关键字实参（同旧版 OS_MAP / * _MAP 分支）
            if a != "":
                return "(" + mfbn + " " + a + ")"
            return "(" + mfbn + ")"
        # 不可变 list 模型：lst.append(x) -> (set! lst (py-list-append lst x))
        if at == "append" and nt(rv) == "Name" and py_list_length(al) == 1:
            vn = mangle_name(dict_get(rv, "id"))
            return f"(set! {vn} (py-list-append {vn} {a}))"
        if at == "copy" and py_list_length(al) == 0:
            return "(dict-copy " + translate_expr(rv) + ")"
        if str_contains(CONTAINER_METHODS, " " + at + " "):
            # .get 定参快路：不走 rest 打包（同旧版）
            if at == "get" and (py_list_length(al) == 1 or py_list_length(al) == 2):
                if py_list_length(al) == 1:
                    fast: str = "py-m-get2"
                else:
                    fast = "py-m-get3"
                return str_replace(f"({fast} {translate_expr(rv)} {a})", "  ", " ")
            return f"(py-m-{at} {translate_expr(rv)} {a})"
        # 未知对象的属性调用：content.splitlines() -> (content-splitlines)
        # 与旧版一致：通用属性调用不展开实参
        return f"({translate_expr(rv)}-{at})"
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
        # 表达式位置（for 头由 block_for 单独化 do 循环）
        return f"(py-range->list {a})"
    if nm == "int":
        return f"(exact (round {a}))"
    if nm == "float":
        return f"(inexact {a})"
    if nm == "bool":
        return f"(py-truthy {a})"
    if nm == "abs":
        return f"(abs {a})"
    if nm == "exit":
        return f"(exit_program {a})"
    if nm == "isinstance":
        al = dict_get(n, "args")
        if py_list_length(al) == 2:
            c = py_list_ref(al, 1)
            x0 = translate_expr(py_list_ref(al, 0))
            if nt(c) == "Name":
                return f"(ir-tag? {x0} '{dict_get(c, 'id')})"
            return f"(ir-tag? {x0} {translate_expr(c)})"
        return f"(ir-tag? {a})"
    # 内建迭代/聚合（同旧版：sum/min/max/sorted/enumerate/zip/any/all/pow）
    if nm == "sum":
        return f"(py-sum {a})"
    if nm == "min" or nm == "max":
        return "(" + "py-" + nm + " " + a + ")"
    if nm == "sorted":
        al2 = dict_get(n, "args")
        if py_list_length(al2) > 0:
            first: str = translate_expr(py_list_ref(al2, 0))
            kval: str = "#f"
            rval: str = "#f"
            kws = dict_get(n, "keywords")
            if kws is not None:
                ki2: int = 0
                while ki2 < py_list_length(kws):
                    k2 = py_list_ref(kws, ki2)
                    if dict_get(k2, "arg") == "key":
                        kval = translate_expr(dict_get(k2, "value"))
                    if dict_get(k2, "arg") == "reverse":
                        rval = translate_expr(dict_get(k2, "value"))
                    ki2 = ki2 + 1
            return f"(py-sorted {first} {kval} {rval})"
    if nm == "enumerate":
        return f"(py-enumerate {a})"
    if nm == "zip":
        return f"(py-zip {a})"
    if nm == "any":
        return f"(py-any {a})"
    if nm == "all":
        return f"(py-all {a})"
    if is_prelude_fn(nm):
        return f"({scheme_name(nm)} {a})"
    if is_param(nm):
        return f"({mangle_name(nm)} {a})"
    _cinfo = dict_get(CLASSES, nm)
    if _cinfo is not None:
        # 类构造：Point(1.0, 2.0) -> (make-Point 1.0 2.0) / (static_Point …)
        return emit_class_call(nm, _cinfo, dict_get(n, "args"))
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
    if nt(tg) == "Tuple":
        # 元组解构：a, b = expr -> (let ((__tmp_N expr)) (set! a (py-get __tmp_N 0)) …)
        tmp: str = "__tmp_" + str(py_list_length(exprs))
        tmp_val: str = translate_expr(v)
        if nt(v) == "Tuple":
            tmp_val = "(py-tuple " + elems_text(dict_get(v, "elts")) + ")"
        binds: str = ""
        elts = dict_get(tg, "elts")
        k: int = 0
        while k < py_list_length(elts):
            e = py_list_ref(elts, k)
            if nt(e) == "Name":
                if binds != "":
                    binds = binds + " "
                binds = binds + f"(set! {mangle_name(dict_get(e, 'id'))} (py-get {tmp} {k}))"
            k = k + 1
        return py_list_append(exprs, f"(let (({tmp} {tmp_val})) {binds})")
    if nt(tg) == "Name":
        nm = dict_get(tg, "id")
        iv = infer_expr_type(v)
        # 已有标注就别覆盖：`items: list[Box] = [...]` 的推断只有 "list"，
        # 覆盖掉就丢了元素类型（`items[0].n` 会退化成 `(n …)`）——同种子
        if iv != "" and tenv_is_ann(nm) == 0:
            tenv_set(nm, iv)
        return py_list_append(exprs, f"(set! {mangle_name(nm)} {translate_expr(v)})")
    if nt(tg) == "Attribute":
        # self.x = v -> (Cls-x-set! self v)；obj.x = v -> (Owner-x-set! obj v)
        # （同种子 try_field_set：先认 self，再按 resolve_expr_class 推静态类型）
        obj = dict_get(tg, "value")
        attr: str = dict_get(tg, "attr")
        if nt(obj) == "Name" and dict_get(obj, "id") == "self" and cur_class_get() != "":
            owner = class_field_owner(cur_class_get(), attr)
            if owner != "":
                return py_list_append(exprs, "(" + owner + "-" + attr + "-set! self " + translate_expr(v) + ")")
            return py_list_append(exprs, ";; " + t)
        rc: str = resolve_expr_class(obj)
        if rc != "":
            owner2: str = class_field_owner(rc, attr)
            if owner2 != "":
                return py_list_append(exprs, "(" + owner2 + "-" + attr + "-set! " + translate_expr(obj) + " " + translate_expr(v) + ")")
        return py_list_append(exprs, ";; " + t)
    if nt(tg) == "Subscript":
        # d[k] = v / a[i] = v -> py-set! 统一分派（dict / list / str 都对）
        return py_list_append(exprs, f"(py-set! {translate_expr(dict_get(tg, 'value'))} {translate_expr(dict_get(tg, 'slice'))} {translate_expr(v)})")
    return py_list_append(exprs, ";; " + t)

def block_delete(s) -> str:
    """del d[k] / del a[i] -> (begin (py-del! …) …)；del 变量 -> (set! v #f)"""
    tg = dict_get(s, "targets")
    parts: str = ""
    i: int = 0
    while i < py_list_length(tg):
        t = py_list_ref(tg, i)
        if nt(t) == "Subscript":
            one = f"(py-del! {translate_expr(dict_get(t, 'value'))} {translate_expr(dict_get(t, 'slice'))})"
        elif nt(t) == "Name":
            one = f"(set! {mangle_name(dict_get(t, 'id'))} #f)"
        else:
            one = ";; del: untranslated target"
        if i > 0:
            parts = parts + " "
        parts = parts + one
        i = i + 1
    if parts == "":
        return "(void)"
    return "(begin " + parts + ")"

def block_try(s, lvl: int) -> str:
    """try/except -> (guard (e (else <handler>)) <body>)"""
    body_scheme: str = jn(translate_block(dict_get(s, "body"), lvl))
    handler_body: str = "(void)"
    hs = dict_get(s, "handlers")
    if py_list_length(hs) > 0:
        handler_body = jn(translate_block(dict_get(py_list_ref(hs, 0), "body"), lvl))
    return f"(guard (e (else {handler_body})) {body_scheme})"

def block_raise(s) -> str:
    """raise X(..) -> (error 'X msg)"""
    exc = dict_get(s, "exc")
    if nt(exc) == "Call" and nt(dict_get(exc, "func")) == "Name":
        msg: str = ""
        ar = dict_get(exc, "args")
        if py_list_length(ar) > 0:
            msg = translate_expr(py_list_ref(ar, 0))
        return "(error '" + dict_get(dict_get(exc, "func"), "id") + " " + msg + ")"
    if nt(exc) == "Name":
        return "(error '" + dict_get(exc, "id") + " \"raised\")"
    return "(error 'raise \"raised\")"

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
        elif t == "FunctionDef":
            # 嵌套函数：就地 (define (static_X ..) ..)（Chez 内部 define，可闭包外层变量）
            exprs = py_list_append(exprs, translate_function(s, src_get()))
        elif t == "Delete":
            exprs = py_list_append(exprs, block_delete(s))
        elif t == "With":
            # with 在 block 内简化为直接执行 body（同旧版）
            sub = translate_block(dict_get(s, "body"), lvl)
            j: int = 0
            while j < py_list_length(sub):
                exprs = py_list_append(exprs, py_list_ref(sub, j))
                j = j + 1
        elif t == "Try":
            # try/except 语法糖：guard 捕获异常（同旧版）
            exprs = py_list_append(exprs, block_try(s, lvl))
        elif t == "Raise":
            exprs = py_list_append(exprs, block_raise(s))
        elif t == "Assert":
            msg: str = "\"assertion failed\""
            if dict_get(s, "msg") is not None:
                msg = translate_expr(dict_get(s, "msg"))
            exprs = py_list_append(exprs, f"(if (not {translate_expr(dict_get(s, 'test'))}) (error 'assert {msg}))")
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
    # for a, b in <iter>：元素按下标取（tuple/pair/vector 统一 py-get）
    if nt(tg) == "Tuple" or nt(tg) == "List":
        elts = dict_get(tg, "elts")
        all_name: int = 1
        binds: str = ""
        i: int = 0
        while i < py_list_length(elts):
            e = py_list_ref(elts, i)
            if nt(e) != "Name":
                all_name = 0
            else:
                if i > 0:
                    binds = binds + " "
                binds = binds + "(" + mangle_name(dict_get(e, "id")) + f" (py-get __e {i}))"
            i = i + 1
        if all_name == 1 and py_list_length(elts) > 0:
            return f"(for-each (lambda (__e) (let ({binds}) {bs})) (py-items {translate_expr(it)}))"
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
        # 函数体顶层（lvl=1）走旧版函数体那条路径：py-iter-seq + vector-length；
        # 嵌套块走 emit_for_stmt：py-seq-len / py-seq-ref（统一 vector/glist/tagged/str）
        iter_name: str = dict_get(it, "id")
        if lvl == 1:
            return (f"(let* ((__iter (py-iter-seq {iter_name})) (__n (vector-length __iter))) "
                    f"(do ((__i 0 (+ __i 1))) ((>= __i __n)) "
                    f"(let (({nm} (vector-ref __iter __i))) {bs})))")
        return (f"(let* ((__iter {iter_name}) (__n (py-seq-len __iter))) "
                f"(do ((__i 0 (+ __i 1))) ((>= __i __n)) "
                f"(let (({nm} (py-seq-ref __iter __i))) {bs})))")
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

def params_of_skip(n, skip: int) -> str:
    """形参串，可跳过前导 skip 个（首参确实是 self/cls 时才跳，同种子）"""
    ps = dict_get(dict_get(n, "args"), "args")
    if skip > 0 and py_list_length(ps) > 0:
        f0 = dict_get(py_list_ref(ps, 0), "arg")
        if f0 != "self" and f0 != "cls":
            skip = 0
    out: str = ""
    i: int = skip
    while i < py_list_length(ps):
        if i > skip:
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
    return function_def(n, src, "static_" + dict_get(n, "name"))

def function_def(n, src: str, full: str) -> str:
    """函数体 -> (define (<full> ..) ..)；类方法用同一套（name 换前缀）"""
    return function_def_skip(n, src, full, 0)

def function_def_skip(n, src: str, full: str, skip: int) -> str:
    """skip = 定义里要丢掉的前导形参个数（@classmethod/@staticmethod 的 self/cls）"""
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
    return hdr + f"(define ({full} {params_of_skip(n, skip)})\n{txt})"

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

# ====== 模块属性表（对齐旧版 BUILTIN_MODULES / NESTED_MODULES）======
def mod_attr(mod: str, attr: str) -> str:
    """mod.attr -> Scheme 函数名；未登记返回空串（同旧版模块别名解析）"""
    if mod == "cuda" and attr == "gemm":
        return "cuda-gemm"
    if mod == "json" and attr == "dumps":
        return "json_dumps"
    if mod == "json" and attr == "loads":
        return "parse_json"
    if mod == "la" and attr == "eigvals":
        return "la-eigvals"
    if mod == "la" and attr == "solve":
        return "la-solve"
    if mod == "la" and attr == "svd":
        return "la-svd"
    if mod == "math" and attr == "abs":
        return "abs"
    if mod == "math" and attr == "acos":
        return "acos"
    if mod == "math" and attr == "asin":
        return "asin"
    if mod == "math" and attr == "atan":
        return "atan"
    if mod == "math" and attr == "atan2":
        return "atan2"
    if mod == "math" and attr == "ceil":
        return "ceil"
    if mod == "math" and attr == "cos":
        return "cos"
    if mod == "math" and attr == "cosh":
        return "cosh"
    if mod == "math" and attr == "e":
        return "e"
    if mod == "math" and attr == "exp":
        return "exp"
    if mod == "math" and attr == "floor":
        return "floor"
    if mod == "math" and attr == "fmod":
        return "fmod"
    if mod == "math" and attr == "log":
        return "log"
    if mod == "math" and attr == "log10":
        return "log10"
    if mod == "math" and attr == "log2":
        return "log2"
    if mod == "math" and attr == "pi":
        return "pi"
    if mod == "math" and attr == "pow":
        return "pow"
    if mod == "math" and attr == "round":
        return "round"
    if mod == "math" and attr == "sin":
        return "sin"
    if mod == "math" and attr == "sinh":
        return "sinh"
    if mod == "math" and attr == "sqrt":
        return "sqrt"
    if mod == "math" and attr == "tan":
        return "tan"
    if mod == "math" and attr == "tanh":
        return "tanh"
    if mod == "nn" and attr == "Sequential":
        return "nn-Sequential"
    if mod == "nn" and attr == "batch_norm1d":
        return "nn-batch-norm1d"
    if mod == "nn" and attr == "batch_norm2d":
        return "nn-batch-norm2d"
    if mod == "nn" and attr == "call":
        return "nn-call"
    if mod == "nn" and attr == "conv2d":
        return "nn-conv2d"
    if mod == "nn" and attr == "flatten":
        return "nn-flatten"
    if mod == "nn" and attr == "linear":
        return "nn-linear"
    if mod == "nn" and attr == "parameters":
        return "nn-parameters"
    if mod == "nn" and attr == "relu":
        return "nn-relu"
    if mod == "nn" and attr == "sigmoid":
        return "nn-sigmoid"
    if mod == "nn" and attr == "tanh":
        return "nn-tanh"
    if mod == "np" and attr == "abs":
        return "np-abs"
    if mod == "np" and attr == "arange":
        return "np-arange"
    if mod == "np" and attr == "argmax":
        return "np-argmax"
    if mod == "np" and attr == "array":
        return "np-array"
    if mod == "np" and attr == "clip":
        return "np-clip"
    if mod == "np" and attr == "concatenate":
        return "np-concatenate"
    if mod == "np" and attr == "copy":
        return "np-copy"
    if mod == "np" and attr == "daxpy":
        return "np-daxpy"
    if mod == "np" and attr == "dot":
        return "np-dot"
    if mod == "np" and attr == "exp":
        return "np-exp"
    if mod == "np" and attr == "gemm":
        return "np-gemm"
    if mod == "np" and attr == "gemv":
        return "np-gemv"
    if mod == "np" and attr == "linspace":
        return "np-linspace"
    if mod == "np" and attr == "matmul":
        return "np-gemm"
    if mod == "np" and attr == "max":
        return "np-max"
    if mod == "np" and attr == "mean":
        return "np-mean"
    if mod == "np" and attr == "min":
        return "np-min"
    if mod == "np" and attr == "ones":
        return "np-ones"
    if mod == "np" and attr == "scal":
        return "np-scal"
    if mod == "np" and attr == "sqrt":
        return "np-sqrt"
    if mod == "np" and attr == "sum":
        return "np-sum"
    if mod == "np" and attr == "zeros":
        return "np-zeros"
    if mod == "os" and attr == "getcwd":
        return "os_cwd"
    if mod == "os" and attr == "getenv":
        return "os_getenv"
    if mod == "os" and attr == "listdir":
        return "os_list_dir"
    if mod == "os" and attr == "mkdir":
        return "os_mkdir"
    if mod == "os" and attr == "remove":
        return "os_delete_file"
    if mod == "os" and attr == "rename":
        return "os_move_file"
    if mod == "os" and attr == "rmdir":
        return "os_rmdir"
    if mod == "os" and attr == "system":
        return "os_shell"
    if mod == "os.path" and attr == "exists":
        return "os_file_exists"
    if mod == "os.path" and attr == "getsize":
        return "os_file_size"
    if mod == "random" and attr == "choice":
        return "random_choice"
    if mod == "random" and attr == "randint":
        return "random_randint"
    if mod == "random" and attr == "random":
        return "random_float"
    if mod == "random" and attr == "seed":
        return "random_seed"
    if mod == "random" and attr == "uniform":
        return "random_uniform"
    if mod == "time" and attr == "sleep":
        return "sleep"
    if mod == "time" and attr == "strftime":
        return "format_time"
    if mod == "time" and attr == "time":
        return "clock"
    if mod == "torch" and attr == "abs":
        return "torch-abs"
    if mod == "torch" and attr == "adam":
        return "torch-adam"
    if mod == "torch" and attr == "adamw":
        return "torch-adamw"
    if mod == "torch" and attr == "add":
        return "torch-add"
    if mod == "torch" and attr == "argmax":
        return "torch-argmax"
    if mod == "torch" and attr == "argmax_dim":
        return "torch-argmax-dim"
    if mod == "torch" and attr == "available":
        return "torch-available"
    if mod == "torch" and attr == "avg_pool2d":
        return "torch-avg-pool2d"
    if mod == "torch" and attr == "backward":
        return "torch-backward"
    if mod == "torch" and attr == "batch_norm1d":
        return "torch-batch-norm1d"
    if mod == "torch" and attr == "batch_norm2d":
        return "torch-batch-norm2d"
    if mod == "torch" and attr == "bce_loss":
        return "torch-bce-loss"
    if mod == "torch" and attr == "bce_with_logits_loss":
        return "torch-bce-with-logits-loss"
    if mod == "torch" and attr == "cat":
        return "torch-cat"
    if mod == "torch" and attr == "clamp":
        return "torch-clamp"
    if mod == "torch" and attr == "clip_grad_norm":
        return "torch-clip-grad-norm"
    if mod == "torch" and attr == "clip_text_forward":
        return "torch-clip-text-forward"
    if mod == "torch" and attr == "clip_tokenizer_create":
        return "torch-clip-tokenizer-create"
    if mod == "torch" and attr == "clip_tokenizer_encode":
        return "torch-clip-tokenizer-encode"
    if mod == "torch" and attr == "clip_tokenizer_free":
        return "torch-clip-tokenizer-free"
    if mod == "torch" and attr == "clone":
        return "torch-clone"
    if mod == "torch" and attr == "color_convert":
        return "torch-color-convert"
    if mod == "torch" and attr == "controlnet_apply":
        return "torch-controlnet-apply"
    if mod == "torch" and attr == "controlnet_forward":
        return "torch-controlnet-forward"
    if mod == "torch" and attr == "conv2d":
        return "torch-conv2d"
    if mod == "torch" and attr == "cross_entropy":
        return "torch-cross-entropy"
    if mod == "torch" and attr == "cuda_is_available":
        return "torch-cuda-is-available"
    if mod == "torch" and attr == "ddpm_add_noise":
        return "torch-ddpm-add-noise"
    if mod == "torch" and attr == "ddpm_betas":
        return "torch-ddpm-betas"
    if mod == "torch" and attr == "detach":
        return "torch-detach"
    if mod == "torch" and attr == "div":
        return "torch-div"
    if mod == "torch" and attr == "empty":
        return "torch-empty"
    if mod == "torch" and attr == "eq":
        return "torch-eq"
    if mod == "torch" and attr == "exp":
        return "torch-exp"
    if mod == "torch" and attr == "flux_forward":
        return "torch-flux-forward"
    if mod == "torch" and attr == "fm_sigmas":
        return "torch-fm-sigmas"
    if mod == "torch" and attr == "fm_step":
        return "torch-fm-step"
    if mod == "torch" and attr == "from_raw":
        return "torch-from-raw"
    if mod == "torch" and attr == "gather":
        return "torch-gather"
    if mod == "torch" and attr == "ge":
        return "torch-ge"
    if mod == "torch" and attr == "gguf_free":
        return "torch-gguf-free"
    if mod == "torch" and attr == "gguf_load":
        return "torch-gguf-load"
    if mod == "torch" and attr == "gguf_load_tensor":
        return "torch-gguf-load-tensor"
    if mod == "torch" and attr == "gguf_load_tensor_by_name":
        return "torch-gguf-load-tensor-by-name"
    if mod == "torch" and attr == "gguf_tensor_count":
        return "torch-gguf-tensor-count"
    if mod == "torch" and attr == "gguf_tensor_name":
        return "torch-gguf-tensor-name"
    if mod == "torch" and attr == "grad":
        return "torch-grad"
    if mod == "torch" and attr == "gt":
        return "torch-gt"
    if mod == "torch" and attr == "has_grad":
        return "torch-has-grad"
    if mod == "torch" and attr == "image_composite":
        return "torch-image-composite"
    if mod == "torch" and attr == "image_crop":
        return "torch-image-crop"
    if mod == "torch" and attr == "image_resize":
        return "torch-image-resize"
    if mod == "torch" and attr == "image_resize_float":
        return "torch-image-resize-float"
    if mod == "torch" and attr == "index_select":
        return "torch-index-select"
    if mod == "torch" and attr == "is_cuda":
        return "torch-is-cuda"
    if mod == "torch" and attr == "jit_delete":
        return "torch-jit-delete"
    if mod == "torch" and attr == "jit_forward":
        return "torch-jit-forward"
    if mod == "torch" and attr == "jit_load":
        return "torch-jit-load"
    if mod == "torch" and attr == "l1_loss":
        return "torch-l1-loss"
    if mod == "torch" and attr == "le":
        return "torch-le"
    if mod == "torch" and attr == "linear":
        return "torch-linear"
    if mod == "torch" and attr == "load_image":
        return "torch-load-image"
    if mod == "torch" and attr == "log":
        return "torch-log"
    if mod == "torch" and attr == "log_softmax":
        return "torch-log-softmax"
    if mod == "torch" and attr == "lora_apply":
        return "torch-lora-apply"
    if mod == "torch" and attr == "lora_merge_into":
        return "torch-lora-merge-into"
    if mod == "torch" and attr == "lt":
        return "torch-lt"
    if mod == "torch" and attr == "manual_seed":
        return "torch-manual-seed"
    if mod == "torch" and attr == "matmul":
        return "torch-matmul"
    if mod == "torch" and attr == "max_dim":
        return "torch-max-dim"
    if mod == "torch" and attr == "max_pool2d":
        return "torch-max-pool2d"
    if mod == "torch" and attr == "mean":
        return "torch-mean"
    if mod == "torch" and attr == "mean_dim":
        return "torch-mean-dim"
    if mod == "torch" and attr == "min_dim":
        return "torch-min-dim"
    if mod == "torch" and attr == "mse_loss":
        return "torch-mse-loss"
    if mod == "torch" and attr == "mul":
        return "torch-mul"
    if mod == "torch" and attr == "multinomial":
        return "torch-multinomial"
    if mod == "torch" and attr == "neg":
        return "torch-neg"
    if mod == "torch" and attr == "nll_loss":
        return "torch-nll-loss"
    if mod == "torch" and attr == "numel":
        return "torch-numel"
    if mod == "torch" and attr == "ones":
        return "torch-ones"
    if mod == "torch" and attr == "optimizer_step":
        return "torch-optimizer-step"
    if mod == "torch" and attr == "optimizer_zero_grad":
        return "torch-optimizer-zero-grad"
    if mod == "torch" and attr == "pow":
        return "torch-pow"
    if mod == "torch" and attr == "randint":
        return "torch-randint"
    if mod == "torch" and attr == "randn":
        return "torch-randn"
    if mod == "torch" and attr == "relu":
        return "torch-relu"
    if mod == "torch" and attr == "reshape":
        return "torch-reshape"
    if mod == "torch" and attr == "safetensors_count":
        return "torch-safetensors-count"
    if mod == "torch" and attr == "safetensors_free":
        return "torch-safetensors-free"
    if mod == "torch" and attr == "safetensors_get_tensor_by_name":
        return "torch-safetensors-get-tensor-by-name"
    if mod == "torch" and attr == "safetensors_load":
        return "torch-safetensors-load"
    if mod == "torch" and attr == "safetensors_name":
        return "torch-safetensors-name"
    if mod == "torch" and attr == "safetensors_tensor":
        return "torch-safetensors-tensor"
    if mod == "torch" and attr == "sample_ddim":
        return "torch-sample-ddim"
    if mod == "torch" and attr == "sample_dpmpp_2m":
        return "torch-sample-dpmpp-2m"
    if mod == "torch" and attr == "sample_euler":
        return "torch-sample-euler"
    if mod == "torch" and attr == "sample_euler_ancestral":
        return "torch-sample-euler-ancestral"
    if mod == "torch" and attr == "sampler_sigmas":
        return "torch-sampler-sigmas"
    if mod == "torch" and attr == "save_image":
        return "torch-save-image"
    if mod == "torch" and attr == "save_state_dict":
        return "torch-save-state-dict"
    if mod == "torch" and attr == "sd_unet_forward":
        return "torch-sd-unet-forward"
    if mod == "torch" and attr == "sdxl_dual_clip":
        return "torch-sdxl-dual-clip"
    if mod == "torch" and attr == "sdxl_unet_forward":
        return "torch-sdxl-unet-forward"
    if mod == "torch" and attr == "set_requires_grad":
        return "torch-set-requires-grad"
    if mod == "torch" and attr == "sgd":
        return "torch-sgd"
    if mod == "torch" and attr == "sigmoid":
        return "torch-sigmoid"
    if mod == "torch" and attr == "softmax":
        return "torch-softmax"
    if mod == "torch" and attr == "sqrt":
        return "torch-sqrt"
    if mod == "torch" and attr == "squeeze":
        return "torch-squeeze"
    if mod == "torch" and attr == "stack":
        return "torch-stack"
    if mod == "torch" and attr == "sub":
        return "torch-sub"
    if mod == "torch" and attr == "sum":
        return "torch-sum"
    if mod == "torch" and attr == "sum_dim":
        return "torch-sum-dim"
    if mod == "torch" and attr == "t5_tokenizer_create":
        return "torch-t5-tokenizer-create"
    if mod == "torch" and attr == "t5_tokenizer_encode":
        return "torch-t5-tokenizer-encode"
    if mod == "torch" and attr == "t5_tokenizer_free":
        return "torch-t5-tokenizer-free"
    if mod == "torch" and attr == "tanh":
        return "torch-tanh"
    if mod == "torch" and attr == "tensor":
        return "torch-tensor"
    if mod == "torch" and attr == "tensor_int64":
        return "torch-tensor-int64"
    if mod == "torch" and attr == "to_cpu":
        return "torch-to-cpu"
    if mod == "torch" and attr == "to_cuda":
        return "torch-to-cuda"
    if mod == "torch" and attr == "to_dtype":
        return "torch-to-dtype"
    if mod == "torch" and attr == "to_list":
        return "torch-to-list"
    if mod == "torch" and attr == "transpose":
        return "torch-transpose"
    if mod == "torch" and attr == "unsqueeze":
        return "torch-unsqueeze"
    if mod == "torch" and attr == "vae_decode_tiled":
        return "torch-vae-decode-tiled"
    if mod == "torch" and attr == "vae_encode_tiled":
        return "torch-vae-encode-tiled"
    if mod == "torch" and attr == "where":
        return "torch-where"
    if mod == "torch" and attr == "zero_grad":
        return "torch-zero-grad"
    if mod == "torch" and attr == "zeros":
        return "torch-zeros"
    return ""

# ====== 裸模块名兜底表（对齐旧版 NUMPY_MAP / MATH_MAP / OS_MAP / ...）======
def mod_alias_attr(raw: str, attr: str) -> str:
    """裸模块名兜底：只登记与属性名不同的项（同旧版 *_MAP；相同则用属性名本身）"""
    if raw == "cuda" and attr == "gemm":
        return "cuda-gemm"
    if raw == "json" and attr == "dumps":
        return "json_dumps"
    if raw == "json" and attr == "loads":
        return "parse_json"
    if raw == "la" and attr == "eigvals":
        return "la-eigvals"
    if raw == "la" and attr == "solve":
        return "la-solve"
    if raw == "la" and attr == "svd":
        return "la-svd"
    if raw == "np" and attr == "abs":
        return "np-abs"
    if raw == "np" and attr == "arange":
        return "np-arange"
    if raw == "np" and attr == "argmax":
        return "np-argmax"
    if raw == "np" and attr == "array":
        return "np-array"
    if raw == "np" and attr == "clip":
        return "np-clip"
    if raw == "np" and attr == "concatenate":
        return "np-concatenate"
    if raw == "np" and attr == "copy":
        return "np-copy"
    if raw == "np" and attr == "daxpy":
        return "np-daxpy"
    if raw == "np" and attr == "dot":
        return "np-dot"
    if raw == "np" and attr == "exp":
        return "np-exp"
    if raw == "np" and attr == "gemm":
        return "np-gemm"
    if raw == "np" and attr == "gemv":
        return "np-gemv"
    if raw == "np" and attr == "linspace":
        return "np-linspace"
    if raw == "np" and attr == "matmul":
        return "np-gemm"
    if raw == "np" and attr == "max":
        return "np-max"
    if raw == "np" and attr == "mean":
        return "np-mean"
    if raw == "np" and attr == "min":
        return "np-min"
    if raw == "np" and attr == "ones":
        return "np-ones"
    if raw == "np" and attr == "scal":
        return "np-scal"
    if raw == "np" and attr == "sqrt":
        return "np-sqrt"
    if raw == "np" and attr == "sum":
        return "np-sum"
    if raw == "np" and attr == "zeros":
        return "np-zeros"
    if raw == "os" and attr == "getcwd":
        return "os_cwd"
    if raw == "os" and attr == "getenv":
        return "os_getenv"
    if raw == "os" and attr == "listdir":
        return "os_list_dir"
    if raw == "os" and attr == "mkdir":
        return "os_mkdir"
    if raw == "os" and attr == "remove":
        return "os_delete_file"
    if raw == "os" and attr == "rename":
        return "os_move_file"
    if raw == "os" and attr == "rmdir":
        return "os_rmdir"
    if raw == "os" and attr == "system":
        return "os_shell"
    if raw == "random" and attr == "choice":
        return "random_choice"
    if raw == "random" and attr == "randint":
        return "random_randint"
    if raw == "random" and attr == "random":
        return "random_float"
    if raw == "random" and attr == "seed":
        return "random_seed"
    if raw == "random" and attr == "uniform":
        return "random_uniform"
    if raw == "time" and attr == "strftime":
        return "format_time"
    if raw == "time" and attr == "time":
        return "clock"
    if raw == "torch" and attr == "add":
        return "torch-add"
    if raw == "torch" and attr == "available":
        return "torch-available"
    if raw == "torch" and attr == "cat":
        return "torch-cat"
    if raw == "torch" and attr == "cat_id":
        return "torch-cat-id"
    if raw == "torch" and attr == "causal_mask":
        return "torch-causal-mask"
    if raw == "torch" and attr == "clip_text_forward":
        return "torch-clip-text-forward"
    if raw == "torch" and attr == "clip_tokenizer_create":
        return "torch-clip-tokenizer-create"
    if raw == "torch" and attr == "clip_tokenizer_encode":
        return "torch-clip-tokenizer-encode"
    if raw == "torch" and attr == "clip_tokenizer_free":
        return "torch-clip-tokenizer-free"
    if raw == "torch" and attr == "clone":
        return "torch-clone"
    if raw == "torch" and attr == "color_convert":
        return "torch-color-convert"
    if raw == "torch" and attr == "controlnet_apply":
        return "torch-controlnet-apply"
    if raw == "torch" and attr == "controlnet_forward":
        return "torch-controlnet-forward"
    if raw == "torch" and attr == "conv2d":
        return "torch-conv2d"
    if raw == "torch" and attr == "cos":
        return "torch-cos"
    if raw == "torch" and attr == "ddpm_add_noise":
        return "torch-ddpm-add-noise"
    if raw == "torch" and attr == "ddpm_betas":
        return "torch-ddpm-betas"
    if raw == "torch" and attr == "empty":
        return "torch-empty"
    if raw == "torch" and attr == "flux_forward":
        return "torch-flux-forward"
    if raw == "torch" and attr == "fm_sigmas":
        return "torch-fm-sigmas"
    if raw == "torch" and attr == "fm_step":
        return "torch-fm-step"
    if raw == "torch" and attr == "gguf_free":
        return "torch-gguf-free"
    if raw == "torch" and attr == "gguf_load":
        return "torch-gguf-load"
    if raw == "torch" and attr == "gguf_load_tensor":
        return "torch-gguf-load-tensor"
    if raw == "torch" and attr == "gguf_load_tensor_by_name":
        return "torch-gguf-load-tensor-by-name"
    if raw == "torch" and attr == "gguf_tensor_count":
        return "torch-gguf-tensor-count"
    if raw == "torch" and attr == "gguf_tensor_name":
        return "torch-gguf-tensor-name"
    if raw == "torch" and attr == "image_composite":
        return "torch-image-composite"
    if raw == "torch" and attr == "image_crop":
        return "torch-image-crop"
    if raw == "torch" and attr == "image_resize":
        return "torch-image-resize"
    if raw == "torch" and attr == "image_resize_float":
        return "torch-image-resize-float"
    if raw == "torch" and attr == "index_select":
        return "torch-tensor-index-select"
    if raw == "torch" and attr == "jit_delete":
        return "torch-jit-delete"
    if raw == "torch" and attr == "jit_forward":
        return "torch-jit-forward"
    if raw == "torch" and attr == "jit_load":
        return "torch-jit-load"
    if raw == "torch" and attr == "last_argmax":
        return "torch-last-argmax"
    if raw == "torch" and attr == "load_image":
        return "torch-load-image"
    if raw == "torch" and attr == "lora_apply":
        return "torch-lora-apply"
    if raw == "torch" and attr == "lora_merge_into":
        return "torch-lora-merge-into"
    if raw == "torch" and attr == "matmul":
        return "torch-matmul"
    if raw == "torch" and attr == "mul":
        return "torch-mul"
    if raw == "torch" and attr == "narrow":
        return "torch-narrow"
    if raw == "torch" and attr == "neg":
        return "torch-tensor-neg"
    if raw == "torch" and attr == "ones":
        return "torch-ones"
    if raw == "torch" and attr == "outer":
        return "torch-outer"
    if raw == "torch" and attr == "randint":
        return "torch-randint"
    if raw == "torch" and attr == "reshape":
        return "torch-reshape"
    if raw == "torch" and attr == "rope_inv_freq":
        return "torch-rope-inv-freq"
    if raw == "torch" and attr == "rope_t":
        return "torch-rope-t"
    if raw == "torch" and attr == "rope_t_pos":
        return "torch-rope-t-pos"
    if raw == "torch" and attr == "rsqrt":
        return "torch-rsqrt"
    if raw == "torch" and attr == "safetensors_count":
        return "torch-safetensors-count"
    if raw == "torch" and attr == "safetensors_free":
        return "torch-safetensors-free"
    if raw == "torch" and attr == "safetensors_get_tensor_by_name":
        return "torch-safetensors-get-tensor-by-name"
    if raw == "torch" and attr == "safetensors_load":
        return "torch-safetensors-load"
    if raw == "torch" and attr == "safetensors_name":
        return "torch-safetensors-name"
    if raw == "torch" and attr == "safetensors_tensor":
        return "torch-safetensors-tensor"
    if raw == "torch" and attr == "sample_ddim":
        return "torch-sample-ddim"
    if raw == "torch" and attr == "sample_dpmpp_2m":
        return "torch-sample-dpmpp-2m"
    if raw == "torch" and attr == "sample_euler":
        return "torch-sample-euler"
    if raw == "torch" and attr == "sample_euler_ancestral":
        return "torch-sample-euler-ancestral"
    if raw == "torch" and attr == "sampler_sigmas":
        return "torch-sampler-sigmas"
    if raw == "torch" and attr == "save_image":
        return "torch-save-image"
    if raw == "torch" and attr == "save_state_dict":
        return "torch-save-state-dict"
    if raw == "torch" and attr == "sd_unet_forward":
        return "torch-sd-unet-forward"
    if raw == "torch" and attr == "sdxl_dual_clip":
        return "torch-sdxl-dual-clip"
    if raw == "torch" and attr == "sdxl_unet_forward":
        return "torch-sdxl-unet-forward"
    if raw == "torch" and attr == "sin":
        return "torch-sin"
    if raw == "torch" and attr == "softmax":
        return "torch-softmax"
    if raw == "torch" and attr == "sqrt":
        return "torch-sqrt"
    if raw == "torch" and attr == "sub":
        return "torch-sub"
    if raw == "torch" and attr == "t5_tokenizer_create":
        return "torch-t5-tokenizer-create"
    if raw == "torch" and attr == "t5_tokenizer_encode":
        return "torch-t5-tokenizer-encode"
    if raw == "torch" and attr == "t5_tokenizer_free":
        return "torch-t5-tokenizer-free"
    if raw == "torch" and attr == "tensor":
        return "torch-tensor"
    if raw == "torch" and attr == "tensor_ptr":
        return "torch-tensor-ptr-debug"
    if raw == "torch" and attr == "to_list":
        return "torch-to-list"
    if raw == "torch" and attr == "topk":
        return "torch-topk"
    if raw == "torch" and attr == "tpack_get":
        return "torch-tpack-get"
    if raw == "torch" and attr == "tpack_index":
        return "torch-tpack-index"
    if raw == "torch" and attr == "tpack_load":
        return "torch-tpack-load"
    if raw == "torch" and attr == "vae_decode_tiled":
        return "torch-vae-decode-tiled"
    if raw == "torch" and attr == "vae_encode_tiled":
        return "torch-vae-encode-tiled"
    if raw == "torch" and attr == "zeros":
        return "torch-zeros"
    return ""

MOD_RET_FLOAT = (" sin cos tan log log2 log10 exp sqrt abs pow fmod floor ceil round "
                 "sinh cosh tanh atan2 asin acos atan random_float random_uniform clock ")
MOD_RET_INT = " random_range random_randint random_int os_file_size "
MOD_RET_STR = " json_dumps os_cwd os_getenv http_get_simple "
MOD_RET_LISTF = " np-array np-zeros np-ones "

def module_ret(sn: str) -> str:
    """模块调用返回类型（同种子 infer_expr_type 的 Attribute 分支）"""
    if sn == "":
        return ""
    if str_contains(MOD_RET_FLOAT, " " + sn + " "):
        return "float"
    if str_contains(MOD_RET_INT, " " + sn + " "):
        return "int"
    if str_contains(MOD_RET_STR, " " + sn + " "):
        return "str"
    if str_contains(MOD_RET_LISTF, " " + sn + " "):
        return "list[float]"
    if sn == "torch-to-list":
        return "vector[float]"
    if sn == "torch-available":
        return "bool"
    if sn == "parse_json":
        return "dict"
    if sn == "os_file_exists":
        return "bool"
    if sn == "os_list_dir":
        return "list[str]"
    if str_starts_with(sn, "torch-") or sn == "torch-tensor":
        return "torch-tensor"
    return ""

MOD_ALIAS = make_dict()
MOD_KEYS = " np la torch nn cuda math random json time os urllib os.path "

def mod_key(name: str) -> str:
    """导入别名 -> 模块名（无导入但属内置模块名也认，同旧版 is_module_alias）"""
    m: str = dict_get(MOD_ALIAS, name)
    if m is not None:
        return m
    if str_contains(MOD_KEYS, " " + name + " "):
        return name
    return ""

MOD_FALLBACK = " np la torch nn cuda math random json time os os.path networkx nx scipy urllib "

def module_call_name(rv, attr: str) -> str:
    """调用点：<mod>.<attr> / <mod>.<mid>.<attr> -> Scheme 名（未登记返回空串）"""
    if nt(rv) == "Name":
        mk: str = mod_key(dict_get(rv, "id"))
        if mk == "":
            return ""
        return mod_attr(mk, attr)
    if nt(rv) == "Attribute" and nt(dict_get(rv, "value")) == "Name":
        top: str = mod_key(dict_get(dict_get(rv, "value"), "id"))
        if top == "":
            return ""
        return mod_attr(top + "." + dict_get(rv, "attr"), attr)
    return ""

def module_fallback_name(rv, attr: str) -> str:
    """未登记表项的模块调用：兜底用属性名本身（同旧版 *_MAP.get(attr, attr)）"""
    if nt(rv) == "Name":
        raw: str = dict_get(rv, "id")
        if str_contains(MOD_FALLBACK, " " + raw + " "):
            sn: str = mod_alias_attr(raw, attr)
            if sn != "":
                return sn
            return attr
        return ""
    if nt(rv) == "Attribute" and nt(dict_get(rv, "value")) == "Name":
        key: str = dict_get(dict_get(rv, "value"), "id") + "." + dict_get(rv, "attr")
        if str_contains(MOD_FALLBACK, " " + key + " "):
            sn2: str = mod_alias_attr(key, attr)
            if sn2 != "":
                return sn2
            return attr
    return ""

def module_value_name(n) -> str:
    """取值点：<mod>.<attr> -> (scheme 常量/函数名)；未登记返回空串"""
    if nt(n) != "Attribute":
        return ""
    rv = dict_get(n, "value")
    if nt(rv) != "Name":
        return ""
    mk: str = mod_key(dict_get(rv, "id"))
    if mk == "":
        return ""
    return mod_attr(mk, dict_get(n, "attr"))

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
        if nt(s) == "Import":
            names = dict_get(s, "names")
            j0: int = 0
            while j0 < py_list_length(names):
                al0 = py_list_ref(names, j0)
                nm0: str = dict_get(al0, "name")
                asn0 = alias_asname(al0)
                if asn0 == "":
                    dict_set(MOD_ALIAS, nm0, nm0)
                else:
                    dict_set(MOD_ALIAS, asn0, nm0)
                j0 = j0 + 1
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

# ========== class（记录类型）支持 ==========
# 对齐种子 static_translate.py 的 analyze_class / translate_class_methods：
#   字段     -> define-record-type 的 mutable 字段（self.x 可读写）
#   __init__ -> static_<Cls>___init__(self, …)：就地 set! 字段并返回 self
#   构造     -> 平凡 __init__ 直接 (make-<Cls> …)；否则 (static_<Cls> …) 内套 __init__
#   方法     -> static_<Cls>_<m>(self, …)，零运行时开销
# 记录字段读取 / isinstance 已由 translate_attribute（IR_FIELDS）与 translate_call 的
# ir-tag? 覆盖；成员分派见下方 try_class_call / member_hit / resolve_expr_class：
#   self.x / obj.x  -> (Owner-x obj)   （字段所属类，含继承链）
#   obj.m()/Cls.m() -> (static_Owner_m …)（实例方法带 self；@classmethod/@staticmethod 去 self/cls）
#   super().__init__(…) -> (static_<Base>___init__ self …)（就地填字段）
# 仍然不做（遇到再补）：方法值（不带调用的 obj.m）、多继承、类属性访问。
CLASSES = make_dict()
CUR_CLASS = make_dict()

def cur_class_set(s: str) -> int:
    dict_set(CUR_CLASS, "v", s)
    return 0

def cur_class_get() -> str:
    v = dict_get(CUR_CLASS, "v")
    if v is None:
        return ""
    return v

def cls_join(l, sep: str) -> str:
    out: str = ""
    i: int = 0
    while i < py_list_length(l):
        if i > 0:
            out = out + sep
        out = out + py_list_ref(l, i)
        i = i + 1
    return out

def self_assign_field(st) -> str:
    """self.x = v / self.x: T = v 的目标字段名；否则空串（同种子 _self_assign_target）"""
    t = nt(st)
    if t != "Assign" and t != "AnnAssign":
        return ""
    tg = dict_get(st, "target")
    if t == "Assign":
        tl = dict_get(st, "targets")
        if py_list_length(tl) != 1:
            return ""
        tg = py_list_ref(tl, 0)
    if nt(tg) != "Attribute":
        return ""
    bv = dict_get(tg, "value")
    if nt(bv) != "Name" or dict_get(bv, "id") != "self":
        return ""
    return dict_get(tg, "attr")

def field_add(fs, seen, f: str):
    """按声明顺序登记字段（去重）；同种子 add_field"""
    if f == "" or dict_get(seen, f) is not None:
        return fs
    dict_set(seen, f, 1)
    return py_list_append(fs, f)

def class_known(nm: str) -> int:
    if nm == "":
        return 0
    if dict_get(CLASSES, nm) is None:
        return 0
    return 1

def drop_self_params(init):
    """__init__ 形参去掉前导 self（不是 self 就原样保留）"""
    ps = param_names(init)
    out = py_list()
    i: int = 0
    while i < py_list_length(ps):
        if i == 0 and py_list_ref(ps, 0) == "self":
            i = i + 1
        else:
            out = py_list_append(out, py_list_ref(ps, i))
            i = i + 1
    return out

def is_trivial_init(info) -> int:
    """__init__ 是否等价于 (make-Cls 参数...)（同种子 _is_trivial_init）"""
    init = dict_get(info, "init")
    if init is None:
        return 1
    args = dict_get(init, "args")
    if py_list_length(dict_get(args, "defaults")) > 0:
        return 0
    if ir_present(dict_get(args, "vararg")) == 1 or ir_present(dict_get(args, "kwarg")) == 1:
        return 0
    if py_list_length(dict_get(args, "kwonlyargs")) > 0:
        return 0
    ps = drop_self_params(init)
    cf = dict_get(info, "ctor_fields")
    if py_list_length(ps) != py_list_length(cf):
        return 0
    sts = py_list()
    ib = dict_get(init, "body")
    i: int = 0
    while i < py_list_length(ib):
        st = py_list_ref(ib, i)
        # 文档字符串之类的裸常量表达式不参与判定
        if nt(st) == "Expr" and nt(dict_get(st, "value")) == "Constant":
            i = i + 1
        else:
            sts = py_list_append(sts, st)
            i = i + 1
    if py_list_length(sts) != py_list_length(cf):
        return 0
    i = 0
    while i < py_list_length(sts):
        st = py_list_ref(sts, i)
        if self_assign_field(st) != py_list_ref(cf, i):
            return 0
        rhs = dict_get(st, "value")
        if nt(rhs) != "Name" or dict_get(rhs, "id") != py_list_ref(ps, i):
            return 0
        i = i + 1
    return 1

def collect_classes(body) -> int:
    """两趟登记：① 字段/基类/__init__ ② 继承后的完整字段表与构造策略"""
    i: int = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        if nt(s) == "ClassDef":
            nm = dict_get(s, "name")
            info = make_dict()
            fs = py_list()
            seen = make_dict()
            init = None
            base: str = ""
            methods = make_dict()
            cms = make_dict()
            sms = make_dict()
            ftypes = make_dict()
            bs = dict_get(s, "bases")
            if py_list_length(bs) > 0 and nt(py_list_ref(bs, 0)) == "Name":
                base = dict_get(py_list_ref(bs, 0), "id")
            sb = dict_get(s, "body")
            j: int = 0
            while j < py_list_length(sb):
                it = py_list_ref(sb, j)
                if nt(it) == "FunctionDef" and dict_get(it, "name") == "__init__":
                    init = it
                    ib = dict_get(it, "body")
                    k: int = 0
                    while k < py_list_length(ib):
                        st = py_list_ref(ib, k)
                        f = self_assign_field(st)
                        fs = field_add(fs, seen, f)
                        # self.x: T = v 的标注也记下（链式解析 o.box.n 要用）
                        if f != "" and nt(st) == "AnnAssign":
                            ft = ann_str(dict_get(st, "annotation"))
                            if ft != "" and dict_get(ftypes, f) is None:
                                dict_set(ftypes, f, ft)
                        k = k + 1
                elif nt(it) == "AnnAssign" and nt(dict_get(it, "target")) == "Name":
                    fnm: str = dict_get(dict_get(it, "target"), "id")
                    fs = field_add(fs, seen, fnm)
                    ft = ann_str(dict_get(it, "annotation"))
                    if ft != "" and dict_get(ftypes, fnm) is None:
                        dict_set(ftypes, fnm, ft)
                elif nt(it) == "FunctionDef":
                    # 方法分类（同种子 analyze_class）：@classmethod / @staticmethod / 实例方法
                    dn: str = dict_get(it, "name")
                    dk = deco_kind(it)
                    if dk == "classmethod":
                        dict_set(cms, dn, it)
                    elif dk == "staticmethod":
                        dict_set(sms, dn, it)
                    else:
                        dict_set(methods, dn, it)
                j = j + 1
            dict_set(info, "name", nm)
            dict_set(info, "node", s)
            dict_set(info, "fields", fs)
            dict_set(info, "base", base)
            dict_set(info, "init", init)
            dict_set(info, "methods", methods)
            dict_set(info, "classmethods", cms)
            dict_set(info, "staticmethods", sms)
            dict_set(info, "field_types", ftypes)
            dict_set(CLASSES, nm, info)
        i = i + 1
    i = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        if nt(s) == "ClassDef":
            info = dict_get(CLASSES, dict_get(s, "name"))
            cf = py_list()
            bl = py_list()
            base = dict_get(info, "base")
            if class_known(base) == 1:
                bl = dict_get(dict_get(CLASSES, base), "ctor_fields")
                k: int = 0
                while k < py_list_length(bl):
                    cf = py_list_append(cf, py_list_ref(bl, k))
                    k = k + 1
            fs = dict_get(info, "fields")
            k = 0
            while k < py_list_length(fs):
                cf = py_list_append(cf, py_list_ref(fs, k))
                k = k + 1
            # 同名字段只留第一份（父类在前）：扁平记录里重复声明会多出槽位
            uniq = py_list()
            mark = make_dict()
            k = 0
            while k < py_list_length(cf):
                fn = py_list_ref(cf, k)
                if dict_get(mark, fn) is None:
                    dict_set(mark, fn, 1)
                    uniq = py_list_append(uniq, fn)
                k = k + 1
            dict_set(info, "ctor_fields", uniq)
            # 记录用 Chez 原生继承：(parent Base) 共享父类槽位，子类只声明自己新增的字段
            own = py_list()
            k = 0
            while k < py_list_length(fs):
                fn = py_list_ref(fs, k)
                if py_list_has(bl, fn) == 0:
                    own = py_list_append(own, fn)
                k = k + 1
            dict_set(info, "record_fields", own)
            dict_set(info, "trivial", is_trivial_init(info))
        i = i + 1
    return 0

def emit_class_init(nm: str, init) -> str:
    """__init__ -> static_<Cls>___init__(self, …)：就地填字段并返回 self"""
    cur_class_set(nm)
    lines = py_list()
    ib = dict_get(init, "body")
    i: int = 0
    while i < py_list_length(ib):
        st = py_list_ref(ib, i)
        f = self_assign_field(st)
        if f != "" and dict_get(st, "value") is not None:
            owner: str = nm
            if py_list_has(dict_get(dict_get(CLASSES, nm), "record_fields"), f) == 0:
                owner = class_field_owner(nm, f)
            if owner == "":
                lines = py_list_append(lines, "  (void)")
            else:
                lines = py_list_append(
                    lines, "  (" + owner + "-" + f + "-set! self " + translate_expr(dict_get(st, "value")) + ")")
        else:
            tr = translate_block(py_list_append(py_list(), st), 1)
            if py_list_length(tr) > 0:
                lines = py_list_append(lines, "  " + py_list_ref(tr, 0))
        i = i + 1
    if py_list_length(lines) == 0:
        lines = py_list_append(lines, "  (void)")
    cur_class_set("")
    return "(define (static_" + nm + "___init__ " + params_of(init) + ")\n" + cls_join(lines, "\n") + "\n  self)"

def emit_class_ctor(nm: str, info, init) -> str:
    """非平凡 __init__ 的构造函数：make-Cls 占位后调 __init__"""
    cf = dict_get(info, "ctor_fields")
    blanks = py_list()
    i: int = 0
    while i < py_list_length(cf):
        blanks = py_list_append(blanks, "#f")
        i = i + 1
    make_call: str = "(make-" + nm + ")"
    if py_list_length(blanks) > 0:
        make_call = "(make-" + nm + " " + cls_join(blanks, " ") + ")"
    ps = py_list()
    raw = drop_self_params(init)
    i = 0
    while i < py_list_length(raw):
        ps = py_list_append(ps, mangle_name(py_list_ref(raw, i)))
        i = i + 1
    call: str = "(static_" + nm + "___init__ __m)"
    if py_list_length(ps) > 0:
        call = "(static_" + nm + "___init__ __m " + cls_join(ps, " ") + ")"
    return "(define (static_" + nm + " " + cls_join(ps, " ") + ")\n  (let ((__m " + make_call + "))\n    " + call + "))"

def emit_class_method(nm: str, m, src: str) -> str:
    """类中方法 -> static_<Cls>_<name>(self, …)"""
    cur_class_set(nm)
    skip: int = 0
    if deco_kind(m) != "method":
        skip = 1
    txt = function_def_skip(m, src, "static_" + nm + "_" + dict_get(m, "name"), skip)
    cur_class_set("")
    return txt

def emit_class(n, src: str) -> str:
    """class X(Base) -> define-record-type + __init__ + 构造 + 方法（同种子 translate_class）"""
    nm = dict_get(n, "name")
    info = dict_get(CLASSES, nm)
    fields = dict_get(info, "record_fields")
    base = dict_get(info, "base")
    out: str = ";; class " + nm
    parent: str = ""
    if class_known(base) == 1:
        out = out + "(" + base + ")"
        parent = " (parent " + base + ")"
    if py_list_length(fields) > 0:
        specs = py_list()
        i: int = 0
        while i < py_list_length(fields):
            specs = py_list_append(specs, "(mutable " + py_list_ref(fields, i) + ")")
            i = i + 1
        out = out + "\n(define-record-type " + nm + "\n  (fields " + cls_join(specs, " ") + ")" + parent + ")"
    else:
        out = out + "\n(define-record-type " + nm + " (fields)" + parent + ")"
    init = dict_get(info, "init")
    if init is not None:
        out = out + "\n" + emit_class_init(nm, init)
        if dict_get(info, "trivial") == 0:
            out = out + "\n" + emit_class_ctor(nm, info, init)
    # 方法输出顺序同种子：实例方法 → @classmethod → @staticmethod（只本类定义的）
    kinds = py_list()
    kinds = py_list_append(kinds, "method")
    kinds = py_list_append(kinds, "classmethod")
    kinds = py_list_append(kinds, "staticmethod")
    sb = dict_get(n, "body")
    ki: int = 0
    while ki < py_list_length(kinds):
        want = py_list_ref(kinds, ki)
        i = 0
        while i < py_list_length(sb):
            it = py_list_ref(sb, i)
            if nt(it) == "FunctionDef" and dict_get(it, "name") != "__init__":
                if deco_kind(it) == want:
                    out = out + "\n" + emit_class_method(nm, it, src)
            i = i + 1
        ki = ki + 1
    return out

def emit_class_call(nm: str, info, al) -> str:
    """Cls(...) -> (make-Cls …) 平凡构造 / (static_Cls …) 带 __init__（同种子 RECORD_TYPES 分支）"""
    args = py_list()
    i: int = 0
    while i < py_list_length(al):
        args = py_list_append(args, translate_expr(py_list_ref(al, i)))
        i = i + 1
    inner = cls_join(args, " ")
    if dict_get(info, "trivial") != 0:
        cf = dict_get(info, "ctor_fields")
        if cf is not None:
            while py_list_length(args) < py_list_length(cf):
                args = py_list_append(args, "#f")
            inner = cls_join(args, " ")
        if inner == "":
            return "(make-" + nm + ")"
        return "(make-" + nm + " " + inner + ")"
    if inner == "":
        return "(static_" + nm + ")"
    return "(static_" + nm + " " + inner + ")"

def class_field_owner(cls: str, f: str) -> str:
    """字段的声明者（决定访问器名 `Owner-f`）；同种子 _field_owner

    先看 record_fields（类自己声明的槽位）：子类只在 __init__ 里给继承字段赋值
    不算声明，否则会生成 `Dog-name-set!` 而记录里只有 `Animal-name-set!`。
    """
    cur = cls
    guard: int = 0
    while cur != "" and class_known(cur) == 1 and guard < 32:
        fs = dict_get(dict_get(CLASSES, cur), "record_fields")
        i: int = 0
        while i < py_list_length(fs):
            if py_list_ref(fs, i) == f:
                return cur
            i = i + 1
        cur = dict_get(dict_get(CLASSES, cur), "base")
        guard = guard + 1
    cur = cls
    guard = 0
    while cur != "" and class_known(cur) == 1 and guard < 32:
        fs = dict_get(dict_get(CLASSES, cur), "fields")
        i: int = 0
        while i < py_list_length(fs):
            if py_list_ref(fs, i) == f:
                return cur
            i = i + 1
        cur = dict_get(dict_get(CLASSES, cur), "base")
        guard = guard + 1
    return ""

def class_field_type(cls: str, f: str) -> str:
    """字段的类型标注（沿继承链找）；没有标注返回 ""（同种子 record_field_type）"""
    cur = cls
    guard: int = 0
    while cur != "" and class_known(cur) == 1 and guard < 32:
        ft = dict_get(dict_get(dict_get(CLASSES, cur), "field_types"), f)
        if ft is not None and ft != "":
            return ft
        cur = dict_get(dict_get(CLASSES, cur), "base")
        guard = guard + 1
    return ""

def deco_names(fn):
    """装饰器名列表（同种子 _decorator_names）"""
    out = py_list()
    dl = dict_get(fn, "decorator_list")
    if dl is None:
        return out
    i: int = 0
    while i < py_list_length(dl):
        d = py_list_ref(dl, i)
        if nt(d) == "Name":
            out = py_list_append(out, dict_get(d, "id"))
        elif nt(d) == "Attribute":
            out = py_list_append(out, dict_get(d, "attr"))
        i = i + 1
    return out

def deco_kind(fn) -> str:
    """方法种类：classmethod / staticmethod / method（同种子 analyze_class 分类）"""
    decos = deco_names(fn)
    if py_list_has(decos, "classmethod") == 1:
        return "classmethod"
    if py_list_has(decos, "staticmethod") == 1:
        return "staticmethod"
    return "method"

def py_list_has(l, v: str) -> int:
    i: int = 0
    while i < py_list_length(l):
        if py_list_ref(l, i) == v:
            return 1
        i = i + 1
    return 0

def py_list_cons(v: str, l):
    out = py_list()
    out = py_list_append(out, v)
    i: int = 0
    while i < py_list_length(l):
        out = py_list_append(out, py_list_ref(l, i))
        i = i + 1
    return out

def ir_call(fn: str, args) -> str:
    """(fn a b) 形式；空实参不出多余空格（同种子的 .replace(" )", ")")）"""
    if py_list_length(args) == 0:
        return "(" + fn + ")"
    return str_replace("(" + fn + " " + cls_join(args, " ") + ")", " )", ")")

def member_pack(kind: str, owner: str, node):
    d = make_dict()
    dict_set(d, "kind", kind)
    dict_set(d, "owner", owner)
    dict_set(d, "node", node)
    return d

def member_hit(cls: str, attr: str):
    """沿继承链找方法 → {kind, owner, node}；找不到 None（同种子 _member_hit）"""
    cur = cls
    guard: int = 0
    while cur != "" and class_known(cur) == 1 and guard < 32:
        info = dict_get(CLASSES, cur)
        v = dict_get(dict_get(info, "methods"), attr)
        if v is not None:
            return member_pack("method", cur, v)
        v = dict_get(dict_get(info, "classmethods"), attr)
        if v is not None:
            return member_pack("classmethod", cur, v)
        v = dict_get(dict_get(info, "staticmethods"), attr)
        if v is not None:
            return member_pack("staticmethod", cur, v)
        cur = dict_get(info, "base")
        guard = guard + 1
    return None

def resolve_expr_class(expr) -> str:
    """推断表达式所属类名；推断不出返回 ""（同种子 resolve_expr_class）"""
    if expr is None:
        return ""
    t = nt(expr)
    if t == "Name":
        nm = dict_get(expr, "id")
        if nm == "self":
            return cur_class_get()
        v = tenv_get(nm)
        if v == "":
            v = tenv_get(mangle_name(nm))
        if v != "" and class_known(v) == 1:
            return v
        return ""
    if t == "Call":
        fn = dict_get(expr, "func")
        if nt(fn) == "Name":
            fid = dict_get(fn, "id")
            if class_known(fid) == 1:
                return fid
            return ""
        if nt(fn) == "Attribute":
            owner = resolve_expr_class(dict_get(fn, "value"))
            if owner != "":
                hit = member_hit(owner, dict_get(fn, "attr"))
                if hit is not None:
                    mn = dict_get(hit, "node")
                    rt = dict_get(mn, "returns")
                    if rt is not None:
                        ret = ann_str(rt)
                        if class_known(ret) == 1:
                            return ret
            return ""
        return ""
    if t == "Attribute":
        # 链式属性：字段标注是类才继续（o.box.n -> Box 的字段）
        owner = resolve_expr_class(dict_get(expr, "value"))
        if owner != "":
            ft = class_field_type(owner, dict_get(expr, "attr"))
            if class_known(ft) == 1:
                return ft
        return ""
    if t == "Subscript":
        # 容器下标取元素：items[0].n / items[0].scaled() （同种子 _container_elem_class）
        bv = dict_get(expr, "value")
        if nt(bv) == "Name":
            elem = tenv_get(dict_get(bv, "id"))
            if str_starts_with(elem, "list["):
                elem = str_slice(elem, 5, str_length(elem) - 1)
                if class_known(elem) == 1:
                    return elem
        return ""
    return ""

def fill_defaults_s(mnode, args, skip: int):
    """调用点补默认实参（args 已是 IR 串）；同种子 _fill_defaults"""
    if mnode is None:
        return args
    anode = dict_get(mnode, "args")
    if anode is None:
        return args
    if ir_present(dict_get(anode, "vararg")) == 1 or ir_present(dict_get(anode, "kwarg")) == 1:
        return args
    np_ = py_list_length(param_names(mnode)) - skip
    na = py_list_length(args)
    if na >= np_:
        return args
    defs = dict_get(anode, "defaults")
    nd = 0
    if defs is not None:
        nd = py_list_length(defs)
    first = np_ - nd
    out = args
    i: int = na
    while i < np_:
        if i >= first:
            out = py_list_append(out, translate_expr(py_list_ref(defs, i - first)))
        else:
            out = py_list_append(out, "#f")
        i = i + 1
    return out

def try_class_call(n) -> str:
    """obj.m(..) / Cls.m(..) / self.m(..) / super().__init__(..) → 直接函数调用"""
    f = dict_get(n, "func")
    if nt(f) != "Attribute":
        return ""
    attr: str = dict_get(f, "attr")
    recv = dict_get(f, "value")
    tl = py_list()
    al = dict_get(n, "args")
    i: int = 0
    while i < py_list_length(al):
        tl = py_list_append(tl, translate_expr(py_list_ref(al, i)))
        i = i + 1
    kws = dict_get(n, "keywords")
    if kws is not None:
        ki: int = 0
        while ki < py_list_length(kws):
            k = py_list_ref(kws, ki)
            if dict_get(k, "arg") is not None:
                tl = py_list_append(tl, translate_expr(dict_get(k, "value")))
            ki = ki + 1
    # super().__init__(...) → 基类 __init__ 就地初始化
    if nt(recv) == "Call":
        rf = dict_get(recv, "func")
        if nt(rf) == "Name" and dict_get(rf, "id") == "super":
            cur = cur_class_get()
            if class_known(cur) == 1:
                base = dict_get(dict_get(CLASSES, cur), "base")
                if class_known(base) == 1:
                    fa = fill_defaults_s(dict_get(dict_get(CLASSES, base), "init"), tl, 1)
                    return ir_call("static_" + base + "___init__", py_list_cons("self", fa))
            return ""
    # 类名调用：Cls.m(..)
    if nt(recv) == "Name":
        rn = dict_get(recv, "id")
        if class_known(rn) == 1:
            hit = member_hit(rn, attr)
            if hit is not None:
                kind = dict_get(hit, "kind")
                skip: int = 1
                if kind == "staticmethod":
                    skip = 0
                fa = fill_defaults_s(dict_get(hit, "node"), tl, skip)
                return ir_call("static_" + dict_get(hit, "owner") + "_" + attr, fa)
            return ""
    # 实例调用：obj.m(...) / self.m(...)
    cls = resolve_expr_class(recv)
    if cls == "":
        return ""
    hit = member_hit(cls, attr)
    if hit is None:
        return ""
    kind = dict_get(hit, "kind")
    mnode = dict_get(hit, "node")
    fn_name: str = "static_" + dict_get(hit, "owner") + "_" + attr
    if kind == "staticmethod":
        return ir_call(fn_name, fill_defaults_s(mnode, tl, 0))
    if kind == "classmethod":
        return ir_call(fn_name, fill_defaults_s(mnode, tl, 1))
    return ir_call(fn_name, py_list_cons(translate_expr(recv), fill_defaults_s(mnode, tl, 1)))

def emit_module(tree, src: str, lib_mode: int) -> str:
    src_set(src)
    out: str = ";; Source: " + src + "\n\n;; StaticPy functions"
    ffi: str = emit_extern_ffi()
    if ffi != "":
        out = ";; extern FFI functions" + ffi + "\n\n" + out
    body = dict_get(tree, "body")
    collect_sigs(body)
    collect_imports(body)
    collect_classes(body)
    i: int = 0
    while i < py_list_length(body):
        s = py_list_ref(body, i)
        t = nt(s)
        if t == "FunctionDef":
            out = out + "\n" + translate_function(s, src)
        elif t == "ClassDef":
            out = out + "\n" + emit_class(s, src)
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
