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

# 循环（支持 break / continue，见 §4.1 补丁 2）
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

# lambda / 一等函数（§4.1 补丁 7）：函数值可赋值、可传参、可回调
def apply_all(img: ptr, f: fn) -> ptr:
    return img_point(img, f)

# 位运算（§4.1 补丁 8）：翻译器兜底发 bitand/bitor/bitxor/lshift/rshift/Invert
# 这些名字由 static_prelude.scm 映射到 R6RS bitwise-*，语义对齐 CPython
m: int = 0xFF & 0x0F        # 15
s: int = 1 << 10            # 1024（bignum 也对：1 << 200 不溢出）
r: int = -8 >> 1            # -4（算术右移，与 Python 一致）
inv: int = ~6               # -7（= -(x+1)，二进制补码）

# 外部 C 函数声明
extern fn img_open(path: str) -> ptr from "imgproc"
```

**有限支持**：推导式（list / dict / set / 生成器；多 `for`、`if` 过滤、元组解包、
迭代 `range` / `list` / `str` / py-list / tagged array）、`match`/`case`（字面量、通配、
捕获、`|`、序列 `[a, *rest]`、映射 `{"k": v}`、类模式 `Pt(x=0)`/`Pt(1, y)`）、
元组解构 `x, y = 1, 2`、切片 `a[1:3]`、`dataclass`（编译成 record）、`enum`（编译成常量）。

### 数值与真值语义（对齐 CPython，不照抄 Scheme）

`+ - * /` 之类落地成 `fx*` / `fl*` 时要注意：**Scheme 的算子语义不等于 Python 的**。
下面这些坑由 `static_prelude.scm` 的 `py-floordiv` / `py-mod` / `py-pow` / `py-round` /
`py-truthy` 吸收，翻译器只负责选对名字：

| Python | 落到 | 关键差异（别用 Scheme 原生） |
|---|---|---|
| `a // b` | `py-floordiv` | 向下取整：`-7 // 2 == -4`（`fxdiv` 给 -3） |
| `a % b` | `py-mod` | 符号随除数：`-7 % 2 == 1`（`fxmod` 给 -1） |
| `a ** b` | `py-pow` | 整数幂走 bignum（`fxexpt` 不存在） |
| `round(x)` | `py-round` | 银行家舍入 + 返回 int（不是 flonum） |
| `pow(a, b)` / `pow(a, b, m)` | `py-pow` | 负指数回 float（`pow(2,-1) == 0.5`）、三参走模幂（`pow(2,10,100) == 24`） |
| `if x:` / `while x:` / `not x` / `a and b` / `a or b` | `py-truthy` | None / `0` / `""` / `[]` / `{}` 为假；`and`/`or` **返回操作数**而非布尔 |
| `a < b < c` | `emit_chained_compare` | 中间操作数只求值一次，逐对短路 |
| `"%d-%s" % (a, b)` | `py-str-percent` | CPython 的 %-格式化：右侧**只有 tuple 展开**（`"%s" % [1,2]` → `[1, 2]`）；`%s %r %d %i %x %X %o %f %%` + `- + 空格 0 #` 标志、宽度、精度；`%e/%g/%c/%(name)s` **运行时 error 报错**（不静默算错） |

整数与浮点混算时翻译器插 `exact->inexact`（`(fl* 1.5 4)` 会报 `4 is not a flonum`）。
每条规则都有对应用例：`tests/semantics/{int_arith,float_arith,aug_assign,cmp_chain,`
`ternary_flow,truthy_flow,bitops,round_builtin,str_format,str_format_spec,fstring_spec,py_builtins,slice_step}.static.py`，跑 `python3 staticpy/semantics_diff.py`。

### class（记录类型 + 静态分派）

`class` 编译成 `define-record-type`：字段是 record 槽，方法是**带 `self` 的普通过程**
（`static_<Cls>_<m>`）。分派在**编译期**完成——`p.twice()` 直接发 `static_P_twice`，
不做动态查找，所以没有多态（见下"能/不能"）。

```python
class Shape:                      # 单继承：class Square(Shape)
    kind: str                     # 类体声明 = record 字段（子类可加字段）
    n: int

    def __init__(self, n: int):   # 构造器 → static_Shape（无 self）
        self.n = n
        self.kind = "sq"

    def area(self) -> int:        # 实例方法：self 收起，调用静态绑定
        return self.n * self.n

    def twice(self) -> int:
        return self.area() * 2    # 方法间互调：self.area() → (static_Shape_area self)

    @classmethod                  # 类方法：cls 收起，Cls.m(...) 直调
    def unnamed(cls) -> str:
        return "shape"

    @staticmethod                 # 静态方法：无 self/cls
    def tag() -> str:
        return "T"
```

| 能 | 说明 |
|---|---|
| 单继承 `class Sub(Base)` + `super().__init__(...)` | 子类 record 含基类槽，基类方法在子类实例上可用（`super().m()` 不支持，会报错） |
| 多基 `class C(A, B)` | 主基类 `A` 挂 record 父槽；`B` 链的字段/方法**并进** C（就近覆盖） |
| 类属性默认值 `k: int = 7` / `tag = "hi"` | 字段声明 + `__init__` 里注入 `self.k = 7`（`__init__` 自己赋过的字段不注入） |
| 字段读写 `self.x = v` / `p.x` | 按**静态类型**解析字段归属（`(Owner-x p)`） |
| `@classmethod` / `@staticmethod` | 装饰器在编译期吃掉，不产生运行时对象 |
| 方法当值 | `p.twice` / `P.twice` → 裸过程值 `static_P_twice`（可直接传给 `fn` 形参） |

子类的 record 写 `(parent A)`：**父类槽位共享**，`static_A_m` 里的 `(A-name self)`
在 `Dog` 实例上照样成立（字段归属由「谁声明了这个槽位」决定，不是调用者）。
继承来的方法不必复制，`Dog` 只声明自己新增的槽位。

多继承与类属性默认值都在**核心里**（种子与自举环 2 同一套语义），不是插件降级：

| 写法 | 编译成 | 限制 |
|---|---|---|
| `class C(A, B, ...)` | `(parent A)` + `B` 链成员内联（顺序：接近的基类优先，C 自己的声明最高） | 额外基类**不能有 `__init__`**（记录只有一条父槽位链，种子会响亮报错；环 2 只合字段/方法）；内联方法里**不能有 `super()`** |
| `class C: k: int = 7` | 字段声明 + `__init__` 首部注入 `self.k = 7`；无 `__init__` 的类合成一个 | 默认值须是字面量（`_literal_type` 只认 str/int/float/bool/None） |
| `super().__init__(args)` | 直接发 `(static_<Base>___init__ self args...)`（主基类；基类没有 `__init__` 且不传参 = 空操作） | 只支持 `__init__`；没有 `super()` 对象、不能 `super().m()` |

```bash
# 语义判据（CPython 输出 vs AOT ELF 输出逐行比）
python3 staticpy/semantics_diff.py class_     # class_defaults / class_inherit / class_methods / class_methodval / class_multi
```

**注意**：没有动态分派、没有 `isinstance`、没有运算符重载（`__eq__`/`__add__` 不生效）。
**方法当值**（`f = P.twice` / `f = p.twice`）可用：类型记作 `fn`，调用点不再加 `static_`
前缀，值是**裸过程** `static_P_twice`——两处都不做 `self` 绑定，调用时必须显式传。

```python
f = P.twice          # 或 p.twice（同样是裸过程，不 bind self）
print(f(p))          # → 6     （CPython 里 p.twice 会绑定，p.twice(p) 报多传参）
print(apply1(P.twice, p))    # 形参 fn 是函数值，调用 fn(p) 不加 static_ 前缀
```

**不支持**（也不要绕）：`try`/`except`/`raise`、生成器/`yield`、
自由变量闭包、`eval`/`exec`、动态 `getattr`/`setattr`。

> 能力缺口按三条路径补：挂 C 库 / 写 C++ helper / 改自举翻译器或加语法插件（见 [PLUGINS.md](./PLUGINS.md)、[SELFHOST.md](./SELFHOST.md)）。

## 2. 类型系统

| StaticPy 类型 | 内部表示 |
|---|---|
| `int` | 64 位整数（Chez fixnum） |
| `float` | **32 位 float**（对齐 C ABI；见 §4.1 补丁 5） |
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

## 4. 编译器的两副面孔：种子（冻结）与自举翻译器（演化面）

| | 文件 | 状态 | 谁在改 |
|---|---|---|---|
| **种子** | `staticpy/static_translate.py`（CPython + `ast`，≈19 万字符） | **冻结**：环 2 的起爆点 | 只在"种子自身算错"时动，动完重走自举 |
| **自举翻译器** | `staticpy/{static_translate,parse_lib,emit_lib,emit_dump}.static.py` | 演化面：词法/解析/类型/代码生成 | 日常改语言就改这里 |

- **改语法 = 改自举链**：`emit_lib.static.py`（代码生成与类型）→ `parse_lib.static.py`（AST 形状）→
  `static_translate.static.py`（token 流）。改完必跑四层差分（见 [SELFHOST.md](./SELFHOST.md) §4）。
- 种子的作用从"生产翻译器"变成"**验收基准 + 引导器**"：自举翻译器产出的 IR 必须与它一致。
- 种子改动的唯一合法理由：**种子违背 Python 语义**（与 CPython `ast` 对不上，或与自举链分歧且错在种子）。
  先怀疑自举链——绝大多数"对不上"都是自举链还没跟上。

### 4.1 种子里的历史补丁（为什么它不等于上游 StaticPy）

`static_translate.py` = 上游 StaticPy + 下列补丁。这些补丁现在**已经搬进自举链**；
保留此表用于审计溯源与"上游升级时该重放什么"：

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
| 9 | 位运算：类型检查对 `Any` 放行 | 位运算规则表要求两侧 `int`，`x = 6`（未注解→`Any`）后 `x & y` 被误判为类型错误。改为 `Any` 跳过严格检查、结果类型置 `None`（走泛型 IR），运行期由 prelude 的 `bitand`/`bitor`/`bitxor`/`lshift`/`rshift`/`Invert` 承接 |

补丁 7 新增的全局：`CURRENT_PARAMS`（当前作用域参数名集合，调用时不加前缀）、
`TYPE_ENV[name] = "fn"`（函数值局部变量）。它是 `Image.eval` / `ImageOps.deform` 这类**回调**的前提。

校验：

```bash
# 自举翻译器单独出 IR（等价于种子，可逐字节对照）
staticpy translate imgproc/mirror_gif.static.py | head

# 自举翻译器的四层机器验收（改完必跑，任一红=没完成）
bash staticpy/check_tokenize.sh  imgproc/pil_lib.static.py   # token 流 vs CPython tokenize
bash staticpy/check_parse.sh     imgproc/pil_lib.static.py   # AST dump vs CPython ast
bash staticpy/check_translate.sh imgproc/pil_lib.static.py   # IR vs 种子（严格/规范化）
python3 staticpy/semantics_diff.py                           # CPython 跑 vs ELF 跑，stdout 逐行

bash selfcheck.sh                                            # 端到端回归
```

## 5. 三条铁律

- **顶层不要调用 `main()`**：翻译器自动加 `(static_main)`，写了会跑两遍。
- **函数名与 Scheme 侧一致**：插件里已在 Scheme 实现的函数必须列进 `prelude_functions`，
  否则调用会被加上 `static_` 前缀当成用户函数。
- **新的语法只走插件**（`hooks.py`），不往翻译器加规则——核心语法已冻结；
  确需动核心语法，改自举链（`staticpy/*-lib.static.py`）并重跑四层差分，**不要动种子**。

### 字符串方法 / 函数值

- `s.strip()/upper()/lower()/split(sep)/join(list)/replace(a,b)/startswith(x)/find(x)/zfill(n)…`
  在种子与环 2 都映射到 prelude 的 `str-*`；**接收者必须是 str**（字面量、f-string 或已推断为 `str`），
  否则仍走旧的 `({recv}-{attr})` 兜底。`split(maxsplit)` **响亮报错**，不静默降级。
- `str.format` 支持 `{}` / `{n}` / `{name}`（关键字实参）/ `{:spec}` / `{{}}`，
  格式说明与 f-string **共用同一套 prelude 函数** `py-format`（见下节）。
  `{}` 与 `{0}` 混用按 CPython 报错（`自动编号与手动编号不能混用`）；
  `{0[1]}` / `{x.attr}` 字段**运行期 `error`**。
- 函数值调用的 `static_` 前缀：形参、`f = lambda …`、**元素全是函数值的 list** 的循环变量
  （`for f in [inc, dbl]: f(1)`）与下标取用（`fs[0](7)`）都不加前缀；
  对应环境类型记 `fn` / `fn-list`，仅用于代码生成。

### f-string 与「响亮失败」

- `f"{x}"` → `(py-str x)`；`f"{x!r}"` → `(py-repr x)`；`f"{x!s}"` 同默认。
  `f"{x=}"` 的自文档走 CPython 的 ast 形状：`Constant("x=")` + `FormattedValue(conversion=114)`，
  相邻字面量必须**合并成一个 Constant**（环 2 的 `parse_lib` 用 `add_fconst` 保证与 CPython ast dump 一致）。
- **格式说明（format spec）已实现**：`f"{x:>5}"` / `f"{x:.2f}"` / `"{:>5}".format(x)` 都发到
  prelude 的 `py-format 值 "spec"`（`!r` 先转成 `py-repr`，即 `format(repr(x), spec)`）。
  `py-format` 支持 fill/align `< > ^ =`、sign `+ - 空格`、`#`、`0`、width、
  `,`/`_` 分组、`.prec`、类型 `s d b o x X c n f F e E g G %`；
  覆盖的 38 条实测（`0.0/#g`→`0.00000`、`999999.5/g`→`1e+06`、`1/=+8`→`+      1`、
  `255/#010x`→`0x000000ff`、`1234567/,`→`1,234,567`…）与 CPython 逐字符一致。
  不支持的组合（如 `,x`、`+` 配 str）**运行期 `error`**，不静默忽略。
- **没有实现的东西一律响亮失败，不许静默降级**：
  - 构建期（`TRANS_ERRORS` → stderr + 退出码 2）：`f"{x!a}"`、格式说明里含**嵌套 `{}`**
    （静态展开不了）、未知字符串方法、`super().attr(..)` 等；
  - 运行期（prelude `error`）：`%e/%g/%c/%(name)s`、`split(maxsplit)`、`{0[1]}` 字段等。
- `TRANS_ERRORS` **只在收集、必须报**：种子在 `main()` 末尾统一写 stderr 并 `sys.exit(2)`
  （`STATICPY_TRANS_ERRORS_WARN=1` 仅告警不退，供存量代码盘点用）。
  环 2 没有构建期失败通道，同样的形状发**运行期** `(error 'f-string …)`——两环都响。
- 用例侧用标记声明期望的失败（`semantics_diff.py` 认）：
  ```python
  # expect: build-error f-string 的格式说明
  # expect: runtime-error 不支持的 %-格式符
  ```
  前者断言「构建必须非零退出且信息含该子串」，后者断言「构建通过、运行非零退出且信息含该子串」；
  这类用例不参与 stdout 比对（CPython 侧不会失败，比了没意义）。
