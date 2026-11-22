#!/bin/bash
# tools/bench.sh — StaticPy 常数因子基准（编译时间 / 产物体积 / 冷启动 / FFI 往返）
#
# 为什么要有它：本仓的优化判据一直是「A/B 实测中位」，但每次都是手搓命令、
# 手抄数字，换个会话就重来一遍，也没人发现「冷启动变慢了」「产物胖了」这类回归。
# 这里把六个阶段固定下来，输入**确定性生成**（tests/bench/gen_bench_input.py），
# 所以任何机器、任何时间跑出来的数都能直接比。
#
#   阶段            量什么                         判据
#   translate-seed  种子（CPython）翻译大输入       中位秒数
#   translate-boot  自举 ELF 翻译同一输入           中位秒数（与上式比值 = 自举收益）
#   build-aot       完整 AOT（翻译+Chez 编译+链接）  中位秒数
#   size            产物 ELF + .so                 字节
#   cold-start      起进程 + 跑完                    中位毫秒
#   ffi             foreign-procedure 往返          纳秒/次
#
# 用法：
#   bash tools/bench.sh                 # 全量（约 1–2 分钟）
#   bash tools/bench.sh --quick         # 单次取数，不取中位（约 20 秒）
#   bash tools/bench.sh --json out.json # 另存 JSON（可作下次 --baseline）
#   bash tools/bench.sh --baseline old.json   # 与旧结果逐项比对（>5% 标红）
#
# 环境：STATICPY_CACHE/STATICPY_OUTDIR 同构建脚本；工作目录默认 ~/iso_gen/bench（禁 /tmp）
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

QUICK=0
JSON_OUT=""
BASELINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1 ;;
    --json) JSON_OUT="$2"; shift ;;
    --baseline) BASELINE="$2"; shift ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) echo "未知参数 $1"; exit 2 ;;
  esac
  shift
done

W="${STATICPY_BENCH_WORK:-$HOME/iso_gen/bench}"
mkdir -p "$W"
export STATICPY_CACHE="${STATICPY_CACHE:-$HOME/iso_gen/staticpy-cache}"
export STATICPY_OUTDIR="${STATICPY_OUTDIR:-$W/out}"
mkdir -p "$STATICPY_OUTDIR"

# ---- 计时工具：date +%s%N（纳秒），取中位 ----------------------------------
now_ns() { date +%s%N; }

# time_ms <重复次数> <命令...> → 打印中位毫秒数
time_ms() {
  local reps="$1"; shift
  local -a vals=()
  local i a b
  for ((i = 0; i < reps; i++)); do
    a=$(now_ns)
    "$@" >/dev/null 2>&1
    b=$(now_ns)
    vals+=($(( (b - a) / 1000000 )))
  done
  printf '%s\n' "${vals[@]}" | sort -n | awk '{v[NR]=$1} END {print v[int((NR+1)/2)]}'
}

# ---- 输入：确定性生成 ------------------------------------------------------
BIG="$W/bench_big.static.py"
MID="$W/bench_mid.static.py"
SMALL="$W/bench_small.static.py"
[ -f "$BIG" ] || python3 tests/bench/gen_bench_input.py "$BIG" 2200 >/dev/null
[ -f "$MID" ] || python3 tests/bench/gen_bench_input.py "$MID" 200 >/dev/null
if [ ! -f "$SMALL" ]; then
  cat > "$SMALL" <<'EOF'
# 冷启动样本：只做一点点工作，主要量「起进程 + 加载运行时 + 退出」
def main():
    total: int = 0
    i: int = 0
    while i < 1000:
        total = total + i
        i = i + 1
    print(total)
EOF
fi

REPS=3; [ "$QUICK" = 1 ] && REPS=1

echo ">>> StaticPy 基准（$(uname -srm)，$(nproc) 核，REPS=$REPS）"
echo "    输入：big=$(wc -c <"$BIG")B mid=$(wc -c <"$MID")B"

# ---- 1 种子翻译 -----------------------------------------------------------
SEED_MS=$(time_ms "$REPS" python3 staticpy/static_translate.py "$BIG")
echo "  translate-seed  ${SEED_MS} ms   （CPython 种子，$(wc -c <"$BIG")B 输入）"

# ---- 2 自举翻译（需要 dist/translator） ------------------------------------
BOOT_MS=0
if [ -x dist/translator ]; then
  BOOT_MS=$(cd dist && time_ms "$REPS" ./translator "$BIG")
  echo "  translate-boot  ${BOOT_MS} ms   （自举 ELF）"
  if [ "$SEED_MS" -gt 0 ] && [ "$BOOT_MS" -gt 0 ]; then
    awk -v a="$SEED_MS" -v b="$BOOT_MS" \
      'BEGIN{printf "                  自举/种子 = %.2f×（%.1f%% 时间）\n", b/a, b/a*100}'
  fi
else
  echo "  translate-boot  跳过（缺 dist/translator）"
fi

# ---- 3 完整 AOT 构建（每个回次先清掉该目标的缓存条目，否则量到的是"缓存命中"）---
BUILD_CMD="rm -f '$STATICPY_CACHE/bench_mid_'* ; env STATICPY_CACHE='$STATICPY_CACHE' \
STATICPY_OUTDIR='$STATICPY_OUTDIR' bash staticpy/static_build.sh '$MID' bench_mid"
BUILD_MS=$(time_ms "$REPS" bash -c "$BUILD_CMD")
echo "  build-aot       ${BUILD_MS} ms   （mid 输入，冷缓存：翻译 + Chez 编译 + 链接）"

# ---- 4 产物体积 -----------------------------------------------------------
if [ -f "$STATICPY_OUTDIR/bench_mid" ]; then
  ELF_B=$(wc -c <"$STATICPY_OUTDIR/bench_mid")
  SO_B=$(wc -c <"$STATICPY_OUTDIR/bench_mid.so" 2>/dev/null || echo 0)
  echo "  size            ELF $((ELF_B / 1024)) KB + .so $((SO_B / 1024)) KB" \
       "= $(( (ELF_B + SO_B) / 1024 )) KB"
else
  ELF_B=0; SO_B=0
  echo "  size            跳过（构建失败）"
fi

# ---- 5 冷启动 -------------------------------------------------------------
[ -f "$STATICPY_OUTDIR/bench_small" ] || env STATICPY_CACHE="$STATICPY_CACHE" \
  STATICPY_OUTDIR="$STATICPY_OUTDIR" bash staticpy/static_build.sh "$SMALL" bench_small >/dev/null 2>&1
COLD_MS=0
if [ -x "$STATICPY_OUTDIR/bench_small" ]; then
  COLD_MS=$(time_ms $((REPS * 3)) "$STATICPY_OUTDIR/bench_small")
  echo "  cold-start      ${COLD_MS} ms   （中位，$((REPS * 3)) 次）"
fi

# ---- 6 FFI 往返 -----------------------------------------------------------
FFI_NS=0
FFI_N=2000000
env STATICPY_CACHE="$STATICPY_CACHE" STATICPY_OUTDIR="$STATICPY_OUTDIR" \
  bash staticpy/static_build.sh tests/bench/ffi_roundtrip.static.py bench_ffi >/dev/null 2>&1
if [ -x "$STATICPY_OUTDIR/bench_ffi" ]; then
  FFI_MS=$(time_ms $((REPS * 3)) "$STATICPY_OUTDIR/bench_ffi")
  FFI_NS=$(( FFI_MS * 1000000 / FFI_N ))
  echo "  ffi             ${FFI_NS} ns/次   （${FFI_N} 次 foreign-procedure 往返）"
fi

# ---- JSON 输出 ------------------------------------------------------------
JSON=$(printf '{"seed_ms":%s,"boot_ms":%s,"build_ms":%s,"elf_bytes":%s,"so_bytes":%s,"cold_ms":%s,"ffi_ns":%s}' \
  "$SEED_MS" "$BOOT_MS" "$BUILD_MS" "$ELF_B" "$SO_B" "$COLD_MS" "$FFI_NS")
[ -n "$JSON_OUT" ] && printf '%s\n' "$JSON" > "$JSON_OUT"

# ---- 与基线比对 -----------------------------------------------------------
if [ -n "$BASELINE" ] && [ -f "$BASELINE" ]; then
  echo ">>> 对比基线 $BASELINE（|Δ|>5% 标红；变小为好）"
  python3 - "$BASELINE" "$JSON" <<'PY'
import json, sys
base = json.load(open(sys.argv[1]))
cur = json.loads(sys.argv[2])
names = [("seed_ms", "translate-seed", "ms"), ("boot_ms", "translate-boot", "ms"),
         ("build_ms", "build-aot", "ms"), ("elf_bytes", "elf", "B"),
         ("so_bytes", "so", "B"), ("cold_ms", "cold-start", "ms"),
         ("ffi_ns", "ffi", "ns")]
for k, label, unit in names:
    b, c = base.get(k, 0), cur.get(k, 0)
    if not b or not c:
        continue
    d = (c - b) / b * 100
    mark = "  " if abs(d) < 5 else ("✗ " if d > 5 else "✓ ")
    print(f"  {mark}{label:<15} {b:>10} → {c:>10} {unit}  ({d:+.1f}%)")
PY
fi

echo ">>> 判读：单次 ±5% 内属噪声；要下结论请用 REPS≥3 的中位，并交替 A/B（同机同时段）"
