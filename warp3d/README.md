# warp3d —— 2D 图像的 3D 旋转 / 透视变换（伪 3D 动效）

按 [`../AGENTS.md`](../AGENTS.md) 迁移。把 2D 精灵做 3D 转动（卡片翻转、金币旋转、拾取物旋转）。

- **C 核心**：`../cpp/warp3d/` → `libwarp3d.so`（单应 warp + 4 点单应求解 + 3D 旋转投影）
- **FFI / 前端**：`warp3d_ffi.scm` + `w3d.static.py` → `w3d` ELF
- **验证**：`difftest.py` 仿射变换 vs `cv2.warpPerspective` **4/4（±1）**（cv2 定点插值舍入）

```bash
bash warp3d/build.sh
LD_LIBRARY_PATH=cpp/warp3d/build ./warp3d/w3d rotate IN.png OUT.png 45 0 0 800 800 200 200
python3 warp3d/difftest.py
```

- `rotate`: yaw/pitch/roll(度) + 相机距离/焦距 → 输出透视投影后的图（伪 3D 转动）。
- `persp`: 直接给 8 系数单应（dst→src，同 PIL `PERSPECTIVE`）。
- 说明：强透视下与 cv2 存在插值/边界差异（未逐位对齐）；仿射与 cv2 一致（±1）。
