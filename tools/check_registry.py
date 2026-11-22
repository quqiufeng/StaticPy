#!/usr/bin/env python3
# [自举豁免 · 宿主] 编排/校验工具，不产出 IR，不进产物（AGENTS §0/§4）。
"""tools/check_registry.py — 预置名登记一致性检查（种子 ⇄ 自举 ⇄ 运行时）

## 为什么需要它

新增一个运行时函数必须在**两套翻译器**里各登记一次，而这两套实现互不校验：

  种子（CPython）    staticpy/static_translate.py : PRELUDE_FUNCTIONS / RUNTIME_MAP
  自举（StaticPy）   staticpy/emit_lib.static.py : PRELUDE_NAMES / scheme_name()
  运行时            tools/seed/prelude.scm（→ plugins/*/runtime.scm）

只登记一边的后果是**只在自举链路上炸**（种子里一切正常）：

  `variable static_scan_ident_end is not bound`   ← 缺 PRELUDE_NAMES
  `variable scan_ident_end is not bound`          ← 缺 scheme_name 的 kebab 映射

这两次都是靠手跑 `static_build.sh` 撞出来的。本工具把它们变成一条命令。

## 检的六条（全部静态，秒级）

  R1 两套登记表集合相同（种子 PRELUDE_FUNCTIONS ⇄ 自举 PRELUDE_NAMES）
  R2 kebab 映射两边一致（scheme_name() ⇄ RUNTIME_MAP，双重实现不许漂移）
  R3 映射指向的名字**确实定义**在运行时（防止映射表写成空指针）
  R4 运行时只以 kebab 形式定义的名字，必须有映射（否则「not bound」）
  R5 plugin.json 的 prelude_functions 是 PRELUDE_FUNCTIONS 的划分（无漏无重）
  R6 登记了但运行时没定义的名字 = 「外部名字」，须落在已知白名单

用法：
  python3 tools/check_registry.py           # 0=一致，1=漂移
  python3 tools/check_registry.py -v        # 附外部名字/孤儿定义清单
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_TA = os.path.join(ROOT, "staticpy/static_translate.py")
EMIT = os.path.join(ROOT, "staticpy/emit_lib.static.py")
RUNTIME_DIRS = [os.path.join(ROOT, "tools/seed")]
PLUG = os.path.join(ROOT, "plugins")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ 抽取
def rc_defined(text):
    """从 Scheme 源码抽「被绑定的顶层名字」

    覆盖四种绑定形式（运行时里都有）：
      (define (f a) ...)      (define f (lambda ...))
      (define f ...)          (define f (foreign-procedure ...))
    """
    out = set()
    for m in re.finditer(r"^\(define(?:-syntax)?\s+\(?([^\s()]+)", text, re.M):
        out.add(m.group(1))
    # define-record-type 隐式绑定：`name?` 谓词 + `make-name` 构造器
    # （pyarray 的 py-listv?/py-map? 就是谓词，不是凭空登记的幽灵名）
    for m in re.finditer(r"^\(define-record-type\s+([^\s()]+)", text, re.M):
        out.add(m.group(1) + "?")
        out.add("make-" + m.group(1))
    return out


def emit_tables():
    """staticpy/emit_lib.static.py → (PRELUDE_NAMES 集合, scheme_name 映射)"""
    src = read(EMIT)
    m = re.search(r"\bPRELUDE_NAMES\s*=\s*\((.*?)\n\)", src, re.S)
    if not m:
        raise SystemExit("[check_registry] emit_lib.static.py 里找不到 PRELUDE_NAMES")
    # 相邻字符串字面量隐式拼接（源码里就是这么写的）
    names = " ".join(re.findall(r'"([^"]*)"', m.group(1))).split()
    mapping = {}
    for mm in re.finditer(r'if nm == "([^"]+)":\s*\n\s*return "([^"]+)"', src):
        mapping[mm.group(1)] = mm.group(2)
    return names, mapping


def seed_tables():
    """static_translate.py → (PRELUDE_FUNCTIONS 集合, RUNTIME_MAP 映射)

    PRELUDE_FUNCTIONS 是 `{字面量} | MATH_FUNCTIONS` 的并集：**直接 import 求值**，
    不要用正则去抠集合字面量（第一版就漏掉了 21 个数学名，得出"只有自举登记"的假红）。
    RUNTIME_MAP 嵌在 runtime_map() 函数体里，只能文本抽。
    """
    src = read(SEED_TA)
    sys.path.insert(0, os.path.join(ROOT, "staticpy"))
    import static_translate as T
    fns = sorted(T.PRELUDE_FUNCTIONS)
    m2 = re.search(r"\bRUNTIME_MAP\s*=\s*\{(.*?)\n    \}", src, re.S)
    if not m2:
        raise SystemExit("[check_registry] static_translate.py 里找不到 RUNTIME_MAP")
    pairs = re.findall(r'"([^"]+)":\s*"([^"]+)"', m2.group(1))
    return fns, dict(pairs)


def plugin_claims():
    """plugin.json → {name: [引用它的插件]}"""
    claims = {}
    for name in sorted(os.listdir(PLUG)):
        pj = os.path.join(PLUG, name, "plugin.json")
        if not os.path.exists(pj):
            continue
        try:
            man = json.loads(read(pj))
        except Exception:
            continue
        for fn in man.get("prelude_functions", []):
            claims.setdefault(fn, []).append(name)
    return claims


def runtime_defs():
    """运行时里所有被 define 的顶层名字（seed + 各插件 runtime.scm）"""
    out = set()
    for d in RUNTIME_DIRS:
        for f in sorted(os.listdir(d)):
            if f.endswith(".scm"):
                out |= rc_defined(read(os.path.join(d, f)))
    for name in sorted(os.listdir(PLUG)):
        p = os.path.join(PLUG, name, "runtime.scm")
        if os.path.exists(p):
            out |= rc_defined(read(p))
    return out


# 登记了但运行时里没有 Scheme 定义的名字：由 Chez 内置或 foreign-procedure 别名提供。
# 每个都要**说得出出处**，不许往里塞「反正能跑」的名字。
EXTERNAL = {
    # Chez 内置算术（(chezscheme) 自带）
    "abs": "Chez", "acos": "Chez", "asin": "Chez", "atan": "Chez", "atan2": "Chez",
    "ceil": "Chez", "cos": "Chez", "cosh": "Chez", "exp": "Chez", "floor": "Chez",
    "fmod": "Chez", "log": "Chez", "log10": "Chez", "log2": "Chez", "pow": "Chez",
    "round": "Chez", "sin": "Chez", "sinh": "Chez", "sqrt": "Chez", "tan": "Chez",
    "tanh": "Chez", "truncate": "Chez",
    # 翻译器直接发出的原语/内联形式（不走预置名）
    "exit": "emit:primitive", "len": "emit:primitive", "range": "emit:primitive",
    "print": "emit:primitive", "open": "emit:primitive", "int": "emit:primitive",
    "float": "emit:primitive", "str": "emit:primitive", "bool": "emit:primitive",
    "list": "emit:primitive", "dict": "emit:primitive", "tuple": "emit:primitive",
    "sum": "emit:primitive", "min": "emit:primitive", "max": "emit:primitive",
    "sorted": "emit:primitive", "reversed": "emit:primitive", "enumerate": "emit:primitive",
    "zip": "emit:primitive", "isinstance": "emit:primitive", "callable": "emit:primitive",
    # CUDA 原语由 cuda 插件在用到时动态挂载（libcublas 未必在场）
    "cuda_gemm": "plugin:cuda", "cuda_gemm_tn": "plugin:cuda", "cuda_axpy": "plugin:cuda",
    "cuda_dot": "plugin:cuda", "cuda_copy": "plugin:cuda",
    "sleep": "plugin:libc", "clock": "plugin:libc", "argv": "plugin:libc",
}


def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    fails, warns = [], []

    names_emit, map_emit = emit_tables()
    names_seed, map_seed = seed_tables()
    defs = runtime_defs()
    claims = plugin_claims()

    set_emit, set_seed = set(names_emit), set(names_seed)

    # ---- R1 两套登记表集合相同
    only_seed = sorted(set_seed - set_emit)
    only_emit = sorted(set_emit - set_seed)
    if only_seed:
        fails.append("R1 只在种子登记（自举链路会 `not bound`）：" + " ".join(only_seed))
    if only_emit:
        fails.append("R1 只在自举登记（种子链路会 `not bound`）：" + " ".join(only_emit))
    dup = len(names_emit) - len(set_emit)
    if dup:
        fails.append(f"R1 自举 PRELUDE_NAMES 有 {dup} 个重复项")

    # ---- R2 kebab 映射两边一致
    for k in sorted(set(map_emit) | set(map_seed)):
        a, b = map_emit.get(k), map_seed.get(k)
        if a is not None and b is not None and a != b:
            fails.append(f"R2 映射不一致 {k}: 自举→{a} 种子→{b}")
        elif a is not None and b is None:
            fails.append(f"R2 缺种子侧映射 {k}→{a}（RUNTIME_MAP）")
        elif b is not None and a is None:
            fails.append(f"R2 缺自举侧映射 {k}→{b}（scheme_name）")

    # ---- R3 映射目标确实存在
    for k, v in sorted(map_emit.items()):
        if v not in defs:
            fails.append(f"R3 映射指向不存在的定义 {k}→{v}")

    # ---- R4 只以 kebab 形式定义（或有映射意图）的名字必须有映射
    for n in names_emit:
        if n in defs or scheme_kebab(n, map_emit) != n:
            continue
        kebab = n.replace("_", "-")
        if kebab in defs:
            fails.append(f"R4 运行时只有 kebab 定义 {kebab}，但 {n} 没登记映射（→ not bound）")

    # ---- R5 plugin.json 的 prelude_functions 覆盖 PRELUDE_FUNCTIONS
    # 注意 pyarray 等插件的 prelude_functions 是**手写**的（split_plugins 只在
    # 自动推导出内容时才覆写），所以「多出来的名字」合法，但必须在运行时里有定义。
    claimed = set(claims)
    miss = sorted(set_seed - claimed)
    extra = sorted(claimed - set_seed)
    twice = sorted(k for k, v in claims.items() if len(v) > 1)
    if miss:
        fails.append("R5 plugin.json 漏登记：" + " ".join(miss))
    ghost = [n for n in extra
             if n not in defs and n.replace("_", "-") not in defs and n not in EXTERNAL]
    if ghost:
        fails.append("R5 plugin.json 登记了运行时里查无此名的预置名：" + " ".join(ghost))
    if twice:
        fails.append("R5 同一预置名被多个插件声明：" + " ".join(twice))

    # ---- R6 登记了但运行时没定义 → 必须是已知外部名字
    external = [n for n in names_emit if scheme_kebab(n, map_emit) not in defs]
    unknown = sorted(n for n in external if n not in EXTERNAL)
    if unknown:
        fails.append("R6 登记了但运行时无定义、也不在白名单：" + " ".join(unknown))

    # ---- 孤儿：运行时定义了、却没进任何登记表（信息性，不判红）
    if verbose:
        orph = sorted(d for d in defs
                      if d not in set_emit and d not in EXTERNAL
                      and not any(k.replace("_", "-") == d for k in set_emit))
        print(f"运行时定义 {len(defs)} 个；外部名字 {len(external)} 个"
              f"（白名单核销 {len(external) - len(unknown)}）；"
              f"孤儿 {len(orph)} 个（内部辅助，不判红）")
        print("  外部：" + " ".join(sorted(external)))
        if orph:
            print("  孤儿示例：" + " ".join(orph[:12]) + (" …" if len(orph) > 12 else ""))

    if fails:
        print("预置名登记漂移：")
        for f in fails:
            print("  ✗ " + f)
        print("\n修复指引（AGENTS §5 四处登记）：")
        print("  1 tools/seed/prelude.scm 定义 → python3 tools/split_plugins.py")
        print("  2 staticpy/emit_lib.static.py : PRELUDE_NAMES + scheme_name() kebab 映射")
        print("  3 staticpy/static_translate.py : PRELUDE_FUNCTIONS + RUNTIME_MAP")
        return 1

    print(f"登记一致：{len(set_emit)} 个预置名 × 2 套实现 × {len(defs)} 个运行时定义"
          f"（外部 {len(external)}）")
    return 0


def scheme_kebab(n, mapping):
    return mapping.get(n, n)


if __name__ == "__main__":
    sys.exit(main())
