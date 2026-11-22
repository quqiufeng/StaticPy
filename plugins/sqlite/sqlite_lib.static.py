# sqlite_lib.static.py — libsqlite3 之上的「CPython sqlite3 等价」封装（库文件，无 main）
#
# 分层（照 imgproc / ltorch 的做法：能力挂 `.so`，语义写在 StaticPy 里）：
#
#   libsqlitec.so  ← libsqlite3 的 C ABI（见 cpp/sqlite/sqlite_capi.h）
#        ↑ extern fn（FFI 契约，docs/FFI.md：类型只有 int/float/double/bool/str/ptr）
#   sqlite_lib.static.py（本文件） ← Connection / Cursor，Python 风格调用
#        ↑ concat（build_app.sh 把本文件与用户程序拼成一个 bundle）
#   用户程序（plugins/sqlite/demo.static.py）
#
# SQL 解析、事务、B 树、索引、类型亲和全部落在 libsqlite3 里 —— 我们**不重写**数据库逻辑，
# 所以差分只可能来自「调用形态」（参数绑定/取值类型），不会来自「算错了」。
#
# 约定与偏差（能对齐的对齐，对不齐的写明白）：
#   * 句柄是 `ptr`（sqlite3* / 游标结构体*），不是 int：`int` 在 FFI 表里是 32 位，
#     指针塞进去会被截断。C 侧返回 NULL 时 StaticPy 看到的是 0，用 `== 0` 判空。
#   * 一行是 **list**，不是 tuple（StaticPy 的 tuple 是定长 vector，行宽运行期才知道）。
#   * 参数用长度前缀的类型化串编码（见 enc_params）：i/f/s/n 四种标签 + 长度前缀，
#     所以文本里出现 `,` `:` 换行都不会串味 —— 比 CSV 更适合「任意用户数据」。
#   * 事务：C 侧打开连接时是**自动提交**（sqlite3_open 默认），而 CPython 的
#     `sqlite3` 默认 isolation_level=""（隐式 BEGIN）。要逐位对齐就在用例里显式
#     `BEGIN`/`commit()`，见 difftest.py 的 transaction 用例。
#   * 游标迭代：StaticPy 的 `for` 走 py-items，句柄不是序列，所以写成
#     `for row in cur.fetchall():`（Python 里可以直接 `for row in cur:`，这是记录在案的偏差）。
#   * 异常：StaticPy 的 try/except 只捕获裸 handler，故出错时返回 -1 并可用
#     `last_error()` 取消息，而不是抛 `sqlite3.OperationalError`。
#
# 用法：
#   bash plugins/sqlite/build_app.sh plugins/sqlite/demo.static.py demo
#   LD_LIBRARY_PATH=cpp/sqlite/build ./demo

extern fn sqlitec_version() -> str from "sqlitec"
extern fn sqlitec_last_error() -> str from "sqlitec"

extern fn sqlitec_open(path: str) -> ptr from "sqlitec"
extern fn sqlitec_close(conn: ptr) -> int from "sqlitec"
extern fn sqlitec_commit(conn: ptr) -> int from "sqlitec"
extern fn sqlitec_rollback(conn: ptr) -> int from "sqlitec"
extern fn sqlitec_exec(conn: ptr, sql: str) -> int from "sqlitec"
extern fn sqlitec_changes(conn: ptr) -> int from "sqlitec"
extern fn sqlitec_total_changes(conn: ptr) -> int from "sqlitec"

extern fn sqlitec_cursor(conn: ptr) -> ptr from "sqlitec"
extern fn sqlitec_cursor_close(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_execute(cur: ptr, sql: str) -> int from "sqlitec"
extern fn sqlitec_prepare(cur: ptr, sql: str) -> int from "sqlitec"
extern fn sqlitec_run(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_bind_count(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_bind_int(cur: ptr, idx: int, text: str) -> int from "sqlitec"
extern fn sqlitec_bind_double(cur: ptr, idx: int, v: double) -> int from "sqlitec"
extern fn sqlitec_bind_text(cur: ptr, idx: int, text: str) -> int from "sqlitec"
extern fn sqlitec_bind_null(cur: ptr, idx: int) -> int from "sqlitec"
extern fn sqlitec_has_row(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_advance(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_ncols(cur: ptr) -> int from "sqlitec"
extern fn sqlitec_coltype(cur: ptr, i: int) -> int from "sqlitec"
extern fn sqlitec_colreal(cur: ptr, i: int) -> double from "sqlitec"
extern fn sqlitec_coltext(cur: ptr, i: int) -> str from "sqlitec"
extern fn sqlitec_colname(cur: ptr, i: int) -> str from "sqlitec"
extern fn sqlitec_rowid(cur: ptr) -> str from "sqlitec"
extern fn sqlitec_rowcount(cur: ptr) -> int from "sqlitec"


# ============================== 元信息 ==============================

def version() -> str:
    """SQLite 引擎版本（对标 sqlite3.sqlite_version）"""
    return sqlitec_version()


def last_error() -> str:
    """最近一次失败的原因（对标 sqlite3 抛出的异常消息）"""
    return sqlitec_last_error()


# ============================== 参数 / 行 编解码 ==============================

def bind_one(st: ptr, idx: int, v) -> int:
    """按 Python 类型选 bind_*：str→TEXT / int→int64 / float→REAL / 其余(含 None)→NULL

    判别顺序先 str 再数值：StaticPy 里 `v is None` 的静态类型是 Any，写成 if 条件
    会被判成 "condition must be bool"，所以把 None 收在最后的兜底分支（NULL 语义等价）。
    """
    if isinstance(v, str):
        return sqlitec_bind_text(st, idx, v)
    if isinstance(v, int):
        # 走十进制串：sqlite3 的 INTEGER 是 64 位，FFI 的 `int` 是 32 位。
        # bool 也走这里：int(True) == 1（Python 里 bool 是 int 的子类）。
        return sqlitec_bind_int(st, idx, str(int(v)))
    if isinstance(v, float):
        return sqlitec_bind_double(st, idx, v)
    return sqlitec_bind_null(st, idx)


def bind_params(st: ptr, params: list) -> int:
    """把 list 依次绑到 ?1..?N（下标 1 起，同 sqlite3_bind_* 的约定）

    一个参数一次 FFI 调用：文本长度由 C 侧 strlen 量（字节），
    所以中文/emoji 不会被 len() 的字符数切坏。
    """
    i: int = 0
    while i < len(params):
        if bind_one(st, i + 1, params[i]) != 0:
            return -1
        i += 1
    return 0


def read_row(st: ptr) -> list:
    """读游标的当前行：NULL→None，INTEGER→int，REAL→float，TEXT/BLOB→str

    INTEGER 走 coltext 而不是 colint：sqlite3 的 INTEGER 是 64 位，而 FFI 的 `int`
    是 32 位（大值会被截断）；text 是十进制全精度串，int() 再转回来不丢位。
    """
    n: int = sqlitec_ncols(st)
    row: list = []
    i: int = 0
    while i < n:
        t: int = sqlitec_coltype(st, i)
        if t == 5:
            # sqlite3_column_type 的 NULL 是 **5**（0 不是 NULL！）
            row.append(None)
        elif t == 1:
            row.append(int(sqlitec_coltext(st, i)))
        elif t == 2:
            row.append(sqlitec_colreal(st, i))
        else:
            row.append(sqlitec_coltext(st, i))
        i += 1
    return row


# ============================== Cursor ==============================

class Cursor:
    """sqlite3_stmt 的壳：一条 SQL 一个 prepared statement（同 CPython 的游标语义）"""

    st: ptr

    def __init__(self, st: ptr):
        self.st = st

    # ---------- 执行 ----------
    def execute(self, sql: str, params: list = []) -> int:
        """prepare + bind + step 一次（返回 0 表示成功；出错用 last_error() 取原因）"""
        if len(params) == 0:
            return sqlitec_execute(self.st, sql)
        if sqlitec_prepare(self.st, sql) != 0:
            return -1
        if bind_params(self.st, params) != 0:
            return -1
        if sqlitec_run(self.st) < 0:
            return -1
        return 0

    def executemany(self, sql: str, rows: list) -> int:
        """对每一组参数 execute 一次（同 CPython：不返回结果集）"""
        i: int = 0
        while i < len(rows):
            if self.execute(sql, rows[i]) != 0:
                return -1
            i += 1
        return 0

    # ---------- 取值 ----------
    def fetchone(self):
        """取一行（list）或 None（游标耗尽）—— 同 CPython 的 Cursor.fetchone"""
        if sqlitec_has_row(self.st) == 0:
            return None
        row: list = read_row(self.st)
        sqlitec_advance(self.st)
        return row

    def fetchmany(self, n: int = 1) -> list:
        out: list = []
        i: int = 0
        while i < n:
            if sqlitec_has_row(self.st) == 0:
                return out
            out.append(read_row(self.st))
            sqlitec_advance(self.st)
            i += 1
        return out

    def fetchall(self) -> list:
        out: list = []
        while sqlitec_has_row(self.st) != 0:
            out.append(read_row(self.st))
            sqlitec_advance(self.st)
        return out

    # ---------- 元信息 ----------
    def description(self) -> list:
        """列名 list[str]（CPython 是 list[7-tuple]，我们只留 name —— 记录在案的偏差）"""
        n: int = sqlitec_ncols(self.st)
        out: list = []
        i: int = 0
        while i < n:
            out.append(sqlitec_colname(self.st, i))
            i += 1
        return out

    def lastrowid(self) -> int:
        return int(sqlitec_rowid(self.st))

    def rowcount(self) -> int:
        """查询 -1、DML = 影响行数（同 CPython 的 Cursor.rowcount）"""
        return sqlitec_rowcount(self.st)

    def close(self) -> int:
        return sqlitec_cursor_close(self.st)


# ============================== Connection ==============================

class Connection:
    """sqlite3* 的壳。关闭连接前必须先关所有游标（否则 close 返回 -1）"""

    db: ptr

    def __init__(self, path: str):
        self.db = sqlitec_open(path)

    def cursor(self) -> Cursor:
        return Cursor(sqlitec_cursor(self.db))

    def execute(self, sql: str, params: list = []) -> Cursor:
        """建游标并执行（同 CPython 的 Connection.execute）"""
        cur: Cursor = self.cursor()
        cur.execute(sql, params)
        return cur

    def executescript(self, sql: str) -> int:
        """多语句脚本（同 CPython 的 Connection.executescript：不返回行）"""
        return sqlitec_exec(self.db, sql)

    def commit(self) -> int:
        return sqlitec_commit(self.db)

    def rollback(self) -> int:
        return sqlitec_rollback(self.db)

    def changes(self) -> int:
        """上一条 DML 的影响行数（CPython 是 Cursor.rowcount，这里也留一份连接级视图）"""
        return sqlitec_changes(self.db)

    def total_changes(self) -> int:
        return sqlitec_total_changes(self.db)

    def close(self) -> int:
        return sqlitec_close(self.db)


# ============================== 入口 ==============================

def connect(path: str = ":memory:") -> Connection:
    """同 sqlite3.connect：path 是文件路径，":memory:" 是内存库"""
    return Connection(path)
