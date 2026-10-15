#!/bin/bash
# 编译静态库 build/libimgproc.a（供把运行时链进单文件 ELF）
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build/obj
CFLAGS="-O2 -fPIC -std=c++17 -Ithirdparty/giflib -Ithirdparty/stb -I. $(pkg-config --cflags freetype2)"
rm -f build/libimgproc.a build/obj/*.o
for f in core geom color ops filters draw effects quant lut; do
  g++ $CFLAGS -c "$f.cpp" -o "build/obj/$f.o"
done
ar rcs build/libimgproc.a build/obj/*.o
echo "built cpp/imgproc/build/libimgproc.a"
