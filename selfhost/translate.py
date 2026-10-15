#!/usr/bin/env python3
"""translate.py — JSON AST → Scheme S-expressions (Python bridge)

Usage:
  php parse.php input.php | python3 translate.py > output.ss
"""

import sys
import json

# ========== Name Mangling ==========

def mangle_php_name(name):
    if name.startswith('$'):
        name = name[1:]
    result = f"php-{name.lower()}"
    # Avoid conflicts with prelude function names
    reserved = {'php-concat', 'php-echo', 'php-print', 'php-array', 'php-foreach',
                 'php-add', 'php-sub', 'php-mul', 'php-div', 'php-mod',
                 'php-eq', 'php-ne', 'php-lt', 'php-gt', 'php-le', 'php-ge',
                 'php-id', 'php-nid', 'php-coalesce', 'php-binop', 'php-unop',
                 'php-pre-inc', 'php-pre-dec', 'php-post-inc', 'php-post-dec',
                 'php-assign-op', 'php-int', 'php-float', 'php-string', 'php-bool',
                 'php-null', 'php-make-value', 'php-type', 'php-val',
                 'php-array-ref', 'php-array-set!', 'php-array-push',
                 'php-prop-get', 'php-prop-set!', 'php-method-call',
                 'php-static-call', 'php-static-prop-get', 'php-new'}
    if result in reserved:
        result = result + '-var'
    return result

def mangle_func_name(name):
    return f"php-fn-{name.lower()}"

# ========== Expression Translation ==========

def translate_expr(node):
    kind = node['kind']
    children = node.get('children', [])
    
    if kind == 'LITERAL':
        val, typ = children
        if typ == 'int': return f"(php-int {val})"
        if typ == 'float': return f"(php-float {val})"
        if typ == 'string': return f"(php-string {json.dumps(val)})"
        if typ == 'bool': return f"(php-bool {'#t' if val else '#f'})"
        if typ == 'null': return "(php-null)"
        raise Exception(f"Unknown literal type: {typ}")
    
    elif kind == 'VAR':
        return mangle_php_name(children[0])
    
    elif kind == 'NAME':
        n = children[0]
        if n.startswith('\\'):
            return n[1:]
        return n
    
    elif kind == 'BINARY_OP':
        op, l, r = children[0], translate_expr(children[1]), translate_expr(children[2])
        ops = {
            '+': 'php-add', '-': 'php-sub', '*': 'php-mul', '/': 'php-div',
            '%': 'php-mod', '.': 'php-concat',
            '==': 'php-eq', '!=': 'php-ne', '===': 'php-id', '!==': 'php-nid',
            '<': 'php-lt', '>': 'php-gt', '<=': 'php-le', '>=': 'php-ge',
            '&&': 'and', '||': 'or', '??': 'php-coalesce',
        }
        if op in ops:
            return f"({ops[op]} {l} {r})"
        return f"(php-binop '{op} {l} {r})"
    
    elif kind == 'UNARY_OP':
        op, e = children[0], translate_expr(children[1])
        if op == '!': return f"(not {e})"
        if op == '~': return f"(bitwise-not {e})"
        if op == '-': return f"(- 0 {e})"
        if op == '+': return e
        return f"(php-unop '{op} {e})"
    
    elif kind in ('PRE_OP', 'POST_OP'):
        op, e = children[0], translate_expr(children[1])
        prefix = 'php-pre' if kind == 'PRE_OP' else 'php-post'
        return f"({prefix}-{'inc' if op == '++' else 'dec'} {e})"
    
    elif kind == 'ASSIGN':
        target_node = children[0]
        value = translate_expr(children[1])
        if target_node.get('kind') == 'DIM':
            arr = translate_expr(target_node['children'][0])
            key = translate_expr(target_node['children'][1])
            return f"(php-array-set! {arr} {key} {value})"
        if target_node.get('kind') == 'PROP':
            obj = translate_expr(target_node['children'][0])
            prop = target_node['children'][1]
            return f"(php-prop-set! {obj} '{prop} {value})"
        return f"(set! {translate_lvalue(target_node)} {value})"
    
    elif kind == 'ASSIGN_OP':
        op = children[0]
        # Simple assignment `=` handled above
        if op == '=':
            return f"(set! {translate_lvalue(children[1])} {translate_expr(children[2])})"
        # Fix: some comparison operators end with = but are not assignments
        if op in ('<=', '>=', '==', '===', '!=', '!==', '<=>'):
            # This is actually a comparison, not assignment
            target = translate_lvalue(children[1])
            value = translate_expr(children[2])
            ops = {'<=': 'php-le', '>=': 'php-ge', '==': 'php-eq', '===': 'php-id',
                   '!=': 'php-ne', '!==': 'php-nid', '<=>': 'php-cmp'}
            return f"({ops[op]} {target} {value})"
        target, value = translate_lvalue(children[1]), translate_expr(children[2])
        return f"(php-assign-op '{op} {target} {value})"
    
    elif kind == 'CALL':
        func = children[0]
        args = children[1:]
        if func.get('kind') == 'NAME':
            n = func['children'][0]
            if n == 'array': fname = 'php-array'
            elif n == 'print': fname = 'php-print'
            elif n == 'echo': fname = 'php-echo'
            else: fname = mangle_func_name(n)
        else:
            fname = translate_expr(func)
        args_str = ' '.join(translate_expr(a) for a in args)
        return f"({fname} {args_str})" if args_str else f"({fname})"
    
    elif kind == 'METHOD_CALL':
        obj, method = translate_expr(children[0]), children[1]
        args = ' '.join(translate_expr(a) for a in children[2:])
        return f"(php-method-call {obj} '{method} {args})"
    
    elif kind == 'STATIC_CALL':
        cls, method = translate_expr(children[0]), children[1]
        args = ' '.join(translate_expr(a) for a in children[2:])
        return f"(php-static-call {cls} '{method} {args})"
    
    elif kind == 'NEW':
        cls = children[0]
        cname = cls['children'][0] if isinstance(cls, dict) else 'stdClass'
        args = ' '.join(translate_expr(a) for a in children[1:])
        return f'(php-new "{cname}" {args})'
    
    elif kind == 'DIM':
        arr = translate_expr(children[0])
        key = translate_expr(children[1]) if len(children) > 1 and children[1] is not None else None
        return f"(php-array-ref {arr} {key})" if key else f"(php-array-push {arr})"
    
    elif kind == 'PROP':
        return f"(php-prop-get {translate_expr(children[0])} '{children[1]})"
    
    elif kind == 'STATIC_PROP':
        return f"(php-static-prop-get {translate_expr(children[0])} '{children[1]})"
    
    elif kind == 'CONDITIONAL':
        cnd, then, els = (translate_expr(children[i]) for i in range(3))
        return f"(if {cnd} {then} {els})"
    
    elif kind == 'ARRAY':
        items = ' '.join(translate_array_elem(c) for c in children)
        return f"(php-array {items})"
    
    elif kind == 'SILENCE':
        return translate_expr(children[0])
    
    else:
        raise Exception(f"Unknown expression kind: {kind}")


def translate_lvalue(node):
    kind = node['kind']
    children = node.get('children', [])
    if kind == 'VAR':
        return mangle_php_name(children[0])
    elif kind == 'DIM':
        arr = translate_lvalue(children[0])
        key = translate_expr(children[1]) if len(children) > 1 and children[1] else None
        return f"(php-array-ref {arr} {key})" if key else arr
    elif kind == 'PROP':
        return f"(php-prop-get {translate_expr(children[0])} '{children[1]})"
    else:
        return translate_expr(node)


def translate_array_elem(node):
    children = node.get('children', [])
    if len(children) == 1:
        return translate_expr(children[0])
    return f"(cons {translate_expr(children[0])} {translate_expr(children[1])})"


# ========== Statement Translation ==========

def translate_stmt(node, indent=''):
    kind = node['kind']
    children = node.get('children', [])
    ind = lambda: indent
    
    if kind == 'STMT_LIST':
        # Merge IF without else with the following statement
        result = ''
        i = 0
        while i < len(children):
            s = children[i]
            if s.get('kind') == 'IF' and len(s.get('children', [])) <= 2:
                # IF without else — try to merge with next statement
                cnd = translate_expr(s['children'][0])
                then_str = translate_stmt(s['children'][1], indent + '  ')
                if i + 1 < len(children):
                    i += 1
                    next_str = translate_stmt(children[i], indent + '  ')
                    result += f"{ind()}(if {cnd}\n{then_str}{ind()}  {next_str})\n"
                else:
                    result += f"{ind()}(if {cnd}\n{then_str})\n"
            else:
                result += translate_stmt(s, indent)
            i += 1
        return result
    
    elif kind == 'ECHO':
        return f"{ind()}(php-echo {translate_expr(children[0])})\n"
    
    elif kind == 'RETURN':
        if children:
            return f"{ind()}{translate_expr(children[0])}\n"
        return f"{ind()}(php-null)\n"
    
    elif kind == 'IF':
        cnd = translate_expr(children[0])
        then_str = translate_stmt(children[1], indent + '  ')
        if len(children) > 2 and children[2] is not None:
            else_str = translate_stmt(children[2], indent + '  ')
            return f"{ind()}(if {cnd}\n{then_str}{ind()}  {else_str})\n"
        # No else — return just the then branch (caller merges next stmt)
        return f"{ind()}(if {cnd}\n{then_str})\n"
    
    elif kind == 'WHILE':
        cnd = translate_expr(children[0])
        body_node = children[1]
        body_str = translate_stmt(body_node, indent + '    ')
        # Wrap body in begin + add loop call
        if body_node.get('kind') == 'STMT_LIST' and len(body_node.get('children', [])) != 1:
            body_str = f"(begin\n{body_str}{ind()}    (loop))\n"
        else:
            body_str = f"(begin\n{body_str}{ind()}    (loop))\n"
        return f"{ind()}(let loop ()\n{ind()}  (if {cnd}\n{ind()}    {body_str}{ind()}  (void)))\n"
    
    elif kind == 'FOR':
        init = translate_expr(children[0]) if len(children) > 0 and children[0] else None
        cnd = translate_expr(children[1]) if len(children) > 1 and children[1] else None
        incr = translate_expr(children[2]) if len(children) > 2 and children[2] else None
        body_node = children[3] if len(children) > 3 else None
        body_str = translate_stmt(body_node, indent + '    ') if body_node else ''
        # Build then branch: body + incr + loop
        then_parts = [body_str]
        if incr: then_parts.append(f"{ind()}    {incr}")
        then_parts.append(f"{ind()}    (loop)")
        then_str = '(begin\n' + '\n'.join(then_parts) + f'\n{ind()}    )'
        result = f"{ind()}(begin\n"
        if init: result += f"{ind()}  {init}\n"
        result += f"{ind()}  (let loop ()\n{ind()}    (if {cnd or '#t'}\n{ind()}      {then_str}\n{ind()}      (void)))\n"
        result += f"{ind()})\n"
        return result
    
    elif kind == 'FOREACH':
        expr = translate_expr(children[0])
        val = translate_lvalue(children[1])
        has_key = len(children) > 2 and isinstance(children[2], dict) and children[2].get('kind') != 'STMT_LIST'
        body_idx = 2 if not has_key else 3
        body = translate_stmt(children[body_idx], indent + '  ')
        if has_key:
            k = translate_lvalue(children[2])
            return f"{ind()}(php-foreach {expr} (lambda ({k} {val})\n{body}{ind()}))\n"
        return f"{ind()}(php-foreach {expr} (lambda ({val})\n{body}{ind()}))\n"
    
    elif kind == 'BREAK':
        return f"{ind()}(break)\n"
    
    elif kind == 'CONTINUE':
        return f"{ind()}(continue)\n"
    
    elif kind == 'THROW':
        return f"{ind()}(raise {translate_expr(children[0])})\n"
    
    elif kind == 'SWITCH':
        expr = translate_expr(children[0])
        cases = children[1]['children'] if children[1] else []
        result = f"{ind()}(case {expr}\n"
        for c in cases:
            cc = c.get('children', [])
            val = cc[0] if cc else None
            body = cc[-1] if cc else None
            val_str = translate_expr(val) if val else 'else'
            result += f"{ind()}  (({val_str})\n"
            if body: result += translate_stmt(body, indent + '    ')
            result += f"{ind()}  )\n"
        result += f"{ind()})\n"
        return result
    
    elif kind == 'FUNC_DECL':
        name = children[0]
        params = children[1]['children'] if len(children) > 1 else []
        body = translate_stmt(children[2], indent + '  ')
        param_str = ' '.join(mangle_php_name(p['children'][0]) for p in params)
        return f"{ind()}(define {mangle_func_name(name)} (lambda ({param_str})\n{body}{ind()}))\n"
    
    elif kind == 'CLASS':
        name = children[0]
        members = children[3]['children'] if len(children) > 3 and children[3] else []
        return f"{ind()};; class {name}\n" + ''.join(translate_stmt(m, indent) for m in members)
    
    elif kind == 'METHOD':
        name = children[0]
        params = children[1]['children'] if len(children) > 1 else []
        body = translate_stmt(children[2], indent + '  ')
        param_str = ' '.join(mangle_php_name(p['children'][0]) for p in params)
        return f"{ind()}(define (php-method-{name.lower()} self {param_str})\n{body}{ind()})\n"
    
    elif kind == 'PROP_DECL':
        result = ''
        for p in children:
            pc = p.get('children', [])
            var = translate_lvalue(pc[0]) if pc else ''
            init = translate_expr(pc[1]) if len(pc) > 1 and pc[1] else "'null"
            result += f"{ind()}(define {var} {init})\n"
        return result
    
    elif kind == 'GLOBAL':
        result = ''
        for v in children:
            result += f"{ind()}(define {translate_lvalue(v)} 'null)\n"
        return result
    
    elif kind in ('NAMESPACE', 'USE'):
        return ''
    
    else:
        e = translate_expr(node)
        return f"{ind()}{e}\n"


# ========== Main ==========

def is_function_def(stmt):
    kind = stmt.get('kind', '')
    return kind in ('FUNC_DECL', 'METHOD', 'CLASS')

def main():
    ast = json.load(sys.stdin)
    
    print(";; Generated by ReScheme PHP frontend")
    print("(import (chezscheme))")
    print('(load "prelude.scm")')
    print()
    
    # Convert AST to statements
    prog = ast.get('children', [])
    stmts = prog[0] if (prog and isinstance(prog[0], list)) else prog
    
    # Collect function definitions and other statements separately
    defs = []
    body = []
    for s in stmts:
        if is_function_def(s):
            defs.append(s)
        else:
            body.append(s)
    
    # Output function definitions first (Scheme requires define before use)
    for s in defs:
        print(translate_stmt(s), end='')
    
    # Then output the body
    for s in body:
        print(translate_stmt(s), end='')

if __name__ == '__main__':
    main()
