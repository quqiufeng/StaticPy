"""StaticPy 训练模板 3：单头 self-attention 编码器块（LayerNorm + GELU），序列三分类。

这条模板专打 v10 扩出来的那批算子：
  Embedding / LayerNorm / masked_fill / softmax(dim) / matmul / GELU / mean_dim / CE
结构就是 Transformer 编码器一层的收缩版（d_model=16, T=8, 单头）：

    tokens (n*T,) --Embedding--> (n*T,d) --LN1--> q,k,v (各 d)
      scores = q @ k^T / sqrt(d)          (n*T, n*T)
      scores = scores.masked_fill(mask, -1e9)   # 因果 + 分块（不同样本互不正视）
      att    = scores.softmax(1) @ v      (n*T, d)
      x = LN2(x + proj(att))              # 残差 + LN
      x = LN3(x + W2(gelu(W1(x))))        # 前馈（4d 隐层）
      pooled = x.reshape(n,T,d).mean_dim(1)   # 序列池化
      logits = head(pooled)               # (n,3)
    CE(logits, y) -> backward -> AdamW

任务：每条样本 8 个 token（vocab=8），其中**类标记 token 出现 5 次**，位置随机旋转；
类别 = 那个 token 的 id（0/1/2），三类均衡 —— 均值池化+注意力都能抓到，
但必须真的把 attention 的 mask 写对才不会跨样本串味。

验收：loss 收敛、三类全对、把 Embedding 清零后掉到随机猜（≈1/3）、load 回来复原。
"""

T_LEN: int = 8
VOCAB: int = 8
D_MODEL: int = 16
N_CLS: int = 3
N_SAMPLE: int = 24


def make_tokens() -> list:
    """返回 [tok（n*T 个 int）, y]；类标记重复 5 次并按样本旋转位置。"""
    tok: list = []
    y: list = []
    i: int = 0
    while i < N_SAMPLE:
        cls: int = i % N_CLS
        row: list = []
        t: int = 0
        while t < T_LEN:
            row.append((i * 5 + t * 3 + 1) % VOCAB)
            t += 1
        off: int = (i * 3) % T_LEN
        t = 0
        while t < 5:
            row[(t + off) % T_LEN] = cls
            t += 1
        tok = tok + row
        y.append(cls)
        i += 1
    return [tok, y]


def mask_csv() -> str:
    """(n*T, n*T) 掩码：0=可见，1=屏蔽（跨样本 + 未来位）。"""
    n: int = N_SAMPLE * T_LEN
    out: str = ""
    i: int = 0
    while i < n:
        j: int = 0
        si: int = i // T_LEN
        ti: int = i % T_LEN
        while j < n:
            sj: int = j // T_LEN
            tj: int = j % T_LEN
            blocked: int = 0
            if sj != si:
                blocked = 1
            if tj > ti:
                blocked = 1
            if i > 0 or j > 0:
                out = out + ","
            out = out + str(blocked)
            j += 1
        i += 1
    return out


def mask_shape() -> str:
    n: int = N_SAMPLE * T_LEN
    return str(n) + "," + str(n)


def tok_shape() -> str:
    """x.reshape(...) 用：把 (n*T,d) 收回 (n,T,d)。"""
    return str(N_SAMPLE) + "," + str(T_LEN) + "," + str(D_MODEL)


def n_params(ps: list) -> int:
    n: int = 0
    i: int = 0
    while i < len(ps):
        t: Tensor = ps[i]
        n += t.numel()
        i += 1
    return n


def accuracy(logits_all: Tensor, y: list) -> float:
    got: list = logits_all.argmax_dim(1).tolist()
    ok: int = 0
    i: int = 0
    while i < len(y):
        if int(got[i]) == int(y[i]):
            ok += 1
        i += 1
    return float(ok) / float(len(y))


class AttnBlock:
    """单头 self-attention 编码器层（纯 Tensor 运算，不依赖 Sequential 派发表）。"""

    emb: Embedding
    ln1: LayerNorm
    lq: Linear
    lk: Linear
    lv: Linear
    proj: Linear
    ln2: LayerNorm
    ff1: Linear
    act: GELU
    ff2: Linear
    ln3: LayerNorm
    head: Linear
    mask: Tensor
    dk: int

    def __init__(self, seed: int):
        self.dk = D_MODEL
        self.emb = Embedding(VOCAB, D_MODEL, seed)
        self.ln1 = LayerNorm(D_MODEL)
        self.lq = Linear(D_MODEL, D_MODEL, seed + 1)
        self.lk = Linear(D_MODEL, D_MODEL, seed + 2)
        self.lv = Linear(D_MODEL, D_MODEL, seed + 3)
        self.proj = Linear(D_MODEL, D_MODEL, seed + 4)
        self.ln2 = LayerNorm(D_MODEL)
        self.ff1 = Linear(D_MODEL, 4 * D_MODEL, seed + 5)
        self.act = GELU()
        self.ff2 = Linear(4 * D_MODEL, D_MODEL, seed + 6)
        self.ln3 = LayerNorm(D_MODEL)
        self.head = Linear(D_MODEL, N_CLS, seed + 7)
        self.mask = tensor_from_csv(mask_csv(), mask_shape())

    def parameters(self) -> list:
        out: list = []
        out.append(self.emb.w)
        out.append(self.ln1.w)
        out.append(self.ln1.b)
        out.append(self.lq.w)
        out.append(self.lq.b)
        out.append(self.lk.w)
        out.append(self.lk.b)
        out.append(self.lv.w)
        out.append(self.lv.b)
        out.append(self.proj.w)
        out.append(self.proj.b)
        out.append(self.ln2.w)
        out.append(self.ln2.b)
        out.append(self.ff1.w)
        out.append(self.ff1.b)
        out.append(self.ff2.w)
        out.append(self.ff2.b)
        out.append(self.ln3.w)
        out.append(self.ln3.b)
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

    def forward(self, tok: list) -> Tensor:
        e: Tensor = self.emb.forward(tok)              # (n*T, d)
        h: Tensor = self.ln1.forward(e)
        q: Tensor = self.lq.forward(h)
        k: Tensor = self.lk.forward(h)
        v: Tensor = self.lv.forward(h)
        scale: float = 1.0 / sqrt_float(float(self.dk))
        sc: Tensor = q.matmul(k.transpose(0, 1)).mul_scalar(scale)
        sc = sc.masked_fill(self.mask, -1.0e9)
        at: Tensor = sc.softmax(1)
        o: Tensor = at.matmul(v)                       # (n*T, d)
        r1: Tensor = e.add(self.proj.forward(o))       # 残差
        h2: Tensor = self.ln2.forward(r1)
        ff: Tensor = self.ff2.forward(self.act.forward(self.ff1.forward(h2)))
        r2: Tensor = r1.add(ff)
        h3: Tensor = self.ln3.forward(r2)
        pooled: Tensor = h3.reshape([N_SAMPLE, T_LEN, D_MODEL]).mean_dim(1)  # (n, d)
        return self.head.forward(pooled)               # (n, 3)

    def save(self, path: str) -> int:
        return save_params(self.parameters(), path)

    def load_ckpt(self, path: str) -> int:
        return load_params(self.parameters(), path)


def train_steps(m: AttnBlock, opt: AdamW, lossf: CrossEntropyLoss,
                tok: list, y: list, steps: int, tag: str) -> None:
    i: int = 0
    while i < steps:
        m.zero_grad()
        loss: Tensor = lossf.forward(m.forward(tok), y)
        loss.backward()
        opt.step()
        if i % 10 == 0:
            print(tag + str(i) + " loss=" + str(loss.item()))
        i += 1


def main() -> None:
    bx: list = make_tokens()
    tok: list = bx[0]
    y: list = bx[1]
    m: AttnBlock = AttnBlock(7)
    ps: list = m.parameters()
    print("n_tensors=" + str(len(ps)))
    print("nparams=" + str(n_params(ps)))
    print("mask_shape=" + m.mask.shape())
    logits: Tensor = m.forward(tok)
    print("logits_shape=" + logits.shape())
    lossf: CrossEntropyLoss = CrossEntropyLoss()
    print("loss0=" + str(lossf.forward(logits, y).item()))
    print("acc0=" + str(accuracy(logits, y)))

    opt: AdamW = AdamW(ps, 0.03)
    train_steps(m, opt, lossf, tok, y, 120, "s")
    out: Tensor = m.forward(tok)
    print("loss1=" + str(lossf.forward(out, y).item()))
    print("acc1=" + str(accuracy(out, y)))

    ck: str = "/home/quqiufeng/iso_gen/attn_ck/model"
    os_mkdir("/home/quqiufeng/iso_gen/attn_ck")
    print("save=" + str(m.save(ck)))
    w0: Tensor = m.emb.w
    z: Tensor = zeros([VOCAB, D_MODEL])
    torchc_copy_into(w0.h, z.h)
    print("acc_wiped=" + str(accuracy(m.forward(tok), y)))
    print("load=" + str(m.load_ckpt(ck)))
    print("acc_restored=" + str(accuracy(m.forward(tok), y)))
