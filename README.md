# StaticPy

**Python 语法 → Scheme(Cchez) IR → AOT 机器码**，产物是独立 ELF/`.so`；
需要什么能力就**运行时挂 C 库**（FFI），**不依赖 Python 解释器 / pip / venv**。

> 定位：把 Python 的**表达力**接到**原生后端**上——不是重造语言，而是把成熟的
> 前端（Python 语法）、后端（Chez Scheme）、原生能力（C 库）对齐成一套**给 AI agent 用的约定**。

## 目录

```
staticpy/                # 语言工具链
├── static_translate.py    # Python → Scheme 翻译器（含本地补丁：is None / break-continue /
│                          #   模块级变量 / 顶层语句 / float ABI / lambda+一等函数）
├── static_prelude.scm     # 运行时值类型
├── static_stdlib.scm      # 标准库
├── static_build.sh        # 上游构建脚本
└── static_build_comfycli.sh  # 本项目构建脚本（translate + Chez AOT + 独立 ELF）

imgproc/                 # 「StaticPy 版 Pillow」——图像处理库（本轮迁移样板）
├── pil_lib.static.py      # 库（纯函数，可被集成；lambda/一等函数）
├── pil_cli.static.py      # pil CLI 分发
├── pilcli.static.py       # 早期 CLI
├── mirror_gif.static.py   # 示例算子
├── concat.static.py       # 构建工具（自举：用 StaticPy 写）
├── build.sh / build_app.sh
├── pyimgproc.py           # libimgproc.so 的 ctypes 绑定（差分测试用）
├── pil_surface.py         # 自省 Pillow API → 清单
├── frontend_coverage.py   # 自省清单核对覆盖面
├── difftest.py            # 自动化差分测试：PIL vs 我们，逐像素
├── README.md / MIGRATION.md / pil_api.md
└── examples/

cpp/imgproc/             # C++ 底层库 libimgproc.so（对标 Pillow libImaging）
├── core.cpp geom.cpp color.cpp ops.cpp filters.cpp draw.cpp
├── effects.cpp quant.cpp lut.cpp
├── imgproc.h imgproc_internal.h
├── build_cpp.sh
└── thirdparty/{giflib,stb}
```

## 三条"补齐运行时"的路径

1. **有现成 C 库** → 运行时挂 `.so`（`libgif/libwebp/libtiff/libfreetype`）
2. **没有** → 自写 **C++ helper**（`libimgproc.so`）
3. **语法不够兼容 Python** → **改编译器**（对齐 Scheme IR）—— 已加 lambda/一等函数

## 构建 / 运行

```bash
bash imgproc/build.sh                 # C++ 库 + StaticPy ELF（pil/mirror_gif 等）
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/pil convert IN.png OUT.png L

bash imgproc/build_app.sh my_app.static.py my_app   # 用 pil_lib 构建用户程序
```

## 部署（强分发 / 自包含）

产物可打成**自包含目录**：把 ELF + 它用到的**全部 `.so`（含传递依赖）**一起放进包里，
配一个设 `LD_LIBRARY_PATH=$DIR/lib` 的启动器。**目标服务器零要求**——不需要 Python、
不需要 pip、不需要任何预装库；`scp` 过去 `./run` 即可。

```
mypkg/
├── <name>        # 启动器（设 LD_LIBRARY_PATH 后 exec app）
├── app           # StaticPy ELF（Chez 运行时已静态嵌入）
└── lib/          # libimgproc.so + libgif/libwebp/libtiff/libfreetype + 传递依赖
```

```bash
bash imgproc/package.sh imgproc/pil pil        # -> dist/pil/ 与 dist/pil.tar.gz
```

**唯一不可再拆的两样（且都可控）**：① Linux 内核 + x86-64 架构；② glibc 版本下限
（用老 glibc 的 `GLIBC_SYSROOT` 构建即可覆盖新老发行版）。其余**全在包里**。

> 对比 Go：产物同样是静态单文件；这里是「Python 语法 + 运行时 FFI 任意 C 库」，
> 交付模型（compile once → copy → run）等价，且宿主不需要任何前置条件。

## 验证（自动化）

```bash
/data/venv/bin/python imgproc/pil_surface.py > imgproc/pil_api.md   # 自省清单
/data/venv/bin/python imgproc/frontend_coverage.py                  # 覆盖面
/data/venv/bin/python imgproc/difftest.py -v                        # 差分测试（逐像素）
```

当前：**PIL 覆盖面 100/100**；差分测试 **100/100**（多数逐像素 max=0）。
方法与经验见 `imgproc/MIGRATION.md`。

## 依赖

- 构建：`g++`、`Chez Scheme`（`/opt/ChezScheme/ta6le`）、`pkg-config freetype2`
- 运行时：`libgif.so.7`、`libwebp.so.7`、`libtiff.so.6`、`libfreetype.so.6`
- 验证脚本：`/data/venv`（Pillow/numpy，仅用于"测量"对照）
