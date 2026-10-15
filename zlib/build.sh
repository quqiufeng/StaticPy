#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/zlib/build.sh"
mkdir -p /tmp/staticpy-cache/zlib
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh zlib/zc.static.py zlib/zc zlib/zlib_ffi.scm )
