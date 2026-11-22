#!/bin/bash
# selfcheck.sh — 一键自检：构建 + 差分测试 + 覆盖面 + 自举比对
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
fail=0

PY="${PYTHON:-python3}"
# 工作目录提前定义：[0e] 步要把判据的差分样本落盘（本仓禁止 /tmp）
W="${STATICPY_WORK:-$HOME/iso_gen/selfcheck}"
mkdir -p "$W"

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

echo ">>> [0d/4] 语义差分（翻译器：CPython 输出 vs AOT ELF 输出）"
_sem_out=$($PY staticpy/semantics_diff.py 2>&1 | tail -1)
if grep -q "失败 0 项" <<<"$_sem_out"; then echo "  ok（$_sem_out）"; else
  echo "  语义差分红了：$PY staticpy/semantics_diff.py -v"; fail=1
fi

echo ">>> [0e/4] IR 规范化判据（StaticPy 自举版 vs CPython 版，逐字节）"
# 判据本身也要防漂移：两份实现（trust/normalize_scm.py / .static.py）必须逐字节一致，
# 否则 trust/fixpoint.sh、trust/ddc.sh 用哪份就得哪份结论。
if bash staticpy/static_build.sh trust/normalize_scm.static.py normscm >/dev/null 2>&1; then
  . "$ROOT/trust/norm.sh"
  _norm_bad=0
  for _f in trust/normalize_scm.py trust/manifest.py selfhost/staticc.py \
            staticpy/static_translate.py imgproc/pil_lib.static.py; do
    $PY trust/normalize_scm.py "$_f" > "$W/norm_py.txt" 2>/dev/null
    dist/normscm "$_f" > "$W/norm_st.txt" 2>/dev/null
    cmp -s "$W/norm_py.txt" "$W/norm_st.txt" || { echo "  差异: $_f"; _norm_bad=1; }
  done
  if [ "$_norm_bad" = 0 ]; then echo "  ok（$NORM_KIND，5 个样本 token 流一致）"; else
    echo "  判据两份实现不一致：判据本身失效"; fail=1
  fi
else
  echo "  构建 dist/normscm 失败"; fail=1
fi

echo ">>> [0f/4] 预置名登记一致性（种子 ⇄ 自举 ⇄ 运行时 六条规则）"
if _reg_out=$($PY tools/check_registry.py 2>&1); then echo "  ok（$(tail -1 <<<"$_reg_out")）"; else
  echo "  登记漂移：$PY tools/check_registry.py -v"; fail=1
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
if ( cd selfhost && $PY run_staticc_py.py tests/test_staticc_input.sp "$W/sc_a.scm" >/dev/null 2>&1 ) \
   && bash staticpy/static_build.sh selfhost/staticc.py staticc >/dev/null 2>&1 \
   && ./dist/staticc selfhost/tests/test_staticc_input.sp "$W/sc_b.scm" >/dev/null 2>&1 \
   && $NORM --eq "$W/sc_a.scm" "$W/sc_b.scm" >/dev/null 2>&1; then
  echo "  ok（IR token 级一致）"
else
  echo "  自举比对失败"; fail=1
fi

echo ">>> [5/7] 信任链清单（trust/manifest.py --verify）"
_mf=$($PY trust/manifest.py --verify 2>&1 | tail -1)
if grep -q "无漂移" <<<"$_mf"; then echo "  ok（$_mf）"; else
  echo "  漂移：$_mf"; echo "    有意改动就跑 $PY trust/manifest.py --write 重签"; fail=1
fi

echo ">>> [5b/7] 依赖的系统 .so（soname→sha256；被换库即红）"
_lb=$($PY trust/manifest.py --verify-libs 2>&1 | tail -1)
if grep -q "无漂移" <<<"$_lb"; then echo "  ok（$_lb）"; else
  echo "  库被换掉：$_lb"; echo "    查：$PY trust/manifest.py --verify-libs";
  echo "    系统真升级了就跑 $PY trust/manifest.py --write 重签"; fail=1
fi

echo ">>> [6/7] DDC 异源双编译（trust/ddc.sh；慢，TRUST_SLOW=0 可跳）"
if [ "${TRUST_SLOW:-1}" = 0 ]; then echo "  跳过（TRUST_SLOW=0）"; else
  # 判据用退出码，不靠文案：0=全通过，1=IR 分叉，2=环境/构建失败，3=C2 覆盖不全（都不算通过）
  _ddout=$(bash trust/ddc.sh 2>&1); _ddrc=$?
  _dd=$(grep -E "^DDC:" <<<"$_ddout" | tail -1)
  case $_ddrc in
    0) echo "  ok（$_dd）" ;;
    1) echo "  分叉：$_dd"; echo "    定位：bash trust/ddc.sh"; fail=1 ;;
    3) echo "  C2 覆盖不全（不算通过）：$_dd"; echo "    先看是否二进制陈旧：bash trust/ddc.sh（默认从源码现建 C2）"; fail=1 ;;
    *) echo "  DDC 无法完成 rc=$_ddrc"; tail -3 <<<"$_ddout" | sed 's/^/    /'; fail=1 ;;
  esac
fi

echo ">>> [7/7] 固定点（trust/fixpoint.sh；最慢，TRUST_FIXPOINT=1 才跑）"
if [ "${TRUST_FIXPOINT:-0}" = 1 ]; then
  _fx=$(bash trust/fixpoint.sh 2>&1 | grep -E "固定点(成立|不成立)" | tail -1)
  if grep -q "成立" <<<"$_fx"; then echo "  ok（$_fx）"; else echo "  失败：bash trust/fixpoint.sh"; fail=1; fi
else
  echo "  跳过（设 TRUST_FIXPOINT=1 启用）"
fi

echo
[ "$fail" = 0 ] && echo "=== 自检通过 ===" || echo "=== 自检有问题 ==="
exit $fail
