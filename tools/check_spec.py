#!/usr/bin/env python3
# [自举豁免 · 检查器] 本文件不参与自举链，只做 CI 门禁；但它**自己**要能过
# `check_parse.sh`（全仓 *.py 都当参考实现来解析），所以刻意只写 Python 子集：
# 不用 yield / 不用装饰器 / 不用 dict 推导式，函数返回值一律显式。
"""check_spec.py — docs/SPEC.md 的语义条目索引 ⇄ tests/semantics/ 用例双向一致。

要守的两件事（评估报告第 3 条短板："自举成功 ≠ 正确"）：
  1. **没有判据的承诺**是谎话：§1 每条语义必须钉住至少一个可跑的用例；
  2. **没有条目的用例**会悄悄腐烂：tests/semantics/ 下每个用例必须被索引引用。

规则：
  R1 表行三列齐全（编号 | 语义要点 | 用例）；
  R2 编号形如 S-XXX、全表唯一（发布后不复用、不改义）；
  R3 索引里的用例文件必须真存在；
  R4 tests/semantics/ 下的用例必须都被引用（孤儿用例 = 红）；
  R5 §2 的 `# expect:` 登记与实际文件头一致（双向：多登记/漏登记都红），
     且被登记的预期失败用例必须在 §1 里也有条目。

用法：
  python3 tools/check_spec.py        # rc=0 一致；rc=1 列出全部不一致
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "docs", "SPEC.md")
CASES = os.path.join(ROOT, "tests", "semantics")
SUFFIX = ".static.py"
ID_RE = re.compile(r"^S-[A-Z][A-Z0-9]*$")
EXPECT_RE = re.compile(r"expect:\s*([a-z]+-error)")


def cells(line):
    """把 `| a | b | c |` 切成去空白的列；不是表行返回 None。

    Markdown 表格里的 `\\|` 是**转义的分隔符**，不能真当分隔符切
    （语义列里写 `a | b` 就会把列数打乱）——先换成占位符，切完再换回来。
    """
    if not line.startswith("|"):
        return None
    line = line.replace("\\|", "\x01")
    parts = line.split("|")
    parts = [p.replace("\x01", "|") for p in parts]
    parts = [p.strip() for p in parts]
    if len(parts) < 3:
        return None
    # 首尾是空串（行首/行尾的 |）
    inner = parts[1:len(parts) - 1]
    return inner


def split_cases(cell):
    """用例列：逗号分隔，容忍空项；兼容误写 `.static.py` 后缀"""
    out = []
    for piece in cell.split(","):
        name = piece.strip().strip("`")
        if name == "":
            continue
        if name.endswith(SUFFIX):
            name = name[0:len(name) - len(SUFFIX)]
        out.append(name)
    return out


def file_expect(path):
    """读用例头部的 `# expect: <kind>`；没有则返回空串"""
    f = open(path, encoding="utf-8")
    try:
        for line in f:
            s = line.strip()
            if not s.startswith("#"):
                return ""
            if s.startswith("# expect:"):
                kind = s[len("# expect:"):].strip().split(" ")[0]
                return kind.strip()
        return ""
    finally:
        f.close()


def main():
    errors = []
    warns = []

    if not os.path.isfile(SPEC):
        print("SPEC 缺失：%s" % SPEC)
        return 1
    f = open(SPEC, encoding="utf-8")
    lines = f.read().splitlines()
    f.close()

    entries = []        # [(编号, 用例列表)]
    expect_rows = []    # [(kind, [用例])]
    for line in lines:
        cols = cells(line)
        if cols is None or len(cols) < 3:
            continue
        first = cols[0].strip("`")
        if ID_RE.match(first):
            entries.append((first, split_cases(cols[2])))
        elif "expect:" in first:
            m = EXPECT_RE.search(first)
            if m is None:
                errors.append("R5 §2 表行缺 kind：%s" % line.strip())
                continue
            expect_rows.append((m.group(1), split_cases(cols[len(cols) - 1])))

    if not entries:
        errors.append("R1 没解析到任何 `| S-XXX | … |` 条目行（表格式被改坏了？）")

    # R2 编号唯一
    seen = {}
    for sid, _cases in entries:
        if sid in seen:
            errors.append("R2 编号重复：%s" % sid)
        seen[sid] = True

    # R3 用例存在 + R1 条目至少一个用例
    indexed = {}
    for sid, cases in entries:
        if not cases:
            errors.append("R1 条目没有用例（等于没判据）：%s" % sid)
        for name in cases:
            indexed[name] = sid
            path = os.path.join(CASES, name + SUFFIX)
            if not os.path.isfile(path):
                errors.append("R3 索引引用了不存在的用例：%s（%s）" % (name, sid))

    # R4 孤儿用例
    actual = []
    for name in sorted(os.listdir(CASES)):
        if name.endswith(SUFFIX):
            actual.append(name[0:len(name) - len(SUFFIX)])
    orphans = []
    for name in actual:
        if name not in indexed:
            orphans.append(name)
    for name in orphans:
        errors.append("R4 用例没被索引引用（会悄悄腐烂）：%s" % name)

    # R5 预期失败双向一致
    declared = {}
    for kind, cases in expect_rows:
        for name in cases:
            declared[name] = kind
            if name not in indexed:
                errors.append("R5 预期失败用例未进 §1 条目：%s" % name)
    for name in actual:
        real = file_expect(os.path.join(CASES, name + SUFFIX))
        if real == "" and name in declared:
            errors.append("R5 §2 登记了 %s 为 %s，但文件头没有 `# expect:`" % (name, declared[name]))
        elif real != "" and name not in declared:
            errors.append("R5 %s 文件头声明 `# expect: %s`，但 §2 没登记" % (name, real))
        elif real != "" and name in declared and real != declared[name]:
            errors.append("R5 %s 声明 %s，§2 登记 %s" % (name, real, declared[name]))

    if orphans:
        warns.append("孤儿用例 %d 个" % len(orphans))

    if errors:
        print("SPEC 索引不一致（%d 项）：" % len(errors))
        for e in errors:
            print("  - %s" % e)
        return 1
    print("SPEC 索引一致：%d 条语义 × %d 个用例（预期失败 %d）"
          % (len(entries), len(actual), len(declared)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
