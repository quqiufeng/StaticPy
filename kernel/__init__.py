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
