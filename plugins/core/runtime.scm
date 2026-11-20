
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

;; ====== 字典（hashtable） ======

(define (make-dict)
  "创建空字典"
  (make-hashtable equal-hash equal?))

(define (dict-get d key)
  "读取字典 d[key]"
  (hashtable-ref d key #f))

(define (dict-get-or-empty d key)
  "读取字典 d[key]，返回空字符串代替 #f"
  (hashtable-ref d key ""))

(define dict_get_or_empty (lambda (d key) (dict-get-or-empty d key)))

(define (dict-set! d key val)
  "写入字典 d[key] = val"
  (hashtable-set! d key val))

(define (dict-contains? d key)
  "检查 key 是否在字典中"
  (hashtable-contains? d key))

(define (dict-copy d)
  "浅拷贝字典"
  (let ((copy (make-dict)))
    (vector-for-each
      (lambda (entry)
        (dict-set! copy (car entry) (cdr entry)))
      (hashtable-cells d))
    copy))


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


;; ====== 通用打印 ======

(define (print-one x)
  (cond ((number? x) (display x))
        ((boolean? x) (display (if x "True" "False")))
        ((string? x) (display x))
        ((hashtable? x) (display (json->string x)))
        ((list? x) (display (json->string (list->vector x))))
        ((vector? x) (display (json->string x)))
        ((null? x) (display "None"))
        (else (display x))))

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
