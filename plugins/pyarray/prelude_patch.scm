;; ====== PyArray 挂载点（plugins/pyarray 载入后填；未载入则退化为旧行为） ======
;; 泛型访问器：翻译器对"类型未知的下标"发 py-get / py-set! / py-del!，
;; 语义交给运行时按容器类型分派（PyArray / dict / list / vector）。
(define py-array-pred    #f)
(define py-array-get-h   #f)
(define py-array-get-def-h #f)   ; c[k] 带默认值的热路
(define py-array-set-h   #f)
(define py-array-del-h   #f)
(define py-array-len-h   #f)
(define py-array-has-h   #f)
(define py-array-items-h #f)

(define (py-array? x) (and py-array-pred (py-array-pred x)))

(define (py-idx n k)
  "Python 下标归一：负数从尾部数；越界 → #f"
  (cond ((not (number? k)) #f)
        ((< k 0) (let ((j (+ n k))) (and (>= j 0) (truncate j))))
        ((>= k n) #f)
        (else (truncate k))))

(define (py-get c k)
  "c[k]：统一入口（缺失 → None）"
  (cond ((py-array? c) (py-array-get-h c k))
        ((hashtable? c) (dict-get c k))
        ((string? c) (let ((i (py-idx (string-length c) k)))
                       (if i (string (string-ref c i)) py-none)))
        ((vector? c) (let ((i (py-idx (vector-length c) k)))
                       (if i (vector-ref c i) py-none)))
        (else py-none)))

(define (py-get-default c k d)
  "c.get(k, d) 语义"
  (if (py-array? c)
      (py-array-get-def-h c k d)
      (cond ((hashtable? c) (dict-get-default c k d))
            ((vector? c) (let ((i (py-idx (vector-length c) k)))
                           (if i (vector-ref c i) d)))
            ((string? c) (let ((i (py-idx (string-length c) k)))
                           (if i (string (string-ref c i)) d)))
            (else d))))

(define (py-set! c k v)
  "c[k] = v"
  (cond ((py-array? c) (py-array-set-h c k v))
        ((hashtable? c) (dict-set! c k v))
        (else (error 'py-set! "item assignment on non-container"))))

(define (py-del! c k)
  "del c[k]"
  (cond ((py-array? c) (py-array-del-h c k))
        ((hashtable? c) (dict-delete! c k))
        (else py-none)))
