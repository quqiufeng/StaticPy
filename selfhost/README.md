# selfhost —— 自举 / 信任链（轻量，无需外部依赖）

本目录是从上游 `ReScheme` 拷贝**自举相关代码与文档**（~316K），使本项目自成一体。

## 三环自举

| 环 | 源语言 | 编译器实现 | 自举 |
|---|---|---|---|
| 1 ReSchme | 自定义(类 OCaml) | OCaml | 自编译（本文档详述） |
| 2 **StaticPy** | Python 子集 | Python `static_translate.py` | `staticc.py → ELF → 编译自身` |
| 3 `.sp` | S-表达式（极简） | Python→.sp | `staticc.sp → staticc → staticc_self` |

## 信任链（收敛到可审计的种子）

```
OCaml 编译器 → ReSchme 编译器 → static_translate.py(CPython)
            → staticc ELF → staticc.sp(~1100 行 = 信任根) → Chez → ELF
```

## 复现自举（本目录即可）

```bash
# 方式 A：CPython 直接跑 staticc.py（StaticPy 语言的编译器）
python3 run_staticc_py.py tests/test_staticc_input.sp /tmp/a.scm

# 方式 B：把 staticc.py 编成 ELF，再用它编译
cd .. && bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc
./staticc selfhost/tests/test_staticc_input.sp /tmp/b.scm

# 二者一致 → 自举成立
diff /tmp/a.scm /tmp/b.scm
```

## 文件

- `staticc.py`：用 StaticPy 子集写的编译器（证明 StaticPy 能编译自身）
- `staticc.sp` / `staticc_split.sp` / `staticc.sp.orig`：`.sp` 编译器（S-表达式，信任根）
- `codegen.sp`、`static_ir.py`、`translate.py`、`translator.ss`：相关组件
- `run_staticc_py.py`：CPython 兼容垫片
- `tests/test_staticc_input.sp`：测试输入
- `BOOTSTRAP.md`：完整自举文档；`static_py_front.md` / `static_py_pipeline.md`：语言参考

## 本机实测（已验证）

```
方式 A：CPython 跑 staticc.py      → /tmp/a.scm
方式 B：staticc.py 编成 ELF 再跑   → /tmp/b.scm
diff A B                            → 一致 ✓          # 环 2：StaticPy 能编译自身

.sp 环：
staticc.py 编 staticc.sp           → sc1.scm → 编成 staticc_self ELF
staticc_self 再编 staticc.sp        → sc2.scm
规范化(去注释+去空白)比对            → 逐字节一致 ✓     # 环 3：.sp 信任根自持
```

结论：**本目录即可自举，不依赖 /opt/ReScheme。** 信任根（staticc.sp）可自持、可审计。
