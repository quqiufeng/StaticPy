#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/atlas/build.sh"
mkdir -p /tmp/staticpy-cache/atlas
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh atlas/atlas.static.py atlas/atlas atlas/atlas_ffi.scm )
