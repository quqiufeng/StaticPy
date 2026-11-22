#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/easing/build.sh"
( cd "$ROOT" && bash staticpy/static_build.sh easing/ease.static.py easing/ease easing/easing_ffi.scm )
