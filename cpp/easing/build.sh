#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 easing.cpp -o build/libeasing.so -lm
echo "built cpp/easing/build/libeasing.so"
