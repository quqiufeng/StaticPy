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

;; ====== 真值判定（CPython 语义） ======
;; Scheme 里只有 #f 是假，而 CPython 里 None / 0 / "" / [] / {} 都是假。
;; 最关键的是 None：它是真实对象，`(not py-none)` 在 Scheme 下是 #f，
;; 直接照搬 `(not (not x))` 会把 `bool(None)` 判成 #t。
(define (py-truthy x)
  (cond ((py-none? x) #f)
        ((eq? x #f) #f)
        ((number? x) (not (zero? x)))
        ((string? x) (> (string-length x) 0))
        ((vector? x) (> (vector-length x) 0))
        ((pair? x) #t)
        ((null? x) #f)
        ((hashtable? x) (> (dict-length x) 0))
        (else #t)))

;; ====== `x in y` 成员判定（按容器类型分派） ======
;; 翻译器只发 `(py-contains? x y)`，语义交给运行时：
;; dict 看键、str 看子串、vector(py-list) 与 Scheme list 逐元素 equal?。
(define (py-contains? needle hay)
  (cond ((hashtable? hay) (dict-contains? hay needle))
        ((string? hay) (str-contains? hay needle))
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
  (reverse (py-dict-order d)))

(define (dict-values d)
  (map (lambda (k) (hashtable-ref d k #f)) (dict-keys d)))

(define (dict-items d)
  (map (lambda (k) (cons k (hashtable-ref d k #f))) (dict-keys d)))

(define (dict-length d)
  (length (py-dict-order d)))

(define (dict-get d key)
  "读取字典 d[key]；缺失 → None"
  (if (hashtable-contains? d key)
      (hashtable-ref d key #f)
      py-none))

(define (dict-get-default d key default)
  "d.get(key, default)"
  (if (hashtable-contains? d key)
      (hashtable-ref d key #f)
      default))

(define (dict-get-or-empty d key)
  "读取字典 d[key]，返回空字符串代替缺失"
  (hashtable-ref d key ""))

(define dict_get_or_empty (lambda (d key) (dict-get-or-empty d key)))

(define (dict-set! d key val)
  "写入字典 d[key] = val（新键追加到末尾）"
  (unless (hashtable-contains? d key)
    (hashtable-set! d py-dict-order-key (cons key (py-dict-order d))))
  (hashtable-set! d key val)
  val)

(define (dict-set-default! d key val)
  "setdefault：键不存在时写入"
  (if (hashtable-contains? d key)
      (hashtable-ref d key #f)
      (dict-set! d key val)))

(define (dict-delete! d key)
  "删除键；存在返回 True"
  (if (hashtable-contains? d key)
      (begin
        (hashtable-set! d py-dict-order-key
                        (let loop ((ks (py-dict-order d)))
                          (cond ((null? ks) '())
                                ((equal? (car ks) key) (loop (cdr ks)))
                                (else (cons (car ks) (loop (cdr ks)))))))
        (hashtable-delete! d key)
        #t)
      #f))

(define (dict-pop d key . default)
  (if (hashtable-contains? d key)
      (let ((v (hashtable-ref d key #f)))
        (dict-delete! d key)
        v)
      (if (null? default) py-none (car default))))

(define (dict-contains? d key)
  "检查 key 是否在字典中（隐藏键不算）"
  (and (hashtable? d)
       (not (eq? key py-dict-order-key))
       (hashtable-contains? d key)))

(define (dict-merge! d other)
  "update：把 other 的键值按序写入 d"
  (for-each (lambda (k) (dict-set! d k (hashtable-ref other k #f)))
            (if (hashtable? other) (dict-keys other) '()))
  d)

(define (dict-copy d)
  "浅拷贝字典（保序）"
  (let ((copy (make-dict)))
    (for-each (lambda (k) (dict-set! copy k (hashtable-ref d k #f)))
              (dict-keys d))
    copy))

;; ====== 真除法 / 长度 ======
;; CPython 的 / 永远返回 float（4/2 → 2.0，1/3 → 0.333…）
(define (py-truediv a b)
  (inexact (/ a b)))

;; 统一迭代源：dict→键、str→字符、vector/list/tagged-array 原样
(define (py-iter-seq x)
  (cond ((hashtable? x) (list->vector (dict-keys x)))
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

(define (py-len x)
  "CPython len()：按实际类型分派"
  (cond ((hashtable? x) (dict-length x))
        ((string? x) (string-length x))
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
        (else (length v))))

(define (list_ref v i)
  (cond ((string? v) (string-ref v i))
        ((vector? v) (vector-ref v i))
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

(define (slice-string s start end)
  "字符串切片 [start, end)"
  (substring s start end))

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
(define (py-repr x)
  (cond ((string? x) (py-str-repr x))
        ((boolean? x) (if x "True" "False"))
        ((py-none? x) "None")
        ((and (number? x) (inexact? x)) (py-float-repr x))
        ((number? x) (number->string x))
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
  "通用列表：可存放任意对象，对应 Python list"
  (list->vector elems))

(define (py-list-append lst val)
  "在通用列表末尾追加元素，返回新列表"
  (list->vector (append (vector->list lst) (list val))))

(define (py-list-concat a b)
  "列表拼接（对应 python list + list），返回新列表"
  (list->vector (append (vector->list a) (vector->list b))))

(define (py-list-ref lst i)
  "读取通用列表第 i 个元素"
  (vector-ref lst i))

(define (py-list-length lst)
  "通用列表长度"
  (vector-length lst))

(define (list->py-list lst)
  "把 Scheme list 转为通用列表"
  (list->vector lst))

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
  (cond ((py-tagged-array? x) (py-tagged->list x))
        ((vector? x) (vector->list x))
        ((string? x) (string->list x))
        ((list? x) x)
        ((null? x) '())
        ((pair? x) (list x))
        (else (list x))))

(define (py-list-slice v start end)
  "py-list/vector 切片 [start,end)；end 为负数时从尾部数。返回 py-list"
  (let* ((lst (vector->list v))
         (n (length lst))
         (hi (if (< end 0) (+ n end) end)))
    (list->vector (if (<= hi start) '()
                      (list-head (list-tail lst start) (- hi start))))))

(define (py-unpack e i)
  "多目标解包的取第 i 项：vector / 点对 (a . b) / 其它按单值"
  (cond ((vector? e) (vector-ref e i))
        ((pair? e) (if (= i 0) (car e) (cdr e)))
        (else e)))
