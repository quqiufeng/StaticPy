/* libTorch 最小 C ABI 实现（见 torch_capi.h 的约定）。
 *
 * 只做一件事：把 at::Tensor 的常用算子压平成 C 调用面，给 StaticPy 的
 * plugins/ltorch 用。张量本身仍是 libtorch 真张量（ATen 内核，CPU），
 * 所以数值与 PyTorch 一致，不需要重写任何算子。
 */
#include "torch_capi.h"

#include <torch/torch.h>

#include <cmath>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <vector>
#include <unordered_set>

namespace {

thread_local std::string g_error;
thread_local std::string g_scratch;

void set_error(const std::string &msg) { g_error = msg; }
void clear_error() { g_error.clear(); }

// "2,3" → {2,3}；空串 → 标量形状的 0 维
bool parse_shape(const char *csv, std::vector<int64_t> &out) {
  out.clear();
  if (csv == nullptr) return false;
  std::string s(csv);
  size_t i = 0;
  while (i < s.size()) {
    size_t j = s.find(',', i);
    if (j == std::string::npos) j = s.size();
    std::string tok = s.substr(i, j - i);
    // trim
    size_t a = tok.find_first_not_of(" \t");
    size_t b = tok.find_last_not_of(" \t");
    if (a == std::string::npos) {
      set_error("shape 里有空维度: " + s);
      return false;
    }
    tok = tok.substr(a, b - a + 1);
    char *end = nullptr;
    long v = std::strtol(tok.c_str(), &end, 10);
    if (end == nullptr || *end != '\0' || v < 0) {
      set_error("shape 维度不是非负整数: '" + tok + "'");
      return false;
    }
    out.push_back(static_cast<int64_t>(v));
    i = j + 1;
  }
  return true;
}

bool parse_values(const char *csv, std::vector<double> &out) {
  out.clear();
  if (csv == nullptr) {
    set_error("values_csv 是 NULL");
    return false;
  }
  std::string s(csv);
  size_t i = 0;
  while (i <= s.size()) {
    size_t j = s.find(',', i);
    if (j == std::string::npos) j = s.size();
    std::string tok = s.substr(i, j - i);
    size_t a = tok.find_first_not_of(" \t");
    size_t b = tok.find_last_not_of(" \t");
    if (a == std::string::npos) break;  // 尾随逗号 / 空串
    tok = tok.substr(a, b - a + 1);
    char *end = nullptr;
    double v = std::strtod(tok.c_str(), &end);
    if (end == nullptr || *end != '\0') {
      set_error("values 里有非数字: '" + tok + "'");
      return false;
    }
    out.push_back(v);
    i = j + 1;
  }
  return true;
}

// 存活句柄登记：Scheme 侧句柄是 integer-64，与用户整数无法区分，
// 所以用这张表回答「这个整数是张量句柄还是标量」（torchc_is_tensor）。
static std::unordered_set<void *> g_live;

torchc_tensor wrap(const at::Tensor &t) {
  auto *p = new at::Tensor(t);
  g_live.insert(p);
  return p;
}

at::Tensor *unwrap(torchc_tensor h) {
  return static_cast<at::Tensor *>(h);
}

// 统一入口：把 libtorch 抛的异常翻成 last_error，返回 NULL。
#define TORCHC_GUARD_BEGIN try {
#define TORCHC_GUARD_END(tag)                     \
  }                                               \
  catch (const std::exception &e) {               \
    set_error(std::string(tag) + ": " + e.what());  \
    return nullptr;                               \
  }                                               \
  catch (...) {                                   \
    set_error(std::string(tag) + ": unknown error"); \
    return nullptr;                               \
  }

// long 返回版（宏里 return nullptr 对 long 不合法）
#define TORCHC_GUARD_END_LONG(tag)                \
  }                                               \
  catch (const std::exception &e) {               \
    set_error(std::string(tag) + ": " + e.what());  \
    return 0;                                     \
  }                                               \
  catch (...) {                                   \
    set_error(std::string(tag) + ": unknown error"); \
    return 0;                                     \
  }

// double 返回版
#define TORCHC_GUARD_END_DOUBLE(tag)              \
  }                                               \
  catch (const std::exception &e) {               \
    set_error(std::string(tag) + ": " + e.what());  \
    return 0.0;                                   \
  }                                               \
  catch (...) {                                   \
    set_error(std::string(tag) + ": unknown error"); \
    return 0.0;                                   \
  }

// const char* 返回版
#define TORCHC_GUARD_END_CSTR(tag)                \
  }                                               \
  catch (const std::exception &e) {               \
    set_error(std::string(tag) + ": " + e.what());  \
    return "";                                    \
  }                                               \
  catch (...) {                                   \
    set_error(std::string(tag) + ": unknown error"); \
    return "";                                    \
  }

#define TORCHC_NEED(h, name)                     \
  if ((h) == nullptr) {                          \
    set_error(std::string(name) + ": 空张量句柄"); \
    return nullptr;                              \
  }

#define TORCHC_NEED_LONG(h, name)                \
  if ((h) == nullptr) {                          \
    set_error(std::string(name) + ": 空张量句柄"); \
    return 0;                                    \
  }

bool parse_dtype(const char *name, at::ScalarType &out) {
  std::string d = name == nullptr ? "" : std::string(name);
  if (d.rfind("torch.", 0) == 0) d = d.substr(6);  /* 接受 torch.float64 形态 */
  if (d == "float64" || d == "double" || d == "") out = at::kDouble;
  else if (d == "float32" || d == "float") out = at::kFloat;
  else if (d == "float16" || d == "half") out = at::kHalf;
  else if (d == "int64" || d == "long") out = at::kLong;
  else if (d == "int32" || d == "int") out = at::kInt;
  else if (d == "int8") out = at::kChar;
  else if (d == "uint8" || d == "byte") out = at::kByte;
  else if (d == "bool") out = at::kBool;
  else {
    set_error("未知 dtype: '" + d + "'（float64/float32/int64/int32/bool）");
    return false;
  }
  return true;
}

/* 对外 dtype 名与 PyTorch 对齐：str(torch.tensor(1., dtype=torch.float64).dtype)
   == "torch.float64"；parse_dtype 也能吃回去。 */
std::string dtype_name_of(at::ScalarType st) {
  if (st == at::kDouble) return "torch.float64";
  if (st == at::kFloat) return "torch.float32";
  if (st == at::kHalf) return "torch.float16";
  if (st == at::kLong) return "torch.int64";
  if (st == at::kInt) return "torch.int32";
  if (st == at::kChar) return "torch.int8";
  if (st == at::kByte) return "torch.uint8";
  if (st == at::kBool) return "torch.bool";
  return "other";
}

const char *scratch(const std::string &s) {
  g_scratch = s;
  return g_scratch.c_str();
}

}  // namespace

extern "C" {

const char *torchc_version(void) { return TORCH_VERSION; }

const char *torchc_last_error(void) { return g_error.c_str(); }

torchc_tensor torchc_from_csv(const char *values_csv, const char *shape_csv) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<double> vals;
    std::vector<int64_t> shape;
    if (!parse_values(values_csv, vals)) return nullptr;
    if (!parse_shape(shape_csv, shape) || shape.empty()) {
      if (g_error.empty()) set_error("from_csv 需要非空 shape");
      return nullptr;
    }
    int64_t want = 1;
    for (auto d : shape) want *= d;
    if (static_cast<int64_t>(vals.size()) != want) {
      std::ostringstream os;
      os << "from_csv: shape 要 " << want << " 个元素，实际 " << vals.size();
      set_error(os.str());
      return nullptr;
    }
    auto opt = at::TensorOptions().dtype(at::kDouble);
    auto t = torch::from_blob(vals.data(), shape, opt).clone();
    return wrap(t);
  TORCHC_GUARD_END("from_csv")
}

torchc_tensor torchc_zeros(const char *shape_csv) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    auto opt = at::TensorOptions().dtype(at::kDouble);
    return wrap(torch::zeros(shape, opt));
  TORCHC_GUARD_END("zeros")
}

torchc_tensor torchc_ones(const char *shape_csv) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    auto opt = at::TensorOptions().dtype(at::kDouble);
    return wrap(torch::ones(shape, opt));
  TORCHC_GUARD_END("ones")
}

torchc_tensor torchc_full(const char *shape_csv, double value) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    auto opt = at::TensorOptions().dtype(at::kDouble);
    return wrap(torch::full(shape, value, opt));
  TORCHC_GUARD_END("full")
}

torchc_tensor torchc_randn(const char *shape_csv, long seed) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    auto opt = at::TensorOptions().dtype(at::kDouble);
    if (seed >= 0) torch::manual_seed(static_cast<int64_t>(seed));
    return wrap(torch::randn(shape, opt));
  TORCHC_GUARD_END("randn")
}

torchc_tensor torchc_arange(double start, double end, double step) {
  clear_error();
  TORCHC_GUARD_BEGIN
    auto opt = at::TensorOptions().dtype(at::kDouble);
    return wrap(torch::arange(start, end, step, opt));
  TORCHC_GUARD_END("arange")
}

torchc_tensor torchc_add(torchc_tensor a, torchc_tensor b) {
  clear_error();
  TORCHC_NEED(a, "add")
  TORCHC_NEED(b, "add")
  TORCHC_GUARD_BEGIN
    return wrap(at::add(*unwrap(a), *unwrap(b)));
  TORCHC_GUARD_END("add")
}

torchc_tensor torchc_sub(torchc_tensor a, torchc_tensor b) {
  clear_error();
  TORCHC_NEED(a, "sub")
  TORCHC_NEED(b, "sub")
  TORCHC_GUARD_BEGIN
    return wrap(at::sub(*unwrap(a), *unwrap(b)));
  TORCHC_GUARD_END("sub")
}

torchc_tensor torchc_mul(torchc_tensor a, torchc_tensor b) {
  clear_error();
  TORCHC_NEED(a, "mul")
  TORCHC_NEED(b, "mul")
  TORCHC_GUARD_BEGIN
    return wrap(at::mul(*unwrap(a), *unwrap(b)));
  TORCHC_GUARD_END("mul")
}

torchc_tensor torchc_div(torchc_tensor a, torchc_tensor b) {
  clear_error();
  TORCHC_NEED(a, "div")
  TORCHC_NEED(b, "div")
  TORCHC_GUARD_BEGIN
    return wrap(at::div(*unwrap(a), *unwrap(b)));
  TORCHC_GUARD_END("div")
}

torchc_tensor torchc_matmul(torchc_tensor a, torchc_tensor b) {
  clear_error();
  TORCHC_NEED(a, "matmul")
  TORCHC_NEED(b, "matmul")
  TORCHC_GUARD_BEGIN
    return wrap(at::matmul(*unwrap(a), *unwrap(b)));
  TORCHC_GUARD_END("matmul")
}

torchc_tensor torchc_add_scalar(torchc_tensor a, double v) {
  clear_error();
  TORCHC_NEED(a, "add_scalar")
  TORCHC_GUARD_BEGIN
    return wrap(at::add(*unwrap(a), v));
  TORCHC_GUARD_END("add_scalar")
}

torchc_tensor torchc_mul_scalar(torchc_tensor a, double v) {
  clear_error();
  TORCHC_NEED(a, "mul_scalar")
  TORCHC_GUARD_BEGIN
    return wrap(at::mul(*unwrap(a), v));
  TORCHC_GUARD_END("mul_scalar")
}

torchc_tensor torchc_sub_scalar(torchc_tensor a, double v) {
  clear_error();
  TORCHC_NEED(a, "sub_scalar")
  TORCHC_GUARD_BEGIN
    return wrap(at::sub(*unwrap(a), v));
  TORCHC_GUARD_END("sub_scalar")
}

torchc_tensor torchc_div_scalar(torchc_tensor a, double v) {
  clear_error();
  TORCHC_NEED(a, "div_scalar")
  TORCHC_GUARD_BEGIN
    return wrap(at::div(*unwrap(a), v));
  TORCHC_GUARD_END("div_scalar")
}

torchc_tensor torchc_neg(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "neg")
  TORCHC_GUARD_BEGIN
    return wrap(at::neg(*unwrap(a)));
  TORCHC_GUARD_END("neg")
}

torchc_tensor torchc_relu(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "relu")
  TORCHC_GUARD_BEGIN
    return wrap(at::relu(*unwrap(a)));
  TORCHC_GUARD_END("relu")
}

torchc_tensor torchc_sigmoid(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "sigmoid")
  TORCHC_GUARD_BEGIN
    return wrap(at::sigmoid(*unwrap(a)));
  TORCHC_GUARD_END("sigmoid")
}

torchc_tensor torchc_tanh(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "tanh")
  TORCHC_GUARD_BEGIN
    return wrap(at::tanh(*unwrap(a)));
  TORCHC_GUARD_END("tanh")
}

torchc_tensor torchc_softmax(torchc_tensor a, long dim) {
  clear_error();
  TORCHC_NEED(a, "softmax")
  TORCHC_GUARD_BEGIN
    return wrap(at::softmax(*unwrap(a), static_cast<int64_t>(dim)));
  TORCHC_GUARD_END("softmax")
}

torchc_tensor torchc_sum(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "sum")
  TORCHC_GUARD_BEGIN
    return wrap(at::sum(*unwrap(a)));
  TORCHC_GUARD_END("sum")
}

torchc_tensor torchc_mean(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "mean")
  TORCHC_GUARD_BEGIN
    return wrap(at::mean(*unwrap(a)));
  TORCHC_GUARD_END("mean")
}

torchc_tensor torchc_sum_dim(torchc_tensor a, long dim) {
  clear_error();
  TORCHC_NEED(a, "sum_dim")
  TORCHC_GUARD_BEGIN
    return wrap(at::sum(*unwrap(a), static_cast<int64_t>(dim)));
  TORCHC_GUARD_END("sum_dim")
}

torchc_tensor torchc_reshape(torchc_tensor a, const char *shape_csv) {
  clear_error();
  TORCHC_NEED(a, "reshape")
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    return wrap(unwrap(a)->reshape(shape));
  TORCHC_GUARD_END("reshape")
}

torchc_tensor torchc_transpose(torchc_tensor a, long d0, long d1) {
  clear_error();
  TORCHC_NEED(a, "transpose")
  TORCHC_GUARD_BEGIN
    return wrap(at::transpose(*unwrap(a), static_cast<int64_t>(d0),
                              static_cast<int64_t>(d1)));
  TORCHC_GUARD_END("transpose")
}

torchc_tensor torchc_clone(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "clone")
  TORCHC_GUARD_BEGIN
    return wrap(unwrap(a)->clone());
  TORCHC_GUARD_END("clone")
}

torchc_tensor torchc_detach(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "detach")
  TORCHC_GUARD_BEGIN
    return wrap(unwrap(a)->detach());
  TORCHC_GUARD_END("detach")
}

long torchc_numel(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("numel: 空张量句柄");
    return 0;
  }
  return static_cast<long>(unwrap(a)->numel());
}

long torchc_ndim(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("ndim: 空张量句柄");
    return 0;
  }
  return static_cast<long>(unwrap(a)->dim());
}

const char *torchc_shape_csv(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("shape: 空张量句柄");
    return "";
  }
  std::ostringstream os;
  auto *t = unwrap(a);
  for (int64_t i = 0; i < t->dim(); i++) {
    if (i > 0) os << ',';
    os << t->size(i);
  }
  return scratch(os.str());
}

const char *torchc_to_csv(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("to_csv: 空张量句柄");
    return "";
  }
  TORCHC_GUARD_BEGIN
    auto t = unwrap(a)->to(at::kDouble).contiguous().flatten();
    auto n = static_cast<int64_t>(t.numel());
    const double *p = t.data_ptr<double>();
    std::ostringstream os;
    os.precision(17);
    for (int64_t i = 0; i < n; i++) {
      if (i > 0) os << ',';
      os << p[i];
    }
    return scratch(os.str());
  TORCHC_GUARD_END("to_csv")
}

double torchc_item(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("item: 空张量句柄");
    return 0.0;
  }
  TORCHC_GUARD_BEGIN
    return unwrap(a)->item<double>();
  } catch (const std::exception &e) {
    set_error(std::string("item: ") + e.what());
    return 0.0;
  } catch (...) {
    set_error("item: unknown error");
    return 0.0;
  }
}

long torchc_set_requires_grad(torchc_tensor a, long flag) {
  clear_error();
  if (a == nullptr) {
    set_error("set_requires_grad: 空张量句柄");
    return 0;
  }
  unwrap(a)->set_requires_grad(flag != 0);
  return 1;
}

long torchc_requires_grad(torchc_tensor a) {
  if (a == nullptr) return 0;
  return unwrap(a)->requires_grad() ? 1 : 0;
}

long torchc_backward(torchc_tensor a) {
  clear_error();
  if (a == nullptr) {
    set_error("backward: 空张量句柄");
    return 0;
  }
  TORCHC_GUARD_BEGIN
    unwrap(a)->backward();
    return 1;
  } catch (const std::exception &e) {
    set_error(std::string("backward: ") + e.what());
    return 0;
  } catch (...) {
    set_error("backward: unknown error");
    return 0;
  }
}

torchc_tensor torchc_grad(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "grad")
  TORCHC_GUARD_BEGIN
    auto g = unwrap(a)->grad();
    if (!g.defined()) {
      set_error("grad: 该张量还没有梯度（先 backward）");
      return nullptr;
    }
    return wrap(g);
  TORCHC_GUARD_END("grad")
}

torchc_tensor torchc_zero_grad(torchc_tensor a) {
  clear_error();
  TORCHC_NEED(a, "zero_grad")
  TORCHC_GUARD_BEGIN
    if (unwrap(a)->grad().defined()) unwrap(a)->grad().zero_();
    return wrap(*unwrap(a));
  TORCHC_GUARD_END("zero_grad")
}

long torchc_sgd_step(torchc_tensor w, torchc_tensor g, double lr) {
  clear_error();
  if (w == nullptr) {
    set_error("sgd_step: 空权重句柄");
    return 0;
  }
  if (g == nullptr) {
    set_error("sgd_step: 空梯度句柄");
    return 0;
  }
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    unwrap(w)->sub_(unwrap(g)->mul(lr));
    return 1;
  TORCHC_GUARD_END_LONG("sgd_step")
}

/* ================= v2：一元数学 / 归约 / 形状 / dtype ================= */

torchc_tensor torchc_exp(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "exp")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->exp()); TORCHC_GUARD_END("exp")
}
torchc_tensor torchc_log(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "log")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->log()); TORCHC_GUARD_END("log")
}
torchc_tensor torchc_sqrt(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "sqrt")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->sqrt()); TORCHC_GUARD_END("sqrt")
}
torchc_tensor torchc_abs(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "abs")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->abs()); TORCHC_GUARD_END("abs")
}
torchc_tensor torchc_pow_scalar(torchc_tensor a, double p) {
  clear_error(); TORCHC_NEED(a, "pow_scalar")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->pow(p)); TORCHC_GUARD_END("pow_scalar")
}

double torchc_max(torchc_tensor a) {
  clear_error(); if (a == nullptr) { set_error("max: 空句柄"); return 0.0; }
  TORCHC_GUARD_BEGIN return unwrap(a)->max().item<double>();
  TORCHC_GUARD_END_DOUBLE("max")
}

double torchc_min(torchc_tensor a) {
  clear_error(); if (a == nullptr) { set_error("min: 空句柄"); return 0.0; }
  TORCHC_GUARD_BEGIN return unwrap(a)->min().item<double>();
  TORCHC_GUARD_END_DOUBLE("min")
}

double torchc_std(torchc_tensor a, long unbiased) {
  clear_error(); if (a == nullptr) { set_error("std: 空句柄"); return 0.0; }
  TORCHC_GUARD_BEGIN
    auto f = unwrap(a)->to(at::kDouble).contiguous().view({-1});
    int64_t n = f.numel();
    if (n <= 1) return 0.0;
    double mu = f.mean().item<double>();
    auto d = f.sub(mu);
    double ss = d.mul(d).sum().item<double>();
    double den = unbiased != 0 ? static_cast<double>(n - 1) : static_cast<double>(n);
    return std::sqrt(ss / den);
  TORCHC_GUARD_END_DOUBLE("std")
}

long torchc_argmax(torchc_tensor a) {
  clear_error(); if (a == nullptr) { set_error("argmax: 空句柄"); return -1; }
  TORCHC_GUARD_BEGIN
    return static_cast<long>(unwrap(a)->contiguous().view({-1}).argmax().item<int64_t>());
  TORCHC_GUARD_END_LONG("argmax")
}

torchc_tensor torchc_max_dim(torchc_tensor a, long dim, long want_index) {
  clear_error(); TORCHC_NEED(a, "max_dim")
  TORCHC_GUARD_BEGIN
    auto r = at::max(*unwrap(a), dim);
    if (want_index != 0) return wrap(std::get<1>(r).to(at::kLong));
    return wrap(std::get<0>(r));
  TORCHC_GUARD_END("max_dim")
}

torchc_tensor torchc_min_dim(torchc_tensor a, long dim, long want_index) {
  clear_error(); TORCHC_NEED(a, "min_dim")
  TORCHC_GUARD_BEGIN
    auto r = at::min(*unwrap(a), dim);
    if (want_index != 0) return wrap(std::get<1>(r).to(at::kLong));
    return wrap(std::get<0>(r));
  TORCHC_GUARD_END("min_dim")
}

torchc_tensor torchc_mean_dim(torchc_tensor a, long dim) {
  clear_error(); TORCHC_NEED(a, "mean_dim")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->mean(dim)); TORCHC_GUARD_END("mean_dim")
}

torchc_tensor torchc_cat(torchc_tensor a, torchc_tensor b, long dim) {
  clear_error(); TORCHC_NEED(a, "cat"); TORCHC_NEED(b, "cat")
  TORCHC_GUARD_BEGIN return wrap(at::cat({*unwrap(a), *unwrap(b)}, dim));
  TORCHC_GUARD_END("cat")
}

torchc_tensor torchc_stack(torchc_tensor a, torchc_tensor b, long dim) {
  clear_error(); TORCHC_NEED(a, "stack"); TORCHC_NEED(b, "stack")
  TORCHC_GUARD_BEGIN return wrap(at::stack({*unwrap(a), *unwrap(b)}, dim));
  TORCHC_GUARD_END("stack")
}

torchc_tensor torchc_squeeze(torchc_tensor a, long dim) {
  clear_error(); TORCHC_NEED(a, "squeeze")
  TORCHC_GUARD_BEGIN
    if (dim < 0) return wrap(unwrap(a)->squeeze());
    return wrap(unwrap(a)->squeeze(dim));
  TORCHC_GUARD_END("squeeze")
}

torchc_tensor torchc_unsqueeze(torchc_tensor a, long dim) {
  clear_error(); TORCHC_NEED(a, "unsqueeze")
  TORCHC_GUARD_BEGIN return wrap(unwrap(a)->unsqueeze(dim)); TORCHC_GUARD_END("unsqueeze")
}

torchc_tensor torchc_zeros_like(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "zeros_like")
  TORCHC_GUARD_BEGIN return wrap(at::zeros_like(*unwrap(a))); TORCHC_GUARD_END("zeros_like")
}
torchc_tensor torchc_ones_like(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "ones_like")
  TORCHC_GUARD_BEGIN return wrap(at::ones_like(*unwrap(a))); TORCHC_GUARD_END("ones_like")
}
torchc_tensor torchc_empty_like(torchc_tensor a) {
  clear_error(); TORCHC_NEED(a, "empty_like")
  TORCHC_GUARD_BEGIN return wrap(at::empty_like(*unwrap(a))); TORCHC_GUARD_END("empty_like")
}

torchc_tensor torchc_cast(torchc_tensor a, const char *dtype_name) {
  clear_error(); TORCHC_NEED(a, "cast")
  TORCHC_GUARD_BEGIN
    at::ScalarType st;
    if (!parse_dtype(dtype_name, st)) return nullptr;
    return wrap(unwrap(a)->to(st));
  TORCHC_GUARD_END("cast")
}

torchc_tensor torchc_zeros_dtype(const char *shape_csv, const char *dtype_name) {
  clear_error();
  TORCHC_GUARD_BEGIN
    std::vector<int64_t> shape;
    if (!parse_shape(shape_csv, shape)) return nullptr;
    at::ScalarType st;
    if (!parse_dtype(dtype_name, st)) return nullptr;
    return wrap(torch::zeros(shape, at::TensorOptions().dtype(st)));
  TORCHC_GUARD_END("zeros_dtype")
}

const char *torchc_dtype(torchc_tensor a) {
  clear_error(); if (a == nullptr) { set_error("dtype: 空句柄"); return ""; }
  TORCHC_GUARD_BEGIN return scratch(dtype_name_of(unwrap(a)->scalar_type()));
  TORCHC_GUARD_END_CSTR("dtype")
}

torchc_tensor torchc_index_select(torchc_tensor w, const char *idx_csv) {
  clear_error(); TORCHC_NEED(w, "index_select")
  TORCHC_GUARD_BEGIN
    std::vector<double> vals;
    if (!parse_values(idx_csv, vals)) return nullptr;
    std::vector<int64_t> idx;
    idx.reserve(vals.size());
    for (double v : vals) idx.push_back(static_cast<int64_t>(v));
    auto it = at::from_blob(idx.data(), {static_cast<int64_t>(idx.size())},
                            at::TensorOptions().dtype(at::kLong)).clone();
    return wrap(unwrap(w)->index_select(0, it));
  TORCHC_GUARD_END("index_select")
}

/* ================= v2：nn 层内核 ================= */

torchc_tensor torchc_conv2d(torchc_tensor x, torchc_tensor w, torchc_tensor b,
                            long sh, long sw, long ph, long pw) {
  clear_error(); TORCHC_NEED(x, "conv2d"); TORCHC_NEED(w, "conv2d")
  TORCHC_GUARD_BEGIN
    auto opt = at::Tensor();
    if (b != nullptr) opt = *unwrap(b);
    return wrap(at::conv2d(*unwrap(x), *unwrap(w), opt,
                           {sh, sw}, {ph, pw}, {1, 1}, 1));
  TORCHC_GUARD_END("conv2d")
}

torchc_tensor torchc_max_pool2d(torchc_tensor x, long kh, long kw, long sh, long sw) {
  clear_error(); TORCHC_NEED(x, "max_pool2d")
  TORCHC_GUARD_BEGIN
    return wrap(at::max_pool2d(*unwrap(x), {kh, kw}, {sh, sw}, {0, 0}, {1, 1}, false));
  TORCHC_GUARD_END("max_pool2d")
}

torchc_tensor torchc_avg_pool2d(torchc_tensor x, long kh, long kw, long sh, long sw) {
  clear_error(); TORCHC_NEED(x, "avg_pool2d")
  TORCHC_GUARD_BEGIN
    return wrap(at::avg_pool2d(*unwrap(x), {kh, kw}, {sh, sw}, {0, 0}, false, true));
  TORCHC_GUARD_END("avg_pool2d")
}

torchc_tensor torchc_batch_norm(torchc_tensor x, torchc_tensor mean, torchc_tensor var,
                                torchc_tensor gamma, torchc_tensor beta, double eps) {
  clear_error(); TORCHC_NEED(x, "batch_norm")
  TORCHC_GUARD_BEGIN
    auto t = *unwrap(x);
    int64_t c = t.size(1);
    auto x3 = t.contiguous().view({t.size(0), c, -1});
    auto m = at::zeros({c}, t.options());
    auto v = at::ones({c}, t.options());
    auto g = at::ones({c}, t.options());
    auto bb = at::zeros({c}, t.options());
    if (mean != nullptr) m = unwrap(mean)->to(t.options());
    if (var != nullptr) v = unwrap(var)->to(t.options());
    if (gamma != nullptr) g = unwrap(gamma)->to(t.options());
    if (beta != nullptr) bb = unwrap(beta)->to(t.options());
    m = m.view({1, c, 1}); v = v.view({1, c, 1});
    g = g.view({1, c, 1}); bb = bb.view({1, c, 1});
    auto y = x3.sub(m).div(v.add(eps).sqrt()).mul(g).add(bb);
    return wrap(y.view(t.sizes()));
  TORCHC_GUARD_END("batch_norm")
}

torchc_tensor torchc_cross_entropy(torchc_tensor logits, const char *target_csv) {
  clear_error(); TORCHC_NEED(logits, "cross_entropy")
  TORCHC_GUARD_BEGIN
    std::vector<double> vals;
    if (!parse_values(target_csv, vals)) return nullptr;
    std::vector<int64_t> idx;
    idx.reserve(vals.size());
    for (double v : vals) idx.push_back(static_cast<int64_t>(v));
    auto t = *unwrap(logits);
    auto tgt = at::from_blob(idx.data(), {static_cast<int64_t>(idx.size())},
                             at::TensorOptions().dtype(at::kLong)).clone();
    auto l = t.to(at::kDouble);
    auto lse = at::logsumexp(l, 1);
    auto picked = l.gather(1, tgt.unsqueeze(1)).squeeze(1);
    return wrap(lse.sub(picked).mean());
  TORCHC_GUARD_END("cross_entropy")
}

torchc_tensor torchc_dropout(torchc_tensor x, double p, long training, long seed) {
  clear_error(); TORCHC_NEED(x, "dropout")
  TORCHC_GUARD_BEGIN
    if (seed > 0) at::manual_seed(seed);
    return wrap(at::dropout(*unwrap(x), p, training != 0));
  TORCHC_GUARD_END("dropout")
}

torchc_tensor torchc_l1_loss(torchc_tensor pred, torchc_tensor target) {
  clear_error(); TORCHC_NEED(pred, "l1_loss"); TORCHC_NEED(target, "l1_loss")
  TORCHC_GUARD_BEGIN
    return wrap(at::l1_loss(*unwrap(pred), *unwrap(target), at::Reduction::Mean));
  TORCHC_GUARD_END("l1_loss")
}

/* ================= v2：优化器内核 ================= */

long torchc_sgd_step_momentum(torchc_tensor w, torchc_tensor g, torchc_tensor buf,
                              double lr, double momentum, double weight_decay,
                              long nesterov) {
  clear_error();
  if (w == nullptr || g == nullptr) { set_error("sgd_step_momentum: 空句柄"); return 0; }
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    auto &W = *unwrap(w);
    auto grad = *unwrap(g);
    if (weight_decay != 0.0) grad = grad.add(W, weight_decay);
    if (momentum != 0.0) {
      if (buf == nullptr) { set_error("sgd_step_momentum: momentum 需要缓冲"); return 0; }
      auto &B = *unwrap(buf);
      B.mul_(momentum).add_(grad);
      if (nesterov != 0) grad = grad.add(B, momentum);
      else grad = B;
    }
    W.sub_(grad.mul(lr));
    return 1;
  TORCHC_GUARD_END_LONG("sgd_step_momentum")
}

long torchc_set_grad(torchc_tensor w, torchc_tensor g) {
  clear_error();
  if (w == nullptr) { set_error("set_grad: 空句柄"); return 0; }
  TORCHC_GUARD_BEGIN
    auto &W = *unwrap(w);
    if (g == nullptr) { W.mutable_grad() = at::Tensor(); return 1; }
    W.mutable_grad() = unwrap(g)->detach().clone();
    return 1;
  TORCHC_GUARD_END_LONG("set_grad")
}

long torchc_adagrad_step(torchc_tensor w, torchc_tensor g, torchc_tensor acc,
                         double lr, double lr_decay, double weight_decay, double eps, long step) {
  clear_error();
  if (w == nullptr || g == nullptr || acc == nullptr) {
    set_error("adagrad_step: 空句柄");
    return 0;
  }
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    auto &W = *unwrap(w);
    auto &S = *unwrap(acc);
    auto grad = *unwrap(g);
    if (weight_decay != 0.0) grad = grad.add(W, weight_decay);
    /* 照抄 torch/optim/adagrad.py：sum += g*g；clr = lr/(sqrt(sum)+eps)；p -= clr*g
       lr_decay 走 torch 的 clr = lr/(1+(step-1)*lr_decay) */
    S.addcmul_(grad, grad, 1);
    double clr = lr;
    if (lr_decay != 0.0) clr = lr / (1.0 + (static_cast<double>(step) - 1.0) * lr_decay);
    at::Tensor denom = S.sqrt() + eps;
    at::Tensor upd = grad / denom;
    W.sub_(upd * clr);
    return 1;
  TORCHC_GUARD_END_LONG("adagrad_step")
}

long torchc_adam_step(torchc_tensor w, torchc_tensor g, torchc_tensor m, torchc_tensor v,
                      double lr, double beta1, double beta2, double eps,
                      double weight_decay, long step, long decoupled) {
  clear_error();
  if (w == nullptr || g == nullptr || m == nullptr || v == nullptr) {
    set_error("adam_step: 空句柄");
    return 0;
  }
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    auto &W = *unwrap(w);
    auto &G0 = *unwrap(g);
    auto &M = *unwrap(m);
    auto &V = *unwrap(v);
    auto grad = G0;
    if (weight_decay != 0.0) {
      if (decoupled != 0) W.mul_(1.0 - lr * weight_decay);
      else grad = grad.add(W, weight_decay);
    }
    long s = step;
    double bc1 = 1.0 - std::pow(beta1, static_cast<double>(s));
    double bc2 = 1.0 - std::pow(beta2, static_cast<double>(s));
    M.lerp_(grad, 1.0 - beta1);
    V.mul_(beta2).addcmul_(grad, grad, 1.0 - beta2);
    double step_size = lr / bc1;
    auto denom = V.sqrt().div(std::sqrt(bc2)).add_(eps);
    W.addcdiv_(M, denom, -step_size);
    return 1;
  TORCHC_GUARD_END_LONG("adam_step")
}

long torchc_rmsprop_step(torchc_tensor w, torchc_tensor g, torchc_tensor sq,
                         double lr, double alpha, double eps, double weight_decay) {
  clear_error();
  if (w == nullptr || g == nullptr || sq == nullptr) {
    set_error("rmsprop_step: 空句柄");
    return 0;
  }
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    auto &W = *unwrap(w);
    auto &S = *unwrap(sq);
    auto grad = *unwrap(g);
    if (weight_decay != 0.0) grad = grad.add(W, weight_decay);
    S.mul_(alpha).addcmul_(grad, grad, 1.0 - alpha);
    auto avg = S.sqrt().add_(eps);
    W.addcdiv_(grad, avg, -lr);
    return 1;
  TORCHC_GUARD_END_LONG("rmsprop_step")
}

/* ================= v2：梯度模式 / 存取 ================= */

long torchc_set_grad_enabled(long flag) {
  clear_error();
  TORCHC_GUARD_BEGIN
    at::GradMode::set_enabled(flag != 0);
    // 无 void 返回：返回**设置后**的模式（0/1），与 is_grad_enabled 同口径
    return at::GradMode::is_enabled() ? 1 : 0;
  TORCHC_GUARD_END_LONG("set_grad_enabled")
}

long torchc_is_grad_enabled(void) {
  return at::GradMode::is_enabled() ? 1 : 0;
}

long torchc_save(torchc_tensor a, const char *path) {
  clear_error();
  if (a == nullptr || path == nullptr) { set_error("save: 空参数"); return 0; }
  TORCHC_GUARD_BEGIN
    torch::save(*unwrap(a), std::string(path));
    return 1;
  TORCHC_GUARD_END_LONG("save")
}

torchc_tensor torchc_load(const char *path) {
  clear_error();
  if (path == nullptr) { set_error("load: 空路径"); return nullptr; }
  TORCHC_GUARD_BEGIN
    auto t = at::zeros({1}, at::TensorOptions().dtype(at::kDouble));
    torch::load(t, std::string(path));
    return wrap(t);
  TORCHC_GUARD_END("load")
}

torchc_tensor torchc_flatten(torchc_tensor a, long start_dim) {
  clear_error(); TORCHC_NEED(a, "flatten")
  TORCHC_GUARD_BEGIN
    return wrap(unwrap(a)->flatten(start_dim, -1));
  TORCHC_GUARD_END("flatten")
}

long torchc_copy_into(torchc_tensor dst, torchc_tensor src) {
  clear_error(); TORCHC_NEED_LONG(dst, "copy_into"); TORCHC_NEED_LONG(src, "copy_into")
  TORCHC_GUARD_BEGIN
    torch::NoGradGuard ng;
    unwrap(dst)->copy_(*unwrap(src));
    return 1;
  TORCHC_GUARD_END_LONG("copy_into")
}

long torchc_is_tensor(torchc_tensor a) {
  if (a == nullptr) return 0;
  return g_live.count(a) ? 1 : 0;
}

// 释放句柄。幂等：不在存活表里说明已经 delete 过（或根本不是我们的句柄），
// 直接忽略——用户代码重复释放不该把进程带走。
void torchc_free(torchc_tensor a) {
  if (a == nullptr) return;
  if (g_live.erase(a) == 0) return;
  delete unwrap(a);
}

long torchc_free_int(torchc_tensor a) {
  if (a == nullptr) return 0;
  if (g_live.erase(a) == 0) return 0;
  delete unwrap(a);
  return 1;
}

}  // extern "C"
