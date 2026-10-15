#!/bin/bash
# selfcheck.sh — 一键自检：构建 + 差分测试 + 覆盖面 + 自举比对
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
fail=0

echo ">>> [1/4] 构建 C 库 + 前端（imgproc）"
bash imgproc/build.sh >/dev/null 2>&1 && echo "  ok" || { echo "  失败"; fail=1; }

PY="${PYTHON:-python3}"
if $PY -c "import PIL, numpy" 2>/dev/null; then
  echo ">>> [2/4] 差分测试（Pillow vs 我们，逐像素）"
  $PY imgproc/difftest.py 2>/dev/null | tail -1
  echo ">>> [3/4] 覆盖面（自省核对）"
  $PY imgproc/frontend_coverage.py 2>/dev/null | tail -1
else
  echo ">>> [2-3/4] 跳过差分/覆盖（缺 Pillow/numpy，仅'测量'需要）"
fi

echo ">>> [4/4] 自举比对（环 2：staticc.py CPython vs 自举 ELF）"
bash imgproc/build.sh >/dev/null 2>&1
if ( cd selfhost && $PY run_staticc_py.py tests/test_staticc_input.sp /tmp/sc_a.scm >/dev/null 2>&1 ) \
   && bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc >/dev/null 2>&1 \
   && ./staticc selfhost/tests/test_staticc_input.sp /tmp/sc_b.scm >/dev/null 2>&1 \
   && diff -q /tmp/sc_a.scm /tmp/sc_b.scm >/dev/null; then
  echo "  ok（一致）"
else
  echo "  自举比对失败"; fail=1
fi

echo
[ "$fail" = 0 ] && echo "=== 自检通过 ===" || echo "=== 自检有问题 ==="
exit $fail
