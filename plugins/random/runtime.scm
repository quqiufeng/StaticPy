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
