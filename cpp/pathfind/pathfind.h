// pathfind.h — 网格 A* 寻路（对标 Python pathfinding/networkx 的最短路），C ABI
#ifndef PATHFIND_H
#define PATHFIND_H
#ifdef __cplusplus
extern "C" {
#endif
// grid_csv: w*h 个逗号分隔的 0/1（0=可走,1=障碍）。
// diag: 0=四邻(代价1), 1=八邻(对角代价 √2)。
// 返回 JSON：{"cost":<double>,"path":[[x,y],...],"reached":true|false}（静态缓冲）
const char* pf_find_json(const char* grid_csv, int w, int h,
                         int sx, int sy, int ex, int ey, int diag);
#ifdef __cplusplus
}
#endif
#endif
