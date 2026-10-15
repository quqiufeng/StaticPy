# zlib —— StaticPy 版压缩（第 3 个迁移样板）

按 [`../AGENTS.md`](../AGENTS.md) 三步闭环：**自省 → 铺桩 → 差分对齐**。

- **C 核心**：`../cpp/zlib/` → `libzlib.so`（走系统 `libz.so.1`，运行时挂载）
- **FFI**：`zlib_ffi.scm`
- **前端**：`zc.static.py` → `zc` ELF
- **验证**：`difftest.py`，与 Python `zlib`/`gzip` **逐字节一致**

```bash
bash zlib/build.sh
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc compress IN OUT [level]
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc decompress IN OUT
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc crc32 FILE
python3 zlib/difftest.py            # Python zlib/gzip vs 我们（逐字节）
```

## 覆盖

| 项 | 状态 |
|---|---|
| `zlib.compress/decompress`（zlib 格式） | ✅ 逐字节一致 |
| `gzip`（gzip 格式） | ✅ 逐字节一致（`mtime=0`） |
| `crc32` / `adler32` | ✅ 一致 |
| `compressobj` 流式 / `wbits` 变体 | 待做 |

> 关键：**与 Python 用同一份 `libz`** → 压缩字节天然可逐字节比对（`0` 容差）。
