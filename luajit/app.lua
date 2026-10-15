-- 内嵌 Lua 脚本：ffi.C 直接调「进程内的」运行时函数（libimgproc 已静态链入）
local ffi = require("ffi")
ffi.cdef[[
void* img_open(const char* path);
int   img_width(void* im);
int   img_height(void* im);
void* img_invert(void* im);
void* img_convert(void* im, const char* mode);
int   img_save(void* im, const char* path);
int   img_free(void* im);
]]
local inp, outp = arg[1], arg[2]
if not inp then io.write("usage: ./app IN OUT\n"); os.exit(1) end
local im = ffi.C.img_open(inp)
assert(im ~= nil, "open failed")
local w, h = ffi.C.img_width(im), ffi.C.img_height(im)
local out = ffi.C.img_invert(im)
ffi.C.img_save(out, outp)
ffi.C.img_free(im); ffi.C.img_free(out)
print(string.format("embedded-luajit ok: %dx%d -> %s", w, h, outp))
