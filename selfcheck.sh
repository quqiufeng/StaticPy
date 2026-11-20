#!/bin/bash
# selfcheck.sh — 一键自检：构建 + 差分测试 + 覆盖面 + 自举比对
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
fail=0

PY="${PYTHON:-python3}"

echo ">>> [0/4] 单一真源检查（plugins/ ⇄ static_prelude.scm）"
if $PY tools/split_plugins.py --check >/dev/null 2>&1; then echo "  ok"; else
  echo "  漂移：跑 python3 tools/split_plugins.py 重新生成"; fail=1
fi

echo ">>> [0b/4] 插件语法钩子（rewrite/expr/stmt/infer）"
_hook_out=$(STATICPY_PLUGINS_PATH="$ROOT/examples" $PY staticpy/static_translate.py \
  --plugins syntax_plugin examples/syntax_plugin/demo.static.py 2>/dev/null)
if grep -qF "(define TAG 7)" <<<"$_hook_out" && grep -qF "(* 2 i)" <<<"$_hook_out" \
   && grep -qF "(not (fx>= i 3))" <<<"$_hook_out"; then echo "  ok"; else
  echo "  插件钩子失效（rewrite/expr/stmt）"; fail=1
fi

echo ">>> [0c/4] 词法器差分（static_translate.static.py vs CPython tokenize）"
if bash staticpy/check_tokenize.sh staticpy/static_translate.py selfhost/staticc.py \
     imgproc/pil_lib.static.py >/dev/null 2>&1; then echo "  ok（token 流一致）"; else
  echo "  词法器漂移：bash staticpy/check_tokenize.sh <file>"; fail=1
fi

echo ">>> [1/4] 构建 C 库 + 前端（imgproc）"
bash imgproc/build.sh >/dev/null 2>&1 && echo "  ok" || { echo "  失败"; fail=1; }

if $PY -c "import PIL, numpy" 2>/dev/null; then
  echo ">>> [2/4] 差分测试（Pillow vs 我们，逐像素）"
  $PY imgproc/difftest.py 2>/dev/null | tail -1
  echo ">>> [3/4] 覆盖面（自省核对）"
  $PY imgproc/frontend_coverage.py 2>/dev/null | tail -1
  echo ">>> [3b/4] hashlib 差分（Python vs 我们，逐字节）"
  bash hashlib/build.sh >/dev/null 2>&1 && $PY hashlib/difftest.py 2>/dev/null | tail -1
  echo ">>> [3c/4] zlib 差分（Python vs 我们，逐字节）"
  bash zlib/build.sh >/dev/null 2>&1 && $PY zlib/difftest.py 2>/dev/null | tail -1
else
  echo ">>> [2-3/4] 跳过差分/覆盖（缺 Pillow/numpy，仅'测量'需要）"
fi

echo ">>> [4/4] 自举比对（环 2：staticc.py CPython vs 自举 ELF）"
bash imgproc/build.sh >/dev/null 2>&1
if ( cd selfhost && $PY run_staticc_py.py tests/test_staticc_input.sp /tmp/sc_a.scm >/dev/null 2>&1 ) \
   && bash staticpy/static_build_comfycli.sh selfhost/staticc.py staticc >/dev/null 2>&1 \
   && ./dist/staticc selfhost/tests/test_staticc_input.sp /tmp/sc_b.scm >/dev/null 2>&1 \
   && diff -q /tmp/sc_a.scm /tmp/sc_b.scm >/dev/null; then
  echo "  ok（一致）"
else
  echo "  自举比对失败"; fail=1
fi

echo
[ "$fail" = 0 ] && echo "=== 自检通过 ===" || echo "=== 自检有问题 ==="
exit $fail
