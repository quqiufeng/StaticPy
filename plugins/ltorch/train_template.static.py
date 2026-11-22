# parse: seed-only
# ============================================================================
# ltorch 训练模板（照抄改形状/超参就能用）
#
#   数据  randn 造 4 维特征，标签由确定性规则给（可学、可复现）
#   模型  Sequential：Linear → ReLU → Dropout → Linear → ReLU → Linear
#   损失  CrossEntropyLoss（target 是「类别下标 list」，Tensor target 走 forward_t）
#   优化  AdamW（decoupled weight decay）+ StepLR（step() **返回**新 lr，要写回 opt.lr）
#   存盘  m.save(prefix) / m.load_ckpt(prefix)：一参数一文件 <prefix>.i
#
# 编译运行：
#   bash plugins/ltorch/build_app.sh plugins/ltorch/train_template.static.py train_template
#   ./dist/train_template
# ============================================================================


def n_in() -> int:
    return 4


def make_labels(x: Tensor, n: int) -> list:
    """标签 = (x[i][0] + x[i][1] > 0)，两层 MLP 足以拟合。"""
    flat: list = x.tolist()
    y: list = []
    i: int = 0
    while i < n:
        a: float = flat[i * 4]
        b: float = flat[i * 4 + 1]
        if a + b > 0.0:
            y.append(1)
        else:
            y.append(0)
        i += 1
    return y


def build_model() -> Sequential:
    m: Sequential = Sequential()
    m.add_linear(Linear(4, 16, 11))
    m.add_relu()
    m.add_dropout(Dropout(0.1, 33))
    m.add_linear(Linear(16, 8, 12))
    m.add_relu()
    m.add_linear(Linear(8, 2, 13))
    return m


def accuracy(m: Sequential, x: Tensor, y: list) -> float:
    """eval 态（dropout 关闭）下的命中率。"""
    out: Tensor = m.forward(x)
    am: Tensor = out.argmax_dim(1)
    pred: list = am.tolist()
    ok: int = 0
    i: int = 0
    while i < len(y):
        if int(pred[i]) == int(y[i]):
            ok += 1
        i += 1
    return float(ok) / float(len(y))


# 注意：静态语言没有向上转型（`opt: Optimizer` 接 `AdamW` 会报错），
# 训练函数要按**具体优化器类**标注；换 SGD 就再写一个或直接把类型改掉。
def train_steps(m: Sequential, opt: AdamW, lossf: CrossEntropyLoss,
                x: Tensor, y: list, base_lr: float, steps: int, tag: str) -> None:
    """跑 steps 步；每步 print 一行 loss（可重定向成曲线）。"""
    sch: StepLR = StepLR(base_lr, 8, 0.5)
    i: int = 0
    while i < steps:
        opt.lr = sch.step()          # scheduler 返回新 lr，由调用方写回
        opt.zero_grad()
        out: Tensor = m.forward(x)
        loss: Tensor = lossf.forward(out, y)
        loss.backward()
        opt.step()
        print(tag + str(i) + " lr=" + str(opt.lr) + " loss=" + str(loss.item()))
        i += 1


def main() -> None:
    x: Tensor = randn([96, 4], 7)
    y: list = make_labels(x, 96)
    m: Sequential = build_model()
    ps: list = m.parameters()
    print("nparams", len(ps))
    print("state_dict_keys", len(m.state_dict()))

    lossf: CrossEntropyLoss = CrossEntropyLoss()
    opt: AdamW = AdamW(ps, 0.05, 0.9, 0.999, 1e-08, 0.01)

    acc0: float = accuracy(m, x, y)
    print("acc_before", acc0)

    ck: str = "/home/quqiufeng/iso_gen/tpl_ck/model"
    # 前 20 步训练 → 落盘
    train_steps(m, opt, lossf, x, y, 0.05, 20, "s")
    print("save", m.save(ck))
    acc_mid: float = accuracy(m, x, y)
    print("acc_mid", acc_mid)

    # 模拟「换进程续训」：把权重清零，再从 checkpoint 读回
    w0: Tensor = m.param_at(0)
    torchc_copy_into(w0.h, zeros([16, 4]).h)
    print("acc_wiped", accuracy(m, x, y))
    print("load", m.load_ckpt(ck))
    print("acc_restored", accuracy(m, x, y))

    # 后 20 步续训（lr 由新 scheduler 从 base 重新衰减，示意可以自定义）
    train_steps(m, opt, lossf, x, y, 0.02, 20, "r")
    acc1: float = accuracy(m, x, y)
    print("acc_after", acc1)

    # 优化器超参快照（对标 opt.state_dict() 里的 param_groups 视图）
    sd: dict = opt.state_dict()
    print("opt_lr", sd["lr"])
    print("opt_wd", sd["weight_decay"])
    print("opt_t", sd["t"])

