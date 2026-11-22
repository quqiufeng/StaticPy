#!/bin/bash
# check_parse.sh — 验收：自持解析器 vs CPython ast（规范 dump 逐字节比对）
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
CACHE=${TMPDIR:-/tmp}/sp_parsecheck
mkdir -p "$CACHE"
cat staticpy/static_translate.static.py staticpy/parse_lib.static.py staticpy/parse_dump.static.py > "$CACHE/parsedump.static.py"
fail=0; total=0; skipped=0
for f in "$@"; do
  if ! $PY -c "import ast,sys; ast.parse(open(sys.argv[1],encoding='utf-8').read())" "$f" 2>/dev/null; then
    continue
  fi
  # 显式声明「种子通道专属」的夹具：自持解析器还没有该语法（如 match），跳过并计入 SKIP 计数
  if head -3 "$f" | grep -q '^# parse: seed-only'; then
    echo "  SKIP $f (种子通道专属：自持解析器尚无该语法)"
    skipped=$((skipped + 1)); continue
  fi
  total=$((total+1))
  $PY staticpy/parse_diff.py "$f" > "$CACHE/exp.txt" 2>"$CACHE/experr.txt" || { echo "  ERR  $f (python)"; head -3 "$CACHE/experr.txt"; fail=1; continue; }
  $PY -m kernel run "$CACHE/parsedump.static.py" "$f" 2>"$CACHE/goterr.txt" | sed -n '/^Module(/p' > "$CACHE/got.txt"
  if diff -q "$CACHE/exp.txt" "$CACHE/got.txt" >/dev/null; then
    echo "  ok   $f"
  else
    echo "  DIFF $f"; diff <(fold -w 100 "$CACHE/exp.txt") <(fold -w 100 "$CACHE/got.txt") | head -8; fail=1
  fi
done
echo "---- $total files checked, fail=$fail, skip=$skipped"
exit $fail
