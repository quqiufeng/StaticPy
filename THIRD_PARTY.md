# 第三方组件与归属（THIRD PARTY NOTICES）

本仓库的 `imgproc` 是**对照 Pillow 的公开源码**做的独立重实现（differential-tested），
并 vendored 了若干单头库 / 头文件。为合规，列明来源与许可，保留原始版权与许可文本。

## 对照实现（按其公开源码逐行对齐数值行为，非链接）

| 项目 | 用途 | 许可 |
|---|---|---|
| **Pillow** (python-pillow/Pillow) | `imgproc` 对标其 API 与 C 实现（Filter/Resample/BoxBlur/Quant*/ColorLUT/Palette/Convert/Chops/ImageOps…） | **MIT-CMU / HISTORICAL**（见 Pillow 仓库 `LICENSE`）。本仓库为**独立重实现**，非 Pillow 源码拷贝；算法行为对齐仅为兼容性目的。 |

> 若对外分发，建议随包附带 Pillow 的 LICENSE 与版权声明。

## vendored 源码（直接拷贝进仓库）

| 组件 | 位置 | 许可 |
|---|---|---|
| **giflib** `gif_lib.h` | `cpp/imgproc/thirdparty/giflib/` | MIT |
| **stb_image / stb_image_write / stb_truetype** | `cpp/imgproc/thirdparty/stb/` | Public Domain / MIT |

## 运行时动态库（不随仓库分发，运行时按需加载）

`libgif.so.7`、`libwebp.so.7`、`libtiff.so.6`、`libfreetype.so.6` 及各发行版自带许可。
打包（`imgproc/package.sh`）时若把它们 vendored 进部署包，请一并附其许可。

## 工具链与上游

| 项目 | 说明 | 许可 |
|---|---|---|
| **Chez Scheme** | AOT 后端 / 运行时（`libkernel.a` + boot 文件静态嵌入产物） | Apache-2.0 |
| **StaticPy / ReScheme** (quqiufeng/ReScheme) | 语言工具链与自举代码的来源 | 见上游仓库 |

## 说明

- `selfhost/` 下的 `BOOTSTRAP.md`、`staticc.py`、`staticc.sp` 等来自上游 `ReScheme`，用于展示自举与信任链。
- 本仓库对第三方代码仅做**引用/对照**；未改变其许可状态。
