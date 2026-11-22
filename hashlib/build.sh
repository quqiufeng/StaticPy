#!/bin/bash
# 构建 hashlib（C 库 + StaticPy ELF）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
bash "$ROOT/cpp/hashlib/build.sh"
( cd "$ROOT" && bash staticpy/static_build.sh hashlib/hash.static.py hashlib/hash hashlib/hashlib_ffi.scm )
