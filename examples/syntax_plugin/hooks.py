"""语法扩展插件模板（插件是唯一的语法扩展入口，核心语法已冻结）。

可用的四个钩子，全部在 register(k) 里注册：

  k.rewrite(fn)          源码级预处理，在所有解析之前；改源码别改行数（行号=错误定位）
  k.expr(NodeType, fn)   表达式：返回 Scheme 字符串，返回 None = 交回内核
  k.stmt(NodeType, fn)   语句：同上；顶层与函数体内都会派发
  k.infer(fn)            类型推断：返回 "int"/"float"/"str"/... 或 None

回调签名：fn(node, kernel)；递归翻译子节点必须用 kernel.api["translate_expr"]，
不要 import static_translate（循环 import）。
"""
import ast

# ---------------------------------------------------------------- rewrite
def until_to_while(code):
    """`until cond:` → `while not (cond):`（逐行改写，行号不变）"""
    out = []
    for line in code.split("\n"):
        s = line.lstrip()
        if s.startswith("until ") and s.rstrip().endswith(":"):
            ind = line[:len(line) - len(s)]
            out.append(f"{ind}while not ({s[len('until '):].rstrip()[:-1]}):")
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- expr
def twice(node, kernel):
    """`twice(x)` → `(* 2 x)`（不认识的形状一律还回内核）"""
    if not (isinstance(node.func, ast.Name) and node.func.id == "twice"
            and len(node.args) == 1):
        return None
    return f"(* 2 {kernel.api['translate_expr'](node.args[0])})"


# ---------------------------------------------------------------- stmt
def tagged_assign(node, kernel):
    """`TAG = <expr>` 顶层赋值：示例如何接管语句并自己产 define"""
    if not (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "TAG"):
        return None
    value = kernel.api["translate_expr"](node.value)
    return f";; [syntax_plugin] tagged assign\n(define TAG {value})"


# ---------------------------------------------------------------- infer
def infer_twice(node):
    """告诉下游 `twice(x)` 恒为 int，类型推断才不会降级到通用路径"""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id == "twice":
        return "int"
    return None


def register(k):
    k.rewrite(until_to_while)
    k.expr(ast.Call, twice)
    k.stmt(ast.Assign, tagged_assign)
    k.infer(infer_twice)
