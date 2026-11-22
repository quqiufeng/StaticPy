# parse: seed-only  —— 跨文件类分派：Tensor/Linear 定义在 tensor_lib.static.py，
# 单文件翻译时自举链路看不见那些方法（成 `(a-matmul)` 这种丢实参的兜底）；
# 真实用法是 build_app.sh 先 concat 再编，那条链路两个翻译器都正确（见 lib_difftest.py --elf）。
# lib_demo.static.py — plugins/ltorch/tensor_lib.static.py（Tensor 类 + nn/optim）的功能演示
#
# 与 PyTorch 的对应关系（差分见 plugins/ltorch/lib_difftest.py）：
#   t = torch.tensor([...], dtype=torch.float64) → tensor([...], [shape])
#   nn.Linear(3, 2)                              → Linear(3, 2, seed)
#   loss.backward(); opt.step()                  → 同（SGD 走 ATen 原地更新）


def show(name: str, t: Tensor) -> None:
    print(name + " shape=(" + t.shape() + ") values=[" + t.values() + "]")


def main():
    print("libtorch " + version())

    a: Tensor = tensor([1.0, 2.0, 3.0, 4.0], [2, 2])
    b: Tensor = tensor([1.0, 0.0, 0.0, 1.0], [2, 2])
    show("a", a)
    show("a @ I", a.matmul(b))
    show("a + I", a.add(b))
    show("relu(a - 2)", a.sub_scalar(2.0).relu())
    show("softmax(a, 1)", a.softmax(1))
    show("reshape(a, [4])", a.reshape([4]))
    print("sum=" + str(a.sum().item()) + " mean=" + str(a.mean().item()) + " numel=" + str(a.numel()))

    # ---- nn.Linear + autograd：y = x @ w.T + b，loss = mean(y^2) ----
    lin: Linear = Linear(3, 2, 1234)
    lin.zero_grad()
    x: Tensor = ones([4, 3])
    y: Tensor = lin.forward(x)
    loss: Tensor = MSELoss().forward(y, zeros([4, 2]))
    loss.backward()
    print("linear y.shape=(" + y.shape() + ") loss=" + str(loss.item()))
    print("w.grad=[" + lin.w.grad_values() + "]")
    print("b.grad=[" + lin.b.grad_values() + "]")

    # ---- 训练一步：SGD 后 loss 必须下降 ----
    opt: SGD = SGD(lin.parameters(), 0.1)
    before: float = loss.item()
    opt.step()
    opt.zero_grad()
    after: Tensor = MSELoss().forward(lin.forward(x), zeros([4, 2]))
    print("loss " + str(before) + " -> " + str(after.item()))

    # ---- 两层 MLP：h = relu(x @ w1.T + b1)，y = h @ w2.T + b2 ----
    l1: Linear = Linear(2, 4, 7)
    relu: ReLU = ReLU()
    l2: Linear = Linear(4, 1, 9)
    mse: MSELoss = MSELoss()
    # lr 必须小：0.05 会把 ReLU 全打死（pred 退化成常数 = b2），0.005 稳收敛
    opt2: SGD = SGD(concat_params(l1, l2), 0.005)
    xs: Tensor = tensor([1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 4.0], [4, 2])
    ys: Tensor = tensor([2.0, 4.0, 6.0, 8.0], [4, 1])
    i: int = 0
    while i < 200:
        pred: Tensor = l2.forward(relu.forward(l1.forward(xs)))
        ml: Tensor = mse.forward(pred, ys)
        opt2.zero_grad()
        ml.backward()
        opt2.step()
        i += 1
    final: Tensor = mse.forward(l2.forward(relu.forward(l1.forward(xs))), ys)
    print("mlp 200 steps loss=" + str(final.item()))
    show("mlp pred", l2.forward(relu.forward(l1.forward(xs))).detach())

    a.free()
    b.free()
    x.free()
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
