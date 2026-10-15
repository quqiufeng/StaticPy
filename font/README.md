# font —— TTF → 字形图集 + 度量（游戏位图字体）

按 [`../AGENTS.md`](../AGENTS.md) 迁移。渲染文字用静态位图字体（图集 + JSON），比每帧画字更省。

- **C 核心**：`../cpp/font/` → `libfont.so`（**FreeType** 光栅化 + shelf 打包）
- **FFI / 前端**：`font_ffi.scm` + `font.static.py` → `font` ELF
- **验证**：`difftest.py`，**15/15** 字形 `advance`/位图高与 PIL(FreeType) 一致

```bash
bash font/build.sh
LD_LIBRARY_PATH=cpp/font/build ./font/font DejaVuSans.ttf 24 "ABCabc0123" out.png out.json 512
python3 font/difftest.py
```

输出：`out.png`（灰度图集）+ `out.json`（`{"size","width","height","glyphs":[{cp,x,y,w,h,bx,by,advance}]}`）。
可与 `atlas`/`imgproc` 组合做完整字体/精灵素材流水线。
