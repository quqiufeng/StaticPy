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

(define (py-m-pop r . k)
  (cond ((py-array? r) (py-array-method-h 'pop r k))
        ((hashtable? r) (if (null? k) (error 'pop "dict.pop needs key")
                            (if (null? (cdr k)) (dict-pop r (car k))
                                (dict-pop r (car k) (cadr k)))))
        (else py-none)))

(define (py-m-clear r)
  (if (py-array? r) (py-array-method-h 'clear r '())
      (begin (dict-clear! r) py-none)))

(define (py-m-setdefault r k . v)
  (if (py-array? r) (py-array-method-h 'setdefault r (cons k v))
      (if (dict-contains? r k) (dict-get r k)
          (let ((dv (if (null? v) py-none (car v)))) (dict-set! r k dv)))))

(define (py-m-update r o)
  (if (py-array? r) (py-array-method-h 'update r (list o)) (begin (dict-merge! r o) py-none)))

(define (py-m-copy r) (if (py-array? r) (py-array-method-h 'copy r '()) (dict-copy r)))

(define (py-m-sort r . args)
  (if (py-array? r) (py-array-method-h 'sort r args) py-none))
(define (py-m-reverse r)
  (if (py-array? r) (py-array-method-h 'reverse r '()) py-none))
(define (py-m-append r v)
  (if (py-array? r) (py-array-append-h r v) (py-list-append r v)))

(define (py-m-extend r o) (if (py-array? r) (py-array-method-h 'extend r (list o)) py-none))
(define (py-m-insert r i v) (if (py-array? r) (py-array-method-h 'insert r (list i v)) py-none))
(define (py-m-remove r v) (if (py-array? r) (py-array-method-h 'remove r (list v)) py-none))

(define (py-m-index r v) (if (py-array? r) (py-array-method-h 'index r (list v)) -1))
(define (py-m-count r v) (if (py-array? r) (py-array-method-h 'count r (list v)) 0))
