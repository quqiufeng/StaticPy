#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 cvops.cpp -o build/libcvops.so
echo "built cpp/cvops/build/libcvops.so"
