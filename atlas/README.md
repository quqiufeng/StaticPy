# atlas —— 精灵图集打包（素材管线）

按 [`../AGENTS.md`](../AGENTS.md) 迁移。把一堆小图（素材）并进一张图，输出布局。

- **C 核心**：`../cpp/atlas/` → `libatlas.so`（MaxRects-BSSF）
- **FFI / 前端**：`atlas_ffi.scm` + `atlas.static.py` → `atlas` ELF
- **验证**：`difftest.py` 性质测试 **60/60**（在界内 + 无重叠 + 全打包）

```bash
bash atlas/build.sh
LD_LIBRARY_PATH=cpp/atlas/build ./atlas/atlas sizes.txt 1024 1024
python3 atlas/difftest.py
```

`sizes.txt` 每行 `w,h`；输出 `{"packed":N,"total":M,"sheet":[W,H],"placements":[[x,y,w,h],...]}`。
下一步可接 **imgproc** 按布局把素材拼成图集 PNG（composite/paste）。
