;; static_prof.scm — Scheme 层剖析运行时（仅 STATICPY_PROFILE 构建时拼进 merged.ss）
;;
;; 分工：
;;   编译器（Chez）在 STATICPY_PROFILE=source|block 时插计数器
;;   （compile-profile 'source / 'block）；这里只负责把计数器落成文件，
;;   source 计数再由 tools/sprof.static.py 按 `;; file:line` 注释并回 Python 源行。
;;
;; 零地址：不碰机器码、不读 /proc、不怕 GC 搬对象——计数值本身就是判据。
;;
;; 环境变量：
;;   STATICPY_PROF_OUT   dump 路径（默认 $HOME/iso_gen/prof/<exe>.prof|.pd）
;;   STATICPY_PROF_MODE  覆盖构建期烘焙的模式（source|block）

(define (static-prof-env name)
  (let ([v (getenv name)])
    (if v v "")))

(define (static-prof-basename path)
  (let loop ([i (- (string-length path) 1)])
    (cond [(< i 0) path]
          [(char=? (string-ref path i) #\/)
           (substring path (+ i 1) (string-length path))]
          [else (loop (- i 1))])))

(define (static-prof-dirname path)
  (let loop ([i (- (string-length path) 1)])
    (cond [(< i 0) "."]
          [(char=? (string-ref path i) #\/) (substring path 0 (max i 1))]
          [else (loop (- i 1))])))

(define (static-prof-strip-so b)
  (let ([n (string-length b)])
    (if (and (> n 3) (string=? (substring b (- n 3) n) ".so"))
        (substring b 0 (- n 3))
        b)))

;; 递归建目录（~/iso_gen/prof 这种两层）
(define (static-prof-mkdirs dir)
  (unless (or (string=? dir "") (string=? dir ".") (string=? dir ".."))
    (unless (file-exists? dir)
      (let ([parent (static-prof-dirname dir)])
        (unless (string=? parent dir)
          (static-prof-mkdirs parent))
        (guard (e [#t #f]) (mkdir dir))))))

(define (static-prof-mode)
  (let ([m (static-prof-env "STATICPY_PROF_MODE")])
    (cond [(> (string-length m) 0) m]
          [(string? static-prof-baked-mode) static-prof-baked-mode]
          [else "source"])))

(define (static-prof-out-path ext)
  (let ([v (static-prof-env "STATICPY_PROF_OUT")])
    (if (> (string-length v) 0)
        v
        (let* ([home (static-prof-env "HOME")]
               [base (if (> (string-length home) 0) home ".")]
               [prog (static-prof-strip-so
                       (if (pair? (command-line))
                           (static-prof-basename (car (command-line)))
                           "static"))])
          (string-append base "/iso_gen/prof/" prog ext)))))

;; ---- source 模式：表达式计数落成 TSV ----
;; 文件格式：
;;   #staticpy-prof 1
;;   #mode source
;;   #ss  /path/to/<stem>_<hash>.ss      ← 计数行号所属的 Scheme 文件
;;   #exe <程序名>
;;   hits <scheme-path> <line> <char>
(define (static-prof-dump-source out)
  (let ([rows (profile-dump-list)])
    (static-prof-mkdirs (static-prof-dirname out))
    (let ([op (open-output-file out 'replace)])
      (dynamic-wind
        void
        (lambda ()
          (display "#staticpy-prof 1" op) (newline op)
          (display "#mode " op) (display (static-prof-mode) op) (newline op)
          (display "#ss " op)
          (display (if (string? static-merged-ss) static-merged-ss "?") op)
          (newline op)
          (display "#exe " op)
          (display (if (pair? (command-line)) (car (command-line)) "?")) (newline op)
          (for-each
            (lambda (r)
              (display (car r) op) (display "\t" op)
              (display (let ([p (list-ref r 1)]) (if (string? p) p "?")) op)
              (display "\t" op)
              (let ([ln (list-ref r 4)])
                (display (if (integer? ln) ln -1) op))
              (display "\t" op)
              (let ([ch (list-ref r 5)])
                (display (if (integer? ch) ch -1) op))
              (newline op))
            rows))
        (lambda () (close-output-port op))))
    (length rows)))

;; ---- block 模式：基本块计数 → .pd（供下一次编译 PGO 回灌） ----
(define (static-prof-dump-block out)
  (static-prof-mkdirs (static-prof-dirname out))
  (profile-dump-data out)
  0)

;; ---- 入口收尾：按模式落盘 + 记下"最近一次" ----
(define (static-prof-report)
  (let* ([mode (static-prof-mode)]
         [block? (string=? mode "block")]
         [out (static-prof-out-path (if block? ".pd" ".prof"))]
         [cnt (guard (e [#t (begin
                              (display "[sprof] dump 失败: ")
                              (display (if (message-condition? e)
                                           (condition-message e) e))
                              (newline)
                              -1)])
                (if block? (static-prof-dump-block out)
                    (static-prof-dump-source out)))])
    ;; 记下最近一次 dump，供 tools/sprof 无参调用找回
    (let ([last (string-append (static-prof-dirname out) "/last.txt")])
      (guard (e [#t #f])
        (let ([lp (open-output-file last 'replace)])
          (display out lp) (newline lp) (close-output-port lp))))
    (if block?
        (begin
          (display "[sprof] 基本块计数 -> ") (display out) (newline)
          (display "[sprof] PGO 回灌: STATICPY_PGO=1 重编同一份源即可用上这份画像")
          (newline))
        (begin
          (display "[sprof] ") (display cnt)
          (display " 条表达式计数 -> ") (display out) (newline)))))
