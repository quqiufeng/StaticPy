-- 示例：LuaJIT 调运行时（convert→grayscale→resize→save）
local dir = (arg and arg[0] and arg[0]:match("(.*[/\\])")) or "./"
package.path = dir .. "?.lua;" .. package.path
local P = require("imgproc")
local inp, outp = arg[1], arg[2]
if not inp or not outp then
  print("usage: luajit example.lua IN OUT")
  os.exit(1)
end
local im = P.open(inp)
assert(im ~= nil, "open failed: " .. tostring(inp))
local g = P.lib.img_grayscale(im)
local r = P.lib.img_resize(g, 120, 90, "lanczos")
local w, h = P.lib.img_width(r), P.lib.img_height(r)
P.lib.img_save(r, outp)
P.lib.img_free(im); P.lib.img_free(g); P.lib.img_free(r)
print(string.format("lua ok: %s (%dx%d) -> %s", inp, w, h, outp))
