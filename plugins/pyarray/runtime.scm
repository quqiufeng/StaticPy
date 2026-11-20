;; ====== PyArray 运行时（plugins/pyarray） ======
;;
;; 两种表示，各用最合适的存储：
;;   py-listv  纯 Scheme **可增长向量**（list 语义，零 FFI）：
;;             append/pop/ref 都是 O(1) 摊还，不再有 (list->vector (append ...)) 的 O(n²)
;;   py-map    C 后端 dict（pyarray.c）：Zend 式 items[]+hash index，
;;             插序保留 / 墓碑压缩；值留在 Scheme 的 handle 表里（handle 回收复用）
;;
;; 未找到 libpyarr.so：py-listv 照常可用，py-map 创建时报清晰错误。

(define *pa-available* #f)
(define *pa-lib-path* "")

(define (pa-load-lib!)
  (let loop ((cands (list (let ((e (getenv "STATICPY_PYARR")))
                            (and e (not (string=? e "")) e))
                          "/opt/StaticPy/plugins/pyarray/libpyarr.so"
                          "libpyarr.so")))
    (cond ((null? cands) #f)
          ((and (string? (car cands))
                (guard (e (#t #f)) (load-shared-object (car cands)) #t))
           (set! *pa-lib-path* (car cands)) (set! *pa-available* #t) #t)
          (else (loop (cdr cands))))))

(pa-load-lib!)

(define pa-new-ptr #f)    (define pa-free-ptr #f)   (define pa-len-ptr #f)
(define pa-set-i-ptr #f)  (define pa-set-s-ptr #f)  (define pa-get-i-ptr #f)
(define pa-get-s-ptr #f)  (define pa-has-i-ptr #f)  (define pa-has-s-ptr #f)
(define pa-get-i2-ptr #f) (define pa-get-s2-ptr #f)
(define pa-del-i-ptr #f)  (define pa-del-s-ptr #f)  (define pa-export-ptr #f)
(define pa-copy-ptr #f)   (define pa-clear-ptr #f)  (define pa-stats-ptr #f)
(define pa-sortd-ptr #f)  (define pa-abi-ptr #f)

(when *pa-available*
  (set! pa-new-ptr    (foreign-procedure "pa_new" () integer-64))
  (set! pa-free-ptr   (foreign-procedure "pa_free" (integer-64) integer-64))
  (set! pa-len-ptr    (foreign-procedure "pa_len" (integer-64) integer-64))
  (set! pa-set-i-ptr  (foreign-procedure "pa_set_i" (integer-64 integer-64 integer-64) integer-64))
  (set! pa-set-s-ptr  (foreign-procedure "pa_set_s" (integer-64 integer-64 integer-64) integer-64))
  (set! pa-get-i-ptr  (foreign-procedure "pa_get_i" (integer-64 integer-64 integer-64) integer-64))
  (set! pa-get-s-ptr  (foreign-procedure "pa_get_s" (integer-64 integer-64 integer-64) integer-64))
  ;; 2 参变体（默认 -1 烧在 C 里）：热路径少打包一次实参
  (set! pa-get-i2-ptr (foreign-procedure "pa_get_i2" (integer-64 integer-64) integer-64))
  (set! pa-get-s2-ptr (foreign-procedure "pa_get_s2" (integer-64 integer-64) integer-64))
  (set! pa-has-i-ptr  (foreign-procedure "pa_has_i" (integer-64 integer-64) integer-64))
  (set! pa-has-s-ptr  (foreign-procedure "pa_has_s" (integer-64 integer-64) integer-64))
  (set! pa-del-i-ptr  (foreign-procedure "pa_del_i" (integer-64 integer-64) integer-64))
  (set! pa-del-s-ptr  (foreign-procedure "pa_del_s" (integer-64 integer-64) integer-64))
  (set! pa-export-ptr (foreign-procedure "pa_export" (integer-64 void* integer-64) integer-64))
  (set! pa-copy-ptr   (foreign-procedure "pa_copy" (integer-64) integer-64))
  (set! pa-clear-ptr  (foreign-procedure "pa_clear" (integer-64) integer-64))
  (set! pa-stats-ptr  (foreign-procedure "pa_stats" (integer-64 integer-64) integer-64))
  (set! pa-sortd-ptr  (foreign-procedure "pa_sort_doubles" (void* integer-64) integer-64))
  (set! pa-abi-ptr    (foreign-procedure "pa_abi_version" () integer-64)))

;; ---------------- 缓冲区池（一次分配，反复复用） ----------------
(define *pa-pool* '())          ; ((len . ptr) ...)
(define *pa-pool-max* 8)

(define (pa-buf-acquire n)
  (let loop ((p *pa-pool*) (pre '()))
    (cond ((null? p) (foreign-alloc (* 8 n)))
          ((>= (caar p) n)
           (set! *pa-pool* (append (reverse pre) (cdr p)))
           (cdar p))
          (else (loop (cdr p) (cons (car p) pre))))))

(define (pa-buf-release ptr len)
  (when (and (< (length *pa-pool*) *pa-pool-max*)
             (not (assq ptr *pa-pool*)))
    (set! *pa-pool* (cons (cons len ptr) *pa-pool*)))
  ptr)

;; ---------------- 字符串键 intern（Scheme 侧，一次哈希换整数 id） ----------------
(define *pa-intern* (make-hashtable string-hash string=?))
(define *pa-names* (make-vector 256 ""))
(define *pa-nnames* 0)
(define *pa-intern-max* 131072)         ; 超过就退回通用路径，防止无界增长

(define (pa-name-of sid)
  (if (and (>= sid 0) (< sid *pa-nnames*)) (vector-ref *pa-names* sid) "?"))

(define (pa-sid s)
  "字符串键 → 稳定整数 id（intern；溢出返回 -1 表示请走通用路径）"
  (let ((hit (hashtable-ref *pa-intern* s #f)))
    (or hit
        (let ((id *pa-nnames*))
          (when (>= id *pa-intern-max*) (error 'pyarray "too many distinct string keys"))
          (when (>= id (vector-length *pa-names*))
            (let* ((old *pa-names*) (n (vector-length old))
                   (nv (make-vector (* 2 n) "")))
              (let loop ((i 0))
                (if (fx< i n)
                    (begin (vector-set! nv i (vector-ref old i)) (loop (fx+ i 1)))))
              (set! *pa-names* nv)))
          (vector-set! *pa-names* id s)
          (set! *pa-nnames* (+ id 1))
          (hashtable-set! *pa-intern* s id)
          id))))

;; 字面量键的单格缓存：热点循环里 d["name"] 连哈希都不用做
(define *pa-kc-str* #f)
(define *pa-kc-id* -1)
(define (pa-k s)
  (if (and (eq? s *pa-kc-str*) (>= *pa-kc-id* 0))
      *pa-kc-id*
      (let ((id (pa-sid s)))
        (set! *pa-kc-str* s) (set! *pa-kc-id* id) id)))

;; ================= py-listv：可增长向量（list 语义） =================
(define-record-type py-listv
  (fields (mutable vs) (mutable len)))

(define pl-init-cap 8)

(define (pl-make)
  (make-py-listv (make-vector pl-init-cap #f) 0))

(define (pl-from-vector v)
  "从 Scheme vector 造 py-listv（复制一份，之后互不影响）"
  (let* ((n (vector-length v)) (cap (if (fx< n pl-init-cap) pl-init-cap n))
         (vs (make-vector cap #f)))
    (let loop ((i 0))
      (when (fx< i n) (vector-set! vs i (vector-ref v i)) (loop (fx+ i 1))))
    (make-py-listv vs n)))

(define (pl-from-list lst) (pl-from-vector (list->vector lst)))

(define (pl-len l) (py-listv-len l))

(define (pl-grow! l need)
  (let* ((old (py-listv-vs l))
         (n (vector-length old))
         (cap (let loop ((c (if (fx< n pl-init-cap) pl-init-cap n)))
                (if (fx< c need) (loop (fx* c 2)) c)))
         (nv (make-vector cap #f)))
    (let loop ((i 0))
      (when (fx< i n) (vector-set! nv i (vector-ref old i)) (loop (fx+ i 1))))
    (py-listv-vs-set! l nv)
    l))

(define (pl-append! l v)
  "list.append：摊还 O(1)"
  (let ((n (py-listv-len l)))
    (when (fx>= n (vector-length (py-listv-vs l))) (pl-grow! l (fx+ n 1)))
    (vector-set! (py-listv-vs l) n v)
    (py-listv-len-set! l (fx+ n 1))
    py-none))

(define (pl-norm-index l i)
  "负下标按 Python 规则折算；越界返回 #f"
  (let ((n (py-listv-len l)))
    (cond ((not (number? i)) #f)
          ((< i 0) (let ((j (+ i n))) (and (>= j 0) j)))
          ((>= i n) #f)
          (else (truncate i)))))

(define (pl-ref l i)
  (let ((j (pl-norm-index l i)))
    (if j (vector-ref (py-listv-vs l) j) py-none)))

(define (pl-get-or l i dflt)
  "越界取默认值（Python 里对应 a[i] if i < len(a) else dflt）"
  (let ((j (pl-norm-index l i)))
    (if j (vector-ref (py-listv-vs l) j) dflt)))

(define (pl-set! l i v)
  (let ((j (pl-norm-index l i)))
    (if j (vector-set! (py-listv-vs l) j v)
        (error 'py-listv "index out of range" i)))
  v)

(define (pl-pop l . idx)
  (let* ((n (py-listv-len l))
         (i (if (null? idx) (fx- n 1) (car idx)))
         (j (pl-norm-index l i)))
    (if (not j)
        (error 'py-listv "pop from empty list / bad index")
        (let* ((vs (py-listv-vs l)) (v (vector-ref vs j)))
          ;; 左移填洞（尾部弹出时不用动）
          (let loop ((k j))
            (when (fx< (fx+ k 1) n)
              (vector-set! vs k (vector-ref vs (fx+ k 1)))
              (loop (fx+ k 1))))
          (vector-set! vs (fx- n 1) #f)
          (py-listv-len-set! l (fx- n 1))
          v))))

(define (pl-insert! l i v)
  (let* ((n (py-listv-len l))
         (j (cond ((<= i 0) 0) ((>= i n) n) (else (truncate i)))))
    (when (fx>= n (vector-length (py-listv-vs l))) (pl-grow! l (fx+ n 1)))
    (let ((vs (py-listv-vs l)))
      (let loop ((k n))
        (when (fx> k j)
          (vector-set! vs k (vector-ref vs (fx- k 1)))
          (loop (fx- k 1))))
      (vector-set! vs j v)
      (py-listv-len-set! l (fx+ n 1)))
    py-none))

(define (pl-clear! l)
  (let ((vs (py-listv-vs l)) (n (py-listv-len l)))
    (let loop ((i 0)) (when (fx< i n) (vector-set! vs i #f) (loop (fx+ i 1)))))
  (py-listv-len-set! l 0)
  py-none)

(define (pl-extend! l other)
  "list.extend：接受 py-listv / Scheme vector / Scheme list / string"
  (cond ((py-listv? other)
         (let ((n (py-listv-len other)))
           (let loop ((i 0))
             (when (fx< i n) (pl-append! l (vector-ref (py-listv-vs other) i)) (loop (fx+ i 1))))))
        ((vector? other)
         (let ((n (vector-length other)))
           (let loop ((i 0))
             (when (fx< i n) (pl-append! l (vector-ref other i)) (loop (fx+ i 1))))))
        ((string? other)
         (let ((n (string-length other)))
           (let loop ((i 0))
             (when (fx< i n) (pl-append! l (string (string-ref other i))) (loop (fx+ i 1))))))
        ((list? other) (for-each (lambda (v) (pl-append! l v)) other)))
  py-none)

(define (pl-copy l)
  "list.copy：浅拷贝"
  (let* ((n (py-listv-len l)) (cap (if (fx< n pl-init-cap) pl-init-cap n))
         (src (py-listv-vs l)) (vs (make-vector cap #f)))
    (let loop ((i 0))
      (when (fx< i n) (vector-set! vs i (vector-ref src i)) (loop (fx+ i 1))))
    (make-py-listv vs n)))

(define (pl-slice l start end . step-arg)
  "a[start:end:step] —— 与 CPython 相同的负下标/负步长语义"
  (let* ((n (py-listv-len l))
         (step (if (null? step-arg) 1 (car step-arg))))
    (let ((st (truncate step)))
      (cond
        ((= st 0) (error 'py-listv "slice step cannot be zero"))
        ((> st 0)
         (let* ((s (let ((x (truncate start))) (if (< x 0) (max 0 (+ x n)) (min x n))))
                (e (let ((x (truncate end))) (if (< x 0) (max 0 (+ x n)) (min x n))))
                (cnt (if (<= e s) 0 (quotient (+ (- e s) st -1) st)))
                (out (pl-make)))
           (let loop ((i 0) (k s))
             (when (fx< i cnt) (pl-append! out (vector-ref (py-listv-vs l) k))
                   (loop (fx+ i 1) (fx+ k st))))
           out))
        (else
         (let* ((s (let* ((x (truncate start)) (j (if (< x 0) (+ x n) x)))
                     (if (< j 0) -1 (if (>= j n) (fx- n 1) j))))
                (e (let* ((x (truncate end)) (j (if (< x 0) (+ x n) x)))
                     (if (< j -1) -1 (if (>= j n) (fx- n 1) j))))
                (cnt (if (<= s e) 0 (quotient (+ (- s e) (- -1 st) -1) (- st))))
                (out (pl-make)))
           (let loop ((i 0) (k s))
             (when (fx< i cnt) (pl-append! out (vector-ref (py-listv-vs l) k))
                   (loop (fx+ i 1) (fx+ k st))))
           out))))))

(define (pl-reverse! l)
  (let ((vs (py-listv-vs l)) (n (py-listv-len l)))
    (let loop ((i 0) (j (fx- n 1)))
      (when (fx< i j)
        (let ((tmp (vector-ref vs i)))
          (vector-set! vs i (vector-ref vs j))
          (vector-set! vs j tmp))
        (loop (fx+ i 1) (fx- j 1))))
    py-none))

(define (pl-to-vector l)
  "取一个长度恰好为 len 的 Scheme vector（for 循环/解构用）"
  (let* ((n (py-listv-len l)) (vs (py-listv-vs l)) (out (make-vector n #f)))
    (let loop ((i 0))
      (when (fx< i n) (vector-set! out i (vector-ref vs i)) (loop (fx+ i 1))))
    out))

(define (pl-to-list l) (vector->list (pl-to-vector l)))

(define pa-sortv-ptr #f)
(when *pa-available*
  (set! pa-sortv-ptr (foreign-procedure "pa_sort_vals" (void* void* integer-64) integer-64)))

;; ---------------- 通用比较（与 Python 的 < 同语义） ----------------
(define (py-cmp a b)
  "返回 -1/0/1；不支持的类型报错（Python 同样 TypeError）"
  (cond ((and (number? a) (number? b)) (cond ((< a b) -1) ((> a b) 1) (else 0)))
        ((and (string? a) (string? b)) (cond ((string<? a b) -1) ((string=? a b) 0) (else 1)))
        ((and (boolean? a) (boolean? b)) (- (if a 1 0) (if b 1 0)))
        ((and (py-none? a) (py-none? b)) 0)
        (else (error 'py-cmp "unorderable types"))))

(define (pl-all-numbers? l)
  (let ((vs (py-listv-vs l)) (n (py-listv-len l)))
    (let loop ((i 0))
      (cond ((fx>= i n) #t)
            ((number? (vector-ref vs i)) (loop (fx+ i 1)))
            (else #f)))))

(define (pl-sort-numbers! l)
  "全数字：抽 double 键 + 下标 → C 稳定归并 → 按下标回填（保原值精度）"
  (let* ((n (py-listv-len l)) (vs (py-listv-vs l)))
    (if (or (fx< n 2) (not pa-sortv-ptr))
        py-none
        (let ((kb (pa-buf-acquire n)) (ib (pa-buf-acquire n)))
          (let loop ((i 0))
            (when (fx< i n)
              (foreign-set! 'double kb (* 8 i) (exact->inexact (vector-ref vs i)))
              (foreign-set! 'integer-64 ib (* 8 i) i)
              (loop (fx+ i 1))))
          (pa-sortv-ptr kb ib n)
          (let ((tmp (make-vector n #f)))
            (let loop ((i 0))
              (when (fx< i n)
                (vector-set! tmp i (vector-ref vs (foreign-ref 'integer-64 ib (* 8 i))))
                (loop (fx+ i 1))))
            (let loop ((i 0))
              (when (fx< i n) (vector-set! vs i (vector-ref tmp i)) (loop (fx+ i 1)))))
          (pa-buf-release kb n)
          (pa-buf-release ib n)
          py-none))))

(define (pl-sort! l . opts)
  "list.sort()：全数字走 C 快路径；其余 Scheme 稳定排序。opts=(keyfn reverse?)"
  (let ((keyfn (if (and (pair? opts) (procedure? (car opts))) (car opts) #f)))
    (let ((rev? (if keyfn
                   (and (pair? (cdr opts)) (not (not (cadr opts))))
                   (and (pair? opts) (not (not (car opts)))))))
      (if (and (not keyfn) (not rev?) (pl-all-numbers? l))
          (pl-sort-numbers! l)
          (let* ((n (py-listv-len l))
                 (lst (pl-to-list l))
                 (cmp (if keyfn
                          (lambda (a b)
                            (let ((c (py-cmp (keyfn a) (keyfn b))))
                              (if rev? (> c 0) (< c 0))))
                          (lambda (a b)
                            (let ((c (py-cmp a b)))
                              (if rev? (> c 0) (< c 0))))))
                 (sorted (sort cmp lst))
                 (vs (py-listv-vs l)))
            (let loop ((p sorted) (i 0))
              (when (pair? p) (vector-set! vs i (car p)) (loop (cdr p) (fx+ i 1))))
            (py-listv-len-set! l n)
            py-none)))))

(define (pl-index-of l v)
  "list.index：返回下标，找不到 -1"
  (let ((vs (py-listv-vs l)) (n (py-listv-len l)))
    (let loop ((i 0))
      (cond ((fx>= i n) -1)
            ((pa-eq? (vector-ref vs i) v) i)
            (else (loop (fx+ i 1)))))))

(define (pl-count l v)
  (let ((vs (py-listv-vs l)) (n (py-listv-len l)))
    (let loop ((i 0) (c 0))
      (cond ((fx>= i n) c)
            ((pa-eq? (vector-ref vs i) v) (loop (fx+ i 1) (+ c 1)))
            (else (loop (fx+ i 1) c))))))

(define (pl-remove! l v)
  "list.remove：删掉第一个相等元素"
  (let ((i (pl-index-of l v)))
    (when (>= i 0) (pl-pop l i))
    py-none))

;; 相等判定（Python ==）：数值按值、字符串按内容、list 逐元素
(define (pa-eq? a b)
  (cond ((and (number? a) (number? b)) (= a b))
        ((and (string? a) (string? b)) (string=? a b))
        ((and (py-none? a) (py-none? b)) #t)
        ((and (py-listv? a) (py-listv? b)) (pl-equal? a b))
        (else (equal? a b))))

(define (pl-equal? a b)
  (let ((na (py-listv-len a)) (nb (py-listv-len b)))
    (if (fx!= na nb)
        #f
        (let ((va (py-listv-vs a)) (vb (py-listv-vs b)))
          (let loop ((i 0))
            (cond ((fx>= i na) #t)
                  ((pa-eq? (vector-ref va i) (vector-ref vb i)) (loop (fx+ i 1)))
                  (else #f)))))))

;; ================= py-map：C 后端 dict（保插入序） =================
(define-record-type py-map
  (fields (immutable id) (mutable vs) (mutable free) (mutable nxt) (mutable extra)))

(define *pm-guard* (make-guardian))

(define (pa-drain!)
  "回收已不可达的 py-map（guardian → pa_free）"
  (let loop ((m (*pm-guard*)))
    (when m
      (when (and *pa-available* (py-map-id m)) (pa-free-ptr (py-map-id m)))
      (loop (*pm-guard*)))))

(define (pm-make)
  (unless *pa-available*
    (error 'pyarray "libpyarr.so not loaded; py_dict() unavailable"))
  (let* ((id (pa-new-ptr))
         (m (make-py-map id (make-vector 32 #f) '() 0 #f)))
    (when (= id 0) (error 'pyarray "pa_new failed"))
    (*pm-guard* m)
    m))

;; ---- handle 表：C 里只存 handle，值留在 Scheme 侧（可被 GC 回收） ----
;; free 是 fixnum 向量：#(count h1 h2 ...) —— 用下标栈，写得再密也**不分配 cons**

(define (pm-halloc! m v)
  (let ((free (py-map-free m)))
    (if (pair? free)
        (let ((h (car free)))
          (py-map-free-set! m (cdr free))
          (vector-set! (py-map-vs m) h v)
          h)
        (let ((h (py-map-nxt m)) (vs (py-map-vs m)))
          (if (fx>= h (vector-length vs))
              (let* ((cap (fx* 2 (vector-length vs))) (nv (make-vector cap #f)))
                (let loop ((i 0))
                  (when (fx< i (vector-length vs))
                    (vector-set! nv i (vector-ref vs i)) (loop (fx+ i 1))))
                (py-map-vs-set! m nv)
                (vector-set! nv h v))
              (vector-set! vs h v))
          (py-map-nxt-set! m (fx+ h 1))
          h))))

(define (pm-hget m h) (vector-ref (py-map-vs m) h))

(define (pm-hfree! m h)
  (vector-set! (py-map-vs m) h #f)
  (py-map-free-set! m (cons h (py-map-free m)))
  py-none)

;; ---- 键分类：int（含整数 float/bool，与 Python 的 hash 一致）/ str / 其它 ----
(define (pa-int-key k)
  (cond ((fixnum? k) k)                              ; 热路：整数键直接返回
        ((and (flonum? k) (integer? k)) (truncate k))
        ((integer? k) (if (boolean? k) (if k 1 0) k))
        (else #f)))

(define (pa-extra! m)
  (or (py-map-extra m)
      (let ((h (make-hashtable equal-hash equal?)))
        (py-map-extra-set! m h) h)))

(define (pm-set! m k v)
  "d[k] = v（补序追加；已有键只改值，不动位置）
   快路：键已存在 → 直接改 handle 表里的值，不分配、不进 C 的插入路径"
  (let ((ik (pa-int-key k)))
    (cond (ik
           (let* ((id (py-map-id m)) (h (pa-get-i2-ptr id ik)))
             (if (>= h 0)
                 (begin (vector-set! (py-map-vs m) h v) v)
                 (let* ((h2 (pm-halloc! m v)) (old (pa-set-i-ptr id ik h2)))
                   (if (>= old 0) (pm-hfree! m old) #f)
                   v))))
          ((string? k)
           (let* ((sid (pa-sid k)) (id (py-map-id m)) (h (pa-get-s2-ptr id sid)))
             (if (>= h 0)
                 (begin (vector-set! (py-map-vs m) h v) v)
                 (let* ((h2 (pm-halloc! m v)) (old (pa-set-s-ptr id sid h2)))
                   (if (>= old 0) (pm-hfree! m old) #f)
                   v))))
          (else (hashtable-set! (pa-extra! m) k v) v))))

(define (pm-get2 m k)
  "d[k] 快路：不带 rest/apply，缺失 → None"
  (let ((ik (pa-int-key k)))
    (cond (ik (let ((h (pa-get-i2-ptr (py-map-id m) ik)))
                (if (>= h 0) (pm-hget m h) py-none)))
          ((string? k)
           (let ((h (pa-get-s2-ptr (py-map-id m) (pa-sid k))))
             (if (>= h 0) (pm-hget m h) py-none)))
          (else (let ((x (py-map-extra m)))
                  (if x (hashtable-ref x k py-none) py-none))))))

(define (pm-get3 m k d)
  "d.get(k, d)：同上，带默认值"
  (let ((ik (pa-int-key k)))
    (cond (ik (let ((h (pa-get-i2-ptr (py-map-id m) ik)))
                (if (>= h 0) (pm-hget m h) d)))
          ((string? k)
           (let ((h (pa-get-s2-ptr (py-map-id m) (pa-sid k))))
             (if (>= h 0) (pm-hget m h) d)))
          (else (let ((x (py-map-extra m)))
                  (if x (hashtable-ref x k d) d))))))

(define (pm-get m k . dflt)
  (if (null? dflt) (pm-get2 m k) (pm-get3 m k (car dflt))))

(define (pm-has? m k)
  (let ((ik (pa-int-key k)))
    (cond (ik (not (zero? (pa-has-i-ptr (py-map-id m) ik))))
          ((string? k) (not (zero? (pa-has-s-ptr (py-map-id m) (pa-sid k)))))
          (else (let ((x (py-map-extra m))) (and x (hashtable-contains? x k)))))))

(define (pm-del! m k)
  "del d[k]：返回值；不存在 → py-none"
  (let ((ik (pa-int-key k)))
    (cond (ik (let ((h (pa-del-i-ptr (py-map-id m) ik)))
                (if (>= h 0) (let ((v (pm-hget m h))) (pm-hfree! m h) v) py-none)))
          ((string? k)
           (let ((h (pa-del-s-ptr (py-map-id m) (pa-sid k))))
             (if (>= h 0) (let ((v (pm-hget m h))) (pm-hfree! m h) v) py-none)))
          (else (let ((x (py-map-extra m)))
                  (if (and x (hashtable-contains? x k))
                      (let ((v (hashtable-ref x k #f)))
                        (hashtable-delete! x k) v)
                      py-none))))))

(define (pm-len m)
  (let ((x (py-map-extra m)))
    (+ (pa-len-ptr (py-map-id m)) (if x (hashtable-size x) 0))))

(define (pm-pairs m)
  "按插入序返回 ((k . v) ...)：一次 pa_export 批量取，解码 kinds"
  (let* ((n (pa-len-ptr (py-map-id m)))
         (need (fx* 3 (fxmax n 1)))
         (buf (pa-buf-acquire need))
         (cnt (pa-export-ptr (py-map-id m) buf need)))
    (let loop ((i 0) (acc '()))
      (if (fx>= i cnt)
          (let ((x (py-map-extra m)))
            (pa-buf-release buf need)
            (if (and x (fx> (hashtable-size x) 0))
                (append (reverse acc) (hashtable->alist x))
                (reverse acc)))
          (let* ((kind (foreign-ref 'integer-64 buf (* 24 i)))
                 (k (foreign-ref 'integer-64 buf (+ (* 24 i) 8)))
                 (h (foreign-ref 'integer-64 buf (+ (* 24 i) 16)))
                 (key (if (= kind 1) k (pa-name-of k))))
            (loop (fx+ i 1) (cons (cons key (pm-hget m h)) acc)))))))

(define (pm-keys m) (map car (pm-pairs m)))
(define (pm-values m) (map cdr (pm-pairs m)))
(define (pm-items m) (map (lambda (p) (py-list (car p) (cdr p))) (pm-pairs m)))

(define (pm-clear! m)
  (pa-clear-ptr (py-map-id m))
  (py-map-vs-set! m (make-vector 32 #f))
  (py-map-free-set! m '())
  (py-map-nxt-set! m 0)
  (py-map-extra-set! m #f)
  py-none)

(define (pm-copy m)
  "dict.copy：C 侧拷 slots，Scheme 侧镜像 handle 表"
  (let* ((nid (pa-copy-ptr (py-map-id m)))
         (vs (py-map-vs m))
         (nv (make-vector (vector-length vs) #f)))
    (when (= nid 0) (error 'pyarray "pa_copy failed"))
    (let loop ((i 0))
      (when (fx< i (vector-length vs))
        (vector-set! nv i (vector-ref vs i)) (loop (fx+ i 1))))
    (let* ((x (py-map-extra m))
           (nx (and x (let ((h (make-hashtable equal-hash equal?)))
                        (for-each (lambda (kv) (hashtable-set! h (car kv) (cdr kv)))
                                  (hashtable->alist x)) h)))
           (c (make-py-map nid nv (py-map-free m) (py-map-nxt m) nx)))
      (*pm-guard* c) c)))

(define (pm-to-dict m)
  "转成既有 runtime 的 hashtable 字典（与老代码/插件互通）"
  (let ((d (make-dict)))
    (for-each (lambda (p) (dict-set! d (car p) (cdr p))) (pm-pairs m))
    d))

(define (pm-from-dict d)
  (let ((m (pm-make)))
    (for-each (lambda (k) (pm-set! m k (dict-get d k))) (dict-keys d))
    m))

;; ================= 统一分派（挂到 prelude 的钩子上） =================
(define (pa-list-or-map? x) (or (py-listv? x) (py-map? x)))

(define (pa-dispatch-get2 c k)
  "c[k] 热路：list/map 各走直连，不分配 rest 列表。
   map 的 int 快路内联在此（不再调 pm-get2）——读是最热的路径，
   少一层调用就少一次栈帧；语义与 pm-get2 完全一致。"
  (if (py-listv? c)
      (pl-ref c k)
      (let ((ik (pa-int-key k)))
        (cond (ik (let ((h (pa-get-i2-ptr (py-map-id c) ik)))
                    (if (>= h 0) (pm-hget c h) py-none)))
              ((string? k)
               (let ((h (pa-get-s2-ptr (py-map-id c) (pa-sid k))))
                 (if (>= h 0) (pm-hget c h) py-none)))
              (else (let ((x (py-map-extra c)))
                      (if x (hashtable-ref x k py-none) py-none)))))))

(define (pa-dispatch-get3 c k d)
  (if (py-listv? c) (pl-get-or c k d) (pm-get3 c k d)))

(define (pa-dispatch-get c k . dflt)
  (if (null? dflt) (pa-dispatch-get2 c k) (pa-dispatch-get3 c k (car dflt))))

(define (pa-dispatch-set c k v)
  (if (py-listv? c) (pl-set! c k v) (pm-set! c k v)))

(define (pa-dispatch-del c k)
  (cond ((py-listv? c) (pl-pop c k))
        (else (pm-del! c k))))

;; ============ 下标快路：一条 cond 直落（装到 prelude 的 py-get / py-set! 上） ============
;; 现状（3 层）：py-get → py-array? → py-array-get-h(间接) → pa-dispatch-get2 → 内层分支
;; 快路（1 层）：py-get 就是 pa-flat-get，map/int 命中一次到底。
;; 语义与 prelude 的 py-get 逐条对齐，最后 else 交回原实现（dict/str/vector 等全部照旧）。
(define pa-py-get-orig py-get)
(define pa-py-get-def-orig py-get-default)
(define pa-py-set-orig py-set!)
(define pa-py-del-orig py-del!)

(define (pa-flat-get c k)
  "c[k] 热路：整数键就地展开（少 pa-int-key / pm-hget 两层调用）"
  (cond ((py-map? c)
         (if (fixnum? k)
             (let ((h (pa-get-i2-ptr (py-map-id c) k)))
               (if (>= h 0) (vector-ref (py-map-vs c) h) py-none))
             (pa-flat-get-slow c k)))
        ((py-listv? c) (pl-ref c k))
        (else (pa-py-get-orig c k))))

(define (pa-flat-get-slow c k)
  "c[k] 非整数键 / 非 fixnum 键"
  (let ((ik (pa-int-key k)))
           (cond (ik (let ((h (pa-get-i2-ptr (py-map-id c) ik)))
                       (if (>= h 0) (pm-hget c h) py-none)))
                 ((string? k)
                  (let ((h (pa-get-s2-ptr (py-map-id c) (pa-sid k))))
                    (if (>= h 0) (pm-hget c h) py-none)))
                 (else (let ((x (py-map-extra c)))
                         (if x (hashtable-ref x k py-none) py-none))))))

(define (pa-flat-get-def c k d)
  "c.get(k, d) 热路：整数键就地展开"
  (cond ((py-map? c)
         (if (fixnum? k)
             (let ((h (pa-get-i2-ptr (py-map-id c) k)))
               (if (>= h 0) (vector-ref (py-map-vs c) h) d))
             (pa-flat-get-def-slow c k d)))
        ((py-listv? c) (pl-get-or c k d))
        (else (pa-py-get-def-orig c k d))))

(define (pa-flat-get-def-slow c k d)
  (let ((ik (pa-int-key k)))
           (cond (ik (let ((h (pa-get-i2-ptr (py-map-id c) ik)))
                       (if (>= h 0) (pm-hget c h) d)))
                 ((string? k)
                  (let ((h (pa-get-s2-ptr (py-map-id c) (pa-sid k))))
                    (if (>= h 0) (pm-hget c h) d)))
                 (else (let ((x (py-map-extra c)))
                         (if x (hashtable-ref x k d) d))))))

(define (pa-flat-set c k v)
  (cond ((py-map? c) (pm-set! c k v))
        ((py-listv? c) (pl-set! c k v))
        (else (pa-py-set-orig c k v))))

(define (pa-flat-del c k)
  (cond ((py-map? c) (pm-del! c k))
        ((py-listv? c) (pl-pop c k))
        (else (pa-py-del-orig c k))))

(define (pa-dispatch-len c) (if (py-listv? c) (pl-len c) (pm-len c)))

(define (pa-dispatch-has c k)
  (if (py-listv? c) (>= (pl-index-of c k) 0) (pm-has? c k)))

(define (pa-dispatch-items c)
  "迭代源（翻译器的 for 循环按 vector 遍历）"
  (if (py-listv? c) (pl-to-vector c) (list->vector (pm-keys c))))

(define (pa-register!)
  (set! py-array-pred    pa-list-or-map?)
  ;; 直接把判定函数本身换掉：prelude 的 py-array? 是一层 (and pred (pred x))，
  ;; 每次 c[k] 都要多走一次调用；这里换成 plugin 自己的（同样语义），省一层栈帧。
  (set! py-array?        pa-list-or-map?)
  (set! py-array-get-h     pa-dispatch-get2)
  (set! py-array-get-def-h pa-dispatch-get3)
  ;; 下标热路：把 prelude 的通用入口换成"一条 cond 到底"的版本（语义等价，少两层分派）
  (set! py-get         pa-flat-get)
  (set! py-get-default pa-flat-get-def)
  (set! py-set!        pa-flat-set)
  (set! py-del!        pa-flat-del)
  (set! py-array-set-h   pa-dispatch-set)
  (set! py-array-del-h   pa-dispatch-del)
  (set! py-array-len-h   pa-dispatch-len)
  (set! py-array-has-h   pa-dispatch-has)
  (set! py-array-items-h pa-dispatch-items))

(pa-register!)

;; ================= 从 StaticPy 代码里直接可用（**无下划线**别名同时给出） =================
 (define (new_list . args) "py_list(1,2,3) → list" (pl-from-list args))
 (define (new_dict . kvs)
  "py_dict() 空表；py_dict(h) 从 hashtable/py-map 拷贝"
  (cond ((null? kvs) (pm-make))
        ((hashtable? (car kvs)) (pm-from-dict (car kvs)))
        ((py-map? (car kvs)) (pm-copy (car kvs)))
        (else (pm-make))))
(define (as_list x) "转成 list（list/tuple/str/py-map keys）" 
  (cond ((py-listv? x) (pl-copy x))
        ((vector? x) (pl-from-vector x))
        ((string? x) (pl-from-list (map (lambda (c) (string c)) (string->list x))))
        ((list? x) (pl-from-list x))
        (else (pl-make))))
(define (as_dict x) "转成 dict（hashtable/py-map）"
  (cond ((py-map? x) (pm-copy x))
        ((hashtable? x) (pm-from-dict x))
        (else (pm-make))))

;; list / list + 的 PyArray 分支（prelude 里 py-list-append / py-list-concat 转发到这里）
(define (pa-dispatch-append lst val)
  (cond ((py-listv? lst) (pl-append! lst val) lst)
        (else (pm-set! lst val #t) lst)))

(define (pa-dispatch-concat a b)
  (let ((out (as_list a)))
    (pl-extend! out b)
    out))

(set! py-dict-pred py-map?)

(set! py-array-append-h pa-dispatch-append)

(set! py-array-concat-h pa-dispatch-concat)

;; ---- 方法分派（prelude 的 py-m-* 转发到这里） ----
(define (pa-dispatch-method name recv args)
  (if (py-listv? recv)
      (case name
        ((sort) (apply pl-sort! recv args))
        ((reverse) (pl-reverse! recv))
        ((extend) (pl-extend! recv (car args)))
        ((insert) (pl-insert! recv (car args) (cadr args)))
        ((remove) (pl-remove! recv (car args)))
        ((index) (pl-index-of recv (car args)))
        ((count) (pl-count recv (car args)))
        ((pop) (if (null? args) (pl-pop recv) (pl-pop recv (car args))))
        ((append) (pa-dispatch-append recv (car args)))
        ((clear) (pl-clear! recv))
        ((copy) (pl-copy recv))
        (else (error 'pyarray "list has no method" name)))
      (case name
        ((keys) (pm-keys recv))
        ((values) (pm-values recv))
        ((items) (pm-items recv))
        ((get) (apply pm-get recv args))
        ((pop) (let ((k (car args)))
                 (if (pm-has? recv k)
                     (pm-del! recv k)
                     (if (null? (cdr args)) py-none (cadr args)))))
        ((clear) (pm-clear! recv))
        ((copy) (pm-copy recv))
        ((setdefault)
         (if (pm-has? recv (car args))
             (pm-get recv (car args))
             (pm-set! recv (car args) (if (null? (cdr args)) py-none (cadr args)))))
        ((update)
         (let ((o (car args)))
           (for-each (lambda (k) (pm-set! recv k (pm-get o k)))
                     (if (py-map? o) (pm-keys o) (dict-keys o)))
           py-none))
        (else (error 'pyarray "dict has no method" name)))))

(set! py-array-method-h pa-dispatch-method)
