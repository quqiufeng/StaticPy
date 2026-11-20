#!/bin/bash
# backend_drill.sh — 后端替换演练：把「可替换」从主张变成可复现的失败
#
# 问题：POLICY §4 说后端（Chez+gcc）不审、降级为「可替换」。凭什么？
#       只有一种回答算数：换一个坏后端，看谁会喊。
#
# 做法：CHEZ_SCHEME 指向 wrapper，在真 Chez 编译前篡改 IR 两个字面量
#       （"True"→"TruE"、"None"→"NonE"）。产物照常构建、照常运行，行为错了。
#       然后分别跑 E3 / E5 / E4，看红绿。
#
# 实测结论（2026-11-20）：
#   E5 固定点   绿（哈希与基线一字不差）—— 结构上看不见均匀下毒
#   E3 IR 差分  红/绿取决于缓存：缓存里已有干净 boot → 绿；让下毒后端去建 boot → 红
#               （E3 比的是两份 Python 翻译器，本与后端无关——这红是「漏进来」的）
#   E4 语义差分 红 —— 唯一硬报警，因为 oracle 是 CPython，不经过后端
#
# 用法: bash trust/backend_drill.sh [--keep]
#   全部临时物在 ~/iso_gen/drill（本仓禁止 /tmp）
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
WORK="${WORK:-$HOME/iso_gen/drill}"
BUILD="bash staticpy/static_build_comfycli.sh"
REAL_SCHEME="${CHEZ_SCHEME:-/opt/ChezScheme/ta6le/bin/ta6le/scheme}"
mkdir -p "$WORK/bin" "$WORK/cache"

say() { echo ">>> $*"; }

if [ ! -x "$REAL_SCHEME" ]; then
  echo "!! 找不到 Chez: $REAL_SCHEME（用 CHEZ_SCHEME 指定）"; exit 2
fi

# ---------- 0) 被测程序 ----------
cat > "$WORK/probe.static.py" <<'EOF'
def main():
    print(True)
    print(None)
    print(1 + 2)
EOF

# ---------- 1) 下毒后端（只改 IR 字面量，不改 Chez 本体）----------
cat > "$WORK/bin/scheme-poison" <<EOF
#!/bin/bash
# 下毒后端：真 Chez 不变，编译前篡改 IR —— "错得稳定"，正是自洽性检验的盲区
for f in "\${STATICPY_CACHE:-\$HOME/iso_gen/staticpy-cache}"/*.ss; do
  [ -f "\$f" ] && sed -i 's/"True"/"TruE"/g; s/"None"/"NonE"/g' "\$f"
done
exec "$REAL_SCHEME" "\$@"
EOF
chmod +x "$WORK/bin/scheme-poison"

# ---------- 2) 基线 vs 下毒 ----------
say "基线构建 + 运行"
$BUILD "$WORK/probe.static.py" drill_base >"$WORK/base.log" 2>&1
BASE_OUT="$(./dist/drill_base 2>&1 | head -3)"

say "下毒后端构建 + 运行"
CHEZ_SCHEME="$WORK/bin/scheme-poison" STATICPY_CACHE="$WORK/cache" \
  $BUILD "$WORK/probe.static.py" drill_poison >"$WORK/poison.log" 2>&1
POISON_OUT="$(./dist/drill_poison 2>&1 | head -3)"

echo "  基线:   $(echo "$BASE_OUT" | tr '\n' ' ')"
echo "  下毒后: $(echo "$POISON_OUT" | tr '\n' ' ')"
if [ "$BASE_OUT" = "$POISON_OUT" ]; then
  echo "!! 下毒没生效——演练无效（检查 sed 目标或缓存目录）"; exit 2
fi
echo "  → 产物照常运行，但行为已经错了。现在看谁喊。"

# ---------- 3) 三判据 ----------
echo
say "E5 固定点（下毒后端下）"
CHEZ_SCHEME="$WORK/bin/scheme-poison" STATICPY_CACHE="$WORK/fp_cache" \
  bash trust/fixpoint.sh >"$WORK/e5.log" 2>&1
E5_RC=$?
E5_HASH="$(grep -oE 'g[123] [0-9]+ B  [0-9a-f]+' "$WORK/e5.log" | tr '\n' '|')"
[ $E5_RC -eq 0 ] && E5_VERDICT="绿（无感）" || E5_VERDICT="红"
echo "  $E5_VERDICT   $E5_HASH"

echo
say "E3 IR 差分（下毒后端下；注意它本该看不见后端）"
CHEZ_SCHEME="$WORK/bin/scheme-poison" STATICPY_CACHE="$WORK/e3_cache_$$" \
  bash staticpy/check_translate.sh "$WORK/probe.static.py" >"$WORK/e3.log" 2>&1
E3_RC=$?
[ $E3_RC -eq 0 ] && E3_VERDICT="绿（看不见后端）" || E3_VERDICT="红"
echo "  $E3_VERDICT   $(tail -1 "$WORK/e3.log")"

echo
say "E4 语义差分（CPython vs 下毒 ELF）"
$PY "$WORK/probe.static.py" >"$WORK/e4_py.txt" 2>&1
./dist/drill_poison 2>&1 | head -3 >"$WORK/e4_elf.txt"
if diff -q "$WORK/e4_py.txt" "$WORK/e4_elf.txt" >/dev/null; then
  E4_VERDICT="绿（没抓住——危险）"
else
  E4_VERDICT="红（抓住）"
fi
echo "  $E4_VERDICT"

# ---------- 4) 判定 ----------
echo
echo "=== 演练结论 ==="
echo "  E3: $E3_VERDICT"
echo "  E5: $E5_VERDICT"
echo "  E4: $E4_VERDICT"
echo
echo "  含义：均匀下毒对 E5 是合法输入（稳定的错=自洽）；E3 根本不经过后端。"
echo "  后端可替换性的真实边界 = 存在一个**不经过后端**的 oracle（CPython/Pillow/zlib）。"
echo "  所以 E4/E7 不是补充判据，而是可替换性的唯一支撑。"

if [ "${1:-}" != "--keep" ]; then
  rm -f "$ROOT/dist/drill_base" "$ROOT/dist/drill_base.so" "$ROOT/dist/drill_base.build-info.json" \
        "$ROOT/dist/drill_poison" "$ROOT/dist/drill_poison.so" "$ROOT/dist/drill_poison.build-info.json"
  echo "  （产物已清理；--keep 保留）"
fi
