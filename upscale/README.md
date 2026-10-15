# upscale —— 像素画高清放大（Scale2x/EPX）

游戏刚需：把低分辨率精灵无损放大（保持硬边、不糊）。确定性算法，**双实现验证**。

- **C 核心**：`../cpp/upscale/` → `libupscale.so`（Scale2x）
- **FFI / 前端**：`upscale_ffi.scm` + `up.static.py` → `up` ELF
- **验证**：`difftest.py` **20/20**（与独立 Python Scale2x 实现逐像素一致）

```bash
bash upscale/build.sh
LD_LIBRARY_PATH=cpp/upscale/build ./upscale/up 2x IN.png OUT.png
python3 upscale/difftest.py
```

> 照片级"高清修复/放大"（ESRGAN/SwinIR）属模型推理——本机无对应 ONNX，故走经典算法；有模型即可按 `tools/` 的方式接入。
