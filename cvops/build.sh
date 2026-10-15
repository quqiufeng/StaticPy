#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/cvops/build.sh"
mkdir -p /tmp/staticpy-cache/cvops
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh cvops/cv.static.py cvops/cv cvops/cvops_ffi.scm )
