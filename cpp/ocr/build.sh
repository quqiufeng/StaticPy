#!/bin/bash
# build.sh — compile the PaddleOCR imgsocr CLI + libocr.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_INC="${ORT_INC:-/data/venv/onnxruntime-linux-x64-gpu-1.20.1/include}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_INC" -I"$DIR")
LIBS=(-L/usr/local/lib -l:libonnxruntime.so.1)  # 系统 ORT（ldconfig 已注册，无需 rpath）

echo ">>> compiling imgsocr"
g++ "${CXXFLAGS[@]}" "$DIR/imgsocr.cpp" "$DIR/ocr.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/imgsocr"

echo ">>> compiling libocr.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/ocr_capi.cpp" "$DIR/ocr.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/libocr.so"

echo "OK:"
echo "  $DIR/imgsocr"
echo "  $DIR/libocr.so"
