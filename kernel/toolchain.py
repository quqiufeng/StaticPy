#!/usr/bin/env python3
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


class ToolchainError(Exception):
    pass


def paths():
    chez_dir = os.environ.get("CHEZ_SCHEME_DIR", "/opt/ChezScheme/ta6le")
    scheme = os.environ.get("CHEZ_SCHEME", os.path.join(chez_dir, "bin/ta6le/scheme"))
    boot = os.environ.get("CHEZ_BOOT_DIR", "/opt/ChezScheme/boot/ta6le")
    if not os.access(scheme, os.X_OK):
        raise ToolchainError(f"找不到 Chez Scheme: {scheme}（设 CHEZ_SCHEME 或 CHEZ_SCHEME_DIR）")
    return chez_dir, scheme, boot


def cache_dir():
    # 与 static_build_comfycli.sh 保持一致：默认 ~/iso_gen/staticpy-cache（不写 /tmp）
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


def build_elf(so_path, stem, key, quiet=False):
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
