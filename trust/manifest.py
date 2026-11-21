#!/usr/bin/env python3
# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""manifest.py — 信任链清单：把「我们信什么」写成可校验的哈希账。

没有清单的信任链只是主张。清单把下列东西固定成具体字节：
  trust-root  信任根（selfhost/staticc.sp）—— 需要人读的那一小段
  seed        种子（staticpy/static_translate.py）—— 起爆用，冻结
  impl        实现（staticpy/*.static.py，环 2 自举编译器）
  tool        .sp 工具链二进制（spark / spboot_self）—— 不可读，只能靠 DDC 兜住
  harness     判定装置（check_*.sh / semantics_diff.py / trust/*）—— 判据本身也要防漂移
              其中 trust/ 下的脚本由 discover_harness() **自动收全**，不靠人记着登记
  cpp         我们手写的 C/C++（imgproc/ocr/face/…）—— 可审计，但以前没归因
  vendored    随仓库带进来的第三方源码（cpp/thirdparty/stb）—— 可审计，但非我们写
  lib         dlopen/DT_NEEDED 吃进来的系统 .so —— 可审计（有源码），本仓只能锁哈希

用法:
    python3 trust/manifest.py --write            # 重新生成 trust/manifest.json
    python3 trust/manifest.py --verify           # 校验，漂移则退出码 1
    python3 trust/manifest.py --verify-libs      # 只校验系统 .so 的 soname→哈希
    python3 trust/manifest.py --verify-thirdparty # 第三方源的上游版本串+哈希
    python3 trust/manifest.py --show             # 只看清单

--verify 是给 CI / selfcheck 用的：任何“被信任的文件”被改动，都必须显式重新签清单。
注意：清单不是加密签名（明文哈希可被一起改）。它的作用是**让改动无从隐蔽**，
     防的是「悄悄漂移」，不是「恶意重构」。真正的恶意由 trust/ddc.sh 兜住。
"""
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "trust", "manifest.json")

# role → 说明。顺序即审计顺序。
ENTRIES = [
    ("trust-root", "selfhost/staticc.sp",
     "信任根：用 .sp 语法写的编译器，人审计的就是它"),
    ("trust-root", "selfhost/staticc_split.sp",
     "信任根的拆分版（同源，用于分段审计）"),
    ("seed", "staticpy/static_translate.py",
     "种子：CPython+ast 翻译器，仅在起爆时用一次"),
    ("seed", "tools/seed/prelude.scm",
     "**运行时真源**（split_plugins.py 从它切出 plugins/ 再拼回 prelude）；改语义改这里"),
    ("seed", "tools/seed/stdlib_full.scm",
     "标准库真源（切出 plugins/*+ static_stdlib_full.scm）"),
    ("seed", "plugins/core/runtime.scm",
     "切分后的 core 运行时（构建实际读它）：位运算等兜底在此"),
    ("gen", "staticpy/static_prelude.scm",
     "**生成物**（勿手改）：prelude ⇄ plugins 必须同步，check 不过就别提交"),
    ("seed", "staticpy/static_stdlib.scm",
     "标准库（合并进 ELF）"),
    ("impl", "staticpy/static_translate.static.py",
     "环2 实现：词法器+驱动（自举，可被 ELF 顶替种子）"),
    ("impl", "staticpy/parse_lib.static.py", "环2 实现：解析器"),
    ("impl", "staticpy/emit_lib.static.py", "环2 实现：类型系统+代码生成"),
    ("impl", "staticpy/emit_dump.static.py", "环2 实现：入口薄壳"),
    ("impl", "selfhost/staticc.py",
     "环3 的另一份实现：Python 子集语法的编译器（DDC 的 C1）"),
    # 注：selfhost/examples/spark.sp（矢量图 DSL → SVG 的**示例**程序）与其产物
    # staticpy/spark 曾登记在此，但两处附注都是错的：spark 不是「.sp → Scheme 编译器」，
    # 它编译的是 .spark 图元 DSL；且两者都不在构建链上（对 *.sh/*.py grep 无引用），
    # staticpy/spark 还是 .gitignore 掉的构建产物。非信任链成员不该占清单条目，
    # 否则会让人误以为它们是必须 DDC 兜底的环节。
    ("harness", "selfcheck.sh", "一键自检"),
    ("harness", "staticpy/check_tokenize.sh", "判据：token 流差分（vs CPython tokenize）"),
    ("harness", "staticpy/check_parse.sh", "判据：AST 形状差分（vs CPython ast）"),
    ("harness", "staticpy/check_translate.sh", "判据：IR 逐字节差分（自举 vs 冻结种子）"),
    ("harness", "staticpy/semantics_diff.py", "判据：语义差分（CPython 跑 vs ELF 跑）"),
    ("harness", "trust/normalize_scm.py", "判据：IR token 级规范化（去注释/去空白）"),
    ("harness", "trust/ddc.sh", "判据：异源双编译交叉验证（环3 抗后门）"),
    ("harness", "trust/fixpoint.sh", "判据：三阶段固定点（自举收敛）"),
    ("harness", "trust/rebuild_spboot.sh",
     "把 ~/iso_gen/spboot/spboot_self 重编成当前源码产物（防止陈旧二进制冒充 C2）"),
]


# ── 自动发现：C/C++ 源码 与 系统 .so ─────────────────────────────────────────
CPP_EXTS = (".c", ".cc", ".cpp", ".h", ".hpp")
CPP_ROOTS = ["cpp"]
SKIP_DIRS = {"build", ".git", "node_modules", ".cache"}
VENDOR_MARK = "/thirdparty/"
# 我们自己产出的 .so（构建物，不入清单）
OWN_LIB_PREFIXES = ("libimgproc", "libocr", "libcvops", "libface", "libpathfind",
                    "libeasing", "libfont", "libhashlib", "libzlib", "libpyarr",
                    "libflorence2", "libbirefnet", "libwhisper", "libtorch_std",
                    "libllm", "libwarp", "libpose", "libeasing")
# 平台 ABI（glibc/libstdc++/…）：算不上「约定的一部分」，升级是常态。
# 我们只记录、提示版本变化，不判漂移；其余库按 pin 处理（哈希不符 = 拒）。
LIB_PLATFORM = ("libc.so", "libm.so", "libdl.so", "libpthread.so", "librt.so",
                "libstdc++.so", "libgcc_s.so", "libresolv.so", "libmvec.so",
                "ld-linux", "libutil.so", "libnsl.so", "libcrypt.so")
# 扫描库名时看的扩展名
SCAN_EXTS = (".scm", ".py", ".sh", ".cpp", ".h", ".hpp")
_LIB_RE = None


def discover_cpp():
    """枚举 cpp/ 下的 C/C++ 源码；thirdparty 归 vendored，其余归 cpp。"""
    out = []
    for r in CPP_ROOTS:
        base = os.path.join(ROOT, r)
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
            for f in sorted(fn):
                if not f.endswith(CPP_EXTS):
                    continue
                rel = os.path.relpath(os.path.join(dp, f), ROOT)
                role = "vendored" if VENDOR_MARK in "/" + rel else "cpp"
                out.append((role, rel,
                            "随仓库带入的第三方源码（非我们写）" if role == "vendored"
                            else "我们手写的 C/C++（可审计）"))
    return out


# trust/ 下要自动入清单的判据脚本（证据装置本身也是约定的一部分：
# 改 backend_drill.sh / fixpoint.sh 就等于改判据，必须让人看见）
HARNESS_ROOT = "trust"
HARNESS_EXTS = (".sh", ".py")
# 不入清单：清单自身（哈希自指无意义）、第三方出处索引（有自己的校验器）、缓存目录
HARNESS_SKIP = {"manifest.json", "thirdparty.json"}


def discover_harness():
    """枚举 trust/ 下所有 .sh/.py 判据脚本；已在 ENTRIES 里显式登记的不重复收。

    为什么要自动收：显式登记靠人记得住，漏一个就等于留了后门——
    改掉证据脚本不会有任何报警（这正是缺口 9）。
    """
    known = {rel for _role, rel, _why in ENTRIES}
    out = []
    base = os.path.join(ROOT, HARNESS_ROOT)
    if not os.path.isdir(base):
        return out
    for dp, dn, fn in os.walk(base):
        dn[:] = sorted(d for d in dn if d != "__pycache__" and not d.startswith("."))
        for f in sorted(fn):
            if not f.endswith(HARNESS_EXTS) or f in HARNESS_SKIP:
                continue
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            if rel in known:
                continue
            out.append(("harness", rel,
                        "判据/证据装置（自动收录：改它=改判据，必须显式重签）"))
    return out


def _arch_tags():
    """ldconfig 的架构标签写法（x86_64 机器上印的是 libc6,x86-64）。"""
    import platform
    m = platform.machine().lower()
    table = {
        "x86_64": ("x86-64", "x86_64", "amd64"),
        "aarch64": ("aarch64", "arm64"),
        "armv7l": ("arm", "armhf"),
        "i686": ("i686", "i386"),
        "riscv64": ("riscv64",),
        "ppc64le": ("ppc64le",),
    }
    return table.get(m, (m,))


def _ldconfig_map():
    """soname → 本机架构下的真实路径（避开 /libx32、/lib32 这类同名多架构条目）。"""
    try:
        out = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True).stdout
    except OSError:
        return {}
    tags = _arch_tags()
    cand = {}   # soname → [(rank, path)]
    for ln in out.splitlines():
        ln = ln.strip()
        if "=>" not in ln:
            continue
        left, path = ln.split("=>", 1)
        left, path = left.strip(), path.strip()
        if "(" in left and ")" in left:
            soname = left[:left.index("(")].strip()
            tag = left[left.index("(") + 1:left.index(")")].lower()
        else:
            soname, tag = left, ""
        rank = 1
        if any(t in tag for t in tags):
            rank = 0
        elif tag and all(t not in tag for t in tags) and soname in cand:
            rank = 2       # 别的架构（/lib32、/libx32），只有当同名项唯一时才采用
        cand.setdefault(soname, []).append((rank, path))
    amap = {}
    for soname, lst in cand.items():
        best = min(r for r, _ in lst)
        if best == 2 and len(lst) > 1:
            continue       # 多个候选且都不是本机架构 → 放弃（宁可 absent 也不错认）
        amap[soname] = next(p for r, p in lst if r == best)
    return amap


def discover_libs(resolved=None):
    """扫源码里出现的 lib*.so 名字，标出可解析的系统库。

    只认「名字在本机 ldconfig 里能解析」的，所以我们自己的构建产物天然被排除；
    可选依赖（libonnxruntime 等）装了才算一条，不装不占位。
    """
    import re
    names = set()
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".git")]
        for f in fn:
            if not f.endswith(SCAN_EXTS):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    t = fh.read()
            except OSError:
                continue
            for m in re.finditer(r"\blib[A-Za-z0-9_+.\-]+\.so(?:\.[0-9]+)*\b", t):
                n = m.group(0)
                if n.startswith(OWN_LIB_PREFIXES):
                    continue
                names.add(n)
    if resolved is None:
        resolved = _ldconfig_map()
    out = []
    for n in sorted(names):
        p = resolved.get(n)
        if not p or not os.path.exists(p):
            continue
        policy = "platform" if n.startswith(LIB_PLATFORM) else "pin"
        why = ("平台 ABI（记录但不判漂移）" if policy == "platform"
               else "dlopen/DT_NEEDED 依赖的系统 .so（源码可得；本仓锁 soname→哈希）")
        out.append(("lib", n, why, policy))
    return out


def digest(path):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def count_lines(path):
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return -1


def _entry(role, rel, why, target, resolved=None):
    """target = 真正要算哈希的文件；rel = 清单里记的名字（系统库记 soname）。"""
    if not os.path.exists(target):
        e = {"role": role, "path": rel, "why": why, "state": "MISSING"}
    else:
        sha, size = digest(target)
        e = {"role": role, "path": rel, "why": why, "state": "present",
             "sha256": sha, "bytes": size, "lines": count_lines(target)}
    if resolved:
        e["resolved"] = resolved
        e["exists"] = os.path.exists(resolved)
    return e


def snapshot(with_libs=True):
    out = {"_about": "StaticPy 信任链清单 — 由 trust/manifest.py --write 生成",
           "root": ROOT, "entries": []}
    for role, rel, why in ENTRIES:
        out["entries"].append(_entry(role, rel, why, os.path.join(ROOT, rel)))
    for role, rel, why in discover_cpp():
        out["entries"].append(_entry(role, rel, why, os.path.join(ROOT, rel)))
    for role, rel, why in discover_harness():
        out["entries"].append(_entry(role, rel, why, os.path.join(ROOT, rel)))
    if with_libs:
        cmap = _ldconfig_map()
        for role, name, why, policy in discover_libs(cmap):
            real = cmap.get(name)
            e = _entry(role, name, why, real or "", real)
            e["policy"] = policy
            out["entries"].append(e)
    return out


def verify_thirdparty(root=None):
    """第三方源码的上游出处校验（离线）：
    manifest 锁的是「我上次记的哈希」= 防本地漂移；
    thirdparty.json 记的是「它声称来自哪」= 防来源传闻。
    判据：文件里声明的版本串必须与 declared_version 一致，哈希与记录一致。
    """
    root = root or ROOT
    idx = os.path.join(root, "trust", "thirdparty.json")
    if not os.path.exists(idx):
        print("无 trust/thirdparty.json，跳过")
        return 0
    recs = json.load(open(idx, encoding="utf-8"))["entries"]
    bad, gone = [], []
    for r in recs:
        p = os.path.join(root, r["path"])
        if not os.path.exists(p):
            gone.append(r["path"])
            continue
        data = open(p, "rb").read()
        sha16 = hashlib.sha256(data).hexdigest()[:16]
        if sha16 != r["local_sha256_16"]:
            bad.append((r["path"], "哈希不符", r["local_sha256_16"], sha16))
            continue
        m = re.search(r["version_regex"], data.decode("utf-8", "replace"))
        found = m.group(0).split(" - ")[-1] if m else "?"
        if found != r["declared_version"]:
            bad.append((r["path"], "版本串不符", r["declared_version"], found))
    for x in gone:
        print("  [缺失] %s（记录在案但文件不在）" % x)
    if bad:
        print("第三方出处漂移 %d 项：" % len(bad))
        for path, why, a, b in bad:
            print("  [%s] %s  %s vs %s" % (why, path, a, b))
        print("\n若确实升级了 vendored 副本：同步改 trust/thirdparty.json 的")
        print("declared_version / local_sha256_16，再跑 trust/manifest.py --write。")
        return 1
    print("第三方出处一致（%d 项，版本串与哈希均对）" % len(recs))
    return 0


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--show"
    if mode == "--verify-thirdparty":
        return verify_thirdparty()
    snap = snapshot()

    if mode == "--write":
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
            f.write("\n")
        n = sum(1 for e in snap["entries"] if e["state"] == "present")
        print("已写 %s（%d 项）" % (MANIFEST, n))
        for e in snap["entries"]:
            if e["state"] == "MISSING":
                print("  MISSING", e["path"])
        return 0

    if mode == "--show":
        print("%-11s %-42s %8s %8s  %s" % ("role", "path", "bytes", "lines", "sha256"))
        for e in snap["entries"]:
            if e["state"] != "present":
                print("%-11s %-42s %8s %8s  %s" % (e["role"], e["path"], "-", "-", "MISSING"))
                continue
            print("%-11s %-42s %8d %8d  %s"
                  % (e["role"], e["path"], e["bytes"], e["lines"], e["sha256"][:16]))
        return 0

    if mode in ("--verify", "--verify-libs"):
        only_libs = mode == "--verify-libs"
        if not os.path.exists(MANIFEST):
            print("缺少 %s —— 先跑 --write" % MANIFEST)
            return 2
        with open(MANIFEST, encoding="utf-8") as f:
            old = json.load(f)
        prev = {e["path"]: e for e in old["entries"]}
        cur = {e["path"]: e for e in snap["entries"]}
        drift, absent, soft = [], [], []
        for path, p in prev.items():
            if p.get("role") != "lib" and only_libs:
                continue
            c = cur.get(path)
            if c is None:
                drift.append(("清单有、规则无", path, "-", "-")); continue
            # 系统库：装了就必须哈希一致；没装是「本机没有」，不算漂移（可选依赖）
            if p.get("role") == "lib":
                if not c.get("exists"):
                    absent.append(path); continue
                if p.get("sha256") != c.get("sha256"):
                    item = ("库被换掉", path,
                            str(p.get("sha256", "?"))[:12], c["sha256"][:12])
                    # 平台 ABI 升级是常态：记账但不判漂移（STRICT_LIBS=1 才当错）
                    if p.get("policy") == "platform" and not os.environ.get("STRICT_LIBS"):
                        soft.append(item)
                    else:
                        drift.append(item)
                elif p.get("resolved") != c.get("resolved"):
                    drift.append(("库路径变了", path,
                                  p.get("resolved", "?"), c.get("resolved", "?")))
                continue
            if c["state"] != "present":
                drift.append(("文件缺失", path, "-", "-")); continue
            if p.get("sha256") != c["sha256"]:
                drift.append(("内容漂移", path,
                              str(p.get("sha256", "?"))[:12], c["sha256"][:12]))
        if not only_libs:
            for path, c in cur.items():
                if path in prev:
                    continue
                if c.get("role") == "lib":
                    continue  # 新装的可选库不干扰仓库漂移判定
                drift.append(("新增未签", path, "-", "-"))
        for kind, path, a, b in soft:
            print("  [提示] %s %s  %s → %s（平台 ABI，升级属正常）"
                  % (kind, path, a, b))
        if drift:
            print("信任链漂移 %d 项：" % len(drift))
            for kind, path, a, b in drift:
                print("  [%s] %s  %s → %s" % (kind, path, a, b))
            print("\n如果这是**有意的**改动：跑 python3 trust/manifest.py --write 重新签，"
                  "\n并在提交信息里说明改了哪一环（改信任根 = 重走完整自举）。")
            return 1
        n_lib = sum(1 for e in prev.values() if e.get("role") == "lib")
        checked = n_lib if only_libs else len(cur)
        msg = "信任链无漂移（%d 项一致" % checked
        if only_libs:
            msg += "，系统 .so soname→sha256 全对"
        if absent:
            msg += "；%d 个可选库本机未装：%s" % (
                len(absent), ", ".join(absent[:4]) + ("…" if len(absent) > 4 else ""))
        print(msg + "）")
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
