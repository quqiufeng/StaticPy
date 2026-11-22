# libTorch 最小绑定演示：真 at::Tensor 走 ATen 内核（数值与 PyTorch 一致）
import ltorch


def show(name: str, t: int) -> None:
    print(name + " shape=" + ltorch.shape(t) + " values=" + str(ltorch.to_list(t)))


def main():
    print("libtorch " + ltorch.version())

    a = ltorch.tensor([1.0, 2.0, 3.0, 4.0], [2, 2])
    b = ltorch.tensor([1.0, 0.0, 0.0, 1.0], [2, 2])
    show("a", a)
    show("a @ I", ltorch.matmul(a, b))
    show("relu(a-2)", ltorch.relu(ltorch.add_scalar(a, -2.0)))
    show("softmax(a, 1)", ltorch.softmax(a, 1))
    print("sum=" + str(ltorch.item(ltorch.sum(a))) + " mean=" + str(ltorch.item(ltorch.mean(a))))
    print("shape after reshape=" + ltorch.shape(ltorch.reshape(a, [4])))

    # autograd：y = sum((x @ x)^2)，dy/dx = 4 * x * (x@x)
    x = ltorch.set_requires_grad(ltorch.tensor([1.0, 2.0, 3.0], [1, 3]), True)
    prod = ltorch.matmul(x, ltorch.transpose(x, 0, 1))
    loss = ltorch.sum(ltorch.mul(prod, prod))
    ltorch.backward(loss)
    print("loss=" + str(ltorch.item(loss)) + " grad=" + str(ltorch.to_list(ltorch.grad(x))))

    ltorch.free(a)
    ltorch.free(b)
    ltorch.free(x)
