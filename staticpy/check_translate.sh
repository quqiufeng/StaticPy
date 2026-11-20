#!/bin/bash
# check_translate.sh — 验收：自举翻译器（tokenize+parse+emit）vs 旧版 static_translate.py
#   严格：IR 逐字节一致（含 `;; file:line` 注释）
#   规范化：去注释 / 去行尾空白 / 压连续空白（当前里程碑判据）
#
# 无 main 的文件（纯函数库）自动按库模式（--lib）比对。
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
CACHE=${TMPDIR:-/tmp}/sp_emitcheck
mkdir -p "$CACHE"
cat staticpy/static_translate.static.py staticpy/parse_lib.static.py \
    staticpy/emit_lib.static.py staticpy/emit_dump.static.py > "$CACHE/emitdump.static.py"
norm() {
  sed -e 's/;;.*$//' -e 's/[[:space:]]\+/ /g' -e 's/^ //' -e 's/ $//' "$1" | grep -av '^[[:space:]]*$'
}
fail=0; total=0
for f in "$@"; do
  total=$((total+1))
  mode=""; marg=""
  if ! $PY staticpy/static_translate.py "$f" > "$CACHE/exp.ss" 2>"$CACHE/experr.txt"; then
    if grep -q "missing main" "$CACHE/experr.txt"; then
      mode="lib"; marg="lib"
      $PY staticpy/static_translate.py --lib "$f" > "$CACHE/exp.ss" 2>"$CACHE/experr.txt" \
        || { echo "  ERR  $f (python --lib)"; head -3 "$CACHE/experr.txt"; fail=1; continue; }
    else
      echo "  ERR  $f (python)"; head -3 "$CACHE/experr.txt"; fail=1; continue
    fi
  fi
  # 整份输出都比（含 `;; extern FFI functions` 段）：extern fn -> foreign-procedure
  $PY -m kernel run "$CACHE/emitdump.static.py" "$f" $marg 2>"$CACHE/err.txt" \
    | sed '/^=== built:/,$d' > "$CACHE/got.ss"
  grep -aq '^;; Source:' "$CACHE/got.ss" || { echo "  FAIL $f (自举翻译器未产出)"; tail -3 "$CACHE/err.txt"; fail=1; continue; }
  if diff -aq "$CACHE/exp.ss" "$CACHE/got.ss" >/dev/null; then
    echo "  ok(严格) $f"
  elif diff -aq <(norm "$CACHE/exp.ss") <(norm "$CACHE/got.ss") >/dev/null; then
    echo "  ok(规范化) $f"
  else
    echo "  DIFF $f"; diff -a <(norm "$CACHE/exp.ss") <(norm "$CACHE/got.ss") | head -8; fail=1
  fi
done
echo "---- $total files, fail=$fail"
exit $fail
