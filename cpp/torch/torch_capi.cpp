/* libTorch 最小 C ABI 实现（见 torch_capi.h 的约定）。
 *
 * 只做一件事：把 at::Tensor 的常用算子压平成 C 调用面，给 StaticPy 的
 * plugins/ltorch 用。张量本身仍是 libtorch 真张量（ATen 内核，CPU），
 * 所以数值与 PyTorch 一致，不需要重写任何算子。
 */
#include "torch_capi.h"

#include <torch/torch.h>

#include <cstdlib>
#include <cstring>
#include <mutex>
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

#define TORCHC_NEED(h, name)                     \
  if ((h) == nullptr) {                          \
    set_error(std::string(name) + ": 空张量句柄"); \
    return nullptr;                              \
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

long torchc_is_tensor(torchc_tensor a) {
  if (a == nullptr) return 0;
  return g_live.count(a) ? 1 : 0;
}

void torchc_free(torchc_tensor a) {
  if (a == nullptr) return;
  g_live.erase(a);
  delete unwrap(a);
}

long torchc_free_int(torchc_tensor a) {
  if (a == nullptr) return 0;
  g_live.erase(a);
  delete unwrap(a);
  return 1;
}

}  // extern "C"
