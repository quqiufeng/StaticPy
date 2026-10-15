#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 warp3d.cpp -o build/libwarp3d.so -lm
echo "built cpp/warp3d/build/libwarp3d.so"
