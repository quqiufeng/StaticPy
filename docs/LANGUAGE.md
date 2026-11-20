# LANGUAGE —— Python 子集、类型与 FFI 约定

> StaticPy 是一门**小的** Python 子集：够写算法、够贴着 C 库编程，但**不做**动态运行时能做的一切。
> 语法不够用时，正确做法是**改翻译器对齐 Scheme IR**，或者**写语法插件**——而不是把 Python 塞进来。

## 1. 支持的语法

```python
# 变量与类型标注
x: int = 10
y: float = 3.14
name: str = "hello"
ok: bool = True

# 函数（用户函数在 Scheme 侧加 static_ 前缀）
def add(a: int, b: int) -> int:
    return a + b

# 控制流
def classify(x: int) -> str:
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    return "zero"

# 循环（支持 break / continue，见 §4 补丁 2）
def total(arr: list[float]) -> float:
    s: float = 0.0
    i: int = 0
    while i < list_length(arr):
        s = s + float_array_ref(arr, i)
        i = i + 1
    return s

for i in range(10):
    if i == 3:
        continue

# lambda / 一等函数（补丁 7）：函数值可赋值、可传参、可回调
def apply_all(img: ptr, f: fn) -> ptr:
    return img_point(img, f)

# 外部 C 函数声明
extern fn img_open(path: str) -> ptr from "imgproc"
```

**有限支持**：推导式（list / dict / set / 生成器；多 `for`、`if` 过滤、元组解包、
迭代 `range` / `list` / `str` / py-list / tagged array）、`match`/`case`（字面量、通配、
捕获、`|`、序列 `[a, *rest]`、映射 `{"k": v}`、类模式 `Pt(x=0)`/`Pt(1, y)`）、
元组解构 `x, y = 1, 2`、切片 `a[1:3]`、`dataclass`（编译成 record）、`enum`（编译成常量）。

**不支持**（也不要绕）：`class`/继承/多态、`try`/`except`/`raise`、生成器/`yield`、
自由变量闭包、`eval`/`exec`、动态 `getattr`/`setattr`。

> 能力缺口按三条路径补：挂 C 库 / 写 C++ helper / 改编译器或加语法插件（见 [PLUGINS.md](./PLUGINS.md)）。

## 2. 类型系统

| StaticPy 类型 | 内部表示 |
|---|---|
| `int` | 64 位整数（Chez fixnum） |
| `float` | **32 位 float**（对齐 C ABI；见补丁 5） |
| `double` | 64 位浮点（需要时显式写 `double`） |
| `bool` | boolean |
| `str` | Scheme string |
| `list[T]` | 运行时长度数组（T 为 `float`/`int`） |
| `array[T, N]` | 编译期定长数组 |
| `dict` | hashtable |
| `ptr` | `void*` |
| `record` / `enum` | `define-record-type` / 顶层常量 |

规则：
- 建议**所有**变量/参数/返回值都标注类型；未标注推断为 `Any`，`Any` 可赋给任何类型。
- `int` → `float` 隐式放宽；`/` 结果按浮点处理。
- 默认 **strict**：类型错误直接失败；`--warn`（kernel）或 `STATICPY_WARN=1` 降级为警告。

## 3. FFI 约定（硬约束）

1. **类型只有 4 个**：`str / int / float / ptr`。
2. **没有 `void` 返回**——返回 void 的 C 函数在 helper 里改成返回 `int`。
3. **多值参数走 CSV 字符串**：点列、调色板、LUT、坐标数组都用 `"x,y,x,y,…"` 传，C 侧解析。
4. `float` 就是 **32 位**：若 C 侧是 `double`，写 `double` 声明，别赌。
5. 声明写在 `.py` 顶部：`extern fn name(args) -> ret from "<逻辑库名>"`；
   `(define name (foreign-procedure …))` 由翻译器生成。
6. `load-shared-object`：**插件按 `libs` 自动生成**（全局去重），不用手写；
   手写绑定/常量表/结构体布局放插件的 `ffi.scm`。
7. 逻辑库名 → soname 由插件的 `libs` 映射决定，`STATICPY_LIB_<LIB>` 可覆盖。

## 4. 编译器本地补丁（`staticpy/static_translate.py`）

`static_translate.py` = 上游 StaticPy + 下列本地补丁。升级上游时：
`static_prelude.scm` / `static_stdlib.scm` 可直接替换；`static_translate.py` 覆盖后**必须重放**下列补丁。

| # | 补丁 | 原因 |
|---|---|---|
| 1 | `is None` / `is not None` → `(eq? x #f)` | 上游未处理，会生成非法 `(None x y)` |
| 2 | `break` / `continue`（`call/cc` 实现） | 上游 while/for 只有 `(let loop …)`，无法提前退出 |
| 3 | 模块级变量进 `module_env` | 上游只收 enum 常量，函数内引用模块变量被判 `undefined name` |
| 4 | 顶层 `AnnAssign`/`Assign`/`Expr` 语句翻译 | 上游丢弃顶层语句，bundle 头部会失效 |
| 5 | `float` → 32 位 `float`（非 double） | C ABI 是 32 位 float 时用 double 会传垃圾值 |
| 6 | 类型收集递归进 `while`/`if`/`for`/`with` 体 | 上游只扫函数直层，控制流内标注丢失 |
| 7 | **lambda + 一等函数** | 语法不够兼容 Python：`lambda` → `(lambda (args) body)`；函数值记为 `fn`、参数名进 `CURRENT_PARAMS`，**调用不加 `static_` 前缀** |
| 8 | `generate_extern_ffi` 去硬编码路径 | 原表写死绝对路径；改为 soname + `STATICPY_LIB_<LIB>`，未知库默认 `lib<lib>.so` |

补丁 7 新增的全局：`CURRENT_PARAMS`（当前作用域参数名集合，调用时不加前缀）、
`TYPE_ENV[name] = "fn"`（函数值局部变量）。它是 `Image.eval` / `ImageOps.deform` 这类**回调**的前提。

校验：

```bash
python3 staticpy/static_translate.py imgproc/mirror_gif.static.py | head   # 翻译器自检
bash selfcheck.sh                                                          # 端到端回归
```

## 5. 三条铁律

- **顶层不要调用 `main()`**：翻译器自动加 `(static_main)`，写了会跑两遍。
- **函数名与 Scheme 侧一致**：插件里已在 Scheme 实现的函数必须列进 `prelude_functions`，
  否则调用会被加上 `static_` 前缀当成用户函数。
- **新的语法只走插件**（`hooks.py`），不往 `static_translate.py` 加规则——核心语法已冻结。
