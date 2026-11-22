# selfhost —— 自举 / 信任链代码

从上游 `ReScheme` 拷来的**自举相关代码**，使本项目自成一体（不依赖 `/opt/ReScheme`）。
完整说明见 **[../docs/SELFHOST.md](../docs/SELFHOST.md)**。

```bash
# 环 2：CPython 跑 staticc.py  vs  staticc.py 编成 ELF 再跑，两边产出一致
python3 run_staticc_py.py tests/test_staticc_input.sp ~/iso_gen/a.scm
bash ../staticpy/static_build.sh selfhost/staticc.py staticc
../dist/staticc tests/test_staticc_input.sp ~/iso_gen/b.scm
diff ~/iso_gen/a.scm ~/iso_gen/b.scm          # 一致 → 自举成立
```

| 文件 | 作用 |
|---|---|
| `staticc.py` | 用 StaticPy 子集写的编译器（证明能编译自身） |
| `staticc.sp` / `staticc_split.sp` / `staticc.sp.orig` | `.sp` 编译器（信任根，**1653 行**；拆分审计版 1167 行） |
| `run_staticc_py.py` | CPython 兼容垫片 |
| `tests/`、`examples/` | 自举比对输入与最小示例 |
