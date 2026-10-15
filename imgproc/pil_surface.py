#!/usr/bin/env python3
"""pil_surface.py — 自省 Pillow 的公开 API，生成覆盖面清单（迁移用）。

用法: /data/venv/bin/python imgproc/pil_surface.py > imgproc/pil_api.md
"""
import inspect
import importlib

MODULES = [
    ("Image", "PIL.Image"),
    ("ImageOps", "PIL.ImageOps"),
    ("ImageChops", "PIL.ImageChops"),
    ("ImageEnhance", "PIL.ImageEnhance"),
    ("ImageFilter", "PIL.ImageFilter"),
    ("ImageStat", "PIL.ImageStat"),
    ("ImageDraw", "PIL.ImageDraw"),
    ("ImageFont", "PIL.ImageFont"),
    ("ImageSequence", "PIL.ImageSequence"),
    ("ImageColor", "PIL.ImageColor"),
    ("ImagePalette", "PIL.ImagePalette"),
]


def sig(obj):
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(...)"


print("# Pillow 公开 API 清单（自省生成）\n")
print("> 由 `imgproc/pil_surface.py` 自动生成。每个名字对应一个待迁移的接口。\n")

total = 0
for short, modname in MODULES:
    try:
        mod = importlib.import_module(modname)
    except Exception as e:
        print(f"## {short}\n\n（导入失败: {e}）\n")
        continue
    names = [n for n in dir(mod) if not n.startswith("_")]
    funcs, classes = [], []
    for n in names:
        try:
            o = getattr(mod, n)
        except Exception:
            continue
        if inspect.isclass(o) and getattr(o, "__module__", "").startswith("PIL"):
            methods = [m for m in dir(o) if not m.startswith("_")]
            classes.append((n, methods))
        elif inspect.isfunction(o) or inspect.isbuiltin(o):
            funcs.append((n, sig(o)))
    print(f"## {short}  （函数 {len(funcs)}，类 {len(classes)}）\n")
    if funcs:
        print("| 函数 | 签名 |")
        print("|---|---|")
        for n, s in sorted(funcs):
            print(f"| `{n}` | `{s}` |")
        print()
    for cn, methods in sorted(classes):
        pub = [m for m in methods if not m.startswith("_")][:30]
        print(f"- **{cn}** ({len(methods)} 成员): " + ", ".join(pub[:20]))
    print()
    total += len(funcs) + len(classes)

import sys
print(f"\n---\n共 {total} 个顶层函数/类。", file=sys.stderr)
