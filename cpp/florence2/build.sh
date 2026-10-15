#!/bin/bash
# build.sh — compile the Florence-2 img2prompt CLI + libflorence2.so (pure C++ / ONNX Runtime).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORT_INC="${ORT_INC:-/data/venv/onnxruntime-linux-x64-gpu-1.20.1/include}"
MODEL_DIR="${MODEL_DIR:-/data/models/florence2}"
PYTHON="${STATICPY_PYTHON:-python3}"

if [ ! -f "$MODEL_DIR/vocab.bin" ]; then
    echo ">>> generating $MODEL_DIR/vocab.bin"
    "$PYTHON" "$DIR/gen_vocab.py" "$MODEL_DIR"
fi

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$ORT_INC" -I"$DIR")
LIBS=(-L/usr/local/lib -l:libonnxruntime.so.1)  # 系统 ORT（ldconfig 已注册，无需 rpath）

echo ">>> compiling img2prompt"
g++ "${CXXFLAGS[@]}" "$DIR/img2prompt.cpp" "$DIR/florence2.cpp" "${INCS[@]}" "${LIBS[@]}" -o "$DIR/img2prompt"

echo ">>> compiling libflorence2.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/florence2_capi.cpp" "$DIR/florence2.cpp" "${INCS[@]}" "${LIBS[@]}" \
    -o "$DIR/libflorence2.so"

echo "OK:"
echo "  $DIR/img2prompt"
echo "  $DIR/libflorence2.so"
