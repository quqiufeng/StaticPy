#!/bin/bash
# 构建 libsqlitec.so（libsqlite3 的 C ABI）
#   bash cpp/sqlite/build.sh
# 产物：cpp/sqlite/build/libsqlitec.so（rpath 不需要：系统 libsqlite3 在默认路径）
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f /usr/include/sqlite3.h ]; then
  echo "缺 sqlite3 开发头：/usr/include/sqlite3.h（apt install libsqlite3-dev）" >&2
  exit 1
fi

mkdir -p build
g++ -O2 -fPIC -shared -std=c++17 \
  sqlite_capi.cpp \
  -lsqlite3 \
  -o build/libsqlitec.so

echo "built $(pwd)/build/libsqlitec.so"
