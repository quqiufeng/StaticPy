#!/bin/bash
# static_build_comfycli.sh — **已废弃的历史名**，仅为外部脚本兼容而保留。
#
# 这个名字来自工具链的上游（comfycli 项目），与"编译什么"无关，容易误导：
# 本仓的静态构建只做 Python → Scheme → AOT —— 不依赖 comfycli，也不链接它。
# 真源已回到通用名 staticpy/static_build.sh，这里只做转发。
#
#   bash staticpy/static_build_comfycli.sh app.static.py app [ffi.scm]   # 等价
#   bash staticpy/static_build.sh            app.static.py app [ffi.scm]   # 推荐
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
echo "note: static_build_comfycli.sh 是历史名，已改名为 static_build.sh" >&2
exec bash "$HERE/static_build.sh" "$@"
