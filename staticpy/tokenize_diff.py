import io, sys, keyword, ast, tokenize

def esc(s):
    if not isinstance(s, str):
        s = repr(s)
    return (s.replace("\\", "\\\\").replace("\n", "\\n")
            .replace("\t", "\\t").replace("\r", "\\r").replace("\x00", "\\0"))

def dump(path):
    out = []
    with open(path, 'rb') as f:
        src = f.read()
    toks = list(tokenize.tokenize(io.BytesIO(src).readline))
    skip_f = 0
    for t in toks:
        tn = tokenize.tok_name[t.type]
        if tn in ('ENCODING', 'NL', 'COMMENT', 'ENDMARKER'):
            continue
        if tn == 'FSTRING_START':
            skip_f = skip_f + 1
            continue
        if skip_f:
            if tn == 'FSTRING_END':
                skip_f = skip_f - 1
            continue
        if tn == 'NAME':
            out.append(('KEYWORD' if keyword.iskeyword(t.string) else 'NAME', t.string))
        elif tn == 'NUMBER':
            out.append(('NUMBER', t.string))
        elif tn == 'STRING':
            s = t.string
            p = ''
            i = 0
            while i < len(s) and s[i] not in '"\'':
                p += s[i]
                i += 1
            if 'f' in p.lower():
                continue
            val = ast.literal_eval(s)
            if isinstance(val, bytes):
                # b'..' 在 CPython 3.12 是 STRING，我们的词法器归类 BYTES：统一成 BYTES(正文)
                out.append(('BYTES', val.decode('utf-8', 'replace')))
            else:
                out.append(('STRING', val))
        elif tn in ('INDENT', 'DEDENT', 'NEWLINE'):
            out.append((tn, ''))
        elif tn == 'OP':
            out.append(('OP', t.string))
        else:
            out.append((tn, t.string))
    return out

for ty, v in dump(sys.argv[1]):
    print(ty + '\t' + esc(v))
