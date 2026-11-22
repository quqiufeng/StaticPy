#!/bin/bash
# rebuild_spboot.sh — 把 ~/iso_gen/spboot/spboot_self 重编成「当前源码的产物」。
#
# 为什么需要它：spboot_self 是个无源可读的 4.3 MB ELF，一旦 staticc.sp 改了而它没重建，
# 所有拿它当 C2 的比较（DDC / run_sp_tests）都会悄悄退化成「新源码 vs 旧二进制」，
# 把"二进制落后"误报成"能力差"。2026-11-20 就是这样报出了 7 项假的 gap。
#
# 做法：走可审计链 种子(static_translate.py) → staticc.py 的 ELF(E0) → 编 staticc.sp
#      → c2.scm → AOT → spboot_self(+.so)。产物落在 ~/iso_gen/spboot/，
#      旧件备份为 spboot_self.old-<时间戳>。
#
# 用法:
#   bash trust/rebuild_spboot.sh
#   bash trust/rebuild_spboot.sh --force      # 即使看起来不旧也重编
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
PY="${PYTHON:-python3}"
WORK="${WORK:-$HOME/iso_gen/spboot}"
BUILD="bash staticpy/static_build.sh"
TRUSTROOT="selfhost/staticc.sp"
SEEDSRC="selfhost/staticc.py"
mkdir -p "$WORK"

if [ "${1:-}" != "--force" ] && [ -x "$WORK/spboot_self" ] && ! [ "$TRUSTROOT" -nt "$WORK/spboot_self" ]; then
  echo "spboot_self 不比 $TRUSTROOT 旧，无需重编（--force 强制）"
  exit 0
fi

# 不备份旧 ELF：二进制是**纯导出物**，留它等于留一堆无法验证的字节
# （旧件对应哪一版 staticc.sp 没人记得，从 HEAD 也重建不出来 = 不可反驳的考古）。
# 该留的是**推导输入**：源 hash + 生成的 c2.scm。有它们，旧二进制随时可再生成。
SRCH="$(sha256sum "$TRUSTROOT" "$SEEDSRC" | sha256sum | cut -c1-16)"
[ -f "$WORK/c2_rebuild.scm" ] && cp -a "$WORK/c2_rebuild.scm" "$WORK/c2_prev-$SRCH.scm" 2>/dev/null

# 1) 种子的 ELF（E0）
$BUILD "$SEEDSRC" staticc_e0_rebuild >"$WORK/e0_build.log" 2>&1 || { echo "!! 构建 E0 失败（$WORK/e0_build.log）"; tail -3 "$WORK/e0_build.log"; exit 1; }
E0="$ROOT/dist/staticc_e0_rebuild"
# 2) E0 编 staticc.sp → c2.scm
"$E0" "$TRUSTROOT" "$WORK/c2_rebuild.scm" >"$WORK/c2_gen.log" 2>&1 || { echo "!! E0 编 $TRUSTROOT 失败（$WORK/c2_gen.log）"; exit 1; }
# 3) c2.scm → spboot_self（ELF + 同名 .so 必须同目录）
STATICPY_OUTDIR="$WORK" $BUILD "$WORK/c2_rebuild.scm" spboot_self >"$WORK/rebuild.log" 2>&1 || { echo "!! 构建 spboot_self 失败（$WORK/rebuild.log）"; tail -3 "$WORK/rebuild.log"; exit 1; }

echo "$SRCH" > "$WORK/spboot_self.src"
echo ">>> 已重编：$WORK/spboot_self（源 hash $SRCH，记在 spboot_self.src）"
echo "    自检：bash selfhost/tests/run_sp_tests.sh && SPSTATICC=$WORK/spboot_self bash trust/ddc.sh"
