;; sqlite_ffi.scm — libsqlite3 C ABI（libsqlitec.so）的运行时加载
;;
;; static_build 的第 3 个参数：拼在 stdlib 之后、用户代码之前。
;; `extern fn ... from "sqlitec"` 的 foreign-procedure 由翻译器自动生成，这里只负责 dlopen。
;; 运行时需要 LD_LIBRARY_PATH 指向 cpp/sqlite/build（build_app.sh 会把命令打出来）。
(load-shared-object "libsqlitec.so")
