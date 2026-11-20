#!/bin/bash
# check_tokenize.sh — 验收：static_translate.static.py 的词法器 vs CPython tokenize
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
CACHE=${TMPDIR:-/tmp}/sp_tokcheck
mkdir -p "$CACHE"
cat staticpy/static_translate.static.py staticpy/tokenize_dump.static.py > "$CACHE/tokdump.static.py"
fail=0
for f in "$@"; do
  $PY staticpy/tokenize_diff.py "$f" > "$CACHE/exp.txt" 2>/dev/null
  $PY -m kernel run "$CACHE/tokdump.static.py" "$f" 2>/dev/null | grep -P "^[A-Z]+\\t" > "$CACHE/got.txt"
  if diff -q "$CACHE/exp.txt" "$CACHE/got.txt" >/dev/null; then
    echo "  ok  $f（$(wc -l < "$CACHE/exp.txt") tokens）"
  else
    echo "  DIFF $f"; diff "$CACHE/exp.txt" "$CACHE/got.txt" | head -5; fail=1
  fi
done
exit $fail
