#!/usr/bin/env python3
# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""kernel.cli — StaticPy 统一入口。

    python3 -m kernel plugins                 # 列出插件
    python3 -m kernel build app.static.py     # 构建独立 ELF（含 --plugin 选择）
    python3 -m kernel run   app.static.py -a x
    python3 -m kernel check app.static.py     # 只翻译，不编译

插件选择优先级：
    --plugin a,b  >  STATICPY_PLUGINS 环境变量  >  按源码 import 自动推断  >  core
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

from . import Kernel, PluginError
from . import bundle as bundle_mod
from . import toolchain

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRANSLATOR = os.path.join(ROOT, "staticpy", "static_translate.py")


def _load_kernel(args, source=""):
    k = Kernel.discover()
    names = []
    if args.plugin:
        names = [n.strip() for n in args.plugin.split(",") if n.strip()]
    else:
        env = os.environ.get("STATICPY_PLUGINS", "")
        names = [n.strip() for n in env.split(",") if n.strip()]
    explicit = bool(names)
    if "core" not in names:
        names.insert(0, "core")
    k.resolve(names, auto=not explicit and not args.no_auto, source=source)
    return k


def _translate(src, k, out_path, warn=False):
    env = dict(os.environ)
    env["STATICPY_PLUGINS"] = ",".join(k.plugins)
    cmd = [sys.executable, TRANSLATOR]
    if warn:
        cmd.append("--warn")
    cmd.append(src)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)
    if r.returncode != 0:
        raise SystemExit("翻译失败")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(r.stdout)
    return out_path


def cmd_plugins(args):
    k = Kernel.discover()
    print(f"插件搜索路径: {', '.join(k.available and []) or ''}".rstrip())
    if args.json:
        import json
        print(json.dumps({n: p.describe() if hasattr(p, "describe") else
                          {"version": p.version, "kind": p.kind,
                           "description": p.description, "requires": p.requires}
                          for n, p in sorted(k.available.items())},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"{'NAME':<12} {'VER':<8} {'KIND':<8} DESCRIPTION")
    for n, p in sorted(k.available.items(), key=lambda kv: (kv[1].order, kv[0])):
        deps = f"  ← {','.join(p.requires)}" if p.requires else ""
        print(f"{n:<12} {p.version:<8} {p.kind:<8} {p.description}{deps}")
    return 0


def cmd_check(args):
    src = os.path.abspath(args.source)
    with open(src, encoding="utf-8") as f:
        source = f.read()
    k = _load_kernel(args, source)
    print(f";; plugins: {', '.join(k.plugins)}", file=sys.stderr)
    out = args.output or os.path.join(toolchain.cache_dir(),
                                      os.path.basename(src) + ".ss")
    _translate(src, k, out, warn=args.warn)
    print(out)
    return 0


def cmd_build(args):
    src = os.path.abspath(args.source)
    if not os.path.isfile(src):
        raise SystemExit(f"源文件不存在: {src}")
    with open(src, encoding="utf-8") as f:
        source = f.read()

    k = _load_kernel(args, source)
    print(f">>> plugins: {', '.join(k.plugins)}", file=sys.stderr)

    # 可选：先构建插件自带的 C 库
    for name, p in k.plugins.items():
        if args.build_libs and p.build.get("cmd"):
            print(f">>> build {name} C library", file=sys.stderr)
            r = subprocess.run(p.build["cmd"], shell=True, cwd=p.path)
            if r.returncode != 0:
                raise SystemExit(f"{name}: C 库构建失败")

    cd = toolchain.cache_dir()
    out_path = args.out or os.path.splitext(os.path.basename(src))[0]
    stem = os.path.basename(out_path)
    code_ss = os.path.join(cd, f"{stem}.kernel.ss")
    _translate(src, k, code_ss, warn=args.warn)

    text, inputs = bundle_mod.assemble(
        k, open(code_ss, encoding="utf-8").read(),
        extra_ffi=[os.path.abspath(p) for p in (args.ffi or [])],
        header=f"plugins = {', '.join(k.plugins)}")
    key = toolchain.hash_inputs([code_ss, TRANSLATOR, *inputs])
    bundle_path = os.path.join(cd, f"{stem}_{key}.ss")
    if not os.path.isfile(bundle_path):
        with open(bundle_path, "w", encoding="utf-8") as f:
            f.write(text)

    if args.emit_ss:
        shutil.copy(bundle_path, os.path.abspath(args.emit_ss))

    so = toolchain.compile_bundle(bundle_path, f"{stem}_{key}")
    elf = toolchain.build_elf(so, stem, key)

    dest = os.path.abspath(out_path)
    shutil.copy(elf, dest)
    shutil.copy(so, dest + ".so")
    print(f"=== built: {dest}")
    print(f"    {dest}.so")
    if args.run:
        return _exec(dest, args.run_args, k)
    return 0


def _exec(elf, argv, k):
    env = dict(os.environ)
    extra = []
    for p in k.plugins.values():
        for key, rel in p.env.items():
            if key == "LD_LIBRARY_PATH":
                extra.append(os.path.join(p.path, rel))
    if extra:
        env["LD_LIBRARY_PATH"] = ":".join(extra + [env.get("LD_LIBRARY_PATH", "")]).strip(":")
    return subprocess.run([elf] + list(argv or []), env=env).returncode


def cmd_run(args):
    args.run = True
    return cmd_build(args)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="staticpy", description="StaticPy kernel 驱动（插件化）")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("source", help="*.static.py 源文件")
        p.add_argument("-p", "--plugin", help="逗号分隔插件名；省略则按 import 自动推断")
        p.add_argument("--no-auto", action="store_true", help="不自动推断插件")
        p.add_argument("--warn", action="store_true", help="类型检查降级为警告")
        p.add_argument("-o", "--out", help="输出名（默认取源文件名）")

    b = sub.add_parser("build", help="构建独立 ELF")
    common(b)
    b.add_argument("-f", "--ffi", action="append", help="额外的 FFI .scm（可多次）")
    b.add_argument("--build-libs", action="store_true", help="顺带构建插件的 C 库")
    b.add_argument("--emit-ss", help="导出拼装后的 Scheme 文件")
    b.set_defaults(func=cmd_build, run=False, run_args=[])

    r = sub.add_parser("run", help="构建并立即运行")
    common(r)
    r.add_argument("-f", "--ffi", action="append")
    r.add_argument("--build-libs", action="store_true")
    r.add_argument("--emit-ss")
    r.set_defaults(func=cmd_run, run=True, run_args=[])

    c = sub.add_parser("check", help="只翻译成 Scheme")
    common(c)
    c.set_defaults(func=cmd_check, output=None, ffi=None)

    pl = sub.add_parser("plugins", help="列出可用插件")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_plugins)

    argv = list(sys.argv[1:] if argv is None else argv)
    tail = []
    if argv and argv[0] == "run" and "--" in argv:
        i = argv.index("--")
        tail, argv = argv[i + 1:], argv[:i]

    # run 允许把程序参数直接跟在源文件后面（不用 --），因此用 parse_known_args
    args, extra = ap.parse_known_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 1
    if args.cmd == "run":
        args.run_args = tail or extra or []
    try:
        return args.func(args)
    except PluginError as e:
        print(f"插件错误: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
