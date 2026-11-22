#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/warp3d/build.sh"
( cd "$ROOT" && bash staticpy/static_build.sh warp3d/w3d.static.py warp3d/w3d warp3d/warp3d_ffi.scm )
