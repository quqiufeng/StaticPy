#!/bin/bash
# build_app.sh USER.static.py OUT — 把用户程序与 pil_lib 拼成一个独立 ELF
# （concat 工具本身也是 StaticPy 写的：imgproc/concat.static.py）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
USER="$1"; OUT="$2"
CONCAT="$ROOT/concat"
if [ ! -x "$CONCAT" ]; then
  ( cd "$ROOT" && bash staticpy/static_build_comfycli.sh imgproc/concat.static.py concat >/dev/null )
fi
mkdir -p /tmp/staticpy-cache
BUNDLE="/tmp/staticpy-cache/$(basename "$OUT").bundle.static.py"
"$CONCAT" "$BUNDLE" "$HERE/pil_lib.static.py" "$USER"
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh "$BUNDLE" "$OUT" "$HERE/imgproc_ffi.scm" )
echo "built: $OUT  (run: LD_LIBRARY_PATH=$ROOT/cpp/imgproc/build ./$OUT ...)"
