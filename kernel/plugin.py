#!/usr/bin/env python3
"""kernel.plugin — 插件发现 / 依赖解析 / 钩子派发。

插件 = 一个目录，含 plugin.json（清单）+ 可选 runtime.scm / ffi.scm / hooks.py。

plugin.json
-----------
{
  "name": "imgproc",              # 必填，唯一
  "version": "1.0.0",
  "kind": "ffi",                  # runtime | syntax | ffi | mixed （仅描述用途）
  "description": "Pillow 对标图像库",
  "requires": ["core", "libc"],   # 依赖（自动补齐、拓扑排序）
  "order": 200,                   # 运行时片段拼接顺序（小在前）
  "runtime": ["runtime.scm"],     # 拼进产物的 Scheme 片段（可多个，按序）
  "ffi": ["ffi.scm"],             # load-shared-object / foreign-procedure 声明
  "syntax": "hooks.py",           # 可选：Python 语法扩展
  "libs": {"imgproc": "/path/libimgproc.so"},   # 逻辑名 -> soname/绝对路径
  "modules": {"pil": {"open": "pil-open"}},     # import pil -> pil-open
  "nested_modules": {"os.path": {"exists": "os_file_exists"}},
  "return_types": {"pil-open": "ptr"},          # 供类型推断
  "prelude_functions": ["pil-open"],            # 已在 Scheme 侧实现，不走 FFI
  "build": {"cmd": "bash build_cpp.sh", "outputs": ["build/libimgproc.so"]},
  "env": {"LD_LIBRARY_PATH": "build"}           # 运行期提示（CLI run 用）
}

hooks.py
--------
def register(k):
    k.expr(ast.Call, my_handler)     # -> Scheme 字符串 或 None（交回内核）
    k.stmt(ast.With, my_stmt)
    k.rewrite(lambda code: code)     # 源码级预处理
"""
from __future__ import annotations

import ast
import glob
import json
import os
import sys

MANIFEST_NAMES = ("plugin.json", "staticpy.plugin.json")


class PluginError(Exception):
    pass


class Plugin:
    def __init__(self, path: str, data: dict):
        self.path = os.path.abspath(path)
        self.name = data.get("name") or os.path.basename(self.path)
        self.version = data.get("version", "0.0.0")
        self.kind = data.get("kind", "runtime")
        self.description = data.get("description", "")
        self.requires = list(data.get("requires", []))
        self.order = int(data.get("order", 500))
        self.runtime = self._files(data.get("runtime") or [])
        self.ffi = self._files(data.get("ffi") or [])
        self.syntax = data.get("syntax")
        self.libs = dict(data.get("libs") or {})
        self.modules = dict(data.get("modules") or {})
        self.nested_modules = dict(data.get("nested_modules") or {})
        self.return_types = dict(data.get("return_types") or {})
        self.prelude_functions = list(data.get("prelude_functions") or [])
        self.build = data.get("build") or {}
        self.env = dict(data.get("env") or {})
        self.extra = {k: v for k, v in data.items() if k not in self.__dict__}

    def _files(self, patterns):
        out = []
        for pat in patterns:
            hits = sorted(glob.glob(os.path.join(self.path, pat)))
            if not hits and not any(ch in pat for ch in "*?["):
                raise PluginError(f"{self.name}: 清单引用的文件不存在 {pat}")
            out.extend(hits)
        return out

    def __repr__(self):
        return f"<Plugin {self.name} {self.version} {self.kind}>"


def discover_dirs():
    """插件搜索路径：env > 仓库 plugins/ > ~/.staticpy/plugins"""
    dirs = []
    env = os.environ.get("STATICPY_PLUGINS_PATH")
    if env:
        dirs.extend(p for p in env.split(os.pathsep) if p)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirs.append(os.path.join(here, "plugins"))
    dirs.append(os.path.join(os.path.expanduser("~"), ".staticpy", "plugins"))
    return [d for d in dirs if os.path.isdir(d)]


def scan(dirs=None):
    """扫描所有插件目录：name -> Plugin"""
    found = {}
    for d in dirs or discover_dirs():
        for entry in sorted(os.listdir(d)):
            p = os.path.join(d, entry)
            if not os.path.isdir(p):
                continue
            for mn in MANIFEST_NAMES:
                mf = os.path.join(p, mn)
                if os.path.isfile(mf):
                    with open(mf, encoding="utf-8") as f:
                        data = json.load(f)
                    plug = Plugin(p, data)
                    if plug.name in found:
                        # 先出现者优先（便于用户用 STATICPY_PLUGINS_PATH 覆盖内置插件）
                        continue
                    found[plug.name] = plug
                    break
    return found


class Kernel:
    """一组已解析的插件 + 钩子派发器。"""

    def __init__(self, plugins=None, available=None):
        self.plugins = plugins or {}
        self.available = available if available is not None else scan()
        self._expr_handlers = []
        self._stmt_handlers = []
        self._rewriters = []
        self.api = {}          # 由翻译器 bind() 注入：translate_expr / infer_expr_type / ...
        self.diagnostics = []

    # ---------------------------------------------------------------- 发现
    @classmethod
    def discover(cls, dirs=None):
        avail = scan(dirs)
        return cls({}, avail)

    def names(self):
        return sorted(self.available)

    # ---------------------------------------------------------------- 加载
    def resolve(self, names, auto=True, source=""):
        """补依赖 + 拓扑排序；auto=True 时按源码 import 自动启用。"""
        want = list(names or [])
        if auto and source:
            want.extend(self.detect(source))
        seen, ordered = set(), []

        def visit(n, chain):
            if n in seen:
                return
            if n not in self.available:
                raise PluginError(
                    f"插件 {n} 不存在（可用: {', '.join(sorted(self.available))}）")
            if n in chain:
                raise PluginError(f"插件依赖成环: {' -> '.join(chain + [n])}")
            plug = self.available[n]
            for dep in plug.requires:
                visit(dep, chain + [n])
            seen.add(n)
            ordered.append(plug)

        for n in want:
            visit(n, [])
        ordered.sort(key=lambda p: p.order)
        self.plugins = {p.name: p for p in ordered}
        return ordered

    def detect(self, source):
        """按源码里的 import / extern fn from "lib" 推断插件。"""
        hits = []
        tree = None
        try:
            tree = ast.parse(_strip_extern_blocks(source))
        except SyntaxError:
            tree = None
        imported = set()
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imported.add(a.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
        for name, plug in self.available.items():
            mods = set(plug.modules) | {k.split(".")[0] for k in plug.nested_modules}
            if imported & mods:
                hits.append(name)
                continue
            # 裸函数 import：from os import listdir
            bare = set()
            for fns in plug.modules.values():
                if isinstance(fns, dict):
                    bare |= set(fns)
            if tree is not None and bare:
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module in plug.modules:
                        if {a.name for a in node.names} & bare:
                            hits.append(name)
                            break
        for m in _extern_libs(source):
            for name, plug in self.available.items():
                if m in plug.libs:
                    hits.append(name)
        return sorted(set(hits))

    # ---------------------------------------------------------------- 钩子
    def load_hooks(self):
        for plug in self.plugins.values():
            if not plug.syntax:
                continue
            path = os.path.join(plug.path, plug.syntax)
            if not os.path.isfile(path):
                raise PluginError(f"{plug.name}: syntax 文件不存在 {path}")
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"staticpy_plugin_{plug.name}", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            if hasattr(mod, "register"):
                mod.register(self)
        return self

    def bind(self, **api):
        """翻译器注入内部函数，供 hooks 复用（避免循环 import）。"""
        self.api.update(api)
        return self

    def expr(self, node_type, handler):
        self._expr_handlers.append((node_type, handler))

    def stmt(self, node_type, handler):
        self._stmt_handlers.append((node_type, handler))

    def rewrite(self, fn):
        self._rewriters.append(fn)

    def dispatch_expr(self, node):
        for ntype, fn in self._expr_handlers:
            if isinstance(node, ntype):
                out = fn(node, self)
                if out:
                    return out
        return None

    def dispatch_stmt(self, node):
        for ntype, fn in self._stmt_handlers:
            if isinstance(node, ntype):
                out = fn(node, self)
                if out:
                    return out
        return None

    def rewrite_source(self, code):
        for fn in self._rewriters:
            code = fn(code)
        return code

    # ---------------------------------------------------------------- 汇总
    @property
    def modules(self):
        out = {}
        for p in self.plugins.values():
            out.update(p.modules)
        return out

    @property
    def nested_modules(self):
        out = {}
        for p in self.plugins.values():
            for k, v in p.nested_modules.items():
                out[tuple(k.split("."))] = v
        return out

    @property
    def return_types(self):
        out = {}
        for p in self.plugins.values():
            out.update(p.return_types)
        return out

    @property
    def prelude_functions(self):
        out = set()
        for p in self.plugins.values():
            out |= set(p.prelude_functions)
        return out

    @property
    def lib_map(self):
        out = {}
        for p in self.plugins.values():
            out.update(p.libs)
        return out

    def runtime_files(self):
        return [(p.name, f) for p in self.plugins.values() for f in p.runtime]

    def ffi_files(self):
        return [(p.name, f) for p in self.plugins.values() for f in p.ffi]

    def merge_into(self, T):
        """把插件表合并进翻译器模块的全局表（保持旧函数引用可用）。"""
        T.BUILTIN_MODULES.clear()
        T.BUILTIN_MODULES.update(self.modules)
        T.NESTED_MODULES.clear()
        T.NESTED_MODULES.update(self.nested_modules)
        T.MODULE_FN_RETURN_TYPES.clear()
        T.MODULE_FN_RETURN_TYPES.update(self.return_types)
        # PRELUDE_FUNCTIONS 含 MATH_FUNCTIONS（数学函数不是 C FFI）
        T.PRELUDE_FUNCTIONS.clear()
        T.PRELUDE_FUNCTIONS.update(self.prelude_functions)
        T.KERNEL_LIBS.clear()
        T.KERNEL_LIBS.update(self.lib_map)
        return self

    def describe(self):
        lines = []
        for p in self.plugins.values():
            lines.append(f"{p.name:<12} {p.version:<8} {p.kind:<8} {p.description}")
        return "\n".join(lines)


# ------------------------------------------------------------------ 源码辅助
def _strip_extern_blocks(src: str) -> str:
    import re
    return re.sub(r"(?m)^\s*extern\s+fn\s+.*?from\s+\"\w+\"", "", src, flags=re.S)


def _extern_libs(src: str):
    import re
    return set(re.findall(r'extern\s+fn\s+\w+\s*\(.*?\)\s*->\s*\w+\s+from\s+"(\w+)"',
                          src, re.S))
