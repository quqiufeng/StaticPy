#!/bin/bash
# build.sh — 构建独立图像处理工具（C++ 底层库 + StaticPy 程序）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
# 信任闸门：被 pin 的系统 .so 若与 trust/manifest.json 不符，拒绝构建（不是静默换库）。
# 跳过：STATICPY_NO_LIB_GATE=1。重签：python3 trust/manifest.py --write
if [ "${STATICPY_NO_LIB_GATE:-0}" != 1 ] && [ -f "$ROOT/trust/manifest.json" ]; then
  if ! python3 "$ROOT/trust/manifest.py" --verify-libs >/dev/null 2>&1; then
    echo "!!! 系统 .so 与信任链清单不符，拒绝构建：" >&2
    python3 "$ROOT/trust/manifest.py" --verify-libs 2>&1 | sed 's/^/    /' >&2
    echo "    确认是新库就重签：python3 trust/manifest.py --write；临时绕过：STATICPY_NO_LIB_GATE=1" >&2
    exit 1
  fi
fi

echo ">>> [1/2] libimgproc.so"
bash "$ROOT/cpp/imgproc/build_cpp.sh"
echo ">>> [2/2] mirror_gif (StaticPy)"
# 缓存目录与构建脚本一致（不再是 /tmp）
CACHE="${STATICPY_CACHE:-$HOME/iso_gen/staticpy-cache}"
mkdir -p "$CACHE/imgproc"
# 自举工具：concat（StaticPy）
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh imgproc/concat.static.py concat >/dev/null )
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh imgproc/mirror_gif.static.py imgproc/mirror_gif imgproc/imgproc_ffi.scm \
      && bash staticpy/static_build_comfycli.sh imgproc/pilcli.static.py imgproc/pilcli imgproc/imgproc_ffi.scm \
      && "$ROOT/dist/concat" "$CACHE/pil.bundle.static.py" imgproc/pil_lib.static.py imgproc/pil_cli.static.py \
      && bash staticpy/static_build_comfycli.sh "$CACHE/pil.bundle.static.py" imgproc/pil imgproc/imgproc_ffi.scm )
echo "=== build done ==="
