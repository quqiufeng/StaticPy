# LuaJIT 集成 —— 通过 C ABI 桥调用运行时

libimgproc.so 的 **C ABI 是共享的运行时表面**：StaticPy（FFI）与 LuaJIT（`ffi.C`）调的是**同一份**。
LuaJIT 侧零开销、零胶水：

```lua
local ffi = require("ffi")
local imgproc = ffi.load("libimgproc.so")
ffi.cdef[[ void* img_open(const char*); void* img_grayscale(void*); int img_save(void*, const char*); ]]
```

运行（`.so` 经 `LD_LIBRARY_PATH` 或 `IMGPROC_SO` 解析）：

```bash
LD_LIBRARY_PATH=cpp/imgproc/build luajit luajit/example.lua IN.png OUT.png
```

> 意义：同一份运行时，Python(ctypes)/StaticPy/LuaJIT 三端共用；Lua 侧可把它当原生库直接用。

## 编译时编入（单文件 ELF）

```bash
bash luajit/embed-build.sh            # 静态链 LuaJIT + libimgproc 进一个 ELF
./lua_app IN.png OUT.png              # 内嵌脚本：ffi.C 调进程内运行时函数
```

产物 `lua_app` **不含动态 luajit 依赖**（已静态编入）；运行时函数经 `-rdynamic` 导出，
Lua 侧 `ffi.C.img_open(...)` 零开销直调。
