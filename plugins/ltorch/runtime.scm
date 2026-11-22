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
(define lt-sgd-step-p #f)
(define lt-is-tensor-p #f)
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
  (set! lt-sgd-step-p (foreign-procedure "torchc_sgd_step" (integer-64 integer-64 double) integer-64))
  (set! lt-is-tensor-p (foreign-procedure "torchc_is_tensor" (integer-64) integer-64))
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
(define (ltorch-sgd-step w g lr)
  "SGD：原地 w -= lr*g（torch.no_grad() 语义）"
  (ltorch-ensure!) (ltorch-check 'sgd_step (lt-sgd-step-p w g (exact->inexact lr))))

;; ---- 杂项 ----
(define (ltorch-free a) (when (and *ltorch-available* (integer? a)) (lt-free-p a)) #t)
(define (ltorch-is-tensor a) (if (and *ltorch-available* (integer? a)) (lt-is-tensor-p a) 0))
(define (ltorch-version) (if *ltorch-available* (lt-ver-p) ""))
(define (ltorch-available) *ltorch-available*)
(define (ltorch-last-error) (if *ltorch-available* (lt-err-p) ""))

;; =====================================================================
;; PyTorch 兼容层：让同一段 `torch.*` 代码在 ltorch 上跑
;;
;; 翻译器已把 torch.tensor / torch.matmul / torch.mse_loss / torch.backward /
;; torch.sgd 等名字硬映射成 `torch-<name>`（emit_lib 的 torch 表）。这里把这些
;; 名字实现成 ltorch 原语的薄包装，于是「PyTorch 写法」直接可用：
;;   torch.matmul(x, w) / torch.mse_loss(pred, y) / torch.backward(loss)
;;   torch.sgd(w, g, lr)
;; 语义差异只在 API 表面（张量句柄是 integer-64，不是 Python 对象）。
;; =====================================================================

;; ---- 从 Python 字面量推断形状（torch.tensor 只给数据的 PyTorch 写法）----
(define (torch-nested->list x)
  "py-glist / vector / list → 嵌套 list（保留层级）"
  (cond ((py-glist? x) (map torch-nested->list (vector->list (py-glist->vector x))))
        ((vector? x) (map torch-nested->list (vector->list x)))
        ((list? x) (map torch-nested->list x))
        (else x)))

(define (torch-infer-shape x)
  "嵌套 list → 形状；标量 → ()"
  (cond ((null? x) '(0))
        ((pair? x) (cons (length x) (torch-infer-shape (car x))))
        (else '())))

(define (torch-flat-nums x acc)
  "按行主序展平（尾部累积，避免 append 的 O(n^2)）；() 不能当元素"
  (cond ((null? x) acc)
        ((pair? x) (torch-flat-nums (cdr x) (torch-flat-nums (car x) acc)))
        (else (cons x acc))))

(define (torch-flat x) (reverse (torch-flat-nums x '())))

;; ---- 构造 ----
(define (torch-tensor data . shape)
  "torch.tensor([1,2,3,4]) / torch.tensor([[1,2],[3,4]])：形状自动推断"
  (let* ((nested (torch-nested->list data))
         (sh (cond ((null? shape) (torch-infer-shape nested))
                   ((null? (car shape)) (torch-infer-shape nested))
                   (else (car shape)))))
    (ltorch-tensor (torch-flat nested) sh)))

(define (torch-zeros shape) (ltorch-zeros shape))
(define (torch-ones shape) (ltorch-ones shape))
(define (torch-empty shape) (ltorch-zeros shape))
(define (torch-full shape v) (ltorch-full shape v))
(define (torch-randn shape . seed) (ltorch-randn shape (if (null? seed) 0 (car seed))))
(define (torch-arange start end . step)
  (ltorch-arange start end (if (null? step) 1 (car step))))

;; ---- 算术：张量×张量 或 张量×标量都接受（PyTorch 的广播子集）----
;; 句柄是 integer-64，光靠 number? 分不出「标量 3」与「句柄 3」，
;; 所以判型一律走 lt-tensor?（C 侧存活句柄表 torchc_is_tensor）。
(define (lt-tensor? v) (and (integer? v) (not (zero? (lt-is-tensor-p v)))))
(define (torch-add a b)
  (cond ((lt-tensor? b) (ltorch-add a b))
        ((lt-tensor? a) (ltorch-add-scalar a b))
        (else (error 'torch-add "参数里没有张量" a b))))
(define (torch-sub a b)
  (cond ((lt-tensor? a) (if (lt-tensor? b) (ltorch-sub a b) (ltorch-add-scalar a (- b))))
        ((lt-tensor? b) (ltorch-add-scalar (ltorch-mul-scalar b -1.0) a))
        (else (error 'torch-sub "参数里没有张量" a b))))
(define (torch-mul a b)
  (cond ((and (lt-tensor? a) (lt-tensor? b)) (ltorch-mul a b))
        ((lt-tensor? a) (ltorch-mul-scalar a b))
        ((lt-tensor? b) (ltorch-mul-scalar b a))
        (else (error 'torch-mul "参数里没有张量" a b))))
(define (torch-div a b)
  (cond ((lt-tensor? b) (ltorch-div a b))
        ((lt-tensor? a) (ltorch-mul-scalar a (/ 1.0 b)))
        (else (error 'torch-div "参数里没有张量" a b))))
(define (torch-matmul a b) (ltorch-matmul a b))
(define (torch-neg a) (ltorch-mul-scalar a -1.0))
(define (torch-pow a p)
  "只支持整数幂（C ABI 无 pow）；>=1 用连乘，p=0 返回 ones"
  (cond ((not (number? p)) (error 'torch-pow "幂必须是整数常量" p))
        ((= p 0) (ltorch-ones (ltorch-shape a)))
        ((< p 0) (error 'torch-pow "负幂未支持（无倒数算子）" p))
        (else (let loop ((i 1) (acc a))
                (if (>= i p) acc (loop (+ i 1) (ltorch-mul acc a)))))))

;; ---- 激活 ----
(define (torch-relu a) (ltorch-relu a))
(define (torch-sigmoid a) (ltorch-sigmoid a))
(define (torch-tanh a) (ltorch-tanh a))
(define (torch-softmax a . dim) (ltorch-softmax a (if (null? dim) 1 (car dim))))

;; ---- 归约 ----
(define (torch-sum a . dim)
  (if (null? dim) (ltorch-sum a) (ltorch-sum-dim a (car dim))))
(define (torch-mean a . dim)
  "带 dim 的 mean 需要先知道该轴长度：用 torch.sum(a, dim) 后自己乘 1/n"
  (if (null? dim)
      (ltorch-mean a)
      (error 'torch-mean "dim 版未支持：用 (torch.sum a dim) 再乘 1/n" dim)))
(define (torch-numel a) (ltorch-numel a))

;; ---- 形状 ----
(define (torch-reshape a shape) (ltorch-reshape a shape))
(define (torch-transpose a d0 d1) (ltorch-transpose a d0 d1))
(define (torch-clone a) (ltorch-clone a))
(define (torch-detach a) (ltorch-detach a))
(define (torch-to-list a) (ltorch-to-list a))
(define (torch-tolist a) (ltorch-to-list a))
(define (torch-item a) (ltorch-item a))

;; ---- 全连接层 / 损失（PyTorch 语义：linear = x@W + b）----
(define (torch-linear x w b) (torch-add (torch-matmul x w) b))
(define (torch-mse-loss pred target)
  (let ((d (torch-sub pred target)))
    (torch-mean (torch-mul d d))))
(define (torch-l1-loss pred target)
  "L1 = mean(|d|)，用 relu(d)+relu(-d) 代替 abs"
  (let ((d (torch-sub pred target)))
    (torch-mean (torch-add (torch-relu d) (torch-relu (torch-neg d))))))

;; ---- autograd / 优化器 ----
(define (torch-set-requires-grad a flag) (ltorch-set-requires-grad a flag))
(define (torch-backward loss) (ltorch-backward loss))
(define (torch-grad a) (ltorch-grad a))
(define (torch-has-grad a) (ltorch-requires-grad a))
(define (torch-zero-grad a) (ltorch-zero-grad a))
(define (torch-sgd w g lr) (ltorch-sgd-step w g lr))
(define (torch-optimizer-step w g lr) (ltorch-sgd-step w g lr))
(define (torch-optimizer-zero-grad a) (ltorch-zero-grad a))
(define (torch-manual-seed seed) seed)
(define (torch-free a) (ltorch-free a))
