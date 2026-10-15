#!/bin/bash
# tools/run.sh — 设好各 C 库路径再跑 tools（ORT 走系统 /usr/local/lib，无需设置）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
export LD_LIBRARY_PATH="$ROOT/cpp/face:$ROOT/cpp/birefnet:$ROOT/cpp/ocr:$ROOT/cpp/florence2:$ROOT/cpp/sr:$ROOT/cpp/codeformer:$ROOT/cpp/colorize:$ROOT/cpp/pose:$ROOT/cpp/det${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/tools" "$@"
