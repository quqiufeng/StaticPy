#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：A 侧用 pip 的 torch 算期望值，B 侧用 ctypes 直连我们的 .so 算实际值。
# pip torch(2.12) 与 /opt/libtorch(2.1.2) 的 c10 符号互斥，所以两侧必须**分进程**跑。
#
# 用法:
#   python3 plugins/ltorch/capi_difftest.py           # 跑全部用例（自动分进程）
#   python3 plugins/ltorch/capi_difftest.py -v        # 打印每条用例的 max|Δ|
#   python3 plugins/ltorch/capi_difftest.py --dump     # 只打印 B 侧值（排障）
import ctypes
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SO = os.path.join(ROOT, "cpp/torch/build/libtorch_capi.so")
TMP = os.environ.get("TMPDIR", os.path.expanduser("~/iso_gen"))
EXPECT = os.path.join(TMP, "ltorch_capi_expect.json")

TOL = 1e-10

# ---------------------------------------------------------------- 公共输入
X = [[1.0, -2.0], [3.0, -4.0]]
Y = [[0.5, 1.5], [2.5, 3.5]]
LOGITS = [[0.1, 0.9, -0.4, 0.2], [1.0, -1.0, 0.0, 0.5], [-0.3, 0.2, 0.7, 0.1]]
TARGETS = [0.0, 2.0, 1.0]
IMGS = [[[[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0],
          [9.0, 10.0, 11.0, 12.0], [13.0, 14.0, 15.0, 16.0]]]]
KERNEL = [[[[1.0, 0.0], [0.0, -1.0]]]]
VEC = [[0.5, -1.5, 2.5, 3.5, -0.25]]


def flat(m):
    out = []
    if isinstance(m, list):
        for e in m:
            out = out + flat(e)
    else:
        out = [float(m)]
    return out


# ---------------------------------------------------------------- A 侧：pip torch
def _lseq(n, phase=0.0):
    """确定性权重序列：两侧各自生成同一份（拷到 CSV 也省得传）。"""
    import math
    return [math.sin((i + 1) * 0.7 + phase) * 0.5 for i in range(n)]


def side_expect():
    import torch

    def tn(m):
        return torch.tensor(m, dtype=torch.float64)

    x = tn(X)
    y = tn(Y)
    logits = tn(LOGITS)
    tgt = torch.tensor([0, 2, 1], dtype=torch.int64)
    img = tn(IMGS)
    ker = tn(KERNEL)
    vec = tn(VEC)
    out = {}

    def put(name, t):
        t = t.detach().to(torch.float64).contiguous()
        out[name] = {"vals": flat(t.tolist()), "shape": list(t.shape)}

    put("exp", x.exp())
    put("log", y.log())
    put("sqrt", y.sqrt())
    put("abs", x.abs())
    put("pow2", x.pow(2.0))
    out["max"] = {"vals": [float(x.max())], "shape": []}
    out["min"] = {"vals": [float(x.min())], "shape": []}
    out["std_u"] = {"vals": [float(vec.std(unbiased=True))], "shape": []}
    out["std_p"] = {"vals": [float(vec.std(unbiased=False))], "shape": []}
    out["argmax"] = {"vals": [float(x.argmax())], "shape": []}
    put("max_dim0", x.max(dim=0).values)
    put("max_dim0_idx", x.max(dim=0).indices)
    put("mean_dim0", x.mean(dim=0))
    put("cat1", torch.cat([x, y], dim=1))
    put("stack0", torch.stack([x, y], dim=0))
    put("squeeze", tn([[[1.0, 2.0]]]).squeeze(0))
    put("unsqueeze", x.unsqueeze(0))
    put("zeros_like", torch.zeros_like(x))
    put("ones_like", torch.ones_like(x))
    put("cast_f32", x.to(torch.float32).to(torch.float64))
    put("cast_i64", x.to(torch.int64).to(torch.float64))
    put("index_select", y.index_select(0, torch.tensor([1, 0], dtype=torch.int64)))
    put("conv2d", torch.nn.functional.conv2d(img, ker))
    put("conv2d_bias", torch.nn.functional.conv2d(
        img, ker, torch.tensor([0.5], dtype=torch.float64)))
    put("max_pool2d", torch.nn.functional.max_pool2d(img, 2, 2))
    put("avg_pool2d", torch.nn.functional.avg_pool2d(img, 2, 2))
    bn_x = tn([[1.0, 2.0], [3.0, 4.0], [5.0, 8.0]])
    put("batch_norm", torch.nn.functional.batch_norm(
        bn_x, tn([0.0, 0.0]), tn([1.0, 1.0]),
        tn([3.0, 4.0]), tn([4.0, 2.0]), False, 0.0, 1e-5))
    put("cross_entropy", torch.nn.functional.cross_entropy(logits, tgt))
    put("l1_loss", torch.nn.functional.l1_loss(x, y))
    out["dtype_x"] = {"vals": [0.0], "shape": [], "text": "torch.float64"}
    return out


# ---------------------------------------------------------------- B 侧：ctypes
class Cap:
    def __init__(self):
        self.lib = ctypes.CDLL(SO)
        L = self.lib
        P = ctypes.c_void_p
        sig = [
            ("torchc_version", ctypes.c_char_p, []),
            ("torchc_last_error", ctypes.c_char_p, []),
            ("torchc_from_csv", P, [ctypes.c_char_p, ctypes.c_char_p]),
            ("torchc_zeros", P, [ctypes.c_char_p]),
            ("torchc_ones", P, [ctypes.c_char_p]),
            ("torchc_to_csv", ctypes.c_char_p, [P]),
            ("torchc_shape_csv", ctypes.c_char_p, [P]),
            ("torchc_dtype", ctypes.c_char_p, [P]),
            ("torchc_exp", P, [P]),
            ("torchc_log", P, [P]),
            ("torchc_sqrt", P, [P]),
            ("torchc_abs", P, [P]),
            ("torchc_pow_scalar", P, [P, ctypes.c_double]),
            ("torchc_max", ctypes.c_double, [P]),
            ("torchc_min", ctypes.c_double, [P]),
            ("torchc_std", ctypes.c_double, [P, ctypes.c_long]),
            ("torchc_argmax", ctypes.c_long, [P]),
            ("torchc_max_dim", P, [P, ctypes.c_long, ctypes.c_long]),
            ("torchc_mean_dim", P, [P, ctypes.c_long]),
            ("torchc_cat", P, [P, P, ctypes.c_long]),
            ("torchc_stack", P, [P, P, ctypes.c_long]),
            ("torchc_squeeze", P, [P, ctypes.c_long]),
            ("torchc_unsqueeze", P, [P, ctypes.c_long]),
            ("torchc_zeros_like", P, [P]),
            ("torchc_ones_like", P, [P]),
            ("torchc_cast", P, [P, ctypes.c_char_p]),
            ("torchc_index_select", P, [P, ctypes.c_char_p]),
            ("torchc_conv2d", P, [P, P, P, ctypes.c_long, ctypes.c_long,
                                  ctypes.c_long, ctypes.c_long]),
            ("torchc_max_pool2d", P, [P, ctypes.c_long, ctypes.c_long,
                                      ctypes.c_long, ctypes.c_long]),
            ("torchc_avg_pool2d", P, [P, ctypes.c_long, ctypes.c_long,
                                      ctypes.c_long, ctypes.c_long]),
            ("torchc_batch_norm", P, [P, P, P, P, P, ctypes.c_double]),
            ("torchc_cross_entropy", P, [P, ctypes.c_char_p]),
            ("torchc_l1_loss", P, [P, P]),
            ("torchc_dropout", P, [P, ctypes.c_double, ctypes.c_long, ctypes.c_long]),
            ("torchc_sgd_step_momentum", ctypes.c_long,
             [P, P, P, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_long]),
            ("torchc_adam_step", ctypes.c_long,
             [P, P, P, P, ctypes.c_double, ctypes.c_double, ctypes.c_double,
              ctypes.c_double, ctypes.c_double, ctypes.c_long, ctypes.c_long]),
            ("torchc_rmsprop_step", ctypes.c_long,
             [P, P, P, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]),
            ("torchc_set_grad_enabled", ctypes.c_long, [ctypes.c_long]),
            ("torchc_is_grad_enabled", ctypes.c_long, []),
            ("torchc_save", ctypes.c_long, [P, ctypes.c_char_p]),
            ("torchc_load", P, [ctypes.c_char_p]),
            ("torchc_lstm", P, [P, P, P, P, P, P, P, ctypes.c_long]),
            ("torchc_free_int", ctypes.c_long, [P]),
        ]
        for nm, res, arg in sig:
            fn = getattr(L, nm)
            fn.restype = res
            fn.argtypes = arg
        self.keep = []

    def t(self, m, shape):
        h = self.lib.torchc_from_csv(
            ",".join(repr(v) for v in flat(m)).encode(), shape.encode())
        if not h:
            raise RuntimeError("from_csv 失败: " + self.lib.torchc_last_error().decode())
        return h

    def csv(self, h):
        s = self.lib.torchc_to_csv(h)
        if s is None:
            raise RuntimeError("to_csv 失败: " + self.lib.torchc_last_error().decode())
        txt = s.decode()
        if txt == "":
            return []
        return [float(v) for v in txt.split(",")]

    def shape(self, h):
        txt = self.lib.torchc_shape_csv(h).decode()
        if txt == "":
            return []          # 0 维标量
        return [int(v) for v in txt.split(",")]

    def put(self, out, name, h):
        out[name] = {"vals": self.csv(h), "shape": self.shape(h)}
        self.lib.torchc_free_int(h)

    def free(self, *hs):
        # 幂等释放（C 侧 g_live 也会兜一遍），这里避免双释放的 UB
        for h in hs:
            self.lib.torchc_free_int(h)


def side_actual():
    c = Cap()
    L = c.lib
    out = {}
    x = c.t(X, "2,2")
    y = c.t(Y, "2,2")
    logits = c.t(LOGITS, "3,4")
    img = c.t(IMGS, "1,1,4,4")
    ker = c.t(KERNEL, "1,1,2,2")
    vec = c.t(VEC, "1,5")

    c.put(out, "exp", L.torchc_exp(x))
    c.put(out, "log", L.torchc_log(y))
    c.put(out, "sqrt", L.torchc_sqrt(y))
    c.put(out, "abs", L.torchc_abs(x))
    c.put(out, "pow2", L.torchc_pow_scalar(x, 2.0))
    out["max"] = {"vals": [L.torchc_max(x)], "shape": []}
    out["min"] = {"vals": [L.torchc_min(x)], "shape": []}
    out["std_u"] = {"vals": [L.torchc_std(vec, 1)], "shape": []}
    out["std_p"] = {"vals": [L.torchc_std(vec, 0)], "shape": []}
    out["argmax"] = {"vals": [float(L.torchc_argmax(x))], "shape": []}
    c.put(out, "max_dim0", L.torchc_max_dim(x, 0, 0))
    c.put(out, "max_dim0_idx", L.torchc_max_dim(x, 0, 1))
    c.put(out, "mean_dim0", L.torchc_mean_dim(x, 0))
    c.put(out, "cat1", L.torchc_cat(x, y, 1))
    c.put(out, "stack0", L.torchc_stack(x, y, 0))
    sq = c.t([[[1.0, 2.0]]], "1,1,2")
    c.put(out, "squeeze", L.torchc_squeeze(sq, 0))
    c.put(out, "unsqueeze", L.torchc_unsqueeze(x, 0))
    c.put(out, "zeros_like", L.torchc_zeros_like(x))
    c.put(out, "ones_like", L.torchc_ones_like(x))
    h = L.torchc_cast(x, b"float32")
    c.put(out, "cast_f32", L.torchc_cast(h, b"float64"))
    c.free(h)
    h = L.torchc_cast(x, b"int64")
    c.put(out, "cast_i64", L.torchc_cast(h, b"float64"))
    c.free(h)
    c.put(out, "index_select", L.torchc_index_select(y, b"1,0"))
    c.put(out, "conv2d", L.torchc_conv2d(img, ker, None, 1, 1, 0, 0))
    bias = c.t([0.5], "1")
    c.put(out, "conv2d_bias", L.torchc_conv2d(img, ker, bias, 1, 1, 0, 0))
    c.put(out, "max_pool2d", L.torchc_max_pool2d(img, 2, 2, 2, 2))
    c.put(out, "avg_pool2d", L.torchc_avg_pool2d(img, 2, 2, 2, 2))
    bn_x = c.t([[1.0, 2.0], [3.0, 4.0], [5.0, 8.0]], "3,2")
    gm = c.t([0.0, 0.0], "2")
    bt = c.t([1.0, 1.0], "2")
    mu = c.t([3.0, 4.0], "2")
    va = c.t([4.0, 2.0], "2")
    c.put(out, "batch_norm", L.torchc_batch_norm(bn_x, gm, bt, mu, va, 1e-5))
    c.put(out, "cross_entropy", L.torchc_cross_entropy(logits, b"0,2,1"))
    c.put(out, "l1_loss", L.torchc_l1_loss(x, y))
    out["dtype_x"] = {"vals": [0.0], "shape": [], "text": L.torchc_dtype(x).decode()}

    # 优化器：单步结果
    w = c.t([[1.0, 2.0]], "1,2")
    g = c.t([[0.1, -0.2]], "1,2")
    buf = L.torchc_zeros(b"1,2")
    L.torchc_sgd_step_momentum(w, g, buf, 0.1, 0.9, 0.01, 0)
    c.put(out, "sgd_mom_w", w)
    m = L.torchc_zeros(b"1,2")
    v = L.torchc_zeros(b"1,2")
    w2 = c.t([[1.0, 2.0]], "1,2")
    g2 = c.t([[0.1, -0.2]], "1,2")
    L.torchc_adam_step(w2, g2, m, v, 0.1, 0.9, 0.999, 1e-8, 0.0, 1, 0)
    c.put(out, "adam_w", w2)
    w3 = c.t([[1.0, 2.0]], "1,2")
    g3 = c.t([[0.1, -0.2]], "1,2")
    m3 = L.torchc_zeros(b"1,2")
    v3 = L.torchc_zeros(b"1,2")
    L.torchc_adam_step(w3, g3, m3, v3, 0.1, 0.9, 0.999, 1e-8, 0.01, 1, 1)
    c.put(out, "adamw_w", w3)
    w4 = c.t([[1.0, 2.0]], "1,2")
    g4 = c.t([[0.1, -0.2]], "1,2")
    s4 = L.torchc_zeros(b"1,2")
    L.torchc_rmsprop_step(w4, g4, s4, 0.01, 0.99, 1e-8, 0.0)
    c.put(out, "rmsprop_w", w4)

    # 梯度模式 / 存取
    L.torchc_set_grad_enabled(0)
    out["grad_off"] = {"vals": [float(L.torchc_is_grad_enabled())], "shape": []}
    L.torchc_set_grad_enabled(1)
    out["grad_on"] = {"vals": [float(L.torchc_is_grad_enabled())], "shape": []}
    path = os.path.join(TMP, "ltorch_state.pt").encode()
    L.torchc_save(x, path)
    c.put(out, "save_load", L.torchc_load(path))
    # dropout：训练态必须恒等，eval 态必须恒等（p 只在 train 生效）
    c.put(out, "dropout_eval", L.torchc_dropout(x, 0.5, 0, 0))

    # LSTM：I=2,H=2,S=3,B=1（权重确定性生成，两侧一致）
    lx = c.t(_lseq(3 * 1 * 2), "3,1,2")
    lwih = c.t(_lseq(4 * 2 * 2, 2.0), "8,2")
    lwhh = c.t(_lseq(4 * 2 * 2, 3.0), "8,2")
    lbih = c.t(_lseq(8, 4.0), "8")
    lbhh = c.t(_lseq(8, 5.0), "8")
    lh0 = L.torchc_zeros(b"1,1,2")
    lc0 = L.torchc_zeros(b"1,1,2")
    c.put(out, "lstm_out", L.torchc_lstm(lx, lwih, lwhh, lbih, lbhh, lh0, lc0, 0))
    c.put(out, "lstm_hn", L.torchc_lstm(lx, lwih, lwhh, lbih, lbhh, lh0, lc0, 1))
    c.put(out, "lstm_cn", L.torchc_lstm(lx, lwih, lwhh, lbih, lbhh, lh0, lc0, 2))
    c.free(lx, lwih, lwhh, lbih, lbhh, lh0, lc0)

    c.free(x, y, logits, img, ker, vec, sq, bias, bn_x, gm, bt, mu, va,
           w, g, buf, w2, g2, m, v, w3, g3, m3, v3, w4, g4, s4)
    return out


def side_expect_optim():
    import torch
    torch.manual_seed(0)

    def tn(m):
        return torch.tensor(m, dtype=torch.float64)

    out = {}
    p = torch.nn.Parameter(tn([[1.0, 2.0]]))
    p.grad = tn([[0.1, -0.2]])
    opt = torch.optim.SGD([p], lr=0.1, momentum=0.9, weight_decay=0.01)
    opt.step()
    out["sgd_mom_w"] = {"vals": flat(p.detach().tolist()), "shape": [1, 2]}

    p = torch.nn.Parameter(tn([[1.0, 2.0]]))
    p.grad = tn([[0.1, -0.2]])
    torch.optim.Adam([p], lr=0.1).step()
    out["adam_w"] = {"vals": flat(p.detach().tolist()), "shape": [1, 2]}

    p = torch.nn.Parameter(tn([[1.0, 2.0]]))
    p.grad = tn([[0.1, -0.2]])
    torch.optim.AdamW([p], lr=0.1, weight_decay=0.01).step()
    out["adamw_w"] = {"vals": flat(p.detach().tolist()), "shape": [1, 2]}

    p = torch.nn.Parameter(tn([[1.0, 2.0]]))
    p.grad = tn([[0.1, -0.2]])
    torch.optim.RMSprop([p], lr=0.01).step()
    out["rmsprop_w"] = {"vals": flat(p.detach().tolist()), "shape": [1, 2]}

    # LSTM（I=2,H=2,S=3,B=1）：与 side_actual 同一份确定性权重
    lm = torch.nn.LSTM(2, 2, dtype=torch.float64)
    with torch.no_grad():
        lm.weight_ih_l0.copy_(tn(_lseq(16, 2.0)).reshape(8, 2))
        lm.weight_hh_l0.copy_(tn(_lseq(16, 3.0)).reshape(8, 2))
        lm.bias_ih_l0.copy_(tn(_lseq(8, 4.0)))
        lm.bias_hh_l0.copy_(tn(_lseq(8, 5.0)))
    lo, (lhn, lcn) = lm(tn(_lseq(6)).reshape(3, 1, 2))
    out["lstm_out"] = {"vals": flat(lo.detach().tolist()), "shape": [3, 1, 2]}
    out["lstm_hn"] = {"vals": flat(lhn.detach().tolist()), "shape": [1, 1, 2]}
    out["lstm_cn"] = {"vals": flat(lcn.detach().tolist()), "shape": [1, 1, 2]}
    return out


def run_child(mode):
    if mode == "expect":
        d = side_expect()
        d.update(side_expect_optim())
        f = open(EXPECT, "w")
        json.dump(d, f)
        f.close()
        return 0
    d = side_actual()
    if "--dump" in sys.argv:
        print(json.dumps(d, indent=1)[:4000])
        return 0
    f = open(EXPECT)
    exp = json.load(f)
    f.close()
    bad = 0
    total = 0
    for name in sorted(exp.keys()):
        total += 1
        if name not in d:
            print("  MISS " + name + "（我们没算）")
            bad += 1
            continue
        e = exp[name]
        g = d[name]
        if e.get("shape") != g.get("shape"):
            print("  DIFF " + name + " shape " + str(g.get("shape")) + " != " + str(e.get("shape")))
            bad += 1
            continue
        if "text" in e:
            if e["text"] != g.get("text"):
                print("  DIFF " + name + " text " + str(g.get("text")) + " != " + e["text"])
                bad += 1
            elif "-v" in sys.argv:
                print("  ok   " + name + " (text)")
            continue
        if len(e["vals"]) != len(g["vals"]):
            print("  DIFF " + name + " len " + str(len(g["vals"])) + " != " + str(len(e["vals"])))
            bad += 1
            continue
        mx = 0.0
        for a, b in zip(g["vals"], e["vals"]):
            dv = abs(a - b)
            if dv > mx:
                mx = dv
        if mx > TOL:
            print("  DIFF " + name + " max|Δ|=" + repr(mx))
            print("       我们: " + str(g["vals"][:8]))
            print("     pytorch: " + str(e["vals"][:8]))
            bad += 1
        elif "-v" in sys.argv:
            print("  ok   " + name + " max|Δ|=" + repr(mx))
    print("---- C ABI 差分 " + str(total - bad) + "/" + str(total) + "（容差 " + str(TOL) + "）")
    return 1 if bad else 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("expect", "actual"):
        return run_child(sys.argv[1])
    env = dict(os.environ)
    # A 侧：pip torch（不带 LD_LIBRARY_PATH=/opt/libtorch/lib）
    env.pop("LD_LIBRARY_PATH", None)
    r1 = subprocess.run([sys.executable, os.path.abspath(__file__), "expect"], env=env)
    if r1.returncode != 0:
        print("期望值侧失败")
        return 1
    env2 = dict(os.environ)
    env2["LD_LIBRARY_PATH"] = "/opt/libtorch/lib:" + env2.get("LD_LIBRARY_PATH", "")
    # B 侧：ctypes + 我们的 .so（需要 libtorch 的 .so）
    argv = [sys.executable, os.path.abspath(__file__), "actual"]
    if "-v" in sys.argv:
        argv.append("-v")
    if "--dump" in sys.argv:
        argv.append("--dump")
    return subprocess.run(argv, env=env2).returncode


if __name__ == "__main__":
    sys.exit(main())
