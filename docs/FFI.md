# FFI 契约（`extern fn` ↔ C ABI）

> 这份文档是**约定**，`tools/check_ffi.py` 是它的**机器校验**。
> 判据不是"人记得住"，而是 `python3 tools/check_ffi.py` 退出码 0。
> 相关：AGENTS §4（工程约定）、[LANGUAGE.md](./LANGUAGE.md)（子集/类型）、[PLUGINS.md](./PLUGINS.md)（运行时挂 `.so`）。

## 1. 一条声明的全貌

```python
extern fn sqlite3_libversion() -> str from "sqlite3"

def main():
    print(sqlite3_libversion())
```

翻译器把它变成（`emit_extern_ffi`）：

```scheme
(load-shared-object "libsqlite3.so")          ; 每个逻辑库名只 load 一次
(define sqlite3_libversion
  (foreign-procedure "sqlite3_libversion" () string))
```

- **符号名 = 声明名**。想在 C 里用别的符号名，就在 C 侧包一层同名函数。
- 声明必须写在**文件顶部区域**（第一个 `def`/`class` 之前），放进函数体不是 FFI 声明。
- 声明是**编译期**信息：不产生运行期开销，也不做参数个数/类型的运行期检查。

## 2. 类型白名单（只有这 7 种 + `list[...]`）

| StaticPy | Chez | C | 语义 |
|---|---|---|---|
| `int` | `int` | `long` / `int` | 整数，直接传值 |
| `float` | `float` | `float` | **单**精度；要双精度写 `double` |
| `double` | `double` | `double` | 双精度 |
| `bool` | `boolean` | `int` | 0 / 非 0 |
| `str` | `string` | `char *` | 见 §4 所有权 |
| `ptr` | `void*` | `void *` | 任意指针；见 §5 生命周期 |
| `list[...]` | `void*` | `T *` | **一律当指针**，不做元素类型检查；多值传参见 §3 |

**没有 `void` 返回**：返回 void 的 C 函数一律在 C 侧改成返回 `int`（成功 0 / 失败负）。
理由：StaticPy 的表达式必须有序，返回 void 会让 `x = f()` 出现"没有值"的状态；
包一层 `int` 是零成本的，也让错误码有了地方放。

**参数表为空合法**：`extern fn now() -> int from "c"`。

**未知类型不报错但也不可信**：`ffi_type()` 把任何未登记类型（含 `list[...]`）降级成 `void*`，
所以 `x: bytecode` 这种写法能编译、能跑，然后在你最不想看到的地方崩。`check_ffi.py` 的 R2 就是拦它。

## 3. 多值参数：CSV 字符串，不要裸指针

点列、LUT、调色板、坐标数组这类"一长串数"，**不要**在 Python 侧拼指针：

```python
extern fn img_polygon(img: ptr, pts: str) -> int from "imgproc"   # "x1,y1,x2,y2,..."
```

```python
img_polygon(obj, "10,10,100,10,50,80")
```

理由：`list[float]` 到 C 数组要跨模块分配/释放一趟，所有权立刻变成双向约定；
CSV 在 C 侧 `strtok`/自写扫描一次就够，字符串的所有权天然在调用方（§4）。
这是 imgproc 全库的既有做法（`docs/LIBS.md`），也是"FFI 只有 7 种类型"的直接推论。

## 4. `str`：所有权在调用方，方向决定谁释放

| 方向 | 谁分配 | 谁释放 | 约定 |
|---|---|---|---|
| Python → C | 运行时（`string`） | **没人**（Chez 的 string 由 GC 管，C 只读） | C **不得**保存该指针、不得改写、不得 free |
| C → Python | C (`malloc`) | **C 侧再导出一个 `*_free`** | 拿到就立刻 `str` 复制或直接交付；不要 free Chez 的 string |

```python
extern fn cfg_dump() -> str from "cfg"
extern fn cfg_free(s: str) -> int from "cfg"      # 必须成对提供
```

`str` 返回**不保证是 NUL 结尾之外的东西**：静态数据、线程局部缓冲、malloc 都可能；
**不要假设可写**，也不要跨线程传。

## 5. `ptr`：来源与生命周期四问

拿到 / 交出 `ptr` 之前，先答四句（答不上就是泄漏或 use-after-free）：

1. **谁分配**？（构造函数名）
2. **谁释放**？（销毁函数名；两者必须都导出，且要求成对调用）
3. **有效期到哪**？调用之间还活着吗？被别的调用移动/重分配过吗？
4. **失败怎么表达**？`ptr` 返回 `0`/空指针表示失败；**不要**指望 errno 自己往上传。

```python
extern fn buf_new(n: int) -> ptr from "x"
extern fn buf_free(p: ptr) -> int from "x"
extern fn buf_len(p: ptr) -> int from "x"
```

规则：
- 运行期不追踪 `ptr`：不计数、不自动释放、不做悬垂检查；
- 不要用 `ptr` 传"临时栈地址"给会保存它的 C 函数；
- `ptr` 与 `str` **不可混用**：`str` 是 Chez 对象，取地址要显式拿 `object->reference-address`
  （`emit_lib` 内部工具才有），用户代码请让 C 侧接受 `str` 或 `ptr`。

## 6. 异常 / 错误：**不跨边界**

C 侧绝不 `longjmp` / 抛 C++ 异常穿过 `foreign-procedure`（Chez 的栈/寄存器状态会坏掉）。
一律：**返回错误码 `int`**，必要时加一个 `*_last_error() -> str` 取值接口。
Python 侧检查返回值，自己 `raise`/`sys.exit` —— 错误语义留在 StaticPy 侧。

## 7. 逻辑库名 → soname（**两条链不一样，注意**）

`from "lib"` 里的 `lib` 是**逻辑名**（小写字母/数字/下划线），解析顺序：

| 链路 | 顺序 |
|---|---|
| 种子（CPython `static_translate.py`） | `STATICPY_LIB_<LIB>` 环境变量 → 插件 `plugin.json` 的 `libs` 映射 → `lib<lib>.so` |
| 自举翻译器 ELF（`emit_lib`） | `STATICPY_LIB_<LIB>` 环境变量 → `lib<lib>.so`（**插件清单不进 emit**） |

所以：插件里登记了 `libs` 的库，走种子链路能直接命中；
**走自举 ELF（含 `static_build.sh` 的产物）时必须自己设 `STATICPY_LIB_<LIB>=<soname>`**，
否则默认拼出来的 `lib<lib>.so` 大概率不存在，`dlopen` 失败会**晚到运行时**、报错也难读。

```bash
# 版本化 soname（libcublas.so.12 之类）必须显式给
STATICPY_LIB_CUBLAS=libcublas.so.12 bash staticpy/static_build.sh app.static.py app
```

`check_ffi.py` 的 R3 就检查这一条：既没有插件映射、也没设环境变量时给 **warn**（不判红，
因为第三方 `.so` 本来就该由使用方用环境变量指路）。

## 8. 校验器：`tools/check_ffi.py`

```bash
python3 tools/check_ffi.py                  # 扫全仓 *.static.py
python3 tools/check_ffi.py a.static.py      # 只查文件
python3 tools/check_ffi.py --warn           # 告警也算失败（严格模式）
```

六条规则：

| 规则 | 拦什么 |
|---|---|
| R1 | 返回类型为空 / `void` / `None` / 不在白名单 |
| R2 | 参数类型不在白名单（会被静默降级成 `void*`） |
| R3 | 逻辑库名不合规，或无插件映射且无 `STATICPY_LIB_<LIB>`（warn） |
| R4 | 声明落在第一个 `def`/`class` 之后（不是 FFI 声明区） |
| R5 | 同文件同名 `extern` 重复（后一条覆盖前一条 ABI） |
| R6 | extern 名撞运行时预置名（两条 ABI 抢同一个符号，如 `sqrt`） |

`selfcheck.sh` 的 `[0g/4]` 段会跑它。当前：**73 个文件 × 124 条声明**，错误 0，
告警 40（都是第三方 `.so` 需要 `STATICPY_LIB_<LIB>` 的那些库 —— 这是设计上的常态）。

## 9. 反模式

- ❌ `extern fn f() -> void`（返回 void）→ ✅ C 侧返回 `int`
- ❌ `x: bytecode`、`x: tensor` 这类"随便写个类型" → ✅ 只用白名单，未知就是 `void*`，把风险显式化
- ❌ `list[float]` 当可变数组来回传 → ✅ CSV 字符串，所有权单向
- ❌ C 侧保存 `str` 指针下次用 → ✅ 立刻复制，或让 C 侧自己 `malloc` + `*_free`
- ❌ `ptr` 没有配对的 `*_free` → ✅ 构造/销毁成对导出，并在注释里写明调用点
- ❌ C 里 `longjmp`/抛异常穿过边界 → ✅ 返回错误码
- ❌ 把 `extern fn` 写在函数体里 → ✅ 文件顶部
