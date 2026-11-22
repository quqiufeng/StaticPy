/* sqlite_capi.cpp — libsqlite3 的 C ABI 实现（见 sqlite_capi.h 的约定）
 *
 * 这一层只做「句柄 ⇄ sqlite3 原生对象」的翻译与类型化取值，
 * SQL 解析、事务、B 树、索引全部落在 libsqlite3 里 —— 我们**不重写**任何数据库逻辑。
 */
#include "sqlite_capi.h"

#include <sqlite3.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

namespace {

/* 进程内单例输出缓冲：返回给 StaticPy 的 str 会被立刻拷成 Scheme 字符串，
 * 所以复用一块缓冲是安全的（也避免了每次 fetch 都 malloc/free）。 */
std::string g_out;
char g_err[2048] = {0};

void set_err(const char *msg) {
  if (msg == nullptr) msg = "";
  std::snprintf(g_err, sizeof(g_err), "%s", msg);
}
void set_err_db(sqlite3 *db) { set_err(db ? sqlite3_errmsg(db) : "no connection"); }

const char *ret(const std::string &s) {
  g_out = s;
  return g_out.c_str();
}

struct Cur {
  sqlite3 *db;
  sqlite3_stmt *st;
  int has_row;
  long long rowid;
};

}  // namespace

/* ---------------- 连接 ---------------- */

void *sqlitec_open(const char *path) {
  sqlite3 *db = nullptr;
  const char *p = (path == nullptr || path[0] == '\0') ? ":memory:" : path;
  int rc = sqlite3_open_v2(p, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr);
  if (rc != SQLITE_OK) {
    set_err(db ? sqlite3_errmsg(db) : sqlite3_errstr(rc));
    if (db) sqlite3_close(db);
    return nullptr;
  }
  /* CPython 的 sqlite3 默认 isolation_level=""（隐式事务），我们给自动提交（NULL）：
   * 语义差别写在 docs/LIBS.md，差分用例显式用 commit()/BEGIN 对齐。 */
  sqlite3_busy_timeout(db, 5000);
  return db;
}

int sqlitec_close(void *conn) {
  if (conn == nullptr) return 0;
  int rc = sqlite3_close(static_cast<sqlite3 *>(conn));
  if (rc != SQLITE_OK) {
    set_err("close failed: connection busy (cursors still open?)");
    return -1;
  }
  return 0;
}

int sqlitec_commit(void *conn) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  if (db == nullptr) return -1;
  int rc = sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
  if (rc != SQLITE_OK) {
    set_err_db(db);
    return -1;
  }
  return 0;
}

int sqlitec_rollback(void *conn) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  if (db == nullptr) return -1;
  int rc = sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);
  if (rc != SQLITE_OK) {
    set_err_db(db);
    return -1;
  }
  return 0;
}

int sqlitec_exec(void *conn, const char *sql) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  if (db == nullptr || sql == nullptr) return -1;
  char *msg = nullptr;
  int rc = sqlite3_exec(db, sql, nullptr, nullptr, &msg);
  if (rc != SQLITE_OK) {
    set_err(msg ? msg : sqlite3_errmsg(db));
    if (msg) sqlite3_free(msg);
    return -1;
  }
  return 0;
}

int sqlitec_changes(void *conn) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  return db ? sqlite3_changes(db) : -1;
}

int sqlitec_total_changes(void *conn) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  return db ? sqlite3_total_changes(db) : -1;
}

/* ---------------- 游标 ---------------- */

void *sqlitec_cursor(void *conn) {
  sqlite3 *db = static_cast<sqlite3 *>(conn);
  if (db == nullptr) return nullptr;
  Cur *c = new (std::nothrow) Cur();
  if (c == nullptr) return nullptr;
  c->db = db;
  c->st = nullptr;
  c->has_row = 0;
  c->rowid = 0;
  return c;
}

int sqlitec_cursor_close(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr) return 0;
  if (c->st) sqlite3_finalize(c->st);
  delete c;
  return 0;
}

/* 无参：prepare + step 一次 */
int sqlitec_execute(void *cur, const char *sql) {
  if (sqlitec_prepare(cur, sql) != 0) return -1;
  sqlitec_run(cur);
  return 0;
}

int sqlitec_prepare(void *cur, const char *sql) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || sql == nullptr) {
    set_err("null cursor/sql");
    return -1;
  }
  if (c->st) {
    sqlite3_finalize(c->st);
    c->st = nullptr;
  }
  c->has_row = 0;
  int rc = sqlite3_prepare_v2(c->db, sql, -1, &c->st, nullptr);
  if (rc != SQLITE_OK) {
    set_err_db(c->db);
    c->st = nullptr;
    return -1;
  }
  if (c->st == nullptr) { /* 空语句（只有注释/空白） */
    set_err("empty statement");
    return -1;
  }
  return 0;
}

int sqlitec_run(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) {
    set_err("no prepared statement");
    return -1;
  }
  c->rowid = sqlite3_last_insert_rowid(c->db);
  int rc = sqlite3_step(c->st);
  if (rc == SQLITE_ROW) {
    c->has_row = 1;
    return 1;
  }
  if (rc != SQLITE_DONE) {
    set_err_db(c->db);
    c->has_row = 0;
    return -1;
  }
  c->has_row = 0;
  c->rowid = sqlite3_last_insert_rowid(c->db); /* DML 后更新 lastrowid */
  return 0;
}

int sqlitec_bind_count(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  return (c && c->st) ? sqlite3_bind_parameter_count(c->st) : 0;
}

static int bind_rc(Cur *c, int rc) {
  if (rc != SQLITE_OK) {
    set_err_db(c->db);
    return -1;
  }
  return 0;
}

int sqlitec_bind_int(void *cur, int idx, const char *text) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return -1;
  long long v = (text == nullptr) ? 0 : std::strtoll(text, nullptr, 10);
  return bind_rc(c, sqlite3_bind_int64(c->st, idx, static_cast<sqlite3_int64>(v)));
}

int sqlitec_bind_double(void *cur, int idx, double v) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return -1;
  return bind_rc(c, sqlite3_bind_double(c->st, idx, v));
}

int sqlitec_bind_text(void *cur, int idx, const char *text) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return -1;
  /* -1 长度 = 让 SQLite 自己 strlen（字节数），UTF-8 多字节安全 */
  return bind_rc(c, sqlite3_bind_text(c->st, idx, text ? text : "", -1, SQLITE_TRANSIENT));
}

int sqlitec_bind_null(void *cur, int idx) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return -1;
  return bind_rc(c, sqlite3_bind_null(c->st, idx));
}

int sqlitec_has_row(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  return c ? c->has_row : 0;
}

int sqlitec_advance(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return 0;
  int rc = sqlite3_step(c->st);
  c->has_row = (rc == SQLITE_ROW) ? 1 : 0;
  if (rc != SQLITE_ROW && rc != SQLITE_DONE) {
    set_err_db(sqlite3_db_handle(c->st));
    return -1;
  }
  return c->has_row;
}

int sqlitec_ncols(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  return (c && c->st) ? sqlite3_column_count(c->st) : 0;
}

int sqlitec_coltype(void *cur, int i) {
  Cur *c = static_cast<Cur *>(cur);
  return (c && c->st) ? sqlite3_column_type(c->st, i) : 0;
}

long long sqlitec_colint(void *cur, int i) {
  Cur *c = static_cast<Cur *>(cur);
  return (c && c->st) ? sqlite3_column_int64(c->st, i) : 0;
}

double sqlitec_colreal(void *cur, int i) {
  Cur *c = static_cast<Cur *>(cur);
  return (c && c->st) ? sqlite3_column_double(c->st, i) : 0.0;
}

const char *sqlitec_coltext(void *cur, int i) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return ret(std::string());
  const unsigned char *t = sqlite3_column_text(c->st, i);
  int n = sqlite3_column_bytes(c->st, i);
  if (t == nullptr) return ret(std::string());
  return ret(std::string(reinterpret_cast<const char *>(t), static_cast<size_t>(n)));
}

const char *sqlitec_colname(void *cur, int i) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return ret(std::string());
  const char *nm = sqlite3_column_name(c->st, i);
  return ret(std::string(nm ? nm : ""));
}

const char *sqlitec_rowid(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr) return ret("0");
  char buf[32];
  std::snprintf(buf, sizeof(buf), "%lld", c->rowid);
  return ret(std::string(buf));
}

int sqlitec_rowcount(void *cur) {
  Cur *c = static_cast<Cur *>(cur);
  if (c == nullptr || c->st == nullptr) return -1;
  if (sqlite3_column_count(c->st) > 0) return -1; /* CPython：查询行数未知 = -1 */
  return sqlite3_changes(sqlite3_db_handle(c->st));
}

/* ---------------- 元信息 ---------------- */

const char *sqlitec_version(void) { return sqlite3_libversion(); }
const char *sqlitec_last_error(void) { return g_err; }
