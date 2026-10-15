#!/bin/bash
# 构建 hashlib（C 库 + StaticPy ELF）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/hashlib/build.sh"
mkdir -p /tmp/staticpy-cache/hashlib
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh hashlib/hash.static.py hashlib/hash hashlib/hashlib_ffi.scm )
