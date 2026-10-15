# 工具链 / 构建环境

## 需要什么

| 类别 | 组件 | 说明 |
|---|---|---|
| 编译器后端 | **Chez Scheme** | AOT 编译 Scheme → 机器码；运行时（`libkernel.a`+boot）静态嵌入产物。期望布局 `/opt/ChezScheme/ta6le/{bin,boot,lz4,zlib}`（可用 `CHEZ_SCHEME_DIR` 覆盖） |
| C/C++ | `g++`、`pkg-config` | 编译 C++ helper（`libimgproc.so`） |
| Python | `python3`（仅翻译器） | `static_translate.py`：Python → Scheme（只用标准库） |
| 头/库（按需） | `libgif-dev` `libwebp-dev` `libtiff-dev` `libfreetype6-dev` | imgproc 的编解码/文字 |
| 测量侧（不进产物） | `pillow` `numpy` | 仅差分测试/自省对照 |

## 一键环境（推荐）

```bash
docker build -t staticpy .
docker run --rm -v $PWD:/w -w /w staticpy bash selfcheck.sh
```

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `CHEZ_SCHEME_DIR` | `/opt/ChezScheme/ta6le` | Chez 构建树 |
| `CHEZ_BOOT_DIR` | `/opt/ChezScheme/boot/ta6le` | boot 文件 |
| `STATICPY_PYTHON` | `python3` | 翻译器解释器 |
| `STATICPY_STDLIB` | `static_stdlib.scm` | 标准库（默认精简；`static_stdlib_full.scm` 为全量扩展） |
| `GLIBC_SYSROOT` | （空） | 目标 glibc sysroot，用于兼容老发行版 |
| `IMGPROC_SO` | 仓库内 `cpp/imgproc/build/libimgproc.so` | 运行时库路径 |

## 图像/视觉工具（tools/，推理）

**ORT 走系统库**（`/usr/local/lib/libonnxruntime.so.1`，ldconfig 已注册，运行时无需 `LD_LIBRARY_PATH`；编译只需头 `ORT_INC`）+ 模型路径
（各 `cpp/*/*_capi.cpp` 内有默认，如 `/data/models/...`，可用 `BIREFNET_MODEL`/`FLORENCE2_MODEL_DIR` 覆盖）。
构建 `bash tools/build.sh`；运行 `tools/run.sh <op> ...`。
含：face（人脸）、birefnet（背景去除/扣图）、ocr、florence2（图像反推）、**sr（Real-ESRGAN 高清放大 4x）**。
`ORT_CUDA=1` 可切 GPU（默认 CPU）；TensorRT provider 亦随系统 ORT 就绪。

## 产物

- `imgproc/build.sh` → `cpp/imgproc/build/libimgproc.so` + `imgproc/{pil,pilcli,mirror_gif}` + `concat`
- `imgproc/build_app.sh USER.static.py OUT` → 用 `pil_lib` 构建用户程序
- `imgproc/package.sh APP NAME` → 自包含部署包 `dist/NAME{,.tar.gz}`
- `selfcheck.sh` → 构建 + 差分 + 覆盖 + 自举 自检
