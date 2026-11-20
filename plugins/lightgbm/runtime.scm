

;; ============================================================
;; Part 9: LightGBM — 树模型（替代方案）
;; ============================================================
(define *lightgbm-available* #f)
(call-with-current-continuation
  (lambda (return)
    (with-exception-handler
      (lambda (e) #f (return))
      (lambda ()
        (load-shared-object "liblightgbm.so")
        (set! *lightgbm-available* #t)))))

(define lgbm-create #f)
(define lgbm-predict #f)
(define lgbm-save #f)
(define lgbm-load #f)

(when *lightgbm-available*
  (set! lgbm-create (foreign-procedure "LGBM_BoosterCreateFromMat"
    (void* int int string void*) int))
  (set! lgbm-predict (foreign-procedure "LGBM_BoosterPredictForMat"
    (void* void* int int int int string void* void*) int))
  (set! lgbm-save (foreign-procedure "LGBM_BoosterSaveModel"
    (void* int string) int))
  (set! lgbm-load (foreign-procedure "LGBM_BoosterLoadModel"
    (string void*) int)))
