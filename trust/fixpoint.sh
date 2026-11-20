#!/bin/bash
# fixpoint.sh — 环 3 的三阶段固定点验证（信任根：selfhost/staticc.sp）
#
# 只做一件事：让编译器**编译自己**，看第 2 代与第 3 代产物是否完全相同。
#
#   stage0  seed(static_translate.py) 编 staticc.py  → E0 ELF
#   stage1  E0    编 staticc.sp       → g1.scm
#   stage2  用 g1.scm 建出 E1；E1 编 staticc.sp → g2.scm
#   stage3  用 g2.scm 建出 E2；E2 编 staticc.sp → g3.scm
#   判定    g2 ≡ g3（token 级）→ 到达固定点：从第 2 代起，编译器对自身的输出不再变化
#
# 为什么是 g2 vs g3 而不是 g1 vs g2：g1 是「种子翻译器」的产物，与自举编译器风格不同，
# 二者本就不同（本脚本会把差异如实报出来）。固定点的意义在于**自举链收敛后不再漂移**。
#
# 重要局限（务必别把这条当"已证"）：固定点只证明「编译器能稳定复制自己」，
# 不证明它把源码翻成 IR 是对的 —— 自洽的后门同样能通过固定点。
# 正确性靠 trust/ddc.sh（异源双编译）+ semantics_diff.py（对外部 oracle）。
#
# 用法: bash trust/fixpoint.sh [--keep]
#   WORK 默认 ~/iso_gen/trust/fixpoint（本仓禁止 /tmp）
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
WORK="${WORK:-$HOME/iso_gen/trust/fixpoint}"
NORM="$PY trust/normalize_scm.py"
BUILD="bash staticpy/static_build_comfycli.sh"
mkdir -p "$WORK"

say() { echo ">>> $*"; }
die() { echo "!! $*"; exit 1; }

# ---------- stage0：种子编出 E0 ----------
say "stage0  种子 → E0（staticc.py）"
$BUILD selfhost/staticc.py staticc_e0 >"$WORK/build_e0.log" 2>&1 || die "构建 E0 失败（$WORK/build_e0.log）"
E0="$ROOT/dist/staticc_e0"
[ -x "$E0" ] || die "没找到 $E0"

# ---------- stage1 ----------
say "stage1  E0 编 staticc.sp → g1.scm"
"$E0" selfhost/staticc.sp "$WORK/g1.scm" >"$WORK/g1.log" 2>&1 || die "g1 失败（$WORK/g1.log）"

# ---------- stage2 ----------
say "stage2  g1.scm → E1；E1 编 staticc.sp → g2.scm"
$BUILD "$WORK/g1.scm" staticc_e1 >"$WORK/build_e1.log" 2>&1 || die "构建 E1 失败（$WORK/build_e1.log）"
E1="$ROOT/dist/staticc_e1"
[ -x "$E1" ] || die "没找到 $E1"
"$E1" selfhost/staticc.sp "$WORK/g2.scm" >"$WORK/g2.log" 2>&1 || die "g2 失败（$WORK/g2.log）"

# ---------- stage3 ----------
say "stage3  g2.scm → E2；E2 编 staticc.sp → g3.scm"
$BUILD "$WORK/g2.scm" staticc_e2 >"$WORK/build_e2.log" 2>&1 || die "构建 E2 失败（$WORK/build_e2.log）"
E2="$ROOT/dist/staticc_e2"
[ -x "$E2" ] || die "没找到 $E2"
"$E2" selfhost/staticc.sp "$WORK/g3.scm" >"$WORK/g3.log" 2>&1 || die "g3 失败（$WORK/g3.log）"

# ---------- 判定 ----------
echo
h() { sha256sum "$1" | cut -c1-16; }
echo "g1 $(wc -c <"$WORK/g1.scm") B  $(h "$WORK/g1.scm")   （种子产物，与自举链风格不同，允许不同）"
echo "g2 $(wc -c <"$WORK/g2.scm") B  $(h "$WORK/g2.scm")"
echo "g3 $(wc -c <"$WORK/g3.scm") B  $(h "$WORK/g3.scm")"
echo

if $NORM --eq "$WORK/g2.scm" "$WORK/g3.scm" 2>"$WORK/fix.diff"; then
  echo "=== 固定点成立：g2 ≡ g3（token 级一致）==="
  echo "    编译器从第 2 代起对自身输出稳定；复制过程不再引入新变化。"
else
  echo "=== 固定点不成立：g2 ≠ g3 ==="
  cat "$WORK/fix.diff"
  echo "    可能原因：非确定性（dict/哈希顺序、时间戳、绝对路径）或 stage 间真实漂移。"
  echo "    排查：diff <(tr ' ' '\n' <g2.scm) <(tr ' ' '\n' <g3.scm) | head"
  exit 1
fi

# 交叉记录：种子产物 vs 自举产物（不是判据，但能看出种子与自举链的偏差幅度）
if $NORM --eq "$WORK/g1.scm" "$WORK/g2.scm" 2>/dev/null; then
  echo "    （附带：g1 ≡ g2，种子与自举链完全一致——这条更强，说明链上无风格漂移）"
else
  echo "    （附带：g1 ≠ g2，属正常——种子与自举编译器是两套实现；差异幅度："
  echo "      $(diff <(tr ' ' '\n' <"$WORK/g1.scm") <(tr ' ' '\n' <"$WORK/g2.scm") | grep -c '^[<>]') token）"
fi

[ "${1:-}" = "--keep" ] || echo "产物保留在 $WORK（要清理手动 rm）"
