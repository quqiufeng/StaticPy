;; ====== PyArray 运行时（plugins/pyarray） ======
;;
;; 本插件现在只管 **dict 的 C 后端**：
;;   py-map    （pyarray.c）Zend 式 items[]+hash index，插序保留 / 墓碑压缩；
;;             值留在 Scheme 的 handle 表里（handle 回收复用）
;;
;; list 的表示已统一到 core 的 py-glist（可增长向量）：原先这里的 py-listv 是
;; 第二套同构实现，注释里写"list 语义"却只被 list()/list(x) 触达，与 py-glist
;; 在两套分派（py-array? vs py-glist?）里重复维护 —— 已删，list() 交回 core。
;;
;; 未找到 libpyarr.so：dict 创建时报清晰错误。

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
(define (pa-dispatch-get2 c k)
  "c[k] 热路：map 的 int 快路内联在此（不再调 pm-get2）——读是最热的路径，
   少一层调用就少一次栈帧；语义与 pm-get2 完全一致。"
  (let ((ik (pa-int-key k)))
    (cond (ik (let ((h (pa-get-i2-ptr (py-map-id c) ik)))
                (if (>= h 0) (pm-hget c h) py-none)))
          ((string? k)
           (let ((h (pa-get-s2-ptr (py-map-id c) (pa-sid k))))
             (if (>= h 0) (pm-hget c h) py-none)))
          (else (let ((x (py-map-extra c)))
                  (if x (hashtable-ref x k py-none) py-none))))))

(define (pa-dispatch-get3 c k d) (pm-get3 c k d))

(define (pa-dispatch-get c k . dflt)
  (if (null? dflt) (pa-dispatch-get2 c k) (pa-dispatch-get3 c k (car dflt))))

(define (pa-dispatch-set c k v) (pm-set! c k v))

(define (pa-dispatch-del c k) (pm-del! c k))

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
        (else (pa-py-set-orig c k v))))

(define (pa-flat-del c k)
  (cond ((py-map? c) (pm-del! c k))
        (else (pa-py-del-orig c k))))

(define (pa-dispatch-len c) (pm-len c))

(define (pa-dispatch-has c k) (pm-has? c k))

(define (pa-dispatch-items c)
  "迭代源（翻译器的 for 循环按 vector 遍历）"
  (list->vector (pm-keys c)))

(define (pa-register!)
  (set! py-array-pred    py-map?)
  ;; 直接把判定函数本身换掉：prelude 的 py-array? 是一层 (and pred (pred x))，
  ;; 每次 c[k] 都要多走一次调用；这里换成 plugin 自己的（同样语义），省一层栈帧。
  (set! py-array?        py-map?)
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
(define (new_dict . kvs)
  "py_dict() 空表；py_dict(h) 从 hashtable/py-map 拷贝"
  (cond ((null? kvs) (pm-make))
        ((hashtable? (car kvs)) (pm-from-dict (car kvs)))
        ((py-map? (car kvs)) (pm-copy (car kvs)))
        (else (pm-make))))
(define (as_dict x) "转成 dict（hashtable/py-map）"
  (cond ((py-map? x) (pm-copy x))
        ((hashtable? x) (pm-from-dict x))
        (else (pm-make))))

(set! py-dict-pred py-map?)

;; ---- 方法分派（prelude 的 py-m-* 转发到这里） ----
(define (pa-dispatch-method name recv args)
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
    (else (error 'pyarray "dict has no method" name))))

(set! py-array-method-h pa-dispatch-method)
