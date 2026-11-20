
;; ============================================================
;; Part 10: ONNX Runtime — 模型推理部署
;; ============================================================
(define *onnx-available* #f)
(call-with-current-continuation
  (lambda (return)
    (with-exception-handler
      (lambda (e) #f (return))
      (lambda ()
        (load-shared-object "libonnxruntime.so")
        (set! *onnx-available* #t)))))

(define onnx-create-session #f)
(define onnx-run #f)

(when *onnx-available*
  (call-with-current-continuation
    (lambda (return)
      (with-exception-handler
        (lambda (e) #f (return))
        (lambda ()
          (set! onnx-create-session (foreign-procedure "OrtCreateSession"
            (void* string void* void*) int))
          (set! onnx-run (foreign-procedure "OrtRun"
            (void* void* void* void* int void* void* int) int)))))))
