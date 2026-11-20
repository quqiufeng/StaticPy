#!/usr/bin/env python3
"""kernel.bundle — 把插件运行时片段 + FFI 声明 + 翻译产物拼成一个 .ss"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATICPY_DIR = os.path.join(os.path.dirname(HERE), "staticpy")


def _runtime_roots():
    """与 static_build_comfycli.sh 一致：prelude + stdlib 必须先于插件/程序。

    旧 .sh 链路用 `cat static_prelude.scm` 打头；kernel 链路此前漏了这一步，
    结果 isinstance→ir-tag?、make_dict 等在 ELF 里未绑定。
    """
    stdlib = os.environ.get("STATICPY_STDLIB", "static_stdlib.scm")
    return [os.path.join(STATICPY_DIR, "static_prelude.scm"),
            os.path.join(STATICPY_DIR, stdlib)]


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

    for path in _runtime_roots():
        parts.append(f";;; ---- runtime: {os.path.basename(path)} ----")
        with open(path, encoding="utf-8") as f:
            parts.append(f.read().rstrip())
        parts.append("")
        inputs.append(path)

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
