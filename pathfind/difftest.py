# difftest.py — 网格 A* 差分：networkx 最短路 vs libpathfind（代价一致 + 路径合法）
import ctypes as C, os, sys, math, random, networkx as nx
lib = C.CDLL(os.environ.get("PATHFIND_SO", os.path.join(os.path.dirname(__file__), "..", "cpp", "pathfind", "build", "libpathfind.so")))
lib.pf_find_json.restype = C.c_char_p
lib.pf_find_json.argtypes = [C.c_char_p] + [C.c_int] * 7
import json

def ref_cost(blocked, w, h, s, e, diag):
    G = nx.Graph()
    for y in range(h):
        for x in range(w):
            if blocked[y][x]:
                continue
            G.add_node((x, y))
    D4 = [(1,0),(-1,0),(0,1),(0,-1)]
    D8 = D4 + [(1,1),(1,-1),(-1,1),(-1,-1)]
    dirs = D8 if diag else D4
    for y in range(h):
        for x in range(w):
            if blocked[y][x]:
                continue
            for dx, dy in dirs:
                nx_, ny = x+dx, y+dy
                if not (0 <= nx_ < w and 0 <= ny < h) or blocked[ny][nx_]:
                    continue
                if diag and dx and dy:
                    if blocked[y][nx_] or blocked[ny][x]:
                        continue
                G.add_edge((x, y), (nx_, ny), weight=(math.sqrt(2) if (dx and dy) else 1.0))
    if s not in G or e not in G:
        return -1.0
    try:
        return nx.shortest_path_length(G, s, e, weight="weight")
    except nx.NetworkXNoPath:
        return -1.0

random.seed(7)
fails = 0
for t in range(60):
    w = random.randint(4, 14); h = random.randint(4, 14)
    blocked = [[1 if random.random() < 0.25 else 0 for _ in range(w)] for _ in range(h)]
    sx, sy = random.randrange(w), random.randrange(h)
    ex, ey = random.randrange(w), random.randrange(h)
    blocked[sy][sx] = 0; blocked[ey][ex] = 0
    diag = t % 2
    csv = ",".join(str(blocked[y][x]) for y in range(h) for x in range(w))
    r = json.loads(lib.pf_find_json(csv.encode(), w, h, sx, sy, ex, ey, diag).decode())
    rc = r["cost"]
    ec = ref_cost(blocked, w, h, (sx, sy), (ex, ey), diag)
    ok = (rc == -1 and ec == -1) or (abs(rc - ec) < 1e-6)
    # 路径合法性
    if r["reached"] and r["path"]:
        p = r["path"]
        ok = ok and p[0] == [sx, sy] and p[-1] == [ex, ey]
    if not ok:
        fails += 1
        print(f"DIFF t={t} w={w} h={h} diag={diag} ours={rc} ref={ec}")
print(f"\n{60-fails}/60 通过（代价与 networkx 一致 + 路径端点正确）")
sys.exit(1 if fails else 0)
