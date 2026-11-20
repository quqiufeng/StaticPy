

;; ============================================================
;; Part 1: OpenBLAS (numpy 底层) — 可选加载，不可用时跳过
;; ============================================================
(define *openblas-available* #f)
(call-with-current-continuation
  (lambda (return)
    (with-exception-handler
      (lambda (e) #f (return))
      (lambda ()
        (load-shared-object "libopenblas.so.0")
        (set! *openblas-available* #t)))))

(define cblas-sdot  #f)
(define cblas-ddot  #f)
(define cblas-saxpy #f)
(define cblas-daxpy #f)
(define cblas-scopy #f)
(define cblas-dcopy #f)
(define cblas-sscal #f)
(define cblas-dscal #f)
(define cblas-sgemv #f)
(define cblas-dgemv #f)
(define cblas-sgemm #f)
(define cblas-dgemm #f)

(when *openblas-available*
  (set! cblas-sdot  (foreign-procedure "cblas_sdot" (int void* int void* int) float))
  (set! cblas-ddot  (foreign-procedure "cblas_ddot" (int void* int void* int) double))
  (set! cblas-saxpy (foreign-procedure "cblas_saxpy" (int float void* int void* int) void))
  (set! cblas-daxpy (foreign-procedure "cblas_daxpy" (int double void* int void* int) void))
  (set! cblas-scopy (foreign-procedure "cblas_scopy" (int void* int void* int) void))
  (set! cblas-dcopy (foreign-procedure "cblas_dcopy" (int void* int void* int) void))
  (set! cblas-sscal (foreign-procedure "cblas_sscal" (int float void* int) void))
  (set! cblas-dscal (foreign-procedure "cblas_dscal" (int double void* int) void))
  (set! cblas-sgemv (foreign-procedure "cblas_sgemv" (int int int float void* int void* int float void* int) void))
  (set! cblas-dgemv (foreign-procedure "cblas_dgemv" (int int int double void* int void* int double void* int) void))
  (set! cblas-sgemm (foreign-procedure "cblas_sgemm" (int int int int int int float void* int void* int float void* int) void))
  (set! cblas-dgemm (foreign-procedure "cblas_dgemm" (int int int int int int double void* int void* int double void* int) void)))
