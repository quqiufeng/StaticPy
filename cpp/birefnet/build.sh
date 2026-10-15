#!/bin/bash
# build.sh — compile the BiRefNet bgremove CLI + libbirefnet.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_INC="${ORT_INC:-/data/venv/onnxruntime-linux-x64-gpu-1.20.1/include}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_INC" -I"$DIR")
LIBS=(-L/usr/local/lib -l:libonnxruntime.so.1)  # 系统 ORT（ldconfig 已注册，无需 rpath）

echo ">>> compiling bgremove"
g++ "${CXXFLAGS[@]}" "$DIR/bgremove.cpp" "$DIR/birefnet.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/bgremove"

echo ">>> compiling libbirefnet.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/birefnet_capi.cpp" "$DIR/birefnet.cpp" "${INCS[@]}" "${LIBS[@]}" \
    -o "$DIR/libbirefnet.so"

echo "OK:"
echo "  $DIR/bgremove"
echo "  $DIR/libbirefnet.so"
