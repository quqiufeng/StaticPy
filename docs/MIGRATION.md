# MIGRATION —— 把 Python 库迁到 StaticPy（方法论）

> 三句话：**广度**用 Python 自省一键枚举；**深度**靠照抄参照实现的 C 源；
> **判据**交给自动化差分。人（或 agent）只做两件事：**读源对齐** + **改实现**，然后重跑差分到全绿。

```
① 自省  inspect / dir / signature  → API 清单（每个名字 = 一个待迁接口）
        │
② 铺桩  清单 → C ABI 声明 + StaticPy 骨架 + 插件声明（一次性铺满接口面）
        │
③ 差分  同输入 → 参照库结果 vs 我们结果 → 逐像素/逐字节 diff → 红了就改 → 全绿
        │
   回到 ①（扩下一批 / 下一个库）
```

三步都是为了把"对不对"变成**机器可判**：自省定义"要做什么"，差分定义"算不算做对"。

## 1. 自省：把 API 面变成清单

```bash
python3 imgproc/pil_surface.py > imgproc/pil_api.md   # 模块公开名 + inspect.signature
python3 imgproc/frontend_coverage.py                  # 清单核对我们的实现 → 覆盖 100/100
```

- `dir(mod)` 过滤 `_` 前缀 → 公开名；`inspect.isclass/isfunction` 分类；`inspect.signature` 取参数表。
- **这一步只给"接口"（名字/签名/文档），给不了"语义"**——语义交给 ③。

## 2. 铺桩：清单 → C ABI + FFI + 骨架

- **C/C++ 核心**（`cpp/<lib>/*.cpp`）：实现 C ABI（`<lib>.h`），重活在这一层。
  多值参数（点列/LUT/调色板）走 **CSV 字符串**；返回 `void` 的 C 函数一律**返回 `int`**。
- **FFI 加载**：插件 `ffi.scm` 只 `load-shared-object`；`foreign-procedure` 由
  `.py` 里的 `extern fn name(args) -> ret from "<lib>"` 自动生成。
- **StaticPy 前端**：纯函数库（无 `main`，可被 `concat` 集成）+ 薄 CLI（有 `main`）。
- **验证基线**：`difftest.py` 用 `ctypes` 直连 `.so`（迭代快），生产走 StaticPy ELF。

> 关键：**照着自省出来的签名写**，别凭记忆——签名/默认值/参数顺序都以清单为准。

## 3. 差分：机器报差异

```bash
python3 <lib>/difftest.py -v
```

同一输入分别用**参照库**与**我们的库**跑一遍，转 numpy/bytes 做逐像素/逐字节 diff，
报 `maxΔ / meanΔ`。对不上的项，**去读参照实现的源码对齐**（这正是自动化的价值——不用猜），
改完重编重跑，直到 `maxΔ=0`。

## 4. 精确对齐：照抄 C 源的数值路径

**凭直觉写一定对不上。** 必须逐行移植——数据结构、运算顺序、整数/浮点行为、边界处理、定点舍入。
imgproc 实战踩过的坑（照抄才对）：

| 模块 | 关键细节 | 参照源 |
|---|---|---|
| 卷积 | 浮点累加 + `offset+0.5` 截断；边界**复制原值**（非 clamp）；**3×3 的垂直方向与 5×5 相反** | Pillow `Filter.c` |
| 重采样 | 定点系数 `PRECISION_BITS=22`、两趟 separable；**nearest 用 double 增量累积** `xo+=a0`（float 会差 1px） | `Resample.c` |
| 盒/高斯模糊 | **分数半径**滑窗（`ww/fw` 定点权重）；高斯 = 3 趟盒 | `BoxBlur.c` |
| `convert("P")` | browser 调色板（10 空 + 6×6×6）+ Floyd–Steinberg + **Heckbert 盒搜索缓存**（按 `>>2` 桶） | `Palette.c` / `Convert.c` |
| 量化 | MEDIANCUT：哈希聚合 + 三轴链表 + 按 pixelCount 的最大堆；MAXCOVERAGE：最远点采样；FASTOCTREE：细/粗/查找立方 | `Quant*.c` |
| Chops / composite | 整数公式；`Image.composite = (a*m+b*(255-m)+127)/255`（mask=255 取 image1） | `Chops.c` / `Image.py` |
| 3D LUT | 定点三线性（`PRECISION_BITS=6`、`SCALE_BITS=18`），表项 `round(item*(255<<6))` | `ColorLUT.c` |
| thumbnail | `round_aspect` + `_get_safe_box` + `reduce`（盒平均）两步 | `Image.py` |
| 文字 | 用 **FreeType**（与 Pillow 同引擎）：`FT_Request_Size` NOMINAL `size*64` + `FT_LOAD_RENDER` | `_imagingft.c` |

**结论**：连 median-cut / octree 这种"难啃的"，只要照搬数据结构与数值顺序，也能 1:1。

## 5. "卡住了"先问三句

| 现象 | 缺什么 | 走哪条路 |
|---|---|---|
| 目标库依赖某个成熟 C 库 | 缺库 | **运行时挂 `.so`**（`libgif`/`libwebp`/`libtiff`/`libfreetype`/`libcrypto`） |
| 没有现成实现 | 缺实现 | **自写 C/C++ helper**（`libimgproc.so` 就是这层） |
| Python 语法写不出来 / 回调表达不了 | 缺语言特性 | **改自举翻译器**（`emit_lib.static.py` 加 lambda/一等函数一类特性 → `Image.eval`；见 [SELFHOST.md](./SELFHOST.md)）或**写语法插件** |

判据只有一条：**产出的 Scheme IR / 数值对不对**。IR 对了，后端 Chez 负责其余。

## 6. 单算子红了怎么办（缩小 → 读源 → 照抄）

1. 缩小输入（小图 / 常量 / 单通道），**打印参照实现与我们各自的输出**定位差异。
2. 找到参照库对应函数（C 或 Python），**读它的实现**。
3. 照抄：数据结构、运算顺序、取整方式、边界处理。
4. 重编重跑差分；边界项（±1px / ±1 值）往往是 **float vs double / 舍入方向 / 边界复制**。

## 7. 架构经验（为什么这套能扩张）

- **C ABI 是稳定面**：一份 `lib<lib>.so` 被 StaticPy ELF / LuaJIT `ffi.C` / Python `ctypes`
  共用；依赖塌成一层，无 import 解析、无 venv、无版本求解。
- **前端可集成**：纯函数库 + `concat`（自举工具，本身也是 StaticPy 写的）+ `build_app.sh`。
- **产物即部署**：AOT 成独立 ELF，拷文件即可跑（见 [DEPLOY.md](./DEPLOY.md)）。
- **换库只换两处**：自省的模块列表、差分的用例集；C ABI 与验证闭环照搬。

当前 imgproc 状态：覆盖面 **100/100**、差分 **100/100**（多数 `maxΔ=0`）；
近似项仅 `draw.rounded_rect` / `draw.chord` 的栅格化细节。
