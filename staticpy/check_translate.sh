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
# 对照口径：自举环 2 不带插件（plugins/ 只在种子链路上生效），所以种子侧也跑 core 链，
# 比较的是"翻译器本身"的 IR；插件改写属于前端约定，不参与此项验收。
SEED_PLUGINS="${SEED_PLUGINS:-core}"
norm() {
  sed -e 's/;;.*$//' -e 's/[[:space:]]\+/ /g' -e 's/^ //' -e 's/ $//' "$1" | grep -av '^[[:space:]]*$'
}
fail=0; total=0
for f in "$@"; do
  total=$((total+1))
  mode=""; marg=""
  # 用例自带 `# expect: build-error`：测的是「不支持的东西必须响」，不比对 IR
  if grep -q '^# expect: build-error' "$f"; then
    if $PY staticpy/static_translate.py --plugins "$SEED_PLUGINS" "$f" >/dev/null 2>"$CACHE/experr.txt"; then
      echo "  LOUD $f (期望构建期失败，但构建成功了)"; fail=1
    else
      echo "  ok(响亮失败) $f"
    fi
    continue
  fi
  if ! $PY staticpy/static_translate.py --plugins "$SEED_PLUGINS" "$f" > "$CACHE/exp.ss" 2>"$CACHE/experr.txt"; then
    if grep -q "missing main" "$CACHE/experr.txt"; then
      mode="lib"; marg="lib"
      $PY staticpy/static_translate.py --plugins "$SEED_PLUGINS" --lib "$f" > "$CACHE/exp.ss" 2>"$CACHE/experr.txt" \
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
