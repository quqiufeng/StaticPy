
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
