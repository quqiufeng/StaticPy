#!/bin/bash
# static_build_comfycli.sh — ComfyCLI 本地构建脚本（基于上游 StaticPy 工具链）
#
# 与上游 static_build.sh 的差异（上游版硬编码 /opt/ReScheme 且链接 torch）：
#   - 使用本项目 staticpy/ 目录下的编译器文件（上游原样拷贝，未改）
#   - 不链接 torch（sd.cpp 后端无需）
#   - 支持 GLIBC_SYSROOT 兼容编译
#   - 产物输出到项目根目录
#
# 用法:
#   bash staticpy/static_build_comfycli.sh <input.py> <output-name> [ffi.scm]
set -euo pipefail

SCHEME_DIR="${CHEZ_SCHEME_DIR:-/opt/ChezScheme/ta6le}"
SCHEME="${CHEZ_SCHEME:-$SCHEME_DIR/bin/ta6le/scheme}"
SCHEME_BOOT_DIR="${CHEZ_BOOT_DIR:-/opt/ChezScheme/boot/ta6le}"
STATICPY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$STATICPY_DIR")"
CACHE_DIR="/tmp/staticpy-cache"
PYTHON="${STATICPY_PYTHON:-python3}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 input.py [output-name] [ffi.scm]"
    exit 1
fi
if [ ! -x "$SCHEME" ]; then
    echo "Error: Chez Scheme not found at $SCHEME"
    exit 1
fi

# 解析为绝对路径（脚本随后会 cd 到 staticpy/）
INPUT="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
STEM="${2:-$(basename "$INPUT" .py)}"
FFI_SCM=""
if [ -n "${3:-}" ]; then
    FFI_SCM="$(cd "$(dirname "$3")" && pwd)/$(basename "$3")"
fi
mkdir -p "$CACHE_DIR"
cd "$STATICPY_DIR"

echo "=== StaticPy Build (ComfyCLI) ==="
echo "Source: $INPUT"
echo "Output: $PROJECT_DIR/$STEM"
echo "Chez:   $SCHEME"

INPUT_EXT="${INPUT##*.}"
IS_SCM=0
[ "$INPUT_EXT" = "scm" ] || [ "$INPUT_EXT" = "ss" ] && IS_SCM=1

# Step 1: Translate
echo ">>> Step 1: Translate"
if [ "$IS_SCM" = "1" ]; then
    echo "  -> Input is Scheme code, skipping translation"
    cp "$INPUT" "$CACHE_DIR/${STEM}_code.ss"
else
    if [ "${STATICPY_WARN:-0}" = "1" ]; then
        "$PYTHON" static_translate.py --warn "$INPUT" > "$CACHE_DIR/${STEM}_code.ss"
    else
        "$PYTHON" static_translate.py "$INPUT" > "$CACHE_DIR/${STEM}_code.ss"
    fi
fi

# Step 2: content hash for caching
if [ "$IS_SCM" = "1" ]; then
    HASH_INPUTS=(static_prelude.scm static_stdlib.scm "$CACHE_DIR/${STEM}_code.ss")
else
    HASH_INPUTS=(static_prelude.scm static_stdlib.scm static_translate.py "$CACHE_DIR/${STEM}_code.ss")
fi
[ -n "$FFI_SCM" ] && HASH_INPUTS+=("$FFI_SCM")
PRELUDE_HASH=$(md5sum "${HASH_INPUTS[@]}" 2>/dev/null | md5sum | cut -d' ' -f1)
CACHED_SO="$CACHE_DIR/${STEM}_${PRELUDE_HASH}.so"
CACHED_ELF="$CACHE_DIR/${STEM}_${PRELUDE_HASH}"

if [ -f "$CACHED_ELF" ] && [ -f "$CACHED_SO" ]; then
    echo ">>> Step 2: Cached, skip compile"
    OUTPUT_SO="$CACHED_SO"
    OUTPUT_ELF="$CACHED_ELF"
else
    echo ">>> Step 2: Compile"
    MERGED_SS="$CACHE_DIR/${STEM}_${PRELUDE_HASH}.ss"
    cat static_prelude.scm > "$MERGED_SS"
    echo "" >> "$MERGED_SS"
    cat static_stdlib.scm >> "$MERGED_SS"
    echo "" >> "$MERGED_SS"
    if [ -n "$FFI_SCM" ] && [ -f "$FFI_SCM" ]; then
        cat "$FFI_SCM" >> "$MERGED_SS"
        echo "" >> "$MERGED_SS"
    fi
    cat "$CACHE_DIR/${STEM}_code.ss" >> "$MERGED_SS"

    cat > "$CACHE_DIR/compile_${PRELUDE_HASH}.ss" << EOF
(import (chezscheme))
(compile-file "$MERGED_SS")
EOF
    $SCHEME --quiet "$CACHE_DIR/compile_${PRELUDE_HASH}.ss" 2>&1
    mv "${MERGED_SS}.so" "$CACHED_SO" 2>/dev/null || true

    # Step 3: standalone ELF
    echo ">>> Step 3: Build standalone ELF binary"
    BUILD_DIR="$CACHE_DIR/elf_${PRELUDE_HASH}"
    rm -rf "$BUILD_DIR"
    mkdir -p "$BUILD_DIR"

    cp "$SCHEME_BOOT_DIR/petite.boot" "$BUILD_DIR/petite.boot"
    cp "$SCHEME_BOOT_DIR/scheme.boot" "$BUILD_DIR/scheme.boot"
    (cd "$BUILD_DIR" && \
      objcopy --input-target binary --output-target elf64-x86-64 --binary-architecture i386:x86-64 \
        petite.boot petite_boot.o && \
      objcopy --input-target binary --output-target elf64-x86-64 --binary-architecture i386:x86-64 \
        scheme.boot scheme_boot.o && \
      objcopy --add-section .note.GNU-stack=/dev/null --set-section-flags .note.GNU-stack=readonly \
        petite_boot.o petite_boot.o && \
      objcopy --add-section .note.GNU-stack=/dev/null --set-section-flags .note.GNU-stack=readonly \
        scheme_boot.o scheme_boot.o)

    cat > "$BUILD_DIR/launcher.c" << 'CCODE'
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "scheme.h"

extern char _binary_petite_boot_start[];
extern char _binary_petite_boot_end[];
extern char _binary_scheme_boot_start[];
extern char _binary_scheme_boot_end[];

int main(int argc, char **argv) {
    Sscheme_init(NULL);
    Sregister_boot_file_bytes("petite.boot",
        _binary_petite_boot_start,
        _binary_petite_boot_end - _binary_petite_boot_start);
    Sregister_boot_file_bytes("scheme.boot",
        _binary_scheme_boot_start,
        _binary_scheme_boot_end - _binary_scheme_boot_start);
    Sbuild_heap(NULL, NULL);

    char *prog_path = "CSTEM.so";
    char self_path[2048];
    if (argc >= 1 && argv[0]) {
        char *slash = strrchr(argv[0], '/');
        if (slash) {
            size_t dir_len = slash - argv[0] + 1;
            if (dir_len < sizeof(self_path)) {
                memcpy(self_path, argv[0], dir_len);
                self_path[dir_len] = '\0';
                strncat(self_path, "CSTEM.so", sizeof(self_path) - dir_len - 1);
                prog_path = self_path;
            }
        }
    }

    return Sscheme_program(prog_path, argc, (const char **)argv);
}
CCODE
    CSTEM_BASE="$(basename "$STEM")"
    sed "s|CSTEM|$CSTEM_BASE|g" "$BUILD_DIR/launcher.c" > "$BUILD_DIR/launcher_fixed.c"

    # GLIBC 兼容：可选 sysroot 链接
    GLIBC_SYSROOT="${GLIBC_SYSROOT:-}"
    GLIBC_LDFLAGS=()
    if [ -n "$GLIBC_SYSROOT" ]; then
        GLIBC_LDFLAGS+=("-L$GLIBC_SYSROOT/lib")
        GLIBC_LDFLAGS+=("-L$GLIBC_SYSROOT/lib/x86_64-linux-gnu")
        GLIBC_LDFLAGS+=("-L$GLIBC_SYSROOT/usr/lib/x86_64-linux-gnu")
        GLIBC_LDFLAGS+=("-Wl,-rpath-link,$GLIBC_SYSROOT/lib")
        GLIBC_LDFLAGS+=("-Wl,-rpath-link,$GLIBC_SYSROOT/lib/x86_64-linux-gnu")
        GLIBC_LDFLAGS+=("-Wl,-rpath-link,$GLIBC_SYSROOT/usr/lib/x86_64-linux-gnu")
    fi

    gcc -o "$CACHED_ELF" \
        "$BUILD_DIR/launcher_fixed.c" \
        "$BUILD_DIR/petite_boot.o" \
        "$BUILD_DIR/scheme_boot.o" \
        -I"$SCHEME_DIR/boot/ta6le" \
        -L"$SCHEME_DIR/boot/ta6le" \
        -l:libkernel.a \
        "$SCHEME_DIR/lz4/lib/liblz4.a" \
        "$SCHEME_DIR/zlib/libz.a" \
        -ldl -lpthread -lm -ltinfo \
        "${GLIBC_LDFLAGS[@]}" \
        2>&1

    echo "  -> ELF cached"
    OUTPUT_SO="$CACHED_SO"
    OUTPUT_ELF="$CACHED_ELF"
fi

# Step 4: copy outputs to project root
cp -L "$OUTPUT_SO" "$PROJECT_DIR/$STEM.so"
cp -L "$OUTPUT_ELF" "$PROJECT_DIR/$STEM"

echo "=== Build complete ==="
echo "  $PROJECT_DIR/$STEM       (ELF binary)"
echo "  $PROJECT_DIR/$STEM.so    (Chez AOT compiled Scheme)"
