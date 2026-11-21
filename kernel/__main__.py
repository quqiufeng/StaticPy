# [自举豁免 · 宿主] 本文件**故意**保留 CPython 实现，不提供 .static.py 版本。
# 它是编译链的启动器（argparse/subprocess/hashlib）：得先能跑起来才谈得上编译别人，
# 把自己自举进来是循环依赖。它只做编排，不产出 IR，也不进产物（AGENTS §4）。

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
