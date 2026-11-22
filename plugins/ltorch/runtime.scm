;; ====== libTorch 最小绑定（plugins/ltorch） ======
;;
;; 这一层只做两件事：
;;   1) dlopen cpp/torch/build/libtorch_capi.so（真 at::Tensor 的 C ABI）；
;;   2) 把 C ABI 的 CSV/句柄形态包成 Python 侧好用的 lt-* 过程。
;;
;; 张量句柄一律用 integer-64 传（不是 void*）：避免 Chez 把指针当 gc 对象处理，
;; 也方便在 Scheme 侧存进 dict/list 而不需要额外 pin。
;;
;; 数值对齐由 libtorch 保证 —— 我们**没有**重写任何算子，走的是 ATen 内核，
;; 所以 diff 只可能来自调用形态（shape/dtype/参数），不会来自算错了。

(define *ltorch-available* #f)
(define *ltorch-lib-path* "")
(define *ltorch-dir* "")

(define (ltorch-load-lib!)
  (let loop ((cands (list (let ((e (getenv "STATICPY_LTORCH")))
                            (and e (not (string=? e "")) e))
                          (let ((e (getenv "STATICPY_LTORCH_DIR")))
                            (and e (not (string=? e ""))
                                 (string-append e "/libtorch_capi.so")))
                          "/opt/StaticPy/cpp/torch/build/libtorch_capi.so"
                          "libtorch_capi.so")))
    (cond ((null? cands) #f)
          ((and (string? (car cands))
                (guard (e (#t #f)) (load-shared-object (car cands)) #t))
           (set! *ltorch-lib-path* (car cands))
           (set! *ltorch-available* #t)
           #t)
          (else (loop (cdr cands))))))

(ltorch-load-lib!)

;; ---- foreign-procedure 槽位 ----
(define lt-ver-p #f)      (define lt-err-p #f)
(define lt-from-csv-p #f) (define lt-zeros-p #f)   (define lt-ones-p #f)
(define lt-full-p #f)     (define lt-randn-p #f)   (define lt-arange-p #f)
(define lt-add-p #f)      (define lt-sub-p #f)     (define lt-mul-p #f)
(define lt-div-p #f)      (define lt-matmul-p #f)
(define lt-add-s-p #f)    (define lt-mul-s-p #f)
(define lt-relu-p #f)     (define lt-sigmoid-p #f) (define lt-tanh-p #f)
(define lt-softmax-p #f)  (define lt-sum-p #f)     (define lt-mean-p #f)
(define lt-sum-dim-p #f)
(define lt-reshape-p #f)  (define lt-transpose-p #f)
(define lt-clone-p #f)    (define lt-detach-p #f)
(define lt-numel-p #f)    (define lt-ndim-p #f)    (define lt-shape-p #f)
(define lt-to-csv-p #f)   (define lt-item-p #f)
(define lt-set-rg-p #f)   (define lt-rg-p #f)
(define lt-backward-p #f) (define lt-grad-p #f)    (define lt-zero-grad-p #f)
(define lt-free-p #f)

(when *ltorch-available*
  (set! lt-ver-p    (foreign-procedure "torchc_version" () string))
  (set! lt-err-p    (foreign-procedure "torchc_last_error" () string))
  (set! lt-from-csv-p  (foreign-procedure "torchc_from_csv" (string string) integer-64))
  (set! lt-zeros-p  (foreign-procedure "torchc_zeros" (string) integer-64))
  (set! lt-ones-p   (foreign-procedure "torchc_ones" (string) integer-64))
  (set! lt-full-p   (foreign-procedure "torchc_full" (string double) integer-64))
  (set! lt-randn-p  (foreign-procedure "torchc_randn" (string integer-64) integer-64))
  (set! lt-arange-p (foreign-procedure "torchc_arange" (double double double) integer-64))
  (set! lt-add-p    (foreign-procedure "torchc_add" (integer-64 integer-64) integer-64))
  (set! lt-sub-p    (foreign-procedure "torchc_sub" (integer-64 integer-64) integer-64))
  (set! lt-mul-p    (foreign-procedure "torchc_mul" (integer-64 integer-64) integer-64))
  (set! lt-div-p    (foreign-procedure "torchc_div" (integer-64 integer-64) integer-64))
  (set! lt-matmul-p (foreign-procedure "torchc_matmul" (integer-64 integer-64) integer-64))
  (set! lt-add-s-p  (foreign-procedure "torchc_add_scalar" (integer-64 double) integer-64))
  (set! lt-mul-s-p  (foreign-procedure "torchc_mul_scalar" (integer-64 double) integer-64))
  (set! lt-relu-p   (foreign-procedure "torchc_relu" (integer-64) integer-64))
  (set! lt-sigmoid-p (foreign-procedure "torchc_sigmoid" (integer-64) integer-64))
  (set! lt-tanh-p   (foreign-procedure "torchc_tanh" (integer-64) integer-64))
  (set! lt-softmax-p (foreign-procedure "torchc_softmax" (integer-64 integer-64) integer-64))
  (set! lt-sum-p    (foreign-procedure "torchc_sum" (integer-64) integer-64))
  (set! lt-mean-p   (foreign-procedure "torchc_mean" (integer-64) integer-64))
  (set! lt-sum-dim-p (foreign-procedure "torchc_sum_dim" (integer-64 integer-64) integer-64))
  (set! lt-reshape-p (foreign-procedure "torchc_reshape" (integer-64 string) integer-64))
  (set! lt-transpose-p (foreign-procedure "torchc_transpose" (integer-64 integer-64 integer-64) integer-64))
  (set! lt-clone-p  (foreign-procedure "torchc_clone" (integer-64) integer-64))
  (set! lt-detach-p (foreign-procedure "torchc_detach" (integer-64) integer-64))
  (set! lt-numel-p  (foreign-procedure "torchc_numel" (integer-64) integer-64))
  (set! lt-ndim-p   (foreign-procedure "torchc_ndim" (integer-64) integer-64))
  (set! lt-shape-p  (foreign-procedure "torchc_shape_csv" (integer-64) string))
  (set! lt-to-csv-p (foreign-procedure "torchc_to_csv" (integer-64) string))
  (set! lt-item-p   (foreign-procedure "torchc_item" (integer-64) double))
  (set! lt-set-rg-p (foreign-procedure "torchc_set_requires_grad" (integer-64 integer-64) integer-64))
  (set! lt-rg-p     (foreign-procedure "torchc_requires_grad" (integer-64) integer-64))
  (set! lt-backward-p (foreign-procedure "torchc_backward" (integer-64) integer-64))
  (set! lt-grad-p   (foreign-procedure "torchc_grad" (integer-64) integer-64))
  (set! lt-zero-grad-p (foreign-procedure "torchc_zero_grad" (integer-64) integer-64))
  (set! lt-free-p   (foreign-procedure "torchc_free" (integer-64) void)))

;; ---- 小工具 ----
(define (ltorch-ensure!)
  (when (not *ltorch-available*)
    (error 'ltorch
           (string-append "libtorch_capi.so 未加载：先 bash cpp/torch/build.sh，"
                          "并设 LD_LIBRARY_PATH=<libtorch>/lib"
                          "（可用 STATICPY_LTORCH=<so 路径> 直接指定）"))))

(define (ltorch-split-csv s)
  "逗号分隔字符串 → list（空串 → 空表）"
  (let ((n (string-length s)))
    (let loop ((i 0) (start 0) (acc '()))
      (cond ((fx>= i n)
             (if (fx> n start)
                 (reverse (cons (substring s start n) acc))
                 (reverse acc)))
            ((char=? (string-ref s i) #\,)
             (loop (fx+ i 1) (fx+ i 1) (cons (substring s start i) acc)))
            (else (loop (fx+ i 1) start acc))))))

(define (ltorch-flat-list x)
  "shape 参数：接受 \"2,3\" / vector / py-glist / list —— 统一成 list"
  (cond ((string? x) (map string->number (ltorch-split-csv x)))
        ((py-glist? x) (vector->list (py-glist->vector x)))
        ((vector? x) (vector->list x))
        ((list? x) x)
        (else (error 'ltorch "shape 需要 list 或 \"2,3\"字符串" x))))

(define (ltorch-num->str v)
  (cond ((integer? v) (number->string v))
        ((flonum? v)
         (let* ((i (exact (truncate v)))
                (d (- v (exact->inexact i))))
           (if (= d 0.0) (number->string i) (number->string v))))
        ((number? v) (number->string (inexact->exact v)))
        (else (error 'ltorch "shape 里有非数字" v))))

(define (ltorch-join-csv xs)
  (cond ((null? xs) "")
        (else
         (let loop ((rest (cdr xs)) (out (ltorch-num->str (car xs))))
           (cond ((null? rest) out)
                 (else (loop (cdr rest)
                             (string-append out "," (ltorch-num->str (car rest))))))))))

(define (ltorch-shape->csv shape) (ltorch-join-csv (ltorch-flat-list shape)))

(define (ltorch-values->csv vals)
  "list/vector → \"1.0,2.0\"；元素必须是数字"
  (ltorch-join-csv (map (lambda (v)
                          (cond ((number? v) (exact->inexact v))
                                (else (error 'ltorch "tensor() 的元素必须是数字" v))))
                        (ltorch-flat-list vals))))

(define (ltorch-fail! who)
  (let ((msg (if *ltorch-available* (lt-err-p) "")))
    (error who (string-append "libtorch 调用失败：" msg))))

(define (ltorch-check who h)
  (if (or (not h) (eqv? h 0)) (ltorch-fail! who) h))

;; ---- 构造 ----
(define (ltorch-tensor values shape)
  "ltorch.tensor([1,2,3,4], [2,2]) → 张量句柄（float64）"
  (ltorch-ensure!)
  (ltorch-check 'tensor
    (lt-from-csv-p (ltorch-values->csv values) (ltorch-shape->csv shape))))

(define (ltorch-zeros shape)
  (ltorch-ensure!)
  (ltorch-check 'zeros (lt-zeros-p (ltorch-shape->csv shape))))

(define (ltorch-ones shape)
  (ltorch-ensure!)
  (ltorch-check 'ones (lt-ones-p (ltorch-shape->csv shape))))

(define (ltorch-full shape value)
  (ltorch-ensure!)
  (ltorch-check 'full (lt-full-p (ltorch-shape->csv shape) (exact->inexact value))))

(define (ltorch-randn shape seed)
  (ltorch-ensure!)
  (ltorch-check 'randn (lt-randn-p (ltorch-shape->csv shape) seed)))

(define (ltorch-arange start end step)
  (ltorch-ensure!)
  (ltorch-check 'arange
    (lt-arange-p (exact->inexact start) (exact->inexact end) (exact->inexact step))))

;; ---- 算术 / 激活 ----
(define (ltorch-add a b) (ltorch-ensure!) (ltorch-check 'add (lt-add-p a b)))
(define (ltorch-sub a b) (ltorch-ensure!) (ltorch-check 'sub (lt-sub-p a b)))
(define (ltorch-mul a b) (ltorch-ensure!) (ltorch-check 'mul (lt-mul-p a b)))
(define (ltorch-div a b) (ltorch-ensure!) (ltorch-check 'div (lt-div-p a b)))
(define (ltorch-matmul a b) (ltorch-ensure!) (ltorch-check 'matmul (lt-matmul-p a b)))
(define (ltorch-add-scalar a v)
  (ltorch-ensure!) (ltorch-check 'add_scalar (lt-add-s-p a (exact->inexact v))))
(define (ltorch-mul-scalar a v)
  (ltorch-ensure!) (ltorch-check 'mul_scalar (lt-mul-s-p a (exact->inexact v))))
(define (ltorch-relu a) (ltorch-ensure!) (ltorch-check 'relu (lt-relu-p a)))
(define (ltorch-sigmoid a) (ltorch-ensure!) (ltorch-check 'sigmoid (lt-sigmoid-p a)))
(define (ltorch-tanh a) (ltorch-ensure!) (ltorch-check 'tanh (lt-tanh-p a)))
(define (ltorch-softmax a dim) (ltorch-ensure!) (ltorch-check 'softmax (lt-softmax-p a dim)))
(define (ltorch-sum a) (ltorch-ensure!) (ltorch-check 'sum (lt-sum-p a)))
(define (ltorch-mean a) (ltorch-ensure!) (ltorch-check 'mean (lt-mean-p a)))
(define (ltorch-sum-dim a dim) (ltorch-ensure!) (ltorch-check 'sum_dim (lt-sum-dim-p a dim)))

;; ---- 形状 ----
(define (ltorch-reshape a shape)
  (ltorch-ensure!) (ltorch-check 'reshape (lt-reshape-p a (ltorch-shape->csv shape))))
(define (ltorch-transpose a d0 d1)
  (ltorch-ensure!) (ltorch-check 'transpose (lt-transpose-p a d0 d1)))
(define (ltorch-clone a) (ltorch-ensure!) (ltorch-check 'clone (lt-clone-p a)))
(define (ltorch-detach a) (ltorch-ensure!) (ltorch-check 'detach (lt-detach-p a)))
(define (ltorch-numel a) (ltorch-ensure!) (lt-numel-p a))
(define (ltorch-ndim a) (ltorch-ensure!) (lt-ndim-p a))
(define (ltorch-shape a) (ltorch-ensure!) (lt-shape-p a))
(define (ltorch-to-list a)
  "张量 → list[float]（按行主序展平）"
  (ltorch-ensure!)
  (map string->number (ltorch-split-csv (lt-to-csv-p a))))
(define (ltorch-item a) (ltorch-ensure!) (lt-item-p a))

;; ---- autograd ----
(define (ltorch-set-requires-grad a flag)
  (ltorch-ensure!) (lt-set-rg-p a (if flag 1 0)) a)
(define (ltorch-requires-grad a) (ltorch-ensure!) (eqv? (lt-rg-p a) 1))
(define (ltorch-backward a) (ltorch-ensure!) (ltorch-check 'backward (lt-backward-p a)))
(define (ltorch-grad a) (ltorch-ensure!) (ltorch-check 'grad (lt-grad-p a)))
(define (ltorch-zero-grad a) (ltorch-ensure!) (lt-zero-grad-p a) a)

;; ---- 杂项 ----
(define (ltorch-free a) (when *ltorch-available* (lt-free-p a)) #t)
(define (ltorch-version) (if *ltorch-available* (lt-ver-p) ""))
(define (ltorch-available) *ltorch-available*)
(define (ltorch-last-error) (if *ltorch-available* (lt-err-p) ""))
