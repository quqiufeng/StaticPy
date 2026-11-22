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
echo "built: $OUT  (run: LD_LIBRARY_PATH=$ROOT/cpp/torch/build ./$OUT)"
