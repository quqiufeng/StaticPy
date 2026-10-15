#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 atlas.cpp -o build/libatlas.so
echo "built cpp/atlas/build/libatlas.so"
