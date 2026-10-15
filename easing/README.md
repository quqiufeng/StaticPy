# easing —— 2D 缓动/补间（游戏动画）

按 [`../AGENTS.md`](../AGENTS.md) 迁移。**规范 = Robert Penner 缓动**，用 Python 独立实现做差分。

- **C 核心**：`../cpp/easing/` → `libeasing.so`
- **FFI / 前端**：`easing_ffi.scm` + `ease.static.py` → `ease` ELF
- **验证**：`difftest.py` **525/525**（25 条曲线 × 21 采样，双实现一致）

曲线：`ease{In,Out,InOut}{Quad,Cubic,Quart,Quint,Sine,Expo,Circ,Back,Elastic,Bounce}` + `linear`。

```bash
bash easing/build.sh
LD_LIBRARY_PATH=cpp/easing/build ./easing/ease easeInOutCubic 0.5   # 0.500000
python3 easing/difftest.py
```

游戏用途：Tween 位移/缩放/透明度、弹出/回弹/弹性等 UI 与角色动效。
