# parse_diff.py — 对照端：CPython ast -> 与 parse_dump.static.py 完全一致的规范 dump
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边跑 CPython/原库，一边跑我们的产物，逐行/逐像素比对。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

import ast, sys

KIND_ROWS = [
    "Module:body,type_ignores",
    "FunctionDef:name,args,body,decorator_list,returns,type_comment,type_params",
    "ClassDef:name,bases,keywords,body,decorator_list,type_params",
    "Return:value", "Delete:targets", "Assign:targets,value",
    "AugAssign:target,op,value", "AnnAssign:target,annotation,value,simple",
    "For:target,iter,body,orelse,type_comment", "While:test,body,orelse",
    "If:test,body,orelse", "With:items,body,type_comment",
    "withitem:context_expr,optional_vars", "Raise:exc,cause",
    "Try:body,handlers,orelse,finalbody", "ExceptHandler:type,name,body",
    "Assert:test,msg", "Import:names", "ImportFrom:module,names,level",
    "alias:name,asname", "Global:names", "Nonlocal:names",
    "Pass:", "Break:", "Continue:", "Expr:value",
    "BoolOp:op,values", "BinOp:left,op,right", "UnaryOp:op,operand",
    "Lambda:args,body", "IfExp:test,body,orelse", "Dict:keys,values",
    "Set:elts", "ListComp:elt,generators", "SetComp:elt,generators",
    "DictComp:key,value,generators", "GeneratorExp:elt,generators",
    "comprehension:target,iter,ifs,is_async", "Compare:left,ops,comparators",
    "Call:func,args,keywords", "keyword:arg,value",
    "FormattedValue:value,conversion,format_spec", "JoinedStr:values",
    "Constant:value,kind", "Attribute:value,attr,ctx",
    "Subscript:value,slice,ctx", "Starred:value,ctx", "Name:id,ctx",
    "List:elts,ctx", "Tuple:elts,ctx", "Slice:lower,upper,step",
    "arg:arg,annotation,type_comment",
    "arguments:posonlyargs,args,vararg,kwonlyargs,kw_defaults,kwarg,defaults",
    "Load:", "Store:", "Del:", "And:", "Or:", "Add:", "Sub:", "Mult:",
    "MatMult:", "Div:", "Mod:", "Pow:", "LShift:", "RShift:", "BitOr:",
    "BitXor:", "BitAnd:", "FloorDiv:", "Invert:", "Not:", "UAdd:", "USub:",
    "Eq:", "NotEq:", "Lt:", "LtE:", "Gt:", "GtE:", "Is:", "IsNot:", "In:",
    "NotIn:", "Await:value", "NamedExpr:target,value",
]
FIELDS = dict(r.split(":", 1) for r in KIND_ROWS)
SKIP = {"type_comment": True}

def esc(s):
    out = ["'"]
    for ch in s:
        if ch == '\\':
            out.append('\\\\')
        elif ch == "'":
            out.append("\\'")
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        else:
            n = ord(ch)
            if 32 <= n <= 126:
                out.append(ch)
            elif n < 256:
                out.append('\\x%02x' % n)
            else:
                out.append('\\u%04x' % n)
    out.append("'")
    return ''.join(out)

def show_float(v):
    s = '%.17f' % v
    if '.' in s:
        while s.endswith('0') and not s.endswith('.0'):
            s = s[:-1]
    return s

def show_val(v):
    if isinstance(v, ast.AST):
        return show_node(v)
    if isinstance(v, list):
        return '[' + ', '.join(show_val(x) for x in v) + ']'
    if v is None:
        return 'None'
    if v is True:
        return 'True'
    if v is False:
        return 'False'
    if isinstance(v, str):
        return esc(v)
    if isinstance(v, bytes):
        return esc(v.decode('latin-1'))
    if isinstance(v, float):
        return show_float(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, complex):
        return esc(repr(v))
    if v is Ellipsis:
        return 'Ellipsis'
    return repr(v)

def show_node(n):
    tn = type(n).__name__
    spec = FIELDS.get(tn)
    if spec is None:
        raise SystemExit('unknown node type: ' + tn)
    if spec == '':
        return tn + '()'
    parts = []
    for fn in spec.split(','):
        fld = n._fields[spec.split(',').index(fn)]
        parts.append(fn + '=' + show_val(getattr(n, fld)))
    return tn + '(' + ', '.join(parts) + ')'

tree = ast.parse(open(sys.argv[1], encoding='utf-8').read())
print(show_node(tree))
