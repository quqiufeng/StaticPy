#!/bin/bash
# embed-build.sh — 把 LuaJIT + 运行时(libimgproc) + 内嵌 Lua 脚本 编成单文件 ELF
#
# 用法: bash luajit/embed-build.sh [APP.lua] [OUT]
#   ./OUT            # 运行内嵌脚本
#   ./OUT script.lua # 运行指定脚本
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
APP="${1:-$HERE/app.lua}"; OUT="${2:-$ROOT/lua_app}"

echo ">>> [1/3] 静态库 libimgproc.a"
bash "$ROOT/cpp/imgproc/build_static.sh"
LIBA="$ROOT/cpp/imgproc/build/libimgproc.a"

echo ">>> [2/3] 内嵌 Lua 脚本（xxd -> embed_lua.h）"
xxd -i -n EMBED_LUA_SRC "$APP" > "$HERE/embed_lua.h"

echo ">>> [3/3] 链接单文件 ELF（含 LuaJIT + 运行时）"
LJINC=/usr/local/luajit/include/luajit-2.1; [ -d "$LJINC" ] || LJINC=/usr/local/include/luajit-2.1
LJLIB=/usr/local/luajit/lib/libluajit-5.1.a; [ -f "$LJLIB" ] || LJLIB=/usr/local/lib/libluajit-5.1.a
# embed.c 用 C 编译（避免 C++ 名字修饰），再 g++ 链接（拉 libstdc++）
gcc -O2 -I"$LJINC" -c "$HERE/embed.c" -o "$HERE/embed.o"
g++ -O2 -rdynamic "$HERE/embed.o" -o "$OUT" \
    -Wl,--whole-archive "$LIBA" -Wl,--no-whole-archive \
    "$LJLIB" -L/usr/lib/x86_64-linux-gnu -l:libgif.so.7 -lwebp -ltiff -lfreetype -lm -ldl -lpthread
echo "=== done: $OUT （单文件：LuaJIT + 图像运行时）==="
echo "  运行: $OUT IN OUT   （或 $OUT script.lua）"
