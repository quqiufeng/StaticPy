# PyTorch 接口面（自省清单）

由 `python3 plugins/ltorch/surface.py` 生成，torch `2.12.0+cpu`。

**规模**：顶层 962 · Tensor 成员 610 · nn 模块 166 · nn.functional 143 · optim 16 · dtype 12

## 顶层 `torch.*`

可调用对象与常量（模块除外）。

| 名 | 形态 | 签名 |
|---|---|---|
| `AVG` | const | `` |
| `AcceleratorError` | fn | `` |
| `AggregationType` | fn | `` |
| `AliasDb` | fn | `` |
| `AnyType` | fn | `` |
| `Argument` | fn | `` |
| `ArgumentSpec` | fn | `` |
| `AwaitType` | fn | `` |
| `BFloat16Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `BFloat16Tensor` | fn | `` |
| `BenchmarkConfig` | fn | `` |
| `BenchmarkExecutionStats` | fn | `` |
| `Block` | fn | `` |
| `BoolStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `BoolTensor` | fn | `` |
| `BoolType` | fn | `` |
| `BufferDict` | fn | `` |
| `ByteStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `ByteTensor` | fn | `` |
| `CallStack` | fn | `` |
| `Capsule` | fn | `` |
| `CharStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `CharTensor` | fn | `` |
| `ClassType` | fn | `` |
| `Code` | fn | `` |
| `CompilationUnit` | fn | `` |
| `CompleteArgumentSpec` | fn | `` |
| `ComplexDoubleStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `ComplexFloatStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `ComplexType` | fn | `` |
| `ConcreteModuleType` | fn | `` |
| `ConcreteModuleTypeBuilder` | fn | `` |
| `DeepCopyMemoTable` | fn | `` |
| `DeserializationStorageContext` | fn | `` |
| `DeviceObjType` | fn | `` |
| `DictType` | fn | `` |
| `DisableTorchFunction` | fn | `` |
| `DisableTorchFunctionSubclass` | fn | `` |
| `DispatchKey` | fn | `` |
| `DispatchKeySet` | fn | `` |
| `DoubleStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `DoubleTensor` | fn | `` |
| `EnumType` | fn | `` |
| `ErrorReport` | fn | `` |
| `Event` | fn | `` |
| `ExcludeDispatchKeyGuard` | fn | `` |
| `ExecutionPlan` | fn | `` |
| `FatalError` | fn | `` |
| `FileCheck` | fn | `` |
| `FloatStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `FloatTensor` | fn | `` |
| `FloatType` | fn | `` |
| `FunctionSchema` | fn | `` |
| `Future` | fn | `` |
| `FutureType` | fn | `` |
| `Generator` | fn | `` |
| `GradScaler` | fn | `(device: 'str' = 'cuda', init_scale: 'float' = 65536.0, growth_factor: 'float' = 2.0, backoff_factor: 'float' = 0.5, gro…` |
| `Gradient` | fn | `` |
| `Graph` | fn | `` |
| `GraphExecutorState` | fn | `` |
| `HalfStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `HalfTensor` | fn | `` |
| `IODescriptor` | fn | `` |
| `InferredType` | fn | `` |
| `IntStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `IntTensor` | fn | `` |
| `IntType` | fn | `` |
| `InterfaceType` | fn | `` |
| `JITException` | fn | `` |
| `ListType` | fn | `` |
| `LiteScriptModule` | fn | `` |
| `LockingLogger` | fn | `` |
| `LoggerBase` | fn | `` |
| `LongStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `LongTensor` | fn | `` |
| `ModuleDict` | fn | `` |
| `Node` | fn | `` |
| `NoneType` | fn | `` |
| `NoopLogger` | fn | `` |
| `NumberType` | fn | `` |
| `OperatorInfo` | fn | `` |
| `OptionalType` | fn | `` |
| `OutOfMemoryError` | fn | `` |
| `PRIVATE_OPS` | const | `` |
| `ParameterDict` | fn | `` |
| `PyObjectType` | fn | `` |
| `PyTorchFileReader` | fn | `` |
| `PyTorchFileWriter` | fn | `` |
| `QInt32Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `QInt8Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `QUInt2x4Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `QUInt4x2Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `QUInt8Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `RRefType` | fn | `` |
| `SUM` | const | `` |
| `ScriptClass` | fn | `` |
| `ScriptClassFunction` | fn | `` |
| `ScriptDict` | fn | `` |
| `ScriptDictIterator` | fn | `` |
| `ScriptDictKeyIterator` | fn | `` |
| `ScriptFunction` | fn | `` |
| `ScriptList` | fn | `` |
| `ScriptListIterator` | fn | `` |
| `ScriptMethod` | fn | `` |
| `ScriptModule` | fn | `` |
| `ScriptModuleSerializer` | fn | `` |
| `ScriptObject` | fn | `` |
| `ScriptObjectProperty` | fn | `` |
| `SerializationStorageContext` | fn | `` |
| `ShortStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `ShortTensor` | fn | `` |
| `Size` | fn | `(iterable=(), /)` |
| `StaticModule` | fn | `` |
| `Storage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `StorageBase` | fn | `` |
| `Stream` | fn | `` |
| `StreamObjType` | fn | `` |
| `StringType` | fn | `` |
| `SymBool` | fn | `(node)` |
| `SymBoolType` | fn | `` |
| `SymFloat` | fn | `(node)` |
| `SymInt` | fn | `(node)` |
| `SymIntType` | fn | `` |
| `TYPE_CHECKING` | const | `` |
| `Tag` | fn | `` |
| `Tensor` | fn | `` |
| `TensorType` | fn | `` |
| `ThroughputBenchmark` | fn | `` |
| `TracingState` | fn | `` |
| `TupleType` | fn | `` |
| `Type` | fn | `` |
| `TypedStorage` | fn | `(*args, wrap_storage=None, dtype=None, device=None, _internal=False)` |
| `USE_GLOBAL_DEPS` | const | `` |
| `USE_RTLD_GLOBAL_WITH_LIBTORCH` | const | `` |
| `UnionType` | fn | `` |
| `UntypedStorage` | fn | `(*args, **kwargs)` |
| `Use` | fn | `` |
| `Value` | fn | `` |
| `abs` | fn | `` |
| `abs_` | fn | `` |
| `absolute` | fn | `` |
| `acos` | fn | `` |
| `acos_` | fn | `` |
| `acosh` | fn | `` |
| `acosh_` | fn | `` |
| `adaptive_avg_pool1d` | fn | `` |
| `adaptive_max_pool1d` | fn | `` |
| `add` | fn | `` |
| `addbmm` | fn | `` |
| `addcdiv` | fn | `` |
| `addcmul` | fn | `` |
| `addmm` | fn | `` |
| `addmv` | fn | `` |
| `addmv_` | fn | `` |
| `addr` | fn | `` |
| `adjoint` | fn | `` |
| `affine_grid_generator` | fn | `` |
| `alias_copy` | fn | `` |
| `align_tensors` | fn | `(*tensors)` |
| `all` | fn | `` |
| `allclose` | fn | `` |
| `alpha_dropout` | fn | `` |
| `alpha_dropout_` | fn | `` |
| `amax` | fn | `` |
| `amin` | fn | `` |
| `aminmax` | fn | `` |
| `angle` | fn | `` |
| `any` | fn | `` |
| `arange` | fn | `` |
| `arccos` | fn | `` |
| `arccos_` | fn | `` |
| `arccosh` | fn | `` |
| `arccosh_` | fn | `` |
| `arcsin` | fn | `` |
| `arcsin_` | fn | `` |
| `arcsinh` | fn | `` |
| `arcsinh_` | fn | `` |
| `arctan` | fn | `` |
| `arctan2` | fn | `` |
| `arctan_` | fn | `` |
| `arctanh` | fn | `` |
| `arctanh_` | fn | `` |
| `are_deterministic_algorithms_enabled` | fn | `() -> bool` |
| `argmax` | fn | `` |
| `argmin` | fn | `` |
| `argsort` | fn | `` |
| `argwhere` | fn | `` |
| `as_strided` | fn | `` |
| `as_strided_` | fn | `` |
| `as_strided_copy` | fn | `` |
| `as_strided_scatter` | fn | `` |
| `as_tensor` | fn | `` |
| `asarray` | fn | `` |
| `asin` | fn | `` |
| `asin_` | fn | `` |
| `asinh` | fn | `` |
| `asinh_` | fn | `` |
| `atan` | fn | `` |
| `atan2` | fn | `` |
| `atan_` | fn | `` |
| `atanh` | fn | `` |
| `atanh_` | fn | `` |
| `atleast_1d` | fn | `(*tensors)` |
| `atleast_2d` | fn | `(*tensors)` |
| `atleast_3d` | fn | `(*tensors)` |
| `autocast` | fn | `(device_type: str, dtype: torch.dtype \| None = None, enabled: bool = True, cache_enabled: bool \| None = None)` |
| `autocast_decrement_nesting` | fn | `` |
| `autocast_increment_nesting` | fn | `` |
| `avg_pool1d` | fn | `` |
| `baddbmm` | fn | `` |
| `bartlett_window` | fn | `` |
| `batch_norm` | fn | `` |
| `batch_norm_backward_elemt` | fn | `` |
| `batch_norm_backward_reduce` | fn | `` |
| `batch_norm_elemt` | fn | `` |
| `batch_norm_gather_stats` | fn | `` |
| `batch_norm_gather_stats_with_counts` | fn | `` |
| `batch_norm_stats` | fn | `` |
| `batch_norm_update_stats` | fn | `` |
| `bernoulli` | fn | `` |
| `bfloat16` | const | `` |
| `bilinear` | fn | `` |
| `binary_cross_entropy_with_logits` | fn | `` |
| `bincount` | fn | `` |
| `binomial` | fn | `` |
| `bit` | const | `` |
| `bits16` | const | `` |
| `bits1x8` | const | `` |
| `bits2x4` | const | `` |
| `bits4x2` | const | `` |
| `bits8` | const | `` |
| `bitwise_and` | fn | `` |
| `bitwise_left_shift` | fn | `` |
| `bitwise_not` | fn | `` |
| `bitwise_or` | fn | `` |
| `bitwise_right_shift` | fn | `` |
| `bitwise_xor` | fn | `` |
| `blackman_window` | fn | `` |
| `block_diag` | fn | `(*tensors)` |
| `bmm` | fn | `` |
| `bool` | const | `` |
| `broadcast_shapes` | fn | `(*shapes)` |
| `broadcast_tensors` | fn | `(*tensors)` |
| `broadcast_to` | fn | `` |
| `bucketize` | fn | `` |
| `can_cast` | fn | `` |
| `cartesian_prod` | fn | `(*tensors: torch.Tensor) -> torch.Tensor` |
| `cat` | fn | `` |
| `ccol_indices_copy` | fn | `` |
| `cdist` | fn | `(x1, x2, p=2.0, compute_mode='use_mm_for_euclid_dist_if_necessary')` |
| `cdouble` | const | `` |
| `ceil` | fn | `` |
| `ceil_` | fn | `` |
| `celu` | fn | `` |
| `celu_` | fn | `` |
| `cfloat` | const | `` |
| `chain_matmul` | fn | `(*matrices, out=None)` |
| `chalf` | const | `` |
| `channel_shuffle` | fn | `` |
| `channels_last` | const | `` |
| `channels_last_3d` | const | `` |
| `cholesky` | fn | `` |
| `cholesky_inverse` | fn | `` |
| `cholesky_solve` | fn | `` |
| `choose_qparams_optimized` | fn | `` |
| `chunk` | fn | `` |
| `clamp` | fn | `` |
| `clamp_` | fn | `` |
| `clamp_max` | fn | `` |
| `clamp_max_` | fn | `` |
| `clamp_min` | fn | `` |
| `clamp_min_` | fn | `` |
| `classproperty` | fn | `(func)` |
| `clear_autocast_cache` | fn | `` |
| `clip` | fn | `` |
| `clip_` | fn | `` |
| `clone` | fn | `` |
| `col_indices_copy` | fn | `` |
| `column_stack` | fn | `` |
| `combinations` | fn | `` |
| `compile` | fn | `(model: collections.abc.Callable[~_InputT, ~_RetT] \| None = None, *, fullgraph: bool = False, dynamic: bool \| None = N…` |
| `compiled_with_cxx11_abi` | fn | `() -> bool` |
| `complex` | fn | `` |
| `complex128` | const | `` |
| `complex32` | const | `` |
| `complex64` | const | `` |
| `concat` | fn | `` |
| `concatenate` | fn | `` |
| `cond` | fn | `(pred: bool \| int \| float \| torch.Tensor, true_fn: collections.abc.Callable, false_fn: collections.abc.Callable, oper…` |
| `conj` | fn | `` |
| `conj_physical` | fn | `` |
| `conj_physical_` | fn | `` |
| `constant_pad_nd` | fn | `` |
| `contiguous_format` | const | `` |
| `conv1d` | fn | `` |
| `conv2d` | fn | `` |
| `conv3d` | fn | `` |
| `conv_tbc` | fn | `` |
| `conv_transpose1d` | fn | `` |
| `conv_transpose2d` | fn | `` |
| `conv_transpose3d` | fn | `` |
| `convolution` | fn | `` |
| `copysign` | fn | `` |
| `corrcoef` | fn | `` |
| `cos` | fn | `` |
| `cos_` | fn | `` |
| `cosh` | fn | `` |
| `cosh_` | fn | `` |
| `cosine_embedding_loss` | fn | `` |
| `cosine_similarity` | fn | `` |
| `count_nonzero` | fn | `` |
| `cov` | fn | `` |
| `cross` | fn | `` |
| `crow_indices_copy` | fn | `` |
| `ctc_loss` | fn | `` |
| `cudnn_affine_grid_generator` | fn | `` |
| `cudnn_batch_norm` | fn | `` |
| `cudnn_convolution` | fn | `` |
| `cudnn_convolution_add_relu` | fn | `` |
| `cudnn_convolution_relu` | fn | `` |
| `cudnn_convolution_transpose` | fn | `` |
| `cudnn_grid_sampler` | fn | `` |
| `cudnn_is_acceptable` | fn | `` |
| `cummax` | fn | `` |
| `cummin` | fn | `` |
| `cumprod` | fn | `` |
| `cumsum` | fn | `` |
| `cumulative_trapezoid` | fn | `` |
| `default_generator` | const | `` |
| `deg2rad` | fn | `` |
| `deg2rad_` | fn | `` |
| `dequantize` | fn | `` |
| `det` | fn | `` |
| `detach` | fn | `` |
| `detach_` | fn | `` |
| `detach_copy` | fn | `` |
| `device` | fn | `` |
| `diag` | fn | `` |
| `diag_embed` | fn | `` |
| `diagflat` | fn | `` |
| `diagonal` | fn | `` |
| `diagonal_copy` | fn | `` |
| `diagonal_scatter` | fn | `` |
| `diff` | fn | `` |
| `digamma` | fn | `` |
| `dist` | fn | `` |
| `div` | fn | `` |
| `divide` | fn | `` |
| `dot` | fn | `` |
| `double` | const | `` |
| `dropout` | fn | `` |
| `dropout_` | fn | `` |
| `dsmm` | fn | `` |
| `dsplit` | fn | `` |
| `dstack` | fn | `` |
| `dtype` | fn | `()` |
| `e` | const | `` |
| `eig` | fn | `(self: torch.Tensor, eigenvectors: bool = False, *, e=None, v=None) -> tuple[torch.Tensor, torch.Tensor]` |
| `einsum` | fn | `(*args: Any) -> torch.Tensor` |
| `embedding` | fn | `` |
| `embedding_bag` | fn | `` |
| `embedding_renorm_` | fn | `` |
| `empty` | fn | `` |
| `empty_like` | fn | `` |
| `empty_permuted` | fn | `` |
| `empty_quantized` | fn | `` |
| `empty_strided` | fn | `` |
| `enable_grad` | fn | `(orig_func: Optional[~F] = None) -> Union[Self, ~F]` |
| `eq` | fn | `` |
| `equal` | fn | `` |
| `erf` | fn | `` |
| `erf_` | fn | `` |
| `erfc` | fn | `` |
| `erfc_` | fn | `` |
| `erfinv` | fn | `` |
| `exp` | fn | `` |
| `exp2` | fn | `` |
| `exp2_` | fn | `` |
| `exp_` | fn | `` |
| `expand_copy` | fn | `` |
| `expm1` | fn | `` |
| `expm1_` | fn | `` |
| `eye` | fn | `` |
| `fake_quantize_per_channel_affine` | fn | `` |
| `fake_quantize_per_tensor_affine` | fn | `` |
| `fbgemm_linear_fp16_weight` | fn | `` |
| `fbgemm_linear_fp16_weight_fp32_activation` | fn | `` |
| `fbgemm_linear_int8_weight` | fn | `` |
| `fbgemm_linear_int8_weight_fp32_activation` | fn | `` |
| `fbgemm_linear_quantize_weight` | fn | `` |
| `fbgemm_pack_gemm_matrix_fp16` | fn | `` |
| `fbgemm_pack_quantized_matrix` | fn | `` |
| `feature_alpha_dropout` | fn | `` |
| `feature_alpha_dropout_` | fn | `` |
| `feature_dropout` | fn | `` |
| `feature_dropout_` | fn | `` |
| `fill` | fn | `` |
| `fill_` | fn | `` |
| `finfo` | fn | `` |
| `fix` | fn | `` |
| `fix_` | fn | `` |
| `flatten` | fn | `` |
| `flip` | fn | `` |
| `fliplr` | fn | `` |
| `flipud` | fn | `` |
| `float` | const | `` |
| `float16` | const | `` |
| `float32` | const | `` |
| `float4_e2m1fn_x2` | const | `` |
| `float64` | const | `` |
| `float8_e4m3fn` | const | `` |
| `float8_e4m3fnuz` | const | `` |
| `float8_e5m2` | const | `` |
| `float8_e5m2fnuz` | const | `` |
| `float8_e8m0fnu` | const | `` |
| `float_power` | fn | `` |
| `floor` | fn | `` |
| `floor_` | fn | `` |
| `floor_divide` | fn | `` |
| `fmax` | fn | `` |
| `fmin` | fn | `` |
| `fmod` | fn | `` |
| `fork` | fn | `` |
| `frac` | fn | `` |
| `frac_` | fn | `` |
| `frexp` | fn | `` |
| `frobenius_norm` | fn | `` |
| `from_dlpack` | fn | `(ext_tensor: Any, *, device: torch.device \| str \| int \| None = None, copy: bool \| None = None) -> 'torch.Tensor'` |
| `from_file` | fn | `` |
| `from_numpy` | fn | `` |
| `frombuffer` | fn | `` |
| `full` | fn | `` |
| `full_like` | fn | `` |
| `fused_moving_avg_obs_fake_quant` | fn | `` |
| `gather` | fn | `` |
| `gcd` | fn | `` |
| `gcd_` | fn | `` |
| `ge` | fn | `` |
| `geqrf` | fn | `` |
| `ger` | fn | `` |
| `get_autocast_cpu_dtype` | fn | `` |
| `get_autocast_dtype` | fn | `` |
| `get_autocast_gpu_dtype` | fn | `` |
| `get_autocast_ipu_dtype` | fn | `` |
| `get_autocast_xla_dtype` | fn | `` |
| `get_default_device` | fn | `() -> 'torch.device'` |
| `get_default_dtype` | fn | `` |
| `get_deterministic_debug_mode` | fn | `() -> int` |
| `get_device` | fn | `` |
| `get_device_module` | fn | `(device: torch.device \| str \| None = None)` |
| `get_file_path` | fn | `(*path_components: str) -> str` |
| `get_float32_matmul_precision` | fn | `() -> str` |
| `get_num_interop_threads` | fn | `` |
| `get_num_threads` | fn | `` |
| `get_rng_state` | fn | `() -> torch.Tensor` |
| `gradient` | fn | `` |
| `greater` | fn | `` |
| `greater_equal` | fn | `` |
| `grid_sampler` | fn | `` |
| `grid_sampler_2d` | fn | `` |
| `grid_sampler_3d` | fn | `` |
| `group_norm` | fn | `` |
| `gru` | fn | `` |
| `gru_cell` | fn | `` |
| `gt` | fn | `` |
| `half` | const | `` |
| `hamming_window` | fn | `` |
| `hann_window` | fn | `` |
| `hardshrink` | fn | `` |
| `has_lapack` | const | `` |
| `has_mkl` | const | `` |
| `has_openmp` | const | `` |
| `has_spectral` | const | `` |
| `hash_tensor` | fn | `` |
| `heaviside` | fn | `` |
| `hinge_embedding_loss` | fn | `` |
| `histc` | fn | `` |
| `histogram` | fn | `` |
| `histogramdd` | fn | `` |
| `hsmm` | fn | `` |
| `hsplit` | fn | `` |
| `hspmm` | fn | `` |
| `hstack` | fn | `` |
| `hypot` | fn | `` |
| `i0` | fn | `` |
| `i0_` | fn | `` |
| `igamma` | fn | `` |
| `igammac` | fn | `` |
| `iinfo` | fn | `` |
| `imag` | fn | `` |
| `import_ir_module` | fn | `` |
| `import_ir_module_from_buffer` | fn | `` |
| `index_add` | fn | `` |
| `index_copy` | fn | `` |
| `index_fill` | fn | `` |
| `index_put` | fn | `` |
| `index_put_` | fn | `` |
| `index_reduce` | fn | `` |
| `index_select` | fn | `` |
| `indices_copy` | fn | `` |
| `inf` | const | `` |
| `inference_mode` | fn | `(mode=True)` |
| `init_num_threads` | fn | `` |
| `initial_seed` | fn | `() -> int` |
| `inner` | fn | `` |
| `instance_norm` | fn | `` |
| `int` | const | `` |
| `int1` | const | `` |
| `int16` | const | `` |
| `int2` | const | `` |
| `int3` | const | `` |
| `int32` | const | `` |
| `int4` | const | `` |
| `int5` | const | `` |
| `int6` | const | `` |
| `int64` | const | `` |
| `int7` | const | `` |
| `int8` | const | `` |
| `int_repr` | fn | `` |
| `inverse` | fn | `` |
| `is_anomaly_check_nan_enabled` | fn | `` |
| `is_anomaly_enabled` | fn | `` |
| `is_autocast_cache_enabled` | fn | `` |
| `is_autocast_cpu_enabled` | fn | `` |
| `is_autocast_enabled` | fn | `` |
| `is_autocast_ipu_enabled` | fn | `` |
| `is_autocast_xla_enabled` | fn | `` |
| `is_complex` | fn | `` |
| `is_conj` | fn | `` |
| `is_deterministic_algorithms_warn_only_enabled` | fn | `() -> bool` |
| `is_distributed` | fn | `` |
| `is_floating_point` | fn | `` |
| `is_grad_enabled` | fn | `` |
| `is_inference` | fn | `` |
| `is_inference_mode_enabled` | fn | `` |
| `is_neg` | fn | `` |
| `is_nonzero` | fn | `` |
| `is_same_size` | fn | `` |
| `is_signed` | fn | `` |
| `is_storage` | fn | `(obj: Any, /) -> TypeGuard[ForwardRef('TypedStorage \| UntypedStorage')]` |
| `is_tensor` | fn | `(obj: Any, /) -> typing_extensions.TypeIs[ForwardRef('torch.Tensor')]` |
| `is_vulkan_available` | fn | `` |
| `is_warn_always_enabled` | fn | `() -> bool` |
| `isclose` | fn | `` |
| `isfinite` | fn | `` |
| `isin` | fn | `` |
| `isinf` | fn | `` |
| `isnan` | fn | `` |
| `isneginf` | fn | `` |
| `isposinf` | fn | `` |
| `isreal` | fn | `` |
| `istft` | fn | `` |
| `jagged` | const | `` |
| `kaiser_window` | fn | `` |
| `kl_div` | fn | `` |
| `kron` | fn | `` |
| `kthvalue` | fn | `` |
| `layer_norm` | fn | `` |
| `layout` | fn | `()` |
| `lcm` | fn | `` |
| `lcm_` | fn | `` |
| `ldexp` | fn | `` |
| `ldexp_` | fn | `` |
| `le` | fn | `` |
| `legacy_contiguous_format` | const | `` |
| `lerp` | fn | `` |
| `less` | fn | `` |
| `less_equal` | fn | `` |
| `lgamma` | fn | `` |
| `linspace` | fn | `` |
| `load` | fn | `(f: Union[str, os.PathLike[str], IO[bytes]], map_location: collections.abc.Callable[[torch.types.Storage, str], torch.ty…` |
| `lobpcg` | fn | `(A: torch.Tensor, k: int \| None = None, B: torch.Tensor \| None = None, X: torch.Tensor \| None = None, n: int \| None …` |
| `log` | fn | `` |
| `log10` | fn | `` |
| `log10_` | fn | `` |
| `log1p` | fn | `` |
| `log1p_` | fn | `` |
| `log2` | fn | `` |
| `log2_` | fn | `` |
| `log_` | fn | `` |
| `log_softmax` | fn | `` |
| `logaddexp` | fn | `` |
| `logaddexp2` | fn | `` |
| `logcumsumexp` | fn | `` |
| `logdet` | fn | `` |
| `logical_and` | fn | `` |
| `logical_not` | fn | `` |
| `logical_or` | fn | `` |
| `logical_xor` | fn | `` |
| `logit` | fn | `` |
| `logit_` | fn | `` |
| `logspace` | fn | `` |
| `logsumexp` | fn | `` |
| `long` | const | `` |
| `lstm` | fn | `` |
| `lstm_cell` | fn | `` |
| `lstsq` | fn | `(input: torch.Tensor, A: torch.Tensor, *, out=None) -> tuple[torch.Tensor, torch.Tensor]` |
| `lt` | fn | `` |
| `lu` | fn | `(*args, **kwargs)` |
| `lu_solve` | fn | `` |
| `lu_unpack` | fn | `` |
| `manual_seed` | fn | `(seed) -> torch._C.Generator` |
| `margin_ranking_loss` | fn | `` |
| `masked_fill` | fn | `` |
| `masked_scatter` | fn | `` |
| `masked_select` | fn | `` |
| `matmul` | fn | `` |
| `matrix_exp` | fn | `` |
| `matrix_power` | fn | `` |
| `matrix_rank` | fn | `(input, tol=None, symmetric=False, *, out=None) -> torch.Tensor` |
| `max` | fn | `` |
| `max_pool1d` | fn | `` |
| `max_pool1d_with_indices` | fn | `` |
| `max_pool2d` | fn | `` |
| `max_pool3d` | fn | `` |
| `maximum` | fn | `` |
| `mean` | fn | `` |
| `median` | fn | `` |
| `memory_format` | fn | `()` |
| `merge_type_from_type_comment` | fn | `` |
| `meshgrid` | fn | `(*tensors, indexing: str \| None = None) -> tuple[torch.Tensor, ...]` |
| `min` | fn | `` |
| `minimum` | fn | `` |
| `miopen_batch_norm` | fn | `` |
| `miopen_convolution` | fn | `` |
| `miopen_convolution_add_relu` | fn | `` |
| `miopen_convolution_relu` | fn | `` |
| `miopen_convolution_transpose` | fn | `` |
| `miopen_ctc_loss` | fn | `` |
| `miopen_depthwise_convolution` | fn | `` |
| `miopen_rnn` | fn | `` |
| `mkldnn_adaptive_avg_pool2d` | fn | `` |
| `mkldnn_convolution` | fn | `` |
| `mkldnn_linear_backward_weights` | fn | `` |
| `mkldnn_max_pool2d` | fn | `` |
| `mkldnn_max_pool3d` | fn | `` |
| `mkldnn_rnn_layer` | fn | `` |
| `mm` | fn | `` |
| `mode` | fn | `` |
| `moveaxis` | fn | `` |
| `movedim` | fn | `` |
| `msort` | fn | `` |
| `mul` | fn | `` |
| `multinomial` | fn | `` |
| `multiply` | fn | `` |
| `mv` | fn | `` |
| `mvlgamma` | fn | `` |
| `nan` | const | `` |
| `nan_to_num` | fn | `` |
| `nan_to_num_` | fn | `` |
| `nanmean` | fn | `` |
| `nanmedian` | fn | `` |
| `nanquantile` | fn | `` |
| `nansum` | fn | `` |
| `narrow` | fn | `` |
| `narrow_copy` | fn | `` |
| `native_batch_norm` | fn | `` |
| `native_channel_shuffle` | fn | `` |
| `native_dropout` | fn | `` |
| `native_group_norm` | fn | `` |
| `native_layer_norm` | fn | `` |
| `native_norm` | fn | `` |
| `ne` | fn | `` |
| `neg` | fn | `` |
| `neg_` | fn | `` |
| `negative` | fn | `` |
| `negative_` | fn | `` |
| `newaxis` | const | `` |
| `nextafter` | fn | `` |
| `no_grad` | fn | `() -> None` |
| `nonzero` | fn | `` |
| `nonzero_static` | fn | `` |
| `norm` | fn | `(input, p: float \| str \| None = 'fro', dim=None, keepdim=False, out=None, dtype=None)` |
| `norm_except_dim` | fn | `` |
| `normal` | fn | `` |
| `not_equal` | fn | `` |
| `nuclear_norm` | fn | `` |
| `numel` | fn | `` |
| `ones` | fn | `` |
| `ones_like` | fn | `` |
| `orgqr` | fn | `` |
| `ormqr` | fn | `` |
| `outer` | fn | `` |
| `pairwise_distance` | fn | `` |
| `parse_ir` | fn | `` |
| `parse_schema` | fn | `` |
| `parse_type_comment` | fn | `` |
| `pca_lowrank` | fn | `(A: torch.Tensor, q: int \| None = None, center: bool = True, niter: int = 2) -> tuple[torch.Tensor, torch.Tensor, torch…` |
| `pdist` | fn | `` |
| `per_channel_affine` | const | `` |
| `per_channel_affine_float_qparams` | const | `` |
| `per_channel_symmetric` | const | `` |
| `per_tensor_affine` | const | `` |
| `per_tensor_symmetric` | const | `` |
| `permute` | fn | `` |
| `permute_copy` | fn | `` |
| `pi` | const | `` |
| `pinverse` | fn | `` |
| `pixel_shuffle` | fn | `` |
| `pixel_unshuffle` | fn | `` |
| `poisson` | fn | `` |
| `poisson_nll_loss` | fn | `` |
| `polar` | fn | `` |
| `polygamma` | fn | `` |
| `positive` | fn | `` |
| `pow` | fn | `` |
| `prelu` | fn | `` |
| `prepare_multiprocessing_environment` | fn | `(path: str) -> None` |
| `preserve_format` | const | `` |
| `prod` | fn | `` |
| `profiler_allow_cudagraph_cupti_lazy_reinit_cuda12` | fn | `()` |
| `promote_types` | fn | `` |
| `put` | fn | `` |
| `q_per_channel_axis` | fn | `` |
| `q_per_channel_scales` | fn | `` |
| `q_per_channel_zero_points` | fn | `` |
| `q_scale` | fn | `` |
| `q_zero_point` | fn | `` |
| `qint32` | const | `` |
| `qint8` | const | `` |
| `qr` | fn | `` |
| `qscheme` | fn | `()` |
| `quantile` | fn | `` |
| `quantize_per_channel` | fn | `` |
| `quantize_per_tensor` | fn | `` |
| `quantize_per_tensor_dynamic` | fn | `` |
| `quantized_batch_norm` | fn | `` |
| `quantized_gru` | fn | `(*args: _P.args, **kwargs: _P.kwargs) -> ~_T` |
| `quantized_gru_cell` | fn | `` |
| `quantized_lstm` | fn | `(*args: _P.args, **kwargs: _P.kwargs) -> ~_T` |
| `quantized_lstm_cell` | fn | `` |
| `quantized_max_pool1d` | fn | `` |
| `quantized_max_pool2d` | fn | `` |
| `quantized_max_pool3d` | fn | `` |
| `quantized_rnn_relu_cell` | fn | `` |
| `quantized_rnn_tanh_cell` | fn | `` |
| `quint2x4` | const | `` |
| `quint4x2` | const | `` |
| `quint8` | const | `` |
| `rad2deg` | fn | `` |
| `rad2deg_` | fn | `` |
| `rand` | fn | `` |
| `rand_like` | fn | `` |
| `randint` | fn | `` |
| `randint_like` | fn | `` |
| `randn` | fn | `` |
| `randn_like` | fn | `` |
| `randperm` | fn | `` |
| `range` | fn | `` |
| `ravel` | fn | `` |
| `real` | fn | `` |
| `reciprocal` | fn | `` |
| `reciprocal_` | fn | `` |
| `relu` | fn | `` |
| `relu_` | fn | `` |
| `remainder` | fn | `` |
| `renorm` | fn | `` |
| `repeat_interleave` | fn | `` |
| `reshape` | fn | `` |
| `resize_as_` | fn | `` |
| `resize_as_sparse_` | fn | `` |
| `resolve_conj` | fn | `` |
| `resolve_neg` | fn | `` |
| `result_type` | fn | `` |
| `rms_norm` | fn | `` |
| `rnn_relu` | fn | `` |
| `rnn_relu_cell` | fn | `` |
| `rnn_tanh` | fn | `` |
| `rnn_tanh_cell` | fn | `` |
| `roll` | fn | `` |
| `rot90` | fn | `` |
| `round` | fn | `` |
| `round_` | fn | `` |
| `row_indices_copy` | fn | `` |
| `row_stack` | fn | `` |
| `rrelu` | fn | `` |
| `rrelu_` | fn | `` |
| `rsqrt` | fn | `` |
| `rsqrt_` | fn | `` |
| `rsub` | fn | `` |
| `saddmm` | fn | `` |
| `save` | fn | `(obj: object, f: Union[str, os.PathLike[str], IO[bytes]], pickle_module: Any = <module 'pickle' from '/usr/lib/python3.1…` |
| `scalar_tensor` | fn | `` |
| `scatter` | fn | `` |
| `scatter_add` | fn | `` |
| `scatter_reduce` | fn | `` |
| `searchsorted` | fn | `` |
| `seed` | fn | `() -> int` |
| `segment_reduce` | fn | `` |
| `select` | fn | `` |
| `select_copy` | fn | `` |
| `select_scatter` | fn | `` |
| `selu` | fn | `` |
| `selu_` | fn | `` |
| `set_anomaly_enabled` | fn | `` |
| `set_autocast_cache_enabled` | fn | `` |
| `set_autocast_cpu_dtype` | fn | `` |
| `set_autocast_cpu_enabled` | fn | `` |
| `set_autocast_dtype` | fn | `` |
| `set_autocast_enabled` | fn | `` |
| `set_autocast_gpu_dtype` | fn | `` |
| `set_autocast_ipu_dtype` | fn | `` |
| `set_autocast_ipu_enabled` | fn | `` |
| `set_autocast_xla_dtype` | fn | `` |
| `set_autocast_xla_enabled` | fn | `` |
| `set_default_device` | fn | `(device: 'Device') -> None` |
| `set_default_dtype` | fn | `(d: 'torch.dtype', /) -> None` |
| `set_default_tensor_type` | fn | `(t: type['torch.Tensor'] \| str, /) -> None` |
| `set_deterministic_debug_mode` | fn | `(debug_mode: int \| str) -> None` |
| `set_float32_matmul_precision` | fn | `(precision: str) -> None` |
| `set_flush_denormal` | fn | `` |
| `set_grad_enabled` | fn | `(mode: bool) -> None` |
| `set_num_interop_threads` | fn | `` |
| `set_num_threads` | fn | `` |
| `set_printoptions` | fn | `(precision=None, threshold=None, edgeitems=None, linewidth=None, profile=None, sci_mode=None)` |
| `set_rng_state` | fn | `(new_state: torch.Tensor) -> None` |
| `set_warn_always` | fn | `(b: bool, /) -> None` |
| `sgn` | fn | `` |
| `short` | const | `` |
| `sigmoid` | fn | `` |
| `sigmoid_` | fn | `` |
| `sign` | fn | `` |
| `signbit` | fn | `` |
| `sin` | fn | `` |
| `sin_` | fn | `` |
| `sinc` | fn | `` |
| `sinc_` | fn | `` |
| `sinh` | fn | `` |
| `sinh_` | fn | `` |
| `slice_copy` | fn | `` |
| `slice_inverse` | fn | `` |
| `slice_scatter` | fn | `` |
| `slogdet` | fn | `` |
| `smm` | fn | `` |
| `softmax` | fn | `` |
| `solve` | fn | `(input: torch.Tensor, A: torch.Tensor, *, out=None) -> tuple[torch.Tensor, torch.Tensor]` |
| `sort` | fn | `` |
| `sparse_bsc` | const | `` |
| `sparse_bsc_tensor` | fn | `` |
| `sparse_bsr` | const | `` |
| `sparse_bsr_tensor` | fn | `` |
| `sparse_compressed_tensor` | fn | `` |
| `sparse_coo` | const | `` |
| `sparse_coo_tensor` | fn | `` |
| `sparse_csc` | const | `` |
| `sparse_csc_tensor` | fn | `` |
| `sparse_csr` | const | `` |
| `sparse_csr_tensor` | fn | `` |
| `split` | fn | `(tensor: torch.Tensor, split_size_or_sections: int \| list[int], dim: int = 0) -> tuple[torch.Tensor, ...]` |
| `split_copy` | fn | `` |
| `split_with_sizes` | fn | `` |
| `split_with_sizes_copy` | fn | `` |
| `spmm` | fn | `` |
| `sqrt` | fn | `` |
| `sqrt_` | fn | `` |
| `square` | fn | `` |
| `square_` | fn | `` |
| `squeeze` | fn | `` |
| `squeeze_copy` | fn | `` |
| `sspaddmm` | fn | `` |
| `stack` | fn | `` |
| `std` | fn | `` |
| `std_mean` | fn | `` |
| `stft` | fn | `(input: torch.Tensor, n_fft: int, hop_length: int \| None = None, win_length: int \| None = None, window: torch.Tensor \…` |
| `strided` | const | `` |
| `sub` | fn | `` |
| `subtract` | fn | `` |
| `sum` | fn | `` |
| `svd` | fn | `` |
| `svd_lowrank` | fn | `(A: torch.Tensor, q: int \| None = 6, niter: int \| None = 2, M: torch.Tensor \| None = None) -> tuple[torch.Tensor, tor…` |
| `swapaxes` | fn | `` |
| `swapdims` | fn | `` |
| `sym_constrain_range` | fn | `` |
| `sym_constrain_range_for_size` | fn | `` |
| `sym_float` | fn | `(a)` |
| `sym_fresh_size` | fn | `(expr)` |
| `sym_int` | fn | `(a)` |
| `sym_ite` | fn | `(b, t, f)` |
| `sym_max` | fn | `(a, b)` |
| `sym_min` | fn | `(a, b)` |
| `sym_not` | fn | `(a)` |
| `sym_sqrt` | fn | `(a)` |
| `sym_sum` | fn | `(*args)` |
| `symeig` | fn | `(input, eigenvectors=False, upper=True, *, out=None) -> tuple[torch.Tensor, torch.Tensor]` |
| `t` | fn | `` |
| `t_copy` | fn | `` |
| `take` | fn | `` |
| `take_along_dim` | fn | `` |
| `tan` | fn | `` |
| `tan_` | fn | `` |
| `tanh` | fn | `` |
| `tanh_` | fn | `` |
| `tensor` | fn | `` |
| `tensor_split` | fn | `` |
| `tensordot` | fn | `(a, b, dims=2, out: torch.Tensor \| None = None)` |
| `thread_safe_generator` | fn | `() -> torch._C.Generator \| None` |
| `threshold` | fn | `` |
| `threshold_` | fn | `` |
| `tile` | fn | `` |
| `to_dlpack` | fn | `` |
| `topk` | fn | `` |
| `trace` | fn | `` |
| `transpose` | fn | `` |
| `transpose_copy` | fn | `` |
| `trapezoid` | fn | `` |
| `trapz` | fn | `` |
| `triangular_solve` | fn | `` |
| `tril` | fn | `` |
| `tril_indices` | fn | `` |
| `triplet_margin_loss` | fn | `` |
| `triu` | fn | `` |
| `triu_indices` | fn | `` |
| `true_divide` | fn | `` |
| `trunc` | fn | `` |
| `trunc_` | fn | `` |
| `typename` | fn | `(obj: Any, /) -> str` |
| `uint1` | const | `` |
| `uint16` | const | `` |
| `uint2` | const | `` |
| `uint3` | const | `` |
| `uint32` | const | `` |
| `uint4` | const | `` |
| `uint5` | const | `` |
| `uint6` | const | `` |
| `uint64` | const | `` |
| `uint7` | const | `` |
| `uint8` | const | `` |
| `unbind` | fn | `` |
| `unbind_copy` | fn | `` |
| `unflatten` | fn | `` |
| `unfold_copy` | fn | `` |
| `unify_type_list` | fn | `` |
| `unique` | fn | `(*args, **kwargs)` |
| `unique_consecutive` | fn | `(*args, **kwargs)` |
| `unravel_index` | fn | `(indices: torch.Tensor, shape: int \| collections.abc.Sequence[int] \| torch.Size) -> tuple[torch.Tensor, ...]` |
| `unsafe_chunk` | fn | `` |
| `unsafe_split` | fn | `` |
| `unsafe_split_with_sizes` | fn | `` |
| `unsqueeze` | fn | `` |
| `unsqueeze_copy` | fn | `` |
| `use_deterministic_algorithms` | fn | `(mode: bool, *, warn_only: bool = False) -> None` |
| `values_copy` | fn | `` |
| `vander` | fn | `` |
| `var` | fn | `` |
| `var_mean` | fn | `` |
| `vdot` | fn | `` |
| `view_as_complex` | fn | `` |
| `view_as_complex_copy` | fn | `` |
| `view_as_real` | fn | `` |
| `view_as_real_copy` | fn | `` |
| `view_copy` | fn | `` |
| `vmap` | fn | `(func: 'Callable[_P, _R]', in_dims: 'in_dims_t' = 0, out_dims: 'out_dims_t' = 0, randomness: 'str' = 'error', *, chunk_s…` |
| `vsplit` | fn | `` |
| `vstack` | fn | `` |
| `wait` | fn | `` |
| `where` | fn | `` |
| `while_loop` | fn | `(cond_fn, body_fn, carried_inputs)` |
| `xlogy` | fn | `` |
| `xlogy_` | fn | `` |
| `zero_` | fn | `` |
| `zeros` | fn | `` |
| `zeros_like` | fn | `` |

## `torch.Tensor` 成员

m=方法，prop=属性。

| 名 | 形态 | 签名 |
|---|---|---|
| `H` | m | `` |
| `T` | m | `` |
| `abs` | m | `` |
| `abs_` | m | `` |
| `absolute` | m | `` |
| `absolute_` | m | `` |
| `acos` | m | `` |
| `acos_` | m | `` |
| `acosh` | m | `` |
| `acosh_` | m | `` |
| `add` | m | `` |
| `add_` | m | `` |
| `addbmm` | m | `` |
| `addbmm_` | m | `` |
| `addcdiv` | m | `` |
| `addcdiv_` | m | `` |
| `addcmul` | m | `` |
| `addcmul_` | m | `` |
| `addmm` | m | `` |
| `addmm_` | m | `` |
| `addmv` | m | `` |
| `addmv_` | m | `` |
| `addr` | m | `` |
| `addr_` | m | `` |
| `adjoint` | m | `` |
| `align_as` | m | `` |
| `align_to` | m | `(self, *names)` |
| `all` | m | `` |
| `allclose` | m | `` |
| `amax` | m | `` |
| `amin` | m | `` |
| `aminmax` | m | `` |
| `angle` | m | `` |
| `any` | m | `` |
| `apply_` | m | `` |
| `arccos` | m | `` |
| `arccos_` | m | `` |
| `arccosh` | m | `` |
| `arccosh_` | m | `` |
| `arcsin` | m | `` |
| `arcsin_` | m | `` |
| `arcsinh` | m | `` |
| `arcsinh_` | m | `` |
| `arctan` | m | `` |
| `arctan2` | m | `` |
| `arctan2_` | m | `` |
| `arctan_` | m | `` |
| `arctanh` | m | `` |
| `arctanh_` | m | `` |
| `argmax` | m | `` |
| `argmin` | m | `` |
| `argsort` | m | `` |
| `argwhere` | m | `` |
| `as_strided` | m | `` |
| `as_strided_` | m | `` |
| `as_strided_scatter` | m | `` |
| `as_subclass` | m | `` |
| `asin` | m | `` |
| `asin_` | m | `` |
| `asinh` | m | `` |
| `asinh_` | m | `` |
| `atan` | m | `` |
| `atan2` | m | `` |
| `atan2_` | m | `` |
| `atan_` | m | `` |
| `atanh` | m | `` |
| `atanh_` | m | `` |
| `backward` | m | `(self, gradient=None, retain_graph=None, create_graph=False, inputs=None)` |
| `baddbmm` | m | `` |
| `baddbmm_` | m | `` |
| `bernoulli` | m | `` |
| `bernoulli_` | m | `` |
| `bfloat16` | m | `` |
| `bincount` | m | `` |
| `bitwise_and` | m | `` |
| `bitwise_and_` | m | `` |
| `bitwise_left_shift` | m | `` |
| `bitwise_left_shift_` | m | `` |
| `bitwise_not` | m | `` |
| `bitwise_not_` | m | `` |
| `bitwise_or` | m | `` |
| `bitwise_or_` | m | `` |
| `bitwise_right_shift` | m | `` |
| `bitwise_right_shift_` | m | `` |
| `bitwise_xor` | m | `` |
| `bitwise_xor_` | m | `` |
| `bmm` | m | `` |
| `bool` | m | `` |
| `broadcast_to` | m | `` |
| `byte` | m | `` |
| `cauchy_` | m | `` |
| `ccol_indices` | m | `` |
| `cdouble` | m | `` |
| `ceil` | m | `` |
| `ceil_` | m | `` |
| `cfloat` | m | `` |
| `chalf` | m | `` |
| `char` | m | `` |
| `cholesky` | m | `` |
| `cholesky_inverse` | m | `` |
| `cholesky_solve` | m | `` |
| `chunk` | m | `` |
| `clamp` | m | `` |
| `clamp_` | m | `` |
| `clamp_max` | m | `` |
| `clamp_max_` | m | `` |
| `clamp_min` | m | `` |
| `clamp_min_` | m | `` |
| `clip` | m | `` |
| `clip_` | m | `` |
| `clone` | m | `` |
| `coalesce` | m | `` |
| `col_indices` | m | `` |
| `conj` | m | `` |
| `conj_physical` | m | `` |
| `conj_physical_` | m | `` |
| `contiguous` | m | `` |
| `copy_` | m | `` |
| `copysign` | m | `` |
| `copysign_` | m | `` |
| `corrcoef` | m | `` |
| `cos` | m | `` |
| `cos_` | m | `` |
| `cosh` | m | `` |
| `cosh_` | m | `` |
| `count_nonzero` | m | `` |
| `cov` | m | `` |
| `cpu` | m | `` |
| `cross` | m | `` |
| `crow_indices` | m | `` |
| `cuda` | m | `` |
| `cummax` | m | `` |
| `cummin` | m | `` |
| `cumprod` | m | `` |
| `cumprod_` | m | `` |
| `cumsum` | m | `` |
| `cumsum_` | m | `` |
| `data` | m | `` |
| `data_ptr` | m | `` |
| `deg2rad` | m | `` |
| `deg2rad_` | m | `` |
| `dense_dim` | m | `` |
| `dequantize` | m | `` |
| `det` | m | `` |
| `detach` | m | `` |
| `detach_` | m | `` |
| `device` | m | `` |
| `diag` | m | `` |
| `diag_embed` | m | `` |
| `diagflat` | m | `` |
| `diagonal` | m | `` |
| `diagonal_scatter` | m | `` |
| `diff` | m | `` |
| `digamma` | m | `` |
| `digamma_` | m | `` |
| `dim` | m | `` |
| `dim_order` | m | `(self, *, ambiguity_check: bool \| list[torch.memory_format] = False)` |
| `dist` | m | `` |
| `div` | m | `` |
| `div_` | m | `` |
| `divide` | m | `` |
| `divide_` | m | `` |
| `dot` | m | `` |
| `double` | m | `` |
| `dsplit` | m | `` |
| `dtype` | m | `` |
| `eig` | m | `(self, eigenvectors=False)` |
| `element_size` | m | `` |
| `eq` | m | `` |
| `eq_` | m | `` |
| `equal` | m | `` |
| `erf` | m | `` |
| `erf_` | m | `` |
| `erfc` | m | `` |
| `erfc_` | m | `` |
| `erfinv` | m | `` |
| `erfinv_` | m | `` |
| `exp` | m | `` |
| `exp2` | m | `` |
| `exp2_` | m | `` |
| `exp_` | m | `` |
| `expand` | m | `` |
| `expand_as` | m | `` |
| `expm1` | m | `` |
| `expm1_` | m | `` |
| `exponential_` | m | `` |
| `fill_` | m | `` |
| `fill_diagonal_` | m | `` |
| `fix` | m | `` |
| `fix_` | m | `` |
| `flatten` | m | `` |
| `flip` | m | `` |
| `fliplr` | m | `` |
| `flipud` | m | `` |
| `float` | m | `` |
| `float_power` | m | `` |
| `float_power_` | m | `` |
| `floor` | m | `` |
| `floor_` | m | `` |
| `floor_divide` | m | `` |
| `floor_divide_` | m | `` |
| `fmax` | m | `` |
| `fmin` | m | `` |
| `fmod` | m | `` |
| `fmod_` | m | `` |
| `frac` | m | `` |
| `frac_` | m | `` |
| `frexp` | m | `` |
| `gather` | m | `` |
| `gcd` | m | `` |
| `gcd_` | m | `` |
| `ge` | m | `` |
| `ge_` | m | `` |
| `geometric_` | m | `` |
| `geqrf` | m | `` |
| `ger` | m | `` |
| `get_device` | m | `` |
| `grad` | m | `` |
| `grad_dtype` | m | `` |
| `grad_fn` | m | `` |
| `greater` | m | `` |
| `greater_` | m | `` |
| `greater_equal` | m | `` |
| `greater_equal_` | m | `` |
| `gt` | m | `` |
| `gt_` | m | `` |
| `half` | m | `` |
| `hardshrink` | m | `` |
| `has_names` | m | `` |
| `hash_tensor` | m | `` |
| `heaviside` | m | `` |
| `heaviside_` | m | `` |
| `histc` | m | `` |
| `histogram` | m | `` |
| `hsplit` | m | `` |
| `hypot` | m | `` |
| `hypot_` | m | `` |
| `i0` | m | `` |
| `i0_` | m | `` |
| `igamma` | m | `` |
| `igamma_` | m | `` |
| `igammac` | m | `` |
| `igammac_` | m | `` |
| `imag` | m | `` |
| `index` | m | `(self, positions, dims)` |
| `index_add` | m | `` |
| `index_add_` | m | `` |
| `index_copy` | m | `` |
| `index_copy_` | m | `` |
| `index_fill` | m | `` |
| `index_fill_` | m | `` |
| `index_put` | m | `` |
| `index_put_` | m | `` |
| `index_reduce` | m | `` |
| `index_reduce_` | m | `` |
| `index_select` | m | `` |
| `indices` | m | `` |
| `inner` | m | `` |
| `int` | m | `` |
| `int_repr` | m | `` |
| `inverse` | m | `` |
| `ipu` | m | `` |
| `is_coalesced` | m | `` |
| `is_complex` | m | `` |
| `is_conj` | m | `` |
| `is_contiguous` | m | `` |
| `is_cpu` | m | `` |
| `is_cuda` | m | `` |
| `is_distributed` | m | `` |
| `is_floating_point` | m | `` |
| `is_inference` | m | `` |
| `is_ipu` | m | `` |
| `is_leaf` | m | `` |
| `is_maia` | m | `` |
| `is_meta` | m | `` |
| `is_mkldnn` | m | `` |
| `is_mps` | m | `` |
| `is_mtia` | m | `` |
| `is_neg` | m | `` |
| `is_nested` | m | `` |
| `is_nonzero` | m | `` |
| `is_pinned` | m | `` |
| `is_quantized` | m | `` |
| `is_same_size` | m | `` |
| `is_set_to` | m | `` |
| `is_shared` | m | `(self)` |
| `is_signed` | m | `` |
| `is_sparse` | m | `` |
| `is_sparse_csr` | m | `` |
| `is_vulkan` | m | `` |
| `is_xla` | m | `` |
| `is_xpu` | m | `` |
| `isclose` | m | `` |
| `isfinite` | m | `` |
| `isinf` | m | `` |
| `isnan` | m | `` |
| `isneginf` | m | `` |
| `isposinf` | m | `` |
| `isreal` | m | `` |
| `istft` | m | `(self, n_fft: int, hop_length: int \| None = None, win_length: int \| None = None, window: 'Tensor \| None' = None, cent…` |
| `item` | m | `` |
| `itemsize` | m | `` |
| `kron` | m | `` |
| `kthvalue` | m | `` |
| `layout` | m | `` |
| `lcm` | m | `` |
| `lcm_` | m | `` |
| `ldexp` | m | `` |
| `ldexp_` | m | `` |
| `le` | m | `` |
| `le_` | m | `` |
| `lerp` | m | `` |
| `lerp_` | m | `` |
| `less` | m | `` |
| `less_` | m | `` |
| `less_equal` | m | `` |
| `less_equal_` | m | `` |
| `lgamma` | m | `` |
| `lgamma_` | m | `` |
| `log` | m | `` |
| `log10` | m | `` |
| `log10_` | m | `` |
| `log1p` | m | `` |
| `log1p_` | m | `` |
| `log2` | m | `` |
| `log2_` | m | `` |
| `log_` | m | `` |
| `log_normal_` | m | `` |
| `log_softmax` | m | `` |
| `logaddexp` | m | `` |
| `logaddexp2` | m | `` |
| `logcumsumexp` | m | `` |
| `logdet` | m | `` |
| `logical_and` | m | `` |
| `logical_and_` | m | `` |
| `logical_not` | m | `` |
| `logical_not_` | m | `` |
| `logical_or` | m | `` |
| `logical_or_` | m | `` |
| `logical_xor` | m | `` |
| `logical_xor_` | m | `` |
| `logit` | m | `` |
| `logit_` | m | `` |
| `logsumexp` | m | `` |
| `long` | m | `` |
| `lstsq` | m | `(self, other)` |
| `lt` | m | `` |
| `lt_` | m | `` |
| `lu` | m | `(self, pivot=True, get_infos=False)` |
| `lu_solve` | m | `` |
| `mH` | m | `` |
| `mT` | m | `` |
| `map2_` | m | `` |
| `map_` | m | `` |
| `masked_fill` | m | `` |
| `masked_fill_` | m | `` |
| `masked_scatter` | m | `` |
| `masked_scatter_` | m | `` |
| `masked_select` | m | `` |
| `matmul` | m | `` |
| `matrix_exp` | m | `` |
| `matrix_power` | m | `` |
| `max` | m | `` |
| `maximum` | m | `` |
| `mean` | m | `` |
| `median` | m | `` |
| `min` | m | `` |
| `minimum` | m | `` |
| `mm` | m | `` |
| `mode` | m | `` |
| `module_load` | m | `(self, other, assign=False)` |
| `moveaxis` | m | `` |
| `movedim` | m | `` |
| `msort` | m | `` |
| `mtia` | m | `` |
| `mul` | m | `` |
| `mul_` | m | `` |
| `multinomial` | m | `` |
| `multiply` | m | `` |
| `multiply_` | m | `` |
| `mv` | m | `` |
| `mvlgamma` | m | `` |
| `mvlgamma_` | m | `` |
| `name` | m | `` |
| `names` | m | `` |
| `nan_to_num` | m | `` |
| `nan_to_num_` | m | `` |
| `nanmean` | m | `` |
| `nanmedian` | m | `` |
| `nanquantile` | m | `` |
| `nansum` | m | `` |
| `narrow` | m | `` |
| `narrow_copy` | m | `` |
| `nbytes` | m | `` |
| `ndim` | m | `` |
| `ndimension` | m | `` |
| `ne` | m | `` |
| `ne_` | m | `` |
| `neg` | m | `` |
| `neg_` | m | `` |
| `negative` | m | `` |
| `negative_` | m | `` |
| `nelement` | m | `` |
| `new` | m | `` |
| `new_empty` | m | `` |
| `new_empty_strided` | m | `` |
| `new_full` | m | `` |
| `new_ones` | m | `` |
| `new_tensor` | m | `` |
| `new_zeros` | m | `` |
| `nextafter` | m | `` |
| `nextafter_` | m | `` |
| `nonzero` | m | `` |
| `nonzero_static` | m | `` |
| `norm` | m | `(self, p: float \| str \| None = 'fro', dim=None, keepdim=False, dtype=None)` |
| `normal_` | m | `` |
| `not_equal` | m | `` |
| `not_equal_` | m | `` |
| `numel` | m | `` |
| `numpy` | m | `` |
| `orgqr` | m | `` |
| `ormqr` | m | `` |
| `outer` | m | `` |
| `output_nr` | m | `` |
| `permute` | m | `` |
| `pin_memory` | m | `` |
| `pinverse` | m | `` |
| `polygamma` | m | `` |
| `polygamma_` | m | `` |
| `positive` | m | `` |
| `pow` | m | `` |
| `pow_` | m | `` |
| `prelu` | m | `` |
| `prod` | m | `` |
| `put` | m | `` |
| `put_` | m | `` |
| `q_per_channel_axis` | m | `` |
| `q_per_channel_scales` | m | `` |
| `q_per_channel_zero_points` | m | `` |
| `q_scale` | m | `` |
| `q_zero_point` | m | `` |
| `qr` | m | `` |
| `qscheme` | m | `` |
| `quantile` | m | `` |
| `rad2deg` | m | `` |
| `rad2deg_` | m | `` |
| `random_` | m | `` |
| `ravel` | m | `` |
| `real` | m | `` |
| `reciprocal` | m | `` |
| `reciprocal_` | m | `` |
| `record_stream` | m | `` |
| `refine_names` | m | `(self, *names)` |
| `register_hook` | m | `(self, hook)` |
| `register_post_accumulate_grad_hook` | m | `(self, hook)` |
| `reinforce` | m | `(self, reward)` |
| `relu` | m | `` |
| `relu_` | m | `` |
| `remainder` | m | `` |
| `remainder_` | m | `` |
| `rename` | m | `(self, *names, **rename_map)` |
| `rename_` | m | `(self, *names, **rename_map)` |
| `renorm` | m | `` |
| `renorm_` | m | `` |
| `repeat` | m | `` |
| `repeat_interleave` | m | `` |
| `requires_grad` | m | `` |
| `requires_grad_` | m | `` |
| `reshape` | m | `` |
| `reshape_as` | m | `` |
| `resize` | m | `(self, *sizes)` |
| `resize_` | m | `` |
| `resize_as` | m | `(self, tensor)` |
| `resize_as_` | m | `` |
| `resize_as_sparse_` | m | `` |
| `resolve_conj` | m | `` |
| `resolve_neg` | m | `` |
| `retain_grad` | m | `` |
| `retains_grad` | m | `` |
| `roll` | m | `` |
| `rot90` | m | `` |
| `round` | m | `` |
| `round_` | m | `` |
| `row_indices` | m | `` |
| `rsqrt` | m | `` |
| `rsqrt_` | m | `` |
| `scatter` | m | `` |
| `scatter_` | m | `` |
| `scatter_add` | m | `` |
| `scatter_add_` | m | `` |
| `scatter_reduce` | m | `` |
| `scatter_reduce_` | m | `` |
| `select` | m | `` |
| `select_scatter` | m | `` |
| `set_` | m | `` |
| `sgn` | m | `` |
| `sgn_` | m | `` |
| `shape` | m | `` |
| `share_memory_` | m | `(self)` |
| `short` | m | `` |
| `sigmoid` | m | `` |
| `sigmoid_` | m | `` |
| `sign` | m | `` |
| `sign_` | m | `` |
| `signbit` | m | `` |
| `sin` | m | `` |
| `sin_` | m | `` |
| `sinc` | m | `` |
| `sinc_` | m | `` |
| `sinh` | m | `` |
| `sinh_` | m | `` |
| `size` | m | `` |
| `slice_inverse` | m | `` |
| `slice_scatter` | m | `` |
| `slogdet` | m | `` |
| `smm` | m | `` |
| `softmax` | m | `` |
| `solve` | m | `(self, other)` |
| `sort` | m | `` |
| `sparse_dim` | m | `` |
| `sparse_mask` | m | `` |
| `sparse_resize_` | m | `` |
| `sparse_resize_and_clear_` | m | `` |
| `split` | m | `(self, split_size, dim=0)` |
| `split_with_sizes` | m | `` |
| `sqrt` | m | `` |
| `sqrt_` | m | `` |
| `square` | m | `` |
| `square_` | m | `` |
| `squeeze` | m | `` |
| `squeeze_` | m | `` |
| `sspaddmm` | m | `` |
| `std` | m | `` |
| `stft` | m | `(self, n_fft: int, hop_length: int \| None = None, win_length: int \| None = None, window: 'Tensor \| None' = None, cent…` |
| `storage` | m | `(self)` |
| `storage_offset` | m | `` |
| `storage_type` | m | `(self)` |
| `stride` | m | `` |
| `sub` | m | `` |
| `sub_` | m | `` |
| `subtract` | m | `` |
| `subtract_` | m | `` |
| `sum` | m | `` |
| `sum_to_size` | m | `` |
| `svd` | m | `` |
| `swapaxes` | m | `` |
| `swapaxes_` | m | `` |
| `swapdims` | m | `` |
| `swapdims_` | m | `` |
| `symeig` | m | `(self, eigenvectors=False)` |
| `t` | m | `` |
| `t_` | m | `` |
| `take` | m | `` |
| `take_along_dim` | m | `` |
| `tan` | m | `` |
| `tan_` | m | `` |
| `tanh` | m | `` |
| `tanh_` | m | `` |
| `tensor_split` | m | `` |
| `tile` | m | `` |
| `to` | m | `` |
| `to_dense` | m | `` |
| `to_mkldnn` | m | `` |
| `to_padded_tensor` | m | `` |
| `to_sparse` | m | `` |
| `to_sparse_bsc` | m | `` |
| `to_sparse_bsr` | m | `` |
| `to_sparse_coo` | m | `(self)` |
| `to_sparse_csc` | m | `` |
| `to_sparse_csr` | m | `` |
| `tolist` | m | `` |
| `topk` | m | `` |
| `trace` | m | `` |
| `transpose` | m | `` |
| `transpose_` | m | `` |
| `triangular_solve` | m | `` |
| `tril` | m | `` |
| `tril_` | m | `` |
| `triu` | m | `` |
| `triu_` | m | `` |
| `true_divide` | m | `` |
| `true_divide_` | m | `` |
| `trunc` | m | `` |
| `trunc_` | m | `` |
| `type` | m | `` |
| `type_as` | m | `` |
| `unbind` | m | `` |
| `unflatten` | m | `(self, dim, sizes)` |
| `unfold` | m | `` |
| `uniform_` | m | `` |
| `unique` | m | `(self, sorted=True, return_inverse=False, return_counts=False, dim=None)` |
| `unique_consecutive` | m | `(self, return_inverse=False, return_counts=False, dim=None)` |
| `unsafe_chunk` | m | `` |
| `unsafe_split` | m | `` |
| `unsafe_split_with_sizes` | m | `` |
| `unsqueeze` | m | `` |
| `unsqueeze_` | m | `` |
| `untyped_storage` | m | `` |
| `values` | m | `` |
| `var` | m | `` |
| `vdot` | m | `` |
| `view` | m | `` |
| `view_as` | m | `` |
| `volatile` | m | `` |
| `vsplit` | m | `` |
| `where` | m | `` |
| `xlogy` | m | `` |
| `xlogy_` | m | `` |
| `xpu` | m | `` |
| `zero_` | m | `` |

## `torch.nn` 模块

nn.Module 子类。

| 名 | 形态 | 签名 |
|---|---|---|
| `AdaptiveAvgPool1d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]]) -> None` |
| `AdaptiveAvgPool2d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]]) -> None` |
| `AdaptiveAvgPool3d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]]) -> None` |
| `AdaptiveLogSoftmaxWithLoss` | cls | `(self, in_features: int, n_classes: int, cutoffs: collections.abc.Sequence[int], div_value: float = 4.0, head_bias: bool…` |
| `AdaptiveMaxPool1d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]], return_indices: bool = False) -> None` |
| `AdaptiveMaxPool2d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]], return_indices: bool = False) -> None` |
| `AdaptiveMaxPool3d` | cls | `(self, output_size: Union[int, NoneType, tuple[int \| None, ...]], return_indices: bool = False) -> None` |
| `AlphaDropout` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `AvgPool1d` | cls | `(self, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int]] = None, padding: Union[int, tuple[int]] = 0, …` |
| `AvgPool2d` | cls | `(self, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int], NoneType] = None, padding: Union[in…` |
| `AvgPool3d` | cls | `(self, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int, int, int], NoneType] = None, padding…` |
| `BCELoss` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `BCEWithLogitsLoss` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, reduce=None, reduction: str = 'mean', pos_weight: torch.T…` |
| `BatchNorm1d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float \| None = 0.1, affine: bool = True, track_running_stats: b…` |
| `BatchNorm2d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float \| None = 0.1, affine: bool = True, track_running_stats: b…` |
| `BatchNorm3d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float \| None = 0.1, affine: bool = True, track_running_stats: b…` |
| `Bilinear` | cls | `(self, in1_features: int, in2_features: int, out_features: int, bias: bool = True, device=None, dtype=None) -> None` |
| `Buffer` | cls | `(self, /, *args, **kwargs)` |
| `CELU` | cls | `(self, alpha: float = 1.0, inplace: bool = False) -> None` |
| `CTCLoss` | cls | `(self, blank: int = 0, reduction: str = 'mean', zero_infinity: bool = False) -> None` |
| `ChannelShuffle` | cls | `(self, groups: int) -> None` |
| `CircularPad1d` | cls | `(self, padding: Union[int, tuple[int, int]]) -> None` |
| `CircularPad2d` | cls | `(self, padding: Union[int, tuple[int, int, int, int]]) -> None` |
| `CircularPad3d` | cls | `(self, padding: Union[int, tuple[int, int, int, int, int, int]]) -> None` |
| `ConstantPad1d` | cls | `(self, padding: Union[int, tuple[int, int]], value: float) -> None` |
| `ConstantPad2d` | cls | `(self, padding: Union[int, tuple[int, int, int, int]], value: float) -> None` |
| `ConstantPad3d` | cls | `(self, padding: Union[int, tuple[int, int, int, int, int, int]], value: float) -> None` |
| `Container` | cls | `(self, **kwargs: 'Any') -> 'None'` |
| `Conv1d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int]] = 1, pad…` |
| `Conv2d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int]…` |
| `Conv3d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int,…` |
| `ConvTranspose1d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int]] = 1, pad…` |
| `ConvTranspose2d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int]…` |
| `ConvTranspose3d` | cls | `(self, in_channels: int, out_channels: int, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int,…` |
| `CosineEmbeddingLoss` | cls | `(self, margin: float = 0.0, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `CosineSimilarity` | cls | `(self, dim: int = 1, eps: float = 1e-08) -> None` |
| `CrossEntropyLoss` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, ignore_index: int = -100, reduce=None, reduction: str = '…` |
| `CrossMapLRN2d` | cls | `(self, size: int, alpha: float = 0.0001, beta: float = 0.75, k: float = 1) -> None` |
| `DataParallel` | cls | `(self, module: ~T, device_ids: collections.abc.Sequence[int \| torch.device] \| None = None, output_device: int \| torch…` |
| `Dropout` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `Dropout1d` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `Dropout2d` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `Dropout3d` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `ELU` | cls | `(self, alpha: float = 1.0, inplace: bool = False) -> None` |
| `Embedding` | cls | `(self, num_embeddings: int, embedding_dim: int, padding_idx: int \| None = None, max_norm: float \| None = None, norm_ty…` |
| `EmbeddingBag` | cls | `(self, num_embeddings: int, embedding_dim: int, max_norm: float \| None = None, norm_type: float = 2.0, scale_grad_by_fr…` |
| `FeatureAlphaDropout` | cls | `(self, p: float = 0.5, inplace: bool = False) -> None` |
| `Flatten` | cls | `(self, start_dim: int = 1, end_dim: int = -1) -> None` |
| `Fold` | cls | `(self, output_size: Union[int, tuple[int, ...]], kernel_size: Union[int, tuple[int, ...]], dilation: Union[int, tuple[in…` |
| `FractionalMaxPool2d` | cls | `(self, kernel_size: Union[int, tuple[int, int]], output_size: Union[int, tuple[int, int], NoneType] = None, output_ratio…` |
| `FractionalMaxPool3d` | cls | `(self, kernel_size: Union[int, tuple[int, int, int]], output_size: Union[int, tuple[int, int, int], NoneType] = None, ou…` |
| `GELU` | cls | `(self, approximate: str = 'none') -> None` |
| `GLU` | cls | `(self, dim: int = -1) -> None` |
| `GRU` | cls | `(self, *args, **kwargs)` |
| `GRUCell` | cls | `(self, input_size: int, hidden_size: int, bias: bool = True, device=None, dtype=None) -> None` |
| `GaussianNLLLoss` | cls | `(self, *, full: bool = False, eps: float = 1e-06, reduction: str = 'mean') -> None` |
| `GroupNorm` | cls | `(self, num_groups: int, num_channels: int, eps: float = 1e-05, affine: bool = True, device=None, dtype=None, *, bias: bo…` |
| `Hardshrink` | cls | `(self, lambd: float = 0.5) -> None` |
| `Hardsigmoid` | cls | `(self, inplace: bool = False) -> None` |
| `Hardswish` | cls | `(self, inplace: bool = False) -> None` |
| `Hardtanh` | cls | `(self, min_val: float = -1.0, max_val: float = 1.0, inplace: bool = False, min_value: float \| None = None, max_value: f…` |
| `HingeEmbeddingLoss` | cls | `(self, margin: float = 1.0, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `HuberLoss` | cls | `(self, reduction: str = 'mean', delta: float = 1.0) -> None` |
| `Identity` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `InstanceNorm1d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float = 0.1, affine: bool = False, track_running_stats: bool = F…` |
| `InstanceNorm2d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float = 0.1, affine: bool = False, track_running_stats: bool = F…` |
| `InstanceNorm3d` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float = 0.1, affine: bool = False, track_running_stats: bool = F…` |
| `KLDivLoss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean', log_target: bool = False) -> None` |
| `L1Loss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `LPPool1d` | cls | `(self, norm_type: float, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None,…` |
| `LPPool2d` | cls | `(self, norm_type: float, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None,…` |
| `LPPool3d` | cls | `(self, norm_type: float, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None,…` |
| `LSTM` | cls | `(self, *args, **kwargs)` |
| `LSTMCell` | cls | `(self, input_size: int, hidden_size: int, bias: bool = True, device=None, dtype=None) -> None` |
| `LayerNorm` | cls | `(self, normalized_shape: int \| list[int] \| torch.Size, eps: float = 1e-05, elementwise_affine: bool = True, bias: bool…` |
| `LazyBatchNorm1d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyBatchNorm2d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyBatchNorm3d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyConv1d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int]] = 1, padding: Union[int, t…` |
| `LazyConv2d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int]] = 1, padding: Un…` |
| `LazyConv3d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int, int, int]] = 1, p…` |
| `LazyConvTranspose1d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int]] = 1, padding: Union[int, t…` |
| `LazyConvTranspose2d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int]] = 1, padding: Un…` |
| `LazyConvTranspose3d` | cls | `(self, out_channels: int, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int, int, int]] = 1, p…` |
| `LazyInstanceNorm1d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyInstanceNorm2d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyInstanceNorm3d` | cls | `(self, eps=1e-05, momentum=0.1, affine=True, track_running_stats=True, device=None, dtype=None, *, bias=True) -> None` |
| `LazyLinear` | cls | `(self, out_features: int, bias: bool = True, device=None, dtype=None) -> None` |
| `LeakyReLU` | cls | `(self, negative_slope: float = 0.01, inplace: bool = False) -> None` |
| `Linear` | cls | `(self, in_features: int, out_features: int, bias: bool = True, device=None, dtype=None) -> None` |
| `LocalResponseNorm` | cls | `(self, size: int, alpha: float = 0.0001, beta: float = 0.75, k: float = 1.0) -> None` |
| `LogSigmoid` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `LogSoftmax` | cls | `(self, dim: int \| None = None) -> None` |
| `MSELoss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `MarginRankingLoss` | cls | `(self, margin: float = 0.0, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `MaxPool1d` | cls | `(self, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None, padding: Union[in…` |
| `MaxPool2d` | cls | `(self, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None, padding: Union[in…` |
| `MaxPool3d` | cls | `(self, kernel_size: Union[int, tuple[int, ...]], stride: Union[int, tuple[int, ...], NoneType] = None, padding: Union[in…` |
| `MaxUnpool1d` | cls | `(self, kernel_size: Union[int, tuple[int]], stride: Union[int, tuple[int], NoneType] = None, padding: Union[int, tuple[i…` |
| `MaxUnpool2d` | cls | `(self, kernel_size: Union[int, tuple[int, int]], stride: Union[int, tuple[int, int], NoneType] = None, padding: Union[in…` |
| `MaxUnpool3d` | cls | `(self, kernel_size: Union[int, tuple[int, int, int]], stride: Union[int, tuple[int, int, int], NoneType] = None, padding…` |
| `Mish` | cls | `(self, inplace: bool = False) -> None` |
| `Module` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `ModuleDict` | cls | `(self, modules: 'Mapping[str, Module] \| None' = None) -> 'None'` |
| `ModuleList` | cls | `(self, modules: 'Iterable[Module] \| None' = None) -> 'None'` |
| `MultiLabelMarginLoss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `MultiLabelSoftMarginLoss` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `MultiMarginLoss` | cls | `(self, p: int = 1, margin: float = 1.0, weight: torch.Tensor \| None = None, size_average=None, reduce=None, reduction: …` |
| `MultiheadAttention` | cls | `(self, embed_dim, num_heads, dropout=0.0, bias=True, add_bias_kv=False, add_zero_attn=False, kdim=None, vdim=None, batch…` |
| `NLLLoss` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, ignore_index: int = -100, reduce=None, reduction: str = '…` |
| `NLLLoss2d` | cls | `(self, weight: torch.Tensor \| None = None, size_average=None, ignore_index: int = -100, reduce=None, reduction: str = '…` |
| `PReLU` | cls | `(self, num_parameters: int = 1, init: float = 0.25, device=None, dtype=None) -> None` |
| `PairwiseDistance` | cls | `(self, p: float = 2.0, eps: float = 1e-06, keepdim: bool = False) -> None` |
| `Parameter` | cls | `(self, /, *args, **kwargs)` |
| `ParameterDict` | cls | `(self, parameters: 'Any' = None) -> 'None'` |
| `ParameterList` | cls | `(self, values: 'Iterable[Any] \| None' = None) -> 'None'` |
| `PixelShuffle` | cls | `(self, upscale_factor: int) -> None` |
| `PixelUnshuffle` | cls | `(self, downscale_factor: int) -> None` |
| `PoissonNLLLoss` | cls | `(self, log_input: bool = True, full: bool = False, size_average=None, eps: float = 1e-08, reduce=None, reduction: str = …` |
| `RMSNorm` | cls | `(self, normalized_shape: int \| list[int] \| torch.Size, eps: float \| None = None, elementwise_affine: bool = True, dev…` |
| `RNN` | cls | `(self, *args, **kwargs)` |
| `RNNBase` | cls | `(self, mode: str, input_size: int, hidden_size: int, num_layers: int = 1, bias: bool = True, batch_first: bool = False, …` |
| `RNNCell` | cls | `(self, input_size: int, hidden_size: int, bias: bool = True, nonlinearity: str = 'tanh', device=None, dtype=None) -> Non…` |
| `RNNCellBase` | cls | `(self, input_size: int, hidden_size: int, bias: bool, num_chunks: int, device=None, dtype=None) -> None` |
| `RReLU` | cls | `(self, lower: float = 0.125, upper: float = 0.3333333333333333, inplace: bool = False) -> None` |
| `ReLU` | cls | `(self, inplace: bool = False) -> None` |
| `ReLU6` | cls | `(self, inplace: bool = False) -> None` |
| `ReflectionPad1d` | cls | `(self, padding: Union[int, tuple[int, int]]) -> None` |
| `ReflectionPad2d` | cls | `(self, padding: Union[int, tuple[int, int, int, int]]) -> None` |
| `ReflectionPad3d` | cls | `(self, padding: Union[int, tuple[int, int, int, int, int, int]]) -> None` |
| `ReplicationPad1d` | cls | `(self, padding: Union[int, tuple[int, int]]) -> None` |
| `ReplicationPad2d` | cls | `(self, padding: Union[int, tuple[int, int, int, int]]) -> None` |
| `ReplicationPad3d` | cls | `(self, padding: Union[int, tuple[int, int, int, int, int, int]]) -> None` |
| `SELU` | cls | `(self, inplace: bool = False) -> None` |
| `Sequential` | cls | `(self, *args)` |
| `SiLU` | cls | `(self, inplace: bool = False) -> None` |
| `Sigmoid` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `SmoothL1Loss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean', beta: float = 1.0) -> None` |
| `SoftMarginLoss` | cls | `(self, size_average=None, reduce=None, reduction: str = 'mean') -> None` |
| `Softmax` | cls | `(self, dim: int \| None = None) -> None` |
| `Softmax2d` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `Softmin` | cls | `(self, dim: int \| None = None) -> None` |
| `Softplus` | cls | `(self, beta: float = 1.0, threshold: float = 20.0) -> None` |
| `Softshrink` | cls | `(self, lambd: float = 0.5) -> None` |
| `Softsign` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `SyncBatchNorm` | cls | `(self, num_features: int, eps: float = 1e-05, momentum: float \| None = 0.1, affine: bool = True, track_running_stats: b…` |
| `Tanh` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `Tanhshrink` | cls | `(self, *args: Any, **kwargs: Any) -> None` |
| `Threshold` | cls | `(self, threshold: float, value: float, inplace: bool = False) -> None` |
| `Transformer` | cls | `(self, d_model: int = 512, nhead: int = 8, num_encoder_layers: int = 6, num_decoder_layers: int = 6, dim_feedforward: in…` |
| `TransformerDecoder` | cls | `(self, decoder_layer: 'TransformerDecoderLayer', num_layers: int, norm: torch.nn.modules.module.Module \| None = None) -…` |
| `TransformerDecoderLayer` | cls | `(self, d_model: int, nhead: int, dim_feedforward: int = 2048, dropout: float = 0.1, activation: str \| collections.abc.C…` |
| `TransformerEncoder` | cls | `(self, encoder_layer: 'TransformerEncoderLayer', num_layers: int, norm: torch.nn.modules.module.Module \| None = None, e…` |
| `TransformerEncoderLayer` | cls | `(self, d_model: int, nhead: int, dim_feedforward: int = 2048, dropout: float = 0.1, activation: str \| collections.abc.C…` |
| `TripletMarginLoss` | cls | `(self, margin: float = 1.0, p: float = 2.0, eps: float = 1e-06, swap: bool = False, size_average=None, reduce=None, redu…` |
| `TripletMarginWithDistanceLoss` | cls | `(self, *, distance_function: collections.abc.Callable[[torch.Tensor, torch.Tensor], torch.Tensor] \| None = None, margin…` |
| `Unflatten` | cls | `(self, dim: int \| str, unflattened_size: torch.Size \| list[int] \| tuple[int, ...] \| tuple[tuple[str, int]]) -> None` |
| `Unfold` | cls | `(self, kernel_size: Union[int, tuple[int, ...]], dilation: Union[int, tuple[int, ...]] = 1, padding: Union[int, tuple[in…` |
| `UninitializedBuffer` | cls | `(self, /, *args, **kwargs)` |
| `UninitializedParameter` | cls | `(self, /, *args, **kwargs)` |
| `Upsample` | cls | `(self, size: Union[int, tuple[int, ...], NoneType] = None, scale_factor: Union[float, tuple[float, ...], NoneType] = Non…` |
| `UpsamplingBilinear2d` | cls | `(self, size: Union[int, tuple[int, int], NoneType] = None, scale_factor: Union[float, tuple[float, float], NoneType] = N…` |
| `UpsamplingNearest2d` | cls | `(self, size: Union[int, tuple[int, int], NoneType] = None, scale_factor: Union[float, tuple[float, float], NoneType] = N…` |
| `ZeroPad1d` | cls | `(self, padding: Union[int, tuple[int, int]]) -> None` |
| `ZeroPad2d` | cls | `(self, padding: Union[int, tuple[int, int, int, int]]) -> None` |
| `ZeroPad3d` | cls | `(self, padding: Union[int, tuple[int, int, int, int, int, int]]) -> None` |

## `torch.nn.functional`

无状态函数。

| 名 | 形态 | 签名 |
|---|---|---|
| `Callable` | fn | `()` |
| `DType` | fn | `` |
| `Optional` | fn | `(*args, **kwds)` |
| `ScalingType` | fn | `` |
| `SwizzleType` | fn | `` |
| `Tensor` | fn | `` |
| `adaptive_avg_pool1d` | fn | `` |
| `adaptive_avg_pool2d` | fn | `(input: torch.Tensor, output_size: None) -> torch.Tensor` |
| `adaptive_avg_pool3d` | fn | `(input: torch.Tensor, output_size: None) -> torch.Tensor` |
| `adaptive_max_pool1d` | fn | `(*args, **kwargs)` |
| `adaptive_max_pool1d_with_indices` | fn | `(input: torch.Tensor, output_size: None, return_indices: bool = False) -> tuple[torch.Tensor, torch.Tensor]` |
| `adaptive_max_pool2d` | fn | `(*args, **kwargs)` |
| `adaptive_max_pool2d_with_indices` | fn | `(input: torch.Tensor, output_size: None, return_indices: bool = False) -> tuple[torch.Tensor, torch.Tensor]` |
| `adaptive_max_pool3d` | fn | `(*args, **kwargs)` |
| `adaptive_max_pool3d_with_indices` | fn | `(input: torch.Tensor, output_size: None, return_indices: bool = False) -> tuple[torch.Tensor, torch.Tensor]` |
| `affine_grid` | fn | `(theta: torch.Tensor, size: list[int], align_corners: bool \| None = None) -> torch.Tensor` |
| `alpha_dropout` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = False, inplace: bool = False) -> torch.Tensor` |
| `assert_int_or_pair` | fn | `(arg: list[int], arg_name: str, message: str) -> None` |
| `avg_pool1d` | fn | `` |
| `avg_pool2d` | fn | `` |
| `avg_pool3d` | fn | `` |
| `batch_norm` | fn | `(input: torch.Tensor, running_mean: torch.Tensor \| None, running_var: torch.Tensor \| None, weight: torch.Tensor \| Non…` |
| `bilinear` | fn | `` |
| `binary_cross_entropy` | fn | `(input: torch.Tensor, target: torch.Tensor, weight: torch.Tensor \| None = None, size_average: bool \| None = None, redu…` |
| `binary_cross_entropy_with_logits` | fn | `(input: torch.Tensor, target: torch.Tensor, weight: torch.Tensor \| None = None, size_average: bool \| None = None, redu…` |
| `boolean_dispatch` | fn | `(arg_name, arg_index, default, if_true, if_false, module_name, func_name)` |
| `celu` | fn | `(input: torch.Tensor, alpha: float = 1.0, inplace: bool = False) -> torch.Tensor` |
| `celu_` | fn | `` |
| `channel_shuffle` | fn | `` |
| `conv1d` | fn | `` |
| `conv2d` | fn | `` |
| `conv3d` | fn | `` |
| `conv_tbc` | fn | `` |
| `conv_transpose1d` | fn | `` |
| `conv_transpose2d` | fn | `` |
| `conv_transpose3d` | fn | `` |
| `cosine_embedding_loss` | fn | `(input1: torch.Tensor, input2: torch.Tensor, target: torch.Tensor, margin: float = 0, size_average: bool \| None = None,…` |
| `cosine_similarity` | fn | `` |
| `cross_entropy` | fn | `(input: torch.Tensor, target: torch.Tensor, weight: torch.Tensor \| None = None, size_average: bool \| None = None, igno…` |
| `ctc_loss` | fn | `(log_probs: torch.Tensor, targets: torch.Tensor, input_lengths: torch.Tensor, target_lengths: torch.Tensor, blank: int =…` |
| `dropout` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = True, inplace: bool = False) -> torch.Tensor` |
| `dropout1d` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = True, inplace: bool = False) -> torch.Tensor` |
| `dropout2d` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = True, inplace: bool = False) -> torch.Tensor` |
| `dropout3d` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = True, inplace: bool = False) -> torch.Tensor` |
| `elu` | fn | `(input: torch.Tensor, alpha: float = 1.0, inplace: bool = False) -> torch.Tensor` |
| `elu_` | fn | `` |
| `embedding` | fn | `(input: torch.Tensor, weight: torch.Tensor, padding_idx: int \| None = None, max_norm: float \| None = None, norm_type: …` |
| `embedding_bag` | fn | `(input: torch.Tensor, weight: torch.Tensor, offsets: torch.Tensor \| None = None, max_norm: float \| None = None, norm_t…` |
| `feature_alpha_dropout` | fn | `(input: torch.Tensor, p: float = 0.5, training: bool = False, inplace: bool = False) -> torch.Tensor` |
| `fold` | fn | `(input: torch.Tensor, output_size: None, kernel_size: None, dilation: None = 1, padding: None = 0, stride: None = 1) -> …` |
| `fractional_max_pool2d` | fn | `(*args, **kwargs)` |
| `fractional_max_pool2d_with_indices` | fn | `(input: torch.Tensor, kernel_size: None, output_size: NoneType = None, output_ratio: NoneType = None, return_indices: bo…` |
| `fractional_max_pool3d` | fn | `(*args, **kwargs)` |
| `fractional_max_pool3d_with_indices` | fn | `(input: torch.Tensor, kernel_size: None, output_size: NoneType = None, output_ratio: NoneType = None, return_indices: bo…` |
| `gaussian_nll_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, var: torch.Tensor \| float, full: bool = False, eps: float = 1e-06, reductio…` |
| `gelu` | fn | `` |
| `glu` | fn | `(input: torch.Tensor, dim: int = -1) -> torch.Tensor` |
| `grid_sample` | fn | `(input: torch.Tensor, grid: torch.Tensor, mode: str = 'bilinear', padding_mode: str = 'zeros', align_corners: bool \| No…` |
| `group_norm` | fn | `(input: torch.Tensor, num_groups: int, weight: torch.Tensor \| None = None, bias: torch.Tensor \| None = None, eps: floa…` |
| `grouped_mm` | fn | `(mat_a: torch.Tensor, mat_b: torch.Tensor, *, offs: torch.Tensor \| None = None, bias: torch.Tensor \| None = None, out_…` |
| `gumbel_softmax` | fn | `(logits: torch.Tensor, tau: float = 1, hard: bool = False, eps: float = 1e-10, dim: int = -1) -> torch.Tensor` |
| `handle_torch_function` | fn | `(public_api: collections.abc.Callable[~_P, ~_R], relevant_args: collections.abc.Iterable[typing.Any], *args: _P.args, **…` |
| `hardshrink` | fn | `` |
| `hardsigmoid` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `hardswish` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `hardtanh` | fn | `(input: torch.Tensor, min_val: float = -1.0, max_val: float = 1.0, inplace: bool = False) -> torch.Tensor` |
| `hardtanh_` | fn | `` |
| `has_torch_function` | fn | `` |
| `has_torch_function_unary` | fn | `` |
| `has_torch_function_variadic` | fn | `` |
| `hinge_embedding_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, margin: float = 1.0, size_average: bool \| None = None, reduce: bool \| None…` |
| `huber_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, reduction: str = 'mean', delta: float = 1.0, weight: torch.Tensor \| None = …` |
| `instance_norm` | fn | `(input: torch.Tensor, running_mean: torch.Tensor \| None = None, running_var: torch.Tensor \| None = None, weight: torch…` |
| `interpolate` | fn | `(input: torch.Tensor, size: int \| None = None, scale_factor: list[float] \| None = None, mode: str = 'nearest', align_c…` |
| `kl_div` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `l1_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `layer_norm` | fn | `(input: torch.Tensor, normalized_shape: list[int], weight: torch.Tensor \| None = None, bias: torch.Tensor \| None = Non…` |
| `leaky_relu` | fn | `(input: torch.Tensor, negative_slope: float = 0.01, inplace: bool = False) -> torch.Tensor` |
| `leaky_relu_` | fn | `` |
| `linear` | fn | `` |
| `local_response_norm` | fn | `(input: torch.Tensor, size: int, alpha: float = 0.0001, beta: float = 0.75, k: float = 1.0) -> torch.Tensor` |
| `log_softmax` | fn | `(input: torch.Tensor, dim: int \| None = None, _stacklevel: int = 3, dtype: int \| None = None) -> torch.Tensor` |
| `logsigmoid` | fn | `` |
| `lp_pool1d` | fn | `(input: torch.Tensor, norm_type: int \| float, kernel_size: int, stride: NoneType = None, ceil_mode: bool = False) -> to…` |
| `lp_pool2d` | fn | `(input: torch.Tensor, norm_type: int \| float, kernel_size: None, stride: NoneType = None, ceil_mode: bool = False) -> t…` |
| `lp_pool3d` | fn | `(input: torch.Tensor, norm_type: int \| float, kernel_size: None, stride: NoneType = None, ceil_mode: bool = False) -> t…` |
| `margin_ranking_loss` | fn | `(input1: torch.Tensor, input2: torch.Tensor, target: torch.Tensor, margin: float = 0, size_average: bool \| None = None,…` |
| `max_pool1d` | fn | `(*args, **kwargs)` |
| `max_pool1d_with_indices` | fn | `(input: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, dilation: None = 1, ceil_mode: bool…` |
| `max_pool2d` | fn | `(*args, **kwargs)` |
| `max_pool2d_with_indices` | fn | `(input: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, dilation: None = 1, ceil_mode: bool…` |
| `max_pool3d` | fn | `(*args, **kwargs)` |
| `max_pool3d_with_indices` | fn | `(input: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, dilation: None = 1, ceil_mode: bool…` |
| `max_unpool1d` | fn | `(input: torch.Tensor, indices: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, output_size:…` |
| `max_unpool2d` | fn | `(input: torch.Tensor, indices: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, output_size:…` |
| `max_unpool3d` | fn | `(input: torch.Tensor, indices: torch.Tensor, kernel_size: None, stride: NoneType = None, padding: None = 0, output_size:…` |
| `mish` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `mse_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `multi_head_attention_forward` | fn | `(query: torch.Tensor, key: torch.Tensor, value: torch.Tensor, embed_dim_to_check: int, num_heads: int, in_proj_weight: t…` |
| `multi_margin_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, p: int = 1, margin: float = 1.0, weight: torch.Tensor \| None = None, size_a…` |
| `multilabel_margin_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `multilabel_soft_margin_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, weight: torch.Tensor \| None = None, size_average: bool \| None = None, redu…` |
| `native_channel_shuffle` | fn | `` |
| `nll_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, weight: torch.Tensor \| None = None, size_average: bool \| None = None, igno…` |
| `normalize` | fn | `(input: torch.Tensor, p: float = 2.0, dim: int = 1, eps: float = 1e-12, out: torch.Tensor \| None = None) -> torch.Tenso…` |
| `one_hot` | fn | `` |
| `pad` | fn | `(input: torch.Tensor, pad: list[int], mode: str = 'constant', value: float \| None = None) -> torch.Tensor` |
| `pairwise_distance` | fn | `` |
| `pdist` | fn | `` |
| `pixel_shuffle` | fn | `` |
| `pixel_unshuffle` | fn | `` |
| `poisson_nll_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, log_input: bool = True, full: bool = False, size_average: bool \| None = Non…` |
| `prelu` | fn | `` |
| `relu` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `relu6` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `relu_` | fn | `` |
| `rms_norm` | fn | `(input: torch.Tensor, normalized_shape: list[int], weight: torch.Tensor \| None = None, eps: float \| None = None) -> to…` |
| `rrelu` | fn | `(input: torch.Tensor, lower: float = 0.125, upper: float = 0.3333333333333333, training: bool = False, inplace: bool = F…` |
| `rrelu_` | fn | `` |
| `scaled_dot_product_attention` | fn | `` |
| `scaled_grouped_mm` | fn | `(mat_a: torch.Tensor, mat_b: torch.Tensor, scale_a: torch.Tensor \| list[torch.Tensor], scale_recipe_a: torch.nn.functio…` |
| `scaled_mm` | fn | `(mat_a: torch.Tensor, mat_b: torch.Tensor, scale_a: torch.Tensor \| list[torch.Tensor], scale_recipe_a: torch.nn.functio…` |
| `selu` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `selu_` | fn | `` |
| `sigmoid` | fn | `(input)` |
| `silu` | fn | `(input: torch.Tensor, inplace: bool = False) -> torch.Tensor` |
| `smooth_l1_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `soft_margin_loss` | fn | `(input: torch.Tensor, target: torch.Tensor, size_average: bool \| None = None, reduce: bool \| None = None, reduction: s…` |
| `softmax` | fn | `(input: torch.Tensor, dim: int \| None = None, _stacklevel: int = 3, dtype: int \| None = None) -> torch.Tensor` |
| `softmin` | fn | `(input: torch.Tensor, dim: int \| None = None, _stacklevel: int = 3, dtype: int \| None = None) -> torch.Tensor` |
| `softplus` | fn | `` |
| `softshrink` | fn | `` |
| `softsign` | fn | `(input)` |
| `tanh` | fn | `(input)` |
| `tanhshrink` | fn | `(input)` |
| `threshold` | fn | `(input: torch.Tensor, threshold: float, value: float, inplace: bool = False) -> torch.Tensor` |
| `threshold_` | fn | `` |
| `triplet_margin_loss` | fn | `(anchor: torch.Tensor, positive: torch.Tensor, negative: torch.Tensor, margin: float = 1.0, p: float = 2, eps: float = 1…` |
| `triplet_margin_with_distance_loss` | fn | `(anchor: torch.Tensor, positive: torch.Tensor, negative: torch.Tensor, *, distance_function: collections.abc.Callable[[t…` |
| `unfold` | fn | `(input: torch.Tensor, kernel_size: None, dilation: None = 1, padding: None = 0, stride: None = 1) -> torch.Tensor` |
| `upsample` | fn | `(input, size=None, scale_factor=None, mode='nearest', align_corners=None)` |
| `upsample_bilinear` | fn | `(input, size=None, scale_factor=None)` |
| `upsample_nearest` | fn | `(input, size=None, scale_factor=None)` |

## `torch.optim` 优化器

优化器类。

| 名 | 形态 | 签名 |
|---|---|---|
| `ASGD` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Adadelta` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Adafactor` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Adagrad` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Adam` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `AdamW` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Adamax` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `LBFGS` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Muon` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `NAdam` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Optimizer` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `RAdam` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `RMSprop` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `Rprop` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `SGD` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |
| `SparseAdam` | cls | `(self, params: collections.abc.Iterable[torch.Tensor] \| collections.abc.Iterable[dict[str, typing.Any]] \| collections.…` |

## dtype

张量元素类型。

| 名 | 形态 | 签名 |
|---|---|---|
| `bfloat16` | dtype | `` |
| `bool` | dtype | `` |
| `complex128` | dtype | `` |
| `complex64` | dtype | `` |
| `double` | dtype | `` |
| `float` | dtype | `` |
| `half` | dtype | `` |
| `int16` | dtype | `` |
| `int32` | dtype | `` |
| `int64` | dtype | `` |
| `int8` | dtype | `` |
| `uint8` | dtype | `` |
