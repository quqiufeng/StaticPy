#!/bin/bash
# whisper/build.sh — 先编 libwhisper.so，再 AOT 编译 StaticPy 前端
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"

bash "$ROOT/cpp/whisper/build.sh"
mkdir -p /tmp/staticpy-cache/whisper
( cd "$ROOT" && bash staticpy/static_build_comfycli.sh \
    whisper/whisper.static.py whisper/whisper whisper/whisper_ffi.scm )
