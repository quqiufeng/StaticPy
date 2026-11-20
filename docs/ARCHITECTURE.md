# ARCHITECTURE —— 从 `.static.py` 到独立 ELF

> 一条流水线、两个入口（`kernel/` 新入口，`staticpy/static_build_comfycli.sh` 兼容入口），
> 产物只是一个**独立 ELF + 它显式挂的 `.so`**。

## 1. 流水线

```
app.static.py
   │  ① 翻译       staticpy/static_translate.py（**种子**，冻结的验收基准）
   │               或 自举翻译器 ELF（staticpy/*.static.py 编出来，演化面）
   │               extern fn 抽取 → token 流 → AST → 类型检查 → Scheme S-表达式
   ▼
   │  ② 拼装       kernel/bundle.py
   │               插件 runtime.scm + 插件 ffi.scm + 用户 -f FFI + 翻译产物
   │               （(load-shared-object …) 全局去重）
   ▼
bundle.ss ── ③ Chez AOT ──► <stem>.so
   │        kernel/toolchain.py: compile-file
   │  ④ 链接
   │        Chez boot 文件 objcopy 成 .o + C launcher（初始化堆 → 调 entry）
   ▼
./<stem>      独立 ELF（Chez 运行时已静态嵌入）   ./<stem>.so  AOT 编译产物
```

- **不依赖 Python**：Python 只在①出现，且只在**种子**那条路上出现；自举翻译器是 ELF，
  产物里没有任何解释器。**①的两条路必须给出同一份 IR**（`staticpy/check_translate.sh`），
  细节与现状见 [SELFHOST.md](./SELFHOST.md)。
- **运行时依赖只有 `.so`**：产物用 `load-shared-object` 在启动时挂（`libimgproc.so`、`libgif.so.7`…），
  解析路径靠 `LD_LIBRARY_PATH` 或 soname；打包时一并收进部署包（见 [DEPLOY.md](./DEPLOY.md)）。
- **确定性 + 缓存**：bundle 的输入文件列表做 hash 作缓存键，命中则跳过 AOT。
  缓存目录 `~/.iso_gen/staticpy-cache`（可用 `STATICPY_CACHE` 覆盖）。
  **本项目约定：临时文件一律写 `~/iso_gen/`，不用 `/tmp`。**

## 2. 两个入口

```bash
# 新入口（推荐）：插件化内核
python3 -m kernel check app.static.py            # 只翻译成 Scheme（调试）
python3 -m kernel build app.static.py -o app     # 出 ELF
python3 -m kernel run   app.static.py -- a b     # 构建并立刻运行
python3 -m kernel plugins                        # 列出插件与依赖

# 兼容入口：等价于「一次性拼上 legacy 全集」的内置插件集
bash staticpy/static_build_comfycli.sh app.static.py app [extra_ffi.scm]
bash staticpy/static_build.sh ...                # 别名（转发，单一真源）
```

`kernel` 是唯一权威实现（`kernel/cli.py` 解析参数、`kernel/plugin.py` 发现与拓扑排序、
`kernel/bundle.py` 拼装、`kernel/toolchain.py` 调 Chez 与链接）；兼容入口只是把
「legacy 插件全集」喂给同一套流程，行为与拆分插件前一致。

产物落点：带路径前缀的输出名沿用原语义（`imgproc/pil` → `imgproc/pil`），
裸名进 `dist/`（`STATICPY_OUTDIR` 可覆盖）。

## 3. 内核与插件

```
kernel/  只做四件事：发现插件 → 解依赖（拓扑排序）→ 拼 bundle → 调 Chez
plugins/*/  一切能力都是插件：
  runtime.scm   Scheme 侧运行时（拼在产物前面）
  ffi.scm       load-shared-object / 常量 / 手写绑定（拼在 runtime 之前）
  hooks.py      Python 语法扩展（ast 钩子）
  plugin.json   清单：requires / order / libs / modules / return_types / prelude_functions / build
```

插件选择优先级：`-p/--plugin` > `STATICPY_PLUGINS` > 按源码 `import` 自动推断 > `core`。
细节见 **[PLUGINS.md](./PLUGINS.md)**。

## 4. 前端 / 核心 / 库的分层（以 imgproc 为样板）

| 层 | 位置 | 职责 |
|---|---|---|
| C/C++ 核心 | `cpp/<lib>/*.cpp` → `lib<lib>.so` | 重活：编解码、卷积、数值路径（对标参照实现的 C 核） |
| FFI 声明 | `<lib>_ffi.scm` 或插件的 `ffi.scm` | 只 `load-shared-object`；`foreign-procedure` 由 `extern fn` 自动生成 |
| 前端 | `*.static.py` | 编排逻辑；纯函数库（无 `main`）+ 薄 CLI |
| 验证 | `difftest.py` / `<lib>_surface.py` | 差分与自省（ctypes 直连 `.so`，迭代快；生产仍走 ELF） |

C ABI 是**稳定面**：同一份 `lib<lib>.so` 被 StaticPy ELF、Python `ctypes`、LuaJIT `ffi.C` 共用。

## 5. 环境与变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `CHEZ_SCHEME_DIR` | `/opt/ChezScheme/ta6le` | Chez 构建树 |
| `CHEZ_SCHEME` | `$CHEZ_SCHEME_DIR/bin/ta6le/scheme` | scheme 可执行文件 |
| `CHEZ_BOOT_DIR` | `/opt/ChezScheme/boot/ta6le` | boot 文件（obcopy 进产物） |
| `STATICPY_CACHE` | `~/iso_gen/staticpy-cache` | AOT 缓存目录 |
| `STATICPY_OUTDIR` | `dist/` | 裸名产物的落点 |
| `STATICPY_PLUGINS` / `STATICPY_PLUGINS_PATH` | — | 插件选择 / 额外插件搜索路径 |
| `STATICPY_LIB_<LIB>` | — | 覆盖某个逻辑库的 soname（如 `STATICPY_LIB_OPENBLAS`） |
| `GLIBC_SYSROOT` | 空 | 目标 glibc sysroot，用于兼容老发行版 |
| `ORT_DIR` / `ORT_CUDA` | `/data/venv/onnxruntime-linux-x64-gpu-1.26.0` / 0 | ONNX Runtime 目录与 GPU 开关 |

构建依赖：`g++`、`pkg-config`、Chez Scheme；`python3` 仅翻译器需要（只用标准库）。

## 6. 关键命令速查

```bash
bash imgproc/build.sh                       # libimgproc.so + pil / concat / mirror_gif
bash imgproc/build_app.sh app.static.py app  # 用 pil_lib 编用户程序（concat 自举拼接）
bash imgproc/package.sh imgproc/pil pil      # 自包含部署包 → dist/pil{,.tar.gz}
bash tools/build.sh                          # ONNX 推理工具（tools/run.sh <op> …）
bash selfcheck.sh                            # 构建 + 差分 + 覆盖 + 插件钩子 + 自举比对

# 改翻译器之后（四层差分；check_parse/check_translate 不在 selfcheck 里，必须手跑）
bash staticpy/check_tokenize.sh <file…>      # token 流 vs CPython tokenize
bash staticpy/check_parse.sh    <file…>      # AST dump vs CPython ast
bash staticpy/check_translate.sh <file…>     # IR vs 种子
python3 staticpy/semantics_diff.py           # CPython 输出 vs AOT ELF 输出
```
