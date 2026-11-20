#!/bin/bash
# static_build.sh — 兼容入口（保留旧名字，逻辑已合并到 static_build_comfycli.sh）
#
# 历史上这里有一份“上游原版”构建脚本（硬编码 /opt/ReScheme、链接 torch），
# 与 static_build_comfycli.sh 功能重复且会漂移。现在只做转发：单一真源。
#
#   bash staticpy/static_build.sh app.static.py app [ffi.scm]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec bash "$HERE/static_build_comfycli.sh" "$@"
