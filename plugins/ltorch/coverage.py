#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是覆盖面的「裁判」：读 PyTorch 自省清单 + 我们的三个真源，核对我们声称的映射是否真的存在。
# 不产出 IR，不进产物链路（AGENTS §0/§2）。

"""coverage.py — 用 PyTorch 自省清单核对 ltorch 的覆盖面。

三源核验（防漂移）：MAP 里写的每个实现名，必须能在下列之一真找到：
  1. `cpp/torch/torch_capi.h`      —— C ABI 函数（torchc_*）
  2. `plugins/ltorch/runtime.scm`  —— Scheme 兼容层（torch-* / lt-*）
  3. `plugins/ltorch/tensor_lib.static.py` —— StaticPy 库（类 / 方法 / 顶层函数）

用法:
  python3 plugins/ltorch/coverage.py          # 覆盖率报告（markdown）
  python3 plugins/ltorch/coverage.py --check  # 只做漂移校验，rc!=0 即红
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
H = os.path.join(ROOT, "cpp/torch/torch_capi.h")
SCM = os.path.join(HERE, "runtime.scm")
LIB = os.path.join(HERE, "tensor_lib.static.py")

# ---------------------------------------------------------------- MAP
# PyTorch 名（域, 名）-> 我们的实现名。
# 值形态：`c:xxx` = C ABI；`s:xxx` = runtime.scm 定义；`p:xxx` = tensor_lib 符号；
#         list[...] = 需要多个符号；None = 已知未覆盖（显式记账，不算实现）。
MAP = {
    # ---- 创建 / 工厂 ----
    ("core", "tensor"): "s:torch-tensor",
    ("core", "zeros"): "s:torch-zeros",
    ("core", "ones"): "s:torch-ones",
    ("core", "full"): "s:torch-full",
    ("core", "arange"): "s:torch-arange",
    ("core", "randn"): "s:torch-randn",
    ("core", "zeros_like"): "p:Tensor.zeros_like",
    ("core", "ones_like"): "p:Tensor.ones_like",
    ("core", "empty"): "s:torch-empty",
    ("core", "manual_seed"): "s:torch-manual-seed",
    # ---- 四则 / 矩阵 ----
    ("core", "add"): "s:torch-add",
    ("core", "sub"): "s:torch-sub",
    ("core", "mul"): "s:torch-mul",
    ("core", "div"): "s:torch-div",
    ("core", "matmul"): "s:torch-matmul",
    ("core", "pow"): "s:torch-pow",
    ("core", "neg"): "s:torch-neg",
    ("core", "mm"): "c:torchc_matmul",
    # ---- 一元 / 激活 ----
    ("core", "relu"): "s:torch-relu",
    ("core", "sigmoid"): "s:torch-sigmoid",
    ("core", "tanh"): "s:torch-tanh",
    ("core", "softmax"): "s:torch-softmax",
    ("core", "exp"): ["c:torchc_exp", "p:Tensor.exp"],
    ("core", "log"): ["c:torchc_log", "p:Tensor.log"],
    ("core", "sqrt"): ["c:torchc_sqrt", "p:Tensor.sqrt"],
    ("core", "abs"): ["c:torchc_abs", "p:Tensor.abs"],
    # ---- 归约 ----
    ("core", "sum"): "s:torch-sum",
    ("core", "mean"): "s:torch-mean",
    ("core", "max"): ["c:torchc_max", "p:Tensor.max"],
    ("core", "min"): ["c:torchc_min", "p:Tensor.min", "p:Tensor.min_dim"],
    ("core", "argmax"): ["c:torchc_argmax", "p:Tensor.argmax", "p:Tensor.argmax_dim"],
    ("core", "std"): ["c:torchc_std", "p:Tensor.std"],
    # ---- 形状 ----
    ("core", "reshape"): "s:torch-reshape",
    ("core", "transpose"): "s:torch-transpose",
    ("core", "cat"): ["c:torchc_cat", "p:Tensor.cat"],
    ("core", "stack"): ["c:torchc_stack", "p:Tensor.stack"],
    ("core", "squeeze"): ["c:torchc_squeeze", "p:Tensor.squeeze"],
    ("core", "unsqueeze"): ["c:torchc_unsqueeze", "p:Tensor.unsqueeze"],
    # ---- autograd ----
    ("core", "backward"): "s:torch-backward",
    ("core", "no_grad"): "p:set_grad_enabled",
    ("core", "is_grad_enabled"): "p:is_grad_enabled",
    # ---- Tensor 成员 ----
    ("tensor", "tolist"): "s:torch-to-list",
    ("tensor", "item"): "s:torch-item",
    ("tensor", "numel"): "s:torch-numel",
    ("tensor", "dim"): "s:torch-numel",
    ("tensor", "ndim"): "c:torchc_ndim",
    ("tensor", "shape"): "c:torchc_shape_csv",
    ("tensor", "size"): "c:torchc_shape_csv",
    ("tensor", "backward"): "s:torch-backward",
    ("tensor", "grad"): "s:torch-grad",
    ("tensor", "detach"): "s:torch-detach",
    ("tensor", "clone"): "s:torch-clone",
    ("tensor", "zero_"): "s:torch-zero-grad",
    ("tensor", "requires_grad_"): "s:torch-set-requires-grad",
    ("tensor", "add"): "s:torch-add",
    ("tensor", "sub"): "s:torch-sub",
    ("tensor", "mul"): "s:torch-mul",
    ("tensor", "div"): "s:torch-div",
    ("tensor", "matmul"): "s:torch-matmul",
    ("tensor", "relu"): "s:torch-relu",
    ("tensor", "sigmoid"): "s:torch-sigmoid",
    ("tensor", "tanh"): "s:torch-tanh",
    ("tensor", "softmax"): "s:torch-softmax",
    ("tensor", "reshape"): "s:torch-reshape",
    ("tensor", "view"): "s:torch-reshape",
    ("tensor", "transpose"): "s:torch-transpose",
    ("tensor", "sum"): "s:torch-sum",
    ("tensor", "mean"): "s:torch-mean",
    # ---- nn（StaticPy 侧类）----
    ("nn", "Linear"): "p:Linear",
    ("nn", "Module"): "p:Module",
    ("nn", "ReLU"): "p:ReLU",
    ("nn", "Sigmoid"): "p:Sigmoid",
    ("nn", "Tanh"): "p:Tanh",
    ("nn", "MSELoss"): "p:MSELoss",
    ("nn", "Sequential"): "p:Sequential",
    ("nn", "Flatten"): "p:Flatten",
    ("nn", "Conv2d"): "p:Conv2d",
    ("nn", "MaxPool2d"): "p:MaxPool2d",
    ("nn", "BatchNorm1d"): "p:BatchNorm1d",
    ("nn", "Dropout"): "p:Dropout",
    ("nn", "CrossEntropyLoss"): "p:CrossEntropyLoss",
    ("nn", "L1Loss"): "s:torch-l1-loss",
    ("nn", "Embedding"): "p:Embedding",
    ("nn", "LSTM"): "p:LSTM",
    # ---- optim ----
    ("optim", "SGD"): "p:SGD",
    ("optim", "Adam"): "p:Adam",
    ("optim", "AdamW"): "p:AdamW",
    ("optim", "RMSprop"): "p:RMSprop",
    ("optim", "Adagrad"): "p:Adagrad",
    ("optim", "Optimizer"): ["p:MomentumSGD", "p:Adam", "p:AdamW", "p:RMSprop", "p:Adagrad"],
    ("optim", "lr_scheduler"): ["p:StepLR", "p:ExponentialLR", "p:CosineAnnealingLR"],
    # ---- dtype ----
    ("dtype", "float64"): "c:torchc_tensor",
    ("dtype", "float32"): ["c:torchc_cast", "p:Tensor.to"],
    ("dtype", "int64"): ["c:torchc_cast", "p:Tensor.to"],
    ("dtype", "bool"): "p:Tensor.bool",
}

# 分母：PyTorch 自省出的接口面规模（surface.py 的实测值）
DENOM = {"core": 962, "tensor": 610, "nn": 166, "optim": 16, "dtype": 12, "no_grad": 0}


def read(path):
    f = open(path, encoding="utf-8")
    txt = f.read()
    f.close()
    return txt


def symbols():
    """三源的真名集合。"""
    h = read(H)
    scm = read(SCM)
    lib = read(LIB)
    c = set(re.findall(r"\b(torchc_[a-z_0-9]+)\b", h))
    s = set(re.findall(r"^\(define\s+\(?([a-z0-9!?*<>=/+-]+)", scm, re.M))
    p = set(re.findall(r"^def ([a-z_0-9]+)", lib, re.M))
    classes = re.findall(r"^class ([A-Za-z_0-9]+)", lib, re.M)
    for cn in classes:
        p.add(cn)
    # 类方法：Class.method
    cur = ""
    for line in lib.split("\n"):
        m = re.match(r"^class ([A-Za-z_0-9]+)", line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^    def ([a-z_0-9]+)", line)
        if m and cur != "":
            p.add(cur + "." + m.group(1))
    return {"c": c, "s": s, "p": p}


def resolve(name, sym):
    """实现名 -> (ok, 真源标签)。"""
    if ":" not in name:
        return (False, "?")
    tag, rest = name.split(":", 1)
    table = sym.get(tag, set())
    if rest in table:
        return (True, tag)
    return (False, tag)


def flatten(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def main():
    check_only = "--check" in sys.argv
    sym = symbols()
    domains = ["core", "tensor", "nn", "optim", "dtype"]
    declared = {}
    verified = {}
    drift = []
    gaps = []
    for d in domains:
        declared[d] = 0
        verified[d] = 0
    for key in sorted(MAP.keys()):
        d = key[0]
        val = MAP[key]
        if val is None:
            gaps.append(key)
            continue
        declared[d] += 1
        vals = flatten(val)
        ok_all = True
        for v in vals:
            ok, tag = resolve(v, sym)
            if not ok:
                drift.append((key, v, tag))
                ok_all = False
        if ok_all:
            verified[d] += 1
    if drift:
        print("!! 漂移：MAP 声称的实现名在三源里找不到", file=sys.stderr)
        for key, v, tag in drift:
            print("   " + key[0] + "." + key[1] + " -> " + v + "（" + tag + " 源缺）", file=sys.stderr)
        return 1
    if check_only:
        print("ok（MAP " + str(len(MAP)) + " 条：已验证 " +
              str(sum(verified.values())) + "，显式未覆盖 " + str(len(gaps)) + "，漂移 0）")
        return 0
    print("# ltorch 覆盖面（vs PyTorch 自省清单）")
    print("")
    print("| 域 | PyTorch 实测 | 已声明 | 已验证 | 未覆盖 | 覆盖率 |")
    print("|---|---|---|---|---|---|")
    total_d = 0
    total_n = 0
    total_v = 0
    for d in domains:
        n = DENOM[d]
        dv = declared[d]
        vv = verified[d]
        pct = 0.0
        if n > 0:
            pct = 100.0 * vv / n
        print("| " + d + " | " + str(n) + " | " + str(dv) + " | " + str(vv) +
              " | " + str(n - vv) + " | " + ("%.1f%%" % pct) + " |")
        total_d += dv
        total_n += n
        total_v += vv
    pct = 0.0
    if total_n > 0:
        pct = 100.0 * total_v / total_n
    print("| **合计** | " + str(total_n) + " | " + str(total_d) + " | " + str(total_v) +
          " | " + str(total_n - total_v) + " | **" + ("%.1f%%" % pct) + "** |")
    print("")
    print("## 显式记账的缺口（" + str(len(gaps)) + "）")
    print("")
    line = ""
    for key in gaps:
        line += "`" + key[0] + "." + key[1] + "` "
    print(line)
    print("")
    print("分母取 `plugins/ltorch/ltorch_api.md` 的实测规模（顶层 962 / Tensor 610 / nn 166 /")
    print("optim 16 / dtype 12）。PyTorch 的 962 个顶层名里含大量别名与工具函数（`torch.utils`、")
    print("`torch.backends`、量化、分布式…），覆盖率按「已验证 / 实测总数」如实报，不做加权。")
    return 0


sys.exit(main())
