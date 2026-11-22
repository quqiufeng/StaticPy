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
def join8(ns: list) -> str:
    s: str = ""
    i: int = 0
    while i < len(ns):
        if i > 0:
            s = s + ","
        s = s + ns[i]
        i += 1
    return s


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
    bn.eval()        # 推理分支：用灌入的 running mean/var（对标 training=False）
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

    # ================= v6：state_dict 协议 / 整模型存取 =================
    ck: Linear = Linear(3, 2, 31)
    ck.load({W1}, {S1}, {B1}, {SB1})
    print("ck_nparams=" + str(len(ck.parameters())))
    print("ck_sd_nkeys=" + str(len(ck.state_dict())))
    ck_w: Tensor = ck.param("weight")          # 键面照 torch：Linear 就是 weight/bias
    print("ck_sd_w=" + ck_w.values())
    ck_b: Tensor = ck.param_at(1)
    print("ck_pat_b=" + ck_b.values())
    ckpath: str = "/home/quqiufeng/iso_gen/ck6/model"
    print("ck_save=" + str(ck.save(ckpath)))
    z6: Tensor = zeros([1, 2])
    torchc_copy_into(ck_b.h, z6.h)
    print("ck_after_zero=" + ck_b.values())
    print("ck_load=" + str(ck.load_ckpt(ckpath)))
    print("ck_after_load=" + ck_b.values())
    # 优化器 state_dict：只装标量超参（对齐 torch param_groups 视图）
    o6p: list = ck.parameters()
    ad6: Adam = Adam(o6p, 0.003, 0.85, 0.995, 1e-07, 0.02)
    ad6.t = 7
    asd: dict = ad6.state_dict()
    print("adam_sd_lr=" + str(asd["lr"]))
    print("adam_sd_beta2=" + str(asd["beta2"]))
    print("adam_sd_wd=" + str(asd["weight_decay"]))
    print("adam_sd_t=" + str(asd["t"]))
    ad7: Adam = Adam(o6p, 0.1)
    ad7.load_state_dict(asd)
    print("adam_restored_lr=" + str(ad7.lr))
    print("adam_restored_t=" + str(ad7.t))
    ga6: Adagrad = Adagrad(o6p, 0.02, 0.1, 0.001, 1e-09)
    gsd: dict = ga6.state_dict()
    print("adagrad_sd_lr_decay=" + str(gsd["lr_decay"]))
    print("adagrad_sd_wd=" + str(gsd["weight_decay"]))
    ga7: Adagrad = Adagrad(o6p, 0.5)
    ga7.load_state_dict(gsd)
    print("adagrad_restored_lr=" + str(ga7.lr))

    # ================= v7：BatchNorm1d 训练态（batch 统计 + running 更新） =================
    bn7: BatchNorm1d = BatchNorm1d(3, 1e-05, 0.1)
    bn7.load({BN7M}, {BN7V}, {BNG}, {BNB}, 3)
    xbt: Tensor = tensor_from_csv({XBT}, {SXBT})
    bn7.train()
    o7a: Tensor = bn7.forward(xbt)
    print("bn7_y1=" + o7a.values())
    print("bn7_rm1=" + bn7.running_mean().values())
    print("bn7_rv1=" + bn7.running_var().values())
    o7b: Tensor = bn7.forward(xbt.mul_scalar(2.0))
    print("bn7_y2=" + o7b.values())
    print("bn7_rm2=" + bn7.running_mean().values())
    print("bn7_rv2=" + bn7.running_var().values())
    bn7path: str = "/home/quqiufeng/iso_gen/ck7/bn"
    print("bn7_save=" + str(bn7.save(bn7path)))
    z7: Tensor = zeros([3])
    torchc_copy_into(bn7.running_mean().h, z7.h)
    print("bn7_rm_zeroed=" + bn7.running_mean().values())
    print("bn7_load=" + str(bn7.load_ckpt(bn7path)))
    print("bn7_rm_loaded=" + bn7.running_mean().values())
    print("bn7_rv_loaded=" + bn7.running_var().values())
    bn7.eval()
    print("bn7_y_eval=" + bn7.forward(xbt).values())
    print("bn7_nparams=" + str(len(bn7.parameters())))
    # 同一个 BN 进 Sequential：add_bn 的派发 + model.train()/eval() 传播
    sq7: Sequential = Sequential()
    sq7.add_linear(Linear(3, 3, 0))
    sq7.add_bn(bn7)
    print("sq7_nparams=" + str(len(sq7.parameters())))
    sq7.train()          # 只验通路（Linear 权重随机，数值不可比）
    q7a: Tensor = sq7.forward(xbt)
    sq7.eval()
    q7b: Tensor = sq7.forward(xbt)
    print("sq7_shapes=" + q7a.shape() + "|" + q7b.shape())

    # ================= v8：torch 键面对齐（嵌套子层编号 + BN buffer） =================
    # （a）键面：与训练模板同形 Sequential(Linear, BN, ReLU, Dropout, Linear)
    m8: Sequential = Sequential()
    bn8: BatchNorm1d = BatchNorm1d(4, 1e-05, 0.1)
    m8.add_linear(Linear(3, 4, 41))
    m8.add_bn(bn8)
    m8.add_relu()
    m8.add_dropout(Dropout(0.1, 42))
    m8.add_linear(Linear(4, 2, 43))
    print("sd8_nkeys=" + str(len(m8.state_dict())))
    print("sd8_keys=" + join8(m8.state_names()))
    print("sd8_nstate=" + str(len(m8.state_list())))
    m8path: str = "/home/quqiufeng/iso_gen/ck8/m"
    print("sd8_save=" + str(m8.save(m8path)))
    print("sd8_load=" + str(m8.load_ckpt(m8path)))
    # （b）数值：BN 打头，running stats 吃同一份输入（Linear 权重随机，不可比）
    m8b: Sequential = Sequential()
    bnb: BatchNorm1d = BatchNorm1d(3, 1e-05, 0.1)
    m8b.add_bn(bnb)
    m8b.add_relu()
    m8b.add_dropout(Dropout(0.1, 44))
    m8b.add_linear(Linear(3, 2, 45))
    print("sd8b_keys=" + join8(m8b.state_names()))
    x8: Tensor = tensor_from_csv({X8}, {SX8})
    m8b.forward(x8)
    m8b.forward(x8)
    print("sd8b_nbt=" + str(bnb.param("num_batches_tracked").item()))
    print("sd8b_rm=" + bnb.param("running_mean").values())
    print("sd8b_rv=" + bnb.param("running_var").values())
    print("sd8b_ngamma=" + str(bnb.param("weight").numel()))

    # ================= v9：Sequential 里的 CNN（Conv2d+MaxPool2d+Flatten） =================
    # 键面 = torch 的嵌套编号（0.weight / 0.bias / 4.weight / 4.bias），前向与 torch 逐值比
    sq9: Sequential = Sequential()
    c9: Conv2d = Conv2d(1, 2, 3, 1, 1, 0)
    c9.load({CW}, {SCW}, {CB}, {SCB})
    sq9.add_conv(c9)
    sq9.add_relu()
    sq9.add_maxpool(MaxPool2d(2, 2))
    sq9.add_flatten()
    l9: Linear = Linear(8, 3, 0)
    l9.load({W9}, {S9}, {B9}, {SB9})
    sq9.add_linear(l9)
    print("cnn9_keys=" + join8(sq9.state_names()))
    print("cnn9_nkeys=" + str(len(sq9.state_dict())))
    print("cnn9_nparams=" + str(len(sq9.parameters())))
    print("cnn9_y=" + sq9.forward(tensor_from_csv({XP}, {SXP})).values())
    print("cnn9_convw=" + str(sq9.param_by("0.weight").numel()))
    print("cnn9_linw=" + str(sq9.param_by("4.weight").numel()))

    # ================= v10：Transformer / 分类必需面 =================
    # （a）Tensor 方法层：chunk 与 F.* 逐值比
    x10: Tensor = tensor_from_csv({X10}, {SX10})
    print("t10_clamp=" + x10.clamp(-0.75, 1.25).values())
    print("t10_logsoftmax=" + x10.log_softmax(1).values())
    print("t10_gelu=" + x10.gelu().values())
    print("t10_gelu_ap=" + x10.gelu_approx().values())
    print("t10_leaky=" + x10.leaky_relu(0.13).values())
    print("t10_cumsum0=" + x10.cumsum(0).values())
    print("t10_cumsum1=" + x10.cumsum(1).values())
    print("t10_norm1=" + str(x10.norm_p(1.0)))
    print("t10_norm2=" + str(x10.norm_p(2.0)))
    print("t10_norm3=" + str(x10.norm_p(3.0)))
    mk10: Tensor = tensor_from_csv({MK10}, {SMK10})
    print("t10_masked=" + x10.masked_fill(mk10, -1000.0).values())
    # （b）nn 类单层前向
    ge10: GELU = GELU()
    print("n10_gelu=" + ge10.forward(x10).values())
    ga10: GELU = GELU()
    ga10.approx = 1
    print("n10_gelu_ap=" + ga10.forward(x10).values())
    lr10: LeakyReLU = LeakyReLU(0.13)
    print("n10_leaky=" + lr10.forward(x10).values())
    sm10: Softmax = Softmax(-1)
    print("n10_softmax=" + sm10.forward(x10).values())
    ls10: LogSoftmax = LogSoftmax(1)
    print("n10_logsoft=" + ls10.forward(x10).values())
    ln10: LayerNorm = LayerNorm(4, 1e-05)
    ln10.load({LN10W}, {LN10B})
    print("n10_ln=" + ln10.forward(x10).values())
    print("n10_ln_nparams=" + str(len(ln10.parameters())))
    # （c）损失
    nl10: NLLLoss = NLLLoss()
    lgt10: Tensor = tensor_from_csv({LG}, {SLG})
    print("n10_nll=" + str(nl10.forward(lgt10, {TG}).item()))
    bc10: BCEWithLogitsLoss = BCEWithLogitsLoss()
    bp10: Tensor = tensor_from_csv({BP10}, {SBP10})
    bt10: Tensor = tensor_from_csv({BT10}, {SBT10})
    print("n10_bce=" + str(bc10.forward(bp10, bt10).item()))
    # （d）Sequential 里的 Linear→LayerNorm→GELU→Linear（键面照 torch 编号，前向逐值）
    l10a: Linear = Linear(4, 3, 0)
    l10a.load({W10A}, {S10A}, {B10A}, {SB10A})
    l10b: Linear = Linear(3, 2, 0)
    l10b.load({W10B}, {S10B}, {B10B}, {SB10B})
    ln10b: LayerNorm = LayerNorm(3, 1e-05)
    ln10b.load({LN10WB}, {LN10BB})
    sq10: Sequential = Sequential()
    sq10.add_linear(l10a)
    sq10.add_layernorm(ln10b)
    sq10.add_gelu()
    sq10.add_linear(l10b)
    print("sq10_keys=" + join8(sq10.state_names()))
    print("sq10_nkeys=" + str(len(sq10.state_dict())))
    print("sq10_nparams=" + str(len(sq10.parameters())))
    print("sq10_y=" + sq10.forward(x10).values())
    print("sq10_lnw=" + str(sq10.param_by("1.weight").numel()))

    # ================= v11：MultiheadAttention（L=3, E=4, H=2 自注意力）=================
    xm11: Tensor = tensor_from_csv({XM11}, {SXM11})
    mh11: MultiheadAttention = MultiheadAttention(4, 2, 0)
    mh11.load_qkv({WQ11}, {WK11}, {WV11}, "4,4", {BQ11}, {BK11}, {BV11}, "1,4")
    mh11.load_out({WO11}, "4,4", {BO11}, "1,4")
    print("m11_attn=" + mh11.attn_weights(xm11).values())
    print("m11_y=" + mh11.forward(xm11).values())
    # torch 把 q/k/v 打包成 in_proj_weight(3E,E) 一个张量；我们拆成 wq/wk/wv 三块，
    # 所以「张量个数」是 8 vs 4，「状态键面」才是可比的口径（都是 4 项）。
    print("m11_nparams=" + str(len(mh11.parameters())))
    print("m11_nsplit=" + str(len(mh11.parameters())))
    print("m11_nstate=" + str(len(mh11.state_dict())))
    print("m11_keys=" + join8(mh11.state_names()))
    print("m11_wqnumel=" + str(mh11.param("in_proj_weight.q").numel()))
    # ================= v12：索引 / 形状面（select / narrow / repeat / expand / t / dot）===
    print("t12_select1=" + xm11.select(1, 2).values())
    print("t12_select0=" + xm11.select(0, 1).values())
    print("t12_narrow0=" + xm11.narrow(0, 1, 2).values())
    print("t12_narrow1=" + xm11.narrow(1, 1, 2).values())
    print("t12_repeat=" + xm11.repeat([2, 1]).values())
    n12: Tensor = xm11.narrow(0, 0, 1)
    print("t12_expand=" + n12.expand([2, 4]).values())
    print("t12_t=" + xm11.t().values())
    v12: Tensor = tensor_from_csv({V12}, "4")
    print("t12_dot=" + str(v12.dot(v12)))
    # ================= v13：梯度范数 / 裁剪 =================
    w13: Tensor = tensor_from_csv({W13}, "2,3").requires_grad_(1)
    b13: Tensor = tensor_from_csv({B13}, "1,2").requires_grad_(1)
    x13: Tensor = tensor_from_csv({X13}, "2,3")
    t13: Tensor = tensor_from_csv({T13}, "2,2")
    y13: Tensor = x13.matmul(w13.transpose(0, 1)).add(b13)
    d13: Tensor = y13.sub(t13)
    l13: Tensor = d13.mul(d13).mean()
    l13.backward()
    print("g13_norm=" + str(grad_norm([w13, b13])))
    print("g13_gw=" + w13.grad_values())
    print("g13_gb=" + b13.grad_values())
    print("g13_clip=" + str(clip_grad_norm([w13, b13], 0.05)))
    print("g13_gw_after=" + w13.grad_values())
    print("g13_gb_after=" + b13.grad_values())
    print("g13_clip2=" + str(clip_grad_norm([w13, b13], 100.0)))
    print("g13_gw_idem=" + w13.grad_values())
    # ================= v14：CSV 读数 =================
    d14: Tensor = load_csv("/home/quqiufeng/iso_gen/lt/csv14/d.csv")
    sh14: str = d14.shape()
    print("t14_shape=" + sh14)
    print("t14_vals=" + d14.values())
    mh11.zero_grad()
    ly11: Tensor = mh11.forward(xm11).mean()
    ly11.backward()
    print("m11_gwq=" + mh11.wq.grad_values())
    print("m11_gwo=" + mh11.wo.grad_values())

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
    _g9 = torch.Generator().manual_seed(29)
    w9 = torch.randn(3, 8, generator=_g9, dtype=torch.float64) * 0.5
    b9 = [0.1, -0.1, 0.05]
    xc = [float(i) for i in range(1, 10)]          # 1x1x3x3
    xp = [float(i) for i in range(1, 17)]          # 1x1x4x4
    bn_mean, bn_var = [0.2, -0.1, 0.05], [1.3, 0.7, 2.1]
    bn_gamma, bn_beta = [1.1, 0.9, 1.4], [0.05, -0.03, 0.2]
    bn7_mu, bn7_va = [0.1, -0.2, 0.3], [0.9, 1.1, 0.7]
    xbt_v = [1.0, 2.0, 3.0, 4.5, -1.0, 2.5, 0.0, 3.0, -2.0, 2.0, 1.0, 0.5]   # 4x3
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

    # ---- v10：Transformer / 分类必需面（3x4 输入，mask/权重全灌进去）----
    x10_v = [0.5, -1.5, 2.0, 3.5, -0.25, 0.75, -2.5, 1.0, 4.0, -3.0, 0.5, 0.25]
    mk10_v = [0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0]
    ln10_w = [1.2, 0.8, -1.1, 0.6]
    ln10_b = [0.1, -0.2, 0.05, 0.0]
    bp10_v = [2.0, -1.5, 0.25]
    bt10_v = [1.0, 0.0, 1.0]
    w10a = torch.randn(3, 4, generator=g2, dtype=torch.float64) * 0.5
    b10a = [0.1, -0.05, 0.2]
    w10b = torch.randn(2, 3, generator=g2, dtype=torch.float64) * 0.5
    b10b = [0.05, -0.1]
    ln10_wb = [1.1, 0.9, 1.3]
    ln10_bb = [0.0, 0.1, -0.05]

    # ---- v11 MHA：L=3, E=4, H=2（q/k/v/out 四组权重全由 torch 生成后灌入）----
    xm11_v = [0.7, -1.2, 2.3, 0.4, -0.8, 1.5, 0.2, -2.1, 1.9, 0.6, -0.5, 1.1]
    # ---- v13：梯度范数 / 裁剪（Linear 单步 backward 后裁剪）----
    w13_v = torch.randn(2, 3, generator=g2, dtype=torch.float64) * 0.9
    b13_v = [0.3, -0.7]
    x13_v = [1.0, -0.5, 2.0, 0.25, 1.5, -1.0]
    t13_v = [0.5, -1.0, 2.5, 0.0]
    wq11 = torch.randn(4, 4, generator=g2, dtype=torch.float64) * 0.5
    wk11 = torch.randn(4, 4, generator=g2, dtype=torch.float64) * 0.5
    wv11 = torch.randn(4, 4, generator=g2, dtype=torch.float64) * 0.5
    wo11 = torch.randn(4, 4, generator=g2, dtype=torch.float64) * 0.5
    bq11 = torch.randn(4, generator=g2, dtype=torch.float64) * 0.1
    bk11 = torch.randn(4, generator=g2, dtype=torch.float64) * 0.1
    bv11 = torch.randn(4, generator=g2, dtype=torch.float64) * 0.1
    bo11 = torch.randn(4, generator=g2, dtype=torch.float64) * 0.1

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
        "BN7M": csv(bn7_mu), "BN7V": csv(bn7_va),
        "XBT": csv(xbt_v), "SXBT": "4,3",
        "X8": csv(xbt_v), "SX8": "4,3",
        # v9
        "W9": csv(flat(w9)), "S9": "3,8", "B9": csv(b9), "SB9": "1,3",
        # v10
        "X10": csv(x10_v), "SX10": "3,4", "MK10": csv(mk10_v), "SMK10": "3,4",
        "LN10W": csv(ln10_w), "LN10B": csv(ln10_b),
        "BP10": csv(bp10_v), "SBP10": "3,1", "BT10": csv(bt10_v), "SBT10": "3,1",
        "W10A": csv(flat(w10a)), "S10A": "3,4", "B10A": csv(b10a), "SB10A": "1,3",
        "W10B": csv(flat(w10b)), "S10B": "2,3", "B10B": csv(b10b), "SB10B": "1,2",
        "LN10WB": csv(ln10_wb), "LN10BB": csv(ln10_bb),
        # v11
        "XM11": csv(xm11_v), "SXM11": "3,4",
        "V12": csv([0.5, -1.5, 2.25, 3.0]),
        "W13": csv(flat(w13_v)), "B13": csv(b13_v),
        "X13": csv(x13_v), "T13": csv(t13_v),
        "WQ11": csv(flat(wq11)), "WK11": csv(flat(wk11)), "WV11": csv(flat(wv11)),
        "BQ11": csv(flat(bq11)), "BK11": csv(flat(bk11)), "BV11": csv(flat(bv11)),
        "WO11": csv(flat(wo11)), "BO11": csv(flat(bo11)),
    }
    # v14 的 CSV 必须在跑 ELF **之前**落盘（驱动进程写，ref 进程只对齐数字）
    _csvdir = os.path.join(WORK, "csv14")
    os.makedirs(_csvdir, exist_ok=True)
    with open(os.path.join(_csvdir, "d.csv"), "w") as _f:
        _f.write("x1,x2,y\n1.0, 2.0 ,0\n-0.5,3.5,1\n#comment\n4.0,5.0\n6.0,-7.5,2\n")

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

    # ---------------- v6：state_dict 协议 ----------------
    _m6 = torch.nn.Linear(3, 2, dtype=torch.float64)
    with torch.no_grad():
        _m6.weight.copy_(w1)
        _m6.bias.copy_(b1[0])
    ref["ck_nparams"] = [2.0]
    ref["ck_sd_nkeys"] = [float(len(_m6.state_dict()))]   # torch 也是 weight/bias 两个键
    ref["ck_sd_w"] = flat(_m6.weight)
    ref["ck_pat_b"] = flat(_m6.bias)
    ref["ck_save"] = [2.0]
    ref["ck_after_zero"] = [0.0, 0.0]
    ref["ck_load"] = [2.0]
    ref["ck_after_load"] = flat(_m6.bias)
    _a6 = torch.optim.Adam(_m6.parameters(), lr=0.003, betas=(0.85, 0.995),
                           eps=1e-07, weight_decay=0.02)
    _g6 = _a6.param_groups[0]
    ref["adam_sd_lr"] = [float(_g6["lr"])]
    ref["adam_sd_beta2"] = [float(_g6["betas"][1])]
    ref["adam_sd_wd"] = [float(_g6["weight_decay"])]
    ref["adam_sd_t"] = [7.0]          # 探针里 t 置 7，等价「第 7 步」
    ref["adam_restored_lr"] = [0.003]  # load_state_dict 覆盖构造时的 0.1
    ref["adam_restored_t"] = [7.0]
    _a7 = torch.optim.Adagrad(_m6.parameters(), lr=0.02, lr_decay=0.1, weight_decay=0.001, eps=1e-09)
    _g7 = _a7.param_groups[0]
    ref["adagrad_sd_lr_decay"] = [float(_g7["lr_decay"])]
    ref["adagrad_sd_wd"] = [float(_g7["weight_decay"])]
    ref["adagrad_restored_lr"] = [0.02]

    # ---------------- v7：BatchNorm1d 训练态 ----------------
    _bn7 = torch.nn.BatchNorm1d(3, eps=1e-05, momentum=0.1)
    with torch.no_grad():
        _bn7.running_mean.copy_(T(bn7_mu, (3,)))
        _bn7.running_var.copy_(T(bn7_va, (3,)))
        _bn7.weight.copy_(T(bn_gamma, (3,)))
        _bn7.bias.copy_(T(bn_beta, (3,)))
    _bn7.train()
    xbt = T(xbt_v, (4, 3))
    ref["bn7_y1"] = flat(_bn7(xbt))
    ref["bn7_rm1"] = flat(_bn7.running_mean)
    ref["bn7_rv1"] = flat(_bn7.running_var)
    ref["bn7_y2"] = flat(_bn7(xbt * 2.0))
    ref["bn7_rm2"] = flat(_bn7.running_mean)
    ref["bn7_rv2"] = flat(_bn7.running_var)
    _bn7.eval()
    ref["bn7_y_eval"] = flat(_bn7(xbt))
    ref["bn7_save"] = [5.0]      # gamma,beta + mean,var + num_batches_tracked
    ref["bn7_rm_zeroed"] = [0.0, 0.0, 0.0]
    ref["bn7_load"] = [5.0]
    ref["bn7_rm_loaded"] = ref["bn7_rm2"]      # 存盘点上的 running_mean
    ref["bn7_rv_loaded"] = ref["bn7_rv2"]
    ref["bn7_nparams"] = [2.0]
    # Sequential(Linear, BN)：Linear 权重随机不可比 → 只比参数个数与 eval/train 形状
    ref["sq7_nparams"] = [4.0]
    ref["sq7_shapes"] = "4,3|4,3"

    # ---------------- v8：torch 键面 ----------------
    _m8 = torch.nn.Sequential(torch.nn.Linear(3, 4), torch.nn.BatchNorm1d(4, 1e-05, 0.1),
                              torch.nn.ReLU(), torch.nn.Dropout(0.1), torch.nn.Linear(4, 2))
    _k8 = list(_m8.state_dict().keys())
    ref["sd8_nkeys"] = [float(len(_k8))]
    ref["sd8_keys"] = ",".join(_k8)
    ref["sd8_nstate"] = [float(len(_k8))]
    ref["sd8_save"] = [float(len(_k8))]
    ref["sd8_load"] = [float(len(_k8))]
    _m8b = torch.nn.Sequential(torch.nn.BatchNorm1d(3, 1e-05, 0.1), torch.nn.ReLU(),
                               torch.nn.Dropout(0.1), torch.nn.Linear(3, 2))
    ref["sd8b_keys"] = ",".join(_m8b.state_dict().keys())
    _x8 = T(xbt_v, (4, 3))
    _m8b(_x8)
    _m8b(_x8)
    ref["sd8b_nbt"] = [float(_m8b[0].num_batches_tracked)]
    ref["sd8b_rm"] = flat(_m8b[0].running_mean)
    ref["sd8b_rv"] = flat(_m8b[0].running_var)
    ref["sd8b_ngamma"] = [float(_m8b[0].weight.numel())]

    # ---------------- v9：Sequential 里的 CNN ----------------
    _c9 = torch.nn.Conv2d(1, 2, 3, padding=1, dtype=torch.float64)
    with torch.no_grad():
        _c9.weight.copy_(cw.reshape(2, 1, 3, 3))
        _c9.bias.copy_(T(cb, (2,)))
    _l9 = torch.nn.Linear(8, 3, dtype=torch.float64)
    with torch.no_grad():
        _l9.weight.copy_(w9)
        _l9.bias.copy_(T(b9, (3,)))
    _m9 = torch.nn.Sequential(_c9, torch.nn.ReLU(), torch.nn.MaxPool2d(2),
                              torch.nn.Flatten(), _l9)
    _k9 = list(_m9.state_dict().keys())
    ref["cnn9_keys"] = ",".join(_k9)
    ref["cnn9_nkeys"] = [float(len(_k9))]
    ref["cnn9_nparams"] = [float(len(_k9))]
    ref["cnn9_y"] = flat(_m9(T(xp, (1, 1, 4, 4))))
    ref["cnn9_convw"] = [float(_c9.weight.numel())]
    ref["cnn9_linw"] = [float(_l9.weight.numel())]

    # ---------------- v10：Transformer / 分类必需面 ----------------
    _x10 = T(x10_v, (3, 4))
    ref["t10_clamp"] = flat(torch.clamp(_x10, -0.75, 1.25))
    ref["t10_logsoftmax"] = flat(F.log_softmax(_x10, dim=1))
    ref["t10_gelu"] = flat(F.gelu(_x10))
    ref["t10_gelu_ap"] = flat(F.gelu(_x10, approximate="tanh"))
    ref["t10_leaky"] = flat(F.leaky_relu(_x10, 0.13))
    ref["t10_cumsum0"] = flat(torch.cumsum(_x10, 0))
    ref["t10_cumsum1"] = flat(torch.cumsum(_x10, 1))
    ref["t10_norm1"] = [float(torch.norm(_x10, 1.0))]
    ref["t10_norm2"] = [float(torch.norm(_x10, 2.0))]
    ref["t10_norm3"] = [float(torch.norm(_x10, 3.0))]
    _mk10 = torch.tensor(mk10_v, dtype=torch.float64).reshape(3, 4) > 0.5
    ref["t10_masked"] = flat(_x10.masked_fill(_mk10, -1000.0))
    _xm11 = T(xm11_v, (3, 4))
    ref["t12_select1"] = flat(_xm11.select(1, 2))
    ref["t12_select0"] = flat(_xm11.select(0, 1))
    ref["t12_narrow0"] = flat(_xm11.narrow(0, 1, 2))
    ref["t12_narrow1"] = flat(_xm11.narrow(1, 1, 2))
    ref["t12_repeat"] = flat(_xm11.repeat(2, 1))
    ref["t12_expand"] = flat(_xm11.narrow(0, 0, 1).expand(2, 4))
    ref["t12_t"] = flat(_xm11.t())
    _v12 = T([0.5, -1.5, 2.25, 3.0], (4,))
    ref["t12_dot"] = [float(torch.dot(_v12, _v12))]
    _w13 = T(flat(w13_v), (2, 3)).requires_grad_(True)
    _b13 = T(b13_v, (1, 2)).requires_grad_(True)
    _x13 = T(x13_v, (2, 3))
    _t13 = T(t13_v, (2, 2))
    _y13 = _x13 @ _w13.T + _b13
    _l13 = ((_y13 - _t13) ** 2).mean()
    _l13.backward()
    ref["g13_norm"] = [float(torch.nn.utils.clip_grad_norm_([_w13, _b13], 1e9))]
    ref["g13_gw"] = flat(_w13.grad)
    ref["g13_gb"] = flat(_b13.grad)
    ref["g13_clip"] = [float(torch.nn.utils.clip_grad_norm_([_w13, _b13], 0.05))]
    ref["g13_gw_after"] = flat(_w13.grad)
    ref["g13_gb_after"] = flat(_b13.grad)
    ref["g13_clip2"] = [float(torch.nn.utils.clip_grad_norm_([_w13, _b13], 100.0))]
    ref["g13_gw_idem"] = flat(_w13.grad)

    # v14：CSV 读数（表头/注释/缺列行都要跳过）
    csvdir = os.path.join(WORK, "csv14")
    os.makedirs(csvdir, exist_ok=True)
    with open(os.path.join(csvdir, "d.csv"), "w") as f:
        f.write("x1,x2,y\n1.0, 2.0 ,0\n-0.5,3.5,1\n#comment\n4.0,5.0\n6.0,-7.5,2\n")
    _t14 = torch.tensor([[1.0, 2.0, 0.0], [-0.5, 3.5, 1.0], [6.0, -7.5, 2.0]],
                        dtype=torch.float64)
    ref["t14_shape"] = [float(_t14.shape[0]), float(_t14.shape[1])]
    ref["t14_vals"] = flat(_t14)
    ref["n10_gelu"] = flat(torch.nn.GELU()(_x10))
    ref["n10_gelu_ap"] = flat(torch.nn.GELU(approximate="tanh")(_x10))
    ref["n10_leaky"] = flat(torch.nn.LeakyReLU(0.13)(_x10))
    ref["n10_softmax"] = flat(torch.nn.Softmax(dim=-1)(_x10))
    ref["n10_logsoft"] = flat(torch.nn.LogSoftmax(dim=1)(_x10))
    _ln10 = torch.nn.LayerNorm(4, 1e-05, dtype=torch.float64)
    with torch.no_grad():
        _ln10.weight.copy_(T(ln10_w, (4,)))
        _ln10.bias.copy_(T(ln10_b, (4,)))
    ref["n10_ln"] = flat(_ln10(_x10))
    ref["n10_ln_nparams"] = [2.0]
    _nl10 = torch.nn.NLLLoss()
    ref["n10_nll"] = [float(_nl10(torch.log_softmax(T(lg, (3, 3)), dim=1),
                                 torch.tensor(ce_t)))]
    ref["n10_bce"] = [float(torch.nn.BCEWithLogitsLoss()(T(bp10_v, (3, 1)),
                                                         T(bt10_v, (3, 1))))]
    _l10a = torch.nn.Linear(4, 3, dtype=torch.float64)
    with torch.no_grad():
        _l10a.weight.copy_(w10a)
        _l10a.bias.copy_(T(b10a, (3,)))
    _l10b = torch.nn.Linear(3, 2, dtype=torch.float64)
    with torch.no_grad():
        _l10b.weight.copy_(w10b)
        _l10b.bias.copy_(T(b10b, (2,)))
    _ln10b = torch.nn.LayerNorm(3, 1e-05, dtype=torch.float64)
    with torch.no_grad():
        _ln10b.weight.copy_(T(ln10_wb, (3,)))
        _ln10b.bias.copy_(T(ln10_bb, (3,)))
    _sq10 = torch.nn.Sequential(_l10a, _ln10b, torch.nn.GELU(), _l10b)
    _k10 = list(_sq10.state_dict().keys())
    ref["sq10_keys"] = ",".join(_k10)
    ref["sq10_nkeys"] = [float(len(_k10))]
    ref["sq10_nparams"] = [float(len(_k10))]
    ref["sq10_y"] = flat(_sq10(_x10))
    ref["sq10_lnw"] = [float(_ln10b.weight.numel())]

    # v11 MHA：torch 的 in_proj 是 q/k/v 竖排的 (3E,E)，正好用 cat 拼出同一组权重
    _mha11 = torch.nn.MultiheadAttention(4, 2, dtype=torch.float64)
    with torch.no_grad():
        _mha11.in_proj_weight.copy_(torch.cat([wq11, wk11, wv11], dim=0))
        _mha11.in_proj_bias.copy_(torch.cat([bq11, bk11, bv11], dim=0))
        _mha11.out_proj.weight.copy_(wo11)
        _mha11.out_proj.bias.copy_(bo11)
    _xm11 = T(xm11_v, (3, 4))
    _o11, _w11 = _mha11(_xm11, _xm11, _xm11, need_weights=True,
                        average_attn_weights=False)
    ref["m11_attn"] = flat(_w11.detach())
    ref["m11_y"] = flat(_o11.detach())
    # torch 打包：in_proj_weight (3E,E) + in_proj_bias (3E) + out_proj.weight + out_proj.bias；
    # 我们拆成 3+3+1+1 = 8 个张量（键面 = torch 的 4 个键，in_proj_* 再分 .q/.k/.v）。
    _e11 = int(_mha11.embed_dim)
    _nsplit11 = (_mha11.in_proj_weight.shape[0] // _e11
                 + _mha11.in_proj_bias.shape[0] // _e11 + 2)
    ref["m11_nparams"] = [float(_nsplit11)]
    ref["m11_nsplit"] = [float(_nsplit11)]
    ref["m11_nstate"] = [float(_nsplit11)]
    _k11 = []
    for _k in _mha11.state_dict().keys():
        if _k.startswith("in_proj_"):
            for _p in ["q", "k", "v"]:
                _k11.append(_k + "." + _p)
        else:
            _k11.append(_k)
    ref["m11_keys"] = ",".join(_k11)
    ref["m11_wqnumel"] = [float(_mha11.in_proj_weight[:4].numel())]
    _mha11.zero_grad()
    _o11.mean().backward()
    ref["m11_gwq"] = flat(_mha11.in_proj_weight.grad[:4])
    ref["m11_gwo"] = flat(_mha11.out_proj.weight.grad)

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
