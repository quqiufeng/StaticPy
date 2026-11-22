#!/bin/bash
# build_app.sh USER.static.py OUT — 把用户程序与 sqlite_lib（Connection/Cursor）拼成独立 ELF
#   bash plugins/sqlite/build_app.sh plugins/sqlite/demo.static.py demo
# 前置：bash cpp/sqlite/build.sh（出 cpp/sqlite/build/libsqlitec.so）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(cd "$HERE/../.." && pwd)"
USER="$1"; OUT="$2"
CONCAT="$ROOT/dist/concat"
if [ ! -x "$CONCAT" ]; then
  ( cd "$ROOT" && bash staticpy/static_build.sh imgproc/concat.static.py concat >/dev/null )
fi
if [ ! -f "$ROOT/cpp/sqlite/build/libsqlitec.so" ]; then
  ( cd "$ROOT" && bash cpp/sqlite/build.sh >/dev/null )
fi
CACHE="${STATICPY_CACHE:-$HOME/iso_gen/staticpy-cache}"; mkdir -p "$CACHE"
BUNDLE="$CACHE/$(basename "$OUT").sqlite.bundle.static.py"
"$CONCAT" "$BUNDLE" "$HERE/sqlite_lib.static.py" "$USER"
( cd "$ROOT" && bash staticpy/static_build.sh "$BUNDLE" "$OUT" "$HERE/sqlite_ffi.scm" )
echo "built: $OUT  (run: LD_LIBRARY_PATH=$ROOT/cpp/sqlite/build ./$OUT)"
