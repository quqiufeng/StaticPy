/* libTorch 最小 C ABI（对标 plugins/ltorch）。
 *
 * 约定（见 docs/FFI.md）：
 *   - 所有字符串参数是 UTF-8 C 字符串，返回字符串走**进程内静态缓冲**
 *     （调用方下一次调用会被覆盖，不要跨调用持有）。
 *   - 张量句柄是不透明指针（at::Tensor*），用完必须 torchc_free。
 *   - 出错一律返回 NULL / 0 并把消息写进静态 last_error，用 torchc_last_error 取。
 */
#ifndef TORCHC_API_H
#define TORCHC_API_H

#ifdef __cplusplus
extern "C" {
#endif

typedef void *torchc_tensor;

/* ---- 元信息 ---- */
const char *torchc_version(void);      /* libtorch 版本，如 "2.1.2" */
const char *torchc_last_error(void);   /* 最近一次失败的原因（成功时空串） */

/* ---- 构造 ---- */
torchc_tensor torchc_from_csv(const char *values_csv, const char *shape_csv);
torchc_tensor torchc_zeros(const char *shape_csv);
torchc_tensor torchc_ones(const char *shape_csv);
torchc_tensor torchc_full(const char *shape_csv, double value);
torchc_tensor torchc_randn(const char *shape_csv, long seed);
torchc_tensor torchc_arange(double start, double end, double step);

/* ---- 逐元素 / 矩阵 ---- */
torchc_tensor torchc_add(torchc_tensor a, torchc_tensor b);
torchc_tensor torchc_sub(torchc_tensor a, torchc_tensor b);
torchc_tensor torchc_mul(torchc_tensor a, torchc_tensor b);
torchc_tensor torchc_div(torchc_tensor a, torchc_tensor b);
torchc_tensor torchc_matmul(torchc_tensor a, torchc_tensor b);
torchc_tensor torchc_add_scalar(torchc_tensor a, double v);
torchc_tensor torchc_mul_scalar(torchc_tensor a, double v);
torchc_tensor torchc_sub_scalar(torchc_tensor a, double v);
torchc_tensor torchc_div_scalar(torchc_tensor a, double v);
torchc_tensor torchc_neg(torchc_tensor a);

/* ---- 激活 / 归约 ---- */
torchc_tensor torchc_relu(torchc_tensor a);
torchc_tensor torchc_sigmoid(torchc_tensor a);
torchc_tensor torchc_tanh(torchc_tensor a);
torchc_tensor torchc_softmax(torchc_tensor a, long dim);
torchc_tensor torchc_sum(torchc_tensor a);
torchc_tensor torchc_mean(torchc_tensor a);
torchc_tensor torchc_sum_dim(torchc_tensor a, long dim);

/* ---- 形状 ---- */
torchc_tensor torchc_reshape(torchc_tensor a, const char *shape_csv);
torchc_tensor torchc_transpose(torchc_tensor a, long d0, long d1);
torchc_tensor torchc_clone(torchc_tensor a);
torchc_tensor torchc_detach(torchc_tensor a);
long torchc_numel(torchc_tensor a);
long torchc_ndim(torchc_tensor a);
const char *torchc_shape_csv(torchc_tensor a);   /* "2,3" */

/* ---- 取值 ---- */
const char *torchc_to_csv(torchc_tensor a);      /* float64，逗号分隔（按行主序展平） */
double torchc_item(torchc_tensor a);             /* 单元素张量取标量，否则 0 + error */

/* ---- autograd ---- */
long torchc_set_requires_grad(torchc_tensor a, long flag);
long torchc_requires_grad(torchc_tensor a);
long torchc_backward(torchc_tensor a);            /* 标量反传；返回 1/0 */
torchc_tensor torchc_grad(torchc_tensor a);       /* 梯度张量（无梯度返回 NULL） */
torchc_tensor torchc_zero_grad(torchc_tensor a);
long torchc_sgd_step(torchc_tensor w, torchc_tensor g, double lr); /* 原地 w -= lr*g（NoGrad） */

/* ---- 一元数学（torch.exp/log/sqrt/abs/pow）---- */
torchc_tensor torchc_exp(torchc_tensor a);
torchc_tensor torchc_log(torchc_tensor a);
torchc_tensor torchc_sqrt(torchc_tensor a);
torchc_tensor torchc_abs(torchc_tensor a);
torchc_tensor torchc_pow_scalar(torchc_tensor a, double p);

/* ---- 归约（torch.max/min/argmax/std + dim 版）---- */
double torchc_max(torchc_tensor a);
double torchc_min(torchc_tensor a);
double torchc_std(torchc_tensor a, long unbiased);
long torchc_argmax(torchc_tensor a);           /* 展平后的最大下标 */
torchc_tensor torchc_max_dim(torchc_tensor a, long dim, long want_index);
torchc_tensor torchc_min_dim(torchc_tensor a, long dim, long want_index);
torchc_tensor torchc_mean_dim(torchc_tensor a, long dim);

/* ---- 形状（cat/stack/squeeze/unsqueeze）---- */
torchc_tensor torchc_cat(torchc_tensor a, torchc_tensor b, long dim);
torchc_tensor torchc_stack(torchc_tensor a, torchc_tensor b, long dim);
torchc_tensor torchc_squeeze(torchc_tensor a, long dim);
torchc_tensor torchc_unsqueeze(torchc_tensor a, long dim);
torchc_tensor torchc_zeros_like(torchc_tensor a);
torchc_tensor torchc_ones_like(torchc_tensor a);
torchc_tensor torchc_empty_like(torchc_tensor a);

/* ---- dtype（float64 默认；扩展 float32/int64/bool）---- */
torchc_tensor torchc_cast(torchc_tensor a, const char *dtype_name); /* "float64"/"float32"/"int64"/"bool" */
torchc_tensor torchc_zeros_dtype(const char *shape_csv, const char *dtype_name);
const char *torchc_dtype(torchc_tensor a);

/* ---- 索引 / 嵌入（gather 行）---- */
torchc_tensor torchc_index_select(torchc_tensor w, const char *idx_csv);

/* ---- nn 层内核 ---- */
torchc_tensor torchc_conv2d(torchc_tensor x, torchc_tensor w, torchc_tensor b,
                            long sh, long sw, long ph, long pw);
torchc_tensor torchc_max_pool2d(torchc_tensor x, long kh, long kw, long sh, long sw);
torchc_tensor torchc_avg_pool2d(torchc_tensor x, long kh, long kw, long sh, long sw);
/* 参数顺序对齐 PyTorch functional.batch_norm(x, running_mean, running_var,
   weight, bias, training, momentum, eps) 的推理分支 */
torchc_tensor torchc_batch_norm(torchc_tensor x, torchc_tensor mean, torchc_tensor var,
                                torchc_tensor gamma, torchc_tensor beta, double eps);
/* 训练分支：batch 统计归一化，并**原地更新** running_mean / running_var
   （torch 语义 running = (1-m)*running + m*batch_stat，无偏方差）*/
torchc_tensor torchc_batch_norm_train(torchc_tensor x, torchc_tensor mean, torchc_tensor var,
                                      torchc_tensor gamma, torchc_tensor beta,
                                      double eps, double momentum, long training);
torchc_tensor torchc_cross_entropy(torchc_tensor logits, const char *target_csv); /* 均值归约 */
torchc_tensor torchc_dropout(torchc_tensor x, double p, long training, long seed);
torchc_tensor torchc_l1_loss(torchc_tensor pred, torchc_tensor target);

/* ---- 优化器内核（原地更新，NoGrad）---- */
long torchc_sgd_step_momentum(torchc_tensor w, torchc_tensor g, torchc_tensor buf,
                              double lr, double momentum, double weight_decay, long nesterov);
long torchc_set_grad(torchc_tensor w, torchc_tensor g);
/* LSTM 单层单向：x(seq,batch,in) + flat_weights{w_ih,w_hh,b_ih,b_hh} + h0/c0(1,batch,hid)；
   want 0=out(seq,batch,hid) 1=h_n 2=c_n。 */
torchc_tensor torchc_lstm(torchc_tensor x, torchc_tensor wih, torchc_tensor whh,
                          torchc_tensor bih, torchc_tensor bhh, torchc_tensor h0,
                          torchc_tensor c0, long want);
long torchc_adagrad_step(torchc_tensor w, torchc_tensor g, torchc_tensor acc,
                         double lr, double lr_decay, double weight_decay, double eps, long step);
long torchc_adam_step(torchc_tensor w, torchc_tensor g, torchc_tensor m, torchc_tensor v,
                      double lr, double beta1, double beta2, double eps,
                      double weight_decay, long step, long decoupled);
long torchc_rmsprop_step(torchc_tensor w, torchc_tensor g, torchc_tensor sq,
                         double lr, double alpha, double eps, double weight_decay);

/* ---- 梯度模式（torch.no_grad）---- */
long torchc_set_grad_enabled(long flag);
long torchc_is_grad_enabled(void);

/* ---- 形状 / 拷贝 ---- */
torchc_tensor torchc_flatten(torchc_tensor a, long start_dim);
long torchc_copy_into(torchc_tensor dst, torchc_tensor src);

/* ---- 存取（state_dict 落盘）---- */
long torchc_save(torchc_tensor a, const char *path);
torchc_tensor torchc_load(const char *path);
torchc_tensor torchc_load_csv(const char *path);

/* ---- 生命周期 ---- */
long torchc_is_tensor(torchc_tensor a);  /* 1=是存活句柄，0=普通整数/空 */
void torchc_free(torchc_tensor a);
long torchc_free_int(torchc_tensor a);   /* 同 torchc_free，返回 1（FFI 契约：无 void 返回） */

/* ---- v10：Transformer / 分类链路 ---- */
torchc_tensor torchc_clamp(torchc_tensor a, double lo, double hi);
torchc_tensor torchc_log_softmax(torchc_tensor a, long dim);
torchc_tensor torchc_gelu(torchc_tensor a);
torchc_tensor torchc_gelu_approx(torchc_tensor a);
torchc_tensor torchc_leaky_relu(torchc_tensor a, double slope);
torchc_tensor torchc_masked_fill(torchc_tensor a, torchc_tensor mask, double value);
torchc_tensor torchc_cumsum(torchc_tensor a, long dim);
double torchc_norm_p(torchc_tensor a, double p);
torchc_tensor torchc_layer_norm(torchc_tensor x, torchc_tensor w, torchc_tensor b,
                                long nnorm, double eps);
torchc_tensor torchc_nll_loss(torchc_tensor logits, const char *target_csv);
torchc_tensor torchc_bce_with_logits(torchc_tensor pred, torchc_tensor target);

/* ---- v12：索引 / 形状面（张量取列、展批、点积）---- */
torchc_tensor torchc_select(torchc_tensor a, long dim, long idx);
torchc_tensor torchc_narrow(torchc_tensor a, long dim, long start, long len);
torchc_tensor torchc_repeat(torchc_tensor a, const char *reps_csv);
torchc_tensor torchc_expand(torchc_tensor a, const char *shape_csv);
torchc_tensor torchc_t(torchc_tensor a);
double torchc_dot(torchc_tensor a, torchc_tensor b);

#ifdef __cplusplus
}
#endif

#endif /* TORCHC_API_H */
