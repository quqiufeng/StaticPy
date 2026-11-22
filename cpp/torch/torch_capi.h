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

/* ---- 生命周期 ---- */
void torchc_free(torchc_tensor a);

#ifdef __cplusplus
}
#endif

#endif /* TORCHC_API_H */
