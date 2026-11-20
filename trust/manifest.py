#!/usr/bin/env python3
"""manifest.py — 信任链清单：把「我们信什么」写成可校验的哈希账。

没有清单的信任链只是主张。清单把下列东西固定成具体字节：
  trust-root  信任根（selfhost/staticc.sp）—— 需要人读的那一小段
  seed        种子（staticpy/static_translate.py）—— 起爆用，冻结
  impl        实现（staticpy/*.static.py，环 2 自举编译器）
  tool        .sp 工具链二进制（spark / spboot_self）—— 不可读，只能靠 DDC 兜住
  harness     判定装置（check_*.sh / semantics_diff.py / trust/*）—— 判据本身也要防漂移

用法:
    python3 trust/manifest.py --write            # 重新生成 trust/manifest.json
    python3 trust/manifest.py --verify           # 校验，漂移则退出码 1
    python3 trust/manifest.py --show             # 只看清单

--verify 是给 CI / selfcheck 用的：任何“被信任的文件”被改动，都必须显式重新签清单。
注意：清单不是加密签名（明文哈希可被一起改）。它的作用是**让改动无从隐蔽**，
     防的是「悄悄漂移」，不是「恶意重构」。真正的恶意由 trust/ddc.sh 兜住。
"""
import hashlib
import json
import os
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


def snapshot():
    out = {"_about": "StaticPy 信任链清单 — 由 trust/manifest.py --write 生成",
           "root": ROOT, "entries": []}
    for role, rel, why in ENTRIES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            out["entries"].append({"role": role, "path": rel, "why": why,
                                   "state": "MISSING"})
            continue
        sha, size = digest(p)
        out["entries"].append({
            "role": role, "path": rel, "why": why, "state": "present",
            "sha256": sha, "bytes": size, "lines": count_lines(p),
        })
    return out


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--show"
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

    if mode == "--verify":
        if not os.path.exists(MANIFEST):
            print("缺少 %s —— 先跑 --write" % MANIFEST)
            return 2
        with open(MANIFEST, encoding="utf-8") as f:
            old = json.load(f)
        prev = {e["path"]: e for e in old["entries"]}
        drift = []
        for e in snap["entries"]:
            p = prev.get(e["path"])
            if p is None:
                drift.append(("新增未签", e["path"], "-", "-"))
                continue
            if e["state"] != "present":
                drift.append(("文件缺失", e["path"], "-", "-")); continue
            if p.get("sha256") != e["sha256"]:
                drift.append(("内容漂移", e["path"],
                              str(p.get("sha256", "?"))[:12], e["sha256"][:12]))
        for path in prev:
            if path not in {e["path"] for e in snap["entries"]}:
                drift.append(("清单有、规则无", path, "-", "-"))
        if drift:
            print("信任链漂移 %d 项：" % len(drift))
            for kind, path, a, b in drift:
                print("  [%s] %s  %s → %s" % (kind, path, a, b))
            print("\n如果这是**有意的**改动：跑 python3 trust/manifest.py --write 重新签，"
                  "\n并在提交信息里说明改了哪一环（改信任根 = 重走完整自举）。")
            return 1
        print("信任链无漂移（%d 项全部一致）" % len(snap["entries"]))
        return 0

    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
