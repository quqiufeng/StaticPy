# PyTorch 风格的训练回路，原样跑在 ltorch 上：
#   torch.tensor / torch.matmul / torch.mse_loss / torch.backward / torch.sgd
# 这些名字翻译器映射成 torch-<name>，由 plugins/ltorch/runtime.scm 的兼容层实现，
# 底层仍是 libtorch 的 ATen 内核 + autograd（算子不重写）。
import torch
import ltorch


def show_loss(step: int, loss: int) -> None:
    print("step=" + str(step) + " loss=" + str(torch.item(loss)))


def linreg() -> None:
    "单层线性回归：y = 2x + 1"
    print("== linear regression ==")
    x = torch.tensor([[-2.0], [-1.0], [0.0], [1.0], [2.0]])
    y = torch.tensor([[-3.0], [-1.0], [1.0], [3.0], [5.0]])
    w = torch.set_requires_grad(torch.tensor([[0.0]]), True)
    b = torch.set_requires_grad(torch.tensor([[0.0]]), True)
    lr = 0.05
    i = 0
    while i < 200:
        pred = torch.add(torch.matmul(x, w), b)
        loss = torch.mse_loss(pred, y)
        if i % 50 == 0:
            show_loss(i, loss)
        torch.backward(loss)
        torch.sgd(w, torch.grad(w), lr)
        torch.sgd(b, torch.grad(b), lr)
        torch.zero_grad(w)
        torch.zero_grad(b)
        i = i + 1
    pred = torch.add(torch.matmul(x, w), b)
    print("w=" + str(torch.item(w)) + " b=" + str(torch.item(b)))
    print("pred=" + str(torch.to_list(pred)))
    print("final loss=" + str(torch.item(torch.mse_loss(pred, y))))
    ltorch.free(x)
    ltorch.free(y)
    ltorch.free(w)
    ltorch.free(b)


def mlp() -> None:
    "两层 MLP：relu 隐层，拟合 y = x0 + 2*x1"
    print("== mlp ==")
    x = torch.tensor([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
    y = torch.tensor([[0.0], [2.0], [1.0], [3.0]])
    w1 = torch.set_requires_grad(torch.randn([2, 4], 7), True)
    b1 = torch.set_requires_grad(torch.zeros([1, 4]), True)
    w2 = torch.set_requires_grad(torch.randn([4, 1], 7), True)
    b2 = torch.set_requires_grad(torch.zeros([1, 1]), True)
    lr = 0.03
    i = 0
    while i < 400:
        h = torch.relu(torch.add(torch.matmul(x, w1), b1))
        pred = torch.add(torch.matmul(h, w2), b2)
        loss = torch.mse_loss(pred, y)
        if i % 100 == 0:
            show_loss(i, loss)
        torch.backward(loss)
        torch.sgd(w1, torch.grad(w1), lr)
        torch.sgd(b1, torch.grad(b1), lr)
        torch.sgd(w2, torch.grad(w2), lr)
        torch.sgd(b2, torch.grad(b2), lr)
        torch.zero_grad(w1)
        torch.zero_grad(b1)
        torch.zero_grad(w2)
        torch.zero_grad(b2)
        i = i + 1
    h = torch.relu(torch.add(torch.matmul(x, w1), b1))
    pred = torch.add(torch.matmul(h, w2), b2)
    print("pred=" + str(torch.to_list(pred)))
    print("final loss=" + str(torch.item(torch.mse_loss(pred, y))))
    ltorch.free(x)
    ltorch.free(y)
    ltorch.free(w1)
    ltorch.free(b1)
    ltorch.free(w2)
    ltorch.free(b2)


def main():
    print("libtorch " + ltorch.version())
    linreg()
    mlp()
