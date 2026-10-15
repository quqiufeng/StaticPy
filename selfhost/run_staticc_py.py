#!/usr/bin/env python3
"""Run staticc.py under CPython by providing Python implementations of
StaticPy builtins it uses."""
import sys
import importlib.util

spec = importlib.util.spec_from_file_location("staticc", "staticc.py")
staticc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staticc)

staticc.argv = lambda: sys.argv
staticc.list_ref = lambda lst, i: lst[i]
staticc.file_open = open
staticc.file_read_all = lambda f: f.read()
staticc.file_close = lambda f: f.close()
staticc.file_write = lambda f, s: f.write(s)
staticc.dict_get_or_empty = lambda d, k: d.get(k, "")

if __name__ == "__main__":
    sys.exit(staticc.main())

