;; tools_ffi.scm — 运行时加载图像/视觉工具（C++ 库，均走 ONNX Runtime）
(load-shared-object "libface.so")
(load-shared-object "libbirefnet.so")
(load-shared-object "libocr.so")
(load-shared-object "libflorence2.so")
