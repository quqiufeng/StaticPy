#!/bin/bash
# ddc.sh — 环 3 的 **多样性双编译（DDC: Diverse Double-Compiling）** 交叉验证。
#
# 要解决的问题：固定点（fixpoint）只证明「编译器能复制自己」，它**不能**证明编译器正确
# ——一个自洽的后门也能完美通过 `sc1 ≡ sc2`（Thompson, "Reflections on Trusting Trust"）。
# 唯一能把它逼出来的办法：用一份**独立实现**编译同一个源，看两份产物是否一致。
#
# 本仓正好有两份实现，但过去只做过「同源不同执行方式」的自比（selfcheck [4/4]），
# 没做过「异源」互比：
#
#   C1 = selfhost/staticc.py   —— 用 **Python 子集语法**写的编译器（CPython 当解释器）
#   C2 = selfhost/staticc.sp   —— 用 **S-表达式语法**写的编译器（由 .sp 工具链编译成 ELF）
#
# 两者对同一 `.sp` 源必须产出 token 级相同的 Scheme IR。任何只藏在其中一份里、
# 且只在「编译自己」时激活的后门，都会让两侧 IR 分叉 → 本脚本抓到。
#
# 用法:
#   bash trust/ddc.sh                 # 全语料
#   bash trust/ddc.sh selfhost/staticc.sp        # 指定文件
#   SPSTATICC=/path/to/spboot_self bash trust/ddc.sh
#
# 环境:
#   PYTHON     默认 python3
#   SPSTATICC  .sp 编译器；**默认不再用预置二进制**，而是从源码现建（见下）
#              显式指定 = 用外部二进制，脚本会做陈旧度检查并大声警告
#   WORK       中间产物目录，默认 ~/iso_gen/trust/ddc（本仓禁止 /tmp）
#
# 为什么默认改为「从源码现建 C2」：
#   DDC 的结论只在「C2 确实由当前 staticc.sp 编出来」时才成立。过去这里默认吃
#   ~/iso_gen/spboot/spboot_self 这个**预置二进制**，一旦 staticc.sp 改过而二进制没重建，
#   比的就是「新 C1 vs 旧 C2」——差异会被误判成 "C2 能力未覆盖"，而真正的分叉可能被
#   陈旧二进制掩盖/伪造。2026-11-20 实测：陈旧二进制报 7 项能力差，源码现建后 gap=0。
#   所以 C2 的**来路**必须与 staticc.sp 的 hash 绑定，不绑定就不认。
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
WORK="${WORK:-$HOME/iso_gen/trust/ddc}"
NORM="$PY trust/normalize_scm.py"
BUILD="bash staticpy/static_build_comfycli.sh"
mkdir -p "$WORK"

# ---------- C2 解析：源码现建（默认）或外部二进制（显式） ----------
TRUSTROOT="selfhost/staticc.sp"
SEEDSRC="selfhost/staticc.py"
src_hash() { sha256sum "$TRUSTROOT" "$SEEDSRC" | sha256sum | cut -c1-16; }

build_c2_from_source() {
  # 可审计路径：种子(static_translate.py) 编 staticc.py → E0；E0 编 staticc.sp → c2.scm；c2.scm → ELF
  # 注意：ELF 与它的 .so 是一对，必须留在 dist/ 里（挪走就找不到同名 .so 了）
  local stamp="$WORK/c2.stamp" bin="$ROOT/dist/staticc_c2built" h
  h="$(src_hash)"
  if [ -x "$bin" ] && [ -f "$stamp" ] && [ "$(cat "$stamp")" = "$h" ]; then
    echo "$bin"; return 0
  fi
  echo ">>> C2 来路校验：staticc.sp/staticc.py 的 hash 与已建 C2 不符（或首次），从源码现建" >&2
  $BUILD "$SEEDSRC" staticc_c2seed >"$WORK/c2_build_e0.log" 2>&1 || { echo "!! 构建 E0 失败（$WORK/c2_build_e0.log）" >&2; return 1; }
  local e0="$ROOT/dist/staticc_c2seed"
  "$e0" "$TRUSTROOT" "$WORK/c2.scm" >"$WORK/c2_gen.log" 2>&1 || { echo "!! E0 编 staticc.sp 失败（$WORK/c2_gen.log）" >&2; return 1; }
  $BUILD "$WORK/c2.scm" staticc_c2built >"$WORK/c2_build.log" 2>&1 || { echo "!! 构建 C2 失败（$WORK/c2_build.log）" >&2; return 1; }
  echo "$h" >"$stamp"
  echo ">>> C2 已建：$bin  ← $TRUSTROOT@${h}（哈希绑定，源一动即重建）" >&2
  echo "$bin"
}

if [ -n "${SPSTATICC:-}" ]; then
  [ -x "$SPSTATICC" ] || { echo "缺少 .sp 编译器: $SPSTATICC"; exit 2; }
  # 陈旧度闸门：外部二进制早于信任根 = 比的不是同一份源码，结论不可信
  if [ "$SPSTATICC" -ot "$TRUSTROOT" ]; then
    echo "!! 警告：SPSTATICC 早于 $TRUSTROOT 的修改时间——这是在拿「新 C1 vs 旧 C2」做 DDC。"
    echo "   由此产生的「能力未覆盖/分叉」都可能是二进制陈旧造成的假象，不能作为结论。"
    echo "   建议去掉 SPSTATICC 让脚本从源码现建 C2。"
  fi
  echo ">>> C2 = $SPSTATICC（外部指定，未与源码 hash 绑定）"
else
  SPSTATICC="$(build_c2_from_source)" || { echo "C2 构建失败，无法进行 DDC"; exit 2; }
fi

# ---------- 语料 ----------
if [ $# -gt 0 ]; then
  CORPUS=("$@")
else
  CORPUS=()
  for f in selfhost/tests/sp/*.sp; do [ -e "$f" ] && CORPUS+=("$f"); done
  for f in selfhost/tests/test_staticc_input.sp selfhost/examples/*.sp; do [ -e "$f" ] && CORPUS+=("$f"); done
  # 信任根本身必须在内：自编译场景正是后门唯一会露头的场景
  for f in selfhost/staticc.sp selfhost/staticc_split.sp; do [ -e "$f" ] && CORPUS+=("$f"); done
fi

sem=0; fail=0; err=0; gap=0
failed_list=(); gap_list=()

for src in "${CORPUS[@]}"; do
  id="$(echo "$src" | sed 's#[^A-Za-z0-9]#_#g')"
  a="$WORK/$id.c1.scm"; b="$WORK/$id.c2.scm"
  ( cd selfhost && timeout 900 "$PY" run_staticc_py.py "../$src" "$a" ) >"$WORK/$id.c1.log" 2>&1
  rc1=$?
  timeout 900 "$SPSTATICC" "$src" "$b" >"$WORK/$id.c2.log" 2>&1
  rc2=$?

  # 负向用例（*_err_*）：两边都必须拒绝。一边接受一边拒绝，本身就是语义分叉。
  case "$src" in
    *_err_*)
      if [ "$rc1" -ne 0 ] && [ "$rc2" -ne 0 ]; then
        echo "  ok $src  （两侧都正确拒绝）"; err=$((err+1))
      elif [ "$rc1" -eq 0 ] && [ "$rc2" -eq 0 ]; then
        echo "  !! $src  两侧都**没**报错（该拒绝却接受）"
        fail=$((fail+1)); failed_list+=("$src")
      else
        echo "  !! $src  报错行为分叉：C1 rc=$rc1 / C2 rc=$rc2"
        fail=$((fail+1)); failed_list+=("$src")
      fi
      continue ;;
  esac

  if [ "$rc1" -ne 0 ]; then
    echo "  !! $src  C1(staticc.py) 编译失败（见 $WORK/$id.c1.log）"
    fail=$((fail+1)); failed_list+=("$src"); continue
  fi
  if [ "$rc2" -ne 0 ]; then
    # C1 能编、C2 编不了 = 两份实现的**能力差**，不是分叉：C2 尚未覆盖该语法。
    # 不计入失败，但必须列出来 —— 能力差之外的部分才是 DDC 真正覆盖到的范围。
    echo "  -- $src  C2 能力未覆盖：$(tail -1 "$WORK/$id.c2.log" | sed 's/^staticc: error: //')"
    gap=$((gap+1)); gap_list+=("$src"); continue
  fi

  if $NORM --eq "$a" "$b" 2>"$WORK/$id.diff"; then
    echo "  ok $src"
    sem=$((sem+1))
  else
    echo "  !! $src  IR 分叉（$(cat "$WORK/$id.diff")）"
    fail=$((fail+1)); failed_list+=("$src")
  fi
done

echo "──────────────────────────────────────────────"
echo "DDC: IR 一致 $sem / 负向拒绝 $err / 分叉 $fail / C2 能力未覆盖 $gap"
if [ "$gap" -gt 0 ]; then
  echo
  echo "C2(.sp 实现) 尚未覆盖的语法（这部分 DDC 覆盖不到，属能力差，非分叉）："
  printf '  %s\n' "${gap_list[@]}"
  echo
  echo "先别急着当'能力差'：若 C2 是外部指定且早于 $TRUSTROOT，"
  echo "这些多半只是**二进制陈旧**的假象——去掉 SPSTATICC 重跑即可分辨。"
fi
if [ "$fail" -ne 0 ]; then
  echo
  echo "分叉文件："
  printf '  %s\n' "${failed_list[@]}"
  echo
  echo "含义：两份独立实现在这些源上给出不同结果。可能是"
  echo "  (1) 一份有 bug / 落后于另一份  -> 修实现"
  echo "  (2) 存在只在特定输入下激活的差异（正是 DDC 要找的东西）-> 逐 token 定位"
  echo "定位：$NORM --eq $WORK/<id>.c1.scm $WORK/<id>.c2.scm   # 报首个差异 token"
  exit 1
fi
if [ "$gap" -gt 0 ]; then
  echo "=== DDC **部分**通过：已比过的全一致，但有 $gap 份语料 C2 处理不了（覆盖不到，不能算通过） ==="
  exit 3
fi
echo "=== DDC 通过：两份独立实现对所有语料（含信任根本身），产出 token 级相同 IR ==="
