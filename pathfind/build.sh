#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/pathfind/build.sh"
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh pathfind/pf.static.py pathfind/pf pathfind/pathfind_ffi.scm )
