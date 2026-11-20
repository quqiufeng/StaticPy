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
