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

import math

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


# ---- v3：一元数学 / 归约 / 形状 / dtype / nn / 优化器 / 存取 ----
extern fn torchc_exp(a: ptr) -> ptr from "torchc"
extern fn torchc_log(a: ptr) -> ptr from "torchc"
extern fn torchc_sqrt(a: ptr) -> ptr from "torchc"
extern fn torchc_abs(a: ptr) -> ptr from "torchc"
extern fn torchc_pow_scalar(a: ptr, p: double) -> ptr from "torchc"

extern fn torchc_max(a: ptr) -> double from "torchc"
extern fn torchc_min(a: ptr) -> double from "torchc"
extern fn torchc_std(a: ptr, unbiased: int) -> double from "torchc"
extern fn torchc_argmax(a: ptr) -> int from "torchc"
extern fn torchc_max_dim(a: ptr, dim: int, want_index: int) -> ptr from "torchc"
extern fn torchc_min_dim(a: ptr, dim: int, want_index: int) -> ptr from "torchc"
extern fn torchc_mean_dim(a: ptr, dim: int) -> ptr from "torchc"

extern fn torchc_cat(a: ptr, b: ptr, dim: int) -> ptr from "torchc"
extern fn torchc_stack(a: ptr, b: ptr, dim: int) -> ptr from "torchc"
extern fn torchc_squeeze(a: ptr, dim: int) -> ptr from "torchc"
extern fn torchc_unsqueeze(a: ptr, dim: int) -> ptr from "torchc"
extern fn torchc_zeros_like(a: ptr) -> ptr from "torchc"
extern fn torchc_ones_like(a: ptr) -> ptr from "torchc"
extern fn torchc_empty_like(a: ptr) -> ptr from "torchc"

extern fn torchc_cast(a: ptr, dtype_name: str) -> ptr from "torchc"
extern fn torchc_zeros_dtype(shape: str, dtype_name: str) -> ptr from "torchc"
extern fn torchc_dtype(a: ptr) -> str from "torchc"
extern fn torchc_index_select(w: ptr, idx: str) -> ptr from "torchc"
extern fn torchc_flatten(a: ptr, start_dim: int) -> ptr from "torchc"
extern fn torchc_copy_into(dst: ptr, src: ptr) -> int from "torchc"

extern fn torchc_conv2d(x: ptr, w: ptr, b: ptr, sh: int, sw: int, ph: int, pw: int) -> ptr from "torchc"
extern fn torchc_max_pool2d(x: ptr, kh: int, kw: int, sh: int, sw: int) -> ptr from "torchc"
extern fn torchc_avg_pool2d(x: ptr, kh: int, kw: int, sh: int, sw: int) -> ptr from "torchc"
extern fn torchc_batch_norm(x: ptr, mean: ptr, var: ptr, gamma: ptr, beta: ptr, eps: double) -> ptr from "torchc"
extern fn torchc_cross_entropy(logits: ptr, target: str) -> ptr from "torchc"
extern fn torchc_l1_loss(pred: ptr, target: ptr) -> ptr from "torchc"
extern fn torchc_dropout(x: ptr, p: double, training: int, seed: int) -> ptr from "torchc"

extern fn torchc_sgd_step_momentum(w: ptr, g: ptr, buf: ptr, lr: double, momentum: double, weight_decay: double, nesterov: int) -> int from "torchc"
extern fn torchc_adam_step(w: ptr, g: ptr, m: ptr, v: ptr, lr: double, beta1: double, beta2: double, eps: double, weight_decay: double, step: int, decoupled: int) -> int from "torchc"
extern fn torchc_set_grad(w: ptr, g: ptr) -> int from "torchc"
extern fn torchc_lstm(x: ptr, wih: ptr, whh: ptr, bih: ptr, bhh: ptr, h0: ptr, c0: ptr, want: int) -> ptr from "torchc"
extern fn torchc_adagrad_step(w: ptr, g: ptr, acc: ptr, lr: double, lr_decay: double, weight_decay: double, eps: double, step: int) -> int from "torchc"
extern fn torchc_rmsprop_step(w: ptr, g: ptr, sq: ptr, lr: double, alpha: double, eps: double, weight_decay: double) -> int from "torchc"

extern fn torchc_set_grad_enabled(flag: int) -> int from "torchc"
extern fn torchc_is_grad_enabled() -> int from "torchc"

extern fn torchc_save(a: ptr, path: str) -> int from "torchc"
extern fn torchc_load(path: str) -> ptr from "torchc"


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

    def set_grad(self, g: Tensor) -> None:
        """对标 `p.grad = g`（差分灌梯度用；C 侧 detach().clone() 存进 mutable_grad）。"""
        torchc_set_grad(self.h, g.h)

    def grad_values(self) -> str:
        """梯度的 CSV（没有梯度时返回空串，与 torch 的 None 对应）"""
        g: Tensor = self.grad()
        if torchc_is_tensor(g.h) == 0:
            return ""
        return g.values()

    def zero_grad(self) -> None:
        torchc_zero_grad(self.h)

    # ---------- 生命周期 ----------
    # ---- v3：一元数学 ----

    def exp(self) -> Tensor:
        return Tensor(torchc_exp(self.h))

    def log(self) -> Tensor:
        return Tensor(torchc_log(self.h))

    def sqrt(self) -> Tensor:
        return Tensor(torchc_sqrt(self.h))

    def abs(self) -> Tensor:
        return Tensor(torchc_abs(self.h))

    def pow(self, p: float) -> Tensor:
        return Tensor(torchc_pow_scalar(self.h, p))

    # ---- v3：归约（标量返回 / dim 版）----

    def max(self) -> double:
        return torchc_max(self.h)

    def min(self) -> double:
        return torchc_min(self.h)

    def std(self, unbiased: int) -> double:
        return torchc_std(self.h, unbiased)

    def argmax(self) -> int:
        return torchc_argmax(self.h)

    def max_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_max_dim(self.h, dim, 0))

    def argmax_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_max_dim(self.h, dim, 1))

    def min_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_min_dim(self.h, dim, 0))

    def argmin_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_min_dim(self.h, dim, 1))

    def mean_dim(self, dim: int) -> Tensor:
        return Tensor(torchc_mean_dim(self.h, dim))

    # ---- v3：形状 ----

    def cat(self, other: Tensor, dim: int) -> Tensor:
        return Tensor(torchc_cat(self.h, other.h, dim))

    def stack(self, other: Tensor, dim: int) -> Tensor:
        return Tensor(torchc_stack(self.h, other.h, dim))

    def squeeze(self, dim: int) -> Tensor:
        return Tensor(torchc_squeeze(self.h, dim))

    def unsqueeze(self, dim: int) -> Tensor:
        return Tensor(torchc_unsqueeze(self.h, dim))

    def zeros_like(self) -> Tensor:
        return Tensor(torchc_zeros_like(self.h))

    def ones_like(self) -> Tensor:
        return Tensor(torchc_ones_like(self.h))

    def empty_like(self) -> Tensor:
        return Tensor(torchc_empty_like(self.h))

    # ---- v3：dtype ----

    def to(self, dtype_name: str) -> Tensor:
        return Tensor(torchc_cast(self.h, dtype_name))

    def bool(self) -> Tensor:
        return Tensor(torchc_cast(self.h, "bool"))

    def float(self) -> Tensor:
        return Tensor(torchc_cast(self.h, "float32"))

    def double(self) -> Tensor:
        return Tensor(torchc_cast(self.h, "float64"))

    def long(self) -> Tensor:
        return Tensor(torchc_cast(self.h, "int64"))

    def int(self) -> Tensor:
        return Tensor(torchc_cast(self.h, "int32"))

    def dtype(self) -> str:
        return torchc_dtype(self.h)

    # ---- v3：索引 / 落盘 ----

    def index_select(self, idx: list) -> Tensor:
        return Tensor(torchc_index_select(self.h, _csv_int(idx)))

    def save(self, path: str) -> int:
        return torchc_save(self.h, path)

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


# ============================== v3：nn 层 ==============================

class Conv2d(Module):
    """对标 nn.Conv2d：输入 NCHW，w 形状 (out, in, k, k)，b 形状 (out,)。"""

    w: Tensor
    b: Tensor
    stride: int
    padding: int

    def __init__(self, n_in: int, n_out: int, k: int, stride: int, padding: int, seed: int):
        super().__init__()
        self.tag = "conv2d"
        self.stride = stride
        self.padding = padding
        fan_in: int = n_in * k * k
        scale: float = 1.0 / sqrt_float(fan_in)
        self.w = randn([n_out, n_in, k, k], seed).mul_scalar(scale).requires_grad_(1)
        self.b = zeros([n_out]).requires_grad_(1)

    def load(self, w_csv: str, w_shape: str, b_csv: str, b_shape: str) -> None:
        self.w = tensor_from_csv(w_csv, w_shape).requires_grad_(1)
        self.b = tensor_from_csv(b_csv, b_shape).requires_grad_(1)

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_conv2d(x.h, self.w.h, self.b.h,
                                    self.stride, self.stride, self.padding, self.padding))

    def parameters(self) -> list:
        out: list = []
        out.append(self.w)
        out.append(self.b)
        return out

    def zero_grad(self) -> None:
        self.w.zero_grad()
        self.b.zero_grad()


class MaxPool2d(Module):
    def __init__(self, k: int, stride: int):
        super().__init__()
        self.tag = "maxpool2d"
        self.k = k
        self.stride = stride

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_max_pool2d(x.h, self.k, self.k, self.stride, self.stride))


class AvgPool2d(Module):
    def __init__(self, k: int, stride: int):
        super().__init__()
        self.tag = "avgpool2d"
        self.k = k
        self.stride = stride

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_avg_pool2d(x.h, self.k, self.k, self.stride, self.stride))


class Flatten(Module):
    """对标 nn.Flatten(start_dim=1)：保留 batch 维，其余展平。"""

    def __init__(self):
        super().__init__()
        self.tag = "flatten"

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_flatten(x.h, 1))


class Dropout(Module):
    """对标 nn.Dropout：eval 时恒等；train 时按 p 置零并缩放（C 侧内核算）。"""

    p: float
    training: int
    seed: int

    def __init__(self, p: float, seed: int):
        super().__init__()
        self.tag = "dropout"
        self.p = p
        self.seed = seed
        self.training = 1

    def eval(self) -> None:
        self.training = 0

    def train(self) -> None:
        self.training = 1

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_dropout(x.h, self.p, self.training, self.seed))


class BatchNorm1d(Module):
    """推理分支：y = (x - mean) / sqrt(var + eps) * gamma + beta（running stats 由 load 灌入）。"""

    mean: Tensor
    var: Tensor
    gamma: Tensor
    beta: Tensor
    eps: float

    def __init__(self, n: int, eps: float):
        super().__init__()
        self.tag = "batchnorm1d"
        self.eps = eps
        self.mean = zeros([n])
        self.var = ones([n])
        self.gamma = ones([n]).requires_grad_(1)
        self.beta = zeros([n]).requires_grad_(1)

    def load(self, mean_csv: str, var_csv: str, gamma_csv: str, beta_csv: str, n: int) -> None:
        """灌 running_mean / running_var / weight / bias（各 (C,) 一条 CSV）。"""
        nstr: str = _csv_int([n])
        self.mean = tensor_from_csv(mean_csv, nstr)
        self.var = tensor_from_csv(var_csv, nstr)
        self.gamma = tensor_from_csv(gamma_csv, nstr).requires_grad_(1)
        self.beta = tensor_from_csv(beta_csv, nstr).requires_grad_(1)

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(torchc_batch_norm(x.h, self.mean.h, self.var.h,
                                        self.gamma.h, self.beta.h, self.eps))

    def parameters(self) -> list:
        out: list = []
        out.append(self.gamma)
        out.append(self.beta)
        return out


class CrossEntropyLoss:
    """对标 nn.CrossEntropyLoss()：log_softmax + NLL，均值归约；target 是类别下标列表。"""

    tag: str

    def __init__(self):
        self.tag = "cross_entropy"

    def forward(self, logits: Tensor, target: list) -> Tensor:
        return Tensor(torchc_cross_entropy(logits.h, _csv_int(target)))

    def forward_t(self, logits: Tensor, target: Tensor) -> Tensor:
        """target 传 Tensor 时的入口（对标 F.cross_entropy 直接吃 long 张量）。"""
        return Tensor(torchc_cross_entropy(logits.h, target.values()))


class Embedding(Module):
    """对标 nn.Embedding(num, dim)：forward(下标列表) = weight[index_select(0)]。"""

    w: Tensor

    def __init__(self, num: int, dim: int, seed: int):
        super().__init__()
        self.tag = "embedding"
        scale: float = 1.0 / sqrt_float(dim)
        self.w = randn([num, dim], seed).mul_scalar(scale).requires_grad_(1)

    def load(self, w_csv: str, w_shape: str) -> None:
        self.w = tensor_from_csv(w_csv, w_shape).requires_grad_(1)

    def forward(self, idx: list) -> Tensor:
        return self.w.index_select(idx)

    def parameters(self) -> list:
        out: list = []
        out.append(self.w)
        return out


class L1Loss:
    """对标 nn.L1Loss()：mean(|pred - target|)。"""

    tag: str

    def __init__(self):
        self.tag = "l1"

    def forward(self, pred: Tensor, target: Tensor) -> Tensor:
        return Tensor(torchc_l1_loss(pred.h, target.h))


class Sequential(Module):
    """对标 nn.Sequential：按登记顺序 forward / 收参数。

    静态语言没有动态派发（docs/LANGUAGE.md「没有多态」），`layer: Module` 上的
    `layer.forward(..)` 会编译期直接绑到 `Module.forward`（原样返回 / 返回 []）。
    所以这里走「显式派发表」：子层按 kind + 同 kind 序号登记，forward 里按 kind 分支，
    每一支先把元素标注成具体类再调，派发点就落到了具体类上。
    """

    kinds: list
    idxs: list
    linears: list
    bns: list
    drops: list
    relu_m: ReLU
    sig_m: Sigmoid
    tanh_m: Tanh
    flat_m: Flatten

    def __init__(self):
        super().__init__()
        self.tag = "sequential"
        self.kinds = []
        self.idxs = []
        self.linears = []
        self.bns = []
        self.drops = []
        self.relu_m = ReLU()
        self.sig_m = Sigmoid()
        self.tanh_m = Tanh()
        self.flat_m = Flatten()

    def push(self, kind: str, idx: int) -> None:
        self.kinds.append(kind)
        self.idxs.append(idx)

    def add_linear(self, m: Linear) -> None:
        self.linears.append(m)
        self.push("linear", len(self.linears) - 1)

    def add_bn(self, m: BatchNorm1d) -> None:
        self.bns.append(m)
        self.push("bn", len(self.bns) - 1)

    def add_dropout(self, m: Dropout) -> None:
        self.drops.append(m)
        self.push("dropout", len(self.drops) - 1)

    def add_relu(self) -> None:
        self.push("relu", 0)

    def add_sigmoid(self) -> None:
        self.push("sigmoid", 0)

    def add_tanh(self) -> None:
        self.push("tanh", 0)

    def add_flatten(self) -> None:
        self.push("flatten", 0)

    def forward(self, x: Tensor) -> Tensor:
        y: Tensor = x
        i: int = 0
        while i < len(self.kinds):
            k: str = self.kinds[i]
            j: int = self.idxs[i]
            if k == "linear":
                l: Linear = self.linears[j]
                y = l.forward(y)
            if k == "bn":
                b: BatchNorm1d = self.bns[j]
                y = b.forward(y)
            if k == "dropout":
                d: Dropout = self.drops[j]
                y = d.forward(y)
            if k == "relu":
                y = self.relu_m.forward(y)
            if k == "sigmoid":
                y = self.sig_m.forward(y)
            if k == "tanh":
                y = self.tanh_m.forward(y)
            if k == "flatten":
                y = self.flat_m.forward(y)
            i += 1
        return y

    def parameters(self) -> list:
        out: list = []
        i: int = 0
        while i < len(self.linears):
            l: Linear = self.linears[i]
            ps: list = l.parameters()
            j: int = 0
            while j < len(ps):
                out.append(ps[j])
                j += 1
            i += 1
        i = 0
        while i < len(self.bns):
            b: BatchNorm1d = self.bns[i]
            qs: list = b.parameters()
            j = 0
            while j < len(qs):
                out.append(qs[j])
                j += 1
            i += 1
        return out

    def zero_grad(self) -> None:
        ps: list = self.parameters()
        i: int = 0
        while i < len(ps):
            p: Tensor = ps[i]
            p.zero_grad()
            i += 1


# ============================== v3：optim 扩展 ==============================

class MomentumSGD:
    """对标 torch.optim.SGD(params, lr, momentum, weight_decay, nesterov)。"""

    params: list
    bufs: list
    lr: float
    momentum: float
    weight_decay: float
    nesterov: int

    def __init__(self, params: list, lr: float = 0.001, momentum: float = 0.0,
                 weight_decay: float = 0.0, nesterov: int = 0):
        self.params = params
        self.lr = lr
        self.momentum = momentum
        self.weight_decay = weight_decay
        self.nesterov = nesterov
        self.bufs = []
        self.init_bufs()

    def init_bufs(self) -> None:
        """动量缓冲：必须放普通方法里做——__init__ 体不进类型环境（见 docs/MIGRATION.md「已知坑」）。"""
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            self.bufs.append(p.zeros_like())
            i += 1

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
                buf: Tensor = self.bufs[i]
                torchc_sgd_step_momentum(p.h, g.h, buf.h, self.lr, self.momentum,
                                         self.weight_decay, self.nesterov)
                n += 1
            i += 1
        return n


class Adam:
    """对标 torch.optim.Adam(params, lr, betas=(0.9,0.999), eps, weight_decay)。"""

    params: list
    ms: list
    vs: list
    lr: float
    beta1: float
    beta2: float
    eps: float
    weight_decay: float
    decoupled: int
    t: int

    def __init__(self, params: list, lr: float = 0.001, beta1: float = 0.9, beta2: float = 0.999,
                 eps: float = 1e-08, weight_decay: float = 0.0):
        self.params = params
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.weight_decay = weight_decay
        self.decoupled = 0
        self.t = 0
        self.ms = []
        self.vs = []
        self.init_state()

    def init_state(self) -> None:
        """m/v 一阶二阶矩：同 init_bufs，放普通方法里才拿得到局部类型。"""
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            self.ms.append(p.zeros_like())
            self.vs.append(p.zeros_like())
            i += 1

    def zero_grad(self) -> None:
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            p.zero_grad()
            i += 1

    def step(self) -> int:
        self.t += 1
        n: int = 0
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            g: Tensor = p.grad()
            if torchc_is_tensor(g.h) != 0:
                m: Tensor = self.ms[i]
                v: Tensor = self.vs[i]
                torchc_adam_step(p.h, g.h, m.h, v.h, self.lr, self.beta1, self.beta2,
                                 self.eps, self.weight_decay, self.t, self.decoupled)
                n += 1
            i += 1
        return n


class AdamW(Adam):
    """对标 torch.optim.AdamW：weight_decay 走 decoupled 分支（w -= lr*wd*w）。"""

    def __init__(self, params: list, lr: float = 0.001, beta1: float = 0.9, beta2: float = 0.999,
                 eps: float = 1e-08, weight_decay: float = 0.01):
        super().__init__(params, lr, beta1, beta2, eps, weight_decay)
        self.decoupled = 1


class Adagrad:
    """对标 torch.optim.Adagrad(params, lr=1e-2, lr_decay=0, weight_decay=0, eps=1e-10)。"""

    params: list
    accs: list
    lr: float
    lr_decay: float
    weight_decay: float
    eps: float
    t: int

    def __init__(self, params: list, lr: float = 0.01, lr_decay: float = 0.0,
                 weight_decay: float = 0.0, eps: float = 1e-10):
        self.params = params
        self.lr = lr
        self.lr_decay = lr_decay
        self.weight_decay = weight_decay
        self.eps = eps
        self.t = 0
        self.accs = []
        self.init_accs()

    def init_accs(self) -> None:
        """梯度平方累积：同 init_bufs。"""
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            self.accs.append(p.zeros_like())
            i += 1

    def zero_grad(self) -> None:
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            p.zero_grad()
            i += 1

    def step(self) -> int:
        self.t += 1
        n: int = 0
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            g: Tensor = p.grad()
            if torchc_is_tensor(g.h) != 0:
                acc: Tensor = self.accs[i]
                torchc_adagrad_step(p.h, g.h, acc.h, self.lr, self.lr_decay,
                                    self.weight_decay, self.eps, self.t)
                n += 1
            i += 1
        return n


class RMSprop:
    """对标 torch.optim.RMSprop(params, lr, alpha, eps, weight_decay)。"""

    params: list
    sqs: list
    lr: float
    alpha: float
    eps: float
    weight_decay: float

    def __init__(self, params: list, lr: float = 0.01, alpha: float = 0.99,
                 eps: float = 1e-08, weight_decay: float = 0.0):
        self.params = params
        self.lr = lr
        self.alpha = alpha
        self.eps = eps
        self.weight_decay = weight_decay
        self.sqs = []
        self.init_sqs()

    def init_sqs(self) -> None:
        """平方梯度累积：同 init_bufs。"""
        i: int = 0
        while i < len(self.params):
            p: Tensor = self.params[i]
            self.sqs.append(p.zeros_like())
            i += 1

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
                sq: Tensor = self.sqs[i]
                torchc_rmsprop_step(p.h, g.h, sq.h, self.lr, self.alpha, self.eps, self.weight_decay)
                n += 1
            i += 1
        return n


# ============================== v3：梯度模式 / 存取 ==============================

def set_grad_enabled(flag: int) -> int:
    return torchc_set_grad_enabled(flag)


def is_grad_enabled() -> int:
    return torchc_is_grad_enabled()


def load_tensor(path: str) -> Tensor:
    return Tensor(torchc_load(path))


# ============================== v3：lr_scheduler ==============================
#
# 偏差（翻译器现状，见下）：调度器**不持有优化器**，只按 torch 的公式算 lr，由调用方写回
# `opt.lr = sch.step()`。原因：静态类型写成 `opt: object` 后，`self.opt.lr` 会被翻译成未绑定
# 裸名、`self.opt.set_lr(...)` 会段错误 —— object 型成员当前不可用。写成「纯函数算 lr」
# 既绕开缺口，又保持数值与 torch 一致。


class StepLR:
    """对标 torch.optim.lr_scheduler.StepLR(opt, step_size, gamma)：
    第 n 轮 lr = base_lr * gamma ** (n // step_size)。用 `opt.lr = sch.step()` 写回。"""

    base_lr: float
    step_size: int
    gamma: float
    last_epoch: int

    def __init__(self, base_lr: float, step_size: int, gamma: float = 0.1):
        self.base_lr = base_lr
        self.step_size = step_size
        self.gamma = gamma
        self.last_epoch = 0

    def step(self) -> float:
        self.last_epoch += 1
        k: int = 0
        if self.step_size > 0:
            k = self.last_epoch // self.step_size
        return self.base_lr * (self.gamma ** k)


class ExponentialLR:
    """对标 ExponentialLR：第 n 轮 lr = base_lr * gamma ** n。"""

    base_lr: float
    gamma: float
    last_epoch: int

    def __init__(self, base_lr: float, gamma: float):
        self.base_lr = base_lr
        self.gamma = gamma
        self.last_epoch = 0

    def step(self) -> float:
        self.last_epoch += 1
        return self.base_lr * (self.gamma ** self.last_epoch)


class CosineAnnealingLR:
    """对标 CosineAnnealingLR(opt, T_max, eta_min)：
    lr = eta_min + (base_lr - eta_min) * (1 + cos(pi * t / T_max)) / 2（t 从 1 开始）。"""

    base_lr: float
    t_max: int
    eta_min: float
    last_epoch: int

    def __init__(self, base_lr: float, t_max: int, eta_min: float = 0.0):
        self.base_lr = base_lr
        self.t_max = t_max
        self.eta_min = eta_min
        self.last_epoch = 0

    def step(self) -> float:
        self.last_epoch += 1
        t: float = float(self.last_epoch)
        tm: float = float(self.t_max)
        frac: float = t / tm
        cosv: float = math.cos(math.pi * frac)
        return self.eta_min + (self.base_lr - self.eta_min) * (1.0 + cosv) / 2.0


def save_state_dict(params: list, paths: list) -> int:
    """把参数逐个落盘（一参数一文件，路径自己给全）；返回写成功的个数。"""
    if len(paths) != len(params):
        raise Exception("save_state_dict: paths 个数与 params 不符（会越界读垃圾指针，故直接拒绝）")
    n: int = 0
    i: int = 0
    while i < len(params):
        p: Tensor = params[i]
        path: str = paths[i]
        if torchc_save(p.h, path) != 0:
            n += 1
        i += 1
    return n


def load_state_dict(params: list, paths: list) -> int:
    if len(paths) != len(params):
        raise Exception("load_state_dict: paths 个数与 params 不符")
    n: int = 0
    i: int = 0
    while i < len(params):
        p: Tensor = params[i]
        path: str = paths[i]
        t: Tensor = load_tensor(path)
        if torchc_is_tensor(t.h) != 0:
            torchc_copy_into(p.h, t.h)
            n += 1
        i += 1
    return n

class LSTM:
    """torch.nn.LSTM 单层单向（batch_first=False）。

    权重顺序与 torch 的 flat_weights 一致 {w_ih, w_hh, b_ih, b_hh}，门序 i,f,g,o；
    数值落 at::lstm（ATen 内核），与 torch 逐位一致（float64 实测 max|Δ|=0）。
    forward(x) → out(seq,batch,hid)；另给 final_hidden / final_cell（h_n / c_n）。
    """

    w_ih: Tensor
    w_hh: Tensor
    b_ih: Tensor
    b_hh: Tensor
    hid: int
    n_in: int

    def __init__(self, n_in: int, n_hidden: int):
        self.n_in = n_in
        self.hid = n_hidden
        self.w_ih = zeros([0])
        self.w_hh = zeros([0])
        self.b_ih = zeros([0])
        self.b_hh = zeros([0])

    def load(self, wih_csv: str, whh_csv: str, bih_csv: str, bhh_csv: str) -> None:
        """灌权重（CSV 展平，行主序）：w_ih(4h,in) w_hh(4h,h) b_ih(4h) b_hh(4h)"""
        h4: int = 4 * self.hid
        self.w_ih = tensor_from_csv(wih_csv, str(h4) + "," + str(self.n_in))
        self.w_hh = tensor_from_csv(whh_csv, str(h4) + "," + str(self.hid))
        self.b_ih = tensor_from_csv(bih_csv, str(h4))
        self.b_hh = tensor_from_csv(bhh_csv, str(h4))

    def run(self, x: Tensor, want: int) -> Tensor:
        sh: str = x.shape()
        parts: list = sh.split(",")
        batch: int = string_to_int(parts[1])
        h0: Tensor = zeros([1, batch, self.hid])
        c0: Tensor = zeros([1, batch, self.hid])
        return Tensor(torchc_lstm(x.h, self.w_ih.h, self.w_hh.h, self.b_ih.h, self.b_hh.h,
                                  h0.h, c0.h, want))

    def forward(self, x: Tensor) -> Tensor:
        return self.run(x, 0)

    def final_hidden(self, x: Tensor) -> Tensor:
        return self.run(x, 1)

    def final_cell(self, x: Tensor) -> Tensor:
        return self.run(x, 2)
