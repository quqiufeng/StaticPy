#!/bin/bash
# build.sh — 编译 libwhisper.so（ctranslate2 C++ Whisper + 自写 log-mel 前端）
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CT2="$DIR/thirdparty/ctranslate2"

if [ ! -f "$CT2/lib/libctranslate2.so.4" ]; then
  echo "缺少 $CT2/lib/libctranslate2.so.4" >&2
  echo "来源: pip ctranslate2==4.8.3 wheel 的 ctranslate2.libs/" >&2
  echo "  cp ctranslate2.libs/libctranslate2-<hash>.so.4.8.3  $CT2/lib/libctranslate2.so.4" >&2
  echo "  cp ctranslate2.libs/libgomp-<hash>.so.1.0.0         $CT2/lib/" >&2
  echo "  ln -sf libctranslate2.so.4 $CT2/lib/libctranslate2-<hash>.so.4.8.3" >&2
  echo "头文件: 来自 CTranslate2 源码 v4.8.3 的 include/{ctranslate2,half_float,nlohmann}" >&2
  exit 1
fi

CXXFLAGS=(-O2 -std=c++17 -fPIC)
INCS=(-I"$DIR" -I"$CT2/include")
LIBS=(-L"$CT2/lib" -l:libctranslate2.so.4 -lfftw3f -lstdc++ -lpthread -ldl)
# --disable-new-dtags -> DT_RPATH（传递性），使 ctranslate2 的依赖 libgomp 也能找到
RPATH="-Wl,--disable-new-dtags -Wl,-rpath,\$ORIGIN/thirdparty/ctranslate2/lib"

echo ">>> compiling libwhisper.so"
g++ "${CXXFLAGS[@]}" -shared \
  "$DIR/whisper_capi.cpp" "$DIR/feat.cpp" \
  "${INCS[@]}" "${LIBS[@]}" $RPATH \
  -o "$DIR/libwhisper.so"

echo "OK: $DIR/libwhisper.so"
ldd "$DIR/libwhisper.so" | grep -E "ctranslate2|gomp|fftw3f" || true
