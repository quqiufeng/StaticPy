#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/font/build.sh"
( cd "$ROOT" && bash staticpy/static_build.sh font/font.static.py font/font font/font_ffi.scm )
