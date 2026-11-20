
;; ============================================================
;; Part 2: LAPACK — 可选加载
;; ============================================================
(define *lapack-available* #f)
(call-with-current-continuation
  (lambda (return)
    (with-exception-handler
      (lambda (e) #f (return))
      (lambda ()
        (load-shared-object "liblapacke.so.3")
        (set! *lapack-available* #t)))))

(define lapack-dgesv  #f)
(define lapack-sgesv  #f)
(define lapack-dgesdd #f)
(define lapack-sgesdd #f)
(define lapack-dsyevd #f)
(define lapack-dgeqrf #f)

(when *lapack-available*
  (set! lapack-dgesv  (foreign-procedure "LAPACKE_dgesv" (int int int void* int void* void* int) int))
  (set! lapack-sgesv  (foreign-procedure "LAPACKE_sgesv" (int int int void* int void* void* int) int))
  (set! lapack-dgesdd (foreign-procedure "LAPACKE_dgesdd" (int int int int void* int void* void* int void* int) int))
  (set! lapack-sgesdd (foreign-procedure "LAPACKE_sgesdd" (int int int int void* int void* void* int void* int) int))
  (set! lapack-dsyevd (foreign-procedure "LAPACKE_dsyevd" (int int int int void* int void*) int))
  (set! lapack-dgeqrf (foreign-procedure "LAPACKE_dgeqrf" (int int int void* int void*) int)))
