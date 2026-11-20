#!/bin/bash
# run_sp_tests.sh — .sp 环差分测试（编译 + 运行 + 比对 stdout/stderr）
#
# 用法:
#   bash selfhost/tests/run_sp_tests.sh              # 全跑
#   bash selfhost/tests/run_sp_tests.sh arith logic  # 只跑名字匹配的用例
#   STATICC=~/iso_gen/spboot/spboot_self bash ...    # 指定被测编译器
#
# 用例约定（selfhost/tests/sp/）：
#   NAME.sp       输入
#   NAME.expected 期望 stdout（缺省 = 期望空）
#   NAME.err      期望**编译失败**：文件内容需出现在编译器 stderr 中，且退出码非 0
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$(dirname "$HERE")")"
STATICC="${STATICC:-$HOME/iso_gen/spboot/spboot_self}"
SCHEME="${CHEZ_SCHEME:-/opt/ChezScheme/ta6le/bin/ta6le/scheme}"
PRELUDE="$ROOT/staticpy/static_prelude.scm"
STDLIB="${STATICPY_STDLIB:-$ROOT/staticpy/static_stdlib.scm}"
WORK="${SPTEST_WORK:-$HOME/iso_gen/sptest}"
mkdir -p "$WORK"

[ -x "$STATICC" ] || { echo "缺少编译器: $STATICC"; exit 2; }
[ -x "$SCHEME" ] || { echo "缺少 Chez: $SCHEME"; exit 2; }

pass=0; fail=0; failed=()

match() {
  [ $# -eq 0 ] && return 0
  for pat in "$@"; do [[ "$(basename "$1" .sp)" == *"$pat"* ]] && return 0; done
  return 1
}

for sp in "$HERE"/sp/*.sp; do
  name="$(basename "$sp" .sp)"
  if [ $# -gt 0 ]; then
    hit=0
    for pat in "$@"; do [[ "$name" == *"$pat"* ]] && hit=1; done
    [ $hit -eq 1 ] || continue
  fi
  scm="$WORK/$name.scm"
  out="$WORK/$name.out"
  err="$WORK/$name.err"

  "$STATICC" "$sp" "$scm" >"$out.err" 2>&1
  rc=$?

  if [ -f "$HERE/sp/$name.err" ]; then
    # 负例：必须编译失败，且 stderr 含指定片段
    want="$(cat "$HERE/sp/$name.err")"
    if [ $rc -ne 0 ] && grep -qF "$want" "$out.err"; then
      pass=$((pass+1)); printf '  ok   %s (expected compile error)\n' "$name"
    else
      fail=$((fail+1)); failed+=("$name")
      printf '  FAIL %s  rc=%s 期望失败且含「%s」，实际:\n' "$name" "$rc" "$want"
      sed 's/^/        /' "$out.err" | head -5
    fi
    continue
  fi

  if [ $rc -ne 0 ]; then
    fail=$((fail+1)); failed+=("$name")
    printf '  FAIL %s  编译失败 rc=%s:\n' "$name" "$rc"
    sed 's/^/        /' "$out.err" | head -8
    continue
  fi

  cat "$PRELUDE" "$STDLIB" "$scm" > "$WORK/$name.merged.scm" 2>/dev/null
  "$SCHEME" --quiet --script "$WORK/$name.merged.scm" >"$out" 2>"$err"
  rc=$?
  if [ $rc -ne 0 ]; then
    fail=$((fail+1)); failed+=("$name")
    printf '  FAIL %s  运行失败 rc=%s:\n' "$name" "$rc"
    sed 's/^/        /' "$err" | head -8
    continue
  fi

  expected=""
  [ -f "$HERE/sp/$name.expected" ] && expected="$(cat "$HERE/sp/$name.expected")"
  if [ "$(cat "$out")" = "${expected%$'\n'}" ]; then
    pass=$((pass+1)); printf '  ok   %s\n' "$name"
  else
    fail=$((fail+1)); failed+=("$name")
    printf '  FAIL %s  stdout 不符\n' "$name"
    diff <(printf '%s\n' "$expected") "$out" | head -10 | sed 's/^/        /'
  fi
done

echo
echo "==== .sp 差分测试: $pass 通过, $fail 失败 ===="
if [ $fail -gt 0 ]; then printf '  失败: %s\n' "${failed[*]}"; exit 1; fi
