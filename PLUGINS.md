# PLUGINS.md — StaticPy 插件规范

> 内核很小：`kernel/` 只负责**发现插件 → 解析依赖 → 拼装产物 → 调 Chez**。
> **一切语法增强 / 运行时能力 / C 库封装都是插件**。写插件不需要改内核。

```
app.static.py ──┐
                ├─ kernel（插件选择/拓扑排序）─► bundle.ss ─► Chez AOT ─► ELF
plugins/*/  ────┘        （runtime.scm + ffi.scm + hooks.py + libs）
```

---

## 1. 目录结构

```
plugins/<name>/
  plugin.json      # 必须：清单
  runtime.scm      # 可选：拼进产物的 Scheme 运行时（define …）
  ffi.scm          # 可选：load-shared-object / 常量定义
  hooks.py         # 可选：Python 语法扩展（ast 钩子）
  *.so / build 脚本 # 可选：插件自带的 C 库
```

`kernel` 按顺序搜索：`$STATICPY_PLUGINS_PATH`（`: `分隔，可多个）→ 仓库 `plugins/`
→ `~/.staticpy/plugins`。**同名插件先到先得**，所以用户目录可以覆盖内置插件。

## 2. plugin.json 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | str | **必填**，唯一 |
| `version` | str | 语义化版本 |
| `kind` | str | `runtime` / `syntax` / `ffi` / `mixed`，仅描述用途 |
| `description` | str | 一行说明（`kernel plugins` 里显示） |
| `requires` | [str] | 依赖插件名，自动补齐并拓扑排序 |
| `order` | int | 运行时片段拼接顺序，小的在前（core=10，库类=50–200） |
| `runtime` | [str] | 拼进产物的 `.scm`，按序拼接（可 glob） |
| `ffi` | [str] | FFI `.scm`，拼在 runtime 之前 |
| `syntax` | str | 语法扩展文件（`hooks.py`） |
| `libs` | {逻辑名: soname} | 例如 `{"imgproc": "libimgproc.so"}` |
| `modules` | {模块: {属性: 函数名}} | `import x` 后 `x.f()` → Scheme 函数名 |
| `nested_modules` | {"a.b": {...}} | 嵌套模块，如 `os.path` |
| `return_types` | {函数名: 类型} | 供 translator 类型推断（`ptr`/`str`/`int`/`float`/`dict`/…） |
| `prelude_functions` | [str] | **已在 Scheme 侧实现**的函数名，避免被当 FFI 重复声明 |
| `build` | {cmd, outputs} | `kernel build --build-libs` 时执行的构建命令 |
| `env` | {LD_LIBRARY_PATH: 相对路径} | 运行期提示（`kernel run` 自动设置） |

### 最小插件（10 行）

```json
{
  "name": "hello",
  "version": "1.0.0",
  "kind": "runtime",
  "order": 100,
  "requires": ["core"],
  "runtime": ["runtime.scm"],
  "prelude_functions": ["hello-world"]
}
```

```scheme
;; runtime.scm
(define (hello-world name) (string-append "hello " name))
```

```python
# app.static.py
def main() -> int:
    print(hello_world("plugin"))
    return 0
```

```bash
STATICPY_PLUGINS_PATH=/tmp/myplug python3 -m kernel run app.static.py -p core,hello
# -> hello plugin
```

> 注意：`runtime.scm` 里的 `define` 名字要与 Python 侧一致（下划线保留），
> 且必须列进 `prelude_functions`，否则 translator 会给调用加 `static_` 前缀当成用户函数。

## 3. 三种插件形态

### ① 纯运行时（runtime.scm）
在 Scheme 侧实现能力：`print`、字符串工具、HTTP、CSV、正则…。**无需 FFI**。
写好后把函数名列进 `prelude_functions`，translator 就不会把它当外部符号。

### ② C 库封装（ffi + libs + modules）
```json
"libs": {"json": "libjansson.so.4"},
"modules": {"json": {"loads": "parse_json", "dumps": "json_dumps"}},
"return_types": {"parse_json": "dict", "json_dumps": "str"},
"prelude_functions": ["parse_json", "json_dumps"]
```
`.py` 侧写法不变：`import json` + `json.loads(s)`。
`load-shared-object` 写在插件的 `ffi.scm` 里。

### ③ 自有 `.so` + extern fn（如 `imgproc`）
插件的 `plugin.json` 声明 `ffi` / `libs` / `build`；用户 `.py` 里：
```python
extern fn img_open(path: str) -> ptr from "imgproc"
```
translator 依据 `extern fn ... from "<lib>"` 生成 `foreign-procedure`，
插件只负责在运行时把 `.so` 载入：

```scheme
;; imgproc/imgproc_ffi.scm（由 plugins/imgproc/plugin.json 的 "ffi" 引入）
(load-shared-object "libimgproc.so")
```

> **FFI 约定（重要）**：类型只有 `str / int / float / ptr`，**没有 `void` 返回**——
> C 侧返回 void 的函数请改成返回 `int`。多值参数（点列/调色板/LUT）用 CSV 字符串传。

### ④ 语法扩展（hooks.py）
```python
def register(k):
    k.expr(ast.Call, lambda node: None)   # 返回 None = 交回内核
    k.stmt(ast.Match, my_match)           # 自定义语句
    k.rewrite(lambda src: src)            # 源码级预处理
```

## 4. 命令行

```bash
python3 -m kernel plugins                 # 列出插件（含依赖关系）
python3 -m kernel check app.static.py     # 只翻译成 Scheme（调试）
python3 -m kernel build app.static.py -o out
python3 -m kernel run   app.static.py -- arg1 arg2   # -- 之后是程序参数
python3 -m kernel run   app.static.py arg1 arg2      # 省略 -- 也可以
python3 -m kernel build app.static.py -p core,libc,json    # 显式插件集
python3 -m kernel build app.static.py --no-auto            # 不按 import 推断
python3 -m kernel build app.static.py --build-libs         # 顺带跑插件的 C 构建
python3 -m kernel build app.static.py --emit-ss out.ss     # 保留拼装产物
```

插件选择优先级：`-p/--plugin` > `STATICPY_PLUGINS` 环境变量 > 按源码 `import` 自动推断 > `core`。

## 5. 现有插件一览

| 插件 | 依赖 | 能力 |
|---|---|---|
| `core` | — | dict / array / py-list / 字符串 / print / Option-Result |
| `libc` | core | 文件 I/O、时间、argv、环境变量 |
| `math` | core | libm 函数与常量（`math.pi`…） |
| `json` | core | jansson |
| `csv` | core | 纯 Scheme CSV |
| `regex` | core | libpcre2 |
| `http` | core, libc | libcurl |
| `random` | core, libc | 随机数 |
| `ir` | core | 自举编译器 IR 标签谓词 |
| `openblas` → `lapack` → `np` | 链式 | 数组/LAPACK/numpy 风格 API |
| `torch` | core, np, cuda | libTorch |
| `xgboost` / `lightgbm` / `onnx` | core, np | 树模型 / ONNX Runtime |
| `imgproc` | core, libc | Pillow 对标（C++ `.so` + extern fn） |

## 6. 兼容性

老的 `staticpy/static_build_comfycli.sh <src> <out> [ffi.scm]` 仍然可用：
它等价于「一次性拼上 **legacy 全集**」的内置插件集，行为与拆分前一致
（已用 `imgproc/difftest.py` 100/100 回归）。

## 7. 给插件作者的检查单

- [ ] `plugin.json` 有 `name` / `runtime`，`kernel plugins` 能看到
- [ ] 函数名进了 `prelude_functions`（Scheme 侧已实现）
- [ ] FFI 只返回 `str|int|float|ptr`
- [ ] `libs` 里的 soname 在目标机存在（`ldconfig -p | grep`）
- [ ] 临时文件写 `~/iso_gen/`（不要 `/tmp`），不引 pip 依赖
- [ ] 自带一个最小 `.static.py` 示例 + 一条 `kernel run` 命令
