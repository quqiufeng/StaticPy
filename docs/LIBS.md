# LIBS —— 已集成的库与工具

> 统一模式：**C/C++ 核心（`lib<lib>.so`）+ StaticPy FFI 前端 + 差分验证**。
> 每节给「构建 / 运行 / 验证」三条命令；细节在各自目录的源码里。
> 共用的构建/部署约定见 [ARCHITECTURE.md](./ARCHITECTURE.md) 与 [DEPLOY.md](./DEPLOY.md)。

| 库 | 能力 | 验证 |
|---|---|---|
| [`imgproc`](#imgproc) | Pillow 对标：GIF/PNG/JPEG/BMP/TGA/WebP/TIFF、几何、滤镜、文字、调色板、量化、伪 3D | 差分 **100/100**；覆盖 **100/100** |
| [`hashlib`](#hashlib) | md5/sha1/sha224/256/384/512 | **6/6** 逐字节 |
| [`zlib`](#zlib) | compress/decompress/gzip/crc32/adler32 | **5/5** 逐字节 |
| [`pathfind`](#pathfind) | 网格 A*（四/八邻，不切角） | **60/60** vs networkx |
| [`atlas`](#atlas) | 精灵图集打包（MaxRects-BSSF） | **60/60** 不变量 |
| [`cvops`](#cvops) | 形态学 / Otsu / Sobel / 双边 | **6/6** vs OpenCV |
| [`font`](#font) | TTF → 字形图集 + 度量（FreeType） | **15/15** vs PIL |
| [`easing`](#easing) | 25 条 Penner 缓动曲线 | **525/525** 双实现 |
| [`warp3d`](#warp3d) | 2D 图像 3D 旋转 / 透视 | **4/4** vs cv2（±1） |
| [`upscale`](#upscale) | `2x` Scale2x / `4x` Real-ESRGAN | Scale2x **20/20**；4x 走 ONNX |
| [`anim`](#anim) | 游戏素材流水线（骨架/切图/打包/GIF） | 端到端出图 |
| [`tools/`](#tools-推理工具) | ONNX 推理：人脸/抠图/OCR/放大/骨骼/深度… | 样例图实测 |
| [`luajit/`](#luajit-同一份-c-abi) | 同一 C ABI 的 LuaJIT 绑定 + 单文件 ELF 嵌入 | — |
| [`ltorch`](#ltorch直吊-libtorchaten--autograd) | 直吊 libTorch：张量 / 矩阵 / 激活 / 归约 / autograd | 差分 **18/18** + ELF |

约定：所有库都是「纯函数库（无 `main`）+ 薄 CLI」，因此可被 `concat` 拼进任意用户程序。

---

## imgproc

`cpp/imgproc/` → `libimgproc.so`（对标 Pillow `libImaging` + 编解码）；前端 `imgproc/`。

- **覆盖**：编解码（GIF 多帧保调色板、PNG/JPEG/BMP/TGA/WebP/TIFF）；Image 核心
  （open/save/new/copy/convert/split/merge/getbbox/frombytes/to_bytes/多帧）；
  几何（crop/resize/thumbnail/rotate/transpose/pad/paste/composite/blend/fit/contain）；
  ImageOps / ImageChops / ImageEnhance / ImageFilter（含 BoxBlur/Gaussian/Median…
  按 Pillow `Filter.c` 精确对齐）/ ImageStat / ImageDraw / ImageFont（FreeType）/
  `convert("P")` 调色板 + FS 抖动 / quantize 三法（MEDIANCUT / MAXCOVERAGE / FASTOCTREE）。
- **近似项**：`draw.rounded_rect`、`draw.chord` 的栅格化细节（差分已放宽容差）。

```bash
bash imgproc/build.sh
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/pil convert IN.png OUT.png L
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/mirror_gif IN.gif OUT.gif
python3 imgproc/difftest.py -v          # 100/100（多数 maxΔ=0）
python3 imgproc/frontend_coverage.py    # 100/100
```

## hashlib

`cpp/hashlib/` → `libhashlib.so`（走 OpenSSL EVP，运行时挂 `libcrypto.so.3`）；前端 `hashlib/hash`。

```bash
bash hashlib/build.sh
LD_LIBRARY_PATH=cpp/hashlib/build ./hashlib/hash sha256 IN.png
python3 hashlib/difftest.py             # Python hashlib vs 我们（逐字节）
```

`md5/sha1/sha224/sha256/sha384/sha512` 一致；`sha3_*`/`blake2*` 算法名可用（未逐一封装前端）；
`pbkdf2_hmac` / `scrypt` 待做。

## zlib

`cpp/zlib/` → `libzlib.so`（挂系统 `libz.so.1`）；前端 `zlib/zc`。
关键：**与 Python 用同一份 `libz`**，所以压缩字节天然可零容差比对。

```bash
bash zlib/build.sh
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc compress IN OUT [level]
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc decompress IN OUT
LD_LIBRARY_PATH=cpp/zlib/build ./zlib/zc crc32 FILE
python3 zlib/difftest.py
```

`compress`/`decompress`/`gzip`（`mtime=0`）/`crc32`/`adler32` 一致；流式 `compressobj`、`wbits` 变体待做。

## pathfind

`cpp/pathfind/` → `libpathfind.so`（A*，曼哈顿/octile 可采纳启发 → 最优）；前端 `pathfind/pf`。

```bash
bash pathfind/build.sh
LD_LIBRARY_PATH=cpp/pathfind/build ./pathfind/pf GRID.txt W H SX SY EX EY [DIAG]
python3 pathfind/difftest.py            # 60/60 vs networkx
```

输出 JSON：`{"cost":…,"path":[[x,y],…],"reached":true|false}`。
四邻（代价 1）/ 八邻（对角 √2，且**不切角**）。

## atlas

`cpp/atlas/` → `libatlas.so`（MaxRects-BSSF）；前端 `atlas/atlas`。

```bash
bash atlas/build.sh
LD_LIBRARY_PATH=cpp/atlas/build ./atlas/atlas sizes.txt 1024 1024
python3 atlas/difftest.py               # 60/60（在界内 + 无重叠 + 全打包）
```

`sizes.txt` 每行 `w,h`；输出 `{"packed":N,"total":M,"sheet":[W,H],"placements":[[x,y,w,h],…]}`。
下一步可接 `imgproc` 按布局贴成图集 PNG。

## cvops

`cpp/cvops/` → `libcvops.so`（自实现，不依赖 OpenCV，避免版本漂移）；前端 `cvops/cv`。

| 命令 | 算法 |
|---|---|
| `erode`/`dilate`/`open`/`close` | 形态学（矩形核，`BORDER_REPLICATE`） |
| `otsu` | Otsu 全局二值化 |
| `sobel` | Sobel 梯度幅度（\|G\|） |
| `bilateral` | 双边去噪（保边，近似） |

```bash
bash cvops/build.sh
LD_LIBRARY_PATH=cpp/cvops/build ./cvops/cv erode IN.png OUT.png 3
python3 cvops/difftest.py               # 6/6（bilateral 近似，mean≈5）
```

## font

`cpp/font/` → `libfont.so`（FreeType 光栅化 + shelf 打包）；前端 `font/font`。
渲染文字用静态位图字体（图集 + JSON），比每帧画字省。

```bash
bash font/build.sh
LD_LIBRARY_PATH=cpp/font/build ./font/font DejaVuSans.ttf 24 "ABCabc0123" out.png out.json 512
python3 font/difftest.py                # 15/15（advance/位图高与 PIL 一致）
```

输出 `out.png`（灰度图集）+ `out.json`（`{"size","width","height","glyphs":[{cp,x,y,w,h,bx,by,advance}]}`）。

## easing

`cpp/easing/` → `libeasing.so`；前端 `easing/ease`。规范 = Robert Penner 缓动。
曲线：`ease{In,Out,InOut}{Quad,Cubic,Quart,Quint,Sine,Expo,Circ,Back,Elastic,Bounce}` + `linear`。

```bash
bash easing/build.sh
LD_LIBRARY_PATH=cpp/easing/build ./easing/ease easeInOutCubic 0.5   # 0.500000
python3 easing/difftest.py              # 525/525（25 曲线 × 21 采样）
```

用途：Tween 位移/缩放/透明度、弹出/回弹等 UI 与角色动效。

## warp3d

`cpp/warp3d/` → `libwarp3d.so`（单应 warp + 4 点求解 + 3D 旋转投影）；前端 `warp3d/w3d`。

```bash
bash warp3d/build.sh
LD_LIBRARY_PATH=cpp/warp3d/build ./warp3d/w3d rotate IN.png OUT.png 45 0 0 800 800 200 200
python3 warp3d/difftest.py              # 4/4 仿射 vs cv2（±1）
```

`rotate`：yaw/pitch/roll(度) + 相机距离/焦距 → 透视投影后的图（伪 3D）。
`persp`：直接给 8 系数单应（dst→src，同 PIL `PERSPECTIVE`）。
强透视下与 cv2 有插值/边界差异（未逐位对齐）；仿射一致（±1）。

## upscale

| 模式 | 实现 | 适用 |
|---|---|---|
| `2x` | Scale2x/EPX（确定算法，保持硬边） | 像素画 / 线稿精灵 |
| `4x` / `esrgan` | Real-ESRGAN x4（ONNX，ORT 推理） | 低清插画 / 模糊帧 |

```bash
bash upscale/build.sh
LD_LIBRARY_PATH=cpp/upscale/build:cpp/sr ./upscale/up 2x IN.png OUT.png
LD_LIBRARY_PATH=cpp/upscale/build:cpp/sr ./upscale/up 4x IN.png OUT.png
python3 upscale/difftest.py             # Scale2x 20/20
```

模型 `/data/models/image/realesr-general-x4v3.onnx`（`SR_MODEL` 覆盖）。
`4x` 输出 RGB（alpha 丢失）；透明精灵先压白底，超分后再抠图/对齐。

## anim

`anim/` 是**游戏素材流水线**（只依赖 StaticPy + imgproc；`bgremove` 除外）。

| 工具 | 作用 | 用法 |
|---|---|---|
| `pose_walk` | 生成 OpenPose 走路骨架帧（含手部 21 点） | `OUTDIR=dir [LEGX/ARMX/YUP/HAND] pose_walk` |
| `pack_sprites` | 透明帧 → 精灵表 PNG + manifest.json | `pack_sprites OUT.png MANIFEST.json CROP_W CROP_H SRC_X SRC_Y CELL_W CELL_H COLS FLIP NAME f1.png …` |
| `frames_to_gif` | 帧序列 → 循环 GIF | `frames_to_gif OUT.gif FPS f1.png …` |
| `cutout` | 整张角色表 → 透明角色（洪泛去背景 + 连通块保留 + 填封闭洞） | `cutout IN.png OUTDIR [SIZE_TH]` |
| `sheet_align` | 透明精灵表按透明缝隙切 N 帧，按脚底对齐到统一画布 | `sheet_align IN.png OUTDIR COLS` |

```bash
bash imgproc/build_app.sh anim/pose_walk.static.py     anim/pose_walk
bash imgproc/build_app.sh anim/pack_sprites.static.py  anim/pack_sprites
bash imgproc/build_app.sh anim/frames_to_gif.static.py anim/frames_to_gif
bash imgproc/build_app.sh anim/cutout.static.py        anim/cutout
bash imgproc/build_app.sh anim/sheet_align.static.py   anim/sheet_align
export LD_LIBRARY_PATH=/opt/StaticPy/cpp/imgproc/build
```

端到端：生成帧/骨架 → 抠透明底（BiRefNet：`bash /opt/static_comfyui/cpp/sd/bgremove.sh in.png cut.png transparent`）
→ `pack_sprites` 打包（`FLIP=1` 出镜像朝向）→ `frames_to_gif` 预览。

`manifest.json`：

```json
{
  "name": "walk_left",
  "image": "knight_walk_left.png",
  "frameWidth": 180, "frameHeight": 240,
  "columns": 8, "rows": 2, "frameCount": 16,
  "animations": { "walk_left": { "from": 0, "to": 15, "fps": 8, "loop": true } }
}
```

## tools/ 推理工具

C++ 库 + ONNX Runtime，暴露 C ABI → StaticPy FFI 驱动。**只集成推理，不含训练**。
ORT 走系统库（`/usr/local/lib/libonnxruntime.so.1`，ldconfig 已注册，运行无需 `LD_LIBRARY_PATH`）。

| 命令 | 能力 | C 库 | 模型 |
|---|---|---|---|
| `detect` / `crop` / `parse` | 人脸检测 / 对齐裁剪 / 解析分割 | `libface.so` | SCRFD + BiSeNet |
| `remove` | 背景去除 / 抠图 | `libbirefnet.so` | BiRefNet（928M） |
| `ocr` | 文字识别 | `libocr.so` | PP-OCRv4 |
| `caption` | 图像反推 / 描述 | `libflorence2.so` | Florence-2 |
| `sr` | 高清放大 4x | `libsr.so` | Real-ESRGAN |
| `restore` | 人脸高清修复 | `libcodeformer.so` | CodeFormer |
| `color` | 上色 | `libcolorize.so` | DDColor |
| `pose` | 骨骼图（COCO-17） | `libpose.so` | YOLOv8-pose |
| `yolo` | 目标检测（80 类） | `libdet.so` | YOLOv8n |
| `depth` / `edge` | 深度图 / 软边缘（ControlNet） | `libannot.so` | Depth-Anything-V2-S / HED |

```bash
bash tools/build.sh
tools/run.sh detect  IN.png
tools/run.sh remove  IN.png OUT.png 0     # 0=透明 RGBA
tools/run.sh ocr     IN.png
tools/run.sh caption IN.png
```

模型路径在各 `*_capi.cpp` 有默认（多为 `/data/models/…`），可用 `BIREFNET_MODEL` /
`FLORENCE2_MODEL_DIR` / `SR_MODEL` 覆盖；`ORT_CUDA=1` 切 GPU。
注：`detect` 对卡通图返回空 `[]` 属正常（SCRFD 认真人脸）。

**可做但未接**（模型已就位）：`faceid`(`w600k_r50`)、`facelm`(`2d106det`/`1k3d68`)、
`faceswap`(`inswapper_128`)、`genderage`、`dwpose`、`vlm`(`Qwen*-VL`)、`imggen`（走 sd.cpp）、`seg`（待下模型）。

## luajit/ 同一份 C ABI

C ABI 是共享的运行时表面：同一份 `libimgproc.so` 被 StaticPy(FFI)、Python(ctypes)、LuaJIT(`ffi.C`) 共用。

```lua
local ffi = require("ffi")
local imgproc = ffi.load("libimgproc.so")
ffi.cdef[[ void* img_open(const char*); void* img_grayscale(void*); int img_save(void*, const char*); ]]
```

```bash
LD_LIBRARY_PATH=cpp/imgproc/build luajit luajit/example.lua IN.png OUT.png
bash luajit/embed-build.sh     # 把 LuaJIT + 运行时静态编进单文件 ELF → ./lua_app
./lua_app IN.png OUT.png       # 内嵌脚本用 ffi.C 直调进程内函数
```

`lua_app` **不含动态 luajit 依赖**；运行时函数经 `-rdynamic` 导出，Lua 侧零开销直调。

---

## ltorch（直吊 libTorch：ATen + autograd）

`cpp/torch/` → `libtorch_capi.so`（真 `at::Tensor`，不重写算子）；插件 `plugins/ltorch/`。

- **不重造算子**：绑定层只做「句柄 ⇄ 张量」翻译，数学全部落在 ATen/autograd 里，
  所以 matmul/softmax/backward 的数值与 PyTorch **逐位相同**（差分 max|Δ|=0）。
- **数据怎么过 FFI**：FFI 只有 `str/int/float/ptr`，故
  - 张量 = **integer-64 句柄**（不是 `void*`：StaticPy 侧统一按 int 走，`ltorch.free` 归还）；
  - 值/形状 = **CSV 字符串**（`"1.0,2.0,3.0,4.0"` + `"2,2"`），读回同样 CSV。
- **C ABI**（`torch_capi.h`）：`from_csv/to_csv/shape_csv/numel/ndim`、`zeros/ones/full/randn/arange`、
  `add/sub/mul/div/matmul`、`add_scalar/mul_scalar`、`relu/sigmoid/tanh/softmax(dim)`、
  `sum/mean/sum_dim`、`reshape/transpose/clone/detach`、`set_requires_grad/requires_grad/backward/grad/zero_grad`、
  `item/version/last_error/free`。失败一律置 `last_error` 并返回 `0`（不抛异常越 ABI 边界）。
- **版本**：本机 `/opt/libtorch` = **2.1.2**；Python 的 `torch` 可能是别的版本，
  差分只比**确定性算子**，`randn` 只比形状（随机流跨版本不保证一致）。

```bash
bash cpp/torch/build.sh                          # → cpp/torch/build/libtorch_capi.so（带 rpath）
STATICPY_PLUGINS=core,ltorch bash staticpy/static_build.sh plugins/ltorch/demo.static.py ltdemo
LD_LIBRARY_PATH=/opt/libtorch/lib ./dist/ltdemo   # 不打 rpath 的实现需要这句；本仓 .so 已内嵌 rpath
python3 plugins/ltorch/difftest.py --elf          # 差分 19/19（含 ELF 端到端）
```

- **两侧必须分进程**：pip 的 torch 与 `/opt/libtorch` 的 `c10` 符号互不兼容，
  同一进程里先 dlopen 我们这侧再 `import torch` 会炸（`libshm.so: undefined symbol`）；
  `difftest.py` 因此起两个子进程各算一遍、只比 JSON。
- 插件开关是 `plugins/ltorch/plugin.json` 的 `libs.torchc`；不启用插件时零依赖、零运行时开销。

---

## 能力边界（明确不做）

- **训练调度**：不做（`ltorch` 只提供 `at::Tensor` 与 autograd 求导，优化器/训练循环留给用户程序；这层不管推理与算法之外的东西）。
- **重型扩散/视频生成**：走 `sd.cpp` + `comfycli`（`/opt/static_comfyui/anim.sh`，零 torch），不塞进本仓。
- **Python 运行时**：产物不依赖；Python/Pillow/numpy 只用于测量与导模型。
