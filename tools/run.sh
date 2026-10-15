#!/bin/bash
# tools/run.sh — 设好 LD_LIBRARY_PATH 再跑 tools
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
ORT_DIR="${ORT_DIR:-/data/venv/onnxruntime-linux-x64-gpu-1.26.0}"
export LD_LIBRARY_PATH="$ROOT/cpp/face:$ROOT/cpp/birefnet:$ROOT/cpp/ocr:$ROOT/cpp/florence2:$ORT_DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/tools" "$@"
