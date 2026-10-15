;; imgproc_ffi.scm — 图像处理底层库 libimgproc.so 的运行时加载
;;
;; 作为 static_build 的第 3 个参数，拼接在 static_stdlib.scm 之后、用户代码之前。
;; 具体函数的 foreign-procedure 绑定由 static_translate.py 依据 .py 里的
;; `extern fn ... from "imgproc"` 自动生成；这里只负责在运行时把 .so 载入
;; （经 LD_LIBRARY_PATH 解析，见 imgproc/build.sh）。
(load-shared-object "libimgproc.so")
