#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 upscale.cpp -o build/libupscale.so
echo "built cpp/upscale/build/libupscale.so"
