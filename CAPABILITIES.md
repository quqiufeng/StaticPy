# CAPABILITIES —— 能力 / 工具清单（复盘）

> 本仓定位：**工具级的封装集成**（算法库 + 单模型 ONNX 推理工具 + 游戏工具）。
> 统一模式：**C ABI（`.so`）+ StaticPy FFI + 可选 ORT** → 产物自包含、多前端（StaticPy / LuaJIT / Python）共用。
> 重型训练 / 扩散管线**不在此**（走各自 C++ 后端，如 `sd.cpp` + `comfycli`）。

---

## 1. 已集成库（自实现 + 差分验证）

| 库 | 能力 | 验证 |
|---|---|---|
| `imgproc` | Pillow（GIF/PNG/JPEG/BMP/TGA/WebP/TIFF、几何、滤镜、文字(FreeType)、调色板、量化、伪3D…） | 差分 **100/100**；覆盖 **100/100** |
| `hashlib` | md5/sha1/sha224/256/384/512 摘要 | **6/6** 逐字节 |
| `zlib` | compress/decompress/gzip/crc32/adler32 | **5/5** 逐字节 |
| `pathfind` | 网格 A*（四/八邻，不切角） | **60/60** vs networkx |
| `atlas` | 精灵图集打包（MaxRects） | **60/60** 不变量 |
| `cvops` | 形态学/Otsu/Sobel/双边去噪 | **6/6** vs OpenCV |
| `font` | TTF → 字形图集 + 度量（FreeType） | **15/15** vs PIL |
| `easing` | 25 条缓动曲线（Penner） | **525/525** 双实现 |
| `warp3d` | 2D 图像 3D 旋转 / 透视（伪 3D） | **4/4** vs cv2（仿射） |
| `upscale` | 像素画高清放大（Scale2x） | **20/20** 双实现 |

## 2. 已集成工具（C++ + ONNX Runtime 推理）

| 命令 | 能力 | 模型 | 大小 |
|---|---|---|---|
| `detect`/`crop`/`parse` | 人脸检测 / 对齐裁剪 / 解析分割 | SCRFD + BiSeNet | 16M / 51M |
| `remove` | 背景去除 / 抠图 | BiRefNet | 928M |
| `ocr` | 文字识别 | PP-OCRv4 | 15M |
| `caption` | 图像反推 / 描述 | Florence-2 | ~1.1G |
| `sr` | 高清放大 4x | Real-ESRGAN | 4.7M |
| `restore` | 人脸高清修复 | CodeFormer | 360M |
| `color` | 上色 | DDColor | 108M |
| `pose` | **骨骼图**（COCO-17 骨架） | YOLOv8-pose | 13M |
| `yolo` | 目标检测（80 类） | YOLOv8n | 13M |
| `depth` | **深度图**（ControlNet） | Depth-Anything-V2-S | — |
| `edge` | **软边缘**（ControlNet） | HED | — |
| `line` 直线(备选) | `annotators/mlsd.onnx` | 需 4ch 输入/9ch 输出解码 |

用法：`bash tools/build.sh` → `tools/run.sh <op> ...`（ORT 走系统 `/usr/local/lib`，无需 `LD_LIBRARY_PATH`）。

## 3. 可做工具（模型已就位，随时按 `tools/` 方式接入）

| 候选工具 | 模型（`/data/models/image/…`） | 用途 |
|---|---|---|
| `faceid` 人脸特征 | `w600k_r50.onnx`（ArcFace） | 人脸识别 / 比对 |
| `facelm` 关键点/3D | `2d106det.onnx` / `1k3d68.onnx` | 五官点 / 3D 头模 |
| `faceswap` 换脸 | `inswapper_128.onnx` | 换脸 |
| `genderage` 性别年龄 | `genderage.onnx` | 属性 |
| `dwpose` 姿态(备选) | `dwpose/{yolox_l,dw-ll_ucoco_384}.onnx` | 高精度骨架 |
| `sr2x` 放大(备选) | `2x_ESRGAN.gguf` | 走 sd.cpp |
| `vlm` 视觉问答 | `Qwen3VL-8B-*.gguf` / `Qwen2.5-VL-3B-*.gguf` | 图像理解（llama.cpp）|
| `imggen` 生图 | `z_image_turbo-*.gguf` / `qwen-image-*.gguf` | 走 sd.cpp |
| `seg` 分割 | 需下（U2Net/SAM） | 前景/通用分割 |

## 4. 游戏相关能力（iso_flutter）

| 需求 | 用哪个 |
|---|---|
| 素材处理 | `imgproc`（编解码/几何/抠图/合成/量化）+ `atlas`（图集）+ `font`（字体图集）+ `upscale`（放大） |
| 精灵行走骨骼 | `tools pose`（COCO-17 骨架 → 接 ControlNet 管线） |
| NPC 寻路 | `pathfind`（A*） |
| 2D 动效 | `easing`（缓动/补间） |
| 伪 3D 转动（卡片/金币） | `warp3d`（3D 旋转 / 透视） |
| 图像增强 | `cvops`（形态学/阈值/去噪）+ `tools sr/restore/color` |
| 压缩/校验 | `zlib` / `hashlib` |

## 5. 能力边界（明确不做）

- **训练**：不做（这层只管推理与算法）。
- **重型扩散/视频生成**：走 `sd.cpp` + `comfycli`（`/opt/static_comfyui/anim.sh`，零 torch），不塞进本仓。
- **Python 运行时**：产物不依赖（测量/导模型时才用 Python/Pillow/ultralytics）。

## 6. 复现 / 自检

```bash
bash selfcheck.sh          # 构建 + 各库差分 + 自举比对
bash imgproc/package.sh imgproc/pil pil   # 零依赖部署包
```
