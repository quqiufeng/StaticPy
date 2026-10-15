#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/font/build.sh"
mkdir -p /tmp/staticpy-cache/font
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh font/font.static.py font/font font/font_ffi.scm )
