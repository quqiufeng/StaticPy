;; lib_ffi.scm — libtorch C ABI（libtorch_capi.so）的运行时加载
;;
;; static_build 的第 3 个参数：拼在 stdlib 之后、用户代码之前。
;; `extern fn ... from "torchc"` 的 foreign-procedure 由翻译器自动生成，这里只负责 dlopen。
;; .so 自身用 rpath 指向 /opt/libtorch/lib（见 cpp/torch/build.sh）。
(load-shared-object "libtorch_capi.so")
