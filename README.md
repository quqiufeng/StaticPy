# StaticPy

> **一个小 Python 子集 + 一个用 C ABI 拼起来的生态；可自举、可审计，因而可信任。**
> **A small Python subset with an ecosystem assembled over a plain C ABI — self-hosting and auditable, hence trustworthy.**

**Python 语法 → Scheme（Chez）IR → AOT 机器码**，产物是独立 ELF / `.so`；
需要什么能力就**运行时挂 C 库**（FFI），**不依赖 Python 解释器 / pip / venv**。

> 定位：把 Python 的**表达力**接到**原生后端**上——不重造语言，而是把成熟的
> 前端（Python 语法）、后端（Chez Scheme）、原生能力（C 库）对齐成一套**给 AI agent 用的约定**。

---

## 30 秒上手

```bash
# 1) 一个程序
cat > app.static.py <<'EOF'
def main() -> int:
    print("hello staticpy")
    return 0
EOF

# 2) 构建并运行（自动推断插件：只有 core/libc）
staticpy run app.static.py          # -> hello staticpy

# 3) 产出的独立 ELF（拷走即可跑，无需 Python）
staticpy build app.static.py -o hello
./hello
```

**整条构建链都不依赖 CPython**（已自举，见 [docs/SELFHOST.md](docs/SELFHOST.md) §7.5）：
`dist/translator` 是把 `staticpy/{static_translate,parse_lib,emit_lib,emit_dump}.static.py`
concat 后编成的 ELF 翻译器，出 IR 就直接喂给兼容入口的 `.scm` 通道：

```bash
./dist/translator app.static.py > ~/iso_gen/app.code.scm
bash staticpy/static_build.sh ~/iso_gen/app.code.scm app    # 无 CPython
./app
```

CPython 只在两处还留着：**起爆翻译器那一次**（`staticpy build … -o dist/translator`，之后
自持；`dist/` 是构建产物、不入库），以及**验收/差分**（`check_*`、`semantics_diff`、`difftest`、
`frontend_coverage` 拿 CPython / 原库当**对照物**，不进产物链路）。
更省事的一条：直接 `staticpy build app.static.py -o app`——没有 python3 时它会自动走上面这条无 CPython 通道。

图像能力（对标 Pillow 的 `imgproc` 样板）：

```bash
bash imgproc/build.sh                                    # libimgproc.so + pil/concat/mirror_gif
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build \
  ./imgproc/pil convert IN.png OUT.png L
```

验证（机器判据）：

```bash
# 下面两条用 CPython + 原库当「对照物」（测量，不进产物；staticpy 不负责原库自省）
python3 imgproc/difftest.py -v     # 差分测试：Pillow vs 我们，逐像素 —— 当前 100/100（maxΔ=0）
python3 imgproc/frontend_coverage.py # 覆盖面：自省核对 —— 当前 100/100
bash selfcheck.sh                  # 全量自检：构建 + 差分 + 覆盖 + 插件钩子 + 自举比对
```

---

## 文档地图

只读你想读的那一篇；**根目录不再堆散文档**。

| 文档 | 回答的问题 |
|---|---|
| **[VISION.md](./VISION.md)** | 为什么"语言是耗材、约定才是资产"；人在这个模型里拥有什么 |
| **[AGENTS.md](./AGENTS.md)** | **agent 作业手册**：把 Python 库迁到 StaticPy 的可复制步骤与踩坑表 |
| **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** | 编译器/内核/插件/AOT 的流水线、产物落点、缓存与环境变量 |
| **[docs/LANGUAGE.md](./docs/LANGUAGE.md)** | Python 子集支持什么、类型系统、FFI 约定（`extern fn`）、种子边界与"改语法"路径 |
| **[docs/PLUGINS.md](./docs/PLUGINS.md)** | 插件规范：`plugin.json` 字段、三种形态、语法钩子、CLI |
| **[docs/LIBS.md](./docs/LIBS.md)** | 已集成的库与推理工具清单（含每个库的构建/运行/验证命令） |
| **[docs/MIGRATION.md](./docs/MIGRATION.md)** | 迁移方法论：自省 → 铺桩 → 差分，以及"照抄 C 源"的坑表 |
| **[docs/SELFHOST.md](./docs/SELFHOST.md)** | 三环自举与信任链：种子冻结约定、四层机器验收、怎么复现 |
| **[docs/DEPLOY.md](./docs/DEPLOY.md)** | 强分发：自包含部署包（零依赖）与 glibc 下限 |
| **[docs/THIRD_PARTY.md](./docs/THIRD_PARTY.md)** | 第三方组件、许可与归属 |
| **[imgproc/README.md](./imgproc/README.md)** | 旗杆样板（对标 Pillow）：三层结构、覆盖面、怎么扩算子 |

---

## 仓库结构

```
staticpy/          # 语言工具链
├── static_translate.py    # 引导种子：冻结的参考翻译器（验收基准，见 docs/SELFHOST.md）
├── *.static.py            # 自举翻译器本体（tokenize/parse/emit），日常改语言改这里
├── static_prelude.scm     # 运行时值类型；static_stdlib.scm 标准库
├── static_build.sh        # 构建入口（translate + Chez AOT + 独立 ELF，单一真源）
└── static_build_comfycli.sh  # 历史名（上游带出来的），仅转发到 static_build.sh

kernel/            # 插件化内核：发现插件 → 拓扑排序 → 拼 bundle → 调 Chez
plugins/           # 一切能力都是插件（core/libc/math/json/http/imgproc/torch/…）
cpp/               # 各库的 C/C++ 核心（libimgproc.so、libatlas.so、…）
imgproc/ anim/ atlas/ font/ cvops/ easing/ pathfind/ upscale/ warp3d/ zlib/ hashlib/
                   # 每个目录 = 一个库的前端（.static.py + ffi.scm + difftest.py）
tools/             # ONNX 推理工具前端（detect/ocr/remove/sr/pose/…）
selfhost/          # 自举代码与信任根（staticc.py / staticc.sp）
luajit/            # 同一份 C ABI 的 LuaJIT 绑定与单文件 ELF 嵌入
docs/              # 本仓文档
```

---

## 三条"补齐运行时"的路径

1. **有现成 C 库** → 运行时挂 `.so`（`libgif` / `libwebp` / `libtiff` / `libfreetype` / `libcrypto`）
2. **没有现成的** → 自写 **C/C++ helper**（如 `libimgproc.so`、`libatlas.so`）
3. **语法不够兼容 Python** → **改自举翻译器**（`staticpy/*.static.py`），对齐 Scheme IR（如 lambda / 一等函数）；种子只作验收基准

> 判据只有一条：**产出的 Scheme IR / 数值对不对**；对不齐就照参照实现（如 Pillow 的 C 源）逐行搬。

## 依赖

- 构建：`g++`、`Chez Scheme`（默认 `/opt/ChezScheme/ta6le`，可用 `CHEZ_SCHEME_DIR` 覆盖）、`pkg-config freetype2`
- 运行：`libgif.so.7`、`libwebp.so.7`、`libtiff.so.6`、`libfreetype.so.6`（按库按需；打包时一并收进部署包）
- 测量侧（**不进产物**）：任一装了 Pillow/numpy 的 Python，仅用于差分测试与 API 自省
- 一键环境：`docker build -t staticpy . && docker run --rm -v $PWD:/w -w /w staticpy bash selfcheck.sh`

## 原理一句话

**广度**用 Python 自省一键枚举；**深度**靠照抄目标库的 C 源；**判据**交给自动化差分；
**缺什么补什么**——挂 `.so` / 写 C++ helper / 改编译器。人（或 agent）只做两件事：
**读源对齐** + **改实现**，然后重跑差分到全绿。
