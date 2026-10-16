#!/bin/bash
# whisper/run.sh — 设好 C 库路径再跑 whisper 前端
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
export LD_LIBRARY_PATH="$ROOT/cpp/whisper${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/whisper" "$@"
