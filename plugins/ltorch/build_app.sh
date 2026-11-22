#!/bin/bash
# build_app.sh USER.static.py OUT — 把用户程序与 tensor_lib（Tensor 类 + nn/optim）拼成独立 ELF
#   bash plugins/ltorch/build_app.sh plugins/ltorch/lib_demo.static.py demo
# 前置：bash cpp/torch/build.sh（出 cpp/torch/build/libtorch_capi.so）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
USER="$1"; OUT="$2"
CONCAT="$ROOT/dist/concat"
if [ ! -x "$CONCAT" ]; then
  ( cd "$ROOT" && bash staticpy/static_build.sh imgproc/concat.static.py concat >/dev/null )
fi
CACHE="${STATICPY_CACHE:-$HOME/iso_gen/staticpy-cache}"; mkdir -p "$CACHE"
BUNDLE="$CACHE/$(basename "$OUT").ltorch.bundle.static.py"
"$CONCAT" "$BUNDLE" "$HERE/tensor_lib.static.py" "$USER"
( cd "$ROOT" && bash staticpy/static_build.sh "$BUNDLE" "$OUT" "$HERE/lib_ffi.scm" )
# 产物 ELF 的 RUNPATH 含 $ORIGIN：把 capi 放到可执行文件旁，裸跑即可
# 裸名（无路径前缀）的产物落 $STATICPY_OUTDIR（默认 dist/），dirname 会是 cwd —— 得按同一规则解析
case "$OUT" in
  */*) OUTDIR="$(cd "$(dirname "$OUT")" && pwd)" ;;
  *)   OUTDIR="${STATICPY_OUTDIR:-$ROOT/dist}"; mkdir -p "$OUTDIR"; OUTDIR="$(cd "$OUTDIR" && pwd)" ;;
esac
if [ "$OUTDIR" != "$ROOT/cpp/torch/build" ]; then
  cp -f "$ROOT/cpp/torch/build/libtorch_capi.so" "$OUTDIR/" 2>/dev/null || true
fi
echo "built: $OUT  (run: ./$OUT ；libtorch_capi.so 已放到产物旁，libtorch 本体需在 /opt/libtorch/lib，或用 LD_LIBRARY_PATH 指过去)"
