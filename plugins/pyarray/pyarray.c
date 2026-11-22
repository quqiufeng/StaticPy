/* pyarray.c — PyArray 的 C 内核：Python dict 语义的紧凑哈希表
 *
 * 布局照抄 Zend HashTable（PHP array）：
 *   items[]  按**插入序**连续存放（删除只打墓碑）；
 *   index[]  开放寻址的 hash -> items 下标（0=空，0xFFFFFFFF=墓碑）；
 *   空洞过多才压缩（items 重排 + index 重建）。
 * 收益：keys()/foreach 天然保序（等价 CPython 3.7+ 的插入序），查找删除 O(1)。
 *
 * **值不进 C**：val 是 Scheme 侧 handle 表的下标（int64），-1 表示"没有旧值"。
 * 键两种：int（K_INT）与 Scheme 侧 intern 好的字符串 id（K_STR）。
 *
 * 约定（AGENTS.md §4）：所有函数返回 int64，不返回 void。
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define K_EMPTY 0
#define K_INT   1
#define K_STR   2

#define IDX_TOMB 0xFFFFFFFFu
#define NOVAL    (-1)
#define ERR      (-2)

typedef struct {
    int64_t key;
    int64_t val;
    uint64_t hk;               /* 高 62 位=哈希，低 2 位=kind（K_EMPTY=0 ⇒ hk=0 即空槽） */
} pslot;                       /* 24 字节（原先 32：多出的 kind+pad 吃掉一整个 cache 行份额） */

#define HK(h, k)   (((h) & ~(uint64_t)3) | (uint64_t)(k))
#define HK_HASH(hk) ((hk) >> 2)
#define HK_KIND(hk) ((int32_t)((hk) & 3u))
#define HK_EMPTY(hk) ((hk) == 0)

typedef struct {
    pslot    *items;
    uint32_t  n;               /* items 已用长度（含墓碑） */
    uint32_t  cap;             /* items 已分配长度 */
    uint32_t  filled;          /* 存活条目数 */
    uint32_t *index;
    uint32_t  nidx;            /* 2 的幂 */
    int64_t   nfnext;          /* next free int key */
    int32_t   packed;          /* 1 = 纯 list：键恰为 0..filled-1 */
} pamap;

/* ---------------- 注册表（id 1 基，可回收复用） ---------------- */
static pamap  **g_reg;
static int64_t  g_cap, g_used;
static int64_t *g_free;
static int64_t  g_nfree, g_freecap;

static int64_t reg_alloc(pamap *m) {
    if (g_nfree > 0) {
        int64_t id = g_free[--g_nfree];
        g_reg[id - 1] = m;
        return id;
    }
    if (g_used == g_cap) {
        int64_t cap = g_cap ? g_cap * 2 : 64;
        pamap **nr = (pamap **)realloc(g_reg, (size_t)cap * sizeof(pamap *));
        if (!nr) return 0;
        g_reg = nr;
        g_cap = cap;
    }
    g_reg[g_used++] = m;
    return g_used;
}

static void reg_release(int64_t id) {
    if (id <= 0 || id > g_used) return;
    g_reg[id - 1] = NULL;
    if (g_nfree == g_freecap) {
        int64_t cap = g_freecap ? g_freecap * 2 : 64;
        int64_t *nf = (int64_t *)realloc(g_free, (size_t)cap * sizeof(int64_t));
        if (!nf) return;
        g_free = nf;
        g_freecap = cap;
    }
    g_free[g_nfree++] = id;
}

static pamap *get_map(int64_t id) {
    if (id <= 0 || id > g_used) return NULL;
    return g_reg[id - 1];
}

/* ---------------- 哈希 ---------------- */
static inline uint64_t mix64(uint64_t x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33; x *= 0xc4ceb9fe1a85ec53ULL;
    x ^= x >> 33;
    return x;
}

static inline uint64_t hash_of(int32_t kind, int64_t key) {
    uint64_t h = mix64((uint64_t)key * 0x9E3779B97F4A7C15ULL + (uint64_t)kind);
    return h ? h : 1;
}

/* ---------------- index（开放寻址 / 线性探测） ---------------- */
static int index_build(pamap *m, uint32_t want) {
    uint32_t cap = 8;
    while (cap < want) cap <<= 1;
    uint32_t *ni = (uint32_t *)calloc((size_t)cap, sizeof(uint32_t));
    if (!ni) return -1;
    uint32_t mask = cap - 1;
    for (uint32_t i = 0; i < m->n; i++) {
        pslot *s = &m->items[i];
        if (HK_EMPTY(s->hk)) continue;
        uint32_t pos = (uint32_t)HK_HASH(s->hk) & mask;
        while (ni[pos] != 0) pos = (pos + 1) & mask;   /* 0 = 空 */
        ni[pos] = i + 1;                                /* 1 基：item 0 不等于空 */
    }
    free(m->index);
    m->index = ni;
    m->nidx = cap;
    return 0;
}

static inline uint32_t index_find(pamap *m, uint64_t h, int32_t kind, int64_t key) {
    if (m->nidx == 0) return 0;
    uint32_t mask = m->nidx - 1;
    uint64_t hk = HK(h, kind);
    uint32_t pos = (uint32_t)HK_HASH(hk) & mask;
    for (;;) {
        uint32_t v = m->index[pos];
        if (v == IDX_TOMB) { pos = (pos + 1) & mask; continue; }
        if (v == 0) return 0;
        pslot *s = &m->items[v - 1];
        if (s->hk == hk && s->key == key) return v;
        pos = (pos + 1) & mask;
    }
}

static inline void index_insert(pamap *m, uint32_t item, uint64_t h) {
    uint32_t mask = m->nidx - 1;
    uint32_t pos = (uint32_t)(h >> 2) & mask;
    while (m->index[pos] != 0 && m->index[pos] != IDX_TOMB) pos = (pos + 1) & mask;
    m->index[pos] = item + 1;
}

static inline void index_tomb(pamap *m, uint32_t item, uint64_t h) {
    uint32_t mask = m->nidx - 1;
    for (uint32_t pos = (uint32_t)(h >> 2) & mask;; pos = (pos + 1) & mask) {
        uint32_t v = m->index[pos];
        if (v == item + 1) { m->index[pos] = IDX_TOMB; return; }
        if (v == 0) return;
    }
}

/* ---------------- 生命周期 ---------------- */
int64_t pa_new(void) {
    pamap *m = (pamap *)calloc(1, sizeof(pamap));
    if (!m) return 0;
    m->cap = 8;
    m->items = (pslot *)malloc(8 * sizeof(pslot));
    m->index = (uint32_t *)calloc(8, sizeof(uint32_t));
    if (!m->items || !m->index) { free(m->items); free(m->index); free(m); return 0; }
    m->nidx = 8;
    m->packed = 1;
    return reg_alloc(m);
}

int64_t pa_free(int64_t id) {
    pamap *m = get_map(id);
    if (!m) return 0;
    free(m->items);
    free(m->index);
    free(m);
    reg_release(id);
    return 1;
}

int64_t pa_len(int64_t id) {
    pamap *m = get_map(id);
    return m ? (int64_t)m->filled : 0;
}

/* ---------------- 内部：压缩 / 扩容 ---------------- */
static int compact(pamap *m) {
    uint32_t w = 0;
    for (uint32_t i = 0; i < m->n; i++) {
        if (HK_EMPTY(m->items[i].hk)) continue;
        if (w != i) m->items[w] = m->items[i];
        w++;
    }
    m->n = w;
    return index_build(m, m->filled * 2 + 8);
}

static int grow_items(pamap *m) {
    uint32_t want = m->cap ? m->cap * 2 : 8;
    pslot *ni = (pslot *)realloc(m->items, (size_t)want * sizeof(pslot));
    if (!ni) return -1;
    m->items = ni;
    m->cap = want;
    return 0;
}

/* 返回旧 handle（NOVAL = 新键，ERR = 出错） */
static int64_t map_set(pamap *m, int32_t kind, int64_t key, int64_t val) {
    if ((m->filled + 2) * 2 > m->nidx) {
        if (index_build(m, (m->filled + 2) * 4) != 0) return ERR;
    }
    uint64_t h = hash_of(kind, key);
    uint32_t hit = index_find(m, h, kind, key);
    if (hit) {
        int64_t old = m->items[hit - 1].val;
        m->items[hit - 1].val = val;
        if (kind == K_INT && key == m->nfnext) m->nfnext = key + 1;
        return old;
    }
    /* 墓碑过多才压缩（amortized O(1)） */
    if (m->n - m->filled > 8 && m->n - m->filled > m->filled) {
        if (compact(m) != 0) return ERR;
    }
    if (m->n == m->cap) {
        if (grow_items(m) != 0) return ERR;
    }
    pslot *s = &m->items[m->n];
    s->key = key; s->val = val; s->hk = HK(h, kind);
    index_insert(m, m->n, h);
    m->n++;
    m->filled++;
    if (kind == K_INT) {
        if (key == m->nfnext) m->nfnext = key + 1;
        if (m->packed && key != (int64_t)(m->filled - 1)) m->packed = 0;
    } else {
        m->packed = 0;
    }
    return NOVAL;
}

int64_t pa_set_i(int64_t id, int64_t key, int64_t val) {
    pamap *m = get_map(id);
    return m ? map_set(m, K_INT, key, val) : ERR;
}

int64_t pa_set_s(int64_t id, int64_t sid, int64_t val) {
    pamap *m = get_map(id);
    return m ? map_set(m, K_STR, sid, val) : ERR;
}

/* ---------------- 读 ---------------- */
int64_t pa_get_i(int64_t id, int64_t key, int64_t def) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return def;
    if (m->packed && key >= 0 && key < (int64_t)m->filled) return m->items[key].val;
    uint32_t hit = index_find(m, hash_of(K_INT, key), K_INT, key);
    return hit ? m->items[hit - 1].val : def;
}

int64_t pa_get_s(int64_t id, int64_t sid, int64_t def) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return def;
    uint32_t hit = index_find(m, hash_of(K_STR, sid), K_STR, sid);
    return hit ? m->items[hit - 1].val : def;
}

/* 2 参变体：默认值 -1（"没有这个键"）烧进 C，省一次 Scheme→C 的实参打包。
 * 语义与 pa_get_i(id, key, -1) / pa_get_s(id, sid, -1) 完全相同。 */
int64_t pa_get_i2(int64_t id, int64_t key) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return NOVAL;
    if (m->packed && key >= 0 && key < (int64_t)m->filled) return m->items[key].val;
    uint32_t hit = index_find(m, hash_of(K_INT, key), K_INT, key);
    return hit ? m->items[hit - 1].val : NOVAL;
}

int64_t pa_get_s2(int64_t id, int64_t sid) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return NOVAL;
    uint32_t hit = index_find(m, hash_of(K_STR, sid), K_STR, sid);
    return hit ? m->items[hit - 1].val : NOVAL;
}

int64_t pa_has_i(int64_t id, int64_t key) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return 0;
    if (m->packed && key >= 0 && key < (int64_t)m->filled) return 1;
    return index_find(m, hash_of(K_INT, key), K_INT, key) ? 1 : 0;
}

int64_t pa_has_s(int64_t id, int64_t sid) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return 0;
    return index_find(m, hash_of(K_STR, sid), K_STR, sid) ? 1 : 0;
}

int64_t pa_del_i(int64_t id, int64_t key) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return NOVAL;
    uint64_t h = hash_of(K_INT, key);
    uint32_t hit = index_find(m, h, K_INT, key);
    if (!hit) return NOVAL;
    int64_t old = m->items[hit - 1].val;
    m->items[hit - 1].hk = 0;
    m->items[hit - 1].val = NOVAL;
    m->filled--;
    m->packed = 0;
    index_tomb(m, hit - 1, h);
    return old;
}

int64_t pa_del_s(int64_t id, int64_t sid) {
    pamap *m = get_map(id);
    if (!m || m->filled == 0) return NOVAL;
    uint64_t h = hash_of(K_STR, sid);
    uint32_t hit = index_find(m, h, K_STR, sid);
    if (!hit) return NOVAL;
    int64_t old = m->items[hit - 1].val;
    m->items[hit - 1].hk = 0;
    m->items[hit - 1].val = NOVAL;
    m->filled--;
    m->packed = 0;
    index_tomb(m, hit - 1, h);
    return old;
}

/* ---------------- 批量导出（迭代用，避免逐项 FFI 回调） ----------------
 * 每个条目写 3 个 int64：(kind, key, val)，按插入序。返回条目数。
 */
int64_t pa_export(int64_t id, int64_t *buf, int64_t cap) {
    pamap *m = get_map(id);
    if (!m || !buf) return 0;
    int64_t w = 0;
    for (uint32_t i = 0; i < m->n && w + 3 <= cap; i++) {
        pslot *s = &m->items[i];
        if (HK_EMPTY(s->hk)) continue;
        buf[w] = HK_KIND(s->hk);
        buf[w + 1] = s->key;
        buf[w + 2] = s->val;
        w += 3;
    }
    return w / 3;
}

/* 浅拷贝：slots 原样（handle 由 Scheme 侧镜像） */
int64_t pa_copy(int64_t id) {
    pamap *m = get_map(id);
    if (!m) return 0;
    pamap *c = (pamap *)calloc(1, sizeof(pamap));
    if (!c) return 0;
    c->n = m->n;
    c->cap = m->cap;
    c->filled = m->filled;
    c->nidx = m->nidx;
    c->nfnext = m->nfnext;
    c->packed = m->packed;
    c->items = (pslot *)malloc((size_t)(m->cap ? m->cap : 8) * sizeof(pslot));
    c->index = (uint32_t *)malloc((size_t)c->nidx * sizeof(uint32_t));
    if (!c->items || !c->index) { free(c->items); free(c->index); free(c); return 0; }
    if (m->n) memcpy(c->items, m->items, (size_t)m->n * sizeof(pslot));
    memcpy(c->index, m->index, (size_t)c->nidx * sizeof(uint32_t));
    return reg_alloc(c);
}

int64_t pa_clear(int64_t id) {
    pamap *m = get_map(id);
    if (!m) return 0;
    m->n = 0; m->filled = 0; m->nfnext = 0; m->packed = 1;
    memset(m->index, 0, (size_t)m->nidx * sizeof(uint32_t));
    return 1;
}

/* 观测入口：0=items 长度 1=存活 2=index 大小 3=墓碑 4=nfnext 5=packed 9=活跃 map 数 */
int64_t pa_stats(int64_t id, int64_t which) {
    if (which == 9) return g_used - g_nfree;
    pamap *m = get_map(id);
    if (!m) return 0;
    switch (which) {
        case 0: return (int64_t)m->n;
        case 1: return (int64_t)m->filled;
        case 2: return (int64_t)m->nidx;
        case 3: return (int64_t)(m->n - m->filled);
        case 4: return m->nfnext;
        case 5: return m->packed;
        default: return 0;
    }
}

/* ---------------- 稳定归并排序（list.sort / sorted 用） ----------------
 * 按 keys[i]（double）升序排列 vals[i]；keys 相同保持原序（Python sort 稳定）。
 * 供 Scheme 侧把数值键抽成双精度数组后一次性排完，避免 N 次 Scheme 回调。
 */
/* 纯数值数组的原地稳定排序（list.sort() 的快路径：元素就是数字） */
int64_t pa_sort_doubles(int64_t *keys_buf, int64_t n) {
    if (!keys_buf || n < 2) return 0;
    double *keys = (double *)keys_buf;
    double *tk = (double *)malloc((size_t)n * sizeof(double));
    if (!tk) return 0;
    for (int64_t w = 1; w < n; w <<= 1)
        for (int64_t lo = 0; lo < n; lo += w << 1) {
            int64_t mid = lo + w, hi = lo + (w << 1);
            if (mid > n) mid = n;
            if (hi > n) hi = n;
            if (mid < hi) {
                int64_t i = lo, j = mid, w2 = lo;
                while (i < mid && j < hi) {
                    if (keys[j] < keys[i]) tk[w2++] = keys[j++];
                    else                   tk[w2++] = keys[i++];
                }
                while (i < mid) tk[w2++] = keys[i++];
                while (j < hi)  tk[w2++] = keys[j++];
                for (int64_t k = lo; k < hi; k++) keys[k] = tk[k];
            }
        }
    free(tk);
    return n;
}

/* 版本号，便于运行时自检 .so 是否与 .scm 匹配 */
int64_t pa_abi_version(void) { return 20261120; }   /* +pa_get_i2 / pa_get_s2 */
