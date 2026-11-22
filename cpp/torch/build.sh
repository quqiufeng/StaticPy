#!/bin/bash
# 构建 libtorch_capi.so（真 at::Tensor 绑定的 C ABI）。
# 依赖本机 libtorch（默认 /opt/libtorch，可用 LIBTORCH_ROOT 覆盖）。
# 产物：cpp/torch/build/libtorch_capi.so，运行时需 LD_LIBRARY_PATH 指向 libtorch/lib。
set -euo pipefail
cd "$(dirname "$0")"

LIBTORCH_ROOT="${LIBTORCH_ROOT:-/opt/libtorch}"
if [ ! -d "$LIBTORCH_ROOT/include/torch" ]; then
  echo "缺 libtorch：$LIBTORCH_ROOT/include/torch 不存在（设 LIBTORCH_ROOT=...）" >&2
  exit 1
fi

mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 \
  -I"$LIBTORCH_ROOT/include" \
  -I"$LIBTORCH_ROOT/include/torch/csrc/api/include" \
  torch_capi.cpp \
  -L"$LIBTORCH_ROOT/lib" -ltorch -ltorch_cpu -lc10 \
  -Wl,-rpath,"$LIBTORCH_ROOT/lib" \
  -o build/libtorch_capi.so

echo "built $(pwd)/build/libtorch_capi.so"
echo "run with: export LD_LIBRARY_PATH=$LIBTORCH_ROOT/lib:\$LD_LIBRARY_PATH"
