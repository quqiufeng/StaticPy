#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/upscale/build.sh"
mkdir -p /tmp/staticpy-cache/upscale
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh upscale/up.static.py upscale/up upscale/upscale_ffi.scm )
