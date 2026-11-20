;; static_prelude.scm — StaticPy 核心运行时（由 plugins/ 自动拼装，勿手改）
;; 单一事实来源: plugins/<name>/runtime.scm；改插件后跑 python3 tools/split_plugins.py

(import (chezscheme))

;; ====== GC 跟踪：自动释放 C 内存 ======
(define *gc-guardian* (make-guardian))

(define (gc-register-ptr ptr)
  "注册 C 指针到 GC 跟踪，不再使用时自动 free"
  (*gc-guardian* ptr)
  ptr)

(define (gc-cleanup)
  "由 GC 在回收时自动调用"
  (let loop ()
    (let ((ptr (*gc-guardian*)))
      (when ptr
        (foreign-free ptr)
        (loop)))))

;; 每帧清理一次（在 prelude 中不自动触发，依赖 Chez GC 周期）
;; 实际由用户或编译器在适当时机调用

;; ====== 浮点数组 ======

(define (make-float-array n)
  "创建 n 个 double 的 C 数组，自动 GC 回收"
  (let ((ptr (foreign-alloc (if (fx= n 0) 8 (fx* n 8)))))
    (do ((i 0 (+ i 1))) ((= i n))
      (foreign-set! 'double ptr (* i 8) 0.0))
    (gc-register-ptr ptr)
    ptr))

(define (float-array-set ptr i val)
  (foreign-set! 'double ptr (* i 8) (inexact val)))

(define (float-array-ref ptr i)
  (foreign-ref 'double ptr (* i 8)))

(define (float-array-free ptr)
  "手动释放（也可等 GC 自动回收）"
  (foreign-free ptr))

;; ====== None 单例（与 #f/False 区分） ======
;; CPython 里 None 是独立对象；这里用一个唯一不可混淆的记录表示，
;; 使 `x is None` / `False is None` / `print(None)` 三处语义都能对上。
(define py-none (string->symbol "\x1;py-none"))
(define (py-none? x) (eq? x py-none))

;; ====== Python tuple ======
;; list 用 vector（repr 为 [..]），tuple 用记录类型包一层 vector，
;; 这样 print((1, 2)) 才是 (1, 2) 而不是 [1, 2]，且与 list 的类型判定互不混淆。
(define-record-type py-tuple
  (fields vs)
  (nongenerative py-tuple-1))

(define (py-tuple . elems)
  "构造 tuple：元素可为任意对象"
  (make-py-tuple (list->vector elems)))

(define (py-tuple-len t) (vector-length (py-tuple-vs t)))
(define (py-tuple-items t) (vector->list (py-tuple-vs t)))
(define (py-tuple-ref t k)
  (let ((i (py-idx (py-tuple-len t) k)))
    (if (or (not i) (>= i (py-tuple-len t))) py-none (vector-ref (py-tuple-vs t) i))))

;; ====== 可增长 py-list（list() 动态构建，append 摊销 O(1)） ======
;; 静态字面量 [1,2,3] 仍是 vector（不可变、repr 同 list）；
;; list() / append 链得到 py-glist（后备 vector + 有效长度，翻倍扩容）。
;; 两者在通用入口 py-get/py-len/py-items/py-repr 里统一分派。
(define-record-type py-glist
  (fields (mutable vs) (mutable n))
  (nongenerative py-glist-1))

(define (py-glist-new . cap)
  (make-py-glist (make-vector (if (null? cap) 8 (max 8 (car cap))) py-none) 0))

(define (py-glist-len g) (py-glist-n g))

(define (py-glist-ref g k)
  (let ((j (py-idx (py-glist-n g) k)))
    (if (and j (< j (py-glist-n g))) (vector-ref (py-glist-vs g) j) py-none)))

(define (py-glist-set! g k v)
  (let ((j (py-idx (py-glist-n g) k)))
    (if (and j (< j (py-glist-n g))) (begin (vector-set! (py-glist-vs g) j v) v)
        (error 'py-set! "list index out of range"))))

(define (py-glist-push! g v)
  "摊还 O(1) 追加：容量满则翻倍拷贝"
  (let* ((vs (py-glist-vs g)) (n (py-glist-n g)) (cap (vector-length vs)))
    (if (fx>= n cap)
        (let* ((nv (make-vector (fx* (if (fx< cap 8) 8 cap) 2) py-none)))
          (do ((i 0 (fx+ i 1))) ((fx>= i n)) (vector-set! nv i (vector-ref vs i)))
          (vector-set! nv n v)
          (py-glist-vs-set! g nv)
          (py-glist-n-set! g (fx+ n 1)))
        (begin (vector-set! vs n v)
               (py-glist-n-set! g (fx+ n 1))))
    g))

(define (py-glist->vector g)
  "导出为普通 vector（长度 = 有效长度）"
  (let* ((n (py-glist-n g)) (out (make-vector n py-none)) (vs (py-glist-vs g)))
    (do ((i 0 (fx+ i 1))) ((fx>= i n)) (vector-set! out i (vector-ref vs i)))
    out))

(define (py-glist-copy g)
  (to-glist (py-glist->vector g)))

(define (py-glist-pop! g . k)
  (let ((n (py-glist-n g)))
    (if (and (pair? k) (number? (car k)))
        (let ((i (py-idx n (car k))))
          (if (or (not i) (>= i n)) (error 'pop "pop index out of range")
              (let ((v (vector-ref (py-glist-vs g) i)))
                (do ((j i (fx+ j 1))) ((fx>= j (fx- n 1)))
                  (vector-set! (py-glist-vs g) j (vector-ref (py-glist-vs g) (fx+ j 1))))
                (vector-set! (py-glist-vs g) (fx- n 1) py-none)
                (py-glist-n-set! g (fx- n 1))
                v)))
        (if (fx= n 0) (error 'pop "pop from empty list")
            (let ((v (vector-ref (py-glist-vs g) (fx- n 1))))
              (vector-set! (py-glist-vs g) (fx- n 1) py-none)
              (py-glist-n-set! g (fx- n 1))
              v)))))

(define (py-glist-insert! g i v)
  (let* ((n (py-glist-n g)) (j (if (fx< i 0) (max 0 (fx+ n i)) (if (fx> i n) n i))))
    (py-glist-push! g v)                      ; 先扩容 + 占位
    (do ((k (fx- (py-glist-n g) 1) (fx- k 1))) ((fx<= k j))
      (vector-set! (py-glist-vs g) k (vector-ref (py-glist-vs g) (fx- k 1))))
    (vector-set! (py-glist-vs g) j v)
    g))

(define (py-glist-extend! g o)
  (for-each (lambda (v) (py-glist-push! g v)) (py-items o))
  g)

(define (py-glist-sort! g . args)
  (let* ((n (py-glist-n g))
         (sorted (list-sort (or (and (pair? args) (car args)) <)
                            (vector->list (py-glist->vector g)))))
    (let ((i 0))
      (for-each (lambda (v) (vector-set! (py-glist-vs g) i v) (set! i (+ i 1))) sorted))
    g))

(define (py-glist-reverse! g)
  (let ((vs (py-glist-vs g)) (n (py-glist-n g)))
    (do ((i 0 (fx+ i 1))) ((fx>= i (fxsra n 1)))
      (let ((a (vector-ref vs i)) (b (vector-ref vs (fx- n 1 i))))
        (vector-set! vs i b) (vector-set! vs (fx- n 1 i) a)))
    g))

(define (py-glist-index g v)
  (let loop ((i 0))
    (cond ((fx>= i (py-glist-n g)) -1)
          ((equal? (vector-ref (py-glist-vs g) i) v) i)
          (else (loop (fx+ i 1))))))

(define (py-glist-count g v)
  (let loop ((i 0) (c 0))
    (if (fx>= i (py-glist-n g)) c
        (loop (fx+ i 1) (if (equal? (vector-ref (py-glist-vs g) i) v) (fx+ c 1) c)))))

(define (py-glist-remove! g v)
  (let loop ((i 0))
    (cond ((fx>= i (py-glist-n g)) py-none)
          ((equal? (vector-ref (py-glist-vs g) i) v)
           (do ((j i (fx+ j 1))) ((fx>= j (fx- (py-glist-n g) 1)))
             (vector-set! (py-glist-vs g) j (vector-ref (py-glist-vs g) (fx+ j 1))))
           (py-glist-n-set! g (fx- (py-glist-n g) 1))
           py-none)
          (else (loop (fx+ i 1))))))

(define (py-glist-seq g)
  "内部遍历用：返回有效元素 list（只读）"
  (let loop ((i (fx- (py-glist-n g) 1)) (acc '()))
    (if (fx< i 0) acc (loop (fx- i 1) (cons (vector-ref (py-glist-vs g) i) acc)))))

(define (py-seq-len x)
  "for 循环快路：vector / py-glist / 其余走 py-len"
  (cond ((vector? x) (vector-length x))
        ((py-glist? x) (py-glist-n x))
        (else (py-len x))))

(define (py-seq-ref x i)
  "for 循环快路：按容器类型取第 i 个元素"
  (cond ((vector? x)
         (if (py-tagged-array? x) (float-array-ref (py-tagged-array-data x) i) (vector-ref x i)))
        ((py-glist? x) (py-glist-ref x i))
        (else (py-get x i))))

(define (py-range->list . args)
  "range(...) 在表达式位置（for 头由翻译器化成 do 循环）：返回 py-glist"
  (let* ((n (length args))
         (start (if (>= n 2) (car args) 0))
         (stop (cond ((>= n 2) (cadr args)) ((= n 1) (car args)) (else 0)))
         (step (if (>= n 3) (caddr args) 1)))
    (when (= step 0) (error 'range "range() arg 3 must not be zero"))
    (let ((g (py-glist-new)))
      (let loop ((i start))
        (if (if (> step 0) (< i stop) (> i stop))
            (begin (py-glist-push! g i) (loop (+ i step)))
            g)))))

;; ====== 真值判定（CPython 语义） ======
;; Scheme 里只有 #f 是假，而 CPython 里 None / 0 / "" / [] / {} 都是假。
;; 最关键的是 None：它是真实对象，`(not py-none)` 在 Scheme 下是 #f，
;; 直接照搬 `(not (not x))` 会把 `bool(None)` 判成 #t。
(define (py-truthy x)
  (cond ((py-none? x) #f)
        ((eq? x #f) #f)
        ((number? x) (not (zero? x)))
        ((string? x) (> (string-length x) 0))
        ((py-tuple? x) (> (py-tuple-len x) 0))
        ((py-glist? x) (> (py-glist-n x) 0))
        ((vector? x) (> (vector-length x) 0))
        ((pair? x) #t)
        ((null? x) #f)
        ((hashtable? x) (> (dict-length x) 0))
        (else #t)))

;; ====== `x in y` 成员判定（按容器类型分派） ======
;; 翻译器只发 `(py-contains? x y)`，语义交给运行时：
;; dict 看键、str 看子串、vector(py-list) 与 Scheme list 逐元素 equal?。
(define (py-contains? needle hay)
  (cond ((py-array? hay) (py-array-has-h hay needle))
        ((hashtable? hay) (dict-contains? hay needle))
        ((string? hay) (str-contains? hay needle))
        ((py-glist? hay)
         (> (py-glist-count hay needle) 0))
        ((py-tuple? hay)
         (let loop ((rest (py-tuple-items hay)))
           (cond ((null? rest) #f)
                 ((equal? (car rest) needle) #t)
                 (else (loop (cdr rest))))))
        ((vector? hay)
         (let loop ((i 0))
           (cond ((>= i (vector-length hay)) #f)
                 ((equal? (vector-ref hay i) needle) #t)
                 (else (loop (+ i 1))))))
        ((pair? hay) (not (not (member needle hay))))
        (else #f)))

;; ====== 字典（hashtable + 插入序） ======
;; CPython 3.7+ 的 dict 保序；Chez 的 hashtable 无序，
;; 所以额外在同一个 hashtable 里挂一个隐藏键存「插入序（逆序）」。
(define py-dict-order-key (string->symbol "\x1;py-dict-order"))

(define (make-dict)
  "创建空字典（保持插入顺序）"
  (let ((d (make-hashtable equal-hash equal?)))
    (hashtable-set! d py-dict-order-key '())
    d))

(define (py-dict-order d)
  (hashtable-ref d py-dict-order-key '()))

(define (dict-keys d)
  "按插入顺序返回键列表"
  (if (py-array? d) (py-m-keys d) (reverse (py-dict-order d))))

(define (dict-values d)
  (if (py-array? d) (py-m-values d)
      (map (lambda (k) (hashtable-ref d k #f)) (dict-keys d))))

(define (dict-items d)
  (if (py-array? d) (py-m-items d)
      (map (lambda (k) (cons k (hashtable-ref d k #f))) (dict-keys d))))

(define (dict-length d)
  (if (py-array? d) (py-array-len-h d) (length (py-dict-order d))))

(define (dict-get d key)
  "读取字典 d[key]；缺失 → None"
  (if (py-array? d)
      (py-array-get-h d key)
      (if (hashtable-contains? d key)
          (hashtable-ref d key #f)
          py-none)))

(define (dict-get-default d key default)
  "d.get(key, default)"
  (if (py-array? d)
      (py-array-get-def-h d key default)
      (if (hashtable-contains? d key)
          (hashtable-ref d key #f)
          default)))

(define (dict-get-or-empty d key)
  "读取字典 d[key]，返回空字符串代替缺失"
  (hashtable-ref d key ""))

(define dict_get_or_empty (lambda (d key) (dict-get-or-empty d key)))

(define (dict-set! d key val)
  "写入字典 d[key] = val（新键追加到末尾）"
  (if (py-array? d)
      (py-array-set-h d key val)
      (begin
        (unless (hashtable-contains? d key)
          (hashtable-set! d py-dict-order-key (cons key (py-dict-order d))))
        (hashtable-set! d key val)
        val)))

(define (dict-set-default! d key val)
  "setdefault：键不存在时写入"
  (cond ((py-array? d) (py-m-setdefault d key val))
        ((hashtable-contains? d key)
        (hashtable-ref d key #f))
        (else (dict-set! d key val))))

(define (dict-delete! d key)
  "删除键；存在返回 True"
  (if (py-array? d)
      (if (py-array-has-h d key) (begin (py-array-del-h d key) #t) #f)
      (if (hashtable-contains? d key)
      (begin
        (hashtable-set! d py-dict-order-key
                        (let loop ((ks (py-dict-order d)))
                          (cond ((null? ks) '())
                                ((equal? (car ks) key) (loop (cdr ks)))
                                (else (cons (car ks) (loop (cdr ks)))))))
          (hashtable-delete! d key)
          #t)
        #f)))

(define (dict-pop d key . default)
  (if (py-array? d)
      (apply py-m-pop d (cons key default))
      (if (hashtable-contains? d key)
          (let ((v (hashtable-ref d key #f)))
            (dict-delete! d key)
            v)
          (if (null? default) py-none (car default)))))

(define (dict-contains? d key)
  "检查 key 是否在字典中（隐藏键不算）"
  (if (py-array? d)
      (py-array-has-h d key)
      (and (hashtable? d)
           (not (eq? key py-dict-order-key))
           (hashtable-contains? d key))))

(define (dict-merge! d other)
  "update：把 other 的键值按序写入 d"
  (if (py-array? d)
      (apply py-m-update d (list other))
      (begin
        (for-each (lambda (k) (dict-set! d k (hashtable-ref other k #f)))
                  (if (hashtable? other) (dict-keys other) '()))
        d)))

(define (dict-copy d)
  "浅拷贝字典（保序）"
  (if (py-array? d)
      (py-m-copy d)
      (let ((copy (make-dict)))
        (for-each (lambda (k) (dict-set! copy k (hashtable-ref d k #f)))
                  (dict-keys d))
        copy)))

;; ====== 真除法 / 长度 ======
;; CPython 的 / 永远返回 float（4/2 → 2.0，1/3 → 0.333…）
(define (py-truediv a b)
  (inexact (/ a b)))

;; ====== 位运算 ======
;; 翻译器对 BinOp 的兜底是 str_lower(op)，位运算于是发出 bitand/bitor/bitxor/
;; lshift/rshift，一元 ~ 发出 Invert —— 这些名字 Chez 里都不存在。
;; 语义交给运行时映射到 R6RS bitwise-*（用泛型版而非 fx 版：Python int 是
;; 任意精度，bitwise-* 同样处理 bignum，比 fx 更贴 CPython）。
;; 算术右移对负数与 Python 一致：-8>>1 → -4；-1&255 → 255。
(define (bitand a b) (bitwise-and a b))
(define (bitor  a b) (bitwise-ior a b))
(define (bitxor a b) (bitwise-xor a b))
(define (lshift a b) (bitwise-arithmetic-shift-left a b))
(define (rshift a b) (bitwise-arithmetic-shift-right a b))
;; ~x 在 Python 是 -(x+1)（二进制补码语义），bitwise-not 正是这个
(define (Invert a) (bitwise-not a))

;; 统一迭代源：dict→键、str→字符、vector/list/tagged-array 原样
(define (py-iter-seq x)
  (cond ((py-array? x) (py-array-items-h x))
        ((py-glist? x) (py-glist->vector x))
        ((hashtable? x) (list->vector (dict-keys x)))
        ((string? x)
         (let* ((n (string-length x)) (v (make-vector n "")))
           (let loop ((i 0))
             (if (fx< i n)
                 (begin (vector-set! v i (string (string-ref x i))) (loop (fx+ i 1)))
                 v))))
        ((vector? x) x)
        ((tagged-array? x)
         (let* ((n (tagged-array-len x)) (v (make-vector n 0.0)))
           (let loop ((i 0))
             (if (fx< i n)
                 (begin (vector-set! v i (float-array-ref (tagged-array-data x) i))
                        (loop (fx+ i 1)))
                 v))))
        ((list? x) (list->vector x))
        (else (vector))))

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

;; py-map（PyArray 的 dict）判定：由 plugins/pyarray 注册；未载入则恒假
(define py-dict-pred #f)
(define (py-dict? x) (and py-dict-pred (py-dict-pred x)))

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
        ((py-tuple? c) (py-tuple-ref c k))
        ((py-glist? c) (py-glist-ref c k))
        ((vector? c) (let ((i (py-idx (vector-length c) k)))
                       (if i (vector-ref c i) py-none)))
        (else py-none)))

(define (py-get-default c k d)
  "c.get(k, d) 语义"
  (if (py-array? c)
      (py-array-get-def-h c k d)
      (cond ((hashtable? c) (dict-get-default c k d))
            ((py-tuple? c) (let ((v (py-tuple-ref c k))) (if (py-none? v) d v)))
            ((py-glist? c) (let ((v (py-glist-ref c k))) (if (py-none? v) d v)))
            ((vector? c) (let ((i (py-idx (vector-length c) k)))
                           (if i (vector-ref c i) d)))
            ((string? c) (let ((i (py-idx (string-length c) k)))
                           (if i (string (string-ref c i)) d)))
            (else d))))

(define (py-set! c k v)
  "c[k] = v"
  (cond ((py-array? c) (py-array-set-h c k v))
        ((hashtable? c) (dict-set! c k v))
        ((py-glist? c) (py-glist-set! c k v))
        ((vector? c)
         (let ((i (py-idx (vector-length c) k)))
           (if i (vector-set! c i v)
               (error 'py-set! "index out of range"))))
        (else (error 'py-set! "item assignment on non-container"))))

(define (py-del! c k)
  "del c[k]"
  (cond ((py-array? c) (py-array-del-h c k))
        ((hashtable? c) (dict-delete! c k))
        ((py-glist? c) (py-glist-set! c k py-none))
        ((and (vector? c) (py-idx (vector-length c) k)) => (lambda (i) (vector-set! c i py-none)))
        (else py-none)))

;; ====== 容器方法泛型分派（dict / list / PyArray 共用一套名字） ======
;; 翻译器把 x.get(...) / x.sort() / x.append(...) 等统一发成 py-m-<name>，
;; 具体语义在这里按接收者类型分派：hashtable（旧 dict）/ PyArray（新）。
(define (py-m-keys r) (if (py-array? r) (py-array-method-h 'keys r '()) (dict-keys r)))
(define (py-m-values r) (if (py-array? r) (py-array-method-h 'values r '()) (dict-values r)))
(define (py-m-items r) (if (py-array? r) (py-array-method-h 'items r '()) (dict-items r)))

(define (py-m-get r k . d)
  (let ((dflt (if (null? d) py-none (car d))))
    (cond ((py-array? r) (if (null? d) (py-array-get-h r k) (py-array-get-def-h r k dflt)))
          ((hashtable? r) (if (null? d) (dict-get r k) (dict-get-default r k dflt)))
          (else py-none))))

;; 定参快路：`.get(k)` / `.get(k, d)` 不走 rest 列表（每次调用少一次 list 分配 + appl）
(define (py-m-get2 r k) "x.get(k)：定参快路（语义同 py-m-get）" (py-get r k))
(define (py-m-get3 r k d) "x.get(k, d)：定参快路（语义同 py-m-get）" (py-get-default r k d))

(define (py-m-pop r . k)
  (cond ((py-array? r) (py-array-method-h 'pop r k))
        ((py-glist? r) (apply py-glist-pop! r k))
        ((hashtable? r) (if (null? k) (error 'pop "dict.pop needs key")
                            (if (null? (cdr k)) (dict-pop r (car k))
                                (dict-pop r (car k) (cadr k)))))
        (else py-none)))

(define (py-m-clear r)
  (cond ((py-array? r) (py-array-method-h 'clear r '()))
        ((py-glist? r) (py-glist-n-set! r 0) py-none)
        (else (begin (dict-clear! r) py-none))))

(define (py-m-setdefault r k . v)
  (if (py-array? r) (py-array-method-h 'setdefault r (cons k v))
      (if (dict-contains? r k) (dict-get r k)
          (let ((dv (if (null? v) py-none (car v)))) (dict-set! r k dv)))))

(define (py-m-update r o)
  (if (py-array? r) (py-array-method-h 'update r (list o)) (begin (dict-merge! r o) py-none)))

(define (py-m-copy r)
  (cond ((py-array? r) (py-array-method-h 'copy r '()))
        ((py-glist? r) (py-glist-copy r))
        (else (dict-copy r))))

(define (py-m-sort r . args)
  (cond ((py-array? r) (py-array-method-h 'sort r args))
        ((py-glist? r)
         (let ((sorted (list-sort (or (and (pair? args) (car args)) <) (py-glist-seq r)))
               (vs (py-glist-vs r)))
           (let loop ((i 0) (rest sorted))
             (if (null? rest) r
                 (begin (vector-set! vs i (car rest)) (loop (+ i 1) (cdr rest)))))))
        (else py-none)))
(define (py-m-reverse r)
  (cond ((py-array? r) (py-array-method-h 'reverse r '()))
        ((py-glist? r) (py-glist-reverse! r))
        (else py-none)))
(define (py-m-append r v)
  (if (py-array? r) (py-array-append-h r v) (py-list-append r v)))

(define (py-m-extend r o)
  (cond ((py-array? r) (py-array-method-h 'extend r (list o)))
        ((py-glist? r) (py-glist-extend! r o))
        (else py-none)))
(define (py-m-insert r i v)
  (cond ((py-array? r) (py-array-method-h 'insert r (list i v)))
        ((py-glist? r) (py-glist-insert! r i v))
        (else py-none)))
(define (py-m-remove r v)
  (cond ((py-array? r) (py-array-method-h 'remove r (list v)))
        ((py-glist? r) (py-glist-remove! r v))
        (else py-none)))

(define (py-m-index r v)
  (cond ((py-array? r) (py-array-method-h 'index r (list v)))
        ((py-glist? r) (py-glist-index r v))
        (else -1)))
(define (py-m-count r v)
  (cond ((py-array? r) (py-array-method-h 'count r (list v)))
        ((py-glist? r) (py-glist-count r v))
        (else 0)))

(define (py-len x)
  "CPython len()：按实际类型分派"
  (cond ((py-array? x) (py-array-len-h x))
        ((hashtable? x) (dict-length x))
        ((string? x) (string-length x))
        ((py-tuple? x) (py-tuple-len x))
        ((py-glist? x) (py-glist-n x))
        ((vector? x) (vector-length x))
        ((tagged-array? x) (tagged-array-len x))
        ((list? x) (length x))
        ((py-none? x) 0)
        (else 0)))

;; ====== 字符串工具（纯 Scheme，不依赖 Chez 扩展） ======

(define (string-split s sep-char)
  "按字符拆分字符串"
  (let ((len (string-length s)))
    (let loop ((i 0) (start 0) (result '()))
      (cond ((>= i len)
             (reverse (if (< start len)
                         (cons (substring s start len) result)
                         result)))
            ((char=? (string-ref s i) sep-char)
             (loop (+ i 1) (+ i 1)
                   (cons (substring s start i) result)))
            (else (loop (+ i 1) start result))))))

(define (str-find s sub . start)
  "查找子串位置（返回 #f 或索引），可选 start 参数"
  (let ((start-idx (if (pair? start) (car start) 0))
        (s-len (string-length s))
        (sub-len (string-length sub)))
    (let loop ((i start-idx))
      (cond ((> i (- s-len sub-len)) #f)
            ((string=? (substring s i (+ i sub-len)) sub) i)
            (else (loop (+ i 1)))))))

(define (string-any pred s)
  "检查是否有任意字符满足谓词"
  (let loop ((i 0))
    (and (< i (string-length s))
         (or (pred (string-ref s i))
             (loop (+ i 1))))))

(define (string-join parts sep)
  "连接字符串列表"
  (if (null? parts) ""
      (let loop ((rest (cdr parts)) (result (car parts)))
        (if (null? rest) result
            (loop (cdr rest) (string-append result sep (car rest)))))))

(define (string-replace s old new)
  "替换所有子串"
  (let ((old-len (string-length old)))
    (let loop ((i 0) (result '()))
      (let ((pos (str-find s old i)))
        (if pos
            (loop (+ pos old-len)
                  (cons new (cons (substring s i pos) result)))
            (apply string-append
                   (reverse (cons (substring s i (string-length s)) result))))))))

;; ====== 字符串工具（对外的简单包装） ======
(define (str-split s sep)
  "按分隔符拆分字符串"
  (let ((sep-len (string-length sep)))
    (let loop ((i 0) (result '()))
      (let ((pos (str-find s sep i)))
        (if pos
            (loop (+ pos sep-len)
                  (cons (substring s i pos) result))
            (reverse (cons (substring s i (string-length s)) result)))))))

(define (str-join parts sep)
  "用分隔符连接字符串列表或 vector"
  (if (vector? parts)
      (let ((n (vector-length parts)))
        (let loop ((i 0) (result ""))
          (if (>= i n)
              result
              (loop (+ i 1)
                    (if (= i 0)
                        (vector-ref parts i)
                        (string-append result sep (vector-ref parts i)))))))
      (string-join parts sep)))

(define (str-trim s)
  "去除首尾空白"
  (let ((len (string-length s)))
    (let ((start (do ((i 0 (+ i 1))) ((or (>= i len) (not (char-whitespace? (string-ref s i)))) i)))
          (end (do ((i (- len 1) (- i 1))) ((or (< i 0) (not (char-whitespace? (string-ref s i)))) (+ i 1)))))
      (if (>= start end) "" (substring s start end)))))

(define (str-lower s)
  "转小写"
  (string-downcase s))

(define (str-upper s)
  "转大写"
  (string-upcase s))

(define (str-replace s old new)
  "替换所有子串"
  (let loop ((i 0) (result '()))
    (let ((pos (str-find s old i)))
      (if pos
          (loop (+ pos (string-length old))
                (cons new (cons (substring s i pos) result)))
          (apply string-append (reverse (cons (substring s i (string-length s)) result)))))))

(define (str-contains? s sub)
  "检查是否包含子串"
  (not (not (str-find s sub))))

(define (str-starts-with? s prefix)
  "检查是否以 prefix 开头"
  (and (>= (string-length s) (string-length prefix))
       (string=? (substring s 0 (string-length prefix)) prefix)))

(define (str-ends-with? s suffix)
  "检查是否以 suffix 结尾"
  (and (>= (string-length s) (string-length suffix))
       (string=? (substring s (- (string-length s) (string-length suffix)) (string-length s)) suffix)))

;; ====== 字符串转数字（用于读取数据文件） ======
(define (string_to_float s)
  (let ((n (string->number s)))
    (if n (inexact n) 0.0)))

(define (string_to_int s)
  (or (string->number s) 0))

(define (string_of_int n)
  (number->string (exact n)))

;; 码点 -> 单字符字符串（词法器解码 \xHH / \uXXXX 用）
(define (integer_to_char n)
  (if (and (integer? n) (>= n 0) (<= n #x10FFFF))
      (string (integer->char n))
      ""))

;; 单字符字符串 -> 码点（integer_to_char 的逆；空串返回 -1）
(define (char_code c)
  (if (and (string? c) (> (string-length c) 0))
      (char->integer (string-ref c 0))
      -1))

;; formats a float to fixed decimal places
(define (format_float f digits)
  (format "~,vf" digits (inexact f)))

;; 精确定点十进制（与 CPython '%.Nf' 一致：二进制精确值 + 半偶舍入）
(define (float_fixed x digits)
  (cond
    ((nan? x) "nan")
    ((infinite? x) (if (> x 0) "inf" "-inf"))
    (else
     (let* ((neg (negative? x))
            (sc (* (exact (abs (inexact x))) (expt 10 digits)))
            (num (numerator sc))
            (den (denominator sc))
            (q (quotient num den))
            (r (- num (* q den)))
            (r2 (* 2 r))
            (q (if (or (> r2 den) (and (= r2 den) (odd? q))) (+ q 1) q))
            (ds0 (number->string (abs q)))
            (need (+ digits 1))
            (ds (string-append (make-string (max 0 (- need (string-length ds0))) #\0) ds0))
            (n (string-length ds))
            (ip (substring ds 0 (- n digits)))
            (fp (substring ds (- n digits) n))
            (mag (if (> digits 0) (string-append ip "." fp) ip)))
       (if (and neg (> q 0)) (string-append "-" mag) mag)))))


(define (list_length v)
  (cond ((string? v) (string-length v))
        ((vector? v) (vector-length v))
        ((py-glist? v) (py-glist-n v))
        (else (length v))))

(define (list_ref v i)
  (cond ((string? v) (string-ref v i))
        ((vector? v) (vector-ref v i))
        ((py-glist? v) (py-glist-ref v i))
        (else (list-ref v i))))

(define (vec_ref v i)
  (vector-ref v i))
(define re_match (lambda (p s) (re-match p s)))
(define re_search (lambda (p s) (re-search p s)))
(define exit_program (lambda (code) (exit-program code)))
(define json_loads (lambda (s) (json-loads s)))
(define json_dumps (lambda (obj) (json->string obj)))
(define parse_json (lambda (s) (parse-json s)))
(define now_ts (lambda () (datetime-now)))
(define format_time (lambda (ts fmt) (datetime-format ts fmt)))
(define csv_parse (lambda (s) (csv-parse s)))
(define csv_encode (lambda (fields) (csv-encode fields)))
(define str_split (lambda (s sep) (str-split s sep)))
(define str_join (lambda (parts sep) (str-join parts sep)))
(define str_trim (lambda (s) (str-trim s)))
(define str_lower (lambda (s) (str-lower s)))
(define str_upper (lambda (s) (str-upper s)))
(define str_replace (lambda (s old new) (str-replace s old new)))
(define str_contains (lambda (s sub) (str-contains? s sub)))
(define str_starts_with (lambda (s prefix) (str-starts-with? s prefix)))
(define str_ends_with (lambda (s suffix) (str-ends-with? s suffix)))
(define str_length (lambda (s) (string-length s)))
(define str_slice (lambda (s start end) (slice-string s start end)))

(define (slice-array src start end)
  "从 tagged-array 或 vector 切片 [start, end)，返回新 vector"
  (let* ((len (- end start))
         (dst (make-vector len)))
    (do ((i 0 (+ i 1))) ((= i len) dst)
      (vector-set! dst i (if (vector? src)
                             (vector-ref src (+ start i))
                             (float-array-ref src (+ start i)))))))

(define (py-str-ref s i)
  "s[i]：负下标从尾部数，越界 → None（与 list 下标一致）"
  (let ((j (py-idx (string-length s) i)))
    (if j (string (string-ref s j)) py-none)))

(define (slice-string s start end)
  "字符串切片 [start, end)；按 Python 规则折算负下标并截断到 [0, len]"
  (let* ((n (string-length s))
         (a (if (< start 0) (+ n start) start))
         (b (if (< end 0) (+ n end) end))
         (a (if (< a 0) 0 a))
         (b (if (> b n) n b))
         (a (if (> a n) n a))
         (b (if (< b 0) 0 b)))
    (if (fx>= a b) "" (substring s a b))))

;; ====== Python 风格 repr（与 CPython 逐字符对齐） ======
;; print() 输出对齐 CPython：字符串单引号、列表 [..]、dict {...}、
;; 浮点用 repr(float) 的最短往返表示（1e+21 / 1e-05 / 100.0）。

(define (py-split-on-char s ch)
  (let loop ((i 0))
    (cond ((fx= i (string-length s)) (list s ""))
          ((char=? (string-ref s i) ch)
           (list (substring s 0 i) (substring s (fx+ i 1) (string-length s))))
          (else (loop (fx+ i 1))))))

(define (py-digits-only s)
  (list->string
   (filter (lambda (c) (and (char>=? c #\0) (char<=? c #\9)))
           (string->list s))))

;; Chez 对次正规浮点会输出 "5e-324|1" 这类尾注，按 '|' 截断
(define (py-strip-notes s)
  (let loop ((i 0))
    (cond ((fx= i (string-length s)) s)
          ((char=? (string-ref s i) #\|) (substring s 0 i))
          (else (loop (fx+ i 1))))))

;; repr(float)：最短往返数字；-4 < decpt <= 16 用定点，否则指数（指数至少两位）
(define (py-float-repr x)
  (if (nan? x)
      "nan"
      (if (infinite? x)
          (if (> x 0) "inf" "-inf")
          (let* ((raw (py-strip-notes (number->string x)))
                 (neg (char=? (string-ref raw 0) #\-))
                 (body (if neg (substring raw 1 (string-length raw)) raw))
                 (parts (py-split-on-char body #\e))
                 (mant (car parts))
                 (exps (cadr parts))
                 (ex (if (string=? exps "") 0 (string->number exps)))
                 (mparts (py-split-on-char mant #\.))
                 (ip (car mparts))
                 (fp (cadr mparts))
                 (ds (py-digits-only (string-append ip fp)))
                 (decpt (fx+ (string-length ip) ex)))
            (let* ((n (string-length ds))
                   (i0 (let loop ((i 0))
                         (if (and (fx< i (fx- n 1)) (char=? (string-ref ds i) #\0))
                             (loop (fx+ i 1)) i)))
                   (ds1 (substring ds i0 n))
                   (decpt1 (fx- decpt i0))
                   (n1 (string-length ds1))
                   (j1 (let loop ((j n1))
                         (if (and (fx> j 1) (char=? (string-ref ds1 (fx- j 1)) #\0))
                             (loop (fx- j 1)) j)))
                   (d (substring ds1 0 j1))
                   (L (string-length d))
                   (zero (string=? d "0")))
              (let ((out
                     (if (or zero (and (fx> decpt1 -4) (fx<= decpt1 16)))
                         (cond (zero "0.0")
                               ((fx<= decpt1 0)
                                (string-append "0." (make-string (fx* -1 decpt1) #\0) d))
                               ((fx>= decpt1 L)
                                (string-append d (make-string (fx- decpt1 L) #\0) ".0"))
                               (else
                                (string-append (substring d 0 decpt1) "."
                                               (substring d decpt1 L))))
                         (let* ((ex2 (fx- decpt1 1))
                                (exs (number->string (abs ex2)))
                                (exs2 (if (fx< (string-length exs) 2)
                                          (string-append "0" exs) exs)))
                           (string-append (substring d 0 1)
                                          (if (fx> L 1) (string-append "." (substring d 1 L)) "")
                                          "e" (if (fx< ex2 0) "-" "+") exs2)))))
                (if neg (string-append "-" out) out)))))))

;; repr(str)：单引号 + CPython 转义（双引号不转义）
(define (py-str-repr s)
  ;; CPython 选引号：默认单引号；若含 ' 且含 " 则仍用单引号，若含 ' 而无 " 则改用双引号
  (let* ((has-sq (py-str-find s #\'))
         (has-dq (py-str-find s #\"))
         (q (if (and has-sq (not has-dq)) #\" #\'))
         (qstr (string q)))
    (let loop ((i 0) (acc '()))
      (if (fx= i (string-length s))
          (string-append qstr (apply string-append (reverse acc)) qstr)
          (let* ((c (string-ref s i))
                 (piece
                  (cond ((char=? c #\\) "\\\\")
                        ((char=? c q) (string-append "\\" qstr))
                        ((char=? c #\newline) "\\n")
                        ((char=? c #\return) "\\r")
                        ((char=? c #\tab) "\\t")
                        ((or (char<? c (integer->char 32)) (char=? c (integer->char 127)))
                         (string-append "\\x" (py-hex2 (char->integer c))))
                        (else (string c)))))
            (loop (fx+ i 1) (cons piece acc)))))))

(define (py-hex2 n)
  "0..255 -> 两位小写十六进制"
  (let ((digits "0123456789abcdef"))
    (string (string-ref digits (fxand (quotient n 16) 15))
            (string-ref digits (fxand n 15)))))

(define (py-str-find s ch)
  (let loop ((i 0))
    (cond ((fx= i (string-length s)) #f)
          ((char=? (string-ref s i) ch) #t)
          (else (loop (fx+ i 1))))))

;; repr(任意值)
(define (py-str x)
  "str(x)：字符串原样返回，其余用 repr"
  (if (string? x) x (py-repr x)))

(define (py-repr x)
  (cond ((string? x) (py-str-repr x))
        ((boolean? x) (if x "True" "False"))
        ((py-none? x) "None")
        ((and (number? x) (inexact? x)) (py-float-repr x))
        ((number? x) (number->string x))
        ((py-dict? x)
         (string-append "{"
                        (string-join
                         (map (lambda (k)
                                (string-append (py-repr k) ": " (py-repr (py-array-get-h x k))))
                              (py-m-keys x))
                         ", ")
                        "}"))
        ((py-array? x)
         (string-append "["
                        (string-join (map py-repr (vector->list (py-array-items-h x))) ", ")
                        "]"))
        ((py-tuple? x)
         (let ((items (py-tuple-items x)))
           (string-append "("
                          (if (null? items)
                              ""
                              (string-append
                               (string-join (map py-repr items) ", ")
                               (if (null? (cdr items)) "," "")))
                          ")")))
        ((hashtable? x)
         (string-append "{"
                        (string-join
                         (map (lambda (k)
                                (string-append (py-repr k)
                                               ": " (py-repr (hashtable-ref x k #f))))
                              (dict-keys x))
                         ", ")
                        "}"))
        ((list? x) (string-append "[" (string-join (map py-repr x) ", ") "]"))
        ((py-glist? x) (string-append "[" (string-join (map py-repr (py-glist-seq x)) ", ") "]"))
        ((vector? x) (string-append "[" (string-join (map py-repr (vector->list x)) ", ") "]"))
        ((null? x) "None")
        (else (format "~a" x))))

;; ====== 通用打印 ======

(define (print-one x)
  (cond ((string? x) (display x))
        ((and (number? x) (inexact? x)) (display (py-float-repr x)))
        ((number? x) (display (number->string x)))
        ((boolean? x) (display (if x "True" "False")))
        ((null? x) (display "None"))
        (else (display (py-repr x)))))

;; 多参数打印：print(a, b, c) -> 空格分隔 + 换行（与 CPython 一致）
(define (print . args)
  (unless (null? args)
    (print-one (car args))
    (let loop ((rest (cdr args)))
      (unless (null? rest)
        (display " ")
        (print-one (car rest))
        (loop (cdr rest)))))
  (newline))

;; ====== 类型化数组/vector 工具 ======
(define (make_int_array n)
  "创建 n 个 int32 的 C 数组，自动 GC 回收"
  (let ((ptr (foreign-alloc (if (fx= n 0) 4 (fx* n 4)))))
    (do ((i 0 (+ i 1))) ((= i n))
      (foreign-set! 'integer-32 ptr (* i 4) 0))
    (gc-register-ptr ptr)
    ptr))

(define (int_array_set ptr i val)
  (foreign-set! 'integer-32 ptr (* i 4) val))

(define (int_array_ref ptr i)
  (foreign-ref 'integer-32 ptr (* i 4)))

;; ====== Option / Result 类型 ======

(define (Ok v) (vector 'ok v))
(define (Error e) (vector 'error e))
(define (Some v) (vector 'some v))
(define (None) (vector 'none))

(define (is_ok r) (eq? (vector-ref r 0) 'ok))
(define (is_error r) (eq? (vector-ref r 0) 'error))
(define (is_some o) (eq? (vector-ref o 0) 'some))
(define (is_none o) (eq? (vector-ref o 0) 'none))

(define (unwrap r)
  (if (is_ok r)
      (vector-ref r 1)
      (error 'unwrap "called on Error")))

(define (unwrap_or r default)
  (if (is_ok r)
      (vector-ref r 1)
      default))

(define (unwrap_error r)
  (if (is_error r)
      (vector-ref r 1)
      (error 'unwrap-error "called on Ok")))

;; ====== 通用 Pythonic 列表（ heterogeneous vector/list ） ======

(define (py-list . elems)
  "通用列表：可存放任意对象，对应 Python list（vector 表示；
append/insert 首次触发升级为可增长 py-glist）"
  (list->vector elems))

(define (vector->glist-buf v)
  "vector → (容量 2n+8, 有效长度 n) 的 py-glist：之后 append 摊还 O(1)"
  (let* ((n (vector-length v))
         (vs (make-vector (max 8 (* 2 n)) py-none)))
    (do ((i 0 (fx+ i 1))) ((fx>= i n)) (vector-set! vs i (vector-ref v i)))
    (make-py-glist vs n)))

(define (to-glist x)
  "把 list 值（vector / py-glist）转成可增长 py-glist（vector 只拷贝一次）"
  (cond ((py-glist? x) x)
        ((vector? x) (vector->glist-buf x))
        ((py-array? x) (vector->glist-buf (as_list x)))
        (else (py-glist-new))))

(define (py-list-append lst val)
  "在通用列表末尾追加元素（py-glist 原地摊还 O(1)，vector 首次升级拷贝）"
  (cond ((py-array? lst) (py-array-append-h lst val))
        ((py-glist? lst) (py-glist-push! lst val))
        (else (py-glist-push! (to-glist lst) val))))

(define (py-list-concat a b)
  "列表拼接（对应 python list + list），返回新列表"
  (if (or (py-glist? a) (py-glist? b))
      (let ((g (py-glist-copy (to-glist a))))
        (py-glist-extend! g b)
        g)
      (if (or (py-array? a) (py-array? b))
          (py-array-concat-h a b)
          (list->vector (append (py-items a) (py-items b))))))

(define (py-list-ref lst i)
  "读取通用列表第 i 个元素（负下标按 Python 规则折算，越界 → None）"
  (cond ((py-array? lst) (py-array-get-h lst i))
        ((py-glist? lst) (py-glist-ref lst i))
        ;; Scheme 原生 list（如 (argv) 的返回值）也要能按 Python 下标取
        ((list? lst) (let ((j (py-idx (length lst) i)))
                       (if j (list-ref lst j) py-none)))
        (else (let ((j (py-idx (vector-length lst) i)))
                (if j (vector-ref lst j) py-none)))))

(define (py-list-length lst)
  "通用列表长度"
  (cond ((py-array? lst) (py-array-len-h lst))
        ((py-glist? lst) (py-glist-n lst))
        ((list? lst) (length lst))
        (else (vector-length lst))))

(define (list->py-list lst)
  "把 Scheme list 转为通用列表"
  (list->vector lst))

;; ====== list() / dict() 构造器（plugins/pyarray 载入后覆盖成 C 版） ======
(define (new_list . args)
  "list()：vector 表示（append 首次触发升级为 py-glist，之后摊还 O(1)）；
np 插件可覆盖成 PyArray 版"
  (list->vector args))

(define (new_dict . kvs)
  "dict()：未挂 PyArray 时退化为保序 hashtable"
  (let ((d (make-dict)))
    (if (and (pair? kvs) (hashtable? (car kvs)))
        (for-each (lambda (k) (dict-set! d k (hashtable-ref (car kvs) k #f)))
                  (dict-keys (car kvs))))
    d))

(define (as_list x)
  "list(x)：vector/list/string/py-map 键 → 通用列表"
  (cond ((py-glist? x) x)
        ((or (py-array? x) (vector? x)) x)
        ((string? x) (list->vector (map (lambda (c) (string c)) (string->list x))))
        ((list? x) (list->vector x))
        ((hashtable? x) (list->vector (dict-keys x)))
        (else (vector))))

(define (as_dict x)
  "dict(x)：hashtable 原样，其余建空表"
  (if (hashtable? x) x (make-dict)))

;; ====== 兼容 py-list 的 append 方法调用 ======
(define (py-list-append-mut! lst val)
  "错误：通用列表当前实现不可变；请使用 py-list-append 返回新列表"
  (error 'py-list-append-mut! "mutable py-list not supported yet"))

;; 为 translator 生成的 object-vector 预留别名
(define obj-list py-list)
(define obj-list-append py-list-append)
(define obj-list-ref py-list-ref)
(define obj-list-length py-list-length)
(define list_append_str py-list-append)
(define tuple_ref vector-ref)

;; ====== 推导式支持（dict/set/list comprehension 共用） ======

;; tagged array 兜底：np 插件（plugins/np/runtime.scm）会覆盖成自己的定义。
;; 判定用「首元素不是数」区分 #(ptr n) 与普通 py-list #(1 2)，避免误判。
(define (py-tagged-array? x)
  (and (vector? x)
       (= (vector-length x) 2)
       (not (number? (vector-ref x 0)))
       (integer? (vector-ref x 1))))

(define (py-tagged-array-data a) (vector-ref a 0))
(define (py-tagged-array-len a) (vector-ref a 1))

;; 无条件提供；np 插件在 bundle 里后加载，会覆盖成它自己的更宽松版本。
(define (tagged-array? x) (py-tagged-array? x))
(define (tagged-array-data a) (py-tagged-array-data a))
(define (tagged-array-len a) (py-tagged-array-len a))

(define (py-tagged->list x)
  (guard (e (#t (list x)))
    (let ((n (tagged-array-len x))
          (d (tagged-array-data x)))
      (let loop ((i 0) (acc '()))
        (if (>= i n) (reverse acc)
            (loop (+ i 1) (cons (float-array-ref d i) acc)))))))

(define (py-iter->list x)
  "把 Python 可迭代对象归一成 Scheme list：py-list/vector、str、list、pair、
   tagged array(#(ptr n))、单值兜底"
  (cond ((py-tuple? x) (py-tuple-items x))
        ((py-glist? x) (py-glist-seq x))
        ((py-tagged-array? x) (py-tagged->list x))
        ((vector? x) (vector->list x))
        ((string? x) (string->list x))
        ((list? x) x)
        ((null? x) '())
        ((pair? x) (list x))
        (else (list x))))

;; ====== Python 内建：sum / min / max / sorted / enumerate / zip / any / all ======
;; 元素级迭代源：把任意 Python 可迭代对象摊成 Scheme list（逐元素，与 CPython 迭代一致）
(define (py-items x)
  (cond ((py-array? x) (vector->list (py-array-items-h x)))
        ((py-tuple? x) (py-tuple-items x))
        ((py-glist? x) (py-glist-seq x))
        ((py-tagged-array? x) (py-tagged->list x))
        ;; Python 迭代 str 得到"1 字符的 str"，不是 Scheme 的 char
        ((string? x) (map string (string->list x)))
        ((vector? x) (vector->list x))
        ((pair? x) (list x))
        ((null? x) '())
        (else (list x))))

;; Python 的 < ：数值（int/float 混合）与字符串可比；其余不可比
(define (py-cmp-lt? a b)
  (cond ((and (number? a) (number? b)) (< a b))
        ((and (string? a) (string? b)) (string<? a b))
        (else #f)))

(define (py-sum seq . start)
  "sum(iterable[, start])"
  (let loop ((rest (py-items seq)) (acc (if (null? start) 0 (car start))))
    (if (null? rest) acc (loop (cdr rest) (+ acc (car rest))))))

(define (py-extremum better? args who)
  "min/max 共用：单参=可迭代；多参=逐值比较（CPython 语义）"
  (if (null? args)
      (error who "expected at least 1 argument, got 0")
      (let ((src (if (null? (cdr args)) (py-items (car args)) args)))
        (if (null? src)
            (error who "arg is an empty sequence")
            (let loop ((rest (cdr src)) (best (car src)))
              (cond ((null? rest) best)
                    ((better? (car rest) best) (loop (cdr rest) (car rest)))
                    (else (loop (cdr rest) best))))))))

(define (py-min . args) (py-extremum py-cmp-lt? args "min"))
(define (py-max . args) (py-extremum (lambda (a b) (py-cmp-lt? b a)) args "max"))

(define (py-sorted seq . opts)
  "sorted(iterable[, key][, reverse])：稳定排序（Chez list-sort 为归并，稳定）"
  (let* ((keyf (if (pair? opts) (car opts) #f))
         (rev  (if (and (pair? opts) (pair? (cdr opts))) (py-truthy (cadr opts)) #f))
         (kfn  (if (procedure? keyf) keyf (lambda (e) e)))
         (less (lambda (a b) (py-cmp-lt? (kfn a) (kfn b))))
         (out  (list-sort (if rev (lambda (a b) (less b a)) less) (py-items seq))))
    (apply py-list out)))

(define (py-enumerate seq . start)
  "enumerate(iterable[, start]) → [(i, v), ...]（元素为 Python tuple）"
  (let ((s (if (null? start) 0 (car start))))
    (let loop ((rest (py-items seq)) (i s) (acc '()))
      (if (null? rest) (apply py-list (reverse acc))
          (loop (cdr rest) (+ i 1) (cons (py-tuple i (car rest)) acc))))))

(define (py-zip . seqs)
  "zip(*iterables) → [(a, b, ...), ...]，长度取最短"
  (if (null? seqs)
      (apply py-list '())
      (let loop ((cols (map py-items seqs)) (acc '()))
        (if (exists null? cols)
            (apply py-list (reverse acc))
            (loop (map cdr cols)
                  (cons (apply py-tuple (map car cols)) acc))))))

(define (py-any seq)
  "any(iterable)"
  (let loop ((rest (py-items seq)))
    (cond ((null? rest) #f)
          ((py-truthy (car rest)) #t)
          (else (loop (cdr rest))))))

(define (py-all seq)
  "all(iterable)"
  (let loop ((rest (py-items seq)))
    (cond ((null? rest) #t)
          ((py-truthy (car rest)) (loop (cdr rest)))
          (else #f))))

(define (py-list-slice v start end)
  "py-list/vector 切片 [start,end)；end 为负数时从尾部数。返回 py-list"
  (let* ((lst (if (py-glist? v) (py-glist-seq v) (vector->list v)))
         (n (length lst))
         (hi (if (< end 0) (+ n end) end)))
    (list->vector (if (<= hi start) '()
                      (list-head (list-tail lst start) (- hi start))))))

(define (py-unpack e i)
  "多目标解包的取第 i 项：tuple / vector / 点对 (a . b) / 其它按单值"
  (cond ((py-tuple? e) (py-tuple-ref e i))
        ((py-glist? e) (py-glist-ref e i))
        ((vector? e) (vector-ref e i))
        ((pair? e) (if (= i 0) (car e) (cdr e)))
        (else e)))

;; ====== 文件 I/O ======

;; 加载 libc
(load-shared-object "libc.so.6")

(define libc-fopen
  (foreign-procedure "fopen" (string string) void*))
(define libc-fclose
  (foreign-procedure "fclose" (void*) int))
(define libc-fread
  (foreign-procedure "fread" (void* unsigned-64 unsigned-64 void*) unsigned-64))
(define libc-fwrite
  (foreign-procedure "fwrite" (void* unsigned-64 unsigned-64 void*) unsigned-64))
(define libc-fprintf
  (foreign-procedure "fprintf" (void* string) int))
(define libc-fgets
  (foreign-procedure "fgets" (void* int void*) void*))

(define (file-open path mode)
  "打开文件，返回文件指针"
  (libc-fopen path mode))

(define (file-close fp)
  "关闭文件"
  (libc-fclose fp))

(define (file-write fp s)
  "写入字符串到文件"
  (let* ((bv (string->utf8 s))
         (len (bytevector-length bv))
         (buf (foreign-alloc len)))
    ;; Copy bytevector to C memory
    (do ((i 0 (+ i 1))) ((= i len))
      (foreign-set! 'unsigned-8 buf i (bytevector-u8-ref bv i)))
    (libc-fwrite buf 1 len fp)
    (foreign-free buf)))

(define (file-read-all fp)
  "读取整个文件内容（先攒字节再一次性 UTF-8 解码，避免多字节字符跨块被撕成 U+FFFD）"
  (let* ((buf-size 65536)
         (buf (foreign-alloc buf-size))
         (chunks '())
         (total 0))
    (let loop ()
      (let ((n (libc-fread buf 1 buf-size fp)))
        (when (> n 0)
          (let ((bv (make-bytevector n 0)))
            (do ((i 0 (+ i 1))) ((= i n))
              (bytevector-u8-set! bv i (foreign-ref 'unsigned-8 buf i)))
            (set! chunks (cons bv chunks))
            (set! total (+ total n)))
          (loop))))
    (foreign-free buf)
    (let ((all (make-bytevector total 0)))
      (let loop2 ((cs chunks) (pos total))
        (when (pair? cs)
          (let* ((bv (car cs)) (n (bytevector-length bv)))
            (do ((i 0 (+ i 1))) ((= i n))
              (bytevector-u8-set! all (+ (- pos n) i) (bytevector-u8-ref bv i)))
            (loop2 (cdr cs) (- pos n)))))
      (utf8->string all))))

(define (file-exists? path)
  "检查文件是否存在"
  (let ((fp (libc-fopen path "r")))
    (when fp (libc-fclose fp))
    (not (not fp))))

;; ====== 日期时间（libc） ======
(define libc-time
  (foreign-procedure "time" (void*) unsigned-64))
(define libc-localtime
  (foreign-procedure "localtime" (void*) void*))
(define libc-strftime
  (foreign-procedure "strftime" (void* unsigned-64 string void*) unsigned-64))
(define libc-mktime
  (foreign-procedure "mktime" (void*) unsigned-64))

(define (datetime-now)
  "当前时间（Unix 时间戳）"
  (libc-time 0))

(define (datetime-format timestamp fmt)
  "格式化时间戳，fmt 如 '%Y-%m-%d %H:%M:%S'"
  (let* ((t (foreign-alloc 8))
         (_ (foreign-set! 'unsigned-64 t 0 timestamp))
         (tm (libc-localtime t))
         (buf-size 256)
         (buf (foreign-alloc buf-size)))
    (let ((n (libc-strftime buf buf-size fmt tm)))
      (let ((bv (make-bytevector n 0)))
        (do ((i 0 (+ i 1))) ((= i n))
          (bytevector-u8-set! bv i (foreign-ref 'unsigned-8 buf i)))
        (foreign-free buf)
        (foreign-free t)
        (utf8->string bv)))))

(define (datetime-str->ts s fmt)
  "解析时间字符串 → 时间戳，fmt 如 '%Y-%m-%d'"
  ;; 简化为 strptime 的 FFI
  ;; 当前返回当前时间戳
  (libc-time 0))

;; ====== 操作系统接口（libc） ======

(define libc-opendir (foreign-procedure "opendir" (string) void*))
(define libc-readdir (foreign-procedure "readdir" (void*) void*))
(define libc-closedir (foreign-procedure "closedir" (void*) int))
(define libc-mkdir (foreign-procedure "mkdir" (string int) int))
(define libc-rmdir (foreign-procedure "rmdir" (string) int))
(define libc-unlink (foreign-procedure "unlink" (string) int))
(define libc-rename (foreign-procedure "rename" (string string) int))
(define libc-getcwd (foreign-procedure "getcwd" (void* unsigned-64) void*))
(define libc-chdir (foreign-procedure "chdir" (string) int))
(define libc-getenv (foreign-procedure "getenv" (string) void*))
(define libc-stat (foreign-procedure "stat" (string void*) int))
(define libc-system (foreign-procedure "system" (string) int))
(define libc-access (foreign-procedure "access" (string int) int))

(define (os-list-dir path)
  (let ((dir (libc-opendir path)))
    (if dir
        (let loop ((acc '()))
          (let ((entry (libc-readdir dir)))
            (if (not (eq? entry 0))
                ;; d_name is at offset 19 in struct dirent on Linux x86_64
                (let ((name (c-str->string (+ entry 19))))
                  (loop (cons name acc)))
                (begin (libc-closedir dir) (reverse acc)))))
        '())))

(define (c-str->string ptr)
  "将 C 字符串（null-terminated）转为 Scheme string"
  (let loop ((i 0) (chars '()))
    (let ((c (foreign-ref 'unsigned-8 ptr i)))
      (if (= c 0)
          (list->string (map integer->char (reverse chars)))
          (loop (+ i 1) (cons c chars))))))

(define (os-getenv name)
  (let ((ptr (libc-getenv name)))
    (if (not (eq? ptr 0))
        (c-str->string ptr)
        "")))

(define (os-getcwd)
  (let ((buf (foreign-alloc 4096)))
    (let ((ptr (libc-getcwd buf 4096)))
      (if (not (eq? ptr 0))
          (let ((result (c-str->string buf)))
            (foreign-free buf)
            result)
          (begin (foreign-free buf) #f)))))

(define (os-file-size path)
  (let ((buf (foreign-alloc 128)))
    (let ((res (libc-stat path buf)))
      (if (= res 0)
          (let ((size (foreign-ref 'unsigned-64 buf 48)))
            (foreign-free buf) size)
          (begin (foreign-free buf) -1)))))

(define (os-file-exists? path) (= (libc-access path 0) 0))
(define (os-move-file src dst) (= (libc-rename src dst) 0))
(define (os-delete-file path) (= (libc-unlink path) 0))
(define (os-mkdir path) (= (libc-mkdir path 511) 0))
(define (os-rmdir path) (= (libc-rmdir path) 0))
(define (os-shell cmd) (libc-system cmd))
(define (os_shell cmd) (os-shell cmd))
(define (os_cwd) (os-getcwd))
(define (os_list_dir path) (os-list-dir path))
(define (os_getenv name) (os-getenv name))
(define (os_file_size path) (os-file-size path))
(define (os_file_exists path) (os-file-exists? path))
(define (os_move_file src dst) (os-move-file src dst))
(define (os_delete_file path) (os-delete-file path))
(define (os_mkdir path) (os-mkdir path))
(define (os_rmdir path) (os-rmdir path))

;; ====== 时间（libc） ======
(define libc-nanosleep
  (foreign-procedure "nanosleep" (void* void*) int))

(define (sleep seconds)
  "休眠 seconds 秒"
  (let* ((sec (inexact->exact (floor seconds)))
         (nsec (inexact->exact (* (- seconds (floor seconds)) 1e9)))
         (ts (foreign-alloc 16)))
    (foreign-set! 'unsigned-64 ts 0 sec)
    (foreign-set! 'unsigned-64 ts 8 nsec)
    (libc-nanosleep ts 0)
    (foreign-free ts)))

(define (clock) (libc-time 0))

;; ====== 命令行参数 ======
(define True #t)
(define False #f)
(define (argv)
  "返回命令行参数列表"
  (command-line))

(define libc-exit (foreign-procedure "exit" (int) void))

(define (exit-program code)
  "退出程序"
  (libc-exit code))

;; C ABI 包装（下划线风格，供 StaticPy 调用）
(define http_get_simple (lambda (url) (http-get-simple url)))
(define random_float (lambda () (random-float)))
(define random_int (lambda () (random-int)))
(define random_range (lambda (low high) (random-range low high)))
(define random_randint (lambda (low high) (random-randint low high)))
(define random_uniform (lambda (low high) (random-uniform low high)))
(define random_choice (lambda (seq) (random-choice seq)))
(define random_seed (lambda (seed) (random-seed seed)))

;; ====== HTTP 客户端（基于 libcurl） ======

(load-shared-object "libcurl.so.4")

;; Curl easy handle
(define curl-easy-init
  (foreign-procedure "curl_easy_init" () void*))
(define curl-easy-setopt-string
  (foreign-procedure "curl_easy_setopt" (void* unsigned-32 string) int))
(define curl-easy-setopt-ptr
  (foreign-procedure "curl_easy_setopt" (void* unsigned-32 void*) int))
(define curl-easy-perform
  (foreign-procedure "curl_easy_perform" (void*) int))
(define curl-easy-cleanup
  (foreign-procedure "curl_easy_cleanup" (void*) void))
(define curl-easy-getinfo-string
  (foreign-procedure "curl_easy_getinfo" (void* unsigned-32 void*) int))

;; Curl slist
(define curl-slist-append
  (foreign-procedure "curl_slist_append" (void* string) void*))
(define curl-slist-free-all
  (foreign-procedure "curl_slist_free_all" (void*) void))

;; Option constants
(define CURLOPT_URL 10002)
(define CURLOPT_WRITEFUNCTION 20011)
(define CURLOPT_WRITEDATA 10001)
(define CURLOPT_HTTPHEADER 10023)
(define CURLOPT_TIMEOUT 13)

;; 全局 write callback（被 C 调用，收集响应数据到字节向量）
(define *http-response-buffer* #f)
(define *http-response-callback*
  (foreign-callable
    (lambda (ptr size nmemb userdata)
      (let* ((total (* size nmemb))
             (bv (make-bytevector total 0)))
        (do ((i 0 (+ i 1))) ((= i total))
          (bytevector-u8-set! bv i (foreign-ref 'unsigned-8 ptr i)))
        (set! *http-response-buffer*
              (cons bv *http-response-buffer*))
        total))
    (void* unsigned-64 unsigned-64 void*) unsigned-64))

(define (http-get url)
  "HTTP GET 请求，返回 (status . body)"
  (let* ((curl (curl-easy-init))
         (callback-ptr (foreign-callable-entry-point *http-response-callback*)))
    ;; 设置 URL
    (curl-easy-setopt-string curl CURLOPT_URL url)
    ;; 设置 write callback
    (curl-easy-setopt-ptr curl CURLOPT_WRITEFUNCTION callback-ptr)
    ;; 超时 30 秒
    (curl-easy-setopt-ptr curl CURLOPT_TIMEOUT 30)
    ;; 执行请求
    (set! *http-response-buffer* '())
    (let ((res (curl-easy-perform curl)))
      ;; 读取响应
      (let* ((parts (reverse *http-response-buffer*))
             (body (apply string-append (map utf8->string parts))))
        (curl-easy-cleanup curl)
        (cons res body)))))

(define (http-get-simple url)
  "HTTP GET，返回 body 字符串"
  (let ((result (http-get url)))
    (cdr result)))

;; C ABI 包装（供 extern fn from "prelude" 调用）
(define make_float_array (lambda (n) (make-float-array n)))
(define float_array_set (lambda (ptr i val) (float-array-set ptr i val)))
(define float_array_ref (lambda (ptr i) (float-array-ref ptr i)))
(define make_dict (lambda () (make-dict)))
(define dict_get (lambda (d key) (dict-get d key)))
(define dict_set (lambda (d key val) (dict-set! d key val)))
(define file_open (lambda (path mode) (file-open path mode)))
(define file_close (lambda (fp) (file-close fp)))
(define file_read_all (lambda (fp) (file-read-all fp)))
(define file_write (lambda (fp s) (file-write fp s)))
(define file_exists (lambda (path) (file-exists? path)))
(define http_get_simple (lambda (url) (http-get-simple url)))

(define (print-float-array ptr n)
  (display "#float[")
  (let loop ((i 0))
    (when (< i n)
      (when (> i 0) (display " "))
      (display (float-array-ref ptr i))
      (loop (+ i 1))))
  (display "]")
  (newline))

;; ====== 数学函数（libm） ======
(load-shared-object "libm.so.6")
(define libm-sin   (foreign-procedure "sin" (double) double))
(define libm-cos   (foreign-procedure "cos" (double) double))
(define libm-tan   (foreign-procedure "tan" (double) double))
(define libm-log   (foreign-procedure "log" (double) double))
(define libm-log2  (foreign-procedure "log2" (double) double))
(define libm-log10 (foreign-procedure "log10" (double) double))
(define libm-exp   (foreign-procedure "exp" (double) double))
(define libm-sqrt  (foreign-procedure "sqrt" (double) double))
(define libm-floor (foreign-procedure "floor" (double) double))
(define libm-ceil  (foreign-procedure "ceil" (double) double))
(define libm-round (foreign-procedure "round" (double) double))
(define libm-pow   (foreign-procedure "pow" (double double) double))
(define libm-fmod  (foreign-procedure "fmod" (double double) double))
(define libm-sinh  (foreign-procedure "sinh" (double) double))
(define libm-cosh  (foreign-procedure "cosh" (double) double))
(define libm-tanh  (foreign-procedure "tanh" (double) double))
(define libm-atan2 (foreign-procedure "atan2" (double double) double))
(define libm-asin  (foreign-procedure "asin" (double) double))
(define libm-acos  (foreign-procedure "acos" (double) double))
(define libm-atan  (foreign-procedure "atan" (double) double))

;; ====== JSON 解析（libjansson） ======
(define *json-available* #f)
(guard (e (else (display "Warning: libjansson not found, json disabled\n")))
  (load-shared-object "libjansson.so.4")
  (set! *json-available* #t))

(define json-loads-ptr #f)
(define json-dumps-ptr #f)
(when *json-available*
  (set! json-loads-ptr
    (foreign-procedure "json_loads" (string int void*) void*))
  (set! json-dumps-ptr
    (foreign-procedure "json_dumps" (void* int) string)))

(define (json-loads s)
  "解析 JSON 字符串 → Scheme 值（vector/list/hashtable）"
  (if *json-available*
      (let* ((flags 0)
             (root (json-loads-ptr s flags 0))
             (result (json->scheme root)))
        root
        #f)  ;; 简化处理
      (begin (display "json not available\n") #f)))

(define (json->file obj path)
  "写入 JSON 到文件"
  (let ((s (json-scheme->string obj)))
    (when s
      (let ((fp (libc-fopen path "w")))
        (when fp
          (file-write fp s)
          (libc-fclose fp))))))

(define (parse-json s)
  "解析 JSON 字符串（简化实现，支持基本类型和嵌套 dict/list）"
  (letrec
    ((skip-whitespace
       (lambda (i)
         (let loop ((i i))
           (if (< i (string-length s))
               (let ((c (string-ref s i)))
                 (if (or (char=? c #\space) (char=? c #\newline) 
                         (char=? c #\tab) (char=? c #\return))
                     (loop (+ i 1))
                     i))
               i))))
     (parse-value
       (lambda (i)
         (let ((i (skip-whitespace i)))
           (if (>= i (string-length s)) (values #f i)
             (let ((c (string-ref s i)))
               (cond ((char=? c #\{) (parse-object (+ i 1)))
                     ((char=? c #\[) (parse-array (+ i 1)))
                     ((char=? c #\") (parse-string (+ i 1)))
                     ((char=? c #\t) (values #t (+ i 4)))
                     ((char=? c #\f) (values #f (+ i 5)))
                     ((char=? c #\n) (values '() (+ i 4)))
                     (else (parse-number i))))))))
     (parse-object
       (lambda (i)
         (let ((tbl (make-dict)))
           (let loop ((i i))
             (let ((i (skip-whitespace i)))
               (if (and (< i (string-length s)) (char=? (string-ref s i) #\}))
                   (values tbl (+ i 1))
                   (let*-values (((key i) (parse-value i))
                                 ((i) (skip-whitespace i))
                                 ((i) (if (char=? (string-ref s i) #\:) (+ i 1) i))
                                 ((val i) (parse-value i))
                                 ((i) (skip-whitespace i)))
                     (dict-set! tbl key val)
                     (let ((i (if (char=? (string-ref s i) #\,) (+ i 1) i)))
                       (loop i)))))))))
      (parse-array
       (lambda (i)
         (let loop ((i i) (acc '()))
           (let ((i (skip-whitespace i)))
             (if (and (< i (string-length s)) (char=? (string-ref s i) #\]))
                 (values (list->vector (reverse acc)) (+ i 1))
                 (let*-values (((val i) (parse-value i))
                               ((i) (skip-whitespace i)))
                   (let ((i (if (char=? (string-ref s i) #\,) (+ i 1) i)))
                     (loop i (cons val acc)))))))))

     (parse-string
       (lambda (i)
         (let loop ((i i) (acc '()))
           (if (>= i (string-length s)) (values (list->string (reverse acc)) i)
             (let ((c (string-ref s i)))
               (cond ((char=? c #\") (values (list->string (reverse acc)) (+ i 1)))
                     ((char=? c #\\) (loop (+ i 2) (cons (parse-escape (+ i 1)) acc)))
                     (else (loop (+ i 1) (cons c acc)))))))))
     (parse-escape
       (lambda (i)
         (if (< i (string-length s))
             (case (string-ref s i)
               ((#\n) #\newline) ((#\t) #\tab) ((#\r) #\return)
               ((#\") #\") ((#\\) #\\) ((#\/) #\/)
               (else (string-ref s i)))
             #\?)))
     (parse-number
       (lambda (i)
         (let loop ((i i) (acc '()))
           (if (and (< i (string-length s))
                    (let ((c (string-ref s i)))
                      (or (char-numeric? c) (char=? c #\-) (char=? c #\+)
                          (char=? c #\.) (char=? c #\e) (char=? c #\E))))
               (loop (+ i 1) (cons (string-ref s i) acc))
               (let ((num-str (list->string (reverse acc))))
                 (values (if (str-find num-str ".")
                             (string->number num-str)
                             (string->number num-str))
                         i)))))))
    (call-with-values (lambda () (parse-value 0))
      (lambda (val i) val))))

(define (json->string obj)
  "Scheme 值 → JSON 字符串"
  (cond ((hashtable? obj)
         (let ((keys (dict-keys obj)))
           (string-append "{"
             (string-join
               (map (lambda (k)
                      (string-append "\"" (if (symbol? k) (symbol->string k) k) "\":"
                        (json->string (hashtable-ref obj k #f))))
                  keys)
               ", ")
             "}")))
        ((vector? obj)
         (string-append "["
           (string-join (map json->string (vector->list obj)) ", ") "]"))
        ((py-none? obj) "null")
        ((number? obj) (format "~s" obj))
        ((boolean? obj) (if obj "true" "false"))
        ((string? obj) (string-append "\"" (json-escape-string obj) "\""))
        ((symbol? obj) (string-append "\"" (symbol->string obj) "\""))
        ((null? obj) "null")
        (else (format "~s" obj))))

(define (json-escape-string s)
  "转义 JSON 字符串中的特殊字符"
  (let loop ((i 0) (acc '()))
    (if (>= i (string-length s))
      (list->string (reverse acc))
      (let ((c (string-ref s i)))
        (case c
          ((#\\) (loop (+ i 1) (cons #\\ (cons #\\ acc))))
          ((#\") (loop (+ i 1) (cons #\\ (cons #\" acc))))
          ((#\newline) (loop (+ i 1) (cons #\\ (cons #\n acc))))
          ((#\tab) (loop (+ i 1) (cons #\\ (cons #\t acc))))
          ((#\return) (loop (+ i 1) (cons #\\ (cons #\r acc))))
          (else (loop (+ i 1) (cons c acc))))))))

;; ====== CSV 读写 ======
(define (csv-parse-line line)
  "解析一行 CSV（支持引号转义）"
  (let loop ((i 0) (fields '()) (current '()))
    (if (>= i (string-length line))
        (reverse (cons (list->string (reverse current)) fields))
        (let ((c (string-ref line i)))
          (cond ((char=? c #\,)
                 (loop (+ i 1) (cons (list->string (reverse current)) fields) '()))
                ((char=? c #\")
                 ;; 引号字段
                 (let inner ((j (+ i 1)) (acc '()))
                   (if (>= j (string-length line))
                       (reverse (cons (list->string (reverse acc)) fields))
                       (let ((c2 (string-ref line j)))
                         (if (char=? c2 #\")
                             (if (and (< (+ j 1) (string-length line))
                                      (char=? (string-ref line (+ j 1)) #\"))
                                 (inner (+ j 2) (cons #\" acc))
                                 (loop (+ j 1) 
                                       (cons (list->string (reverse acc)) fields)
                                       current))
                             (inner (+ j 1) (cons c2 acc)))))))
                (else
                 (loop (+ i 1) fields (cons c current))))))))

(define (csv-parse s)
  "解析 CSV 字符串 → list of list"
  (let ((lines (string-split s #\newline)))
    (map csv-parse-line lines)))

(define (csv-encode fields)
  "将字段列表编码为 CSV 行"
  (string-join
    (map (lambda (f)
           (let ((s (if (number? f) (format "~s" f) f)))
             (if (string-any (lambda (c) (or (char=? c #\,) (char=? c #\"))) s)
                 (string-append "\"" (string-replace s "\"" "\"\"") "\"")
                 s)))
         fields)
    ","))

;; ====== 正则表达式（libpcre2） ======
(load-shared-object "libpcre2-8.so.0")

(define pcre-compile
  (foreign-procedure "pcre2_compile_8" (void* unsigned-64 unsigned-32 void* void* void*) void*))
(define pcre-match
  (foreign-procedure "pcre2_match_8" (void* void* unsigned-64 unsigned-64 unsigned-32 void* void*) int))
(define pcre-get-error
  (foreign-procedure "pcre2_get_error_message_8" (int void* unsigned-64) void*))

(define (string->c-ptr s)
  "将 Scheme 字符串复制到 C 内存，返回指针"
  (let* ((bv (string->utf8 s))
         (len (bytevector-length bv))
         (ptr (foreign-alloc (+ len 1))))
    (do ((i 0 (+ i 1))) ((= i len))
      (foreign-set! 'unsigned-8 ptr i (bytevector-u8-ref bv i)))
    (foreign-set! 'unsigned-8 ptr len 0)  ;; null terminator
    ptr))

(define (re-match pattern text)
  "正则匹配，返回 #t/#f"
  (let* ((bv (string->utf8 text))
         (text-len (bytevector-length bv))
         (c-pattern (string->c-ptr pattern))
         (err-ptr (foreign-alloc 8))
         (err-off (foreign-alloc 8))
         (re (pcre-compile c-pattern 0 0 err-ptr err-off 0)))
    (if re
        (let* ((c-text (string->c-ptr text))
               (rc (pcre-match re c-text text-len 0 0 0 0)))
          (foreign-free c-text)
          (foreign-free c-pattern)
          (>= rc 0))
        (begin (foreign-free c-pattern) #f))))

(define (re-search pattern text)
  "搜索，返回匹配位置或 -1"
  (let* ((c-pattern (string->c-ptr pattern))
         (err-ptr (foreign-alloc 8))
         (err-off (foreign-alloc 8))
         (re (pcre-compile c-pattern 0 0 err-ptr err-off 0)))
    (if re
        (let* ((c-text (string->c-ptr text))
               (ovector (foreign-alloc (* 3 8)))
               (rc (pcre-match re c-text (string-length text) 0 0 ovector 0)))
          (foreign-free c-text)
          (if (>= rc 0)
              (foreign-ref 'long ovector 0)
              -1))
        -1)))

;; ====== 随机数（libc） ======
(define libc-rand (foreign-procedure "rand" () int))
(define libc-srand (foreign-procedure "srand" (unsigned-32) void))
(define libc-random (foreign-procedure "random" () long))
(define libc-srandom (foreign-procedure "srandom" (unsigned-32) void))

(define (random-seed seed)
  "设置随机种子"
  (libc-srand seed))

(define (random-int)
  "返回 0..RAND_MAX 的随机整数"
  (libc-rand))

(define (random-float)
  "返回 0.0..1.0 的随机浮点数"
  (/ (inexact (libc-rand)) 2147483647.0))

(define (random-range low high)
  "返回 [low, high) 的随机整数"
  (+ low (remainder (libc-rand) (- high low))))

(define (random-randint low high)
  "返回 [low, high] 的随机整数（Python random.randint 语义）"
  (+ low (remainder (libc-rand) (+ (- high low) 1))))

(define (random-uniform low high)
  "返回 low..high 的随机浮点数"
  (+ low (* (random-float) (- high low))))

(define (random-choice seq)
  "从 vector/list 中随机选择一个元素"
  (let ((n (if (vector? seq) (vector-length seq) (length seq))))
    (if (= n 0)
      #f
      (let ((i (random-range 0 n)))
        (if (vector? seq) (vector-ref seq i) (list-ref seq i))))))

(define pi 3.141592653589793)
(define e 2.718281828459045)

;; ====== IR 节点标签判断（StaticPy 自举编译器用） ======
;; Python 的 isinstance(x, EConst) 在 Scheme 里对应 (ir-tag? x 'EConst)
;; 因为 EConst(x) 被翻译成 (vector 'EConst x)

;; 记录类（define-record-type）的 isinstance：沿父类链比较类型名
(define (ir-record-isa? node tname)
  (let loop ((rtd (record-rtd node)))
    (cond ((not rtd) #f)
          ((eq? (record-type-name rtd) tname) #t)
          (else (loop (record-type-parent rtd))))))

;; 内置类型的 isinstance：isinstance(x, str) -> (ir-tag? x 'str)
;; 早先 ir-tag? 只认记录/标签向量，对 str/int/float 一律返回 #f，
;; 于是 isinstance(any, str) 恒假——调用方（含自举版 emit_lib）会静默走错分支。
(define (ir-builtin-isa? node t)
  (cond ((eq? t 'object) #t)
        ((eq? t 'str) (string? node))
        ((eq? t 'bool) (boolean? node))
        ((eq? t 'int) (and (integer? node) (not (boolean? node))))
        ((eq? t 'float) (flonum? node))
        ((eq? t 'number) (number? node))
        ((eq? t 'list) (vector? node))
        ((eq? t 'tuple) (vector? node))
        ((eq? t 'dict) (hashtable? node))
        ((eq? t 'set) (hashtable? node))
        ((eq? t 'none) (or (py-none? node) (null? node)))
        ((eq? t 'bytes) (string? node))
        (else 'unknown)))

(define (ir-tag? node tag)
  (let ((t (if (string? tag) (string->symbol tag) tag)))
    (cond
     ((not (eq? (ir-builtin-isa? node t) 'unknown)) (ir-builtin-isa? node t))
     ((record? node) (ir-record-isa? node t))
     ((vector? node)
      (and (> (vector-length node) 0)
           (let ((actual (vector-ref node 0)))
             (cond ((and (string? actual) (string? tag))
                    (string=? actual tag))
                   ((string? actual)
                    (eq? (string->symbol actual) t))
                   (else
                    (eq? actual t))))))
     (else #f))))

;; Generic IR field accessor.  Python IR classes are translated to tagged
;; vectors, and different node types store the same field at different
;; indices.  This function dispatches on the tag at runtime.
(define (ir-field node field)
  (let ((f (if (string? field) (string->symbol field) field)))
    (cond
     ;; 记录类：沿父类链按字段名找下标，用 record-accessor 取值
     ((record? node)
      (let loop ((rtd (record-rtd node)))
        (if (not rtd)
            (vector-ref node 1)
            (let* ((names (record-type-field-names rtd))
                   (n (vector-length names))
                   (idx (let scan ((i 0))
                          (cond ((fx>= i n) #f)
                                ((eq? (vector-ref names i) f) i)
                                (else (scan (fx+ i 1)))))))
              (if idx
                  ((record-accessor rtd idx) node)
                  (loop (record-type-parent rtd)))))))
     (else
    (case f
    ((value)
     (cond ((ir-tag? node 'SLet)   (vector-ref node 3))
           ((ir-tag? node 'SSet)   (vector-ref node 2))
           (else                   (vector-ref node 1))))
    ((name)    (vector-ref node 1))
    ((op)      (vector-ref node 1))
    ((left)    (vector-ref node 2))
    ((right)   (vector-ref node 3))
    ((operand) (vector-ref node 2))
    ((func)    (vector-ref node 1))
    ((args)    (vector-ref node 2))
    ((cond_expr cond-expr) (vector-ref node 1))
    ((then_body then-body) (vector-ref node 2))
    ((else_body else-body) (vector-ref node 3))
    ((var)     (vector-ref node 1))
    ((stop)    (vector-ref node 2))
    ((body)
     (cond ((ir-tag? node 'SWhile) (vector-ref node 2))
           ((ir-tag? node 'SFor)   (vector-ref node 3))
           ((ir-tag? node 'IRFunc) (vector-ref node 5))
           (else                   (vector-ref node 2))))
    ((params)
     (cond ((ir-tag? node 'ELambda) (vector-ref node 1))   ; ELambda: (tag params body)
           (else                    (vector-ref node 2))))
    ((param_types param-types) (vector-ref node 3))
    ((ret)         (vector-ref node 4))
    ((ty)          (vector-ref node 2))
    (else          (vector-ref node 1)))))))

