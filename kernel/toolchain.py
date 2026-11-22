#!/usr/bin/env python3
# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""kernel.toolchain — Chez Scheme AOT 编译 + 独立 ELF 链接（纯 Python，无 shell 依赖）。"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile

LAUNCHER_C = r"""
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
"""


# 共享运行时模式：ELF 只有十几 KB，Chez 内核 + 引导文件字节都在 libstaticpyrt.so 里，
# 多个工具共用一份（默认开启；STATICPY_STATIC_RT=1 回到"每个 ELF 各自内嵌"的老行为）。
STUB_C = r"""
#include <stdio.h>

/* 由 libstaticpyrt.so 提供：初始化 Chez（全进程一次）+ 载入 <stem>.so */
extern int staticpy_run(const char *prog_path, int argc, char **argv);

int main(int argc, char **argv) {
    /* stem 在编译期烘死：ELF 可被改名（打包成 app），.so 名不变 */
    const char *stem = "CSTEM";
    static char prog_path[2048];
    const char *slash = NULL;
    if (argc >= 1 && argv[0]) slash = strrchr(argv[0], '/');
    if (slash && (size_t)(slash - argv[0]) + 1 < sizeof(prog_path)) {
        size_t n = (size_t)(slash - argv[0]) + 1;
        memcpy(prog_path, argv[0], n);
        prog_path[n] = 0;
        snprintf(prog_path + n, sizeof(prog_path) - n, "%s.so", stem);
    } else {
        snprintf(prog_path, sizeof(prog_path), "%s.so", stem);
    }
    return staticpy_run(prog_path, argc, argv);
}
"""

RT_C = r"""
#include <stdio.h>
#include "scheme.h"

extern char _binary_petite_boot_start[];
extern char _binary_petite_boot_end[];
extern char _binary_scheme_boot_start[];
extern char _binary_scheme_boot_end[];

static int inited = 0;

/* 多个工具共用一个进程内运行时也只初始化一次 */
int staticpy_run(const char *prog_path, int argc, char **argv) {
    if (!inited) {
        Sscheme_init(NULL);
        Sregister_boot_file_bytes("petite.boot",
            _binary_petite_boot_start,
            _binary_petite_boot_end - _binary_petite_boot_start);
        Sregister_boot_file_bytes("scheme.boot",
            _binary_scheme_boot_start,
            _binary_scheme_boot_end - _binary_scheme_boot_start);
        Sbuild_heap(NULL, NULL);
        inited = 1;
    }
    return Sscheme_program(prog_path, argc, (const char **)argv);
}
"""

# 机器宏（Chez 构建系统用 -D 传入，不从 config.h 推出）
ARCH_DEFINES = {
    "x86_64": "X86_64", "amd64": "X86_64",
    "i386": "I386", "i686": "I386",
    "aarch64": "AARCH64", "arm64": "AARCH64",
    "riscv64": "RISCV64",
    "loongarch64": "LOONGARCH64",
}


class ToolchainError(Exception):
    pass


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def shared_runtime_enabled():
    v = (os.environ.get("STATICPY_STATIC_RT") or "").strip().lower()
    return v in ("", "0", "false", "no")


def paths():
    chez_dir = os.environ.get("CHEZ_SCHEME_DIR", "/opt/ChezScheme/ta6le")
    scheme = os.environ.get("CHEZ_SCHEME", os.path.join(chez_dir, "bin/ta6le/scheme"))
    boot = os.environ.get("CHEZ_BOOT_DIR", "/opt/ChezScheme/boot/ta6le")
    if not os.access(scheme, os.X_OK):
        raise ToolchainError(f"找不到 Chez Scheme: {scheme}（设 CHEZ_SCHEME 或 CHEZ_SCHEME_DIR）")
    return chez_dir, scheme, boot


def cache_dir():
    # 与 static_build.sh 保持一致：默认 ~/iso_gen/staticpy-cache（不写 /tmp）
    d = os.environ.get("STATICPY_CACHE") or os.path.join(
        os.path.expanduser("~"), "iso_gen", "staticpy-cache")
    os.makedirs(d, exist_ok=True)
    return d


def hash_inputs(paths_):
    h = hashlib.md5()
    for p in paths_:
        try:
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(1 << 20)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError:
            h.update(b"<missing>")
        h.update(b"\0")
    return h.hexdigest()


def compile_bundle(bundle_ss, key, quiet=False):
    """Chez compile-file -> .so"""
    chez_dir, scheme, boot = paths()
    cd = cache_dir()
    out_so = os.path.join(cd, f"{key}.so")
    if os.path.isfile(out_so):
        return out_so
    drv = os.path.join(cd, f"compile_{key}.ss")
    with open(drv, "w") as f:
        f.write(f'(import (chezscheme))\n(compile-file "{bundle_ss}")\n')
    r = subprocess.run([scheme, "--quiet", drv], capture_output=True, text=True)
    if r.returncode != 0:
        raise ToolchainError("Chez 编译失败:\n" + (r.stdout or "") + (r.stderr or ""))
    produced = os.path.splitext(bundle_ss)[0] + ".so"
    if not os.path.isfile(produced):
        raise ToolchainError("Chez 没有产出 .so:\n" + (r.stdout or "") + (r.stderr or ""))
    shutil.move(produced, out_so)
    if not quiet:
        sys_stderr(f"  -> {out_so}")
    return out_so


def runtime_so(quiet=False):
    """构建/复用共享运行时 libstaticpyrt.so（Chez 内核 PIC 重编 + 引导文件字节）。

    落地在 <repo>/dist/libstaticpyrt.so。工具 ELF 只通过 DT_NEEDED + rpath 引用它，
    所以每个工具从 4.2MB 降到十几 KB（那 4.2MB 本来是同一份内容被复制 N 遍）。
    """
    import platform
    from concurrent.futures import ThreadPoolExecutor

    chez_dir, scheme, boot_dir = paths()
    cd = cache_dir()
    dist = os.path.join(repo_root(), "dist")
    os.makedirs(dist, exist_ok=True)
    link = os.path.join(dist, "libstaticpyrt.so")

    arch = ARCH_DEFINES.get(platform.machine().lower())
    if not arch:
        raise ToolchainError(f"未知架构 {platform.machine()}，无法构建共享运行时")

    src_dir = os.environ.get("CHEZ_SRC_DIR") or ""
    if not os.path.isfile(os.path.join(src_dir, "alloc.c")):
        src_dir = ""
        # 内核 .c 在 Chez 发行根目录的 c/（chez_dir 本身只放 ta6le/c 的 config.h 与 .o）
        for cand in (os.path.join(os.path.dirname(chez_dir.rstrip("/")), "c"),
                     os.path.join(chez_dir, "c")):
            if os.path.isfile(os.path.join(cand, "alloc.c")):
                src_dir = cand
                break
    kernel_a = os.path.join(chez_dir, "boot", "ta6le", "libkernel.a")
    if not src_dir or not os.path.isfile(kernel_a):
        raise ToolchainError(
            f"缺 Chez 内核源码（找 alloc.c）或 {kernel_a}；"
            "可用 STATICPY_STATIC_RT=1 退回静态内嵌")

    key = hash_inputs([os.path.join(boot_dir, "petite.boot"),
                       os.path.join(boot_dir, "scheme.boot"), kernel_a]) + arch
    work = os.path.join(cd, f"rt_{key[:12]}")
    built = os.path.join(work, "libstaticpyrt.so")

    if not os.path.isfile(built):
        os.makedirs(work, exist_ok=True)
        for b in ("petite.boot", "scheme.boot"):
            shutil.copy(os.path.join(boot_dir, b), os.path.join(work, b))
        for n in ("petite", "scheme"):
            for args in (["objcopy", "--input-target", "binary",
                          "--output-target", "elf64-x86-64",
                          "--binary-architecture", "i386:x86-64",
                          f"{n}.boot", f"{n}_boot.o"],
                         ["objcopy", "--add-section", ".note.GNU-stack=/dev/null",
                          "--set-section-flags", ".note.GNU-stack=readonly",
                          f"{n}_boot.o", f"{n}_boot.o"]):
                r = subprocess.run(args, cwd=work, capture_output=True, text=True)
                if r.returncode != 0:
                    raise ToolchainError(f"objcopy 失败: {r.stderr}")

        members = [m for m in subprocess.run(["ar", "t", kernel_a],
                                             capture_output=True, text=True).stdout.split()
                   if m.endswith(".o")]

        def cc(member):
            # Chez 的机器宏由构建系统 -D 传入（X86_64 等），不从 config.h 推导
            src = os.path.join(src_dir, os.path.splitext(member)[0] + ".c")
            r = subprocess.run(
                ["gcc", "-c", "-fPIC", "-O2", f"-D{arch}",
                 f"-I{boot_dir}", f"-I{src_dir}", f"-I{chez_dir}/c",
                 "-o", os.path.join(work, member), src],
                capture_output=True, text=True)
            if r.returncode != 0:
                raise ToolchainError(f"内核 {member} 编译失败:\n{r.stderr}")
            return member

        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as ex:
            objs = list(ex.map(cc, members))

        with open(os.path.join(work, "rt.c"), "w") as f:
            f.write(RT_C)
        r = subprocess.run(
            ["gcc", "-shared", "-fPIC", "-O2", f"-I{boot_dir}",
             "-Wl,-soname,libstaticpyrt.so", "-o", built,
             os.path.join(work, "rt.c"),
             *[os.path.join(work, o) for o in objs],
             os.path.join(work, "petite_boot.o"), os.path.join(work, "scheme_boot.o"),
             os.path.join(chez_dir, "lz4/lib/liblz4.a"),
             os.path.join(chez_dir, "zlib/libz.a"),
             "-ldl", "-lpthread", "-lm", "-ltinfo"],
            capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolchainError(f"共享运行时链接失败:\n{r.stderr}")

    if not os.path.isfile(link) or os.path.getsize(link) != os.path.getsize(built):
        shutil.copy(built, link)
    if not quiet:
        sys_stderr(f"  -> {link}  （共享运行时，所有工具复用这一份）")
    return link


def build_elf(so_path, stem, key, quiet=False):
    """链接工具 ELF：默认共享运行时；STATICPY_STATIC_RT=1 时恢复静态内嵌"""
    if shared_runtime_enabled():
        try:
            return _build_elf_shared(so_path, stem, key, quiet)
        except ToolchainError as e:
            sys_stderr(f"  !! 共享运行时不可用，退回静态内嵌：{e}")
    return _build_elf_static(so_path, stem, key, quiet)


def _build_elf_shared(so_path, stem, key, quiet=False):
    """十几 KB 的 stub：DT_NEEDED libstaticpyrt.so，rpath 覆盖同目录/lib/dist"""
    rt = runtime_so(quiet=True)
    cd = cache_dir()
    out_elf = os.path.join(cd, f"{stem}_{key}.rt")
    if os.path.isfile(out_elf):
        return out_elf
    work = os.path.join(cd, f"stub_{key}")
    os.makedirs(work, exist_ok=True)
    stub = os.path.join(work, "stub.c")
    with open(stub, "w") as f:
        f.write(STUB_C.replace("CSTEM", stem))
    rt_dir = os.path.dirname(rt)
    rpath = ":".join(["$ORIGIN", "$ORIGIN/lib", rt_dir, "/usr/local/lib"])
    r = subprocess.run(["gcc", "-O2", "-o", out_elf, stub,
                        f"-L{rt_dir}", "-lstaticpyrt", f"-Wl,-rpath,{rpath}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ToolchainError("ELF 链接失败（共享运行时）:\n" + r.stderr)
    if not quiet:
        sys_stderr(f"  -> {out_elf}")
    return out_elf


def _build_elf_static(so_path, stem, key, quiet=False):
    """把 boot 文件 + launcher + 编译产物 链接成独立 ELF"""
    chez_dir, scheme, boot_dir = paths()
    cd = cache_dir()
    out_elf = os.path.join(cd, f"{stem}_{key}")
    if os.path.isfile(out_elf):
        return out_elf
    work = os.path.join(cd, f"elf_{key}")
    os.makedirs(work, exist_ok=True)
    for b in ("petite.boot", "scheme.boot"):
        shutil.copy(os.path.join(boot_dir, b), os.path.join(work, b))

    def objcopy(args):
        r = subprocess.run(args, cwd=work, capture_output=True, text=True)
        if r.returncode != 0:
            raise ToolchainError(f"objcopy 失败: {r.stderr}")

    for name in ("petite", "scheme"):
        objcopy(["objcopy", "--input-target", "binary", "--output-target", "elf64-x86-64",
                 "--binary-architecture", "i386:x86-64", f"{name}.boot", f"{name}_boot.o"])
        objcopy(["objcopy", "--add-section", ".note.GNU-stack=/dev/null",
                 "--set-section-flags", ".note.GNU-stack=readonly", f"{name}_boot.o", f"{name}_boot.o"])

    launcher = os.path.join(work, "launcher.c")
    with open(launcher, "w") as f:
        f.write(LAUNCHER_C.replace("CSTEM", stem))

    sysroot = os.environ.get("GLIBC_SYSROOT", "")
    ldflags = []
    if sysroot:
        ldflags += [f"-L{sysroot}/lib", f"-L{sysroot}/lib/x86_64-linux-gnu",
                    f"-L{sysroot}/usr/lib/x86_64-linux-gnu",
                    f"-Wl,-rpath-link,{sysroot}/lib",
                    f"-Wl,-rpath-link,{sysroot}/lib/x86_64-linux-gnu",
                    f"-Wl,-rpath-link,{sysroot}/usr/lib/x86_64-linux-gnu"]

    cmd = ["gcc", "-o", out_elf, launcher, os.path.join(work, "petite_boot.o"),
           os.path.join(work, "scheme_boot.o"),
           f"-I{chez_dir}/boot/ta6le", f"-L{chez_dir}/boot/ta6le",
           "-l:libkernel.a", f"{chez_dir}/lz4/lib/liblz4.a", f"{chez_dir}/zlib/libz.a",
           "-ldl", "-lpthread", "-lm", "-ltinfo"] + ldflags
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ToolchainError("ELF 链接失败:\n" + r.stderr)
    if not quiet:
        sys_stderr(f"  -> {out_elf}")
    return out_elf


def sys_stderr(msg):
    import sys
    print(msg, file=sys.stderr, flush=True)
