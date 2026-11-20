#!/bin/bash
# 构建 libpyarr.so（C 内核）。产物留在插件目录，运行时按 STATICPY_PYARR / 绝对路径 / soname 依次找。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cc -O2 -fPIC -shared -o "$HERE/libpyarr.so" "$HERE/pyarray.c"
echo "built $HERE/libpyarr.so"
