#!/usr/bin/env python3
"""kernel.bundle — 把插件运行时片段 + FFI 声明 + 翻译产物拼成一个 .ss"""
from __future__ import annotations

import os


def assemble(kernel, code_ss, extra_ffi=None, header=None):
    """返回 (bundle 文本, 参与 hash 的输入文件列表)"""
    parts = []
    inputs = []

    parts.append(";;; -*- scheme -*- 由 StaticPy kernel 自动拼装")
    if header:
        for line in header.strip().splitlines():
            parts.append(";;; " + line)
    parts.append("(import (chezscheme))")
    parts.append("")

    for name, path in kernel.runtime_files():
        parts.append(f";;; ---- plugin: {name} :: {os.path.basename(path)} ----")
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().rstrip())
        parts.append("")
        inputs.append(path)

    for name, path in kernel.ffi_files():
        parts.append(f";;; ---- plugin ffi: {name} :: {os.path.basename(path)} ----")
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().rstrip())
        parts.append("")
        inputs.append(path)

    if extra_ffi:
        for path in extra_ffi:
            parts.append(f";;; ---- user ffi: {os.path.basename(path)} ----")
            with open(path, encoding="utf-8") as f:
                parts.append(f.read().rstrip())
            parts.append("")
            inputs.append(path)

    parts.append(";;; ---- translated program ----")
    parts.append(code_ss.rstrip())
    parts.append("")

    # load-shared-object 去重：插件 ffi、用户 -f、内核按 libs 自动生成的可能重复
    seen = set()
    out = []
    for line in "\n".join(parts).splitlines():
        st = line.strip()
        if st.startswith("(load-shared-object"):
            if st in seen:
                continue
            seen.add(st)
        out.append(line)
    return "\n".join(out) + "\n", inputs
