

(define (np-dot a b n)
  "向量点积 a·b"
  (if *openblas-available* (cblas-ddot n a 1 b 1) (begin (display "OpenBLAS not available\n") 0.0)))

(define (np-daxpy n alpha x y)
  "向量线性组合 y = alpha*x + y"
  (if *openblas-available* (cblas-daxpy n alpha x 1 y 1) -1))

(define (np-copy n x y)
  "向量拷贝 y = x"
  (if *openblas-available* (cblas-dcopy n x 1 y 1) -1))

(define (np-scal n alpha x)
  "向量缩放 x = alpha*x"
  (if *openblas-available* (cblas-dscal n alpha x 1) -1))

(define (np-gemv trans m n alpha a x beta y)
  "矩阵×向量 y = alpha*A*x + beta*y"
  (if *openblas-available* (cblas-dgemv 101 trans m n alpha a n x 1 beta y 1) -1))

(define (np-gemm trans-a trans-b m n k alpha a b beta c)
  "矩阵乘法 C = alpha*A*B + beta*C"
  (if *openblas-available* (cblas-dgemm 101 trans-a trans-b m n k alpha a k b n beta c n) -1))

;; ====== tagged array 抽象：#(data len) ======
;; 所有 numpy 风格函数统一操作 tagged array，自动携带长度

(define (make-tagged-array data n)
  (vector data n))

(define (tagged-array-data a)
  (vector-ref a 0))

(define (tagged-array-len a)
  (vector-ref a 1))

(define (tagged-array? x)
  (and (vector? x) (= (vector-length x) 2) (integer? (vector-ref x 1))))


;; ====== numpy 数学函数（操作 tagged array） ======

(define (np-array v . maybe-n)
  "从 Scheme vector/list 创建 float64 tagged array，或透传已有 tagged array"
  (if (tagged-array? v)
    v
    (let* ((n (if (null? maybe-n)
                  (if (vector? v) (vector-length v) (length v))
                  (car maybe-n)))
           (ptr (make-float-array n)))
      (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array ptr n))
        (float-array-set ptr i (if (vector? v) (vector-ref v i) (list-ref v i)))))))

(define (np-from-list lst)
  "从 Scheme list 创建 float64 tagged array"
  (np-array lst))

(define (np-dot a b)
  "向量点积 a·b"
  (let ((n (tagged-array-len a))
        (da (tagged-array-data a))
        (db (tagged-array-data b)))
    (if *openblas-available*
      (cblas-ddot n da 1 db 1)
      (begin (display "OpenBLAS not available\n") 0.0))))

(define (np-daxpy alpha x y)
  "向量线性组合 y = alpha*x + y"
  (let ((n (tagged-array-len x))
        (dx (tagged-array-data x))
        (dy (tagged-array-data y)))
    (if *openblas-available* (cblas-daxpy n alpha dx 1 dy 1) -1)))

(define (np-copy x)
  "向量拷贝 y = x"
  (let ((n (tagged-array-len x))
        (dx (tagged-array-data x))
        (dy (tagged-array-data (np-zeros n))))
    (if *openblas-available* (cblas-dcopy n dx 1 dy 1) -1)
    (make-tagged-array dy n)))

(define (np-scal alpha x)
  "向量缩放 x = alpha*x"
  (let ((n (tagged-array-len x))
        (dx (tagged-array-data x)))
    (if *openblas-available* (cblas-dscal n alpha dx 1) -1)
    x))

(define (np-gemm trans-a trans-b m n k alpha a b beta c)
  "矩阵乘法 C = alpha*A*B + beta*C"
  (let ((da (tagged-array-data a))
        (db (tagged-array-data b))
        (dc (tagged-array-data c)))
    (if *openblas-available*
      (cblas-dgemm 101 trans-a trans-b m n k alpha da k db n beta dc n)
      -1)))

(define (np-sum a)
  "求和"
  (let ((n (tagged-array-len a))
        (ptr (tagged-array-data a)))
    (do ((i 0 (+ i 1)) (s 0.0 (+ s (foreign-ref 'double ptr (* i 8))))) ((= i n) s))))

(define (np-mean a)
  "平均值"
  (/ (np-sum a) (tagged-array-len a)))

(define (np-max a)
  "最大值"
  (let ((n (tagged-array-len a))
        (ptr (tagged-array-data a)))
    (do ((i 1 (+ i 1)) (m (foreign-ref 'double ptr 0) (max m (foreign-ref 'double ptr (* i 8))))) ((= i n) m))))

(define (np-min a)
  "最小值"
  (let ((n (tagged-array-len a))
        (ptr (tagged-array-data a)))
    (do ((i 1 (+ i 1)) (m (foreign-ref 'double ptr 0) (min m (foreign-ref 'double ptr (* i 8))))) ((= i n) m))))

(define (np-zeros n)
  "创建全零 tagged array"
  (make-tagged-array (make-float-array n) n))

(define (np-ones n)
  "创建全一 tagged array"
  (let ((ptr (make-float-array n)))
    (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array ptr n))
      (foreign-set! 'double ptr (* i 8) 1.0))))

(define (np-sqrt a)
  "逐元素平方根"
  (let* ((n (tagged-array-len a))
         (ptr (tagged-array-data a))
         (r (make-float-array n)))
    (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array r n))
      (foreign-set! 'double r (* i 8) (sqrt (foreign-ref 'double ptr (* i 8)))))))

(define (np-exp a)
  "逐元素指数"
  (let* ((n (tagged-array-len a))
         (ptr (tagged-array-data a))
         (r (make-float-array n)))
    (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array r n))
      (foreign-set! 'double r (* i 8) (exp (foreign-ref 'double ptr (* i 8)))))))

(define (np-abs a)
  "逐元素绝对值"
  (let* ((n (tagged-array-len a))
         (ptr (tagged-array-data a))
         (r (make-float-array n)))
    (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array r n))
      (foreign-set! 'double r (* i 8) (abs (foreign-ref 'double ptr (* i 8)))))))

(define (np-arange start end step)
  "arange: 从 start 到 end，步长 step"
  (let* ((n (max 0 (inexact->exact (ceiling (/ (- end start) step)))))
         (ptr (make-float-array n)))
    (do ((i 0 (+ i 1)) (v start (+ v step))) ((= i n) (make-tagged-array ptr n))
      (foreign-set! 'double ptr (* i 8) v))))

(define (np-linspace start end n)
  "linspace: 从 start 到 end，均匀 n 个点"
  (let ((ptr (make-float-array n))
        (step (/ (- end start) (max 1 (- n 1)))))
    (do ((i 0 (+ i 1)) (v start (+ v step))) ((= i n) (make-tagged-array ptr n))
      (foreign-set! 'double ptr (* i 8) v))))

(define (np-concatenate arrays)
  "拼接多个 tagged array"
  (let* ((sizes (map tagged-array-len arrays))
         (total-size (apply + sizes))
         (result (make-float-array total-size))
         (offsets (let loop ((acc 0) (szs sizes))
                    (if (null? szs) '()
                      (cons acc (loop (+ acc (car szs)) (cdr szs)))))))
    (let loop ((arrs arrays) (offs offsets))
      (if (null? arrs)
        (make-tagged-array result total-size)
        (let ((src (tagged-array-data (car arrs)))
              (offset (car offs))
              (len (tagged-array-len (car arrs))))
          (do ((i 0 (+ i 1))) ((= i len))
            (foreign-set! 'double result (* (+ offset i) 8)
              (foreign-ref 'double src (* i 8))))
          (loop (cdr arrs) (cdr offs)))))))

(define (np-clip a lo hi)
  "截断值到 [lo, hi] 范围"
  (let* ((n (tagged-array-len a))
         (ptr (tagged-array-data a))
         (r (make-float-array n)))
    (do ((i 0 (+ i 1))) ((= i n) (make-tagged-array r n))
      (foreign-set! 'double r (* i 8)
        (max lo (min hi (foreign-ref 'double ptr (* i 8))))))))

(define (np-argmax a)
  "最大值的索引"
  (let ((n (tagged-array-len a))
        (ptr (tagged-array-data a)))
    (do ((i 1 (+ i 1)) (mi 0) (mv (foreign-ref 'double ptr 0)))
        ((= i n) mi)
      (let ((v (foreign-ref 'double ptr (* i 8))))
        (when (> v mv) (set! mi i) (set! mv v))))))

;; 兼容旧 API：允许 (np-dot a b n) 直接传裸指针（弃用）
(define (np-dot-compat a b . maybe-n)
  (if (null? maybe-n)
    (np-dot a b)
    (np-dot (make-tagged-array a (car maybe-n)) (make-tagged-array b (car maybe-n)))))

;; 如果 import 映射生成的是 np-dot，上面定义的是 np-dot
;; 旧代码可能生成 (np-dot a b n)，下面加一个接受 3 参数的包装会覆盖
;; 但 Scheme 不支持重载，因此保留旧名 np-dot-old，让新代码用 np-dot
(define np-dot-old np-dot-compat)

;; ============================================================
;; Part 5: Python 风格包装 — scipy.linalg 兼容层
;; ============================================================

(define (la-solve n a b)
  "解线性方程组 Ax = b"
  (lapack-dgesv 101 n 1 a n b 1))

(define (la-svd m n a s u vt)
  "SVD 分解 A = U*S*V^T"
  (lapack-dgesdd 101 65 m n a n s u m vt n))

(define (la-eigvals n a w)
  "特征值分解 (对称矩阵)"
  (lapack-dsyevd 101 78 78 n a n w))
