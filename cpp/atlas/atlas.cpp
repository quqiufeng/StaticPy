// atlas.cpp — MaxRects(BSSF) 打包
#include "atlas.h"
#include <vector>
#include <algorithm>
#include <string>
#include <cstdio>
#include <cstdlib>

namespace {
struct Rect { int x, y, w, h; };
thread_local std::string g_out;
// MaxRects 自由矩形表
struct MR {
    std::vector<Rect> freeRects;
    std::vector<Rect> placed;
    void init(int w, int h) { freeRects.clear(); placed.clear(); freeRects.push_back({0, 0, w, h}); }
    bool insert(Rect& r) {
        int best = -1, bestShort = 1 << 30, bestLong = 1 << 30;
        for (size_t i = 0; i < freeRects.size(); ++i) {
            const Rect& f = freeRects[i];
            if (f.w >= r.w && f.h >= r.h) {
                int lw = f.w - r.w, lh = f.h - r.h;
                int shortSide = std::min(lw, lh), longSide = std::max(lw, lh);
                if (shortSide < bestShort || (shortSide == bestShort && longSide < bestLong)) { best = (int)i; bestShort = shortSide; bestLong = longSide; }
            }
        }
        if (best < 0) return false;
        r.x = freeRects[best].x; r.y = freeRects[best].y;   // BSSF：靠左上
        placed.push_back(r);
        // 用 r 切分所有与之相交的自由矩形
        std::vector<Rect> next;
        for (const Rect& f : freeRects) {
            bool inter = !(r.x >= f.x + f.w || r.x + r.w <= f.x || r.y >= f.y + f.h || r.y + r.h <= f.y);
            if (!inter) { next.push_back(f); continue; }
            if (r.x > f.x) next.push_back({f.x, f.y, r.x - f.x, f.h});                       // 左
            if (r.x + r.w < f.x + f.w) next.push_back({r.x + r.w, f.y, f.x + f.w - (r.x + r.w), f.h}); // 右
            if (r.y > f.y) next.push_back({f.x, f.y, f.w, r.y - f.y});                        // 上
            if (r.y + r.h < f.y + f.h) next.push_back({f.x, r.y + r.h, f.w, f.y + f.h - (r.y + r.h)}); // 下
        }
        freeRects = next;
        return true;
    }
};
}

extern "C" {

const char* atlas_pack_json(const char* sizes_csv, int sw, int sh) {
    // 解析
    std::vector<std::pair<int, int>> sizes;
    const char* p = sizes_csv;
    while (*p) {
        while (*p == ';' || *p == ' ' || *p == '\n') ++p;
        if (!*p) break;
        int a = strtol(p, (char**)&p, 10);
        while (*p == ',' || *p == ' ') ++p;
        int b = strtol(p, (char**)&p, 10);
        sizes.push_back({a, b});
    }
    int total = (int)sizes.size();
    // 面积降序
    std::vector<int> order(total); for (int i = 0; i < total; ++i) order[i] = i;
    std::sort(order.begin(), order.end(), [&](int a, int b) {
        long aa = (long)sizes[a].first * sizes[a].second, bb = (long)sizes[b].first * sizes[b].second;
        return aa > bb;
    });
    MR mr; mr.init(sw, sh);
    int packed = 0;
    char buf[128];
    std::string placements = "[";
    for (int oi = 0; oi < total; ++oi) {
        int i = order[oi]; int w = sizes[i].first, h = sizes[i].second;
        Rect r; r.x = 0; r.y = 0; r.w = w; r.h = h;
        if (!mr.insert(r)) continue;
        if (packed) placements += ",";
        snprintf(buf, sizeof buf, "[%d,%d,%d,%d]", r.x, r.y, w, h);
        placements += buf;
        packed++;
    }
    placements += "]";
    snprintf(buf, sizeof buf, "{\"packed\":%d,\"total\":%d,\"sheet\":[%d,%d],\"placements\":", packed, total, sw, sh);
    g_out = std::string(buf) + placements + "}";
    return g_out.c_str();
}

}  // extern "C"
