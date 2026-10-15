# hashlib —— StaticPy 版消息摘要（第 2 个迁移样板）

沿用 [`../AGENTS.md`](../AGENTS.md) 的三步闭环：**自省 → 铺桩 → 差分对齐**。

- **C 核心**：`../cpp/hashlib/` → `libhashlib.so`（走 OpenSSL EVP，运行时挂 `libcrypto.so.3`）
- **FFI**：`hashlib_ffi.scm`（`load-shared-object`）
- **前端**：`hash.static.py` → `hash` ELF（`hash [ALGO] FILE`，默认 sha256）

```bash
bash hashlib/build.sh
LD_LIBRARY_PATH=cpp/hashlib/build ./hashlib/hash sha256 IN.png
python3 hashlib/difftest.py            # Python hashlib vs 我们（逐字节）
```

## 覆盖

| 项 | 状态 |
|---|---|
| `md5` `sha1` `sha224` `sha256` `sha384` `sha512` | ✅ 逐字节一致（差分 6/6） |
| `sha3_256/512` `blake2b/s` | 算法名可用（OpenSSL 提供），未逐一封装前端 |
| `file_digest` | ≈ `hl_file_hex` |
| `pbkdf2_hmac` / `scrypt` | 待做 |

> 与 imgproc 同一套路：C ABI 是稳定面，StaticPy/Python/LuaJIT 共用。
