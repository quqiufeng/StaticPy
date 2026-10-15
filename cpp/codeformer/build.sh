#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
ORT_INC="${ORT_INC:-/data/venv/onnxruntime-linux-x64-gpu-1.20.1/include}"
g++ -O2 -fPIC -shared -std=c++17 cf.cpp -o "$PWD/libcodeformer.so" -I"$ORT_INC" -L/usr/local/lib -l:libonnxruntime.so.1
echo "built cpp/codeformer/libcodeformer.so"
