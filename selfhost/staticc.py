#!/usr/bin/env python3
from typing import Tuple

"""staticc.py — minimal StaticPy compiler written in StaticPy.

This compiler targets a tiny StaticPy subset whose semantics map directly
onto Chez Scheme.  The key invariant is:

    Every StaticPy construct must have an obvious, one-to-one Chez equivalent.

Input example (test_staticc_input.sp):

    def main () -> int
      let x int 10
      let y int 20
      (call print (+ x y))
      return 0
    end

Semantics:

    def f (p1 : t1 p2 : t2) -> rt
      body
    end
      =>  (define (f p1 p2) body-expr)

    let x ty expr
      =>  (let ((x expr)) ...)

    set x expr
      =>  (set! x expr)

    return expr
      =>  expr  (function value is the value of the body expression)

    if cond then-body else else-body end
      =>  (if cond then-expr else-expr)

    while cond body end
      =>  (let loop () (when cond body-expr (loop)))

    for i stop body end
      =>  (do ((i 0 (+ i 1))) ((>= i stop)) body-expr)

    (call f a b)
      =>  (f a b)

    (+ a b)
      =>  (fx+ a b)  /  (fl+ a b)  /  (string-append a b)  /  (+ a b)
          depending on the static type of the operands.
"""


# ---------- loud failure（最小核原则：不检查语义，但结构性失败必须响） ----------

def parse_fail(msg: str):
    print("staticc: error: " + msg)
    exit_program(1)


# ---------- tokenizer ----------


def is_digit(c):
    return c >= "0" and c <= "9"


def is_alpha(c):
    return (c >= "a" and c <= "z") or (c >= "A" and c <= "Z")


def is_alnum(c):
    return is_alpha(c) or is_digit(c) or c == "_" or c == "-" or c == ">" or c == "?" or c == "/" or c == "="


def tokenize(src: str):
    out = ""
    i = 0
    n = len(src)
    while i < n:
        c = src[i:i + 1]
        if c == " " or c == "\t" or c == "\n" or c == "\r":
            i = i + 1
        elif c == "#":
            while i < n and src[i:i + 1] != "\n":
                i = i + 1
        elif c == "\"":
            start = i
            i = i + 1
            while i < n and src[i:i + 1] != "\"":
                if src[i:i + 1] == "\\":
                    i = i + 2
                else:
                    i = i + 1
            i = i + 1
            out = out + src[start:i] + " "
        elif c == "-" and i + 1 < n and src[i + 1:i + 2] == ">":
            out = out + "-> "
            i = i + 2
        elif c == ">" and i + 1 < n and src[i + 1:i + 2] == "=":
            out = out + ">= "
            i = i + 2
        elif c == "<" and i + 1 < n and src[i + 1:i + 2] == "=":
            out = out + "<= "
            i = i + 2
        elif c == "=" and i + 1 < n and src[i + 1:i + 2] == "=":
            out = out + "== "
            i = i + 2
        elif c == "!" and i + 1 < n and src[i + 1:i + 2] == "=":
            out = out + "!= "
            i = i + 2
        elif c == "(" or c == ")":
            out = out + c + " "
            i = i + 1
        elif is_alnum(c):
            start = i
            while i < n and is_alnum(src[i:i + 1]):
                i = i + 1
            out = out + src[start:i] + " "
        else:
            out = out + c + " "
            i = i + 1
    return out


def next_token(tokens: str, pos: int):
    n = len(tokens)
    while pos < n and tokens[pos:pos + 1] == " ":
        pos = pos + 1
    if pos >= n:
        return "", pos
    start = pos
    # If the token starts with a double-quote, read until matching close.
    if tokens[pos:pos + 1] == "\"":
        pos = pos + 1
        while pos < n and tokens[pos:pos + 1] != "\"":
            if tokens[pos:pos + 1] == "\\":
                pos = pos + 2
            else:
                pos = pos + 1
        pos = pos + 1
    else:
        while pos < n and tokens[pos:pos + 1] != " ":
            pos = pos + 1
    return tokens[start:pos], pos


# ---------- IR ----------
class IRExpr:
    pass


class EConst(IRExpr):
    def __init__(self, value):
        self.value = value


class EVar(IRExpr):
    def __init__(self, name):
        self.name = name


class EBinop(IRExpr):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class EUnary(IRExpr):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class ECall(IRExpr):
    def __init__(self, func, args):
        self.func = func
        self.args = args


class IRStmt:
    pass


class SLet(IRStmt):
    def __init__(self, name, ty, value):
        self.name = name
        self.ty = ty
        self.value = value


class SSet(IRStmt):
    def __init__(self, name, value):
        self.name = name
        self.value = value


class SReturn(IRStmt):
    def __init__(self, value):
        self.value = value


class SExpr(IRStmt):
    def __init__(self, value):
        self.value = value


class SIf(IRStmt):
    def __init__(self, cond_expr, then_body, else_body):
        self.cond_expr = cond_expr
        self.then_body = then_body
        self.else_body = else_body


class SWhile(IRStmt):
    def __init__(self, cond_expr, body):
        self.cond_expr = cond_expr
        self.body = body


class SFor(IRStmt):
    def __init__(self, var, stop, body):
        self.var = var
        self.stop = stop
        self.body = body


class IRFunc:
    def __init__(self, name, params, param_types, ret, body):
        self.name = name
        self.params = params
        self.param_types = param_types
        self.ret = ret
        self.body = body


# ---------- list helpers (compatible with StaticPy runtime) ----------


def list_ref(lst: list, i):
    return lst[i]


def list_length(lst: list):
    return len(lst)


def list_append(lst: list, val):
    result = py_list_append(lst, val)
    return result


def list_append_str(lst: list[str], val: str) -> list[str]:
    result = py_list_append(lst, val)
    return result


def py_list_append(lst: list, val):
    result = lst + [val]
    return result


def str_join(parts: list, sep_str):
    result = ""
    i = 0
    n = len(parts)
    while i < n:
        if i == 0:
            result = parts[i]
        else:
            result = result + sep_str + parts[i]
        i = i + 1
    return result


def list_append_all(target: list, source):
    i = 0
    n = len(source)
    while i < n:
        target = list_append(target, list_ref(source, i))
        i = i + 1
    return target


def list_ref_range(lst: list, start, stop):
    result = []
    i = start
    while i < stop:
        result = list_append(result, list_ref(lst, i))
        i = i + 1
    return result


def func_params_to_str(params: list):
    result = ""
    i = 0
    n = len(params)
    while i < n:
        if i == 0:
            result = params[i]
        else:
            result = result + " " + params[i]
        i = i + 1
    return result


# ---------- parser ----------


def parse_expr(tokens: str, pos: int):
    tok, pos = next_token(tokens, pos)
    return parse_expr_at(tokens, pos, tok)


def parse_expr_at(tokens: str, pos: int, tok: str) -> Tuple:
    result = (EConst(""), pos)
    if tok == "(":
        op, pos = next_token(tokens, pos)
        if op == "call":
            name, pos = next_token(tokens, pos)
            args = []
            done = False
            while not done:
                nxt, pos2 = next_token(tokens, pos)
                if nxt == ")":
                    pos = pos2
                    done = True
                else:
                    arg, pos = parse_expr_at(tokens, pos2, nxt)
                    args = list_append(args, arg)
            result = (ECall(name, args), pos)
        else:
            if op == "not":
                operand, pos = parse_expr(tokens, pos)
                rparen, pos = next_token(tokens, pos)
                result = (EUnary("not", operand), pos)
            else:
                left, pos = parse_expr(tokens, pos)
                right, pos = parse_expr(tokens, pos)
                rparen, pos = next_token(tokens, pos)
                result = (EBinop(op, left, right), pos)
    else:
        if tok == "":
            result = (EConst(""), pos)
        else:
            first = tok[0:1]
            if first == "\"":
                result = (EConst(tok), pos)
            else:
                if is_digit(first) or first == "-" or first == ".":
                    result = (EConst(tok), pos)
                else:
                    result = (EVar(tok), pos)
    return result[0], result[1]


def parse_stmts(tokens: str, pos: int):
    stmts = []
    tok, pos2 = next_token(tokens, pos)
    while tok != "end" and tok != "else":
        if tok == "":
            parse_fail("unexpected end of input: missing 'end'")
        stmt, pos = parse_stmt(tokens, pos)
        stmts = list_append(stmts, stmt)
        tok, pos2 = next_token(tokens, pos)
    return stmts, pos


def parse_stmt(tokens: str, pos: int) -> Tuple:
    tok, pos = next_token(tokens, pos)
    result = (SExpr(EConst("")), pos)
    if tok == "let":
        name, pos = next_token(tokens, pos)
        ty, pos = next_token(tokens, pos)
        value, pos = parse_expr(tokens, pos)
        result = (SLet(name, ty, value), pos)
    else:
        if tok == "set":
            name, pos = next_token(tokens, pos)
            value, pos = parse_expr(tokens, pos)
            result = (SSet(name, value), pos)
        else:
            if tok == "return":
                value, pos = parse_expr(tokens, pos)
                result = (SReturn(value), pos)
            else:
                if tok == "if":
                    cond_expr, pos = parse_expr(tokens, pos)
                    then_body, pos = parse_stmts(tokens, pos)
                    else_body = []
                    nxt, pos2 = next_token(tokens, pos)
                    if nxt == "else":
                        pos = pos2
                        else_body, pos = parse_stmts(tokens, pos)
                    end_tok, pos = next_token(tokens, pos)
                    result = (SIf(cond_expr, then_body, else_body), pos)
                else:
                    if tok == "while":
                        cond_expr, pos = parse_expr(tokens, pos)
                        body, pos = parse_stmts(tokens, pos)
                        end_tok, pos = next_token(tokens, pos)
                        result = (SWhile(cond_expr, body), pos)
                    else:
                        if tok == "for":
                            var, pos = next_token(tokens, pos)
                            stop, pos = parse_expr(tokens, pos)
                            body, pos = parse_stmts(tokens, pos)
                            end_tok, pos = next_token(tokens, pos)
                            result = (SFor(var, stop, body), pos)
                        else:
                            value, pos = parse_expr_at(tokens, pos, tok)
                            result = (SExpr(value), pos)
    return result[0], result[1]


def parse_params(tokens: str, pos: int) -> Tuple:
    nxt, pos2 = next_token(tokens, pos)
    if nxt == ")":
        return [], [], pos2
    name = nxt
    ty = ""
    pos = pos2
    nxt, pos2 = next_token(tokens, pos)
    if nxt == ":":
        ty, pos = next_token(tokens, pos2)
        nxt, pos2 = next_token(tokens, pos)
    if nxt == ",":
        pos = pos2
    rest_names, rest_types, pos = parse_params(tokens, pos)
    names = []
    names = list_append(names, name)
    names = list_append_all(names, rest_names)
    types = []
    types = list_append(types, ty)
    types = list_append_all(types, rest_types)
    return names, types, pos


def parse_func(tokens: str, pos: int):
    def_tok, pos = next_token(tokens, pos)
    name, pos = next_token(tokens, pos)
    lparen, pos = next_token(tokens, pos)
    params, param_types, pos = parse_params(tokens, pos)
    arrow, pos = next_token(tokens, pos)
    ret, pos = next_token(tokens, pos)
    body, pos = parse_stmts(tokens, pos)
    end_tok, pos = next_token(tokens, pos)
    return IRFunc(name, params, param_types, ret, body), pos


def parse_funcs(tokens: str, pos: int) -> Tuple:
    tok, pos2 = next_token(tokens, pos)
    result = ([], pos2)
    if tok != "":
        func, pos = parse_func(tokens, pos)
        rest, pos = parse_funcs(tokens, pos)
        out = []
        out = list_append(out, func)
        out = list_append_all(out, rest)
        result = (out, pos)
    return result[0], result[1]


def parse_program(tokens: str):
    funcs, pos = parse_funcs(tokens, 0)
    if list_length(funcs) == 0:
        parse_fail("empty program: no function definitions")
    tok, pos2 = next_token(tokens, pos)
    if tok != "":
        parse_fail("unexpected trailing token after last function: " + tok)
    return funcs


# ---------- type environment ----------


def const_is_float(v):
    i = 0
    n = len(v)
    while i < n:
        c = v[i:i + 1]
        if c == "." or c == "e" or c == "E":
            return True
        i = i + 1
    return False


def expr_type(expr, env):
    result = "Any"
    if isinstance(expr, EConst):
        v: str = expr.value
        if v == "":
            result = "str"
        else:
            c = v[0:1]
            if c == "\"":
                result = "str"
            else:
                if is_digit(c) or c == "-" or c == ".":
                    if const_is_float(v):
                        result = "float"
                    else:
                        result = "int"
    else:
        if isinstance(expr, EVar):
            t = dict_get_or_empty(env, expr.name)
            if len(t) != 0:
                result = t
            else:
                result = "Any"
        else:
            if isinstance(expr, EBinop):
                lt = expr_type(expr.left, env)
                rt = expr_type(expr.right, env)
                op = expr.op
                if op == "+" or op == "-" or op == "*" or op == "/":
                    if lt == "float" or rt == "float":
                        result = "float"
                    else:
                        if lt == "int" and rt == "int":
                            result = "int"
                        else:
                            if op == "+":
                                if lt == "str" or rt == "str":
                                    result = "str"
                else:
                    result = "bool"
            else:
                if isinstance(expr, EUnary):
                    if expr.op == "not":
                        result = "bool"
                    else:
                        result = expr_type(expr.operand, env)
    return result


def collect_func_env(func):
    env = make_dict()
    i = 0
    n = len(func.params)
    while i < n:
        ty = list_ref(func.param_types, i)
        if ty == "":
            ty = "Any"
        env[list_ref(func.params, i)] = ty
        i = i + 1
    return env


def add_env_binding(env, name, ty):
    if ty == "":
        ty = "Any"
    env[name] = ty


def make_dict():
    return {}


# ---------- codegen helpers ----------


def emit_plus(left, right, lt, rt):
    result = ""
    if lt == "str" or rt == "str":
        result = "(string-append " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl+ " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx+ " + left + " " + right + ")"
            else:
                result = "(+ " + left + " " + right + ")"
    return result


def emit_minus(left, right, lt, rt):
    result = ""
    if lt == "float" or rt == "float":
        result = "(fl- " + left + " " + right + ")"
    else:
        if lt == "int" and rt == "int":
            result = "(fx- " + left + " " + right + ")"
        else:
            result = "(- " + left + " " + right + ")"
    return result


def emit_mult(left, right, lt, rt):
    result = ""
    if lt == "float" or rt == "float":
        result = "(fl* " + left + " " + right + ")"
    else:
        if lt == "int" and rt == "int":
            result = "(fx* " + left + " " + right + ")"
        else:
            result = "(* " + left + " " + right + ")"
    return result


def emit_div(left, right, lt, rt):
    result = ""
    if lt == "float" or rt == "float":
        result = "(fl/ " + left + " " + right + ")"
    else:
        if lt == "int" and rt == "int":
            result = "(fx/ " + left + " " + right + ")"
        else:
            result = "(/ " + left + " " + right + ")"
    return result


def emit_eq(left, right, lt, rt):
    result = ""
    if lt == "str" and rt == "str":
        result = "(string=? " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl= " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx= " + left + " " + right + ")"
            else:
                result = "(equal? " + left + " " + right + ")"
    return result


def emit_lt(left, right, lt, rt):
    result = ""
    if lt == "str" and rt == "str":
        result = "(string<? " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl< " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx< " + left + " " + right + ")"
            else:
                result = "(< " + left + " " + right + ")"
    return result


def emit_gt(left, right, lt, rt):
    result = ""
    if lt == "str" and rt == "str":
        result = "(string>? " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl> " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx> " + left + " " + right + ")"
            else:
                result = "(> " + left + " " + right + ")"
    return result


def emit_le(left, right, lt, rt):
    result = ""
    if lt == "str" and rt == "str":
        result = "(string<=? " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl<= " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx<=? " + left + " " + right + ")"
            else:
                result = "(<= " + left + " " + right + ")"
    return result


def emit_ge(left, right, lt, rt):
    result = ""
    if lt == "str" and rt == "str":
        result = "(string>=? " + left + " " + right + ")"
    else:
        if lt == "float" or rt == "float":
            result = "(fl>= " + left + " " + right + ")"
        else:
            if lt == "int" and rt == "int":
                result = "(fx>=? " + left + " " + right + ")"
            else:
                result = "(>= " + left + " " + right + ")"
    return result


# ---------- codegen ----------


def escape_string(s):
    out = ""
    i = 0
    n = len(s)
    while i < n:
        c = s[i:i + 1]
        if c == "\\":
            out = out + "\\\\"
        elif c == '"':
            out = out + '\\"'
        elif c == "\n":
            out = out + "\\n"
        elif c == "\t":
            out = out + "\\t"
        elif c == "\r":
            out = out + "\\r"
        else:
            out = out + c
        i = i + 1
    return out


def emit_expr(expr: IRExpr, env):
    result = ""
    if isinstance(expr, EConst):
        v: str = expr.value
        if v == "":
            result = '""'
        else:
            if v[0:1] == "\"":
                # The token already contains a valid Scheme string literal.
                result = v
            else:
                result = v
    else:
        if isinstance(expr, EVar):
            result = expr.name
        else:
            if isinstance(expr, EBinop):
                left = emit_expr(expr.left, env)
                right = emit_expr(expr.right, env)
                result = emit_binop(expr.op, left, right, expr.left, expr.right, env)
            else:
                if isinstance(expr, EUnary):
                    op = expr.op
                    operand = emit_expr(expr.operand, env)
                    if op == "not":
                        result = "(not " + operand + ")"
                    else:
                        result = "(" + op + " " + operand + ")"
                else:
                    if isinstance(expr, ECall):
                        result = "(" + expr.func
                        args = expr.args
                        i = 0
                        n = len(args)
                        while i < n:
                            result = result + " " + emit_expr(list_ref(args, i), env)
                            i = i + 1
                        result = result + ")"
                    else:
                        result = "#<expr>"
    return result


def emit_binop(op, left, right, ln, rn, env):
    lt = expr_type(ln, env)
    rt = expr_type(rn, env)
    result = ""
    if op == "+":
        result = emit_plus(left, right, lt, rt)
    else:
        if op == "-":
            result = emit_minus(left, right, lt, rt)
        else:
            if op == "*":
                result = emit_mult(left, right, lt, rt)
            else:
                if op == "/":
                    result = emit_div(left, right, lt, rt)
                else:
                    if op == "==" or op == "=":
                        result = emit_eq(left, right, lt, rt)
                    else:
                        if op == "!=":
                            inner = emit_binop("==", left, right, ln, rn, env)
                            result = "(not " + inner + ")"
                        else:
                            if op == "<":
                                result = emit_lt(left, right, lt, rt)
                            else:
                                if op == ">":
                                    result = emit_gt(left, right, lt, rt)
                                else:
                                    if op == "<=":
                                        result = emit_le(left, right, lt, rt)
                                    else:
                                        if op == ">=":
                                            result = emit_ge(left, right, lt, rt)
                                        else:
                                            if op == "and":
                                                result = "(and " + left + " " + right + ")"
                                            else:
                                                if op == "or":
                                                    result = "(or " + left + " " + right + ")"
                                                else:
                                                    result = "(__unknown__ " + op + " " + left + " " + right + ")"
    return result


def emit_block(stmts, env, indent):
    n = len(stmts)
    if n == 0:
        return "(void)"

    first = list_ref(stmts, 0)
    if isinstance(first, SLet):
        binding = "(" + first.name + " " + emit_expr(first.value, env) + ")"
        add_env_binding(env, first.name, first.ty)
        rest = list_ref_range(stmts, 1, n)
        rest_expr = emit_block(rest, env, indent + "  ")
        return "(let (" + binding + ")\n" + indent + "  " + rest_expr + ")"

    return emit_raw_block(stmts, env, indent)


def emit_raw_block(stmts, env, indent):
    n = len(stmts)
    if n == 0:
        return "(void)"

    # Collect non-SLet statements until we hit an SLet or end.
    parts = []
    i = 0
    while i < n:
        stmt = list_ref(stmts, i)
        if isinstance(stmt, SLet):
            # Prefix statements before this SLet become a begin.
            prefix = ""
            if len(parts) == 1:
                prefix = list_ref(parts, 0)
            elif len(parts) > 1:
                prefix = "(begin\n" + indent + "  " + str_join(parts, "\n" + indent + "  ") + "\n" + indent + ")"

            # The SLet and its following statements are handled by emit_block.
            rest = list_ref_range(stmts, i, n)
            rest_expr = emit_block(rest, env, indent)

            if prefix == "":
                return rest_expr
            return "(begin\n" + indent + "  " + prefix + "\n" + indent + "  " + rest_expr + "\n" + indent + ")"
        else:
            parts = list_append(parts, emit_stmt(stmt, env, indent + "  "))
            i = i + 1

    # No SLet found, emit all parts.
    if len(parts) == 1:
        return list_ref(parts, 0)
    return "(begin\n" + indent + "  " + str_join(parts, "\n" + indent + "  ") + "\n" + indent + ")"


def emit_stmt(stmt, env, indent):
    result = ""
    if isinstance(stmt, SLet):
        # SLet statements should be handled by emit_block, but provide
        # a valid fallback if reached.
        result = "(let ((" + stmt.name + " " + emit_expr(stmt.value, env) + ")) (void))"
    else:
        if isinstance(stmt, SSet):
            result = "(set! " + stmt.name + " " + emit_expr(stmt.value, env) + ")"
        else:
            if isinstance(stmt, SReturn):
                result = f"(__return__ {emit_expr(stmt.value, env)})"
            else:
                if isinstance(stmt, SExpr):
                    result = emit_expr(stmt.value, env)
                else:
                    if isinstance(stmt, SIf):
                        c = emit_expr(stmt.cond_expr, env)
                        then_expr = emit_block(stmt.then_body, env.copy(), indent)
                        else_expr = emit_block(stmt.else_body, env.copy(), indent)
                        result = "(if " + c + "\n" + indent + then_expr + "\n" + indent + else_expr + ")"
                    else:
                        if isinstance(stmt, SWhile):
                            c = emit_expr(stmt.cond_expr, env)
                            body_expr = emit_block(stmt.body, env.copy(), indent)
                            result = "(let loop ()\n" + indent + "  (when " + c + "\n" + indent + "    " + body_expr + "\n" + indent + "    (loop)))"
                        else:
                            if isinstance(stmt, SFor):
                                stop = emit_expr(stmt.stop, env)
                                body_expr = emit_block(stmt.body, env.copy(), indent)
                                result = "(do ((" + stmt.var + " 0 (fx+ " + stmt.var + " 1)))\n" + indent + "    ((fx>=? " + stmt.var + " " + stop + "))\n" + indent + "  " + body_expr + ")"
                            else:
                                result = "#<stmt>"
    return result


def emit_func(func: IRFunc):
    env = collect_func_env(func)
    body_expr = emit_block(func.body, env, "  ")
    # Wrap body in call/cc so that return statements with __return__ work.
    wrapped = f"(call/cc (lambda (__return__)\n{body_expr}\n  ))"
    params_str = func_params_to_str(func.params)
    if params_str == "":
        return "(define (" + func.name + ")\n  " + wrapped + ")\n"
    return "(define (" + func.name + " " + params_str + ")\n  " + wrapped + ")\n"


def emit_program(funcs):
    out = ";; generated by staticc.py\n(import (chezscheme))\n"
    i = 0
    n = len(funcs)
    while i < n:
        out = out + emit_func(list_ref(funcs, i))
        i = i + 1
    out = out + "(main)\n"
    return out


# ---------- public API ----------


def compile_file(path: str):
    fp = file_open(path, "r")
    src: str = file_read_all(fp)
    file_close(fp)
    tokens = tokenize(src)
    funcs = parse_program(tokens)
    return emit_program(funcs)


def main():
    args = argv()
    result = 0
    if len(args) < 3:
        print("usage: staticc <input.sp> <output.scm>")
        result = 1
    else:
        inp = list_ref(args, 1)
        out_path = list_ref(args, 2)
        scm = compile_file(inp)
        fp = file_open(out_path, "w")
        file_write(fp, scm)
        file_close(fp)
    return result


if __name__ == "__main__":
    main()
