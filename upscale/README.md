# upscale —— 图像放大（2x 像素画 / 4x Real-ESRGAN）

两种模式，按素材类型选：

| 模式 | 实现 | 适用 |
|---|---|---|
| `2x` | Scale2x/EPX（确定算法，保持硬边） | 像素画 / 线稿精灵 |
| `4x` / `esrgan` | **Real-ESRGAN x4（ONNX 模型）** | 低清插画 / 模糊帧 |

- **C 核心**：`../cpp/upscale/` → `libupscale.so`（Scale2x）；`../cpp/sr/` → `libsr.so`（Real-ESRGAN，ORT）
- **FFI / 前端**：`upscale_ffi.scm` 加载两个库 + `up.static.py` → `up` ELF
- **模型**：`/data/models/image/realesr-general-x4v3.onnx`（可用 `SR_MODEL` 覆盖）
- **验证**：Scale2x `difftest.py` **20/20**；`4x` 用假模型路径会直接报 ORT 加载失败，确认真的走模型

```bash
bash upscale/build.sh

# 像素画：保持硬边
LD_LIBRARY_PATH=cpp/upscale/build:cpp/sr ./upscale/up 2x  IN.png OUT.png

# 照片/插画：Real-ESRGAN 模型 4x
LD_LIBRARY_PATH=cpp/upscale/build:cpp/sr ./upscale/up 4x IN.png OUT.png

python3 upscale/difftest.py
```

> `4x` 输出 RGB（alpha 丢失）；透明精灵请先压白底，超分后再抠图/对齐。
