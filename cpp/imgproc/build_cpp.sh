#!/bin/bash
# 编译 C++ 底层库（多文件 -> libimgproc.so）
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 \
    -Ithirdparty/giflib -Ithirdparty/stb -I. $(pkg-config --cflags freetype2) \
    core.cpp geom.cpp color.cpp ops.cpp filters.cpp draw.cpp effects.cpp quant.cpp lut.cpp \
    -o build/libimgproc.so -L/usr/lib/x86_64-linux-gnu -l:libgif.so.7 -lfreetype -lwebp -ltiff
echo "built build/libimgproc.so"
