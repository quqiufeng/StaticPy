

;; ============================================================
;; Part 3: CUDA cuBLAS — GPU 矩阵运算
;; ============================================================
;; CUDA libs are loaded by torch internally — do NOT preload with RTLD_LOCAL
(define *cuda-available* #f)

(define cublas-handle #f)
(define cublas-create #f)
(define cublas-destroy #f)
(define cublas-sgemm #f)
(define cublas-dgemm #f)
(define cublas-saxpy #f)
(define cublas-daxpy #f)
(define cublas-sdot #f)
(define cublas-ddot #f)
(define cublas-dcopy #f)

(when *cuda-available*
  (set! cublas-create (foreign-procedure "cublasCreate_v2" (void*) int))
  (set! cublas-destroy (foreign-procedure "cublasDestroy_v2" (void*) int))
  (set! cublas-sgemm (foreign-procedure "cublasSgemm_v2"
    (void* int int int int int int float void* int void* int float void* int) int))
  (set! cublas-dgemm (foreign-procedure "cublasDgemm_v2"
    (void* int int int int int int void* void* int void* int void* void* int) int))
  (set! cublas-saxpy (foreign-procedure "cublasSaxpy_v2"
    (void* int float void* int void* int) int))
  (set! cublas-daxpy (foreign-procedure "cublasDaxpy_v2"
    (void* int double void* int void* int) int))
  (set! cublas-ddot (foreign-procedure "cublasDdot_v2"
    (void* int void* int void* int) double))
  (set! cublas-dcopy (foreign-procedure "cublasDcopy_v2"
    (void* int void* int void* int) int))
  ;; 初始化 cuBLAS handle
  (let ((h (foreign-alloc 8)))
    (cublas-create h)
    (set! cublas-handle (foreign-ref 'void* h 0))
    (foreign-free h)))

;; ============================================================
;; Part 3a: cuRAND — GPU 随机数生成（权重初始化/dropout）
;; ============================================================
;; loaded by torch internally
(define *curand-available* #f)

(define curand-create #f)
(define curand-destroy #f)
(define curand-set-seed #f)
(define curand-uniform #f)
(define curand-normal #f)

(when *curand-available*
  (set! curand-create (foreign-procedure "curandCreateGenerator" (void* int) int))
  (set! curand-destroy (foreign-procedure "curandDestroyGenerator" (void*) int))
  (set! curand-set-seed (foreign-procedure "curandSetPseudoRandomGeneratorSeed" (void* int) int))
  (set! curand-uniform (foreign-procedure "curandGenerateUniform" (void* void* int) int))
  (set! curand-normal (foreign-procedure "curandGenerateNormal" (void* void* int double double) int)))

;; ============================================================
;; Part 4: cuSOLVER — GPU 矩阵分解（SVD/Cholesky）
;; ============================================================
;; loaded by torch internally
(define *cusolver-available* #f)

(define cusolver-dn-create #f)
(define cusolver-dn-destroy #f)
(define cusolver-dgesvd #f)
(define cusolver-dpotrf #f)

(when *cusolver-available*
  (set! cusolver-dn-create (foreign-procedure "cusolverDnCreate" (void*) int))
  (set! cusolver-dn-destroy (foreign-procedure "cusolverDnDestroy" (void*) int))
  (set! cusolver-dgesvd (foreign-procedure "cusolverDnDgesvd"
    (void* int int int int void* int void* void* int void* int void* int void* void*) int))
  (set! cusolver-dpotrf (foreign-procedure "cusolverDnDpotrf"
    (void* int int void* int void* int void*) int)))

;; ============================================================
;; Part 5: cuDNN — GPU 深度学习原语
;; ============================================================
;; loaded by torch internally
(define *cudnn-available* #f)

(define cudnn-create #f)
(define cudnn-destroy #f)
(define cudnn-create-tensor-desc #f)
(define cudnn-set-tensor-4d #f)
(define cudnn-create-filter-desc #f)
(define cudnn-set-filter-4d #f)
(define cudnn-create-conv-desc #f)
(define cudnn-set-conv-2d #f)
(define cudnn-conv-forward #f)
(define cudnn-activation-forward #f)
(define cudnn-activation-backward #f)
(define cudnn-pooling-forward #f)
(define cudnn-softmax-forward #f)
(define cudnn-batchnorm-forward #f)

(when *cudnn-available*
  (call-with-current-continuation
    (lambda (return)
      (with-exception-handler
        (lambda (e) #f (return))
        (lambda ()
          (set! cudnn-create (foreign-procedure "cudnnCreate" (void*) int))
          (set! cudnn-destroy (foreign-procedure "cudnnDestroy" (void*) int))
          (set! cudnn-create-tensor-desc (foreign-procedure "cudnnCreateTensorDescriptor" (void*) int))
          (set! cudnn-set-tensor-4d (foreign-procedure "cudnnSetTensor4dDescriptor" (void* int int int int int int) int))
          (set! cudnn-create-filter-desc (foreign-procedure "cudnnCreateFilterDescriptor" (void*) int))
          (set! cudnn-set-filter-4d (foreign-procedure "cudnnSetFilter4dDescriptor" (void* int int int int int int) int))
          (set! cudnn-create-conv-desc (foreign-procedure "cudnnCreateConvolutionDescriptor" (void*) int))
          (set! cudnn-set-conv-2d (foreign-procedure "cudnnSetConvolution2dDescriptor" (void* int int int int int int int int) int))
          (set! cudnn-conv-forward (foreign-procedure "cudnnConvolutionForward"
            (void* void* void* void* void* void* void* int void* int void* void* void*) int))
          (set! cudnn-activation-forward (foreign-procedure "cudnnActivationForward"
            (void* int void* void* void* void* void* void*) int))
          (set! cudnn-activation-backward (foreign-procedure "cudnnActivationBackward"
            (void* int void* void* void* void* void* void* void* void* void* void*) int))
          (set! cudnn-pooling-forward (foreign-procedure "cudnnPoolingForward"
            (void* void* void* void* void* void* void* void*) int))
          (set! cudnn-softmax-forward (foreign-procedure "cudnnSoftmaxForward"
            (void* int int void* void* void* void* void* void*) int))
          (set! cudnn-batchnorm-forward (foreign-procedure "cudnnBatchNormalizationForwardTraining"
            (void* int void* void* void* void* void* void* void* void* void* void* void* double) int)))))))
