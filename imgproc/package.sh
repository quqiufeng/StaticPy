#!/bin/bash
# package.sh — 把一个 StaticPy ELF 打成「自包含部署包」（含全部 .so 传递依赖）
#
# 用法: bash imgproc/package.sh [APP] [NAME]
#   默认 APP=imgproc/pil  NAME=basename(APP)
# 产物: dist/<NAME>/  （含启动器 <NAME>、app、lib/*.so）与 dist/<NAME>.tar.gz
#
# 目标服务器零要求：不需要 Python/pip/任何预装库；解包后 ./<NAME> 即可运行。
# 唯一不可再拆：Linux 内核 + x86-64 + glibc 下限（用 GLIBC_SYSROOT 构建即可覆盖新老发行版）。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
APP="${1:-$ROOT/imgproc/pil}"
NAME="${2:-$(basename "$APP")}"
LIBDIR_BUILD="$ROOT/cpp/imgproc/build"
OUT="$ROOT/dist/$NAME"

# glibc 核心：不打包（宿主提供；用老 sysroot 构建即可覆盖新老发行版）
EXCLUDE_RE='^(libc\.so|libm\.so|libpthread\.so|libdl\.so|librt\.so|ld-linux|linux-vdso)'

echo ">>> 打包 $APP -> $OUT"
rm -rf "$OUT"; mkdir -p "$OUT/lib"

cp "$APP" "$OUT/app"; chmod +x "$OUT/app"
# StaticPy ELF 运行期还要加载同名 <stem>.so（Chez AOT 的 Scheme 机器码）
[ -f "${APP}.so" ] && cp "${APP}.so" "$OUT/" && echo "  附带 ${APP}.so"
[ -f "$LIBDIR_BUILD/libimgproc.so" ] && cp "$LIBDIR_BUILD/libimgproc.so" "$OUT/lib/"

# 递归收集 .so 闭包（从 app 与 libimgproc.so 出发）
declare -A seen
collect() {
  local obj="$1" dep
  while read -r dep; do
    [ -z "$dep" ] && continue
    local base; base="$(basename "$dep")"
    [[ "$base" =~ $EXCLUDE_RE ]] && continue
    [ -n "${seen[$base]:-}" ] && continue
    seen[$base]=1
    [ -f "$dep" ] && cp -n "$dep" "$OUT/lib/" 2>/dev/null || true
    collect "$dep"
  done < <(LD_LIBRARY_PATH="$LIBDIR_BUILD" ldd "$obj" 2>/dev/null | awk '/=>/ {print $3}')
}
collect "$APP"
[ -f "$OUT/lib/libimgproc.so" ] && collect "$OUT/lib/libimgproc.so"

# 启动器：设 LD_LIBRARY_PATH 指向包内 lib，再 exec
cat > "$OUT/$NAME" <<'LAUNCH'
#!/bin/sh
DIR="$(cd "$(dirname "$0")" && pwd)"
LD_LIBRARY_PATH="$DIR/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec "$DIR/app" "$@"
LAUNCH
chmod +x "$OUT/$NAME"

tar czf "$ROOT/dist/$NAME.tar.gz" -C "$ROOT/dist" "$NAME"

echo "=== 完成 ==="
echo "  目录: $OUT"
echo "  压缩: $ROOT/dist/$NAME.tar.gz"
echo "  包内 .so: $(ls "$OUT/lib" | wc -l) 个"
ls "$OUT/lib"
