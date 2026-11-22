# probe.static.py — sqlite_lib 差分探针（同一份脚本两种跑法）
#
#   StaticPy：bash plugins/sqlite/build_app.sh plugins/sqlite/probe.static.py sqprobe
#             → concat(sqlite_lib + 本文件) → AOT ELF，走 libsqlitec.so
#   CPython ：plugins/sqlite/difftest.py 把本文件拼在 sqlite3 适配层后面直接跑
#
# 所以本文件**不写 extern fn**、只用 sqlite_lib 暴露的 API（connect / version /
# last_error / Connection.* / Cursor.*），这样它同时是合法 Python。
# 行一律 list（CPython 是 tuple，适配层会转），避免表示差异掩盖真实差异。
#
# 刻意避开「一个表达式里多个有副作用的调用」：StaticPy 的函数实参求值顺序是
# 右→左（Chez 侧），而 CPython 是左→右 —— 那是语言层的已知偏差，不该混进
# 数据库的差分里（见 docs/LIBS.md）。


def dump_row(row) -> str:
    """一行 → 稳定的文本表示（list 的 str 两边一致）"""
    if row is None:
        return "None"
    return str(row)


def show(tag: str, cur: Cursor, limit: int = 99) -> int:
    """把游标剩余行逐行打印成 tag=行，返回行数"""
    n: int = 0
    while n < limit:
        row = cur.fetchone()
        if row is None:
            return n
        print(tag + "=" + dump_row(row))
        n += 1
    return n


def main():
    print("version=" + version())

    # ---------- DDL + 各种类型的写入 ----------
    conn: Connection = connect(":memory:")
    conn.executescript("CREATE TABLE t(id INTEGER PRIMARY KEY, a INTEGER, b TEXT, c REAL, d BLOB);")

    cur: Cursor = conn.cursor()
    cur.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [1, "alpha", 1.5])
    print("lastrowid=" + str(cur.lastrowid()))
    cur.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [2, "beta", 2.5])
    cur.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [3, "gamma, 带逗号: 也不怕\n换行", -0.25])
    cur.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [None, None, None])
    cur.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [1099511627776, "big", 0.0])
    print("rowcount=" + str(cur.rowcount()))
    print("total_changes=" + str(conn.total_changes()))
    print("changes=" + str(conn.changes()))

    # ---------- 读回：类型保真 ----------
    sel: Cursor = conn.cursor()
    sel.execute("SELECT id, a, b, c, d FROM t ORDER BY id")
    print("description=" + str(sel.description()))
    print("nrows=" + str(show("row", sel)))
    print("exhausted=" + dump_row(sel.fetchone()))

    # ---------- 标量与聚合 ----------
    agg: Cursor = conn.execute("SELECT count(*), sum(a), avg(a), min(a), max(a) FROM t")
    print("agg=" + dump_row(agg.fetchone()))

    nulls: Cursor = conn.execute("SELECT count(*) FROM t WHERE a IS NULL")
    print("nulls=" + dump_row(nulls.fetchone()))

    real3: Cursor = conn.execute("SELECT avg(x) FROM (SELECT 1.0 AS x UNION ALL SELECT 2.0 UNION ALL SELECT 2.0)")
    print("avg3=" + dump_row(real3.fetchone()))

    # ---------- fetchone / fetchmany / fetchall 的游标推进 ----------
    c1: Cursor = conn.execute("SELECT id FROM t ORDER BY id")
    first = c1.fetchone()
    print("one=" + dump_row(first))
    batch: list = c1.fetchmany(2)
    print("many=" + str(batch))
    print("many2=" + str(c1.fetchmany(10)))
    print("rest=" + str(c1.fetchall()))
    print("one_after=" + dump_row(c1.fetchone()))

    # ---------- executemany ----------
    em: Cursor = conn.cursor()
    em.executemany("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [[10, "m1", 1.0], [11, "m2", 2.0], [12, "m3", 3.0]])
    print("after_many=" + dump_row(conn.execute("SELECT count(*) FROM t").fetchone()))

    # ---------- UPDATE / DELETE 的 rowcount ----------
    upd: Cursor = conn.cursor()
    upd.execute("UPDATE t SET b = ? WHERE a >= ?", ["touched", 10])
    print("update_rowcount=" + str(upd.rowcount()))
    del_cur: Cursor = conn.cursor()
    del_cur.execute("DELETE FROM t WHERE a = ?", [12])
    print("delete_rowcount=" + str(del_cur.rowcount()))

    # ---------- 事务：BEGIN + rollback / commit ----------
    conn.executescript("BEGIN;")
    conn.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [20, "tx", 20.0])
    print("in_tx=" + dump_row(conn.execute("SELECT count(*) FROM t").fetchone()))
    conn.rollback()
    print("after_rollback=" + dump_row(conn.execute("SELECT count(*) FROM t").fetchone()))

    conn.executescript("BEGIN;")
    conn.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [21, "tx2", 21.0])
    conn.commit()
    print("after_commit=" + dump_row(conn.execute("SELECT count(*) FROM t").fetchone()))

    # ---------- 大整数（int64 全范围）+ 布尔 ----------
    big: Cursor = conn.cursor()
    big.execute("INSERT INTO t(a, b, c) VALUES (?, ?, ?)", [9007199254740993, "int64", 1.0])
    print("big=" + str(big.lastrowid()))
    got: Cursor = conn.execute("SELECT a FROM t WHERE b = ?", ["int64"])
    print("big_back=" + dump_row(got.fetchone()))
    neg: Cursor = conn.execute("SELECT ? + 0", [-9007199254740993])
    print("neg_back=" + dump_row(neg.fetchone()))

    # ---------- 两个游标互不干扰 ----------
    a1: Cursor = conn.execute("SELECT a FROM t WHERE a IS NOT NULL ORDER BY a")
    a2: Cursor = conn.execute("SELECT b FROM t WHERE b IS NOT NULL ORDER BY a")
    print("a1_first=" + dump_row(a1.fetchone()))
    print("a2_first=" + dump_row(a2.fetchone()))
    print("a1_second=" + dump_row(a1.fetchone()))

    # ---------- 空结果集 ----------
    empty: Cursor = conn.execute("SELECT id, b FROM t WHERE a = ?", [-1])
    print("empty_desc=" + str(empty.description()))
    print("empty_rows=" + str(empty.fetchall()))
    print("empty_one=" + dump_row(empty.fetchone()))

    # ---------- 错误路径：不抛异常，走 last_error() ----------
    bad: Cursor = conn.cursor()
    print("bad_rc=" + str(bad.execute("SELECT * FROM no_such_table")))
    print("bad_err_nonempty=" + str(len(last_error()) > 0))
    bad2: Cursor = conn.cursor()
    print("bad_rc2=" + str(bad2.execute("INSERT INTO t(nope) VALUES (1)", [])))
    print("bad_err2_nonempty=" + str(len(last_error()) > 0))

    print("ok")
