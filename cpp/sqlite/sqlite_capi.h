/* sqlite_capi.h — libsqlite3 的 C ABI（给 StaticPy 的 extern fn 用）
 *
 * 约定（与 cpp/torch/torch_capi.h 一致）：
 *   * 句柄一律 void*（StaticPy 侧声明成 `ptr`）：`int` 在 FFI 表里是 32 位，
 *     指针塞进去会被截断。
 *   * 返回字符串的用 const char*（StaticPy 侧 `str`）：缓冲区是进程内单例，
 *     foreign-procedure 的 `string` 结果会立刻拷成 Scheme 字符串，所以可以复用。
 *   * 所有函数都返回 int 而非 void（FFI 契约：没有 void 返回，见 docs/FFI.md）。
 *
 * 游标语义（对齐 CPython sqlite3.Cursor）：
 *   execute() = prepare + bind + step 一次；`has_row` 表示「当前有一行可取」。
 *   fetchone() = 读当前行 → advance（再 step 一次）。fetchall()/fetchmany() 同理。
 */
#ifndef SQLITE_CAPI_H
#define SQLITE_CAPI_H

#ifdef __cplusplus
extern "C" {
#endif

/* ---- 连接 ---- */
void *sqlitec_open(const char *path);   /* ":memory:" 亦可；失败返回 NULL 并置 last_error */
int sqlitec_close(void *conn);
int sqlitec_commit(void *conn);
int sqlitec_rollback(void *conn);
int sqlitec_exec(void *conn, const char *sql);   /* executescript：多语句，无行返回 */
int sqlitec_changes(void *conn);                 /* 上一条 DML 影响行数 */
int sqlitec_total_changes(void *conn);

/* ---- 游标 ---- */
void *sqlitec_cursor(void *conn);        /* 新游标（空 stmt），失败 NULL */
int sqlitec_cursor_close(void *cur);
/* 无参语句：prepare + step 一次（等价 prepare/run 二连） */
int sqlitec_execute(void *cur, const char *sql);
/* 带参语句：prepare → bind_*（按下标 1..N）→ run
 *
 * 为什么一个参数一次 FFI 调用，而不是像 imgproc 那样打成一个串：
 *   StaticPy 的 `len(str)` 是**字符数**，而 sqlite3_bind_text 要**字节数**；
 *   UTF-8 文本（中文 3 字节）用字符数当长度会把串切坏。让 C 侧用 strlen 量，
 *   长度问题就自动消失了 —— 代价只是每个参数多一次 FFI 往返（~40ns）。
 *   非 ASCII 的坑见 difftest.py 的 utf8 用例。 */
int sqlitec_prepare(void *cur, const char *sql);
int sqlitec_run(void *cur);              /* step 一次，更新 has_row */
int sqlitec_bind_count(void *cur);       /* 语句里的参数个数（? / :name 都算） */
int sqlitec_bind_int(void *cur, int idx, const char *text);   /* int64：十进制串进，避免 32 位截断 */
int sqlitec_bind_double(void *cur, int idx, double v);
int sqlitec_bind_text(void *cur, int idx, const char *text);  /* 长度由 C 侧 strlen 定 */
int sqlitec_bind_null(void *cur, int idx);
int sqlitec_has_row(void *cur);          /* 1=有当前行 0=没有（耗尽或非查询） */
int sqlitec_advance(void *cur);          /* step 到下一行，更新 has_row */
int sqlitec_ncols(void *cur);
int sqlitec_coltype(void *cur, int i);   /* 0=null 1=int 2=real 3=text（同 sqlite3_column_type） */
long long sqlitec_colint(void *cur, int i);
double sqlitec_colreal(void *cur, int i);
const char *sqlitec_coltext(void *cur, int i);
const char *sqlitec_colname(void *cur, int i);
const char *sqlitec_rowid(void *cur);    /* last_insert_rowid，十进制串（int64 全范围） */
int sqlitec_rowcount(void *cur);         /* 查询=-1，DML=changes（同 CPython） */

/* ---- 元信息 ---- */
const char *sqlitec_version(void);
const char *sqlitec_last_error(void);

#ifdef __cplusplus
}  /* extern "C" */
#endif

#endif /* SQLITE_CAPI_H */
