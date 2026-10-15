#!/bin/bash
# build.sh — 构建独立图像处理工具（C++ 底层库 + StaticPy 程序）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
echo ">>> [1/2] libimgproc.so"
bash "$ROOT/cpp/imgproc/build_cpp.sh"
echo ">>> [2/2] mirror_gif (StaticPy)"
mkdir -p /tmp/staticpy-cache/imgproc
# 自举工具：concat（StaticPy）
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh imgproc/concat.static.py concat >/dev/null )
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh imgproc/mirror_gif.static.py imgproc/mirror_gif imgproc/imgproc_ffi.scm \
      && bash staticpy/static_build_comfycli.sh imgproc/pilcli.static.py imgproc/pilcli imgproc/imgproc_ffi.scm \
      && "$ROOT/concat" /tmp/staticpy-cache/pil.bundle.static.py imgproc/pil_lib.static.py imgproc/pil_cli.static.py \
      && bash staticpy/static_build_comfycli.sh /tmp/staticpy-cache/pil.bundle.static.py imgproc/pil imgproc/imgproc_ffi.scm )
echo "=== build done ==="
