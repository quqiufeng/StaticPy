#!/usr/bin/env python3
# [自举豁免 · 对照端] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是差分的「裁判」：一边是真 PyTorch（Python），一边是 plugins/ltorch 的 C ABI。
# 若把它改写进 StaticPy，被测物就成了自己的考官，判据立刻失效（AGENTS §0/§2）。
# 这里的 Python 只用于「测量对照」，不进任何产物链路。

"""plugins/ltorch/difftest.py — libTorch 绑定 vs PyTorch，逐值差分。

判据：同一份输入，PyTorch 算一遍、我们（真 at::Tensor 的 C ABI）算一遍，逐元素比 |Δ|。
lit 的算子都落在 ATen 的 double 路径，容差取 0（浮点逐位相同）；
唯一豁免 randn —— 随机流跨 torch 版本不保证一致（本机 /opt/libtorch 是 2.1.2，
Python torch 是 2.12.0），只比形状不比取值。

**两侧必须分进程**：pip 的 torch(2.12) 与 /opt/libtorch(2.1.2) 的 c10 符号互不兼容，
同一进程里先 dlopen 我们那侧再 import torch 会炸（libshm.so: undefined symbol）。
所以本文件是「裁判」：起两个子进程各算一遍，只比 JSON。

用法:
  python3 plugins/ltorch/difftest.py          # 快速差分
  python3 plugins/ltorch/difftest.py -v       # 打印每个用例的实际值
  python3 plugins/ltorch/difftest.py --elf    # 额外跑一遍 demo 的 ELF
退出码：0 全绿 / 1 有超差 / 2 环境缺失（无 torch 或未构建 .so）
"""
import json
import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SO = os.environ.get("STATICPY_LTORCH",
                    os.path.join(ROOT, "cpp", "torch", "build", "libtorch_capi.so"))
VERBOSE = "-v" in sys.argv
RUN_ELF = "--elf" in sys.argv
TOL = 0.0  # double 路径逐位相同；留这个常量便于临时放宽

BASE = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
EYE = [1.0, 0.0, 0.0, 1.0, 1.0, 1.0]  # 3x2
NEG = [-2.0, -0.5, 0.0, 0.5, 2.0, 3.0]
XV = [1.0, 2.0, 3.0]


def csv_of(xs):
    return ",".join([repr(float(v)) for v in xs])


def shape_csv(shape):
    return ",".join([str(int(d)) for d in shape])


def floats_of(csv):
    if csv is None or csv == "":
        return []
    return [float(v) for v in csv.split(",")]


# ================================================================ 我们的侧（ctypes）
def side_ours():
    import ctypes as C
    lib = C.CDLL(SO)
    P = C.c_void_p
    SIGS = [
        ("torchc_version", [], C.c_char_p),
        ("torchc_last_error", [], C.c_char_p),
        ("torchc_from_csv", [C.c_char_p, C.c_char_p], P),
        ("torchc_ones", [C.c_char_p], P),
        ("torchc_full", [C.c_char_p, C.c_double], P),
        ("torchc_randn", [C.c_char_p, C.c_long], P),
        ("torchc_arange", [C.c_double, C.c_double, C.c_double], P),
        ("torchc_sub", [P, P], P),
        ("torchc_mul", [P, P], P),
        ("torchc_matmul", [P, P], P),
        ("torchc_relu", [P], P),
        ("torchc_sigmoid", [P], P),
        ("torchc_tanh", [P], P),
        ("torchc_softmax", [P, C.c_long], P),
        ("torchc_sum", [P], P),
        ("torchc_mean", [P], P),
        ("torchc_sum_dim", [P, C.c_long], P),
        ("torchc_reshape", [P, C.c_char_p], P),
        ("torchc_transpose", [P, C.c_long, C.c_long], P),
        ("torchc_shape_csv", [P], C.c_char_p),
        ("torchc_to_csv", [P], C.c_char_p),
        ("torchc_item", [P], C.c_double),
        ("torchc_set_requires_grad", [P, C.c_long], C.c_long),
        ("torchc_backward", [P], C.c_long),
        ("torchc_grad", [P], P),
        ("torchc_add", [P, P], P),
        ("torchc_add_scalar", [P, C.c_double], P),
        ("torchc_zero_grad", [P], P),
        ("torchc_sgd_step", [P, P, C.c_double], C.c_long),
        ("torchc_is_tensor", [P], C.c_long),
        ("torchc_free", [P], None),
    ]
    for name, args, ret in SIGS:
        fn = getattr(lib, name)
        fn.argtypes = args
        fn.restype = ret

    def mk(values, shape):
        h = lib.torchc_from_csv(csv_of(values).encode(), shape_csv(shape).encode())
        if not h:
            raise RuntimeError("from_csv 失败: " + lib.torchc_last_error().decode())
        return h

    def vals(h):
        return floats_of(lib.torchc_to_csv(h).decode())

    def shape_of(h):
        return lib.torchc_shape_csv(h).decode()

    out = []
    a = mk(BASE, [2, 3])
    b = mk(EYE, [3, 2])
    n = mk(NEG, [2, 3])
    out.append(["matmul(2x3 @ 3x2)", vals(lib.torchc_matmul(a, b)), "2,2"])
    out.append(["a*a - a", vals(lib.torchc_sub(lib.torchc_mul(a, a), a)), "2,3"])
    out.append(["relu", vals(lib.torchc_relu(n)), "2,3"])
    out.append(["sigmoid", vals(lib.torchc_sigmoid(n)), "2,3"])
    out.append(["tanh", vals(lib.torchc_tanh(n)), "2,3"])
    out.append(["softmax(dim=1)", vals(lib.torchc_softmax(n, 1)), "2,3"])
    out.append(["sum(dim=0)", vals(lib.torchc_sum_dim(a, 0)), "3"])
    out.append(["sum", [lib.torchc_item(lib.torchc_sum(a))], ""])
    out.append(["mean", [lib.torchc_item(lib.torchc_mean(a))], ""])
    out.append(["reshape(6)", vals(lib.torchc_reshape(a, b"6")), "6"])
    out.append(["transpose(0,1)", vals(lib.torchc_transpose(a, 0, 1)), "3,2"])
    out.append(["arange(0,1,0.25)", vals(lib.torchc_arange(0.0, 1.0, 0.25)), "4"])
    out.append(["full(2x2, 3.5)", vals(lib.torchc_full(b"2,2", 3.5)), "2,2"])
    out.append(["ones(3)", vals(lib.torchc_ones(b"3")), "3"])
    hr = lib.torchc_randn(b"4,5", 7)
    out.append(["randn(4x5) 形状", [], shape_of(hr)])
    lib.torchc_free(hr)

    # autograd：loss = sum((x @ x^T)^2) → dloss/dx = 4*x*(x@x^T)
    x = mk(XV, [1, 3])
    lib.torchc_set_requires_grad(x, 1)
    p = lib.torchc_matmul(x, lib.torchc_transpose(x, 0, 1))
    loss = lib.torchc_sum(lib.torchc_mul(p, p))
    lib.torchc_backward(loss)
    out.append(["loss", [lib.torchc_item(loss)], ""])
    out.append(["dloss/dx", vals(lib.torchc_grad(x)), "1,3"])

    # 判型：句柄 vs 普通整数（Scheme 侧靠这张表区分标量与张量）
    a_probe = lib.torchc_from_csv(b"1.0", b"1,1")
    out.append(["is_tensor(句柄)", [float(lib.torchc_is_tensor(a_probe))], ""])
    out.append(["is_tensor(整数3)", [float(lib.torchc_is_tensor(3))], ""])
    lib.torchc_free(a_probe)
    out.append(["is_tensor(已释放)", [float(lib.torchc_is_tensor(a_probe))], ""])

    # 训练回路：linear + MSE + 200 步 SGD（与 PyTorch 同初值、同更新顺序）
    xt = mk([-2.0, -1.0, 0.0, 1.0, 2.0], [5, 1])
    yt = mk([-3.0, -1.0, 1.0, 3.0, 5.0], [5, 1])
    w = mk([0.0], [1, 1])
    bb = mk([0.0], [1, 1])
    lib.torchc_set_requires_grad(w, 1)
    lib.torchc_set_requires_grad(bb, 1)
    tloss = None
    for _ in range(200):
        lib.torchc_zero_grad(w)
        lib.torchc_zero_grad(bb)
        pred = lib.torchc_add(lib.torchc_matmul(xt, w), bb)
        d = lib.torchc_sub(pred, yt)
        tloss = lib.torchc_mean(lib.torchc_mul(d, d))
        lib.torchc_backward(tloss)
        lib.torchc_sgd_step(w, lib.torchc_grad(w), 0.1)
        lib.torchc_sgd_step(bb, lib.torchc_grad(bb), 0.1)
    out.append(["train200 w", vals(w), "1,1"])
    out.append(["train200 b", vals(bb), "1,1"])
    out.append(["train200 loss", [lib.torchc_item(tloss)], ""])

    # 错误路径：shape 与元素数不符必须报错（而不是静默算错）
    bad = lib.torchc_from_csv(b"1,2,3", b"2,2")
    msg = lib.torchc_last_error().decode()
    ok = (not bad) and ("shape" in msg)
    out.append(["坏 shape 报错", [1.0 if ok else 0.0], ""])
    if bad:
        lib.torchc_free(bad)
    return {"version": lib.torchc_version().decode(), "cases": out}


# ================================================================ 裁判侧（PyTorch）
def side_ref():
    import torch
    T = torch.tensor

    def ref(values, shape):
        return T(values, dtype=torch.float64).reshape(tuple(shape))

    out = []
    r = ref(BASE, [2, 3]) @ ref(EYE, [3, 2])
    out.append(["matmul(2x3 @ 3x2)", r.flatten().tolist(), shape_csv(tuple(r.shape))])
    a = ref(BASE, [2, 3])
    r = a * a - a
    out.append(["a*a - a", r.flatten().tolist(), shape_csv(tuple(r.shape))])
    n = ref(NEG, [2, 3])
    out.append(["relu", torch.relu(n).flatten().tolist(), "2,3"])
    out.append(["sigmoid", torch.sigmoid(n).flatten().tolist(), "2,3"])
    out.append(["tanh", torch.tanh(n).flatten().tolist(), "2,3"])
    out.append(["softmax(dim=1)", torch.softmax(n, 1).flatten().tolist(), "2,3"])
    out.append(["sum(dim=0)", torch.sum(a, 0).flatten().tolist(), "3"])
    out.append(["sum", [a.sum().item()], ""])
    out.append(["mean", [a.mean().item()], ""])
    out.append(["reshape(6)", a.reshape(6).tolist(), "6"])
    out.append(["transpose(0,1)", a.t().flatten().tolist(), "3,2"])
    out.append(["arange(0,1,0.25)",
                torch.arange(0.0, 1.0, 0.25, dtype=torch.float64).tolist(), "4"])
    out.append(["full(2x2, 3.5)",
                torch.full((2, 2), 3.5, dtype=torch.float64).flatten().tolist(), "2,2"])
    out.append(["ones(3)", torch.ones(3, dtype=torch.float64).tolist(), "3"])
    out.append(["randn(4x5) 形状", [], shape_csv(tuple(torch.randn(4, 5, dtype=torch.float64).shape))])

    x = ref(XV, [1, 3])
    x.requires_grad_(True)
    p = x @ x.t()
    loss = (p * p).sum()
    loss.backward()
    out.append(["loss", [loss.item()], ""])
    out.append(["dloss/dx", x.grad.flatten().tolist(), "1,3"])
    a_probe = T([1.0], dtype=torch.float64)
    out.append(["is_tensor(句柄)", [1.0], ""])
    out.append(["is_tensor(整数3)", [0.0], ""])
    out.append(["is_tensor(已释放)", [0.0], ""])

    # 训练回路（与 C ABI 侧同初值、同更新顺序）
    xt = ref([-2.0, -1.0, 0.0, 1.0, 2.0], [5, 1])
    yt = ref([-3.0, -1.0, 1.0, 3.0, 5.0], [5, 1])
    w = ref([0.0], [1, 1]).requires_grad_(True)
    bb = ref([0.0], [1, 1]).requires_grad_(True)
    tloss = None
    for _ in range(200):
        w.grad = None
        bb.grad = None
        pred = xt @ w + bb
        tloss = ((pred - yt) ** 2).mean()
        tloss.backward()
        with torch.no_grad():
            w -= 0.1 * w.grad
            bb -= 0.1 * bb.grad
    out.append(["train200 w", w.flatten().tolist(), "1,1"])
    out.append(["train200 b", bb.flatten().tolist(), "1,1"])
    out.append(["train200 loss", [tloss.item()], ""])

    out.append(["坏 shape 报错", [1.0], ""])
    return {"version": torch.__version__, "cases": out}


# ================================================================ 裁判
def maxdiff(mine, ref):
    if len(mine) != len(ref):
        return float("inf")
    worst = 0.0
    for i in range(len(mine)):
        d = math.fabs(mine[i] - ref[i])
        if d > worst:
            worst = d
    return worst


def run_side(flag):
    env = dict(os.environ)
    env.pop("LD_LIBRARY_PATH", None)  # 别让 /opt/libtorch 抢先污染 pip 的 torch
    p = subprocess.run([sys.executable, os.path.abspath(__file__), flag],
                       capture_output=True, env=env, timeout=600)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode())
        raise RuntimeError("子进程 " + flag + " 退出码 " + str(p.returncode))
    return json.loads(p.stdout.decode())


def compare(ours, ref):
    print("libtorch (C ABI) : " + ours["version"])
    print("PyTorch  (Python): " + ref["version"])
    print("so               : " + SO)
    fails = 0
    total = 0
    mine_all = ours["cases"]
    ref_all = ref["cases"]
    for i in range(len(mine_all)):
        name = mine_all[i][0]
        mine = mine_all[i][1]
        got_shape = mine_all[i][2]
        rvals = ref_all[i][1]
        want_shape = ref_all[i][2]
        total += 1
        d = maxdiff(mine, rvals)
        shape_ok = (want_shape == "" or got_shape == want_shape)
        bad = (d > TOL) or (not shape_ok)
        line = "  [" + ("FAIL" if bad else "ok") + "] " + name + "  max|Δ|=" + repr(d)
        if want_shape != "" or got_shape != "":
            line += "  shape=" + got_shape + "/" + want_shape
        print(line)
        if VERBOSE:
            print("       mine=" + repr(mine))
            print("       ref =" + repr(rvals))
        if bad:
            fails += 1
    return fails, total


def run_elf():
    exe = os.path.join(ROOT, "dist", "ltdemo")
    if not os.path.isfile(exe):
        exe = os.path.expanduser("~/iso_gen/ctlbin/ltdemo")
    print("  ELF: " + exe)
    if not os.path.isfile(exe):
        print("  [FAIL] 找不到 demo ELF（先 bash staticpy/static_build.sh ...）")
        return 1, 1
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = "/opt/libtorch/lib:" + env.get("LD_LIBRARY_PATH", "")
    p = subprocess.run([exe], env=env, capture_output=True)
    if p.returncode != 0:
        print("  [FAIL] ELF 退出码 " + str(p.returncode))
        return 1, 1
    print("  [ok] ELF 跑通（退出码 0）")
    return 0, 1


def main():
    argv = sys.argv[1:]
    if "--side=ours" in argv:
        print(json.dumps(side_ours()))
        return 0
    if "--side=ref" in argv:
        print(json.dumps(side_ref()))
        return 0
    if not os.path.isfile(SO):
        sys.stderr.write("缺 " + SO + "（先 bash cpp/torch/build.sh）\n")
        return 2
    ours = run_side("--side=ours")
    ref = run_side("--side=ref")
    fails, total = compare(ours, ref)
    if RUN_ELF:
        f, t = run_elf()
        fails += f
        total += t
    print("差分：" + str(total - fails) + "/" + str(total) + " 通过")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
