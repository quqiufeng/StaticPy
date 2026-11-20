#!/bin/bash
# norm.sh — 统一选「IR 规范化」判据的实现（被 fixpoint.sh / ddc.sh / selfcheck.sh source）
#
# 为什么要有这一层：判据原来写死在 `$PY trust/normalize_scm.py`，于是
# 「校验信任链」这件事本身要求目标机器装着 CPython——判据比它审的东西还脆。
# normalize_scm.static.py 用被审的语言自己编出了 ELF（dist/normscm），
# 于是校验可以在「只有我们自己的产物」的机器上跑。
#
# 用法:
#   . "$ROOT/trust/norm.sh"      # 之后用 $NORM <file> / $NORM --eq A B
#
# 说明：$NORM 故意是“命令串”（可能含空格），调用处按 `$NORM "$f"` 不带引号展开。
#      两份实现已做逐字节差分（见 selfcheck.sh 的 [0e] 步），不一致即判据失效。
ROOT="${ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PY="${PYTHON:-python3}"

if [ -x "$ROOT/dist/normscm" ]; then
    NORM="$ROOT/dist/normscm"          # StaticPy 自举产物：判据不依赖 CPython
    NORM_KIND="staticpy-elf"
else
    NORM="$PY $ROOT/trust/normalize_scm.py"   # 退回弱化路径（会被提示）
    NORM_KIND="cpython"
fi
