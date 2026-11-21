#!/usr/bin/env python3
# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""tools/split_plugins.py — 一次性迁移工具（可重跑）

把两块"大杂烩"运行时拆成 plugins/<name>/runtime.scm，并生成 plugin.json 的
运行时/模块表部分。kernel 从此只认 plugins/；static_prelude.scm 与
static_stdlib_full.scm 由插件重新拼装（保持旧构建脚本可用）。

用法: python3 tools/split_plugins.py [--check]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUG = os.path.join(ROOT, "plugins")

# ---------------------------------------------------------------- 运行时切片
# (起始行, 结束行(不含), 插件名)；按原始顺序拼接可还原整个文件。
# prelude 切片锚点：(段标题前缀, 插件名)。按标题锚定而非行号——
# 行号表会被 seed 的增删悄悄改坏：整块代码平移后，某段会落进**错误的插件**，
# 而构建只挑选用到的插件，落错=整段被丢弃（曾把 libc 的
# `(load-shared-object "libc.so.6")` 切进别的插件，产出的 ELF 启动即
# `no entry for "nanosleep"`）。标题写错/顺序颠倒会直接报错，不再静默。
# 同一插件可出现多段，按 seed 原文顺序拼进该插件的 runtime.scm。
PRELUDE_MARKS = [
    (";; ====== GC 跟踪",                  "core"),   # GC / 浮点数组 / None 单例 / 真值 / 成员
    (";; ====== 文件 I/O",                 "libc"),
    (";; ====== HTTP 客户端",              "http"),   # libcurl
    (";; ====== 数学函数（libm）",          "math"),
    (";; ====== JSON 解析",                "json"),   # libjansson
    (";; ====== 日期时间（libc）",          "libc"),
    (";; ====== CSV 读写",                 "csv"),
    (";; ====== 字符串工具（纯 Scheme",     "core"),
    (";; ====== 操作系统接口",              "libc"),
    (";; ====== 正则表达式",                "regex"),  # libpcre2
    (";; ====== 随机数（libc）",            "random"),
    (";; ====== 时间（libc）",              "libc"),   # 时间 + argv
    (";; ====== 字符串转数字",              "core"),
    (";; ====== 类型化数组/vector 工具",    "core"),   # vector 工具 + Option/Result + py-list
    (";; ====== IR 节点标签判断",           "ir"),     # 自举编译器 IR 标签
]

STDLIB_SLICE = [
    (9, 48, "openblas"),
    (48, 75, "lapack"),
    (75, 199, "cuda"),      # cublas / curand / cusolver / cudnn
    (199, 224, None),       # 与 http 插件重复，丢弃
    (224, 259, None),       # 与 json 插件重复，丢弃
    (259, 289, "xgboost"),
    (289, 316, "lightgbm"),
    (316, 341, "onnx"),
    (341, 576, "np"),
    (576, None, "torch"),
]

# 模块表 → 插件
MODULE_OWNER = {
    "np": "np", "la": "np", "cuda": "cuda", "torch": "torch", "nn": "torch",
    "math": "math", "random": "random", "json": "json",
    "time": "libc", "os": "libc", "urllib": "http",
}

# 函数名前缀 → 插件（return_types / prelude_functions）
PREFIX_OWNER = [
    ("np-", "np"), ("la-", "np"), ("cuda-", "cuda"), ("cuda_", "cuda"),
    ("torch-", "torch"), ("nn-", "torch"), ("ml-", "torch"),
    ("os_", "libc"), ("file_", "libc"), ("http_", "http"),
    ("parse_json", "json"), ("json_", "json"),
    ("clock", "libc"), ("sleep", "libc"), ("format_time", "libc"), ("now_ts", "libc"),
    ("random_", "random"), ("re_", "regex"), ("csv_", "csv"),
    ("str_", "core"), ("py_list", "core"), ("list_", "core"), ("vec_", "core"),
    ("make_", "core"), ("dict_", "core"), ("float_array", "core"),
    ("int_array", "core"), ("string_", "core"), ("integer_to_", "core"),
    ("argv", "libc"), ("exit", "libc"), ("pi", "math"), ("e", "math"),
]


# 插件元数据：依赖、加载顺序、动态库、说明
META = {
    "core": dict(order=10, requires=[], description="语言核心运行时：GC 指针托管、浮点/整数数组、字典、字符串工具、print、Option/Result、py-list"),
    "libc": dict(order=20, requires=["core"], libs={"c": "libc.so.6"}, description="libc 能力：文件 I/O、时间/日期、命令行参数、环境变量"),
    "http": dict(order=30, requires=["core", "libc"], libs={"curl": "libcurl.so.4"}, description="HTTP 客户端（libcurl）"),
    "math": dict(order=40, requires=["core"], libs={"m": "libm.so.6"}, description="libm 数学函数与常量"),
    "json": dict(order=50, requires=["core"], libs={"jansson": "libjansson.so.4"}, description="JSON 解析/序列化（libjansson）"),
    "csv": dict(order=60, requires=["core"], description="CSV 读写（纯 Scheme）"),
    "regex": dict(order=70, requires=["core"], libs={"pcre2": "libpcre2-8.so.0"}, description="正则表达式（libpcre2）"),
    "random": dict(order=80, requires=["core", "libc"], description="随机数（libc rand）"),
    "ir": dict(order=90, requires=["core"], description="自举编译器 IR 节点标签谓词"),
    "openblas": dict(order=100, requires=["core"], libs={"openblas": "libopenblas.so.0"}, description="BLAS 后端（OpenBLAS，可选加载）"),
    "lapack": dict(order=110, requires=["openblas"], libs={"lapack": "liblapacke.so"}, description="LAPACK 线性代数（可选加载）"),
    "np": dict(order=120, requires=["openblas", "lapack"], description="numpy/scipy 风格数组 API（tagged array）"),
    "cuda": dict(order=130, requires=["core"], libs={"cublas": "libcublas.so.12", "cudnn": "libcudnn.so.9"}, description="CUDA GPU 原语（由 libTorch 内部加载）"),
    "torch": dict(order=140, requires=["core", "np", "cuda"], description="libTorch 标准 API 包装：tensor/autograd/nn/JIT/SD/safetensors/采样器"),
    "xgboost": dict(order=150, requires=["core", "np"], libs={"xgboost": "libxgboost.so"}, description="XGBoost 树模型"),
    "lightgbm": dict(order=160, requires=["core", "np"], description="LightGBM 树模型"),
    "onnx": dict(order=170, requires=["core", "np"], libs={"onnxruntime": "libonnxruntime.so"}, description="ONNX Runtime 推理"),
}


def owner_of_fn(fn):
    for pre, plug in PREFIX_OWNER:
        if fn.startswith(pre):
            return plug
    return "math"


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


def _line_depths(lines):
    """每行行首的括号深度（0 = 顶层）。只数真实括号：跳过字符串、字符字面量、注释。"""
    depths, depth = [], 0
    for text in lines:
        depths.append(depth)
        i = 0
        while i < len(text):
            c = text[i]
            if c == ';':
                break
            if c == '"':
                i += 1
                while i < len(text):
                    if text[i] == '\\':
                        i += 2
                        continue
                    if text[i] == '"':
                        i += 1
                        break
                    i += 1
                continue
            if c == '#' and i + 1 < len(text) and text[i + 1] == '\\':
                j = i + 2
                if j < len(text) and text[j].isalpha():
                    while j < len(text) and text[j].isalnum():
                        j += 1
                else:
                    j += 1
                i = j
                continue
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            i += 1
    return depths


def _is_top_boundary(lines, depths, k):
    """该行是否是安全切点：处在顶层，且是空行或新 form 的起始"""
    if k <= 0 or k >= len(lines):
        return False
    if depths[k] != 0:
        return False
    text = lines[k]
    return (not text.strip()) or text[:1] not in (' ', '\t', ')')


def _snap(lines, idx, lo, hi, depths=None):
    """把切点吸附到最近的**顶层 form 边界**。

    只吸附到空行是不够的：letrec/let 内部也可能有空行，切在那里会把顶层 form
    从中间劈开（parse-json 被切进两个插件就是这么坏的）。这里改为按括号深度
    0 判定，行号表因此只作“大致位置”用，源码增删行都不会切坏 form。
    """
    if idx >= hi:
        idx = hi
    if idx <= lo:
        return lo
    if depths is None:
        depths = _line_depths(lines)
    if _is_top_boundary(lines, depths, idx):
        return idx
    for d in range(1, 400):
        for cand in (idx - d, idx + d):
            if lo < cand < hi and _is_top_boundary(lines, depths, cand):
                return cand
    return idx


def slice_and_group(lines, spans):
    """按 (start,end,plugin) 切片（1 基，end 不含），按插件累积（保持原文顺序）

    所有切点先按原顺序吸附到空行并保证单调，再按吸附后的位置切片；
    行号表因此只作“大致位置”用，运行时增删几行不会切坏顶层 form。
    """
    n = len(lines)
    raw = sorted({b for start, end, _ in spans for b in [start - 1] + ([end - 1] if end else [n])})
    snapped = {}
    prev = 0
    for b in raw:
        cur = _snap(lines, b, prev, n)
        if cur < prev:
            cur = prev
        snapped[b] = cur
        prev = cur
    out = {}
    for start, end, plug in spans:
        if plug is None:
            continue
        a = snapped[start - 1]
        b = snapped[end - 1] if end else n
        chunk = lines[a:b]
        out.setdefault(plug, []).append("\n".join(chunk).rstrip() + "\n")
    return out


def _dedup_plugins(plugs):
    """去重保序（同一插件在切片表里可能多段，拼装时只写一次）"""
    out, seen = [], set()
    for pl in plugs:
        if pl is None or pl in seen:
            continue
        seen.add(pl)
        out.append(pl)
    return out


def slice_by_marks(lines, marks, name="prelude"):
    """按段标题锚点切片：每段从标记行开始，到下一个标记行结束（最后一段到 EOF）。

    返回 {plugin: [chunk, ...]}，chunk 按 seed 原文顺序累积。
    标记缺失/顺序颠倒直接报错——这正是行号表静默错位时缺的那道防线。
    """
    idxs, prev = [], 0
    for mark, plug in marks:
        i = next((k for k in range(prev, len(lines)) if lines[k].startswith(mark)), None)
        if i is None:
            raise SystemExit(f"[split_plugins] {name}: 找不到段标记 {mark!r}"
                             f"（第 {prev + 1} 行之后）；改了 seed 就同步 PRELUDE_MARKS")
        if i == 0:
            raise SystemExit(f"[split_plugins] {name}: 段标记 {mark!r} 落在第 1 行，"
                             f"前面没有 banner 可丢弃")
        idxs.append((i, plug))
        prev = i + 1
    out = {}
    for j, (i, plug) in enumerate(idxs):
        end = idxs[j + 1][0] if j + 1 < len(idxs) else len(lines)
        out.setdefault(plug, []).append("\n".join(lines[i:end]).rstrip() + "\n")
    return out


def emit_legacy(check=False):
    """用插件重新拼装旧的两块单文件（兼容老构建脚本）

    check=True 时只比对不落盘：这样 --check 也能守住 prelude ⇄ plugins 的漂移
    （否则 prelude 里的 183 个重复定义改了一边、另一边不动，谁也发现不了）。
    拼接顺序 = 段标记/slice 表里的插件顺序（同一插件只写一次）。
    """
    changed = []
    targets = [
        ("staticpy/static_prelude.scm", _dedup_plugins([pl for _, pl in PRELUDE_MARKS]),
         ";; static_prelude.scm — StaticPy 核心运行时（由 plugins/ 自动拼装，勿手改）\n"
         ";; 单一事实来源: plugins/<name>/runtime.scm；改插件后跑 python3 tools/split_plugins.py\n\n(import (chezscheme))\n\n"),
        ("staticpy/static_stdlib_full.scm", _dedup_plugins([pl for _, _, pl in STDLIB_SLICE]),
         ";; static_stdlib_full.scm — StaticPy 全量扩展（由 plugins/ 自动拼装，勿手改）\n"
         ";; 单一事实来源: plugins/<name>/runtime.scm；按需选用，默认不合并\n\n"),
    ]
    for rel, plugs, banner in targets:
        parts = [banner]
        for plug in plugs:
            if plug is None:
                continue
            p = os.path.join(PLUG, plug, "runtime.scm")
            with open(p, encoding="utf-8") as f:
                body = f.read().rstrip() + "\n"
            parts.append(body)
        text = "".join(p if p.endswith("\n\n") else p + "\n" for p in parts)
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            changed.append(path)
    return changed


def main():
    check = "--check" in sys.argv
    prelude = read_lines(os.path.join(ROOT, "tools/seed/prelude.scm"))
    stdlib = read_lines(os.path.join(ROOT, "tools/seed/stdlib_full.scm"))

    groups = {}
    for plug, chunks in slice_by_marks(prelude, PRELUDE_MARKS).items():
        groups.setdefault(plug, {})["runtime"] = "\n".join(chunks)
    for plug, chunks in slice_and_group(stdlib, STDLIB_SLICE).items():
        groups.setdefault(plug, {})["runtime"] = \
            groups.get(plug, {}).get("runtime", "") + "\n" + "\n".join(chunks)

    # 模块表/返回类型从 translator 抽取（import 其全局表）
    sys.path.insert(0, os.path.join(ROOT, "staticpy"))
    import static_translate as T

    tables = {name: {} for name in groups}
    for mod, fns in T.BUILTIN_MODULES.items():
        owner = MODULE_OWNER.get(mod)
        if not owner:
            print(f"  ! 模块 {mod} 无归属，跳过")
            continue
        tables.setdefault(owner, {}).setdefault("modules", {})[mod] = fns
    for (a, b), fns in T.NESTED_MODULES.items():
        owner = MODULE_OWNER.get(a, "core")
        tables.setdefault(owner, {}).setdefault("nested_modules", {})[f"{a}.{b}"] = fns
    for fn, ty in T.MODULE_FN_RETURN_TYPES.items():
        owner = owner_of_fn(fn)
        tables.setdefault(owner, {}).setdefault("return_types", {})[fn] = str(ty)
    for fn in sorted(T.PRELUDE_FUNCTIONS):
        owner = owner_of_fn(fn)
        tables.setdefault(owner, {}).setdefault("prelude_functions", []).append(fn)

    # 写出
    changed = []
    for name, data in sorted(tables.items()):
        d = os.path.join(PLUG, name)
        os.makedirs(d, exist_ok=True)
        rt = groups.get(name, {}).get("runtime")
        if rt is not None:
            p = os.path.join(d, "runtime.scm")
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != rt:
                changed.append(p)
                if not check:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(rt)
        pj = os.path.join(d, "plugin.json")
        manifest = {}
        if os.path.exists(pj):
            with open(pj, encoding="utf-8") as f:
                manifest = json.load(f)
        meta = META.get(name, {})
        manifest.setdefault("name", name)
        manifest.setdefault("version", "1.0.0")
        manifest.setdefault("kind", "runtime")
        manifest["order"] = meta.get("order", manifest.get("order", 999))
        manifest["requires"] = meta.get("requires", manifest.get("requires", []))
        if meta.get("libs"):
            manifest["libs"] = meta["libs"]
        if os.path.exists(os.path.join(d, "runtime.scm")):
            manifest["runtime"] = ["runtime.scm"]
        if not manifest.get("description"):
            manifest["description"] = meta.get("description", "")
        for k in ("modules", "nested_modules", "return_types", "prelude_functions"):
            if data.get(k):
                manifest[k] = data[k]
        text = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        if not os.path.exists(pj) or open(pj, encoding="utf-8").read() != text:
            changed.append(pj)
            if not check:
                with open(pj, "w", encoding="utf-8") as f:
                    f.write(text)

    # 旧构建脚本仍读 static_prelude.scm / static_stdlib_full.scm：
    # 由插件重新拼装（保持原切片顺序），单一事实来源 = plugins/
    changed += emit_legacy(check=check)

    if check and changed:
        print("插件与源文件不同步：")
        for c in changed:
            print("  " + os.path.relpath(c, ROOT))
        return 1
    print(f"插件目录：{', '.join(sorted(tables))}")
    print(f"变更 {len(changed)} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
