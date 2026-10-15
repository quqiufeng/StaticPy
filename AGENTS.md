# AGENTS.md — 把 Python 库迁移到 StaticPy（给 AI agent 的作业手册）

> 本项目的定位：**Python 语法 → Scheme IR → AOT 机器码 + 运行时挂 C 库**。
> 不重造语言：把成熟前端（Python 语法）、成熟后端（Chez Scheme）、原生能力（C 库）
> 对齐成一套**约定**。任何一层不够用，都可以改（翻译器 / C helper / FFI）。
>
> 本文以第一个样板 **`imgproc`（StaticPy 版 Pillow，对标 100% 覆盖、差分 100/100）**
> 为案例，把可复制的工作流写成 agent 能直接照做的步骤。

---

## 0. 心智模型（先记住这几条）

1. **Python 的自省是免费的 API 清单**：`inspect` / `dir` / `signature` 能把目标库的
   接口面机器枚举出来。**覆盖面的“广度”可以自动化**。
2. **语义靠差分测试判定**：同一输入分别跑「原库」与「我们」，逐像素/逐值比对。
   **“对不对”交给机器报**。
3. **精确对齐只能照抄 C 源的数值路径**——数据结构、运算顺序、整数/浮点行为、
   边界处理、定点舍入。**凭直觉写一定对不上**。
4. **只认一条判据：产出的 Scheme IR / 数值对不对**。IR 对了，后端 Chez 负责其余。
5. **不引入 Python 运行时依赖**：产物是独立 ELF/`.so`；能力用 FFI 挂 `.so`。
   验证阶段的 Python（含 Pillow/numpy）**只用于“测量对照”**，不进产物。

---

## 1. 三步闭环（核心工作流）

```
① 自省  inspect/dir/signature → API 清单（每个名字=一个待迁接口）
        │
② 铺桩  清单 → C ABI 声明 + StaticPy 骨架（一次性把接口面铺满）
        │
③ 差分  同输入 → 原库结果 vs 我们结果 → 逐像素 diff → 红了就改 → 直到全绿
        │
   回到 ①（扩下一批 / 下一个库）
```

命令（imgproc 里已具备，换库照搬）：

```bash
PY=/data/venv/bin/python
$PY <lib>/surface.py > <lib>/api.md          # ① 自省清单
$PY <lib>/coverage.py                        #    覆盖面核对（映射表驱动）
$PY <lib>/difftest.py -v                     # ③ 差分测试（逐像素）
```

- **自省只给“接口”（名字/签名/文档），给不了“语义”**。语义交给 ③。
- ③ 用 ctypes 直连 `.so` 迭代（比走 StaticPy ELF 快）；生产仍走 StaticPy ELF。

---

## 2. 三条“补齐运行时”的路径（按优先级）

| 情况 | 做法 | imgproc 实例 |
|---|---|---|
| 有现成的 C 库 | **运行时挂 `.so`**（`load-shared-object` / `DT_NEEDED`） | `libgif.so.7`、`libwebp.so.7`、`libtiff.so.6`、`libfreetype.so.6` |
| 没有现成的 | **自己写 C++ helper** 集成 | `libimgproc.so`（对标 `libImaging`+编解码） |
| 语法不够兼容 Python | **改编译器**，对齐 Scheme IR | 给 `static_translate.py` 加 **lambda / 一等函数** → `Image.eval`、`deform` |

> 遇到“做不了”时，先问：是缺库（→1）、缺实现（→2）、还是缺语言特性（→3）？

---

## 3. 精确对齐：照抄 C 源（血泪坑表）

**必读目标库的 C 实现**，逐行搬数值路径。imgproc 踩过的坑（照抄才对）：

| 模块 | 关键细节 | 源码 |
|---|---|---|
| 卷积 | 浮点累加 + `offset+0.5` 截断；边界**复制原值**（非 clamp）；**3×3 的垂直方向与 5×5 相反** | `Filter.c` |
| 重采样 | 定点系数 `PRECISION_BITS=22`、两趟 separable；**nearest 用 double 增量累积** `xo+=a0`（float 会在边界差 1px） | `Resample.c` |
| 盒/高斯模糊 | **分数半径**滑窗（`ww/fw` 定点权重）；高斯 = 3 趟盒 | `BoxBlur.c` |
| `convert("P")` | browser 调色板（10 空 + 6×6×6）+ Floyd–Steinberg + **Heckbert 盒搜索缓存**（按 `>>2` 桶） | `Palette.c` / `Convert.c` |
| 量化 | MEDIANCUT：哈希聚合 + **三轴链表** + **按 pixelCount 的最大堆**；MAXCOVERAGE：**最远点采样**；FASTOCTREE：细/粗/查找立方 | `Quant.c` / `QuantOctree.c` |
| Chops / composite | 整数公式；`Image.composite` = `(a*m+b*(255-m)+127)/255`（mask=255 取 image1） | `Chops.c` / `Image.py` |
| 3D LUT | 定点三线性（`PRECISION_BITS=6`、`SCALE_BITS=18`），表项 `round(item*(255<<6))` | `ColorLUT.c` |
| thumbnail | `round_aspect` + `_get_safe_box` + `reduce`（盒平均）两步 | `Image.py` |
| 文字 | 用 **FreeType**（与 Pillow 同引擎）：`FT_Request_Size` NOMINAL `size*64` + `FT_LOAD_RENDER`，`PIXEL(x)=((x+32)&-64)>>6` | `_imagingft.c` |

**结论**：连 quantize 的 median-cut / octree 这种“难啃的”，只要照搬数据结构与
数值顺序，也能 1:1 对齐。

---

## 4. 工程约定（务必遵守）

- **FFI 类型**：只支持 `str / int / float / ptr`；**没有 `void` 返回**——返回 void 的
  C 函数一律改成返回 `int`。多值参数（点列/LUT/调色板/坐标）用 **CSV 字符串**传。
- **`extern fn` 声明**：写在 `.py` 顶部；`foreign-procedure` 由翻译器生成；库用
  `load-shared-object`（放在 `<lib>_ffi.scm`）。
- **入口**：函数叫 `main()`，**不要在顶层调用**（翻译器自动加 `(static_main)`，重复会跑两遍）。
- **前可集成**：库拆成**纯函数文件**（无 `main`，如 `pil_lib.static.py`）+ 薄 CLI；
  用 `concat`（自举，StaticPy 写的）把库与用户程序拼成一个 bundle。
- **编译器可改**：语法不够兼容就改 `static_translate.py`，**让 IR 正确**即可
  （例：lambda → `(lambda (args) body)`；参数是函数值时调用不加 `static_` 前缀）。
- **临时文件**：一律放 `~/iso_gen/`，**禁止 `/tmp`**。
- **不引 pip 依赖**：能 `dlopen` 就别 `pip install`。

---

## 5. 每个算子/库的作业清单（Checklist）

迁移一个库：

- [ ] 写 `surface.py`：自省目标库 → `api.md`（函数/类/签名）
- [ ] 写 `coverage.py`：PIL 名 → 我们的实现名（映射表），量化覆盖进度
- [ ] 定 C ABI（`xxx.h`），多文件分域（core/geom/color/ops/filters/draw…）
- [ ] `build_cpp.sh`：`g++ -O2 -shared`，缺库用 `-l:libname.so.N`
- [ ] `<lib>_ffi.scm`：`load-shared-object`
- [ ] StaticPy 库（纯函数）+ CLI
- [ ] `difftest.py`：每个算子一条用例，**逐像素 max/mean**，红了就改
- [ ] 对齐：**读目标库 C 源**逐行搬（见 §3）
- [ ] 全绿后：文档（README / MIGRATION）+ 提交

迁移单个算子（当差分红时）：

- [ ] 缩小输入（小图/常量），**打印原库与我们各自的输出**定位差异
- [ ] 找到目标库对应函数（C 或 Python），**读它的实现**
- [ ] 照抄：数据结构、运算顺序、取整方式、边界处理
- [ ] 重编重跑差分；边界项（±1px/±1 值）往往是 float vs double / 舍入方向 / 边界复制

---

## 6. 反模式（别做）

- ❌ 凭直觉实现算法（对不上，且难查）→ ✅ 先读 C 源
- ❌ 用 `float` 做需要 `double` 的边界计算（差 1px）
- ❌ 用 clamp 代替“边界复制”（卷积/重采样对不上）
- ❌ 把构建产物（`.so`/ELF）提交进 git
- ❌ 让“测量用”的 Python 依赖进产物链路
- ❌ 在顶层调用 `main()`（跑两遍）

---

## 7. 案例时间线（imgproc 的真实提交脉络，可对照复现）

> 从"一个算子"到"对标 Pillow 100% 覆盖、差分 100/100"的路径：

1. `b07cf06` 起手：独立图像区，**首个算子 GIF 镜像**（C++ 挂 `libgif.so.7`，保留调色板无损）
2. `7ed1324` 铺开：多格式编解码 + 几何/Ops/Chops/Enhance/Filter/Stat/Draw/Font，
   **同时建立自动化夹具（自省 + 差分）**
3. `39b35f2` 首个难点：`resize` 按 `Resample.c` 定点算法对齐（38/38）
4. `485507c`→`ce3b42a` 扩覆盖（数据进出/合成/Ops/chop 变体/getcolors…）
5. `7f9fcd5` 文字：改用 **FreeType**（与 Pillow 同引擎，bboxΔ=0）
6. `3107221` `convert("P")`：browser 调色板 + FS 抖动 + **Heckbert 缓存**（无抖动逐像素一致）
7. `5834bd8`/`883b6f4` WebP / TIFF：**运行时挂 `.so`**
8. `0d8259b` 工具自举：`concat` 改用 **StaticPy 自己写**
9. `566881d` 前端拆成**可集成库**（`pil_lib`）+ `build_app.sh`
10. `f12cd02`/`dfd6ac0` 边界修正：nearest 改 **double 增量**；BoxBlur/Gaussian 精确移植
11. `90fb063`/`c138433`/`799143e` **量化三法**（median-cut / max-coverage / octree）逐位对齐
12. `dedd296` `thumbnail`（`reducing_gap` 两步）逐像素一致
13. `9257c6e` **改编译器**加 lambda/一等函数 → `Image.eval` 逐像素一致
14. `03e3bb7`/`a0428eb` `Color3DLUT` / `deform` 收尾 → **覆盖 100/100、差分 100/100**

**观察这条脉络**：先打通“一个算子 + 自动化闭环”，再批量铺接口面，
然后逐个攻“精确对齐”，遇到语言瓶颈就改编译器——**广度靠自省自动化，深度靠照抄 C 源**。

---

## 7.5 部署 = 强分发（自包含）

打包时把 ELF 用到的**全部 `.so`（含传递依赖）**一并收进包，配启动器设
`LD_LIBRARY_PATH=$DIR/lib` → **目标服务器零要求（连 Python 都不需要）**。
`bash imgproc/package.sh <app> <name>`。这正契合"给 agent 的强分发语言"：agent 产出的
工具是自包含产物，交给谁都能直接跑，不挑环境。

## 7.6 自举与信任链（工具链可自持、可审计）

StaticPy 不是"只能靠宿主"的：它**能自举**。上游 `/opt/ReScheme` 记录了**三环自举**：

| 环 | 源语言 | 编译器实现 | 自举 |
|---|---|---|---|
| 1 ReSchme | 自定义(类 OCaml) | OCaml（HM 类型） | 自编译 |
| 2 **StaticPy** | Python 子集 | Python（`static_translate.py`） | `staticc.py → ELF → 编译自身` |
| 3 `.sp` | S-表达式（极简） | Python→.sp | `staticc.sp → staticc → staticc_self` |

**信任链**：OCaml 编译器 → ReSchme 编译器 → `static_translate.py`(CPython) → `staticc` ELF →
`staticc.sp`（**~1100 行，几天可完整审计 = 整个系统的信任根**）→ Chez → ELF。

含义：**编译器和解释器只是"约定"的实现**——谁都可以另写一份，甚至自持/自举；
需要信任的只有那一小段可审计的种子。这也是"开放架构给 agent"的完整含义。

## 8. 关键命令速查

```bash
# 编译工具链目标（Python → Scheme → ELF）
bash staticpy/static_build_comfycli.sh input.static.py out_name [ffi.scm]

# 迁移库的构建 / 运行
bash imgproc/build.sh
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/pil <op> IN OUT [args...]

# 用库构建用户程序（concat 自举 + AOT）
bash imgproc/build_app.sh my_app.static.py my_app

# 验证
PY=/data/venv/bin/python
$PY imgproc/pil_surface.py > imgproc/pil_api.md
$PY imgproc/frontend_coverage.py
$PY imgproc/difftest.py -v
```

---

## 9. 一句话总结

> **广度**用 Python 自省一键枚举；**深度**靠照抄目标库的 C 源；**判据**交给自动化差分；
> **缺什么补什么**——挂 `.so` / 写 C++ helper / 改编译器。
> 人（或 agent）只做两件事：**读源对齐** + **改实现**，然后重跑差分到全绿。
