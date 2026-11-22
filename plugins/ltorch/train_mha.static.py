"""StaticPy 训练模板 4：真 nn.MultiheadAttention 多头自注意力分类（逐样本拼批）。

前三条模板把注意力拆成 q/k/v 三个 Linear 手写（等价但不叫 torch 的名字）；
这条直接用 v11 的 `MultiheadAttention(embed, heads, seed)` 模块 —— 用户从 torch
搬过来的 `nn.MultiheadAttention` 代码可以几乎原样落地：

    每样本 (T,E) --mha--> (T,E) --+xs 残差--> LayerNorm --mean(dim=0)--> (1,E) --Linear--> (1,N_CLS)
    9 个样本的 (1,N_CLS) 用 cat(dim=0) 拼成 (9,N_CLS) → CE → backward → AdamW

为什么不是一次喂 (N*T, E)？`MultiheadAttention` 的注意力在整段序列上做，
直接喂会把不同样本串味（torch 里靠 attn_mask/padding mask 解决，本模板故意不引掩码，
改成逐样本前向 + 拼 logits —— 这也是 batch=1 推理的标准写法）。
取样本切片用 `index_select(行号 list)`，拼批用 `cat(dim=0)`，都是 v3 的算子。

任务：T=6 个 token、E=8 维、2 头。类别 = 第 0 维「高值 token」的个数：

    cls=0 → 恰好 1 个 +2.0（其余 -0.4，**均值恰好 0**）
    cls=1 → 恰好 2 个 +2.0（其余 -1.0，**均值恰好 0**）
    cls=2 → 全 0

关键：三类在第 0 维上的**均值完全相同（都是 0）**，所以"先池化再看"永远分不开；
其它通道用 `t%3` 零和抖动（每条样本不同、但跨 token 均值恒为 0），也不泄漏类别。
能分开的唯一通路是**注意力按内容给高值 token 加权**（3 类分别 1/2/0 个），
即这条模板真的在考 `MultiheadAttention` 的 QK 打分，而不是在学一个线性池化。

验收：loss 收敛、9 条全对；把 out_proj 权重 wo 清零（注意力支路彻底失效，只剩残差
通道 → 退化成纯均值池化）后掉到随机猜（**恰好 3/9，因为三类均值相同、argmax 全取 0**），
load 回来复原。
"""

T_LEN: int = 6
E_DIM: int = 8
HEADS: int = 2
N_CLS: int = 3
N_SAMPLE: int = 9


def chan0(cls: int, t: int, p1: int, p2: int) -> float:
    """第 0 维：高值 token 个数 = 类别，且**均值恒为 0**（池化看不到类别）。"""
    if cls == 0:
        if t == p1:
            return 2.0
        return -0.4
    if cls == 1:
        if t == p1 or t == p2:
            return 2.0
        return -1.0
    return 0.0


def data_csv() -> str:
    """(N*T, E) 输入；高值 token 的位置每条样本不同，抖动项跨 token 零和。"""
    out: str = ""
    i: int = 0
    while i < N_SAMPLE:
        cls: int = i % N_CLS
        p1: int = (i * 2) % T_LEN
        p2: int = (i * 2 + 3) % T_LEN
        t: int = 0
        while t < T_LEN:
            c: int = 0
            while c < E_DIM:
                v: float = 0.0
                if c == 0:
                    v = chan0(cls, t, p1, p2)
                else:
                    v = float(((t * 3 + c * 5) % 5) - 2) * 0.1
                    v += float(((i + t) % 3) - 1) * 0.15
                if i > 0 or t > 0 or c > 0:
                    out += ","
                out += str(v)
                c += 1
            t += 1
        i += 1
    return out


def data_shape() -> str:
    """tensor_from_csv 认 "行,列"（不带方括号）。"""
    return str(N_SAMPLE * T_LEN) + "," + str(E_DIM)


def labels() -> list:
    y: list = []
    i: int = 0
    while i < N_SAMPLE:
        y.append(i % N_CLS)
        i += 1
    return y


def n_params(ps: list) -> int:
    n: int = 0
    i: int = 0
    while i < len(ps):
        t: Tensor = ps[i]
        n += t.numel()
        i += 1
    return n


def accuracy(logits: Tensor, y: list) -> float:
    got: list = logits.argmax_dim(1).tolist()
    ok: int = 0
    i: int = 0
    while i < len(y):
        if int(got[i]) == int(y[i]):
            ok += 1
        i += 1
    return float(ok) / float(len(y))


class MhaNet:
    """一个自注意力块 + 均值池化 + 线性头；参数 12 个张量（mha 8 + ln 2 + head 2）。"""

    mha: MultiheadAttention
    ln: LayerNorm
    head: Linear

    def __init__(self, seed: int):
        self.mha = MultiheadAttention(E_DIM, HEADS, seed)
        self.ln = LayerNorm(E_DIM)
        self.head = Linear(E_DIM, N_CLS, seed + 9)

    def parameters(self) -> list:
        out: list = []
        out.append(self.mha.wq)
        out.append(self.mha.wk)
        out.append(self.mha.wv)
        out.append(self.mha.bq)
        out.append(self.mha.bk)
        out.append(self.mha.bv)
        out.append(self.mha.wo)
        out.append(self.mha.bo)
        out.append(self.ln.w)
        out.append(self.ln.b)
        out.append(self.head.w)
        out.append(self.head.b)
        return out

    def zero_grad(self) -> None:
        ps: list = self.parameters()
        i: int = 0
        while i < len(ps):
            t: Tensor = ps[i]
            t.zero_grad()
            i += 1

    def rows_of(self, i: int) -> list:
        """第 i 条样本在 (N*T, E) 里占的行号。"""
        rows: list = []
        t: int = 0
        while t < T_LEN:
            rows.append(i * T_LEN + t)
            t += 1
        return rows

    def one(self, x: Tensor, i: int) -> Tensor:
        """单样本前向：(T,E) → (1,N_CLS)。"""
        xs: Tensor = x.index_select(self.rows_of(i))   # (T,E)
        h: Tensor = self.mha.forward(xs)               # (T,E)
        r: Tensor = h.add(xs)                          # 残差
        pooled: Tensor = r.mean_dim(0)                 # (1,E) —— 先池化再 LN
        n: Tensor = self.ln.forward(pooled)            # (1,E)
        return self.head.forward(n)                    # (1,N_CLS)

    def forward(self, x: Tensor) -> Tensor:
        out: Tensor = self.one(x, 0)
        i: int = 1
        while i < N_SAMPLE:
            out = out.cat(self.one(x, i), 0)
            i += 1
        return out

    def save(self, path: str) -> int:
        return save_params(self.parameters(), path)

    def load_ckpt(self, path: str) -> int:
        return load_params(self.parameters(), path)


def train_steps(m: MhaNet, opt: AdamW, lossf: CrossEntropyLoss,
                x: Tensor, y: list, steps: int, tag: str) -> None:
    i: int = 0
    while i < steps:
        m.zero_grad()
        loss: Tensor = lossf.forward(m.forward(x), y)
        loss.backward()
        opt.step()
        if i % 10 == 0:
            print(tag + str(i) + " loss=" + str(loss.item()))
        i += 1


def main() -> None:
    x: Tensor = tensor_from_csv(data_csv(), data_shape())
    y: list = labels()
    m: MhaNet = MhaNet(7)
    ps: list = m.parameters()
    print("n_tensors=" + str(len(ps)))
    print("nparams=" + str(n_params(ps)))
    x0: Tensor = x.index_select(m.rows_of(0))
    print("x0_shape=" + x0.shape())
    print("attn_shape=" + m.mha.attn_weights(x0).shape())

    lossf: CrossEntropyLoss = CrossEntropyLoss()
    logits: Tensor = m.forward(x)
    print("logits_shape=" + logits.shape())
    print("loss0=" + str(lossf.forward(logits, y).item()))
    print("acc0=" + str(accuracy(logits, y)))

    opt: AdamW = AdamW(ps, 0.02)
    train_steps(m, opt, lossf, x, y, 100, "s")
    out: Tensor = m.forward(x)
    print("loss1=" + str(lossf.forward(out, y).item()))
    print("acc1=" + str(accuracy(out, y)))

    ck: str = "/home/quqiufeng/iso_gen/mha_ck/model"
    os_mkdir("/home/quqiufeng/iso_gen/mha_ck")
    print("save=" + str(m.save(ck)))
    w0: Tensor = m.mha.wo
    z: Tensor = zeros([E_DIM, E_DIM])
    torchc_copy_into(w0.h, z.h)
    print("acc_wiped=" + str(accuracy(m.forward(x), y)))
    print("load=" + str(m.load_ckpt(ck)))
    print("acc_restored=" + str(accuracy(m.forward(x), y)))
