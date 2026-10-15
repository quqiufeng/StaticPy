#!/bin/bash
# img2prompt.sh — 一张图片 → Florence-2 生成提示词 → backup.sh 出图
#
# 用法:
#   bash img2prompt.sh <输入图> [输出图] [宽] [高]
#   bash img2prompt.sh photo.jpg                # 只出提示词（不调 backup.sh）
#   bash img2prompt.sh photo.jpg out.png 2560 1440
#
# 环境变量:
#   TASK        Florence-2 任务（默认 <MORE_DETAILED_CAPTION>）
#               <CAPTION> <DETAILED_CAPTION> <MORE_DETAILED_CAPTION> <OCR>
#   BACKUP      backup.sh 路径（默认 ../sd/backup.sh）
#   MODEL_DIR   Florence-2 ONNX 目录（默认 /data/models/florence2）
#   GEN=0       只出提示词，不调 backup.sh
#   IMG2PROMPT  img2prompt 二进制路径
#
# 其余环境变量（CFG_SCALE/STEPS/SEED/...）透传给 backup.sh。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMG2PROMPT="${IMG2PROMPT:-$SCRIPT_DIR/img2prompt}"
MODEL_DIR="${MODEL_DIR:-/data/models/florence2}"
BACKUP="${BACKUP:-$SCRIPT_DIR/../sd/backup.sh}"
TASK="${TASK:-<MORE_DETAILED_CAPTION>}"
GEN="${GEN:-1}"

if [ "$#" -lt 1 ]; then
    echo "用法: bash img2prompt.sh <输入图> [输出图] [宽] [高]" >&2
    exit 2
fi

IMAGE="$1"; OUTPUT="${2:-}"; W="${3:-}"; H="${4:-}"

[ -f "$IMAGE" ] || { echo "输入图不存在: $IMAGE" >&2; exit 1; }
[ -x "$IMG2PROMPT" ] || { echo "img2prompt 未编译: $IMG2PROMPT (先跑 build.sh)" >&2; exit 1; }

echo "[img2prompt.sh] Florence-2 任务: $TASK" >&2
PROMPT="$("$IMG2PROMPT" --model-dir "$MODEL_DIR" --task "$TASK" "$IMAGE")"

echo ""
echo "================ 生成的提示词 ================"
echo "$PROMPT"
echo "=============================================="
echo ""

if [ "$GEN" = "0" ] || [ -z "$OUTPUT" ]; then
    echo "（未指定输出图或 GEN=0，仅输出提示词）" >&2
    exit 0
fi

[ -x "$BACKUP" ] || { echo "backup.sh 不存在: $BACKUP" >&2; exit 1; }

# 透传分辨率；未指定则由 backup.sh 用默认 2560x1440
if [ -n "$W" ] && [ -n "$H" ]; then
    bash "$BACKUP" "$PROMPT" "$OUTPUT" "$W" "$H"
else
    bash "$BACKUP" "$PROMPT" "$OUTPUT"
fi
