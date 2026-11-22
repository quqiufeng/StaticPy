#!/usr/bin/env python3
# [自举豁免 · 宿主] 静态检查 FFI 声明契约，不产出 IR，不进产物（AGENTS §0/§4）。
"""tools/check_ffi.py — 机器校验 `extern fn` 声明是否符合 FFI 契约（docs/FFI.md）

契约靠人记必然漂移，所以把它写成红/绿：

  R1 返回类型只能是 str/int/float/double/bool/ptr 或 list[...]（**不许 void**——C 侧改成返回 int）
  R2 参数类型同上（未知类型在 ABI 上按 void* 处理，等于把类型错误推给运行期）
  R3 `from "<lib>"` 的逻辑库名要能解析成 soname：STATICPY_LIB_<LIB> > 插件 libs 映射 > lib<lib>.so；
     三者都没有时告警（运行期 dlopen 大概率失败，且失败得晚、报错难懂）
  R4 声明必须在文件顶部区域（第一个 def/class 之前）——放进函数体不是 FFI 声明
  R5 同一文件里同名 extern 不许重复（重复 define 会覆盖前一条 ABI）
  R6 extern 名不得与运行时预置名撞名（撞了等于两条 ABI 抢同一个符号）

用法：
  python3 tools/check_ffi.py                 # 扫仓库内 *.static.py
  python3 tools/check_ffi.py a.static.py     # 只查指定文件
  python3 tools/check_ffi.py --warn          # 告警也当失败（严格模式）
退出码：0 一致 / 1 有硬错误 / 2 参数错
"""
import glob
import json
import os
import re
import sys

OK_TYPES = {"int", "float", "double", "bool", "str", "ptr"}
LIST_RE = re.compile(r"^list\[.*\]$")

# extern fn name(a: t, b: t) -> ret from "lib"
#   声明允许折行（参数表太长时），所以先按 `from "…"` 归并成一条逻辑行再解析；
#   这里不用 DOTALL 正则直接扫全文——那样会把两条声明连成一条，且漏掉"缺返回类型"。
DECL_RE = re.compile(r"^\s*extern\s+fn\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*(?:->\s*(.*?))?\s*from\s+\"([^\"]*)\"\s*$")
PARAM_RE = re.compile(r"([A-Za-z_]\w*)\s*:\s*([^,=)]+)")


def find_decls(text):
    """返回 [(行号, 逻辑行)]——从 `extern fn` 起到含 `from "` 的行止。

    用列表而非惰性产出：本仓的检查器自身也要能被 StaticPy 前端解析（子集没有生成器）。
    """
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if re.match(r"^\s*extern\s+fn\s", lines[i]):
            start = i
            buf = lines[i]
            while 'from "' not in buf and i + 1 < len(lines) and i - start < 8:
                i += 1
                buf += " " + lines[i].strip()
            out.append((start + 1, buf))
        i += 1
    return out

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_plugin_libs():
    """逻辑库名 → soname，汇总所有插件的 libs 映射"""
    out = {}
    for p in glob.glob(os.path.join(ROOT, "plugins", "*", "plugin.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        libs = d.get("libs") or {}
        if isinstance(libs, dict):
            for k, v in libs.items():
                out.setdefault(k, (v, os.path.basename(os.path.dirname(p))))
    return out


def load_prelude_names():
    """运行时预置名：从 emit_lib 的 PRELUDE_NAMES 文本抽取（避免 import 翻译器）"""
    src = os.path.join(ROOT, "staticpy", "emit_lib.static.py")
    names = set()
    try:
        text = open(src, encoding="utf-8").read()
    except OSError:
        return names
    m = re.search(r"PRELUDE_NAMES\s*=\s*\((.*?)\n\)", text, re.DOTALL)
    if m:
        for w in re.findall(r'"([^"]*)"', m.group(1)):
            for n in w.split():
                names.add(n)
    return names


def type_ok(t):
    t = t.strip()
    return t in OK_TYPES or bool(LIST_RE.match(t))


def check_file(path, plugin_libs, prelude_names):
    """返回 (errors, warns)"""
    errs, warns = [], []
    try:
        text = open(path, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        return errs, warns
    lines = text.splitlines()

    # 第一个 def/class 的行号：上面是"顶部区域"
    top_end = len(lines)
    for i, ln in enumerate(lines):
        if re.match(r"^(def |class |async def )", ln):
            top_end = i
            break

    seen = {}
    for line_no, logical in find_decls(text):
        m = DECL_RE.match(logical)
        if not m:
            errs.append(f"{path}:{line_no} 无法解析的 extern 声明：{logical.strip()[:80]}")
            continue
        name, params, ret, lib = m.group(1), m.group(2), m.group(3) or "", m.group(4)

        # R6 撞运行时预置名
        if name in prelude_names:
            errs.append(f"{path}:{line_no} R6 extern `{name}` 与运行时预置名撞名")

        # R1 返回类型
        ret_t = ret.strip()
        if ret_t in ("void", "None", ""):
            errs.append(f"{path}:{line_no} R1 `{name}` 返回 {ret_t or '空'}——C 侧须改成返回 int")
        elif not type_ok(ret_t):
            errs.append(f"{path}:{line_no} R1 `{name}` 返回类型 `{ret_t}` 不在 "
                        f"{sorted(OK_TYPES)} / list[...] 内")

        # R2 参数类型（空参数表合法）
        for pname, ptype in PARAM_RE.findall(params):
            if not type_ok(ptype):
                errs.append(f"{path}:{line_no} R2 `{name}` 参数 `{pname}: {ptype.strip()}` "
                            f"不在白名单内（会被当成 void*）")

        # R3 库名可解析
        if not re.match(r"^[a-z0-9_]+$", lib):
            errs.append(f"{path}:{line_no} R3 `{name}` 逻辑库名 `{lib}` 应为小写字母/数字/下划线")
        else:
            env_key = "STATICPY_LIB_" + lib.upper()
            if lib in plugin_libs:
                pass  # 插件映射（或运行期 env 覆盖），合法
            elif not os.environ.get(env_key):
                warns.append(f"{path}:{line_no} R3 `{name}` 库 `{lib}` 无插件 libs 映射，"
                             f"需运行期设 {env_key}=<soname>，否则按 lib{lib}.so dlopen")

        # R4 顶部区域
        if line_no > top_end:
            errs.append(f"{path}:{line_no} R4 `{name}` 声明出现在第一个 def/class 之后"
                        f"（第 {top_end} 行），不是 FFI 声明区")

        # R5 同文件重名
        if name in seen:
            errs.append(f"{path}:{line_no} R5 extern `{name}` 与第 {seen[name]} 行重复声明")
        else:
            seen[name] = line_no
    return errs, warns


def main(argv):
    strict = "--warn" in argv
    files = [a for a in argv if not a.startswith("-")]
    if files:
        targets = files
    else:
        targets = sorted(glob.glob(os.path.join(ROOT, "**", "*.static.py"), recursive=True))
        targets = [t for t in targets if "/.git/" not in t]
    plugin_libs = load_plugin_libs()
    prelude_names = load_prelude_names()

    all_errs, all_warns, n_decls = [], [], 0
    for t in targets:
        e, w = check_file(t, plugin_libs, prelude_names)
        n_decls += len(list(find_decls(open(t, encoding="utf-8").read()))) if os.path.isfile(t) else 0
        all_errs += e
        all_warns += w

    for line in all_errs:
        print("  ERR  " + line)
    for line in all_warns:
        print("  warn " + line)
    if all_errs or (strict and all_warns):
        print(f"---- {len(targets)} 个文件 / {n_decls} 条声明，"
              f"错误 {len(all_errs)} 项，告警 {len(all_warns)} 项")
        return 1
    print(f"FFI 契约一致：{len(targets)} 个文件 × {n_decls} 条 extern fn 声明"
          f"（告警 {len(all_warns)} 项，见 docs/FFI.md）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
