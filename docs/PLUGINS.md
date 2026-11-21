# PLUGINS —— 插件规范（一切能力都是插件）

> 内核很小：`kernel/` 只负责**发现插件 → 解依赖 → 拼装产物 → 调 Chez**。
> **语法增强 / 运行时能力 / C 库封装全部是插件**。写插件不需要改内核。

```
app.static.py ──┐
                ├─ kernel（插件选择 / 拓扑排序）─► bundle.ss ─► Chez AOT ─► ELF
plugins/*/  ────┘        （runtime.scm + ffi.scm + hooks.py + libs）
```

## 1. 目录结构

```
plugins/<name>/
  plugin.json       # 必须：清单
  runtime.scm       # 可选：拼进产物的 Scheme 运行时（define …）
  ffi.scm           # 可选：load-shared-object / 常量 / 手写绑定
  hooks.py          # 可选：Python 语法扩展（ast 钩子）
  *.so / build 脚本  # 可选：插件自带的 C 库
```

搜索顺序：`$STATICPY_PLUGINS_PATH`（`:` 分隔，可多个）→ 仓库 `plugins/` → `~/.staticpy/plugins`。
**同名插件先到先得**，用户目录可覆盖内置插件。

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
| `nested_modules` | {"a.b": {…}} | 嵌套模块，如 `os.path` |
| `return_types` | {函数名: 类型} | 供翻译器类型推断（`ptr`/`str`/`int`/`float`/`dict`/…） |
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
STATICPY_PLUGINS_PATH=$PWD/myplug staticpy run app.static.py -p core,hello
# -> hello plugin
```

> `runtime.scm` 里的 `define` 名字要与 Python 侧一致（下划线保留），且必须列进
> `prelude_functions`，否则翻译器会加 `static_` 前缀把它当用户函数。

## 3. 三种形态

### ① 纯运行时（`runtime.scm`）

在 Scheme 侧实现能力：`print`、字符串工具、CSV、正则、HTTP…，**无需 FFI**。
函数名列进 `prelude_functions`，翻译器就不会把它当外部符号。

### ② C 库封装（`ffi` + `libs` + `modules`）

```json
"libs": {"json": "libjansson.so.4"},
"modules": {"json": {"loads": "parse_json", "dumps": "json_dumps"}},
"return_types": {"parse_json": "dict", "json_dumps": "str"},
"prelude_functions": ["parse_json", "json_dumps"]
```

`.py` 侧写法不变：`import json` + `json.loads(s)`。
`load-shared-object` 由内核按 `libs` 自动生成（见 §3.5），不用手写。

### ③ 自有 `.so` + `extern fn`（如 `imgproc`）

```python
extern fn img_open(path: str) -> ptr from "imgproc"
```

翻译器依据 `extern fn … from "<lib>"` 生成 `foreign-procedure`，并依据 `libs` 自动生成
`load-shared-object`。手写绑定 / 常量表 / 结构体布局放插件自己的 `ffi.scm`。

> **FFI 硬约定**：类型只有 `str / int / float / ptr`，**没有 `void` 返回**——C 侧返回 void 的
> 函数请改成返回 `int`；多值参数（点列/调色板/LUT）用 CSV 字符串传。详见 [LANGUAGE.md](./LANGUAGE.md) §3。

### ④ 语法扩展（`hooks.py`）

核心语法已冻结，**新语法一律走插件**。模板见 `examples/syntax_plugin/`。

```python
def register(k):
    k.rewrite(lambda src: src)             # 源码级预处理
    k.expr(ast.Call, lambda node: None)    # 返回 None = 交回内核
    k.stmt(ast.Match, my_match)            # 自定义语句（含顶层语句）
    k.infer(my_infer)                      # 类型推断钩子
```

| 钩子 | 时机 | 返回 |
|---|---|---|
| `k.rewrite(fn)` | `ast.parse` 之前，`fn(code) -> code` | 新源码（**别改行数**，行号=报错定位） |
| `k.expr(NodeType, fn)` | `translate_expr` 开头，优先于内核规则 | Scheme 字符串；`None` = 交回内核 |
| `k.stmt(NodeType, fn)` | `translate_stmt` 与**顶层语句** | 同上 |
| `k.infer(fn)` | `infer_expr_type` 开头 | 类型名 `"int"/"float"/…`；`None` = 交回内核 |

回调签名 `fn(node, kernel)`；递归翻译子节点用 `kernel.api["translate_expr"]`，
**不要** `import static_translate`（循环 import）。

**铁律**：不认识的形状**必须 `return None`**——`dispatch_*` 按注册顺序遍历、命中即返回，
抢了别人的节点会静默改语义。插件只在插件链路生效；自举环 2（`selfhost/staticc.py`）不带插件。

```bash
# 模板自检（selfcheck.sh 的 [0b/4] 会跑这条）
# 插件只在内核链路生效（自举 ELF 翻译器不带插件）
STATICPY_PLUGINS_PATH=$PWD/examples staticpy check \
  examples/syntax_plugin/demo.static.py -p syntax_plugin
```

**真实案例：`plugins/clsx/`（class 特性补齐）**

内核的 class 子集是**原生单继承记录**：子类 `(parent A)` 共享祖先槽位，`static_A_m`
在子类实例上照常可用（见 [LANGUAGE.md](./LANGUAGE.md)「class」）。`clsx` 用 `k.rewrite`
纯源码补三件事，**一个 pass 一件事**：

| 写法 | 降级成 | 为什么 |
|---|---|---|
| `class C(A, B):` | `class C(A)` + 把 `B` 链的方法/类属性内联进 C 类体（就近覆盖：C 自己 > A 链 > B 链） | 记录只有一条父槽位链，第二个基类没有槽位可挂 → 只能当 mixin 搬方法 |
| `super().__init__(args)` | 基类 `__init__` 的赋值就地展开（形参→实参，递归） | 多基内联后可能已没有基类；也让「类属性默认值」对子类生效 |
| `kind: int = 7` / `tag = "hi"` | `kind: int` + `__init__` 里注入 `self.kind = 7` | 内核只认「类体声明字段」，不认默认值 |

pass 顺序 `mixin → defaults → super`：先内联（多基收敛成单基），再合成默认值的
`__init__`，最后展开 `super()`——这样 `super().__init__()` 一定能读到刚合成的基类 `__init__`。
非主基类定义了 `__init__` 会响亮报错（记录不能有两条父槽位链）。

三条工程约束（写进代码注释，也是所有 rewrite 类插件的通用经验）：

1. **每个 pass 都重新 `ast.parse` 当前文本**——行号只在单个 pass 内有效，
   跨 pass 复用行号会让「插入行」把后续编辑挤歪。
2. **幂等**：改写结果再喂一遍必须完全不变（`check.sh` 有这条断言）。
3. **不认识就响亮失败**：内联方法引用了未声明字段、残留 `super().<name>()` 都直接
   `SyntaxError`，不静默生成错代码。

```bash
bash plugins/clsx/check.sh     # 5 个用例 AOT 双跑（core vs core,clsx）：defaults/inherit/multi/over/methodval
```

### ⑤ FFI 翻译分工（谁翻译什么）

| 环节 | 归属 | 位置 |
|---|---|---|
| `extern fn name(a: int, b: str) -> ptr from "lib"` 解析 | **内核** | `static_translate.py: parse_extern_functions` |
| 类型 `int/float/str/ptr` → C 类型（无 `void` 返回） | **内核** | `translate_type` / `TYPE_MAP` |
| `(define name (foreign-procedure …))` 生成 | **内核** | `generate_extern_ffi` |
| 逻辑库名 → soname（`STATICPY_LIB_<LIB>` 可覆盖） | **插件声明 + 内核消费** | `plugin.json: libs` |
| `(load-shared-object …)` 自动挂载（全局去重） | **内核** | `kernel/bundle.py: assemble` |
| 手写绑定 / 常量表 / 结构体布局 | **插件** | `plugins/<name>/ffi.scm` |

## 4. 命令行

```bash
staticpy plugins                              # 列出插件（含依赖关系）
staticpy check app.static.py                  # 只翻译成 Scheme（调试）
staticpy build app.static.py -o out           # 出 ELF
staticpy run   app.static.py -- arg1 arg2     # 构建并运行（-- 之后是程序参数）
staticpy build app.static.py -p core,libc,json  # 显式插件集
staticpy build app.static.py --no-auto          # 不按 import 推断
staticpy build app.static.py --build-libs       # 顺带跑插件的 C 构建
staticpy build app.static.py --emit-ss out.ss   # 保留拼装产物
```

插件选择优先级：`-p/--plugin` > `STATICPY_PLUGINS` > 按源码 `import` 自动推断 > `core`。

## 5. 现有插件

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
| `openblas` → `lapack` → `np` | 链式 | 数组 / LAPACK / numpy 风格 API |
| `cuda` | core | CUDA 相关运行时 |
| `torch` | core, np, cuda | libTorch |
| `xgboost` / `lightgbm` / `onnx` | core, np | 树模型 / ONNX Runtime |
| `imgproc` | core, libc | Pillow 对标（C++ `.so` + extern fn） |
| `clsx` | core | 语法：多继承 / `super().__init__` / 类属性默认值（`k.rewrite`） |

## 6. 兼容性

老的 `staticpy/static_build_comfycli.sh <src> <out> [ffi.scm]` 仍然可用：
它等价于「一次性拼上 **legacy 全集**」的内置插件集，行为与拆分前一致
（已用 `imgproc/difftest.py` 100/100 回归）。

## 7. 给插件作者的检查单

- [ ] `plugin.json` 有 `name` / `runtime`，`kernel plugins` 能看到
- [ ] 函数名列进 `prelude_functions`（Scheme 侧已实现）
- [ ] FFI 只返回 `str|int|float|ptr`
- [ ] `libs` 里的 soname 在目标机存在（`ldconfig -p | grep`）
- [ ] 临时文件写 `~/iso_gen/`（不用 `/tmp`），不引 pip 依赖
- [ ] 自带一个最小 `.static.py` 示例 + 一条 `kernel run` 命令
