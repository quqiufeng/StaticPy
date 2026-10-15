#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 font.cpp -o build/libfont.so $(pkg-config --cflags --libs freetype2)
echo "built cpp/font/build/libfont.so"
