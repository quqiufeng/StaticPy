#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 pathfind.cpp -o build/libpathfind.so
echo "built cpp/pathfind/build/libpathfind.so"
