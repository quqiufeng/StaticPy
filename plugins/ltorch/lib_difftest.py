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

    # ================= v3：一元数学 / 归约 =================
    s: Tensor = b.abs().add_scalar(0.5)
    print("exp=" + b.exp().values())
    print("log=" + s.log().values())
    print("sqrt=" + s.sqrt().values())
    print("abs=" + b.abs().values())
    print("pow=" + s.pow(2.5).values())
    print("t_max=" + str(b.max()))
    print("t_min=" + str(b.min()))
    print("t_std1=" + str(b.std(1)))
    print("t_std0=" + str(b.std(0)))
    print("t_argmax=" + str(b.argmax()))
    print("max_dim=" + b.max_dim(0).values())
    print("argmax_dim=" + b.argmax_dim(1).values())
    print("mean_dim=" + b.mean_dim(0).values())

    # ================= v3：形状 / dtype / 索引 =================
    print("cat0=" + a.cat(b, 0).values())
    print("cat1=" + a.cat(b, 1).values())
    print("stack0=" + a.stack(b, 0).values())
    print("stack1=" + a.stack(b, 1).values())
    print("unsq0=" + a.unsqueeze(0).values())
    sq: Tensor = tensor([1.0, 2.0, 3.0, 4.0], [1, 4])
    print("sq_shape=" + sq.squeeze(0).shape())
    print("sq_vals=" + sq.squeeze(0).values())
    print("zeros_like=" + b.zeros_like().values())
    print("ones_like=" + b.ones_like().values())
    print("empty_like_shape=" + b.empty_like().shape())
    idx: list = []
    idx.append(1)
    idx.append(1)
    idx.append(0)
    print("index_select=" + b.index_select(idx).values())
    print("f32_dtype=" + b.to("float32").dtype())
    print("f32_shape=" + b.to("float32").shape())
    print("i64=" + b.to("int64").values())
    print("base_dtype=" + b.dtype())

    # ================= v3：nn 层 =================
    conv: Conv2d = Conv2d(1, 2, 3, 1, 0, 0)
    conv.load({CW}, {SCW}, {CB}, {SCB})
    xc: Tensor = tensor_from_csv({XC}, {SXC})
    print("conv_y=" + conv.forward(xc).values())
    print("conv_shape=" + conv.forward(xc).shape())
    convp: Conv2d = Conv2d(1, 2, 3, 1, 1, 0)
    convp.load({CW}, {SCW}, {CB}, {SCB})
    print("conv_pad=" + convp.forward(xc).values())
    xp: Tensor = tensor_from_csv({XP}, {SXP})
    print("maxpool=" + MaxPool2d(2, 2).forward(xp).values())
    print("avgpool=" + AvgPool2d(2, 2).forward(xp).values())
    print("flatten_shape=" + Flatten().forward(xp).shape())

    dr: Dropout = Dropout(0.5, 7)
    dr.eval()
    print("drop_eval=" + dr.forward(b).values())
    dr0: Dropout = Dropout(0.0, 7)
    print("drop_p0=" + dr0.forward(b).values())

    bn: BatchNorm1d = BatchNorm1d({NB}, 1e-5)
    bn.load({BNM}, {BNV}, {BNG}, {BNB}, {NB})
    xb: Tensor = tensor_from_csv({XB}, {SXB})
    print("bn=" + bn.forward(xb).values())

    ce: CrossEntropyLoss = CrossEntropyLoss()
    lg: Tensor = tensor_from_csv({LG}, {SLG})
    print("ce=" + ce.forward(lg, {TG}).values())
    emb: Embedding = Embedding(4, 3, 0)
    emb.load({EW}, {SEW})
    print("emb=" + emb.forward({EIDX}).values())
    print("l1loss=" + L1Loss().forward(a, b).values())

    sq1: Linear = Linear(2, 3, 0)
    sq1.load({Q1W}, {SQ1W}, {Q1B}, {SQ1B})
    sq2: Linear = Linear(3, 1, 0)
    sq2.load({Q2W}, {SQ2W}, {Q2B}, {SQ2B})
    net: Sequential = Sequential()
    net.add_linear(sq1)
    net.add_relu()
    net.add_linear(sq2)
    print("seq_y=" + net.forward(xs).values())
    ps: list = net.parameters()
    print("seq_nparams=" + str(len(ps)))

    # ================= v3：优化器（3 步，Adam 的 t 计数要盖住） =================
    o1: Linear = Linear(2, 1, 0)
    o1.load({OW}, {SOW}, {OB}, {SOB})
    ox: Tensor = tensor_from_csv({OX}, {SOX})
    oy: Tensor = tensor_from_csv({OY}, {SOY})
    mse2: MSELoss = MSELoss()
    optm: MomentumSGD = MomentumSGD(o1.parameters(), 0.1, 0.9, 0.0, 0)
    i = 0
    while i < 3:
        optm.zero_grad()
        lm: Tensor = mse2.forward(o1.forward(ox), oy)
        lm.backward()
        optm.step()
        i += 1
    print("opt_momentum_w=" + o1.w.values())
    print("opt_momentum_b=" + o1.b.values())

    o2: Linear = Linear(2, 1, 0)
    o2.load({OW}, {SOW}, {OB}, {SOB})
    opta: Adam = Adam(o2.parameters(), 0.01, 0.9, 0.999, 9.9999999999999995e-09, 0.0)
    i = 0
    while i < 3:
        opta.zero_grad()
        la: Tensor = mse2.forward(o2.forward(ox), oy)
        la.backward()
        opta.step()
        i += 1
    print("opt_adam_w=" + o2.w.values())
    print("opt_adam_b=" + o2.b.values())

    o3: Linear = Linear(2, 1, 0)
    o3.load({OW}, {SOW}, {OB}, {SOB})
    optw: AdamW = AdamW(o3.parameters(), 0.01, 0.9, 0.999, 9.9999999999999995e-09, 0.01)
    i = 0
    while i < 3:
        optw.zero_grad()
        lw: Tensor = mse2.forward(o3.forward(ox), oy)
        lw.backward()
        optw.step()
        i += 1
    print("opt_adamw_w=" + o3.w.values())
    print("opt_adamw_b=" + o3.b.values())

    o4: Linear = Linear(2, 1, 0)
    o4.load({OW}, {SOW}, {OB}, {SOB})
    optr: RMSprop = RMSprop(o4.parameters(), 0.01, 0.99, 9.9999999999999995e-09, 0.0)
    i = 0
    while i < 3:
        optr.zero_grad()
        lr4: Tensor = mse2.forward(o4.forward(ox), oy)
        lr4.backward()
        optr.step()
        i += 1
    print("opt_rmsprop_w=" + o4.w.values())
    print("opt_rmsprop_b=" + o4.b.values())

    # ================= v3：存取 / 梯度模式 =================
    sp: Tensor = tensor([1.5, -2.5, 3.5, 0.0], [2, 2])
    spl: list = []
    spl.append(sp)
    pth: list = []
    pth.append({SPATH})
    print("save_n=" + str(save_state_dict(spl, pth)))
    dst: Tensor = zeros([2, 2])
    dpl: list = []
    dpl.append(dst)
    print("load_n=" + str(load_state_dict(dpl, pth)))
    print("load_vals=" + dst.values())

    print("gradmode_off=" + str(set_grad_enabled(0)))
    print("gradmode_is=" + str(is_grad_enabled()))
    print("gradmode_on=" + str(set_grad_enabled(1)))

    # ================= v4：Adagrad / scheduler / dim 归约 / 类型转换 =================
    o5: Linear = Linear(2, 1, 0)
    o5.load({OW}, {SOW}, {OB}, {SOB})
    optg: Adagrad = Adagrad(o5.parameters(), 0.01)
    i = 0
    while i < 3:
        optg.zero_grad()
        lg: Tensor = mse2.forward(o5.forward(ox), oy)
        lg.backward()
        optg.step()
        i += 1
    print("opt_adagrad_w=" + o5.w.values())
    print("opt_adagrad_b=" + o5.b.values())

    # set_grad：等价 `p.grad = g`，单步 Adagrad（闭式可算，便于定位）
    s1: Tensor = tensor([1.0, 2.0], [1, 2]).requires_grad_(1)
    s1.set_grad(tensor([0.5, -0.25], [1, 2]))
    sl1: list = []
    sl1.append(s1)
    ag1: Adagrad = Adagrad(sl1, 0.01)
    ag1.step()
    print("setgrad_adagrad=" + s1.values())

    # min_dim / argmin_dim
    md: Tensor = tensor([3.0, 1.0, 4.0, 2.0], [2, 2])
    print("min_dim=" + md.min_dim(0).values())
    print("argmin_dim=" + md.argmin_dim(0).values())
    print("min_dim1=" + md.min_dim(1).values())

    # 类型转换
    tc: Tensor = tensor([0.0, 1.5, -2.5, 3.9], [2, 2])
    print("cast_bool_dtype=" + tc.bool().dtype())
    print("cast_bool=" + tc.bool().values())
    print("cast_long=" + tc.long().values())
    print("cast_float_dtype=" + tc.long().float().dtype())

    # lr_scheduler（不持 opt：opt.lr = sch.step()）
    o6: MomentumSGD = MomentumSGD(o5.parameters(), 0.1, 0.0, 0.0, 0)
    st: StepLR = StepLR(0.1, 2, 0.1)
    j = 0
    while j < 5:
        o6.lr = st.step()
        j += 1
    print("steplr=" + str(o6.lr))
    ex: ExponentialLR = ExponentialLR(0.1, 0.5)
    j = 0
    while j < 3:
        o6.lr = ex.step()
        j += 1
    print("explr=" + str(o6.lr))
    ca: CosineAnnealingLR = CosineAnnealingLR(1.0, 4, 0.0)
    j = 0
    while j < 3:
        o6.lr = ca.step()
        j += 1
    print("coslr=" + str(o6.lr))

    # ================= v5：LSTM（单层单向，落 at::lstm） =================
    lx: Tensor = tensor({LX}, [3, 2, 4])
    rec: LSTM = LSTM(4, 5)
    rec.load({LW_IH}, {LW_HH}, {LB_IH}, {LB_HH})
    print("lstm_out=" + rec.forward(lx).values())
    print("lstm_hn=" + rec.final_hidden(lx).values())
    print("lstm_cn=" + rec.final_cell(lx).values())

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

    # ---- v3 用的同源初值（两边都从这些 list 建张量，杜绝 RNG 差异）----
    g2 = torch.Generator().manual_seed(7)
    cw = torch.randn(2, 1, 3, 3, generator=g2, dtype=torch.float64) * 0.4
    cb = [0.1, -0.2]
    xc = [float(i) for i in range(1, 10)]          # 1x1x3x3
    xp = [float(i) for i in range(1, 17)]          # 1x1x4x4
    bn_mean, bn_var = [0.2, -0.1, 0.05], [1.3, 0.7, 2.1]
    bn_gamma, bn_beta = [1.1, 0.9, 1.4], [0.05, -0.03, 0.2]
    xb = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]            # 2x3
    lg = [1.0, 2.0, 0.5, -1.0, 0.0, 3.0, 2.0, 1.0, -2.0]   # 3x3 logits
    ce_t = [0, 2, 1]
    ew = torch.randn(4, 3, generator=g2, dtype=torch.float64) * 0.5
    emb_idx = [2, 0]
    q1w = torch.randn(3, 2, generator=g2, dtype=torch.float64) * 0.6
    q1b = [0.1, -0.1, 0.05]
    q2w = torch.randn(1, 3, generator=g2, dtype=torch.float64) * 0.6
    q2b = [0.2]
    ow = [0.3, -0.4]
    ob = [0.05]
    ox = [1.0, 2.0, 3.0, 4.0, 0.5, -1.0]           # 3x2
    oy = [1.0, 2.0, 3.0]                           # 3x1

    # ---- v5 LSTM：S=3,B=2,I=4,H=5（pairs 与 ref 共用同一份数值）----
    lS, lB, lI, lH = 3, 2, 4, 5
    lw_ih = torch.randn(4 * lH, lI, generator=g2, dtype=torch.float64) * 0.5
    lw_hh = torch.randn(4 * lH, lH, generator=g2, dtype=torch.float64) * 0.5
    lb_ih = torch.randn(4 * lH, generator=g2, dtype=torch.float64) * 0.2
    lb_hh = torch.randn(4 * lH, generator=g2, dtype=torch.float64) * 0.2
    lx = torch.randn(lS, lB, lI, generator=g2, dtype=torch.float64)

    spath = os.path.join(WORK, "saved_param.bin")
    if os.path.exists(spath):
        os.remove(spath)

    pairs = {
        "W1": csv(flat(w1)), "S1": "2,3", "B1": csv(flat(b1)), "SB1": "1,2",
        "XI": csv(xin), "SX": "2,3", "TI": csv(tgt), "ST": "2,2",
        "W2": csv(flat(w2)), "S2": "4,2", "B2": csv(flat(b2)), "SB2": "1,4",
        "W3": csv(flat(w3)), "S3": "1,4", "B3": csv(flat(b3)), "SB3": "1,1",
        "XS": csv(xs), "SXS": "4,2", "YS": csv(ys), "SYS": "4,1",
        # v3
        "CW": csv(flat(cw)), "SCW": "2,1,3,3", "CB": csv(cb), "SCB": "2",
        "XC": csv(xc), "SXC": "1,1,3,3", "XP": csv(xp), "SXP": "1,1,4,4",
        "NB": "3", "BNM": csv(bn_mean), "BNV": csv(bn_var),
        "BNG": csv(bn_gamma), "BNB": csv(bn_beta), "XB": csv(xb), "SXB": "2,3",
        "LG": csv(lg), "SLG": "3,3", "TG": "[" + ",".join(str(i) for i in ce_t) + "]",
        "EW": csv(flat(ew)), "SEW": "4,3",
        "EIDX": "[" + ",".join(str(i) for i in emb_idx) + "]",
        "Q1W": csv(flat(q1w)), "SQ1W": "3,2", "Q1B": csv(q1b), "SQ1B": "1,3",
        "Q2W": csv(flat(q2w)), "SQ2W": "1,3", "Q2B": csv(q2b), "SQ2B": "1,1",
        "OW": csv(ow), "SOW": "1,2", "OB": csv(ob), "SOB": "1,1",
        "OX": csv(ox), "SOX": "3,2", "OY": csv(oy), "SOY": "3,1",
        "SPATH": '"' + spath + '"',
        "LX": "[" + csv(flat(lx)) + "]", "LW_IH": csv(flat(lw_ih)), "LW_HH": csv(flat(lw_hh)),
        "LB_IH": csv(flat(lb_ih)), "LB_HH": csv(flat(lb_hh)),
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

    # ---------------- v3：一元数学 / 归约 ----------------
    F = torch.nn.functional
    s = torch.abs(b) + 0.5
    ref["exp"] = flat(torch.exp(b))
    ref["log"] = flat(torch.log(s))
    ref["sqrt"] = flat(torch.sqrt(s))
    ref["abs"] = flat(torch.abs(b))
    ref["pow"] = flat(s ** 2.5)
    ref["t_max"] = [float(b.max())]
    ref["t_min"] = [float(b.min())]
    ref["t_std1"] = [float(b.std(unbiased=True))]
    ref["t_std0"] = [float(b.std(unbiased=False))]
    ref["t_argmax"] = [float(torch.argmax(b))]
    ref["max_dim"] = flat(torch.max(b, dim=0).values)
    ref["argmax_dim"] = flat(torch.argmax(b, dim=1))
    ref["mean_dim"] = flat(b.mean(dim=0))

    # ---------------- v3：形状 / dtype / 索引 ----------------
    ref["cat0"] = flat(torch.cat([a, b], 0))
    ref["cat1"] = flat(torch.cat([a, b], 1))
    ref["stack0"] = flat(torch.stack([a, b], 0))
    ref["stack1"] = flat(torch.stack([a, b], 1))
    ref["unsq0"] = flat(a.unsqueeze(0))
    sq = T([1.0, 2.0, 3.0, 4.0], (1, 4)).squeeze(0)
    ref["sq_shape"] = [float(d) for d in sq.shape]
    ref["sq_vals"] = flat(sq)
    ref["zeros_like"] = [0.0] * 4
    ref["ones_like"] = [1.0] * 4
    ref["empty_like_shape"] = [2.0, 2.0]
    ref["index_select"] = flat(torch.index_select(b, 0, torch.tensor([1, 1, 0])))
    ref["f32_dtype"] = str(torch.float32)   # torch 口径：'torch.float32'
    ref["f32_shape"] = [2.0, 2.0]
    ref["i64"] = flat(b.to(torch.int64))
    ref["base_dtype"] = str(b.dtype)        # 'torch.float64'

    # ---------------- v3：nn 层 ----------------
    cw4 = cw
    cb1 = T(cb, (2,))
    xc4 = T(xc, (1, 1, 3, 3))
    ref["conv_y"] = flat(F.conv2d(xc4, cw4, cb1))
    ref["conv_shape"] = [1.0, 2.0, 1.0, 1.0]
    ref["conv_pad"] = flat(F.conv2d(xc4, cw4, cb1, stride=1, padding=1))
    xp4 = T(xp, (1, 1, 4, 4))
    ref["maxpool"] = flat(F.max_pool2d(xp4, 2, 2))
    ref["avgpool"] = flat(F.avg_pool2d(xp4, 2, 2))
    ref["flatten_shape"] = [1.0, 16.0]
    ref["drop_eval"] = flat(b)
    ref["drop_p0"] = flat(b)
    xb2 = T(xb, (2, 3))
    ref["bn"] = flat(F.batch_norm(xb2, T(bn_mean, (3,)), T(bn_var, (3,)),
                                  T(bn_gamma, (3,)), T(bn_beta, (3,)),
                                  training=False, momentum=0.0, eps=1e-5))
    ref["ce"] = [float(F.cross_entropy(T(lg, (3, 3)), torch.tensor(ce_t)))]
    ref["emb"] = flat(torch.index_select(ew, 0, torch.tensor(emb_idx)))
    ref["l1loss"] = [float((a - b).abs().mean())]
    hseq = T(xs, (4, 2)) @ q1w.T + T(q1b, (1, 3))
    ref["seq_y"] = flat(torch.relu(hseq) @ q2w.T + T(q2b, (1, 1)))
    ref["seq_nparams"] = [4.0]

    # ---------------- v3：优化器（同初值 3 步）----------------
    def opt_run(ctor):
        w = T(ow, (1, 2)).requires_grad_(True)
        bb = T(ob, (1, 1)).requires_grad_(True)
        X = T(ox, (3, 2))
        Y = T(oy, (3, 1))
        opt = ctor([w, bb])
        for _ in range(3):
            opt.zero_grad()
            ((X @ w.T + bb - Y) ** 2).mean().backward()
            opt.step()
        return flat(w.detach()), flat(bb.detach())

    for name, ctor in (
        ("momentum", lambda p: torch.optim.SGD(p, lr=0.1, momentum=0.9)),
        ("adam", lambda p: torch.optim.Adam(p, lr=0.01, eps=1e-8)),
        ("adamw", lambda p: torch.optim.AdamW(p, lr=0.01, eps=1e-8, weight_decay=0.01)),
        ("rmsprop", lambda p: torch.optim.RMSprop(p, lr=0.01, alpha=0.99, eps=1e-8)),
    ):
        wv, bv = opt_run(ctor)
        ref["opt_%s_w" % name] = wv
        ref["opt_%s_b" % name] = bv

    # ---------------- v3：存取 / 梯度模式 ----------------
    ref["save_n"] = [1.0]
    ref["load_n"] = [1.0]
    ref["load_vals"] = [1.5, -2.5, 3.5, 0.0]
    ref["gradmode_off"] = [0.0]
    ref["gradmode_is"] = [0.0]
    ref["gradmode_on"] = [1.0]

    # ---------------- v4：Adagrad / scheduler / dim 归约 / 类型转换 ----------------
    wv, bv = opt_run(lambda p: torch.optim.Adagrad(p, lr=0.01))
    ref["opt_adagrad_w"] = wv
    ref["opt_adagrad_b"] = bv

    _s = torch.tensor([1.0, 2.0], dtype=torch.float64, requires_grad=True)
    _s.grad = torch.tensor([0.5, -0.25], dtype=torch.float64)
    torch.optim.Adagrad([_s], lr=0.01).step()
    ref["setgrad_adagrad"] = flat(_s.detach())

    _md = T([3.0, 1.0, 4.0, 2.0], (2, 2))
    ref["min_dim"] = flat(_md.min(dim=0).values)
    ref["argmin_dim"] = [float(x) for x in _md.argmin(dim=0).tolist()]
    ref["min_dim1"] = flat(_md.min(dim=1).values)

    _tc = T([0.0, 1.5, -2.5, 3.9], (2, 2))
    ref["cast_bool_dtype"] = str(_tc.bool().dtype)
    ref["cast_bool"] = [float(x) for x in _tc.bool().reshape(-1).tolist()]
    ref["cast_long"] = [float(x) for x in _tc.long().reshape(-1).tolist()]
    ref["cast_float_dtype"] = str(_tc.long().float().dtype)

    _o = torch.optim.SGD([torch.zeros(1, dtype=torch.float64)], lr=0.1)
    _st = torch.optim.lr_scheduler.StepLR(_o, step_size=2, gamma=0.1)
    for _ in range(5):
        _o.step()
        _st.step()
    ref["steplr"] = [_o.param_groups[0]["lr"]]
    _o3 = torch.optim.SGD([torch.zeros(1, dtype=torch.float64)], lr=0.1)
    _ex = torch.optim.lr_scheduler.ExponentialLR(_o3, gamma=0.5)
    for _ in range(3):
        _o3.step()
        _ex.step()
    ref["explr"] = [_o3.param_groups[0]["lr"]]
    _o2 = torch.optim.SGD([torch.zeros(1, dtype=torch.float64)], lr=1.0)
    _ca = torch.optim.lr_scheduler.CosineAnnealingLR(_o2, T_max=4, eta_min=0.0)
    for _ in range(3):
        _o2.step()
        _ca.step()
    ref["coslr"] = [_o2.param_groups[0]["lr"]]

    # ---------------- v5：LSTM ----------------
    _lstm = torch.nn.LSTM(lI, lH, dtype=torch.float64)
    with torch.no_grad():
        _lstm.weight_ih_l0.copy_(lw_ih)
        _lstm.weight_hh_l0.copy_(lw_hh)
        _lstm.bias_ih_l0.copy_(lb_ih)
        _lstm.bias_hh_l0.copy_(lb_hh)
    _lout, (_lhn, _lcn) = _lstm(lx)
    ref["lstm_out"] = flat(_lout.detach())
    ref["lstm_hn"] = flat(_lhn.detach())
    ref["lstm_cn"] = flat(_lcn.detach())

    # ---------------- 比对 ----------------
    bad = 0
    for k, want in ref.items():
        got = ours.get(k)
        if got is None:
            print("FAIL %-16s 缺失（%r）" % (k, got))
            bad += 1
            continue
        if isinstance(want, str) or isinstance(got, str):
            if str(got) != str(want):
                print("FAIL %-16s 字符串 %r vs %r" % (k, got, want))
                bad += 1
            elif verbose:
                print("ok   %-16s %s" % (k, want))
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
