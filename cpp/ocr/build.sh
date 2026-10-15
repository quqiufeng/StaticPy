#!/bin/bash
# build.sh — compile the PaddleOCR imgsocr CLI + libocr.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_DIR="${ORT_DIR:-/data/venv/onnxruntime-linux-x64-gpu-1.26.0}"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_DIR/include" -I"$DIR")
LIBS=(-L"$ORT_DIR/lib" -Wl,-rpath,"$ORT_DIR/lib" -lonnxruntime)

echo ">>> compiling imgsocr"
g++ "${CXXFLAGS[@]}" "$DIR/imgsocr.cpp" "$DIR/ocr.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/imgsocr"

echo ">>> compiling libocr.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/ocr_capi.cpp" "$DIR/ocr.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/libocr.so"

echo "OK:"
echo "  $DIR/imgsocr"
echo "  $DIR/libocr.so"
