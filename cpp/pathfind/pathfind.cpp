// pathfind.cpp — A*（曼哈顿/八方向 octile 启发，可采纳 → 最优）
#include "pathfind.h"
#include <vector>
#include <queue>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>

namespace {
struct PF {
    int w, h, diag;
    std::vector<unsigned char> blocked;
    bool walk(int x, int y) const { return x >= 0 && x < w && y >= 0 && y < h && !blocked[(size_t)y * w + x]; }
    double sc(int dx, int dy) const { return (dx && dy) ? std::sqrt(2.0) : 1.0; }
    double hcost(int x, int y, int ex, int ey) const {
        int dx = std::abs(x - ex), dy = std::abs(y - ey);
        if (diag) { int mn = std::min(dx, dy); return (dx + dy - 2 * mn) + mn * std::sqrt(2.0); }
        return dx + dy;
    }
};
thread_local std::string g_out;
}

extern "C" {

const char* pf_find_json(const char* grid_csv, int w, int h,
                         int sx, int sy, int ex, int ey, int diag) {
    PF pf; pf.w = w; pf.h = h; pf.diag = diag;
    pf.blocked.assign((size_t)w * h, 0);
    // 解析 grid_csv
    const char* p = grid_csv; int i = 0;
    while (*p && i < w * h) {
        while (*p == ',' || *p == ' ' || *p == '\n') ++p;
        if (!*p) break;
        pf.blocked[i++] = (unsigned char)(*p != '0');
        while (*p && *p != ',' && *p != ' ' && *p != '\n') ++p;
    }
    if (i < w * h) { g_out = "{\"cost\":-1,\"path\":[],\"reached\":false}"; return g_out.c_str(); }

    auto idx = [&](int x, int y) { return (size_t)y * w + x; };
    std::vector<double> g((size_t)w * h, 1e18);
    std::vector<int> from((size_t)w * h, -1);
    std::vector<unsigned char> closed((size_t)w * h, 0);
    typedef std::pair<double, int> QN;
    std::priority_queue<QN, std::vector<QN>, std::greater<QN>> open;
    auto push = [&](int x, int y, double gv, int come) {
        int id = (int)idx(x, y); g[id] = gv; from[id] = come;
        open.push({gv + pf.hcost(x, y, ex, ey), id});
    };
    if (pf.walk(sx, sy)) push(sx, sy, 0.0, -1);
    const int DX4[] = {1,-1,0,0}, DY4[] = {0,0,1,-1};
    const int DX8[] = {1,-1,0,0,1,1,-1,-1}, DY8[] = {0,0,1,-1,1,-1,1,-1};
    const int* DX = diag ? DX8 : DX4; const int* DY = diag ? DY8 : DY4;
    int nbr = diag ? 8 : 4;
    bool reached = false;
    while (!open.empty()) {
        QN top = open.top(); open.pop();
        int id = top.second; if (closed[id]) continue; closed[id] = 1;
        int x = id % w, y = id / w;
        if (x == ex && y == ey) { reached = true; break; }
        for (int k = 0; k < nbr; ++k) {
            int nx = x + DX[k], ny = y + DY[k];
            if (!pf.walk(nx, ny)) continue;
            if (diag && DX[k] && DY[k] && (!pf.walk(x + DX[k], y) || !pf.walk(x, y + DY[k]))) continue;  // 不切角
            double ng = g[id] + pf.sc(DX[k], DY[k]);
            int nid = (int)idx(nx, ny);
            if (ng < g[nid] - 1e-12) push(nx, ny, ng, id);
        }
    }
    // 回溯
    char buf[64];
    if (!reached) { g_out = "{\"cost\":-1,\"path\":[],\"reached\":false}"; return g_out.c_str(); }
    std::vector<int> chain; int cur = (int)idx(ex, ey);
    while (cur != -1) { chain.push_back(cur); cur = from[cur]; }
    std::string path = "[";
    int last = (int)chain.size() - 1;
    for (int j = last; j >= 0; --j) {
        int x = chain[j] % w, y = chain[j] / w;
        snprintf(buf, sizeof buf, j == last ? "[%d,%d]" : ",[%d,%d]", x, y);
        path += buf;
    }
    path += "]";
    snprintf(buf, sizeof buf, "{\"cost\":%.10g,\"path\":", g[(size_t)ey * w + ex]);
    g_out = std::string(buf) + path + ",\"reached\":true}";
    return g_out.c_str();
}

}  // extern "C"
