#!/bin/bash
# build.sh — compile the face facecli CLI + libface.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_INC="${ORT_INC:-/data/venv/onnxruntime-linux-x64-gpu-1.20.1/include}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_INC" -I"$DIR")
LIBS=(-L/usr/local/lib -l:libonnxruntime.so.1)  # 系统 ORT（ldconfig 已注册，无需 rpath）

echo ">>> compiling facecli"
g++ "${CXXFLAGS[@]}" "$DIR/facecli.cpp" "$DIR/face.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/facecli"

echo ">>> compiling libface.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/face_capi.cpp" "$DIR/face.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/libface.so"

echo "OK: $DIR/facecli  $DIR/libface.so"
