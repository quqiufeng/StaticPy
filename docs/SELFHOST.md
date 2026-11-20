# SELFHOST —— 三环自举与信任链

> 编译器不是"凭什么信它"，而是"**能被谁审计**"。答案是：把信任收敛到一段很小的种子，
> 而这条收敛路径本身**在本仓就能复现**（`selfhost/` 是从上游 `ReScheme` 拷来的自举代码，不依赖外部仓库）。

## 1. 三环

| 环 | 源语言 | 编译器实现 | 自举结果 |
|---|---|---|---|
| 1 ReScheme | 自定义（类 OCaml，HM 类型） | OCaml（lexer/parser/typecheck/codegen） | OCaml 版编译 bootstrap 编译器，再编译自身 |
| 2 **StaticPy** | Python 子集 | `staticpy/static_translate.py`（CPython） | `staticc.py` → ELF → 编译自身 |
| 3 **`.sp`** | S-表达式（极简） | Python → `.sp` 自持 | `staticc.sp` → `staticc` ELF → `staticc_self` ELF |

本仓只保留环 2 / 环 3 的**可执行部分**与环 1 的说明；环 1 的 OCaml 源码在上游 `ReScheme`。

## 2. 信任链

```
OCaml 编译器 → ReScheme 编译器 → static_translate.py (CPython)
            → staticc ELF → staticc.sp（~1100 行 = 信任根）→ Chez → 机器码
```

- **信任根**：`selfhost/staticc.sp`，约 1100 行，可几天内完整读完。
- **可替换**：编译器/解释器只是"约定"的一种实现——谁都可以另写一份（甚至自持/自举），
  需要信任的只有那一小段种子。这与 [VISION.md](../VISION.md) 一致：**约定长存，实现皆耗材**。

## 3. 复现自举（本目录即可，不依赖 `/opt/ReScheme`）

```bash
# 环 2：CPython 跑 staticc.py（StaticPy 写的编译器）
python3 selfhost/run_staticc_py.py selfhost/tests/test_staticc_input.sp ~/iso_gen/a.scm

# 环 2'：把 staticc.py 编成 ELF，再用它编译
bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc
./dist/staticc selfhost/tests/test_staticc_input.sp ~/iso_gen/b.scm
diff ~/iso_gen/a.scm ~/iso_gen/b.scm     # 一致 → 环 2 成立

bash selfcheck.sh                        # 一键（其 [4/4] 就是这条比对）
```

环 3（`.sp` 信任根自持）：`staticc.py` 编 `staticc.sp` → `sc1.scm` → 编成 `staticc_self` ELF；
`staticc_self` 再编 `staticc.sp` → `sc2.scm`；**规范化（去注释+去空白）后逐字节一致** → 环 3 成立。

## 4. 文件

| 文件 | 作用 |
|---|---|
| `staticc.py` | 用 StaticPy 子集写的编译器（证明 StaticPy 能编译自身） |
| `staticc.sp` / `staticc_split.sp` / `staticc.sp.orig` | `.sp` 编译器（信任根）及其拆分/原始版本 |
| `run_staticc_py.py` | CPython 兼容垫片（让 `staticc.py` 直接跑） |
| `tests/` / `examples/` | 自举比对输入与最小示例 |

## 5. 已验证的结论

```
方式 A：CPython 跑 staticc.py      → a.scm
方式 B：staticc.py 编成 ELF 再跑   → b.scm
diff A B                           → 一致 ✓        # 环 2：StaticPy 能编译自身

.sp 环：staticc.py 编 staticc.sp  → sc1.scm → staticc_self ELF
       staticc_self 再编 staticc.sp → sc2.scm
       规范化比对                    → 逐字节一致 ✓  # 环 3：.sp 信任根自持
```

含义：**编译器和解释器只是"约定"的实现**；需要信任的只有那一小段可审计的种子。
这也是"开放架构给 agent"的完整含义——工具链可自持、可替换、可审计。
