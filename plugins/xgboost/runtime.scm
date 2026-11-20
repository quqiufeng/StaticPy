
;; ============================================================
;; Part 8: XGBoost — 树模型训练/推理
;; ============================================================
(define *xgboost-available* #f)
(call-with-current-continuation
  (lambda (return)
    (with-exception-handler
      (lambda (e) #f (return))
      (lambda ()
        (load-shared-object "libxgboost.so")
        (set! *xgboost-available* #t)))))

(define xgb-create #f)
(define xgb-set-param #f)
(define xgb-train #f)
(define xgb-predict #f)
(define xgb-dmatrix-create #f)
(define xgb-dmatrix-set-float #f)

(when *xgboost-available*
  (set! xgb-create (foreign-procedure "XGBoosterCreate" (void* int) int))
  (set! xgb-set-param (foreign-procedure "XGBoosterSetParam" (void* string string) int))
  (set! xgb-train (foreign-procedure "XGBoosterTrainOneIter" (void* void*) int))
  (set! xgb-predict (foreign-procedure "XGBoosterPredict"
    (void* void* int int void* void*) int))
  (set! xgb-dmatrix-create (foreign-procedure "XGDMatrixCreateFromMat"
    (void* int int double void*) int))
  (set! xgb-dmatrix-set-float (foreign-procedure "XGDMatrixSetFloatInfo"
    (void* string void* int) int)))
