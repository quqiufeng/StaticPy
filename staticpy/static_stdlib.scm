;; static_stdlib.scm — 精简默认标准库（空）。
;;
;; 说明：本文件被 static_build 无条件合并进每个产物。默认保持**最小**（零外部依赖）。
;; 原「全量扩展」（OpenBLAS/LAPACK/CUDA/curl/xgboost/lightgbm/onnx/libTorch/numpy/scipy…）
;; 已移到 static_stdlib_full.scm —— **按需选用**：
;;
;;   STATICPY_STDLIB=static_stdlib_full.scm bash staticpy/static_build_comfycli.sh app.static.py app
;;
;; 各扩展段均带 guard（库不存在则跳过），因此全量文件也不会强拉依赖；
;; 但默认不合并它，可让产物更小、依赖更明确（imgproc 仅用 static_prelude.scm）。
