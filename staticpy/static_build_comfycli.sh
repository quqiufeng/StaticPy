#!/bin/bash
# static_build.sh — StaticPy 唯一构建入口（translate → Chez AOT → 独立 ELF）
#
# 用法:
#   bash staticpy/static_build_comfycli.sh <input.static.py|input.scm> [output-name] [ffi.scm]
#
# 环境变量:
#   CHEZ_SCHEME_DIR / CHEZ_SCHEME / CHEZ_BOOT_DIR  Chez 安装位置
#   STATICPY_CACHE   缓存目录（默认 ~/iso_gen/staticpy-cache）
#   STATICPY_OUTDIR  产物目录（默认 dist/，仅对“无路径前缀”的 output-name 生效）
#   STATICPY_STDLIB  合并的标准库（默认 static_stdlib.scm，可给 static_stdlib_full.scm）
#   STATICPY_PLUGINS 启用的插件（默认全部）
#   STATICPY_LIB=1   库模式：允许没有 main()，不生成 (static_main)
#   STATICPY_WARN=1  类型检查用 warn 模式
#   STATICPY_CACHE_KEEP  缓存保留条目数（默认 24）
#   GLIBC_SYSROOT    可选 sysroot，兼容老 glibc
#
# 后缀 .scm/.ss 视为已翻译的 Scheme，跳过翻译阶段。
# 产物：<outdir>/<stem>（ELF）与 <outdir>/<stem>.so（Chez AOT 代码）
set -euo pipefail

SCHEME_DIR="${CHEZ_SCHEME_DIR:-/opt/ChezScheme/ta6le}"
SCHEME="${CHEZ_SCHEME:-$SCHEME_DIR/bin/ta6le/scheme}"
SCHEME_BOOT_DIR="${CHEZ_BOOT_DIR:-/opt/ChezScheme/boot/ta6le}"
STATICPY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$STATICPY_DIR")"
PYTHON="${STATICPY_PYTHON:-python3}"
STDLIB="${STATICPY_STDLIB:-static_stdlib.scm}"
# 缓存不再写 /tmp（本项目约定：临时文件一律放 ~/iso_gen）
CACHE_DIR="${STATICPY_CACHE:-$HOME/iso_gen/staticpy-cache}"
CACHE_KEEP="${STATICPY_CACHE_KEEP:-24}"
LIB_MODE="${STATICPY_LIB:-0}"
# STATICPY_PROFILE=source|block → Scheme 层剖析构建（Chez compile-profile 插计数器）
PROFILE_MODE="${STATICPY_PROFILE:-}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <input.static.py|input.scm> [output-name] [ffi.scm]"
    echo "  STATICPY_CACHE=$CACHE_DIR   (缓存目录)"
    echo "  STATICPY_OUTDIR=dist        (裸名产物目录)"
    echo "  STATICPY_LIB=1              (库模式：无 main)"
    exit 1
fi
if [ "$1" = "--clean" ]; then
    rm -rf "$CACHE_DIR"
    echo "cleaned cache: $CACHE_DIR"
    exit 0
fi
if [ ! -x "$SCHEME" ]; then
    echo "Error: Chez Scheme not found at $SCHEME"
    echo "Set CHEZ_SCHEME_DIR or CHEZ_SCHEME."
    exit 1
fi

# --- 绝对路径（脚本随后会 cd 到 staticpy/） --------------------------------
abspath() { local d; d="$(cd "$(dirname "$1")" && pwd)"; echo "$d/$(basename "$1")"; }
INPUT="$(abspath "$1")"
STEM="${2:-$(basename "$INPUT" .py)}"
STEM="${STEM%.static.py}"
STEM="${STEM%.py}"
FFI_SCM=""
[ -n "${3:-}" ] && FFI_SCM="$(abspath "$3")"

# 产物落点：带路径前缀（imgproc/pil）沿用原语义；裸名进 dist/
OUTDIR=""
if [ -n "${STATICPY_OUTDIR:-}" ] || [ "${STEM#*/}" = "$STEM" ]; then
    OUTDIR="${STATICPY_OUTDIR:-$PROJECT_DIR/dist}"
    # 相对路径按**调用者 cwd** 解析（脚本随后会 cd 到 staticpy/，相对路径会跑偏）
    case "$OUTDIR" in
        /*) ;;
        *) OUTDIR="$(pwd)/$OUTDIR" ;;
    esac
    mkdir -p "$OUTDIR"
    OUTPUT_BASE="$OUTDIR/$(basename "$STEM")"
else
    OUTPUT_BASE="$PROJECT_DIR/$STEM"
    mkdir -p "$(dirname "$OUTPUT_BASE")"
fi
STEM_BASE="$(basename "$STEM")"

mkdir -p "$CACHE_DIR"
cd "$STATICPY_DIR"

echo "=== StaticPy Build ==="
echo "Source: $INPUT"
echo "Output: $OUTPUT_BASE (+ .so)"
echo "Cache:  $CACHE_DIR"

INPUT_EXT="${INPUT##*.}"
IS_SCM=0
if [ "$INPUT_EXT" = "scm" ] || [ "$INPUT_EXT" = "ss" ]; then IS_SCM=1; fi

# --- 输入指纹：所有**影响产物**的输入都进 hash（含插件与内核） ------------
fingerprint() {
    local files=()
    if [ "$IS_SCM" = "1" ]; then
        files+=("$INPUT" "$STATICPY_DIR/static_prelude.scm" "$STATICPY_DIR/$STDLIB")
    else
        files+=("$INPUT" "$STATICPY_DIR/static_translate.py"
                "$STATICPY_DIR/static_prelude.scm" "$STATICPY_DIR/$STDLIB")
    fi
    [ -n "$FFI_SCM" ] && [ -f "$FFI_SCM" ] && files+=("$FFI_SCM")
    # 插件（语法重写 + 运行时 .scm/.py）与内核：改了插件必须重编，不能命中旧 .so
    files+=($(find "$PROJECT_DIR/plugins" "$PROJECT_DIR/kernel" \
                -type f \( -name '*.py' -o -name '*.scm' -o -name '*.lua' \) 2>/dev/null | sort))
    [ -f "$STATICPY_DIR/static_prof.scm" ] && files+=("$STATICPY_DIR/static_prof.scm")
    {
        echo "STATICPY_STDLIB=$STDLIB"
        echo "STATICPY_PLUGINS=${STATICPY_PLUGINS:-}"
        echo "STATICPY_LIB=$LIB_MODE"
        echo "STATICPY_PROFILE=$PROFILE_MODE"
        echo "STATICPY_PGO=${STATICPY_PGO:-0}"
        echo "STATICPY_OPT_LEVEL=${STATICPY_OPT_LEVEL:-3}"
        echo "STATICPY_DEBUG_LEVEL=${STATICPY_DEBUG_LEVEL:-}"
        echo "STATICPY_MAXGEN=${STATICPY_MAXGEN:-1}"
        md5sum "${files[@]}" 2>/dev/null
    } | md5sum | cut -d' ' -f1
}

BUILD_HASH="$(fingerprint)"
CACHED_SO="$CACHE_DIR/${STEM_BASE}_${BUILD_HASH}.so"
CACHED_ELF="$CACHE_DIR/${STEM_BASE}_${BUILD_HASH}"

prune_cache() {
    # 只保留最近的 N 个顶层条目（文件与 elf_* 目录），避免缓存无限膨胀
    local victims
    # boot_* 与 launcher 是跨产物复用的公共件，不参与淘汰
    victims=$(ls -1dt "$CACHE_DIR"/* 2>/dev/null \
        | grep -v '/boot_' \
        | tail -n +$((CACHE_KEEP + 1)) || true)
    if [ -n "$victims" ]; then echo "$victims" | xargs -r rm -rf; fi
    return 0
}

if [ -f "$CACHED_ELF" ] && [ -f "$CACHED_SO" ]; then
    echo ">>> Cached (hash ${BUILD_HASH:0:12}), skip translate+compile"
else
    # --- Step 1: 翻译 -----------------------------------------------------
    echo ">>> Step 1: Translate"
    CODE_SS="$CACHE_DIR/${STEM_BASE}_${BUILD_HASH}.code.ss"
    if [ "$IS_SCM" = "1" ]; then
        echo "  -> input is Scheme, skip translation"
        cp "$INPUT" "$CODE_SS"
    else
        TRANSLATE_ARGS=()
        [ "${STATICPY_WARN:-0}" = "1" ] && TRANSLATE_ARGS+=(--warn)
        [ "$LIB_MODE" = "1" ] && TRANSLATE_ARGS+=(--lib)
        [ -n "${STATICPY_PLUGINS:-}" ] && TRANSLATE_ARGS+=(--plugins "$STATICPY_PLUGINS")
        "$PYTHON" static_translate.py "${TRANSLATE_ARGS[@]}" "$INPUT" > "$CODE_SS"
    fi

    # --- Step 2: Chez AOT -------------------------------------------------
    echo ">>> Step 2: Compile (Chez AOT)"
    MERGED_SS="$CACHE_DIR/${STEM_BASE}_${BUILD_HASH}.ss"
    # 插件 runtime（plugin.json 的 "runtime"）：按 Kernel 的拓扑顺序拼在 prelude 之后
    PLUGIN_SCM_LIST=""
    if [ -n "${STATICPY_PLUGINS:-}" ]; then
        PLUGIN_SCM_LIST=$(cd "$PROJECT_DIR" && "$PYTHON" - "$STATICPY_PLUGINS" <<'PYEOF'
import sys
from kernel.plugin import Kernel
k = Kernel.discover()
k.resolve([n for n in sys.argv[1].split(',') if n])
for name, path in k.runtime_files():
    print(path)
PYEOF
)
    fi
    # GC 代际调优：产物多为「短命堆型」CLI（解析-发射-退出），
    # 默认 maxgen 4 会把存活数据逐代复制 4 次；降到 1（Chez 允许的最小值）
    # 实测自举翻译器 n5 输入 1.47s → 1.23s（-16%），t3 输入 0.41s → 0.31s。
    # STATICPY_MAXGEN=default 回退 Chez 默认；=2/3 取中间值。
    MAXGEN="${STATICPY_MAXGEN:-1}"
    GC_TUNE=""
    if [ -n "$MAXGEN" ] && [ "$MAXGEN" != "default" ]; then
        GC_TUNE="(collect-maximum-generation $MAXGEN)"
    fi
    {
        if [ -n "$GC_TUNE" ]; then printf '%s\n' "$GC_TUNE"; fi
        cat static_prelude.scm; echo
        cat "$STDLIB"; echo
        if [ -n "$PROFILE_MODE" ] && [ -f static_prof.scm ]; then
            # Scheme 层剖析运行时：报告函数 + 本次 merged.ss 的路径（供 sprof 反查源码行）
            cat static_prof.scm; echo
            printf '(define static-merged-ss "%s")\n' "$MERGED_SS"
            printf '(define static-prof-baked-mode "%s")\n' "$PROFILE_MODE"
        fi
        if [ -n "$FFI_SCM" ] && [ -f "$FFI_SCM" ]; then cat "$FFI_SCM"; echo; fi
        for pscm in $PLUGIN_SCM_LIST; do cat "$pscm"; echo; done
        cat "$CODE_SS"
        # 入口跑完再落盘；库模式（无 static_main）不插
        if [ -n "$PROFILE_MODE" ] && [ "$LIB_MODE" != "1" ]; then
            echo; echo ";; -- profiling: 落盘表达式执行计数 --"; echo "(static-prof-report)"
        fi
    } > "$MERGED_SS"

    # Chez 编译优化级别。默认 3（更激进的 copy propagation / inline）：
    # 本仓库自举翻译器实测 n5 输入 1.79s → 1.49s（-17%），IR 与 opt2 逐字节一致。
    # STATICPY_OPT_LEVEL=0/1/2 可回退；STATICPY_DEBUG_LEVEL=0 再去掉源码信息可再快 ~5%。
    OPT_FORMS=""
    OPT_LV="${STATICPY_OPT_LEVEL:-3}"
    if [ "$OPT_LV" != "0" ] && [ "$OPT_LV" != "none" ]; then
        OPT_FORMS="(optimize-level ${OPT_LV})\n"
        if [ -n "${STATICPY_DEBUG_LEVEL:-}" ]; then
            OPT_FORMS="${OPT_FORMS}(debug-level ${STATICPY_DEBUG_LEVEL})\n"
        fi
    fi
    if [ -n "$PROFILE_MODE" ]; then
        # 列好编译驱动：可选 PGO 回灌（把上一轮 block 画像喂回编译器）再编译
        {
            echo '(import (chezscheme))'
            PD_FILE="${STATICPY_PD:-$HOME/iso_gen/prof/${STEM_BASE}.pd}"
            if [ "${STATICPY_PGO:-0}" = "1" ] && [ -f "$PD_FILE" ]; then
                echo ";; PGO: 回灌 block 画像 $PD_FILE"
                printf '(profile-load-data "%s")\n' "$PD_FILE"
            fi
            printf "$OPT_FORMS"
            printf '(compile-profile (quote %s))\n' "$PROFILE_MODE"
            printf '(compile-file "%s")\n' "$MERGED_SS"
        } > "$CACHE_DIR/compile_${BUILD_HASH}.ss"
    else
        { printf '(import (chezscheme))\n'; printf "$OPT_FORMS"; \
          printf '(compile-file "%s")\n' "$MERGED_SS"; } \
            > "$CACHE_DIR/compile_${BUILD_HASH}.ss"
    fi
    $SCHEME --quiet "$CACHE_DIR/compile_${BUILD_HASH}.ss" 2>&1
    # Chez 把 foo.ss 编到 foo.so（就是 CACHED_SO 本身）；缺了说明编译失败
    if [ ! -f "$CACHED_SO" ]; then
        echo "Error: Chez compile-file 未产出 $CACHED_SO" >&2
        exit 1
    fi

    # --- Step 3: 独立 ELF -------------------------------------------------
    echo ">>> Step 3: Link standalone ELF"
    # 默认走共享运行时：ELF 只留十几 KB，Chez 内核 + boot 字节都在 dist/libstaticpyrt.so
    # STATICPY_STATIC_RT=1 回到「每个 ELF 各自内嵌一份 4.2MB」的老行为
    RT_SO=""
    if [ -z "${STATICPY_STATIC_RT:-}" ] && [ "${STATICPY_SHARED_RT:-1}" != "0" ]; then
        RT_SO="$(cd "$PROJECT_DIR" && "$PYTHON" - <<'PYEOF' 2>/dev/null
import sys
from kernel.toolchain import runtime_so
try:
    print(runtime_so(quiet=True))
except Exception:
    print("")
PYEOF
)"
    fi

    if [ -n "$RT_SO" ] && [ -f "$RT_SO" ]; then
        STUB_C="$CACHE_DIR/stub_${BUILD_HASH}.c"
        cat > "$STUB_C" << 'CCODE'
#include <stdio.h>
#include <string.h>

/* 由 libstaticpyrt.so 提供：初始化 Chez（全进程一次）+ 载入 prog_path */
extern int staticpy_run(const char *prog_path, int argc, char **argv);

int main(int argc, char **argv) {
    /* stem 编译期烘死：ELF 可被改名（打包成 app），同名 .so 不变 */
    const char *stem = "CSTEM";
    static char prog_path[2048];
    const char *slash = NULL;
    if (argc >= 1 && argv[0]) slash = strrchr(argv[0], '/');
    if (slash && (size_t)(slash - argv[0]) + 1 < sizeof prog_path) {
        size_t n = (size_t)(slash - argv[0]) + 1;
        memcpy(prog_path, argv[0], n);
        prog_path[n] = 0;
        snprintf(prog_path + n, sizeof prog_path - n, "%s.so", stem);
    } else {
        snprintf(prog_path, sizeof prog_path, "%s.so", stem);
    }
    return staticpy_run(prog_path, argc, argv);
}
CCODE
        STUB_FIXED="${STUB_C%.c}_fixed.c"
        sed "s|CSTEM|$STEM_BASE|g" "$STUB_C" > "$STUB_FIXED"
        RT_DIR="$(dirname "$RT_SO")"
        gcc -O2 -o "$CACHED_ELF" "$STUB_FIXED" -L"$RT_DIR" -lstaticpyrt \
            -Wl,-rpath,"\$ORIGIN:\$ORIGIN/lib:$RT_DIR:/usr/local/lib"
        echo "  -> built (hash ${BUILD_HASH:0:12})  [shared rt: $(basename "$RT_SO")]"
        prune_cache
    else
    # --- 静态内嵌后备路径（无内核源码 / 显式 STATICPY_STATIC_RT=1）---
    BOOT_HASH="$(md5sum "$SCHEME_BOOT_DIR/petite.boot" "$SCHEME_BOOT_DIR/scheme.boot" | md5sum | cut -d' ' -f1)"
    BOOT_DIR="$CACHE_DIR/boot_${BOOT_HASH:0:12}"
    if [ ! -f "$BOOT_DIR/.stamp" ]; then
        # boot 文件与产物无关，跨 build hash 复用（只做一次 objcopy）
        echo "  -> objcopy boot files (once per Chez install)"
        rm -rf "$BOOT_DIR"; mkdir -p "$BOOT_DIR"
        cp "$SCHEME_BOOT_DIR/petite.boot" "$SCHEME_BOOT_DIR/scheme.boot" "$BOOT_DIR/"
        ( cd "$BOOT_DIR" && \
          objcopy --input-target binary --output-target elf64-x86-64 --binary-architecture i386:x86-64 \
            petite.boot petite_boot.o && \
          objcopy --input-target binary --output-target elf64-x86-64 --binary-architecture i386:x86-64 \
            scheme.boot scheme_boot.o && \
          objcopy --add-section .note.GNU-stack=/dev/null --set-section-flags .note.GNU-stack=readonly \
            petite_boot.o petite_boot.o && \
          objcopy --add-section .note.GNU-stack=/dev/null --set-section-flags .note.GNU-stack=readonly \
            scheme_boot.o scheme_boot.o && \
          touch .stamp )
    fi

    LAUNCHER="$CACHE_DIR/launcher_${BUILD_HASH}.c"
    cat > "$LAUNCHER" << 'CCODE'
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
    sed "s|CSTEM|$STEM_BASE|g" "$LAUNCHER" > "${LAUNCHER%.c}_fixed.c"

    GLIBC_LDFLAGS=()
    if [ -n "${GLIBC_SYSROOT:-}" ]; then
        GLIBC_LDFLAGS+=("-L$GLIBC_SYSROOT/lib" "-L$GLIBC_SYSROOT/lib/x86_64-linux-gnu"
                        "-L$GLIBC_SYSROOT/usr/lib/x86_64-linux-gnu"
                        "-Wl,-rpath-link,$GLIBC_SYSROOT/lib"
                        "-Wl,-rpath-link,$GLIBC_SYSROOT/lib/x86_64-linux-gnu"
                        "-Wl,-rpath-link,$GLIBC_SYSROOT/usr/lib/x86_64-linux-gnu")
    fi

    gcc -o "$CACHED_ELF" \
        "${LAUNCHER%.c}_fixed.c" \
        "$BOOT_DIR/petite_boot.o" "$BOOT_DIR/scheme_boot.o" \
        -I"$SCHEME_DIR/boot/ta6le" -L"$SCHEME_DIR/boot/ta6le" \
        -l:libkernel.a \
        "$SCHEME_DIR/lz4/lib/liblz4.a" \
        "$SCHEME_DIR/zlib/libz.a" \
        -ldl -lpthread -lm -ltinfo \
        "${GLIBC_LDFLAGS[@]}"

    echo "  -> built (hash ${BUILD_HASH:0:12})"
    prune_cache
    fi
fi

# --- Step 4: 发布到输出目录 ------------------------------------------------
# --- Step 3.5: 记账（不 gate，只留证据）-----------------------------------
# 目的：让「换掉后端看差分会不会红」这类验证将来可复现。
# 没有它，Chez/gcc 的版本就是传闻；有了它，谁都能拿同一组版本重跑。
{
    printf '{\n'
    printf '  "product": "%s",\n' "$(basename "$OUTPUT_BASE")"
    printf '  "built_at": "%s",\n' "$(date -Iseconds)"
    printf '  "chez_version": "%s",\n' "$("$SCHEME" --version 2>/dev/null | head -1 || echo unknown)"
    printf '  "chez_dir": "%s",\n' "$SCHEME_DIR"
    printf '  "chez_boot_md5": "%s",\n' "${BOOT_HASH:-unknown}"
    printf '  "gcc_version": "%s",\n' "$(gcc -dumpfullversion 2>/dev/null || echo unknown)"
    printf '  "build_inputs_md5": "%s"\n' "${BUILD_HASH:-unknown}"
    printf '}\n'
} > "$OUTPUT_BASE.build-info.json"

cp -L "$CACHED_SO" "$OUTPUT_BASE.so"
cp -L "$CACHED_ELF" "$OUTPUT_BASE"
chmod +x "$OUTPUT_BASE"
touch "$CACHED_ELF" "$CACHED_SO"   # 供 LRU 判定“最近使用”

echo "=== Build complete ==="
echo "  $OUTPUT_BASE       (ELF binary)"
echo "  $OUTPUT_BASE.so    (Chez AOT compiled Scheme)"
echo "  $OUTPUT_BASE.build-info.json  (chez/gcc 版本 + boot 指纹)"
