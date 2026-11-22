# demo.static.py — sqlite_lib（Connection/Cursor）的功能演示
#
# 对应 CPython：
#   import sqlite3
#   conn = sqlite3.connect(":memory:")
#   cur = conn.cursor(); cur.execute(...); cur.fetchall()


def main():
    print("sqlite " + version())
    conn: Connection = connect(":memory:")
    conn.executescript("CREATE TABLE t(a INTEGER, b TEXT, c REAL);")

    cur: Cursor = conn.cursor()
    cur.execute("INSERT INTO t VALUES (?, ?, ?)", [1, "alpha", 1.5])
    cur.execute("INSERT INTO t VALUES (?, ?, ?)", [2, "beta", None])
    cur.execute("INSERT INTO t VALUES (?, ?, ?)", [3, "gamma, 带逗号: 也不怕", -0.25])
    print("rowcount=" + str(cur.rowcount()) + " lastrowid=" + str(cur.lastrowid()))
    print("total_changes=" + str(conn.total_changes()))

    cur.execute("SELECT a, b, c FROM t ORDER BY a")
    print("columns=" + str(cur.description()))
    rows: list = cur.fetchall()
    i: int = 0
    while i < len(rows):
        print("row " + str(rows[i]))
        i += 1

    # 参数绑定：(int, str, float) 与 NULL
    q: Cursor = conn.execute("SELECT count(*), sum(a), avg(c) FROM t WHERE a >= ?", [2])
    print("agg=" + str(q.fetchone()))

    # fetchone / fetchmany 的游标语义
    # 注意：StaticPy 的函数实参求值顺序是右→左（Chez 侧），所以拆成多条语句，
    # 不把三个有副作用的调用塞进一个 print 里（CPython 是左→右）。
    q2: Cursor = conn.execute("SELECT a FROM t ORDER BY a")
    one = q2.fetchone()
    many: list = q2.fetchmany(5)
    rest: list = q2.fetchall()
    print("one=" + str(one))
    print("many=" + str(many))
    print("rest=" + str(rest))

    # 事务：显式 BEGIN + rollback，行数必须回到 3
    conn.executescript("BEGIN;")
    conn.execute("INSERT INTO t VALUES (4, 'rolled-back', 0.0)")
    print("in-tx=" + str(conn.changes()))
    conn.rollback()
    print("after-rollback=" + str(conn.execute("SELECT count(*) FROM t").fetchone()))

    print("ok")
