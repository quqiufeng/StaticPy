-- imgproc.lua — 用 LuaJIT ffi 直接调 libimgproc.so（与 StaticPy 共用同一份 C ABI）
-- 这就是"桥"：Lua <-> 运行时，靠 C ABI，零开销。
local ffi = require("ffi")

ffi.cdef[[
void* img_open(const char* path);
void* img_new(int w, int h);
void* img_copy(void* im);
int   img_free(void* im);
int   img_width(void* im);
int   img_height(void* im);
int   img_save(void* im, const char* path);
void* img_convert(void* im, const char* mode);
void* img_convert_p(void* im, int dither);
void* img_resize(void* im, int w, int h, const char* resample);
void* img_crop(void* im, int x, int y, int w, int h);
void* img_rotate(void* im, float deg, int expand, int fill);
void* img_transpose(void* im, int m);
void* img_mirror(void* im);
void* img_invert(void* im);
void* img_grayscale(void* im);
void* img_posterize(void* im, int bits);
void* img_autocontrast(void* im, int cutoff);
void* img_filter(void* im, const char* name, float r1, float r2, int i1);
void* img_quantize(void* im, int colors, int method);
void* img_blend(void* a, void* b, float alpha);
void* img_lut3d(void* im, const char* table_csv, int ch, int s1, int s2, int s3);
unsigned char* img_frame_ptr(void* im, int i);
int   img_frame_bpp(void* im, int i);
]]

local M = {}
M.lib = ffi.load(os.getenv("IMGPROC_SO") or "libimgproc.so")

-- 便捷：打开
function M.open(path) return M.lib.img_open(path) end
-- 便捷：就地变换并保存
function M.apply(inp, outp, fn)
  local im = M.open(inp)
  assert(im ~= nil, "open failed: "..inp)
  local out = fn(im)
  M.lib.img_save(out, outp)
  M.lib.img_free(im)
  if out ~= im then M.lib.img_free(out) end
  return true
end

return M
