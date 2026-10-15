#!/usr/bin/env python3
"""Generate vocab.bin (id -> decoded token bytes) for Florence-2 C++ detokenizer.

Format: uint32 count, then count * (uint32 len, len bytes).
Bytes are the byte-level (GPT-2/BART) decoded form, ready to concatenate as UTF-8.
"""
import struct
import sys
from pathlib import Path


def bytes_to_unicode():
    bs = list(range(ord("!"), ord("~") + 1))
    bs += list(range(ord("\u00a1"), ord("\u00ac") + 1))
    bs += list(range(ord("\u00ae"), ord("\u00ff") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


def main():
    model_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "/data/models/florence2")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else model_dir / "vocab.bin")

    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(model_dir))
    u2b = {v: k for k, v in bytes_to_unicode().items()}
    n = len(tok)

    with open(out_path, "wb") as f:
        f.write(struct.pack("<I", n))
        for i in range(n):
            t = tok.convert_ids_to_tokens(i)
            if t is None:
                b = b""
            else:
                try:
                    b = bytes(u2b[c] for c in t)
                except KeyError:
                    b = t.encode("utf-8")
            f.write(struct.pack("<I", len(b)))
            f.write(b)
    print(f"wrote {out_path} ({n} tokens, {out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
