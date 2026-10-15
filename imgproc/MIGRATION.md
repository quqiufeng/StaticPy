# 用 Python 自省驱动 API 对齐（自动化迁移方法）

把 Python 库（Pillow、numpy、cv2 …）迁到 StaticPy 的**可复制流程**。核心思想：
Python 的自省（`inspect` / `dir()` / 签名）能**机器枚举出全部接口**，于是"覆盖面"
可以自动化；语义则用**差分测试**（跑同一个操作，逐像素比对）来自动验证。两者配一对，
就是一条"自省 → 铺桩 → 差分对齐"的闭环——**人只写实现，对不齐由机器报**。

```
   ┌── 1. 自省 ──────────────┐   inspect / dir / signature
   │  枚举目标库全部函数/类/签名 │   → API 清单（每个名字 = 一个待迁接口）
   └──────────────┬──────────┘
                  ▼
   ┌── 2. 铺桩 ──────────────┐   清单 → extern fn 声明 + StaticPy 骨架 + C ABI
   │  一次性把接口面铺满          │   （"一口气全铺完"）
   └──────────────┬──────────┘
                  ▼
   ┌── 3. 差分对齐 ──────────┐   同输入 → PIL 结果 vs 我们结果 → 逐像素 diff
   │  绿=对齐，红=有差异         │   （"再调"：红项逐个修，直到全绿）
   └──────────────┬──────────┘
                  │
            回到 1（扩下一批接口 / 下一个库）
```

## 1. 自省：把 API 面变成清单

`imgproc/pil_surface.py` 遍历 PIL 各模块的公开名字，用 `inspect.signature` 取签名，
产出 `imgproc/pil_api.md`：

```bash
/data/venv/bin/python imgproc/pil_surface.py > imgproc/pil_api.md
```

- `dir(mod)` 过滤 `_` 前缀 → 公开名；
- `inspect.isclass / isfunction` 分类；`inspect.signature(obj)` 取参数表；
- 输出 markdown 表（函数/签名 + 类/成员）。

**这一步只给"接口"（名字/签名/文档），给不了"语义"。** 语义交给下一步。

## 2. 铺桩：清单 → FFI 声明 + 骨架

对清单里每个待迁接口：

- **C++ 底层库**（`cpp/imgproc/*.cpp`）：实现 C ABI（`imgproc.h`）。这是"重活"，对标
  Pillow 的 C 核心 `libImaging` + 编解码库。FFI 不擅长数组，故多值参数（点列/LUT/调色板）
  走 **CSV 字符串**；返回 `void` 的 C 函数一律**返回 `int`**（翻译器类型表没有 `void`）。
- **FFI 加载**（`imgproc_ffi.scm`）：只 `load-shared-object`；`foreign-procedure` 由 `.py` 的
  `extern fn name(args) -> ret from "imgproc"` 自动生成。
- **StaticPy API**（`*.static.py`）：`def main()` 里编排（**不在顶层调用 main**）。

> 关键：**照着自省出来的签名写**，别凭记忆——签名/默认值/参数顺序都以清单为准。

## 3. 差分对齐：机器报差异

`imgproc/difftest.py` 对每个算子：同一输入分别用 **PIL** 与 **我们的库**（经 `pyimgproc.py`
的 ctypes 绑定）跑一遍，转成 numpy 做**逐像素 diff**，报 `max/mean`：

```bash
/data/venv/bin/python imgproc/difftest.py -v      # 全绿即对齐
```

- 用 ctypes 直连 `.so` 跑差分，比走 StaticPy ELF 快，迭代顺（生产仍走 StaticPy）。
- 对不上的项，**去读 Pillow 源码对齐算法**（这正是自动化的价值——不用猜）：
  - 卷积：`src/libImaging/Filter.c`（浮点 `+0.5` 取整、**边界复制**、3×3 垂直翻转）；
  - 重采样：`src/libImaging/Resample.c`（定点系数 `PRECISION_BITS=22`、两趟 separable）；
  - `ImageOps/ImageEnhance`：`.py` 源（如 Brightness = `blend(black, image, factor)`）。
- 改完重编重跑，**直到 max=0**。

## 现状

`difftest.py`：**38/38 全绿（max=0）**，含 `resize.{nearest,bilinear,lanczos}`、全部
`transpose`、`ImageOps`、`ImageChops`、`ImageEnhance`、`ImageFilter`（卷积精确对齐）。

## 复用到别的库

把 `pil_surface.py` 的模块列表一换（numpy/cv2/…）、`difftest.py` 的用例一换即可。
C ABI 是稳定面，**多前端可绑**：StaticPy ELF、LuaJIT FFI、Python ctypes 调同一份 `.so`。

---

# 经验（本轮实战总结）

## A. 三条"补齐运行时"的路径

1. **有现成的 C 库** → 运行时挂 `.so`（`load-shared-object` / `DT_NEEDED`）。
   本轮：`libgif.so.7`、`libwebp.so.7`、`libtiff.so.6`、`libfreetype.so.6`。
2. **没有现成的** → 自己写 **C++ helper** 集成（`libimgproc.so` 就是这一层）。
3. **语法不够兼容 Python** → **直接改编译器**，让翻译器产出正确的 **Scheme IR**。
   本轮：给 `static_translate.py` 加 **lambda 表达式 + 一等函数**（赋值/传参/调用不加
   `static_` 前缀），据此把 `Image.eval`（要回调）做成了，且与 Pillow 逐像素一致。

> 判据只有一条：**产出的 Scheme IR 对不对**。IR 对了，后端 Chez 负责其余。

## B. 精确对齐的唯一方法：照抄 C 源的数值路径

**凭直觉写一定对不上。** 必须逐行移植 Pillow 的 C 实现——包括数据结构、运算顺序、
整数/浮点行为、边界处理、定点舍入。本轮遇到的"坑"：

| 模块 | 关键细节（照抄才对） | 源码 |
|---|---|---|
| 卷积 | 浮点累加 + `offset+0.5` 截断；边界**复制原值**（非 clamp）；**3×3 的垂直方向与 5×5 相反** | `Filter.c` |
| 重采样 | 定点系数 `PRECISION_BITS=22`、两趟 separable；**nearest 用 double 增量累积** `xo+=a0`（float 会在边界差 1px） | `Resample.c` |
| 盒/高斯模糊 | **分数半径**滑窗（`ww/fw` 定点权重），高斯=3 趟盒 | `BoxBlur.c` |
| 调色板 `convert("P")` | browser 调色板（10 空 + 6×6×6）+ Floyd–Steinberg + **Heckbert 盒搜索缓存**（按 `>>2` 桶） | `Palette.c` / `Convert.c` |
| 量化 | MEDIANCUT：哈希聚合 + **三轴链表** + **按 pixelCount 的最大堆**；MAXCOVERAGE：**最远点采样**；FASTOCTREE：细/粗/查找立方 | `Quant.c` / `QuantOctree.c` |
| Chops / composite | 整数公式；`Image.composite` 是 `(a*m+b*(255-m)+127)/255`（mask=255 取 image1） | `Chops.c` / `Image.py` |
| thumbnail | `round_aspect` + `_get_safe_box` + `reduce`（盒平均）两步 | `Image.py` |

**结论**：难啃的（quantize 的 median-cut / octree）只要照搬数据结构和数值顺序，也能 1:1。

## C. 自动化的价值

- **自省**给"接口面"（`inspect`/`dir`/签名）→ 清单、铺桩；
- **差分测试**给"语义"判据（同输入 → PIL vs 我们 → 逐像素 max/mean）→ **对不齐由机器报**；
- 人（或 agent）只做两件事：**读 C 源对齐** + **改实现**，然后重跑差分直到全绿。

## D. 架构经验

- **C ABI 是稳定面**：一份 `libimgproc.so` 被 StaticPy ELF / LuaJIT FFI / Python ctypes 共用；
  依赖塌成一层，无 import 解析、无 venv、无版本求解。
- **前端可集成**：`pil_lib`（纯库）+ `concat`（自举工具，也是 StaticPy 写的）+ `build_app.sh`。
- **产物即部署**：AOT 成独立 ELF/SO，拷文件即可跑。

## E. 尚未对齐（真·长尾）

`ImageOps.deform`（需网格变换回调）、`ImageFilter.Color3DLUT`（.cube/三线性）、
`ImageDraw` 圆角/弦的逐像素栅格化。均已记录，非阻塞。
