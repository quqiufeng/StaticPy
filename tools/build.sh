#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
for d in face birefnet ocr florence2 sr codeformer colorize; do bash "$ROOT/cpp/$d/build.sh" >/dev/null 2>&1 || echo "warn: $d build"; done
mkdir -p /tmp/staticpy-cache/tools
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh tools/tools.static.py tools/tools tools/tools_ffi.scm )
