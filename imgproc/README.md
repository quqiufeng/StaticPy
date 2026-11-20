# imgproc —— StaticPy 版 Pillow（旗杆样板）

把图像处理从 Python/PIL 迁到 StaticPy：逻辑写 `.static.py`，底层能力交给运行时挂的
C++ 库 `libimgproc.so`；产物是**独立 ELF**（不依赖 Python / venv / PIL）。
方法论见 [../docs/MIGRATION.md](../docs/MIGRATION.md)，构建与部署见
[../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) 与 [../docs/DEPLOY.md](../docs/DEPLOY.md)。

## 三层结构

| 层 | 文件 | 说明 |
|---|---|---|
| C++ 核心 | `../cpp/imgproc/*.cpp` → `libimgproc.so` | 对标 Pillow `libImaging` + 编解码 |
| FFI | `imgproc_ffi.scm` | 只 `load-shared-object`；`foreign-procedure` 由 `extern fn … from "imgproc"` 生成 |
| StaticPy API | `*.static.py` | `pil_lib`（纯函数库，可集成）+ `pil_cli`（薄 CLI） |

C ABI 是稳定面：StaticPy ELF / LuaJIT FFI / Python ctypes 调同一份 `.so`。

## 文件

```
imgproc/
├── pil_lib.static.py      # ★ 库：extern fn 声明 + 包装函数（无 main，可被集成）
├── pil_cli.static.py      # pil CLI 分发
├── pilcli.static.py       # 早期 CLI（convert/resize/crop/…）
├── mirror_gif.static.py   # 示例算子：GIF 逐帧镜像（保留索引帧，无损）
├── concat.static.py       # 构建工具：库 + 用户程序拼成 bundle（自举，StaticPy 写的）
├── build.sh / build_app.sh / package.sh
├── imgproc_ffi.scm
├── pil_surface.py         # 自省 Pillow 公开 API → pil_api.md
├── pil_api.md             # 上面生成的自省清单
├── frontend_coverage.py   # 用清单核对我们的实现（覆盖 100/100）
├── difftest.py            # 差分测试：PIL vs 我们，逐像素（100/100）
├── pyimgproc.py           # libimgproc.so 的 ctypes 绑定（给 difftest 用）
└── examples/              # 集成示例（make_banner：用库而非 CLI）
```

## 构建 / 运行 / 验证

```bash
bash imgproc/build.sh
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/pil convert IN.png OUT.png L
LD_LIBRARY_PATH=$PWD/cpp/imgproc/build ./imgproc/mirror_gif IN.gif OUT.gif

python3 imgproc/pil_surface.py > imgproc/pil_api.md   # 自省清单
python3 imgproc/frontend_coverage.py                  # 覆盖 100/100
python3 imgproc/difftest.py -v                        # 差分 100/100（多数 maxΔ=0）
```

## 覆盖（简表）

编解码（GIF 多帧保调色板、PNG/JPEG/BMP/TGA/WebP/TIFF）· Image 核心（open/save/new/convert/
split/merge/getbbox/frombytes/to_bytes/多帧）· 几何（crop/resize/thumbnail/rotate/transpose/pad/
paste/composite/alpha_composite/blend/fit/contain）· ImageOps · ImageChops · ImageEnhance ·
ImageFilter（BoxBlur/Gaussian/Median 等，按 `Filter.c` 精确对齐）· ImageStat · ImageDraw ·
ImageFont（FreeType）· `convert("P")` 调色板 + FS 抖动 · quantize 三法（MEDIANCUT /
MAXCOVERAGE / FASTOCTREE）· `Image.eval` / `ImageOps.deform`（lambda 回调）。

近似项：`draw.rounded_rect` / `draw.chord` 的栅格化细节（差分已放宽容差）。
逐项清单见 `pil_api.md` 与 `frontend_coverage.py` 输出。

## 作为库被集成

```python
# my_app.static.py
from pil_lib import img_open, img_save, img_grayscale, img_resize, img_pad

def main():
    im = img_open("in.png")
    g = img_grayscale(im)
    r = img_resize(g, 120, 90, "lanczos")
    img_save(img_pad(r, 8, 8, 8, 8, 0xFFFFFFFF), "out.png")

# bash imgproc/build_app.sh my_app.static.py my_app
# LD_LIBRARY_PATH=cpp/imgproc/build ./my_app
```

`concat`（自举工具）去掉 `import` 行并把库与用户代码合到一个作用域；`build_app.sh` 封装了
「concat + AOT 编译 + 链接」。C ABI 本身也是稳定面，LuaJIT/ctypes 无需 StaticPy 即可直调。

## 加新算子

1. 新底层能力 → 加到 `cpp/imgproc/`（C ABI 在 `imgproc.h`）。
2. `.py` 顶部 `extern fn name(args) -> ret from "imgproc"` 声明。
3. 主逻辑写 `def main():`（**别在顶层调用 main**，翻译器会自动加 `(static_main)`）。
4. `bash imgproc/build.sh`；`difftest.py` 验证到 maxΔ=0。

FFI 约定：类型只有 `str/int/float/ptr`、**无 `void` 返回**（返回 void 的 C 函数改成返回 `int`）；
多值参数（点列/LUT/调色板）用 CSV 字符串传。详见 [../docs/LANGUAGE.md](../docs/LANGUAGE.md)。
