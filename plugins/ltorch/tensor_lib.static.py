# tensor_lib.static.py — libTorch C ABI 之上的「PyTorch 等价」封装库（库文件，无 main）
#
# 分层（照 imgproc 的做法：能力挂 `.so`，语义写在 StaticPy 里）：
#
#   libtorch_capi.so  ← 真 at::Tensor / ATen 内核（C ABI，见 cpp/torch/torch_capi.h）
#        ↑ extern fn（FFI 契约，docs/FFI.md：类型只有 int/float/double/bool/str/ptr，无 void 返回）
#   tensor_lib.static.py（本文件）  ← Tensor 类 + Linear/ReLU/MSELoss/SGD，PyTorch 风格调用
#        ↑ concat
#   用户程序（plugins/ltorch/lib_demo.static.py）
#
# 约定与偏差（照抄 Pillow 迁移的规矩：能对齐的对齐，对不齐的写明白）：
#   * dtype：C ABI 全走 **float64**，等价于 `torch.tensor(..., dtype=torch.float64)`；
#     PyTorch 默认 float32，所以差分对拍要显式 float64（否则差异全来自 dtype）。
#   * 张量句柄是 `ptr`（ATen 的 at::Tensor*），**不是** int：
#     `int` 在 FFI 表里是 C `int`（32 位），指针塞进去会被截断（第一版就栽在这）。
#   * 自动求导是 ATen 的 autograd，不重写；`backward()` 后梯度**累加**，
#     所以一轮训练必须 `opt.zero_grad()`（与 PyTorch 一致）。
#   * 句柄手动释放（`Tensor.free()`）：没有 GC 管 C 侧的 at::Tensor。
#   * Linear.w 形状 (out, in)、forward = x @ w.T + b —— 与 torch.nn.Linear 一致，
#     这样差分可以把 torch 的权重直接灌进来。
#
# 用法（concat 进用户程序，见 plugins/ltorch/build_app.sh）：
#   bash plugins/ltorch/build_app.sh plugins/ltorch/lib_demo.static.py demo

extern fn torchc_version() -> str from "torchc"
extern fn torchc_last_error() -> str from "torchc"

extern fn torchc_from_csv(values: str, shape: str) -> ptr from "torchc"
extern fn torchc_zeros(shape: str) -> ptr from "torchc"
extern fn torchc_ones(shape: str) -> ptr from "torchc"
extern fn torchc_full(shape: str, v: double) -> ptr from "torchc"
extern fn torchc_randn(shape: str, seed: int) -> ptr from "torchc"
extern fn torchc_arange(start: double, end: double, step: double) -> ptr from "torchc"

extern fn torchc_add(a: ptr, b: ptr) -> ptr from "torchc"
extern fn torchc_sub(a: ptr, b: ptr) -> ptr from "torchc"
extern fn torchc_mul(a: ptr, b: ptr) -> ptr from "torchc"
extern fn torchc_div(a: ptr, b: ptr) -> ptr from "torchc"
extern fn torchc_matmul(a: ptr, b: ptr) -> ptr from "torchc"

extern fn torchc_add_scalar(a: ptr, v: double) -> ptr from "torchc"
extern fn torchc_sub_scalar(a: ptr, v: double) -> ptr from "torchc"
extern fn torchc_mul_scalar(a: ptr, v: double) -> ptr from "torchc"
extern fn torchc_div_scalar(a: ptr, v: double) -> ptr from "torchc"

extern fn torchc_relu(a: ptr) -> ptr from "torchc"
extern fn torchc_sigmoid(a: ptr) -> ptr from "torchc"
extern fn torchc_tanh(a: ptr) -> ptr from "torchc"
extern fn torchc_neg(a: ptr) -> ptr from "torchc"
extern fn torchc_softmax(a: ptr, dim: int) -> ptr from "torchc"
extern fn torchc_sum(a: ptr) -> ptr from "torchc"
extern fn torchc_mean(a: ptr) -> ptr from "torchc"
extern fn torchc_sum_dim(a: ptr, dim: int) -> ptr from "torchc"

extern fn torchc_reshape(a: ptr, shape: str) -> ptr from "torchc"
extern fn torchc_transpose(a: ptr, d0: int, d1: int) -> ptr from "torchc"
extern fn torchc_clone(a: ptr) -> ptr from "torchc"
extern fn torchc_detach(a: ptr) -> ptr from "torchc"

extern fn torchc_numel(a: ptr) -> int from "torchc"
extern fn torchc_ndim(a: ptr) -> int from "torchc"
extern fn torchc_shape_csv(a: ptr) -> str from "torchc"
extern fn torchc_to_csv(a: ptr) -> str from "torchc"
extern fn torchc_item(a: ptr) -> double from "torchc"

extern fn torchc_set_requires_grad(a: ptr, flag: int) -> int from "torchc"
extern fn torchc_requires_grad(a: ptr) -> int from "torchc"
extern fn torchc_backward(a: ptr) -> int from "torchc"
extern fn torchc_grad(a: ptr) -> ptr from "torchc"
extern fn torchc_zero_grad(a: ptr) -> ptr from "torchc"
extern fn torchc_sgd_step(w: ptr, g: ptr, lr: double) -> int from "torchc"

extern fn torchc_is_tensor(a: ptr) -> int from "torchc"
extern fn torchc_free_int(a: ptr) -> int from "torchc"


# ============================== 元信息 ==============================

def version() -> str:
    return torchc_version()


def last_error() -> str:
    return torchc_last_error()


def available() -> bool:
    return torchc_version() != ""


# ============================== CSV 编解码 ==============================
# C ABI 多值参数一律 CSV（docs/FFI.md §3）；str(float) 是「最短往返」表示，
# 所以 list -> CSV -> at::Tensor 是**精确**的（0.1 不会变成 0.10000000000000001 后再变回来）。

def _csv_num(values: list) -> str:
    out: str = ""
    i: int = 0
    while i < len(values):
        if i > 0:
            out = out + ","
        out = out + str(values[i])
        i += 1
    return out


def _csv_int(values: list) -> str:
    return _csv_num(values)


def sqrt_float(x: float) -> float:
    """float 版 sqrt（PyTorch 的 1/sqrt(fan_in) 初始化要用）；
    必须定义在类之前 —— 方法体内引用后置顶层函数会 unbound。"""
    return x ** 0.5


# ============================== Tensor ==============================

class Tensor:
    """at::Tensor 的 StaticPy 壳：`h` 是裸句柄，方法一一对应 ATen 算子。"""

    h: ptr

    def __init__(self, h: ptr):
        self.h = h

    # ---------- 元信息 ----------
    def shape(self) -> str:
        return torchc_shape_csv(self.h)

    def ndim(self) -> int:
        return torchc_ndim(self.h)

    def numel(self) -> int:
        return torchc_numel(self.h)

    def values(self) -> str:
        """CSV 展平值（float64，行主序）"""
        return torchc_to_csv(self.h)

    def tolist(self) -> list:
        """展平成 Python list（对标 torch.Tensor.tolist）"""
        v: str = self.values()
        parts: list = v.split(",")
        out: list = []
        i: int = 0
        while i < len(parts):
            out.append(float(parts[i]))
            i += 1
        return out

    def item(self) -> double:
        return torchc_item(self.h)

    def repr(self) -> str:
        return "tensor([" + self.values() + "], shape=(" + self.shape() + "))"

    # ---------- 张量 × 张量 ----------
    def add(self, other: Tensor) -> Tensor:
        return Tensor(torchc_add(self.h, other.h))

    def sub(self, other: Tensor) -> Tensor:
        return Tensor(torchc_sub(self.h, other.h))

    def mul(self, other: Tensor) -> Tensor:
        return Tensor(torchc_mul(self.h, other.h))

    def div(self, other: Tensor) -> Tensor:
        return Tensor(torchc_div(self.h, other.h))

    def matmul(self, other: Tensor) -> Tensor:
        return Tensor(torchc_matmul(self.h, other.h))

    # ---------- 张量 × 常量（对标 add/sub/mul/div 的标量重载） ----------
    def add_scalar(self, v: float) -> Tensor:
        return Tensor(torchc_add_scalar(self.h, v))

    def sub_scalar(self, v: float) -> Tensor:
        return Tensor(torchc_sub_scalar(self.h, v))

    def mul_scalar(self, v: float) -> Tensor:
        return Tensor(torchc_mul_scalar(self.h, v))

    def div_scalar(self, v: float) -> Tensor:
        return Tensor(torchc_div_scalar(self.h, v))

    # ---------- 一元 ----------
    def relu(self) -> Tensor:
        return Tensor(torchc_relu(self.h))

    def sigmoid(self) -> Tensor:
        return Tensor(torchc_sigmoid(self.h))

    def tanh(self) -> Tensor:
        return Tensor(torchc_tanh(self.h))

    def neg(self) -> Tensor:
        return Tensor(torchc_neg(self.h))

    def softmax(self, dim: int) -> Tensor:
        return Tensor(torchc_softmax(self.h, dim))

    def sum(self) -> Tensor:
        return Tensor(torchc_sum(self.h))

    def mean(self) -> Tensor:
        return Tensor(torchc_mean(self.h))

    def sum_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_sum_dim(self.h, dim))

    # ---------- 形状 ----------
    def reshape(self, shape: list) -> Tensor:
        return Tensor(torchc_reshape(self.h, _csv_int(shape)))

    def transpose(self, d0: int, d1: int) -> Tensor:
        return Tensor(torchc_transpose(self.h, d0, d1))

    def clone(self) -> Tensor:
        return Tensor(torchc_clone(self.h))

    def detach(self) -> Tensor:
        return Tensor(torchc_detach(self.h))

    # ---------- autograd ----------
    def requires_grad_(self, flag: int) -> Tensor:
        torchc_set_requires_grad(self.h, flag)
        return self

    def requires_grad(self) -> int:
        return torchc_requires_grad(self.h)

    def backward(self) -> None:
        torchc_backward(self.h)

    def grad(self) -> Tensor:
        return Tensor(torchc_grad(self.h))

    def grad_values(self) -> str:
        """梯度的 CSV（没有梯度时返回空串，与 torch 的 None 对应）"""
        g: Tensor = self.grad()
        if torchc_is_tensor(g.h) == 0:
            return ""
        return g.values()

    def zero_grad(self) -> None:
        torchc_zero_grad(self.h)

    # ---------- 生命周期 ----------
    def free(self) -> None:
        if torchc_is_tensor(self.h) != 0:
            torchc_free_int(self.h)


# ============================== 工厂函数（对标 torch.*） ==============================

def tensor(values: list, shape: list) -> Tensor:
    return Tensor(torchc_from_csv(_csv_num(values), _csv_int(shape)))


def tensor_from_csv(values: str, shape: str) -> Tensor:
    return Tensor(torchc_from_csv(values, shape))


def zeros(shape: list) -> Tensor:
    return Tensor(torchc_zeros(_csv_int(shape)))


def ones(shape: list) -> Tensor:
    return Tensor(torchc_ones(_csv_int(shape)))


def full(shape: list, v: float) -> Tensor:
    return Tensor(torchc_full(_csv_int(shape), v))


def randn(shape: list, seed: int) -> Tensor:
    return Tensor(torchc_randn(_csv_int(shape), seed))


def arange(start: double, end: double, step: double) -> Tensor:
    return Tensor(torchc_arange(start, end, step))


# ============================== nn ==============================

class Module:
    """对标 torch.nn.Module：子类覆盖 forward / parameters。"""

    tag: str

    def __init__(self):
        self.tag = "module"

    def forward(self, x: Tensor) -> Tensor:
        return x

    def parameters(self) -> list:
        return []


class Linear(Module):
    """y = x @ w.T + b；w 形状 (out, in)、b 形状 (1, out)，与 torch.nn.Linear 一致。"""

    w: Tensor
    b: Tensor

    def __init__(self, n_in: int, n_out: int, seed: int):
        super().__init__()
        self.tag = "linear"
        # torch 默认是 uniform(-1/sqrt(in), 1/sqrt(in))；这里用 randn 缩放近似，
        # 只为「能训起来」——要逐位对齐就把权重灌进来（见 difftest）。
        scale: float = 1.0 / sqrt_float(n_in)
        self.w = randn([n_out, n_in], seed).mul_scalar(scale).requires_grad_(1)
        self.b = zeros([1, n_out]).requires_grad_(1)

    def load(self, w_csv: str, w_shape: str, b_csv: str, b_shape: str) -> None:
        """灌权重（差分成对拍用）：w 形状 (out, in)、b 形状 (1, out)。"""
        self.w = tensor_from_csv(w_csv, w_shape).requires_grad_(1)
        self.b = tensor_from_csv(b_csv, b_shape).requires_grad_(1)

    def forward(self, x: Tensor) -> Tensor:
        wt: Tensor = self.w.transpose(0, 1)
        prod: Tensor = x.matmul(wt)
        return prod.add(self.b)

    def parameters(self) -> list:
        out: list = []
        out.append(self.w)
        out.append(self.b)
        return out

    def zero_grad(self) -> None:
        self.w.zero_grad()
        self.b.zero_grad()


class ReLU(Module):
    def __init__(self):
        super().__init__()
        self.tag = "relu"

    def forward(self, x: Tensor) -> Tensor:
        return x.relu()


class Sigmoid(Module):
    def __init__(self):
        super().__init__()
        self.tag = "sigmoid"

    def forward(self, x: Tensor) -> Tensor:
        return x.sigmoid()


class Tanh(Module):
    def __init__(self):
        super().__init__()
        self.tag = "tanh"

    def forward(self, x: Tensor) -> Tensor:
        return x.tanh()


class MSELoss:
    """对标 torch.nn.MSELoss(reduction='mean')：mean((pred - target)^2)。"""

    tag: str

    def __init__(self):
        self.tag = "mse"

    def forward(self, pred: Tensor, target: Tensor) -> Tensor:
        diff: Tensor = pred.sub(target)
        sq: Tensor = diff.mul(diff)
        return sq.mean()


# ============================== optim ==============================

class SGD:
    """对标 torch.optim.SGD(params, lr)：step 走 torchc_sgd_step（NoGrad 原地 w -= lr*g）。"""

    params: list
    lr: float

    def __init__(self, params: list, lr: float):
        self.params = params
        self.lr = lr

    def zero_grad(self) -> None:
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            p.zero_grad()
            i += 1

    def step(self) -> int:
        n: int = 0
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            g: Tensor = p.grad()
            if torchc_is_tensor(g.h) != 0:
                torchc_sgd_step(p.h, g.h, self.lr)
                n += 1
            i += 1
        return n
