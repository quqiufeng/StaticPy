;; static_prelude.scm — StaticPy 值类型运行时
;; 
;; 值类型: int=fixnum, float=flonum, bool=boolean
;; 数组类型: float[] = foreign-alloc 分配的 C double*
;;           GC 自动回收（通过 guardian），无需手动 free

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

;; ====== IR 节点标签判断（StaticPy 自举编译器用） ======
;; Python 的 isinstance(x, EConst) 在 Scheme 里对应 (ir-tag? x 'EConst)
;; 因为 EConst(x) 被翻译成 (vector 'EConst x)

;; 记录类（define-record-type）的 isinstance：沿父类链比较类型名
(define (ir-record-isa? node tname)
  (let loop ((rtd (record-rtd node)))
    (cond ((not rtd) #f)
          ((eq? (record-type-name rtd) tname) #t)
          (else (loop (record-type-parent rtd))))))

(define (ir-tag? node tag)
  (let ((t (if (string? tag) (string->symbol tag) tag)))
    (cond
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

