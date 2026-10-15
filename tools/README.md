# tools —— 图像/视觉工具（推理）集成

把 `static_comfyui` 里的**推理工具**接入本仓（**只集成推理，不含训练**）。
它们都是 **C++ 库 + ONNX Runtime**，各自暴露 C ABI → StaticPy 用 FFI 驱动。

| 命令 | 能力 | C 库 | 模型 |
|---|---|---|---|
| `detect` | 人脸检测（SCRFD） | `libface.so` | `det_10g.onnx` |
| `crop` | 检测最大脸→对齐裁剪 | `libface.so` | 同上 |
| `parse` | 人脸解析（BiSeNet 分割） | `libface.so` | `faceparser.onnx` |
| `remove` | **背景去除 / 扣图**（BiRefNet） | `libbirefnet.so` | `/data/models/birefnet` |
| `ocr` | 文字识别（PP-OCRv4） | `libocr.so` | `dist/ocr/*.onnx` |
| `caption` | **图像反推**（Florence-2 描述） | `libflorence2.so` | `/data/models/florence2` |
| `sr` | **高清放大 4x**（Real-ESRGAN） | `libsr.so` | `/data/models/image/realesr-general-x4v3.onnx` |
| `restore` | **人脸高清修复**（CodeFormer） | `libcodeformer.so` | `/data/models/image/codeformer.onnx` |
| `color` | **上色**（DDColor） | `libcolorize.so` | `/data/models/image/ddcolor-fp16.onnx` |

## 构建 / 运行

```bash
bash tools/build.sh                       # 编 C 库 + StaticPy ELF
# 运行时需能解析 ORT 与各 .so（见 tools/run.sh）
tools/run.sh detect  IN.png
tools/run.sh remove  IN.png OUT.png 0     # 0=透明 RGBA
tools/run.sh ocr     IN.png
tools/run.sh caption IN.png
```

## 依赖（环境变量，见 ../toolchain.md）

- `ORT_DIR`：ONNX Runtime 目录（含 `include/`、`lib/`），默认 `/data/venv/onnxruntime-linux-x64-gpu-1.26.0`
- 模型路径各 `*_capi.cpp` 有默认（多为 `/data/models/...`），可用 `BIREFNET_MODEL` / `FLORENCE2_MODEL_DIR` 等覆盖

## 状态（实测）

- ✅ `ocr` / `caption` / `remove` 在样例图上正常出结果
- ⚠️ `detect` 返回合法 JSON；样例 `example.png` 是**卡通角色**（SCRFD 认真人脸），故为空 `[]`
- 说明：本目录**只有推理路径**（`*_capi.cpp` / `*cpp`），未包含任何训练代码
