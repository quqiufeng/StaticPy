# pathfind —— 网格 A* 寻路（游戏用）

按 [`../AGENTS.md`](../AGENTS.md) 三步闭环迁移。iso_flutter 的 NPC 走格子直接可用。

- **C 核心**：`../cpp/pathfind/` → `libpathfind.so`（A*，曼哈顿/octile 可采纳启发 → 最优）
- **FFI / 前端**：`pathfind_ffi.scm` + `pf.static.py` → `pf` ELF
- **验证**：`difftest.py` 对随机网格与 **networkx 最短路**比对，**60/60**（代价一致 + 路径合法）

```bash
bash pathfind/build.sh
LD_LIBRARY_PATH=cpp/pathfind/build ./pathfind/pf GRID.txt W H SX SY EX EY [DIAG]
python3 pathfind/difftest.py
```

- 四邻（代价 1）/ 八邻（对角 √2，且**不切角**）两种模式。
- 输出 JSON：`{"cost":...,"path":[[x,y],...],"reached":true|false}`。
