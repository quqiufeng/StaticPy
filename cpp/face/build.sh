#!/bin/bash
# build.sh — compile the face facecli CLI + libface.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_DIR="${ORT_DIR:-/data/venv/onnxruntime-linux-x64-gpu-1.26.0}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_DIR/include" -I"$DIR")
LIBS=(-L"$ORT_DIR/lib" -Wl,-rpath,"$ORT_DIR/lib" -lonnxruntime)

echo ">>> compiling facecli"
g++ "${CXXFLAGS[@]}" "$DIR/facecli.cpp" "$DIR/face.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/facecli"

echo ">>> compiling libface.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/face_capi.cpp" "$DIR/face.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/libface.so"

echo "OK: $DIR/facecli  $DIR/libface.so"
