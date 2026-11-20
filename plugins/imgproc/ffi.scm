;; imgproc_ffi.scm — 图像处理底层库 libimgproc.so 的运行时加载
;;
;; 作为 static_build 的第 3 个参数，拼接在 static_stdlib.scm 之后、用户代码之前。
;; 具体函数的 foreign-procedure 绑定由内核依据 .py 里的
;; `extern fn ... from "imgproc"` 自动生成；`load-shared-object "libimgproc.so"`
;; 也由内核按 plugin.json 的 libs 映射自动挂在产物最前，这里不重复写。
;; 需要手写的绑定/常量表放这个文件。
