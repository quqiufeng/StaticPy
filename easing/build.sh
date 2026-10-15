#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/easing/build.sh"
mkdir -p /tmp/staticpy-cache/easing
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh easing/ease.static.py easing/ease easing/easing_ffi.scm )
