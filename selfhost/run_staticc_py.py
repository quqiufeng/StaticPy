#!/usr/bin/env python3
# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""Run staticc.py under CPython by providing Python implementations of
StaticPy builtins it uses."""
import sys, os
import importlib.util

spec = importlib.util.spec_from_file_location("staticc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "staticc.py"))
staticc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staticc)

staticc.argv = lambda: sys.argv
staticc.list_ref = lambda lst, i: lst[i]
staticc.file_open = open
staticc.file_read_all = lambda f: f.read()
staticc.file_close = lambda f: f.close()
staticc.file_write = lambda f, s: f.write(s)
staticc.dict_get_or_empty = lambda d, k: d.get(k, "")
staticc.exit_program = lambda code: sys.exit(code)

if __name__ == "__main__":
    sys.exit(staticc.main())

