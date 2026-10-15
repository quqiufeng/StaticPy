# cvops —— 经典图像处理/优化算法（对标 OpenCV）

按 [`../AGENTS.md`](../AGENTS.md) 迁移，**自实现、不依赖 OpenCV**（避免版本漂移）。

- **C 核心**：`../cpp/cvops/` → `libcvops.so`
- **FFI / 前端**：`cvops_ffi.scm` + `cv.static.py` → `cv` ELF
- **验证**：`difftest.py` 与 `cv2`（OpenCV）对拍，**6/6 逐像素一致**

| 命令 | 算法 |
|---|---|
| `erode`/`dilate`/`open`/`close` | 形态学（矩形核，`BORDER_REPLICATE`） |
| `otsu` | Otsu 全局二值化 |
| `sobel` | Sobel 梯度幅度（\|G\|） |

```bash
bash cvops/build.sh
LD_LIBRARY_PATH=cpp/cvops/build ./cvops/cv erode IN.png OUT.png 3
python3 cvops/difftest.py
```
