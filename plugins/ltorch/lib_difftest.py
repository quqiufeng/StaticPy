#!/usr/bin/env python3
# lib_difftest.py — tensor_lib.static.py（Tensor 类 + nn/optim）对拍 pip torch
#
# 为什么必须两个进程：pip torch 是 2.12.0+cpu、/opt/libtorch 是 2.1.2，
# 两者的 c10 符号互斥，同一进程里 dlopen 会打架。所以：
#   参考值 = CPython + torch（dtype=float64，本脚本内）
#   我们的值 = AOT ELF（build_app.sh 拼 tensor_lib + 探针），子进程跑
#
# 口径：C ABI 全 float64 → 对标 torch.tensor(..., dtype=torch.float64)。
# 随机初始化（randn/seed）在 2.1.2 与 2.12 上 RNG 不同，不参与逐位对拍；
# 线性层权重由本脚本用 torch 生成后**灌进探针**（Linear.load），这样梯度/SGD 全链路可比。
#
# 用法：python3 plugins/ltorch/lib_difftest.py [-v] [--no-elf]
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORK = os.path.expanduser("~/iso_gen/lt")
TOL = 1e-10


def csv(vals):
    return ",".join(repr(float(v)) for v in vals)


def flat(t):
    return [float(x) for x in t.reshape(-1).tolist()]


# ---------------------------------------------------------------- 探针源码
PROBE = '''# 自动生成（plugins/ltorch/lib_difftest.py）—— tensor_lib 对拍探针
def main():
    a: Tensor = tensor([1.0, 2.0, 3.0, 4.0], [2, 2])
    b: Tensor = tensor([0.5, -1.0, 2.0, 3.0], [2, 2])
    print("matmul=" + a.matmul(b).values())
    print("add=" + a.add(b).values())
    print("sub=" + a.sub(b).values())
    print("mul=" + a.mul(b).values())
    print("div=" + a.div(b).values())
    print("add_s=" + a.add_scalar(2.5).values())
    print("sub_s=" + a.sub_scalar(2.5).values())
    print("mul_s=" + a.mul_scalar(-1.5).values())
    print("div_s=" + a.div_scalar(3.0).values())
    print("relu=" + b.sub_scalar(1.0).relu().values())
    print("sigmoid=" + b.sigmoid().values())
    print("tanh=" + b.tanh().values())
    print("neg=" + b.neg().values())
    print("softmax=" + b.softmax(1).values())
    print("sum=" + a.sum().values())
    print("mean=" + a.mean().values())
    print("sum_dim=" + b.sum_dim(0).values())
    print("transpose=" + a.transpose(0, 1).values())
    print("reshape=" + a.reshape([4]).values())
    print("item=" + str(a.sum().item()))
    print("shape=" + a.matmul(b).shape())
    print("numel=" + str(b.numel()))

    lin: Linear = Linear(3, 2, 0)
    lin.load({W1}, {S1}, {B1}, {SB1})
    lin.zero_grad()
    x: Tensor = tensor_from_csv({XI}, {SX})
    tgt: Tensor = tensor_from_csv({TI}, {ST})
    y: Tensor = lin.forward(x)
    print("lin_y=" + y.values())
    loss: Tensor = MSELoss().forward(y, tgt)
    print("lin_loss=" + str(loss.item()))
    loss.backward()
    print("lin_gw=" + lin.w.grad_values())
    print("lin_gb=" + lin.b.grad_values())
    opt: SGD = SGD(lin.parameters(), 0.1)
    opt.step()
    print("lin_w_after=" + lin.w.values())
    print("lin_b_after=" + lin.b.values())
    opt.zero_grad()
    print("lin_after_grad=" + lin.w.grad_values())

    l1: Linear = Linear(2, 4, 0)
    l1.load({W2}, {S2}, {B2}, {SB2})
    l2: Linear = Linear(4, 1, 0)
    l2.load({W3}, {S3}, {B3}, {SB3})
    relu: ReLU = ReLU()
    mse: MSELoss = MSELoss()
    opt2: SGD = SGD(concat_params(l1, l2), 0.01)
    xs: Tensor = tensor_from_csv({XS}, {SXS})
    ys: Tensor = tensor_from_csv({YS}, {SYS})
    i: int = 0
    while i < 200:
        pred: Tensor = l2.forward(relu.forward(l1.forward(xs)))
        ml: Tensor = mse.forward(pred, ys)
        opt2.zero_grad()
        ml.backward()
        opt2.step()
        i += 1
    final: Tensor = mse.forward(l2.forward(relu.forward(l1.forward(xs))), ys)
    print("mlp_loss=" + str(final.item()))
    print("mlp_pred=" + l2.forward(relu.forward(l1.forward(xs))).values())
    print("ok")


def concat_params(m1: Linear, m2: Linear) -> list:
    out: list = []
    p1: list = m1.parameters()
    p2: list = m2.parameters()
    i: int = 0
    while i < len(p1):
        out.append(p1[i])
        i += 1
    i = 0
    while i < len(p2):
        out.append(p2[i])
        i += 1
    return out
'''


def run_elf(pairs, verbose):
    """用注入的权重生成探针 → build_app.sh → 跑 ELF → {key: [float]}"""
    src = PROBE
    for k, v in pairs.items():
        src = src.replace("{%s}" % k, v if v.startswith('"') or v.startswith("[") else '"%s"' % v)
    path = os.path.join(WORK, "lib_probe.static.py")
    with open(path, "w") as f:
        f.write(src)
    env = dict(os.environ)
    env["TMPDIR"] = os.path.expanduser("~/iso_gen/ctlbin")
    env["STATICPY_OUTDIR"] = WORK
    b = subprocess.run(["bash", os.path.join(HERE, "build_app.sh"), path, "lib_probe"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    if b.returncode != 0:
        sys.exit("构建失败:\n" + b.stdout[-3000:] + b.stderr[-3000:])
    env2 = dict(env)
    env2["LD_LIBRARY_PATH"] = os.path.join(ROOT, "cpp/torch/build")
    r = subprocess.run([os.path.join(WORK, "lib_probe")], env=env2, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("运行失败:\n" + r.stdout[-2000:] + r.stderr[-2000:])
    if verbose:
        print(r.stdout)
    out = {}
    for line in r.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            try:
                out[k] = [float(x) for x in v.split(",")] if "," in v else [float(v)]
            except ValueError:
                out[k] = v
    return out


def main():
    import torch
    torch.set_default_dtype(torch.float64)
    verbose = "-v" in sys.argv

    def T(vals, shape):
        return torch.tensor(vals, dtype=torch.float64).reshape(shape)

    # 线性层权重（灌给探针，保证两边同一个初值）
    g = torch.Generator().manual_seed(20261122)
    w1 = (torch.randn(2, 3, generator=g, dtype=torch.float64) * 0.5).requires_grad_(True)
    b1 = torch.zeros(1, 2, dtype=torch.float64, requires_grad=True)
    w2 = (torch.randn(4, 2, generator=g, dtype=torch.float64) * 0.7).requires_grad_(True)
    b2 = torch.zeros(1, 4, dtype=torch.float64, requires_grad=True)
    w3 = (torch.randn(1, 4, generator=g, dtype=torch.float64) * 0.5).requires_grad_(True)
    b3 = torch.zeros(1, 1, dtype=torch.float64, requires_grad=True)
    xin = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    tgt = [1.0, 2.0, 1.0, 2.0]
    xs = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0]
    ys = [2.0, 4.0, 6.0, 8.0]

    pairs = {
        "W1": csv(flat(w1)), "S1": "2,3", "B1": csv(flat(b1)), "SB1": "1,2",
        "XI": csv(xin), "SX": "2,3", "TI": csv(tgt), "ST": "2,2",
        "W2": csv(flat(w2)), "S2": "4,2", "B2": csv(flat(b2)), "SB2": "1,4",
        "W3": csv(flat(w3)), "S3": "1,4", "B3": csv(flat(b3)), "SB3": "1,1",
        "XS": csv(xs), "SXS": "4,2", "YS": csv(ys), "SYS": "4,1",
    }
    ours = run_elf(pairs, verbose)

    # ---------------- 参考值（torch float64） ----------------
    a = T([1.0, 2.0, 3.0, 4.0], (2, 2))
    b = T([0.5, -1.0, 2.0, 3.0], (2, 2))
    ref = {
        "matmul": flat(a @ b), "add": flat(a + b), "sub": flat(a - b),
        "mul": flat(a * b), "div": flat(a / b),
        "add_s": flat(a + 2.5), "sub_s": flat(a - 2.5),
        "mul_s": flat(a * -1.5), "div_s": flat(a / 3.0),
        "relu": flat(torch.relu(b - 1.0)), "sigmoid": flat(torch.sigmoid(b)),
        "tanh": flat(torch.tanh(b)), "neg": flat(-b),
        "softmax": flat(torch.softmax(b, dim=1)),
        "sum": flat(a.sum().reshape(1)), "mean": flat(a.mean().reshape(1)),
        "sum_dim": flat(b.sum(dim=0)), "transpose": flat(a.T),
        "reshape": flat(a.reshape(4)), "item": [float(a.sum().item())],
        "numel": [float(b.numel())],
    }
    # 线性层：同初值前向 + 梯度 + 一步 SGD
    x = T(xin, (2, 3))
    t = T(tgt, (2, 2))
    lin_w = T(flat(w1), (2, 3)).requires_grad_(True)
    lin_b = T(flat(b1), (1, 2)).requires_grad_(True)
    y = x @ lin_w.T + lin_b
    l1 = ((y - t) ** 2).mean()
    l1.backward()
    ref["lin_y"] = flat(y.detach())
    ref["lin_loss"] = [float(l1.item())]
    ref["lin_gw"] = flat(lin_w.grad)
    ref["lin_gb"] = flat(lin_b.grad)
    with torch.no_grad():
        lin_w -= 0.1 * lin_w.grad
        lin_b -= 0.1 * lin_b.grad
    ref["lin_w_after"] = flat(lin_w)
    ref["lin_b_after"] = flat(lin_b)
    ref["lin_after_grad"] = [0.0] * 6

    # MLP：同初值 200 步
    mw1 = T(flat(w2), (4, 2)).requires_grad_(True)
    mb1 = T(flat(b2), (1, 4)).requires_grad_(True)
    mw2 = T(flat(w3), (1, 4)).requires_grad_(True)
    mb2 = T(flat(b3), (1, 1)).requires_grad_(True)
    mx = T(xs, (4, 2))
    my = T(ys, (4, 1))
    params = [mw1, mb1, mw2, mb2]
    for _ in range(200):
        pred = torch.relu(mx @ mw1.T + mb1) @ mw2.T + mb2
        ml = ((pred - my) ** 2).mean()
        for p in params:
            if p.grad is not None:
                p.grad = None
        ml.backward()
        with torch.no_grad():
            for p in params:
                p -= 0.01 * p.grad
    pred = torch.relu(mx @ mw1.T + mb1) @ mw2.T + mb2
    ref["mlp_loss"] = [float(((pred - my) ** 2).mean().item())]
    ref["mlp_pred"] = flat(pred.detach())

    # ---------------- 比对 ----------------
    bad = 0
    for k, want in ref.items():
        got = ours.get(k)
        if got is None or isinstance(got, str):
            print("FAIL %-16s 缺失（%r）" % (k, got))
            bad += 1
            continue
        if len(got) != len(want):
            print("FAIL %-16s 长度 %d vs %d" % (k, len(got), len(want)))
            bad += 1
            continue
        d = max((abs(g - w) for g, w in zip(got, want)), default=0.0)
        scale = max((abs(w) for w in want), default=1.0) or 1.0
        if d > TOL * max(scale, 1.0):
            print("FAIL %-16s max|Δ|=%.3e  (n=%d)" % (k, d, len(want)))
            if verbose:
                print("   ours:", got[:6], "\n   ref :", want[:6])
            bad += 1
        elif verbose:
            print("ok   %-16s max|Δ|=%.3e" % (k, d))
    total = len(ref)
    print("%s  %d/%d（max|Δ| 容差 %.0e）" % ("通过" if bad == 0 else "失败", total - bad, total, TOL))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
