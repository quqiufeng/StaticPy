
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
