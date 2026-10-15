#!/bin/bash
# build.sh — compile the BiRefNet bgremove CLI + libbirefnet.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_DIR="${ORT_DIR:-/data/venv/onnxruntime-linux-x64-gpu-1.26.0}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_DIR/include" -I"$DIR")
LIBS=(-L"$ORT_DIR/lib" -Wl,-rpath,"$ORT_DIR/lib" -lonnxruntime)

echo ">>> compiling bgremove"
g++ "${CXXFLAGS[@]}" "$DIR/bgremove.cpp" "$DIR/birefnet.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/bgremove"

echo ">>> compiling libbirefnet.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/birefnet_capi.cpp" "$DIR/birefnet.cpp" "${INCS[@]}" "${LIBS[@]}" \
    -o "$DIR/libbirefnet.so"

echo "OK:"
echo "  $DIR/bgremove"
echo "  $DIR/libbirefnet.so"
