# DEPLOY —— 强分发（自包含产物）

> 交付模型：**compile once → copy → run**。目标服务器零要求——不需要 Python、不需要 pip、
> 不需要任何预装库；`scp` 过去 `./run` 即可。

## 1. 部署包结构

```
mypkg/
├── <name>        # 启动器（设 LD_LIBRARY_PATH=$DIR/lib 后 exec app）
├── app           # StaticPy ELF（Chez 运行时已静态嵌入）
└── lib/          # libimgproc.so + libgif/libwebp/libtiff/libfreetype + 全部传递依赖
```

```bash
bash imgproc/package.sh imgproc/pil pil     # -> dist/pil/ 与 dist/pil.tar.gz
scp dist/pil.tar.gz host:                 # 目标机
ssh host 'tar xf pil.tar.gz && ./pil/pil convert in.png out.png L'
```

`package.sh` 做的事：`ldd` 递归收集 ELF 依赖 → 复制进 `lib/` → 写启动器
（`LD_LIBRARY_PATH=$DIR/lib`）→ 打 tar.gz。glibc 核心（`libc/libm/libpthread/libdl/librt/ld-linux`）
**不打包**，由宿主提供。

## 2. 唯一不可再拆的两样

| 依赖 | 说明 |
|---|---|
| Linux 内核 + x86-64 | 产物是原生 ELF |
| glibc 版本下限 | 用老 glibc 的 sysroot 构建（`GLIBC_SYSROOT=...`）即可覆盖新老发行版 |

其余**全在包里**。对比 Go：产物同样是静态单文件；这里是「Python 语法 + 运行时 FFI 任意 C 库」，
且宿主不需要任何前置条件。

## 3. 产物一览

| 命令 | 产物 |
|---|---|
| `python3 -m kernel build app.static.py -o app` | `./app`（ELF）+ `./app.so`（AOT 产物），路径按 `-o` 给的相对 cwd |
| `bash staticpy/static_build_comfycli.sh src out [ffi]` | 裸名 → `dist/out`（兼容入口，`STATICPY_OUTDIR` 可覆盖） |
| `bash imgproc/build.sh` | `cpp/imgproc/build/libimgproc.so` + `imgproc/{pil,concat}` + `dist/mirror_gif` |
| `bash imgproc/build_app.sh USER.static.py OUT` | 用 `pil_lib` 构建的用户程序 |
| `bash imgproc/package.sh APP NAME` | 自包含部署包 `dist/NAME{,.tar.gz}` |
| `bash luajit/embed-build.sh` | 单文件 `lua_app`（内嵌 LuaJIT + 运行时，无动态 luajit） |

## 4. 部署前自检

```bash
bash selfcheck.sh                              # 构建 + 差分 + 覆盖 + 插件钩子 + 自举比对
ldd dist/app | grep "not found"                # 空 = 依赖齐全
bash imgproc/package.sh imgproc/pil pil && \
  docker run --rm -v $PWD/dist:/d debian:stable-slim /d/pil/pil --help   # 干净容器验证
```

构建产物（`.so` / ELF）**不提交进 git**；`dist/` 是产物目录。
