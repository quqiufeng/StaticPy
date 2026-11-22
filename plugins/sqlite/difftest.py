#!/usr/bin/env python3
# difftest.py — sqlite_lib（Connection/Cursor）对拍 CPython 的 sqlite3
#
# 口径：**同一份用户脚本，两种后端**
#   参考 = CPython3 `sqlite3`（标准库，同一台机器的 libsqlite3 3.45.1）
#   我方 = AOT ELF（build_app.sh 拼 sqlite_lib + probe，走 libsqlitec.so → libsqlite3）
#
# 所以差异只可能来自「调用形态」（绑定/取值/句柄语义），不会来自「SQL 算错了」——
# SQL 引擎两边是同一份 C 库。适配层（下面的 SHIM）把 CPython 的 sqlite3 打扮成
# 我们的 API：行转 list、description 转列名、异常转 rc+-1 + last_error()，
# 并且 isolation_level=None（自动提交）对齐 C ABI 的默认行为。
#
# 用法：
#   python3 plugins/sqlite/difftest.py [-v] [--no-elf] [--only KEY]
#   -v        逐行打印两边输出
#   --no-elf  只跑 CPython 侧（不编译，快速看参考输出）
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.expanduser("~/iso_gen/sqlite")
PROBE = os.path.join(HERE, "probe.static.py")
LIBDIR = os.path.join(ROOT, "cpp/sqlite/build")

# ---------------------------------------------------------------- CPython 适配层
SHIM = r'''# 自动生成（plugins/sqlite/difftest.py）—— 把 CPython sqlite3 打扮成 sqlite_lib 的 API
import sqlite3

_ERR = [""]
_LAST_CHANGES = [0]


def version():
    return sqlite3.sqlite_version


def last_error():
    return _ERR[0]


class Cursor:
    def __init__(self, c):
        self._c = c

    def execute(self, sql, params=[]):
        _ERR[0] = ""
        try:
            if len(params) == 0:
                self._c.execute(sql)
            else:
                self._c.execute(sql, tuple(params))
            _LAST_CHANGES[0] = self._c.rowcount
            return 0
        except sqlite3.Error as e:
            _ERR[0] = str(e)
            return -1

    def executemany(self, sql, rows):
        _ERR[0] = ""
        try:
            self._c.executemany(sql, [tuple(r) for r in rows])
            _LAST_CHANGES[0] = self._c.rowcount
            return 0
        except sqlite3.Error as e:
            _ERR[0] = str(e)
            return -1

    def fetchone(self):
        r = self._c.fetchone()
        return None if r is None else list(r)

    def fetchmany(self, n=1):
        return [list(r) for r in self._c.fetchmany(n)]

    def fetchall(self):
        return [list(r) for r in self._c.fetchall()]

    def description(self):
        d = self._c.description
        return [] if d is None else [x[0] for x in d]

    def lastrowid(self):
        return self._c.lastrowid

    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()
        return 0


class Connection:
    def __init__(self, path):
        # isolation_level=None = 自动提交，对齐 sqlitec_open 的默认行为
        self._c = sqlite3.connect(path, isolation_level=None)

    def cursor(self):
        return Cursor(self._c.cursor())

    def execute(self, sql, params=[]):
        cur = Cursor(self._c.cursor())
        cur.execute(sql, params)
        return cur

    def executescript(self, sql):
        _ERR[0] = ""
        try:
            self._c.executescript(sql)
            return 0
        except sqlite3.Error as e:
            _ERR[0] = str(e)
            return -1

    def commit(self):
        self._c.commit()
        return 0

    def rollback(self):
        self._c.rollback()
        return 0

    def changes(self):
        return _LAST_CHANGES[0]

    def total_changes(self):
        return self._c.total_changes

    def close(self):
        self._c.close()
        return 0


def connect(path=":memory:"):
    return Connection(path)

'''


def reference_output():
    """CPython 参考：SHIM + probe 源码 + main()"""
    src = open(PROBE, encoding="utf-8").read()
    body = SHIM + "\n" + src + "\n\nmain()\n"
    os.makedirs(WORK, exist_ok=True)
    path = os.path.join(WORK, "probe_ref.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit("CPython 参考脚本失败（rc=%d）" % r.returncode)
    return r.stdout


def our_output():
    """StaticPy：concat(sqlite_lib + probe) → AOT ELF"""
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = LIBDIR + ":" + env.get("LD_LIBRARY_PATH", "")
    env.setdefault("TMPDIR", os.path.join(os.path.expanduser("~"), "iso_gen", "ctlbin"))
    env["STATICPY_OUTDIR"] = env.get("STATICPY_OUTDIR", os.path.join(os.path.expanduser("~"), "iso_gen", "ctlbin"))
    b = subprocess.run(["bash", os.path.join(HERE, "build_app.sh"), PROBE, "sqprobe"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    if b.returncode != 0:
        sys.stderr.write(b.stdout[-3000:] + b.stderr[-3000:])
        raise SystemExit("构建失败（rc=%d）" % b.returncode)
    if "type error" in b.stdout:
        sys.stderr.write(b.stdout)
        raise SystemExit("翻译器报类型错误 —— 类型错误会静默产出错代码，必须修")
    exe = os.path.join(env["STATICPY_OUTDIR"], "sqprobe")
    r = subprocess.run([exe], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit("ELF 运行失败（rc=%d）" % r.returncode)
    return r.stdout


def main():
    verbose = "-v" in sys.argv
    no_elf = "--no-elf" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    ref = reference_output().splitlines()
    if no_elf:
        for line in ref:
            if only is None or line.startswith(only):
                print(line)
        print("--- 参考输出 %d 行（--no-elf，未编译）" % len(ref))
        return 0

    ours = our_output().splitlines()
    cases = [l.split("=", 1)[0] for l in ref]
    ok = 0
    bad = []
    n = max(len(ref), len(ours))
    for i in range(n):
        a = ref[i] if i < len(ref) else "<missing>"
        b = ours[i] if i < len(ours) else "<missing>"
        key = a.split("=", 1)[0]
        if only is not None and not key.startswith(only):
            continue
        if a == b:
            ok += 1
            if verbose:
                print("ok   %s" % a)
        else:
            bad.append((key, a, b))
            print("DIFF %s\n  ref = %s\n  got = %s" % (key, a, b))
    total = ok + len(bad)
    print("\n%d/%d 一致" % (ok, total))
    if bad:
        print("红项：" + ", ".join(k for k, _, _ in bad))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
