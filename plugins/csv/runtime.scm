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
