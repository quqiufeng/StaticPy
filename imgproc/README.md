# imgproc —— 图像处理库的 StaticPy 重写区（对标 Pillow）

把此前用 **Python/PIL** 做的图像处理，改用 **StaticPy** 重写：处理逻辑写在
`.static.py` 里，编解码/卷积等底层能力交给一个**运行时加载的 C++ 库**
（`libimgproc.so`，内部动态链接 `libgif.so.7` + 随附 stb 单头）。产物是**独立 ELF**
（不依赖 Python / venv / PIL）。与推理栈（comfycli / sdcpp_adapter）**无关**。

## 三层结构（各改各的）

| 层 | 文件 | 说明 |
|---|---|---|
| C++ 核心 | `../cpp/imgproc/*.cpp` → `libimgproc.so` | 对标 Pillow 的 C 核心 `libImaging` + 编解码 |
| FFI | `imgproc_ffi.scm` | 仅 `load-shared-object`；`foreign-procedure` 由 `.py` 的 `extern fn ... from "imgproc"` 生成 |
| StaticPy API | `*.static.py` | 处理逻辑（如镜像） |

C ABI 是稳定面，**多前端可绑**：StaticPy ELF、LuaJIT FFI、Python ctypes 都能直接调同一份 `.so`。
底层按需在**运行时**挂 C 库：截到今天 = `libgif.so.7`（GIF）、`libfreetype.so.6`（文字）+ 随附 stb（PNG/JPEG/BMP/TGA）。

## 目录

```
imgproc/
├── build.sh                 # 一键：C++ 库 + StaticPy ELF
├── imgproc_ffi.scm
├── mirror_gif.static.py     # 示例算子：GIF 逐帧镜像（无损，走索引帧）
├── pil_lib.static.py        # ★ StaticPy 版 Pillow 库（纯函数，无 main，可被集成）
├── pil_cli.static.py        # pil 的 CLI 分发（import pil_lib + main）
├── concat.py                # 把 pil_lib 与任意用户程序拼成 bundle
├── build_app.sh             # 用本库构建用户程序：build_app.sh USER.static.py OUT
├── examples/                # 集成示例（make_banner：用库而非 CLI）
├── pilcli.static.py         # 早期 CLI（convert/resize/crop/...）
├── pyimgproc.py             # libimgproc.so 的 ctypes 绑定（差分测试用）
├── pil_surface.py           # 自省 Pillow 公开 API → 覆盖面清单
├── pil_api.md               # 上面生成的清单
├── difftest.py              # 自动化差分测试：PIL vs 我们，逐像素比对
└── ../cpp/imgproc/
    ├── core.cpp geom.cpp color.cpp ops.cpp filters.cpp draw.cpp
    ├── imgproc.h imgproc_internal.h
    ├── build_cpp.sh
    └── thirdparty/{giflib/stb}
```

## 构建 / 运行

```bash
bash imgproc/build.sh
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/mirror_gif IN.gif OUT.gif
```

## 自动化迁移夹具（自省 → 铺桩 → 差分对齐）

整套方法论见 **[MIGRATION.md](./MIGRATION.md)**。要点：Python 自省把"接口面"机器枚举出来，
差分测试把"语义"自动验证——人只写实现，对不齐由机器报。

```bash
# 1) 自省 Pillow API → 清单（每个名字 = 一个待迁移接口）
/data/venv/bin/python imgproc/pil_surface.py > imgproc/pil_api.md

# 2) 差分测试：同一操作 PIL / 我们各跑一遍，逐像素比对
/data/venv/bin/python imgproc/difftest.py -v
```

`difftest.py` 是"再调"的驱动：改动 C++ 后重跑，**绿了就对齐了**（当前 38/38 全绿）。
对不上的项照 Pillow 源码对齐（`Filter.c` / `Resample.c` / `ImageOps.py` …）。

## 当前覆盖 / 状态

- **编解码**：GIF（多帧，保留索引+调色板，无损）、PNG/JPEG/BMP/TGA（stb）、**WebP（libwebp.so.7）**、**TIFF（libtiff.so.6）**（解码均逐像素一致）。
- **Image 核心**：open/save/new/copy/convert(RGB·RGBA·L·LA·P)/split/merge/getchannel/getbbox/frombytes/to_bytes/**多帧取用(img_frame/set_frame/append_frame)**。
- **几何**：crop · resize（+带 box）· thumbnail · rotate · transpose(7) · pad · scale · paste · paste(mask) · composite · alpha_composite(带位置) · blend · fit · contain。
- **ImageOps**：invert · grayscale · posterize · solarize · autocontrast · equalize · colorize · mirror · expand · fit · contain · pad。
- **ImageChops**：add/subtract/difference/multiply/screen/darker/lighter/blend · **add_modulo/subtract_modulo** · **soft_light/hard_light/overlay** · logical_and/or/xor · const · offset · **composite(a,b,mask)**。**ImageColor**：getrgb。**ImageStat**：getextrema。
- **调色板/量化**：`convert("P")` = browser 调色板 + Floyd–Steinberg + Heckbert 缓存（`Palette.c`）；`quantize()` 的 **MEDIANCUT**（哈希+3链表+最大堆 median-cut+逐盒平均）与 **MAXCOVERAGE**（最远点采样）、**FASTOCTREE**（`QuantOctree.c` 细/粗/查找立方）为精确移植，**索引/调色板与 Pillow 一致**。
- **ImageEnhance**：brightness/contrast/color/sharpness。
- **ImageOps.deform**：逆向映射 `img_warp` + StaticPy lambda 建坐标（PIL 为正向网格/deformer 协议）。
- **ImageFilter**：BLUR·SMOOTH(S)·SHARPEN·DETAIL·EDGE_ENHANCE(MORE)·FIND_EDGES·CONTOUR·EMBOSS·UNSHARP·BoxBlur·GaussianBlur·Median/Min/Max/Mode/Rank —— **卷积已按 Pillow `Filter.c` 精确对齐（含浮点/边界/3×3 翻转）**。
- **ImageStat**：mean/median/extrema/stddev/sum。
- **ImageDraw**：point/line/rectangle/rounded_rectangle/ellipse/polygon/arc。**ImageFont**：**FreeType**（运行时链接 `libfreetype.so.6`，与 Pillow 同引擎）+ `getbbox`/`multiline_text`。另有 `putalpha`。

**近似项**（未逐位对齐，已在差异测试放宽容差）：`draw.rounded_rect`/`draw.chord`（栅格化细节）。`thumbnail`（`reducing_gap` 两步）、`BoxBlur`/`GaussianBlur` 均已精确对齐。

差分测试当前 **97 项全部通过**（像素项 max=0；文字项 bboxΔ=0；Floyd–Steinberg 逐像素 99.2%）——含 `resize.{nearest,bilinear,lanczos}`（已按 Pillow
`Resample.c` 定点算法精确对齐）、全部 transpose / Ops / Chops / Enhance / Filter。GIF 镜像与源逐像素 **maxdiff=0**。

## 经验（见 MIGRATION.md 详述）

三条补齐路径：**运行时挂 `.so`** / **自写 C++ helper** / **改编译器对齐 Scheme IR**（本轮加 lambda/一等函数 → `Image.eval`）。
精确对齐只能**照抄 Pillow 的 C 源数值路径**（Filter/Resample/BoxBlur/Palette/Quant*），
配合**自省 + 差分测试**自动化闭环。工具（concat）用 StaticPy 自举。

## 覆盖面（自省核对）

`frontend_coverage.py` 用 PIL 自省清单核对我们的实现：**覆盖 97/100**（仅 `Image.eval`（需回调）、`ImageOps.deform`、`ImageFilter.Color3DLUT` 待做）。

## 编译器扩展（第 3 条路径）

StaticPy 语法不够兼容 Python 时，**直接改翻译器对齐 Scheme IR**（`staticpy/static_translate.py`）：
已加入 **lambda 表达式** 与 **一等函数**（函数值赋值/传参/调用不加 `static_` 前缀）。
据此实现了 `Image.eval`（lambda 建 LUT → `img_point`），与 Pillow 逐像素一致。

## 作为库被集成

`pil_lib.static.py` 是**纯库**（只有 `extern fn` 声明 + 包装函数，没有 `main`），任何 StaticPy 程序都能用它：

```python
# my_app.static.py
from pil_lib import img_open, img_save, img_grayscale, img_resize, img_pad, img_draw_line

def main():
    im = img_open("in.png")
    g = img_grayscale(im)
    r = img_resize(g, 120, 90, "lanczos")
    p = img_pad(r, 8, 8, 8, 8, 0xFFFFFFFF)
    img_draw_line(p, 8, 8, 128, 98, 0xFF0000FF, 2)
    img_save(p, "out.png")

# 构建（concat 把库拼进来 → 一个独立 ELF）：
#   bash imgproc/build_app.sh my_app.static.py my_app
#   LD_LIBRARY_PATH=cpp/imgproc/build ./my_app
```

`concat.py` 去掉 `import` 行并把库与用户代码合到一个作用域；`build_app.sh` 封装了「concat + AOT 编译 + 链接」。
C ABI（`libimgproc.so`）本身也是稳定面，LuaJIT/ctypes 等无需 StaticPy 即可直接调用。

## 写新算子

1. 新底层能力 → 加到 `cpp/imgproc/`（C ABI 在 `imgproc.h`）。
2. `.py` 顶部 `extern fn name(args) -> ret from "imgproc"` 声明。
3. 主逻辑写 `def main():`（**别在顶层调用 main**，翻译器自动加 `(static_main)`）。
4. `bash imgproc/build.sh`；`difftest.py` 验证。

FFI 细节：类型表**无 `void`**，返回 void 的 C 函数一律返回 `int`；入参 `str/int/float/ptr`；
多值参数（点列/LUT/调色板）用 CSV 字符串传。
