# SPEC —— 语义子集的条目 ↔ 用例索引

> [LANGUAGE.md](./LANGUAGE.md) 讲**是什么**（语法/类型/FFI 约定），本文只做一件事：
> 把「承诺的语义」拆成**编号条目**，每条**钉住至少一个可跑的用例**。
>
> 为什么要这一层：评估报告的第 3 条短板是「自举成功 ≠ 正确」。
> 自举只证明「编译器能编自己」，不证明「语义对」。语义对只能靠 `semantics_diff.py`
> 的 CPython ⇄ ELF 逐行差分；而**差分只在有用例覆盖那条语义时才存在**。
> 所以真正要守的不是"文档写全了"，而是**这条语义有没有被判据盯着**——
> 本文 + `tools/check_spec.py` 就是那个"盯着"：条目没用例 = 红，用例没条目 = 红。
>
> 判据链（每层各有独立门禁，缺一层就有一段盲区）：

| 层 | 门禁 | 守什么 | 盲区 |
|---|---|---|---|
| token 流 | `check_tokenize.sh` | 分词一致（种子 ⇄ 自举） | 语义 |
| AST | `check_parse.sh` | 树形状一致 | 语义 |
| IR | `check_translate.sh` | IR 逐字节一致 | 运行期语义 |
| **语义** | **`semantics_diff.py`** + **本文** | CPython 输出 ⇄ ELF 输出逐行一致 | 没用例的条目 |
| 自举 | 三环重编 + IR 基线 | 工具链自持 | 语义 |

---

## 1. 条目索引（机器校验：`python3 tools/check_spec.py`）

格式固定：`| 编号 | 语义要点 | 用例（tests/semantics/，逗号分隔，省略 `.static.py`） |`。
编号一旦发布**不复用、不改义**；条目废弃写 `（已废弃）` 并保留行，让 git 历史可追。

| 编号 | 语义要点 | 用例 |
|---|---|---|
| S-INT | 整数算术、bignum 不溢出、`//`/`%` 符号随除数、`**` 整数幂 | int_arith, aug_assign |
| S-BIT | 位运算（与/或/异或/取反/左移/右移）：左移走 bignum 不溢出，右移对负数补符号 | bitops |
| S-FLOAT | 浮点算术与 int/float 混算（插 `exact->inexact`）、打印格式 | float_arith |
| S-ROUND | `round()` 银行家舍入且返回 int；`round(x, n)` | round_builtin |
| S-TRUTHY | `py-truthy`：None/0/""/[]/{} 为假；`and`/`or` 返回操作数；`in` 判定 | truthy_flow, none_truthy_in |
| S-CMPCHAIN | 链式比较 `a < b < c`：中间操作数只求值一次、逐对短路 | cmp_chain |
| S-TERNARY | 条件表达式与短路求值 | ternary_flow |
| S-STR | str 字面量/拼接/比较/成员/方法（`strip split replace join upper lower startswith find` 等） | str_ops |
| S-STRFMT | `str.format`：位置/关键字/嵌套字段/格式说明符（宽度·精度·对齐·进制） | str_format, str_format_spec |
| S-STRPCT | `%` 格式化：右侧单值 vs tuple 展开、标志/宽度/精度、未知转换符运行期响亮失败 | str_percent_misc, str_percent_bad |
| S-FSTR | f-string：插值、`!r`/`!a` 转换、格式说明符、嵌套引号；不支持的转换响亮失败 | fstring_repr, fstring_spec, fstring_conv_a |
| S-SLICE | 切片含步长与负下标、负步长、tuple 切片 | slice_step, tuple_slice |
| S-LIST | list 构造/追加/索引赋值/成员/长度/嵌套 | list_ops |
| S-DICT | dict 字面量/读写/键存在/`get`/迭代给 keys/删除 | dict_ops, dict_sub |
| S-ITER | `for` 迭代协议：range/str（给 1 字符 str）/list/dict（给 keys）/表达式结果/嵌套 | iter_seq, for_iter_seq |
| S-CLASS | class → record：单继承、多基内联、类属性默认值、`@classmethod`/`@staticmethod`、方法当值 | class_inherit, class_multi, class_defaults, class_methods, class_methodval |
| S-LAMBDA | lambda / 一等函数：函数值赋值、传参、回调 | lambda_fn |
| S-RECUR | 递归（含深递归不炸栈的边界） | recursion |
| S-BUILTIN | 内建函数子集：`len range int float str bool abs min max sum sorted print` | py_builtins |
| S-TIME | `time.time()` 返回 float（一次调用内自洽，不比对绝对时间） | time_time_float |
| S-TOPFOR | 顶层 `for`/`while`/`if` 无静态语义 → **构建期响亮失败** | toplevel_for |

## 2. 预期失败用例（`# expect:` 头）

有些条目测的不是输出值，而是「**不支持的东西必须响**」（VISION：静默降级 = bug）。
这类用例在文件首行声明预期，`semantics_diff.py` 走另一条判定路径：

| 标记 | 判据 | 现用例 |
|---|---|---|
| `# expect: build-error <子串>` | 构建必须失败，且产物/报错含该子串 | toplevel_for, fstring_conv_a |
| `# expect: runtime-error <子串>` | 构建成功、运行期必须非零退出且输出含该子串 | str_percent_bad |

新写这类用例时**必须**同时登记到上表和本节（`check_spec.py` 会核对两处一致）。

## 3. 怎么加一条语义（agent 的操作手册）

1. 在 [LANGUAGE.md](./LANGUAGE.md) 对应小节写清**语义**（示例代码 + 与 CPython 的差异点）。
2. 在 `tests/semantics/<name>.static.py` 写最小复现：只写 `def main():`，
   **不要在顶层调用**；打印可逐行 diff 的值（浮点用 `%.17g` 或固定 `:.6f` 避免尾数噪声）。
3. 在本文 §1 加/改一行，把用例名写进去。
4. 跑三层门禁，任一红都不算完成：
   ```bash
   export TMPDIR=$HOME/iso_gen/ctlbin
   python3 tools/check_spec.py                 # 索引 ⇄ 用例目录 双向一致
   bash staticpy/check_translate.sh tests/semantics/<name>.static.py
   python3 staticpy/semantics_diff.py <name>
   ```
5. 用例若暴露了语义错（不只是覆盖缺口）→ 先修**实现**（`staticpy/*.static.py` 或
   `tools/seed/prelude.scm`），门禁全绿再提交；提交信息写清「哪条语义、原来错在哪」。

## 4. 明确的空白（不要假装有覆盖）

下面这些**故意没有条目**，因为它们是 VISION §4.5 的**非目标**，而不是待办：
`try/except/raise`、生成器、闭包自由变量、`eval/exec`、动态 `getattr/setattr`、
`isinstance`、运算符重载、`super().m()`（只支持 `super().__init__`）。

判断标准：某个语义属于「非目标」还是「缺口」，只看它是否要求
「万物皆 PyObject + 运行期查找」——是则是非目标（[LANGUAGE.md](./LANGUAGE.md) §1 末），
否则就是缺口，补条目 + 用例。
