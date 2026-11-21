# SELFHOST —— 三环自举、种子边界与信任链

> 编译器不是"凭什么信它"，而是"**能被谁审计**"。答案：把信任收敛到一小段**冻结的种子**，
> 而"自举实现 ≡ 种子"这件事本身**在本仓可复现、可差分**（`staticpy/check_*.sh`）。

---

## 1. 三环

| 环 | 源语言 | 编译器实现 | 自举结果 |
|---|---|---|---|
| 1 ReScheme | 自定义（类 OCaml，HM 类型） | OCaml（lexer/parser/typecheck/codegen） | OCaml 版编译 bootstrap 编译器，再编译自身 |
| 2 **StaticPy** | Python 子集 | **自举翻译器**（`staticpy/*.static.py` → ELF） | 翻译器编自己，编 `staticc.py`，再编自身 |
| 3 **`.sp`** | S-表达式（极简） | Python → `.sp` 自持 | `staticc.sp` → `staticc` ELF → `staticc_self` ELF |

本仓保留环 2 / 环 3 的**可执行部分**与环 1 的说明；环 1 的 OCaml 源码在上游 `ReScheme`。

## 2. 环 2 的内部：谁是"真的翻译器"

环 2 不是"一个 CPython 脚本"，而是**一份用 StaticPy 子集写的编译器**，四个文件拼起来即为全部：

| 文件 | 职责 |
|---|---|
| `staticpy/static_translate.static.py` | **词法器 + 驱动**：缩进敏感的 token 流（NEWLINE/INDENT/DEDENT）、字符串/数字字面量、extern 抽取、CLI |
| `staticpy/parse_lib.static.py` | **解析器**：token → AST（dict 表示，节点键与 CPython `ast` 对齐） |
| `staticpy/emit_lib.static.py` | **类型系统 + 代码生成**：`emit_expr`/`emit_stmt`/`emit_program` → Scheme IR |
| `staticpy/emit_dump.static.py` | **入口薄壳**：把上面三个 `concat` 起来，接受 `<src> [--lib]`，输出 IR |

把它们拼起来编译成 ELF，就是**生产可用的翻译器**：

```bash
cat staticpy/static_translate.static.py staticpy/parse_lib.static.py \
    staticpy/emit_lib.static.py staticpy/emit_dump.static.py > ~/iso_gen/t.static.py
staticpy build ~/iso_gen/t.static.py -o translator
./dist/translator imgproc/mirror_gif.static.py | head -20   # 出 Scheme IR
```

另外两个 dump 薄壳（`tokenize_dump.static.py` / `parse_dump.static.py`）与上面的 `emit_dump`
同构，专供**前端形状差分**使用（见 §4）。

> 这个 ELF 翻译器**已经顶替 `static_translate.py`**（连它自己都能编），
> 无 CPython 的完整构建路径与现状表见 **§7.5**。

## 3. 种子：`staticpy/static_translate.py` 已冻结

`staticpy/static_translate.py`（CPython + `ast` 模块，约 19 万字符）现在是**种子**，不是待迁移品：

```
种子（CPython + ast）──起爆──► 自举翻译器（.static.py → ELF）──► 编译一切，包括自己
        ↑                                                              │
        └──────────────── 验收：IR 逐字节/规范化一致 ◄──────────────────┘
```

**约定（本仓的硬规矩）**：

- **日常开发不碰种子**。要改语言/修翻译行为，改 `*-lib.static.py`（环 2 自举链）。
- **种子只做最小必要修改**，且只在一种情形下允许改：发现**翻译器语义 bug** ——
  种子与自举翻译器对同一输入给出不同 IR，**且**种子本身违背 Python 语义（照 CPython `ast` 对不上）。
  先怀疑自举链，确认"种子算错了"再动种子。
- **改种子 = 重走完整自举**。种子一改，它产出的 IR 就变，而自举链是照着旧种子的 IR 写的，
  必然连带修改 `*-lib.static.py`；改完让两者重新一致。**这两件事不可分割。**

> 为什么冻结：种子是信任链的起爆点，等于公理。公理动一次，下游全部要重新证明。
> 与 [VISION.md](../VISION.md) 一致：**约定长存，实现皆耗材**——种子是"约定的一种已审计实现"。

## 4. 四层验收（机器判据，逐层收窄）

| 层 | 脚本 | 判据 | 挡住的错 |
|---|---|---|---|
| 词法 | `bash staticpy/check_tokenize.sh <f…>` | 自举词法器 vs CPython `tokenize`，**token 流逐行一致** | 缩进/字面量/转义解析偏了 |
| 语法 | `bash staticpy/check_parse.sh <f…>` | 自举解析器 vs CPython `ast`，**规范 dump 逐字节一致** | AST 形状错、节点键漏 |
| IR | `bash staticpy/check_translate.sh <f…>` | 自举翻译器 vs 种子，**IR 逐字节一致**（严格）；否则规范化后一致 | 代码生成跑偏 |
| 语义 | `python3 staticpy/semantics_diff.py [-v]` | 同一份 `.static.py`：CPython 跑 vs AOT ELF 跑，**stdout 逐行 diff** | "翻过去了但算错了" |

- 每个脚本默认只吃你给的文件；给全仓库的 `.static.py` 就是全量回归（当前 **fail=0**）。
- 无 `main()` 的纯函数库自动按库模式（`--lib`）比对，不需要手写标志。
- `check_translate.sh` 会报 `ok(严格)` 或 `ok(规范化)`：前者含 `;; file:line` 注释逐字节相同，
  后者允许注释/空白差异——**里程碑判据是规范化一致**，严格一致是加分项。

`selfcheck.sh` 把其中三层挂进了一键回归（`[0c]` 词法、`[0d]` 语义、`[4]` 环 2/3 比对 + imgproc 构建与差分）；
**`check_parse.sh` 与 `check_translate.sh` 是显式的"改完就跑"项**——改了 `parse_lib`/`emit_lib` 之后必须手跑。

## 5. 改种子后的复跑清单（一次都不能省）

```bash
# 1 词法：种子/种子对应物 vs CPython tokenize
bash staticpy/check_tokenize.sh staticpy/static_translate.py selfhost/staticc.py imgproc/pil_lib.static.py
# 2 语法：自举解析器 vs CPython ast
bash staticpy/check_parse.sh $(git ls-files '*.static.py' | head -20)
# 3 IR：种子 vs 自举翻译器，须 fail=0
bash staticpy/check_translate.sh $(git ls-files '*.static.py')
# 4 语义：CPython 输出 vs AOT ELF 输出
python3 staticpy/semantics_diff.py
# 5 一键端到端：单一真源/插件钩子/词法/语义/imgproc 构建+差分+覆盖/hashlib/zlib/自举比对
bash selfcheck.sh
# 6 重建环 3：staticc.py → ELF，再用 staticc.sp 验自持
bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc
```

任何一环红了就等于没有完成——**判据只认"IR 一致 + 差分全绿"，不认"我觉得改对了"**。

## 6. 信任链

```
OCaml 编译器 → ReScheme 编译器 → static_translate.py（种子，冻结）
                              → 自举翻译器 ELF（staticpy/*.static.py）
                              → staticc ELF → staticc.sp（1653 行，信任根）
                              → Chez → 机器码
```

| 角色 | 文件 | 规模/性质 |
|---|---|---|
| 种子 | `staticpy/static_translate.py` | 冻结；改动 = 重走自举 |
| 自举翻译器 | `staticpy/{static_translate,parse_lib,emit_lib,emit_dump}.static.py` | 日常演化面 |
| 信任根 | `selfhost/staticc.sp` | 1653 行（拆分审计版 `staticc_split.sp` 1167 行） |
| 兼容垫片 | `selfhost/run_staticc_py.py` | 让 `staticc.py` 在 CPython 下直跑（比对用） |

可替换性：编译器/解释器只是"约定"的实现——谁都可以另写一份（甚至自持/自举），
需要信任的只有那一小段种子。这是"开放架构给 agent"的完整含义：**工具链可自持、可替换、可审计**。

## 7. 复现环 2 / 环 3

```bash
# 环 2：staticc.py 在 CPython 下 与 编成 ELF 后，编同一份输入，输出必须一致
python3 selfhost/run_staticc_py.py selfhost/tests/test_staticc_input.sp ~/iso_gen/a.scm
bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc
./dist/staticc selfhost/tests/test_staticc_input.sp ~/iso_gen/b.scm
diff ~/iso_gen/a.scm ~/iso_gen/b.scm     # 一致 → 环 2 成立

bash selfcheck.sh                        # 一键（[4/4] 这条比对 + [5-7] 信任链/DDC/固定点）
```

环 3（`.sp` 信任根自持）——**已自动化，别再手敲**：

```bash
bash trust/fixpoint.sh      # 三阶段固定点，产物落 ~/iso_gen/trust/fixpoint
```

```
stage0  seed 编 staticc.py → E0
stage1  E0 编 staticc.sp   → g1.scm
stage2  g1 → E1；E1 编 staticc.sp → g2.scm
stage3  g2 → E2；E2 编 staticc.sp → g3.scm
判定    g2 ≡ g3（token 级）→ 固定点成立
```

**规范化**指 token 级比较（`trust/normalize_scm.py`：去注释、去空白，但字符串字面量原样保留），
不是行级 `sed`——行级正则会截断 `"a;b"`、折叠 `"a  b"`，把不同的 IR 误判成相同。

2026-11-20 实测：`g1 66150 B / g2 65698 B / g3 65698 B`，`g2 ≡ g3` 且 `g1 ≡ g2`
（字节数差只是换行风格）。**g1 ≡ g2 比固定点更强**：种子与自举编译器给出的 IR token 全同。

> 固定点只证明「编译器能稳定复制自己」，**不证明它翻译得对** —— 自洽后门同样能通过
> （Thompson 攻击）。正确性另需异源双编译 `trust/ddc.sh`，见 §6.5。

## 6.5 信任判据装置（`trust/`）

信任链不能只有主张，得有装置。四件套：

| 装置 | 干什么 | 命令 |
|---|---|---|
| `trust/fixpoint.sh` | 三阶段固定点：自举链是否收敛 | `bash trust/fixpoint.sh` |
| `trust/ddc.sh` | **异源双编译（DDC）**：`staticc.py`（Python 语法）vs `staticc.sp`（S-表达式）对同一源出 IR 是否一致 | `bash trust/ddc.sh` |
| `trust/manifest.py` | 信任链清单：被信文件的哈希/行数；`--verify` 检测悄悄漂移 | `python3 trust/manifest.py --verify` |
| `trust/normalize_scm.py` | IR 的 token 级规范化（E5/E6 的判据实现）——**判据自己也有 StaticPy 版**，见下行 | `python3 trust/normalize_scm.py --eq A B` |
| `trust/normalize_scm.static.py` | 同一判据的 StaticPy 实现，编出 `dist/normscm`；`trust/norm.sh` 优先用它，于是**校验不再要求目标机有 CPython**。两份实现由 `selfcheck.sh [0e]` 逐字节比对，不一致即判据失效 | `bash staticpy/static_build_comfycli.sh trust/normalize_scm.static.py normscm` |

**为什么必须有 DDC**：本仓过去只有「同源不同执行方式」的自比（`staticc.py` 用 CPython 跑
vs 编成 ELF 跑）—— 同源自比挡不住 Thompson 攻击，因为两份产物来自同一份代码。
DDC 比的是**两份不同代码**：只藏在其中一份、且只在自编译时激活的后门，会让两侧 IR 分叉。

**边界（务必照抄到主张里）**：DDC 只覆盖**两份实现都能处理**的语法子集。
2026-11-20 实测 31 个用例：`IR 一致 25 / 负向拒绝 6 / 分叉 0 / C2 能力未覆盖 0`。

> 早先报的"7 个用例 C2 未覆盖（lambda / 嵌套 def / `list` / `%`）"**是假的**：根因不是
> `staticc.sp` 缺语法，而是 `ddc.sh` 默认吃了一个陈旧的预置二进制（`spboot_self` 早于
> `staticc.sp` 的修改时间），把"新 C1 vs 旧 C2"的二进制落后误报成能力差。改为**从源码
> 现建 C2 并按 `sha256(staticc.sp)+sha256(staticc.py)` 绑定**后，gap 归零。
> 教训：任何"预置二进制 + 源码"的组合都可能悄悄错配——C2 来路必须 hash 绑定。

DDC 仍**不是**普遍正确性证明：它只证明两份实现一致（且二者并非完全独立作者）。
分级与仍未证的两件事见 **`trust/REPORT.md`**。

## 7.5 不用 CPython 的构建路径（自举翻译器 ELF，已验证）

环 2 的产物可以**直接替代种子 `static_translate.py`**：四份 `.static.py` concat 成一个程序、
编译成 ELF，就是生产翻译器；它出 Scheme IR，再把这份 IR 当 `.scm` 喂给兼容入口
（该入口对 `.scm` 输入跳过翻译阶段），全程不碰 CPython。

```bash
# ① 起爆（只在翻译器自身改动后才需要 CPython，一次）
cat staticpy/static_translate.static.py staticpy/parse_lib.static.py \
    staticpy/emit_lib.static.py staticpy/emit_dump.static.py > ~/iso_gen/t.static.py
staticpy build ~/iso_gen/t.static.py -o dist/translator   # → dist/translator{,.so}

# ② 之后：翻译 + AOT + 链接，全无 python3
./dist/translator app.static.py > ~/iso_gen/app.code.scm
STATICPY_OUTDIR=$PWD/dist bash staticpy/static_build_comfycli.sh ~/iso_gen/app.code.scm app
./dist/app

# ③ 自举不动点：翻译器编自己 → 新 ELF 再编自己，两份 IR 逐字节相同
./dist/translator ~/iso_gen/t.static.py > ~/iso_gen/t.code.scm
STATICPY_OUTDIR=$PWD/dist bash staticpy/static_build_comfycli.sh ~/iso_gen/t.code.scm translator_self
diff <(./dist/translator_self ~/iso_gen/t.static.py) <(./dist/translator ~/iso_gen/t.static.py)   # 必须空
```

现状（在 `staticpy/check_translate.sh` 与上述命令下可复现）：

| 环节 | 现在是否要 CPython | 说明 |
|---|---|---|
| 翻译 `.static.py` → Scheme IR | **否** | `dist/translator`（自举 ELF）；全量 69 个 `.static.py` 的 `check_translate.sh`：fail=1，唯一例外是 `examples/syntax_plugin/demo.static.py`（它要 `syntax_plugin` 自定义语法，得带插件跑）。带 `# expect: build-error` 头的**故意响亮失败**用例（`fstring_conv_a`、`toplevel_for`）不再算 fail —— 脚本按标记断言「构建必须非零退出」（种子的 `TRANS_ERRORS` 退出码 2，环 2 发运行期 `(error …)`）；`check_parse.sh` 同集合 fail=0 |
| IR → AOT → 独立 ELF | **否** | `.scm` 输入跳过翻译；只依赖 `scheme` + `gcc` |
| 运行产物 | **否** | 独立 ELF，目标机零依赖（见 [DEPLOY.md](./DEPLOY.md)） |
| 起爆翻译器本身 | 是（**一次**） | 种子 `static_translate.py`；之后靠 ③ 自持，Python 可完全退场 |
| 插件顺序解析（`STATICPY_PLUGINS`） | 是 | `kernel.plugin` 仍是 Python；不传该变量就不触发 |
| 验收 / 差分（`check_*`、`semantics_diff`、`difftest`、`coverage`） | 是 | **测量对照**用，按 [AGENTS.md](../AGENTS.md) 约定不进产物链路 |

> 别把"产物不需要 Python"和"仓库工具不需要 Python"混为一谈：**编译链**（①②③）已可无 CPython，
> **验收链**（用 CPython + Pillow/numpy 当对照物）仍然需要——它是判据，不是依赖。

## 7.6 把 isinstance 的坑记下来（自举时必须裸名）

自举翻译器一度整体崩在 `hashtable-contains?: "\x0;N" is not a hashtable`，根因不在 dict，
而在**类型标签**——三个必须守住的约定（已修，回归判据是 `check_translate.sh` 全绿）：

1. `isinstance(x, T)` 的 `T` 必须取**裸名**（`'str`/`'int`/`'EConst`），不能走 `translate_expr`：
   内建类型名在值位置会被换成值包装器（`str → py-str`、`int → ((lambda (x) ...))`），
   而 prelude 的 `ir-builtin-isa?` 只认 `'str`/`'int`/`'float`…——一旦错位，`isinstance(any, str)`
   **恒假**，自举版 `emit_lib` 的 `nt()` 就把哨兵字符串当 dict 用，直接崩。
2. `Tuple` 字面量是 **`py-tuple`**（Python tuple 记录，repr 为 `(..)`），不是 `vector`；
   `vector` 只给 `EConst(x)` 这类 IR 记录类构造器用。
3. Python 侧 `py_float_repr` 在 Scheme 预置里叫 **`py-float-repr`**；`scheme_name` 的
   `RUNTIME_MAP` 漏映射就会在运行时报「variable py_float_repr is not bound」。

## 8. 文件

| 文件 | 作用 |
|---|---|
| `staticc.py` | 用 StaticPy 子集写的编译器（证明 StaticPy 能编译自身） |
| `staticc.sp` / `staticc_split.sp` / `staticc.sp.orig` | `.sp` 编译器（信任根）及其拆分/原始版本 |
| `run_staticc_py.py` | CPython 兼容垫片（给 `staticc.py` 补 StaticPy 内建） |
| `tests/` / `examples/` | 自举比对输入与最小示例 |
