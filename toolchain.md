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

## 产物

- `imgproc/build.sh` → `cpp/imgproc/build/libimgproc.so` + `imgproc/{pil,pilcli,mirror_gif}` + `concat`
- `imgproc/build_app.sh USER.static.py OUT` → 用 `pil_lib` 构建用户程序
- `imgproc/package.sh APP NAME` → 自包含部署包 `dist/NAME{,.tar.gz}`
- `selfcheck.sh` → 构建 + 差分 + 覆盖 + 自举 自检
