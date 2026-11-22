#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是覆盖面的「测量端」：用 pip 的 torch 自省出 API 清单，不产出 IR，不进任何产物链路。
# 若把它改写进 StaticPy，被测物就成了自己的考官（AGENTS §0/§2）。

"""surface.py — 自省 PyTorch，导出待迁接口清单（markdown）。

产出的 ltorch_api.md 是「广度」的输入：coverage.py 拿它核对我们的映射表。
自省只给名字/签名，给不了语义——语义由 difftest.py 判定。

用法: python3 plugins/ltorch/surface.py > plugins/ltorch/ltorch_api.md
"""
import inspect

import torch


DOMAINS = ["core", "tensor", "nn", "optim", "dtype", "no_grad"]


def sig_of(obj):
    # 签名拿不到就退化成空串（builtin）——不影响覆盖面统计
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return ""


def top_level():
    # torch.<name> 顶层函数/常量：只要可调用且非私有
    out = []
    for nm in sorted(dir(torch)):
        if nm.startswith("_"):
            continue
        obj = getattr(torch, nm)
        if inspect.ismodule(obj):
            continue
        kind = "fn" if callable(obj) else "const"
        out.append((nm, kind, sig_of(obj) if callable(obj) else ""))
    return out


def tensor_methods():
    out = []
    for nm in sorted(dir(torch.Tensor)):
        if nm.startswith("_"):
            continue
        attr = getattr(torch.Tensor, nm, None)
        kind = "prop" if isinstance(attr, property) else "m"
        out.append((nm, kind, sig_of(attr) if callable(attr) else ""))
    return out


def nn_names():
    out = []
    for nm in sorted(dir(torch.nn)):
        if nm.startswith("_"):
            continue
        obj = getattr(torch.nn, nm)
        if inspect.ismodule(obj):
            continue
        if not inspect.isclass(obj):
            continue
        out.append((nm, "cls", sig_of(obj.__init__)))
    return out


def nn_functional():
    out = []
    for nm in sorted(dir(torch.nn.functional)):
        if nm.startswith("_"):
            continue
        obj = getattr(torch.nn.functional, nm)
        if callable(obj):
            out.append((nm, "fn", sig_of(obj)))
    return out


def optim_names():
    out = []
    for nm in sorted(dir(torch.optim)):
        if nm.startswith("_"):
            continue
        obj = getattr(torch.optim, nm)
        if inspect.ismodule(obj):
            continue
        if not inspect.isclass(obj):
            continue
        out.append((nm, "cls", sig_of(obj.__init__)))
    return out


def dtype_names():
    out = []
    for nm in sorted(dir(torch)):
        if nm.startswith("_"):
            continue
        if nm in ("float", "double", "half", "bfloat16", "int8", "int16", "int32", "int64",
                  "uint8", "bool", "complex64", "complex128"):
            out.append((nm, "dtype", ""))
    return out


def emit_section(title, rows, note):
    print("")
    print("## " + title)
    print("")
    print(note)
    print("")
    print("| 名 | 形态 | 签名 |")
    print("|---|---|---|")
    for nm, kind, sg in rows:
        cell = sg.replace("|", "\\|").replace("\n", " ")
        if len(cell) > 120:
            cell = cell[:120] + "…"
        print("| `" + nm + "` | " + kind + " | `" + cell + "` |")


def main():
    print("# PyTorch 接口面（自省清单）")
    print("")
    print("由 `python3 plugins/ltorch/surface.py` 生成，torch `" + torch.__version__ + "`。")
    print("")
    top = top_level()
    tm = tensor_methods()
    nn = nn_names()
    nf = nn_functional()
    op = optim_names()
    dt = dtype_names()
    print("**规模**：顶层 " + str(len(top)) + " · Tensor 成员 " + str(len(tm)) +
          " · nn 模块 " + str(len(nn)) + " · nn.functional " + str(len(nf)) +
          " · optim " + str(len(op)) + " · dtype " + str(len(dt)))
    emit_section("顶层 `torch.*`", top, "可调用对象与常量（模块除外）。")
    emit_section("`torch.Tensor` 成员", tm, "m=方法，prop=属性。")
    emit_section("`torch.nn` 模块", nn, "nn.Module 子类。")
    emit_section("`torch.nn.functional`", nf, "无状态函数。")
    emit_section("`torch.optim` 优化器", op, "优化器类。")
    emit_section("dtype", dt, "张量元素类型。")


main()
