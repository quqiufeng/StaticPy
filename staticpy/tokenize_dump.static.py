
def esc(s: str) -> str:
    t: str = str_replace(s, "\\", "\\\\")
    t = str_replace(t, "\n", "\\n")
    t = str_replace(t, "\t", "\\t")
    t = str_replace(t, "\r", "\\r")
    t = str_replace(t, integer_to_char(0), "\\0")
    return t

def dump_tokens(path: str) -> int:
    fp = file_open(path, "r")
    src: str = file_read_all(fp)
    file_close(fp)
    toks = tokenize(src)
    i: int = 0
    nt = list_length(toks)
    while i < nt:
        t = list_ref(toks, i)
        ty = tok_type(t)
        if ty == "ENDMARKER" or ty == "FSTRING":
            i = i + 1
            continue
        elif ty == "INDENT" or ty == "DEDENT" or ty == "NEWLINE":
            print(ty + "\t")
        else:
            print(ty + "\t" + esc(tok_value(t)))
        i = i + 1
    return 0

def main() -> int:
    args = argv()
    return dump_tokens(list_ref(args, 1))
