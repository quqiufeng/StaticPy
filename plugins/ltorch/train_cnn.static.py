"""StaticPy 训练模板 2：CNN（Conv2d + MaxPool2d + Flatten），均衡三类。

图形是 8x8 单通道，三类按"亮在哪半张"区分（左半 / 右半 / 上半），
每类样本数相等 —— 所以准确率不能靠猜多数类混过去。
loss 用 CrossEntropyLoss，优化器 SGD，中途存盘/清空/续训做验收。
"""


def n_cls() -> int:
    return 3


def make_batch(n: int, seed: int) -> list:
    """返回 [x, y]：x 形状 (n,1,8,8)，y 是 n 个 0/1/2（均衡轮转）。"""
    x: Tensor = randn([n, 1, 8, 8], seed).mul_scalar(0.45)
    v: list = x.tolist()
    y: list = []
    i: int = 0
    while i < n:
        cls: int = i % 3
        base: int = i * 64
        r: int = 0
        while r < 8:
            c: int = 0
            while c < 8:
                k: int = base + r * 8 + c
                on: int = 0
                if cls == 0:
                    if c < 4:
                        on = 1
                if cls == 1:
                    if c >= 4:
                        on = 1
                if cls == 2:
                    if r < 4:
                        on = 1
                if on == 1:
                    v[k] = v[k] + 1.0
                c += 1
            r += 1
        y.append(cls)
        i += 1
    return [tensor_from_csv(_csv_float(v), _shape_str(n)), y]


def _shape_str(n: int) -> str:
    return str(n) + ",1,8,8"


def _csv_float(v: list) -> str:
    out: str = ""
    i: int = 0
    while i < len(v):
        if i > 0:
            out = out + ","
        out = out + str(v[i])
        i += 1
    return out


def build_model() -> Sequential:
    m: Sequential = Sequential()
    m.add_conv(Conv2d(1, 4, 3, 1, 1, 51))
    m.add_relu()
    m.add_maxpool(MaxPool2d(2, 2))
    m.add_flatten()
    m.add_linear(Linear(64, 16, 52))
    m.add_relu()
    m.add_linear(Linear(16, n_cls(), 53))
    return m


def accuracy(m: Sequential, x: Tensor, y: list) -> float:
    out: Tensor = m.forward(x)
    got: list = out.argmax_dim(1).tolist()
    ok: int = 0
    i: int = 0
    while i < len(y):
        if int(got[i]) == int(y[i]):
            ok += 1
        i += 1
    return float(ok) / float(len(y))


def train_steps(m: Sequential, opt: SGD, lossf: CrossEntropyLoss,
                x: Tensor, y: list, steps: int, tag: str) -> None:
    i: int = 0
    while i < steps:
        m.train()
        m.zero_grad()
        loss: Tensor = lossf.forward(m.forward(x), y)
        loss.backward()
        opt.step()
        if i % 5 == 0:
            print(tag + str(i) + " loss=" + str(loss.item()))
        i += 1


def main() -> None:
    n: int = 48
    bx: list = make_batch(n, 9)
    x: Tensor = bx[0]
    y: list = bx[1]
    print("in_shape=" + x.shape())
    m: Sequential = build_model()
    print("nparams=" + str(len(m.parameters())))
    print("sd_keys=" + str(len(m.state_dict())))
    print("out_shape=" + m.forward(x).shape())
    lossf: CrossEntropyLoss = CrossEntropyLoss()
    opt: SGD = SGD(m.parameters(), 0.05)
    print("acc0=" + str(accuracy(m, x, y)))
    train_steps(m, opt, lossf, x, y, 40, "s")
    print("acc1=" + str(accuracy(m, x, y)))

    ck: str = "/home/quqiufeng/iso_gen/cnn_ck/model"
    print("save=" + str(m.save(ck)))
    w0: Tensor = m.param_by("0.weight")
    z: Tensor = zeros([4, 1, 3, 3])
    torchc_copy_into(w0.h, z.h)
    print("acc_wiped=" + str(accuracy(m, x, y)))
    print("load=" + str(m.load_ckpt(ck)))
    print("acc_restored=" + str(accuracy(m, x, y)))
    m.eval()
    print("acc_eval=" + str(accuracy(m, x, y)))
