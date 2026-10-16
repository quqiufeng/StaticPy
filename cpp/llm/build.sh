#!/bin/bash
# build.sh — 编译 libllm.so（Hunyuan-MT / llama.cpp 服务的 C ABI 封装）
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$DIR/thirdparty")

echo ">>> compiling libllm.so"
g++ "${CXXFLAGS[@]}" -shared "$DIR/llm_capi.cpp" \
  "${INCS[@]}" -lpthread -o "$DIR/libllm.so"

echo "OK: $DIR/libllm.so"
