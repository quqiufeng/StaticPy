# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

"""StaticPy kernel — 只负责语言核心：词法/语法 → Scheme IR。

其余能力全部是插件（plugins/<name>/）：
  * syntax    : 语法扩展（hooks.py 注册 expr/stmt 处理器或源码重写）
  * runtime   : 运行时增强（runtime.scm，按 order 拼进产物）
  * ffi       : C 库封装（ffi.scm 声明 + manifest 里的 libs / build）

公共 API:
    from kernel import Kernel
    k = Kernel.discover()
    k.load(["core", "libc", "http"])
    k.merge_into(translator_module)
"""
from .plugin import Kernel, Plugin, PluginError, discover_dirs  # noqa: F401

__all__ = ["Kernel", "Plugin", "PluginError", "discover_dirs"]
__version__ = "1.0.0"
