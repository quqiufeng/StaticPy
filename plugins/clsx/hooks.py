# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现：插件钩子必须能被「CPython 种子」
# 直接 import / 调用，环 2 自举翻译器不带插件（见 AGENTS.md 文件头约定）。

"""clsx —— 类特性补齐（语法扩展只走插件，核心语法已冻结）

内核（种子 + 环 2）的 class 子集只有三件事：单继承、记录字段、方法分派。
本插件用 `k.rewrite` 做**纯源码预处理**，把两件"常用但不在子集里"的写法降级成子集：

  ① 继承扁平化（单继承 / 多继承）
        class C(A, B):              →  class C:
                                       A、B 链上的字段声明 + 方法（含装饰器）内联进 C 的类体

     · 成员 = 方法（含 @staticmethod/@classmethod）+ 类级字段声明（默认值一并带过来）；
       就近覆盖（C 自己 > A 链 > B 链），同一个名字只留第一份。
     · C 没有 __init__ 时，内联最近祖先的 __init__（于是 C(...) 能收参数）。
     · `super().__init__(args)` 就地展开成基类 __init__ 的赋值（递归，形参换成实参）；
       基类没有 __init__ 时视为空操作。其余 `super().<name>()` 显式报错。
     · 为什么要扁平化：内核的 define-record-type 用 (parent Base) + 各自的
       `x: T` 声明，子类字段会**遮蔽**基类同名字段，而 `static_Base_m` 用的仍是
       `(Base-x self)` —— 基类方法作用在子类实例上会读到 #f。把祖先方法搬进 C，
       它们用的就是 `(C-x self)`，语义才和 Python 一致。
     · 显式拒绝（响亮失败，不静默出错）：
         - 内联来的方法写了 self.<f>，而 <f> 不在 C 的字段表 → 显式声明 `f: <type>`；
         - 方法里出现 super().<name>()（扁平化后没有基类，请直接写祖先的实现）。

  ② 类属性默认值（含继承来的）
        class Q:
            kind: int = 7          →  kind: int              （字段声明保留，值摘掉）
                                       __init__ 里注入 self.kind = 7
        class Q:
            tag = "hi"             →  tag: str               （无注解：按字面量补 int/float/str/bool）

     · 生效顺序 = Python 语义：**最近的类**（C → 基类链）的默认值赢；
       若 C 的 __init__ 自己给该字段赋过值，则不注入（赋值赢）。
     · 无 __init__ 的类会被合成一个，只为承载默认值。

  ③ 方法当值（`p.twice` / `P.twice`）不需要本插件：内核 translate_attribute 已对齐种子。

实现要点：**两个 pass，每个 pass 都重新 ast.parse 当前文本**。行号只在单个 pass 内有效，
跨 pass 复用行号会让"插入行"把后续编辑挤歪（第一版就栽在这）。

用法：
    python3 staticpy/static_translate.py --plugins core,clsx prog.static.py
    STATICPY_PLUGINS=core,clsx bash staticpy/static_build_comfycli.sh prog.static.py prog
    bash plugins/clsx/check.sh        # 回归（用例生成到 ~/iso_gen/clsx-check/）
"""
import ast
import re

_COMPOUND = (ast.If, ast.For, ast.While, ast.Try, ast.With,
             ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)


# ---------------------------------------------------------------- 小工具
def _ty_from_literal(node):
    """无注解的类属性：按字面量补一个子集类型（推断不出返回 ""）"""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, float):
            return "float"
        if isinstance(node.value, str):
            return "str"
    return ""


def _reindent(text, col, indent):
    """把一段源码整体左移 col 列，再统一压到 indent 缩进"""
    out = []
    for ln in text.split("\n"):
        out.append(ln[col:] if ln[:col].strip() == "" else ln.lstrip())
    return "\n".join(indent + ln if ln.strip() else "" for ln in out)


def _src(code, node, indent):
    """取节点源码（含装饰器，原样重排到 indent）"""
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    parts = code.split("\n")[start - 1:node.end_lineno]
    if not parts:
        return ""
    return _reindent("\n".join(parts), node.col_offset, indent)


def _self_attrs(node):
    """方法里写到的 self.<attr> 名字集合"""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) \
                and sub.value.id == "self":
            out.add(sub.attr)
    return out


def _uses_super(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "super":
            return True
    return False


def _init_node(node):
    for st in node.body:
        if isinstance(st, ast.FunctionDef) and st.name == "__init__":
            return st
    return None


def _params(fn):
    return [a.arg for a in fn.args.args if a.arg not in ("self", "cls")]


def _subst_words(expr, params, arg_srcs):
    """把参数名当整词替换成实参源码（super().__init__ 展开用）"""
    for p, a in zip(params, arg_srcs):
        expr = re.sub(r"\b" + re.escape(p) + r"\b", lambda m, a=a: a, expr)
    return expr


def _is_super_init(st):
    if not isinstance(st, ast.Expr):
        return False
    v = st.value
    if not isinstance(v, ast.Call):
        return False
    f = v.func
    return isinstance(f, ast.Attribute) and f.attr == "__init__" \
        and isinstance(f.value, ast.Call) and isinstance(f.value.func, ast.Name) \
        and f.value.func.id == "super"


def _super_assign_text(code, classes, clsname, args_srcs):
    """展开 clsname.__init__ 的赋值（形参换成 args_srcs），遇到 super() 继续向下展开"""
    if clsname not in classes:
        raise SyntaxError("clsx: super().__init__() 展开时找不到类 " + clsname)
    init = _init_node(classes[clsname]["node"])
    if init is None:
        return ""
    params = _params(init)
    if len(params) != len(args_srcs):
        raise SyntaxError("clsx: super().__init__() 的实参个数与 " + clsname + ".__init__ 不一致")
    parts = []
    for st in init.body:
        if isinstance(st, (ast.Assign, ast.AnnAssign)):
            if isinstance(st, ast.Assign):
                if len(st.targets) != 1:
                    raise SyntaxError("clsx: " + clsname + ".__init__ 有链式赋值，无法展开")
                tgt = st.targets[0]
            else:
                tgt = st.target
            if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"):
                raise SyntaxError("clsx: " + clsname + ".__init__ 里有非 self.x 赋值，无法展开")
            if st.value is None:
                continue
            v = ast.get_source_segment(code, st.value) or ""
            parts.append("self." + tgt.attr + " = " + _subst_words(v, params, args_srcs))
        elif _is_super_init(st):
            sub_args = [_subst_words(ast.get_source_segment(code, a) or "", params, args_srcs)
                        for a in st.value.args]
            inner = _super_assign_text(code, classes, classes[clsname]["base"], sub_args)
            if inner:
                parts.append(inner)
        else:
            raise SyntaxError("clsx: " + clsname + ".__init__ 里有非赋值语句，展开 super() 时无法处理")
    return "; ".join(parts)


def _indent_of(text):
    return text[:len(text) - len(text.lstrip())]


def _scan(code):
    """收集类表：{类名: {node, base, members}}（只取第一个 Name 基类为 parent 链）"""
    tree = ast.parse(code)
    classes = {}
    for st in tree.body:
        if not isinstance(st, ast.ClassDef):
            continue
        base = ""
        for b in st.bases:
            if isinstance(b, ast.Name):
                base = b.id
                break
        mem = set()
        for s in st.body:
            if isinstance(s, ast.FunctionDef):
                mem.add(s.name)
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                mem.add(s.target.id)
            elif isinstance(s, ast.Assign) and len(s.targets) == 1 \
                    and isinstance(s.targets[0], ast.Name):
                mem.add(s.targets[0].id)
        classes[st.name] = {"node": st, "base": base, "members": mem}
    return classes


def _chain(classes, name):
    out, cur, guard = [], name, 0
    while cur in classes and guard < 32:
        out.append(cur)
        cur = classes[cur]["base"]
        guard += 1
    return out


def _assemble(lines, ed_line, ed_after):
    out = []
    for i, ln in enumerate(lines):
        out.append(ed_line.get(i, ln))
        for chunk in ed_after.get(i, []):
            out.append(chunk)
    return "\n".join(out)


# ---------------------------------------------------------------- pass ①：多继承（mixin）
def _pass_mixin(code):
    """`class C(A, B)` → `class C(A)` + 把 B 链的方法/类属性内联进 C 的类体

    内核支持的是**单继承原生记录**（`(parent A)`：槽位与访问器由父类共享）。
    Python 的多继承在记录模型里只能退化成"A 当真基类、其余当 mixin 内联"：
    - 方法：按 C→A 链→B 链的就近顺序，缺谁补谁（C 自己的同名方法不动）
    - 类属性：内联声明（`x: T = v`），默认值由 pass ② 统一注入
    - 非主基类的 `__init__`：明确报错（记录不能有两个父槽位）
    """
    try:
        classes = _scan(code)
        tree = ast.parse(code)
    except SyntaxError:
        return code                       # 让内核按原样报错
    if not classes:
        return code
    lines = code.split("\n")
    ed_line = {}
    ed_after = {}

    for st in tree.body:
        if not isinstance(st, ast.ClassDef):
            continue
        nm = st.name
        bases = [b.id for b in st.bases if isinstance(b, ast.Name)]
        if len(bases) < 2:
            continue                      # 单继承：内核原生处理，不碰
        own = set(classes[nm]["members"])
        fields = set(own)
        # 主基类链上的字段（继承来的，inlined 方法里可以直接用）
        for c in _chain(classes, bases[0]):
            for s in classes[c]["node"].body:
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    fields.add(s.target.id)
                elif isinstance(s, ast.FunctionDef) and s.name == "__init__":
                    fields |= _self_attrs(s)
        for s in st.body:
            if isinstance(s, ast.FunctionDef) and s.name == "__init__":
                fields |= _self_attrs(s)

        have = set(own)
        for c in _chain(classes, bases[0]):        # 主链已有的名字：mixin 不许覆盖
            for s in classes[c]["node"].body:
                if isinstance(s, ast.FunctionDef):
                    have.add(s.name)
                elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    have.add(s.target.id)

        body_indent = _indent_of(lines[st.body[0].lineno - 1])
        copied = []
        for base in bases[1:]:
            for c in _chain(classes, base):
                for s in classes[c]["node"].body:
                    if isinstance(s, ast.FunctionDef):
                        if s.name == "__init__":
                            raise SyntaxError(
                                "clsx: " + nm + " 的非主基类 " + c
                                + " 定义了 __init__；记录只有一条父槽位链，"
                                + "请把 " + nm + ".__init__ 显式写出来并手动初始化该部分")
                        if _uses_super(s):
                            raise SyntaxError(
                                "clsx: 内联 " + c + "." + s.name + " 进 " + nm
                                + " 时遇到 super()；请先展开 super")
                        if s.name in have:
                            continue
                        have.add(s.name)
                        bad = sorted(_self_attrs(s) - fields)
                        if bad:
                            raise SyntaxError(
                                "clsx: 内联 " + c + "." + s.name + " 时用了 self." + bad[0]
                                + "，但不在 " + nm + " 的字段表里；请在 " + nm
                                + " 类体中显式声明（如 " + bad[0] + ": int）")
                        copied.append(_src(code, s, body_indent))
                    elif isinstance(s, (ast.AnnAssign, ast.Assign)):
                        if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                            fld = s.target.id
                            ty = ast.get_source_segment(code, s.annotation) or "int"
                            val = ast.get_source_segment(code, s.value) if s.value is not None else None
                        elif isinstance(s, ast.Assign) and len(s.targets) == 1 \
                                and isinstance(s.targets[0], ast.Name):
                            fld = s.targets[0].id
                            ty = _ty_from_literal(s.value)
                            if ty == "":
                                continue                # 不认识的字面量：留给内核
                            val = ast.get_source_segment(code, s.value)
                        else:
                            continue
                        if fld in have:
                            continue
                        have.add(fld)
                        fields.add(fld)
                        line = body_indent + fld + ": " + ty
                        if val is not None:
                            line += " = " + val
                        copied.append(line)
        if copied:
            # 类头只留主基类；内联成员贴到类体末尾
            head = lines[st.lineno - 1].split("(", 1)[0] + "(" + bases[0] + "):"
            ed_line[st.lineno - 1] = head
            ed_after[st.end_lineno - 1] = copied

    if not ed_line and not ed_after:
        return code
    return _assemble(lines, ed_line, ed_after)


# ---------------------------------------------------------------- pass ②：super 展开
def _pass_super(code):
    """super().__init__(args) → 就地展开成基类 __init__ 的赋值（纯源码改写，幂等）

    内核现在用**原生记录继承**（`(parent Base)`，子类只声明自己新增的字段），
    父类方法与访问器在子类实例上直接可用，所以这里不再做继承扁平化；
    只剩一件子集外的事：显式调父类 `__init__`。
    """
    try:
        classes = _scan(code)
        tree = ast.parse(code)
    except SyntaxError:
        return code                       # 让内核按原样报错
    if not classes:
        return code
    lines = code.split("\n")
    ed_line = {}

    for st in tree.body:
        if not isinstance(st, ast.ClassDef):
            continue
        nm = st.name
        bases = [b.id for b in st.bases if isinstance(b, ast.Name)]
        if not bases:
            continue
        for s in st.body:
            if not isinstance(s, ast.FunctionDef) or not _uses_super(s):
                continue
            if s.name != "__init__":
                raise SyntaxError("clsx: " + nm + "." + s.name
                                  + " 里用了 super().<name>()；核心只展开了 super().__init__(...)，"
                                  + "其余请直接调用祖先的实现（如 Base.method(self, ...)）")
            for e in s.body:
                if not _is_super_init(e):
                    continue
                if getattr(e, "end_lineno", e.lineno) != e.lineno:
                    raise SyntaxError("clsx: " + nm
                                      + " 的 super().__init__() 跨多行，请写在一行里")
                args_srcs = [ast.get_source_segment(code, a) or "" for a in e.value.args]
                txt = _super_assign_text(code, classes, bases[0], args_srcs)
                if txt == "":
                    # 基类没有 __init__（只有类级默认值）→ 空操作，别把类体挖空
                    txt = "pass" if len(s.body) == 1 else ""
                ed_line[e.lineno - 1] = (_indent_of(lines[e.lineno - 1]) + txt) if txt else ""

    if not ed_line:
        return code
    out = _assemble(lines, ed_line, {})
    # 收尾自检：展开之后不该再残留 super()
    for st in ast.parse(out).body:
        if isinstance(st, ast.ClassDef) and _uses_super(st):
            raise SyntaxError("clsx: " + st.name + " 展开后仍残留 super()（内部错误）")
    return out


# ---------------------------------------------------------------- pass ③：类属性默认值
def _pass_defaults(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    lines = code.split("\n")
    ed_line = {}
    ed_after = {}

    for st in tree.body:
        if not isinstance(st, ast.ClassDef):
            continue
        nm = st.name
        decl = []                         # [(字段, 值源码)]，按类体内出现顺序（就近优先）
        seen = set()
        for s in st.body:
            if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                fld = s.target.id
                ty = ast.get_source_segment(code, s.annotation) or "int"
                if s.value is None:
                    continue
                v = ast.get_source_segment(code, s.value)
                if v is None:
                    continue
                if fld in seen:
                    continue
                seen.add(fld)
                decl.append((fld, v))
                ed_line[s.lineno - 1] = _indent_of(lines[s.lineno - 1]) + fld + ": " + ty
            elif isinstance(s, ast.Assign) and len(s.targets) == 1 \
                    and isinstance(s.targets[0], ast.Name):
                ty = _ty_from_literal(s.value)
                if ty == "":
                    continue              # 不认识的字面量：留给内核（本来就被忽略）
                fld = s.targets[0].id
                v = ast.get_source_segment(code, s.value)
                if v is None or fld in seen:
                    continue
                seen.add(fld)
                decl.append((fld, v))
                ed_line[s.lineno - 1] = _indent_of(lines[s.lineno - 1]) + fld + ": " + ty
        if not decl:
            continue

        init = _init_node(st)
        assigned = _self_attrs(init) if init is not None else set()
        inject = [(f, v) for f, v in decl if f not in assigned]
        if not inject:
            continue
        text = "; ".join("self." + f + " = " + v for f, v in inject)
        if init is not None:
            first = init.body[0]
            simple = (not isinstance(first, _COMPOUND)
                      and first is not init
                      and getattr(first, "end_lineno", first.lineno) == first.lineno
                      and first.lineno - 1 not in ed_line)
            bi = first.lineno - 1
            if simple:
                t = lines[bi]
                ed_line[bi] = _indent_of(t) + text + "; " + t.lstrip()
            else:
                ed_after.setdefault(bi - 1, []).append(_indent_of(lines[bi]) + text)
        else:
            last = st.body[-1]
            bi = getattr(last, "end_lineno", last.lineno) - 1   # 插在类体最后一行之后
            ed_after.setdefault(bi, []).append(
                _indent_of(lines[st.body[0].lineno - 1]) + "def __init__(self): " + text)

    if not ed_line and not ed_after:
        return code
    return _assemble(lines, ed_line, ed_after)


# ---------------------------------------------------------------- 主流程
def class_features(code):
    """多继承内联 + 类属性默认值 + super().__init__ 展开 → 子集写法（幂等）"""
    code = _pass_mixin(code)
    code = _pass_defaults(code)
    code = _pass_super(code)
    return code


def register(k):
    k.rewrite(class_features)
