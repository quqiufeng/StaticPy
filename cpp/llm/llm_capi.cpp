// llm_capi.cpp — Hunyuan-MT (llama.cpp 服务) 的 C ABI 封装
//
// 自写最小 HTTP/1.1 POST 客户端（POSIX socket），无 libcurl 依赖；
// JSON 用 nlohmann/json 构造与解析。
//
// 翻译策略（借鉴 BaoCut 字幕管线）：
//   1) 整句翻译：把连续字幕条按「句末标点 / 停顿 / 说话人切换」聚合成完整句子，
//      整句送模型，避免逐条碎片翻译导致的断句错误与上下文缺失。
//   2) 确定性回切：按各条原文字数比例，把整句译文用「目标语切分器」切回同样的
//      条数，时间轴不变；只在合法缝（不在词内、不悬标点）切。
//   3) 顺句驱动：可选（SUB_ORDER_HINT=1）提示模型尽量贴近源语小句顺序，
//      使每条译文与当时说的话对得上。
//
// 整句聚合默认按源语文字自动选择：拉丁字母等「以空格分词」的语言（英/法/德…）
// Whisper 常把一句切成多条，聚合收益大；中日韩等「不分词」语言的 Whisper 分段
// 往往已是短语级，强行聚合再回切会拆散专名、错位时间轴，因此默认逐条翻译。
//
// 可用环境变量（都有默认值）：
//   SUB_GROUP      -1|0|1   整句翻译：-1 自动（默认），0 关，1 强开
//   SUB_PAUSE      秒        句间停顿阈值，默认 0.7
//   SUB_MAX_LINES  条        单句最多聚合几条字幕，默认 8
//   SUB_MAX_CHARS  字        单句最多聚合多少字，默认 400
//   SUB_ORDER_HINT 1|0       是否加「贴近源语顺序」提示，默认 0
#include "llm.h"

#include <nlohmann/json.hpp>

#include <sys/socket.h>
#include <netdb.h>
#include <unistd.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>
#include <algorithm>

using json = nlohmann::json;

namespace {

std::mutex g_mutex;

struct Url {
  std::string host = "127.0.0.1";
  int port = 8080;
  std::string base = "/v1";
};

Url ParseUrl(const std::string& url) {
  Url u;
  std::string s = url;
  if (s.rfind("http://", 0) == 0) s = s.substr(7);
  else if (s.rfind("https://", 0) == 0) s = s.substr(8);
  size_t slash = s.find('/');
  std::string hostport = (slash == std::string::npos) ? s : s.substr(0, slash);
  u.base = (slash == std::string::npos) ? "" : s.substr(slash);
  size_t colon = hostport.find(':');
  if (colon == std::string::npos) {
    u.host = hostport;
  } else {
    u.host = hostport.substr(0, colon);
    u.port = std::atoi(hostport.c_str() + colon + 1);
  }
  if (u.base.empty()) u.base = "/v1";
  return u;
}

Url BaseUrl() {
  const char* e = std::getenv("LLM_HOST");
  return ParseUrl(e ? e : "http://127.0.0.1:8080/v1");
}

std::string Model() {
  const char* e = std::getenv("LLM_MODEL");
  return e ? e : "hunyuan-mt";
}

int EnvInt(const char* name, int def) {
  const char* e = std::getenv(name);
  if (!e || !e[0]) return def;
  return std::atoi(e);
}

double EnvDouble(const char* name, double def) {
  const char* e = std::getenv(name);
  if (!e || !e[0]) return def;
  return std::atof(e);
}

bool SendAll(int fd, const char* data, size_t len) {
  size_t sent = 0;
  while (sent < len) {
    ssize_t n = ::send(fd, data + sent, len - sent, 0);
    if (n <= 0) return false;
    sent += (size_t)n;
  }
  return true;
}

// 解析 chunked 传输编码
std::string Dechunk(const std::string& body) {
  std::string out;
  size_t i = 0;
  while (i < body.size()) {
    size_t eol = body.find("\r\n", i);
    if (eol == std::string::npos) break;
    std::string szline = body.substr(i, eol - i);
    size_t sc = szline.find(';');
    if (sc != std::string::npos) szline = szline.substr(0, sc);
    long sz = std::strtol(szline.c_str(), nullptr, 16);
    if (sz <= 0) break;
    size_t start = eol + 2;
    out.append(body, start, (size_t)sz);
    i = start + (size_t)sz + 2;  // skip data + CRLF
  }
  return out;
}

std::string Lower(std::string s) {
  for (char& c : s) c = (char)tolower((unsigned char)c);
  return s;
}

bool HttpPost(const std::string& path, const std::string& body, std::string& out) {
  Url u = BaseUrl();
  struct addrinfo hints{}, *res = nullptr;
  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;
  if (getaddrinfo(u.host.c_str(), std::to_string(u.port).c_str(), &hints, &res) != 0)
    return false;
  int fd = -1;
  for (auto* p = res; p; p = p->ai_next) {
    fd = ::socket(p->ai_family, p->ai_socktype, p->ai_protocol);
    if (fd < 0) continue;
    if (::connect(fd, p->ai_addr, p->ai_addrlen) == 0) break;
    ::close(fd);
    fd = -1;
  }
  freeaddrinfo(res);
  if (fd < 0) return false;

  std::string req = "POST " + path + " HTTP/1.1\r\n";
  req += "Host: " + u.host + ":" + std::to_string(u.port) + "\r\n";
  req += "Content-Type: application/json\r\n";
  req += "Content-Length: " + std::to_string(body.size()) + "\r\n";
  req += "Connection: close\r\n\r\n";
  req += body;
  bool ok = SendAll(fd, req.data(), req.size());

  std::string resp;
  if (ok) {
    char buf[16384];
    ssize_t n;
    while ((n = ::recv(fd, buf, sizeof(buf), 0)) > 0) resp.append(buf, (size_t)n);
  }
  ::close(fd);
  if (!ok || resp.empty()) return false;

  size_t hdr_end = resp.find("\r\n\r\n");
  if (hdr_end == std::string::npos) return false;
  std::string headers = Lower(resp.substr(0, hdr_end));
  std::string raw = resp.substr(hdr_end + 4);

  if (headers.find("transfer-encoding: chunked") != std::string::npos) {
    out = Dechunk(raw);
  } else {
    out = raw;
  }
  return true;
}

std::string Trim(const std::string& s) {
  size_t a = s.find_first_not_of(" \t\r\n");
  if (a == std::string::npos) return "";
  size_t b = s.find_last_not_of(" \t\r\n");
  return s.substr(a, b - a + 1);
}

std::string StripTags(const std::string& s) {
  std::string o;
  for (size_t i = 0; i < s.size(); ++i) {
    if (s[i] == '{') {
      while (i < s.size() && s[i] != '}') ++i;
      continue;
    }
    o += s[i];
  }
  return o;
}

std::string CleanAssText(std::string t) {
  std::string o;
  for (size_t i = 0; i < t.size(); ++i) {
    if (t[i] == '\\' && i + 1 < t.size() && (t[i + 1] == 'N' || t[i + 1] == 'n')) {
      o += ' ';
      ++i;
    } else {
      o += t[i];
    }
  }
  return Trim(StripTags(o));
}

// 把译文放回 ASS 文本域：去掉换行/大括号覆盖标记，保留字符本身。
std::string SanitizeAssText(std::string t) {
  std::string o;
  for (size_t i = 0; i < t.size(); ++i) {
    char c = t[i];
    if (c == '\r' || c == '\n') { o += ' '; continue; }
    if (c == '{') { while (i < t.size() && t[i] != '}') ++i; continue; }
    if (c == '\\' && i + 1 < t.size() && (t[i + 1] == 'N' || t[i + 1] == 'n')) { o += ' '; ++i; continue; }
    o += c;
  }
  return Trim(o);
}

std::vector<std::string> SplitN(const std::string& s, char sep, size_t n) {
  std::vector<std::string> out;
  size_t start = 0;
  while (out.size() + 1 < n) {
    size_t p = s.find(sep, start);
    if (p == std::string::npos) break;
    out.push_back(s.substr(start, p - start));
    start = p + 1;
  }
  out.push_back(s.substr(start));
  return out;
}

std::string LangName(const std::string& code) {
  static const std::vector<std::pair<std::string, std::string>> m = {
      {"zh", "Chinese"},   {"en", "English"},    {"ja", "Japanese"},
      {"ko", "Korean"},    {"fr", "French"},     {"de", "German"},
      {"es", "Spanish"},   {"ru", "Russian"},    {"it", "Italian"},
      {"pt", "Portuguese"},{"ar", "Arabic"},     {"th", "Thai"},
      {"vi", "Vietnamese"},{"id", "Indonesian"}};
  for (auto& p : m)
    if (p.first == code) return p.second;
  return code;
}

// ---------------------- UTF-8 与目标语切分器 ----------------------

std::vector<std::string> Utf8Split(const std::string& s) {
  std::vector<std::string> out;
  for (size_t i = 0; i < s.size();) {
    unsigned char c = (unsigned char)s[i];
    size_t len = 1;
    if (c >= 0xF0) len = 4;
    else if (c >= 0xE0) len = 3;
    else if (c >= 0xC0) len = 2;
    if (i + len > s.size()) len = 1;
    out.push_back(s.substr(i, len));
    i += len;
  }
  return out;
}

unsigned int Utf8Decode(const std::string& ch) {
  unsigned char c = (unsigned char)ch[0];
  if (c < 0x80) return c;
  if ((c >> 5) == 0x6 && ch.size() >= 2)
    return ((unsigned int)(c & 0x1F) << 6) | ((unsigned char)ch[1] & 0x3F);
  if ((c >> 4) == 0xE && ch.size() >= 3)
    return ((unsigned int)(c & 0x0F) << 12) | (((unsigned char)ch[1] & 0x3F) << 6) |
           ((unsigned char)ch[2] & 0x3F);
  if ((c >> 3) == 0x1E && ch.size() >= 4)
    return ((unsigned int)(c & 0x07) << 18) | (((unsigned char)ch[1] & 0x3F) << 12) |
           (((unsigned char)ch[2] & 0x3F) << 6) | ((unsigned char)ch[3] & 0x3F);
  return c;
}

bool IsSpace(unsigned int c) { return c == ' ' || c == '\t' || c == 0x3000; }

bool IsCjk(unsigned int c) {
  return (c >= 0x3040 && c <= 0x30FF) || (c >= 0x3400 && c <= 0x4DBF) ||
         (c >= 0x4E00 && c <= 0x9FFF) || (c >= 0xF900 && c <= 0xFAFF) ||
         (c >= 0xFF00 && c <= 0xFFEF) || (c >= 0xAC00 && c <= 0xD7AF) ||
         (c >= 0x3000 && c <= 0x303F);
}

bool IsOpening(unsigned int c) {
  switch (c) {
    case '(': case '[': case '{': case '<': case '"': case '\'':
    case 0x2018: case 0x201C: case 0x300C: case 0x300E: case 0x3010:
    case 0xFF08: case 0x300A: case 0x3008: case 0xFF5B: case 0x3014:
      return true;
  }
  return false;
}

bool IsClosing(unsigned int c) {
  switch (c) {
    case ')': case ']': case '}': case '>': case '"': case '\'':
    case '.': case ',': case '!': case '?': case ';': case ':':
    case 0x2019: case 0x201D: case 0x300D: case 0x300F: case 0x3011:
    case 0xFF09: case 0x300B: case 0x3009: case 0xFF5D: case 0x3015:
    case 0x3002: case 0xFF0C: case 0xFF01: case 0xFF1F: case 0xFF1B:
    case 0xFF1A: case 0x3001: case 0x2026:
      return true;
  }
  return false;
}

bool IsWordChar(unsigned int c) {
  return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
         (c >= 'a' && c <= 'z') || c == '_' || c == '\'';
}

bool IsTrailCloser(unsigned int c) {
  switch (c) {
    case ')': case ']': case '}': case '>': case '"': case '\'':
    case 0x2019: case 0x201D: case 0x300D: case 0x300F: case 0x3011:
    case 0xFF09: case 0x300B: case 0x3009: case 0xFF5D: case 0x3015:
      return true;
  }
  return false;
}

bool IsTerminal(unsigned int c) {
  return c == '.' || c == '!' || c == '?' || c == 0x3002 || c == 0xFF01 ||
         c == 0xFF1F || c == 0x2026;
}

bool IsClausePunct(unsigned int c) {
  switch (c) {
    case ',': case ';': case ':':
    case 0xFF0C: case 0x3001: case 0xFF1B: case 0xFF1A:
      return true;
  }
  return false;
}

// 两个码点之间能否断行（不切断词、不悬标点）。
bool AllowedBreak(unsigned int a, unsigned int b) {
  if (IsSpace(a) || IsSpace(b)) return true;         // 空白处总能切
  if (IsOpening(a)) return false;                    // 开括号/引号后不切
  if (IsClosing(b)) return false;                    // 闭标点/句读前不切
  if (IsWordChar(a) && IsWordChar(b)) return false;  // 词内、数字内不切
  if ((a >= '0' && a <= '9') && (b == '%' || b == 0xFF05)) return false;
  return true;
}

// 判定一行原文是否以句末标点收尾（忽略尾随引号/括号）。
bool EndsSentence(const std::string& s) {
  std::vector<std::string> ch = Utf8Split(s);
  for (int i = (int)ch.size() - 1; i >= 0; --i) {
    unsigned int c = Utf8Decode(ch[i]);
    if (IsSpace(c) || IsTrailCloser(c)) continue;
    return IsTerminal(c);
  }
  return false;
}

// "0:00:04.19" -> 秒
double ParseAssTime(const std::string& t) {
  int h = 0, m = 0;
  double s = 0;
  if (std::sscanf(t.c_str(), "%d:%d:%lf", &h, &m, &s) != 3) return 0;
  return h * 3600.0 + m * 60.0 + s;
}

// 把整句译文按 weights 比例切成等量片；只在合法缝切，尽量贴标点。
std::vector<std::string> SplitByWeights(const std::string& text,
                                        const std::vector<size_t>& weights) {
  std::vector<std::string> chars = Utf8Split(text);
  int L = (int)chars.size();
  int k = (int)weights.size();
  std::vector<std::string> out;
  if (k <= 1 || L == 0) { out.push_back(Trim(text)); return out; }

  if (L <= k) {  // 字太少：逐字分配，其余为空
    for (int i = 0; i < k; ++i) out.push_back(i < L ? chars[i] : std::string());
    return out;
  }

  std::vector<int> cand;
  for (int p = 1; p < L; ++p) {
    if (AllowedBreak(Utf8Decode(chars[p - 1]), Utf8Decode(chars[p]))) cand.push_back(p);
  }

  long W = 0;
  for (size_t w : weights) W += (long)std::max<size_t>(w, 1);

  std::vector<int> cuts;
  long cum = 0;
  for (int i = 0; i < k - 1; ++i) {
    cum += (long)std::max<size_t>(weights[i], 1);
    double target = (double)L * (double)cum / (double)W;
    int lo = cuts.empty() ? 1 : cuts.back() + 1;
    int hi = L - (k - 1 - i);
    if (hi < lo) hi = lo;
    int best = -1;
    double best_cost = 1e18;
    for (int c : cand) {
      if (c < lo) continue;
      if (c > hi) break;
      unsigned int prev = Utf8Decode(chars[c - 1]);
      double cost = std::fabs((double)c - target);
      if (IsTerminal(prev)) cost -= 6.0;       // 优先在句末标点后切
      else if (IsClausePunct(prev)) cost -= 3.0;  // 其次从句标点
      if (cost < best_cost) { best_cost = cost; best = c; }
    }
    if (best < 0) {
      best = (int)std::lround(target);
      if (best < lo) best = lo;
      if (best > hi) best = hi;
    }
    cuts.push_back(best);
  }

  int prev = 0;
  for (int i = 0; i < k; ++i) {
    int end = (i < k - 1) ? cuts[i] : L;
    std::string piece;
    for (int j = prev; j < end; ++j) piece += chars[j];
    out.push_back(Trim(piece));
    prev = end;
  }
  return out;
}

std::string ReadFile(const char* path) {
  FILE* f = std::fopen(path, "rb");
  if (!f) return "";
  std::string s;
  char buf[8192];
  size_t n;
  while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) s.append(buf, n);
  std::fclose(f);
  if (s.size() >= 3 && (unsigned char)s[0] == 0xEF && (unsigned char)s[1] == 0xBB &&
      (unsigned char)s[2] == 0xBF)
    s = s.substr(3);
  return s;
}

std::vector<std::string> SplitLines(const std::string& s) {
  std::vector<std::string> out;
  size_t start = 0;
  while (true) {
    size_t p = s.find('\n', start);
    if (p == std::string::npos) {
      out.push_back(s.substr(start));
      break;
    }
    out.push_back(s.substr(start, p - start));
    start = p + 1;
  }
  return out;
}

std::string BuildPrompt(const std::string& target_name, const std::string& text) {
  std::string p = "Translate the following segment into " + target_name +
                  ", without additional explanation.";
  if (EnvInt("SUB_ORDER_HINT", 0) != 0)
    p += " Keep the clause order close to the source.";
  p += "\n\n" + text;
  return p;
}

std::string TranslateOne(const std::string& text, const std::string& target_name) {
  json payload;
  payload["model"] = Model();
  payload["messages"] = json::array(
      {{{"role", "user"}, {"content", BuildPrompt(target_name, text)}}});
  payload["max_tokens"] = 2048;
  payload["temperature"] = 0;

  std::string resp;
  if (!HttpPost(BaseUrl().base + "/chat/completions", payload.dump(), resp)) return "";
  try {
    json j = json::parse(resp);
    if (!j.contains("choices") || j["choices"].empty()) return "";
    return SanitizeAssText(j["choices"][0]["message"]["content"].get<std::string>());
  } catch (const std::exception&) {
    return "";
  }
}

struct DialogueRow {
  std::string prefix;    // 字段 0..8 + ","
  std::string original;  // 原始文本域（含 \N 等）
  std::string src;       // CleanAssText 后的纯文本
  std::string actor;     // Name 字段
  double start = 0;
  double end = 0;
};

void EmitRow(const DialogueRow& r, const std::string& trans, std::string& events) {
  if (trans.empty() || trans == r.src)
    events += r.prefix + r.original + "\n";
  else
    events += r.prefix + r.original + "\\N" + trans + "\n";
}

// 把一组连续字幕条当作一个句子翻译，再按原文字数比例回切。
void ProcessGroup(const std::vector<DialogueRow>& g, const std::string& target_name,
                  std::string& events, int& count) {
  if (g.size() == 1) {
    const DialogueRow& r = g[0];
    EmitRow(r, r.src.empty() ? "" : TranslateOne(r.src, target_name), events);
    ++count;
    return;
  }

  // 拼接整句（CJK 之间不加空格，其余加空格）
  std::string joined;
  for (const auto& r : g) {
    if (r.src.empty()) continue;
    if (joined.empty()) { joined = r.src; continue; }
    std::vector<std::string> a = Utf8Split(joined);
    std::vector<std::string> b = Utf8Split(r.src);
    bool tight = !a.empty() && !b.empty() && IsCjk(Utf8Decode(a.back())) &&
                 IsCjk(Utf8Decode(b.front()));
    joined += tight ? r.src : (" " + r.src);
  }

  std::string trans = joined.empty() ? "" : TranslateOne(joined, target_name);
  if (trans.empty()) {  // 整句失败：退回逐条
    for (const auto& r : g) {
      EmitRow(r, r.src.empty() ? "" : TranslateOne(r.src, target_name), events);
      ++count;
    }
    return;
  }

  std::vector<size_t> weights;
  for (const auto& r : g) weights.push_back(Utf8Split(r.src).size());
  std::vector<std::string> pieces = SplitByWeights(trans, weights);
  for (size_t i = 0; i < g.size(); ++i) {
    EmitRow(g[i], i < pieces.size() ? pieces[i] : std::string(), events);
    ++count;
  }
}

}  // namespace

// =============================== C ABI ======================================

const char* llm_host(void) {
  static std::string h = [] { return BaseUrl().host + ":" + std::to_string(BaseUrl().port); }();
  return h.c_str();
}

const char* llm_translate(const char* text, const char* target_name) {
  std::lock_guard<std::mutex> lk(g_mutex);
  static thread_local std::string out;
  out = TranslateOne(text ? text : "", target_name ? target_name : "Chinese");
  return out.c_str();
}

int llm_translate_ass(const char* in_ass, const char* out_ass, const char* target_lang) {
  std::lock_guard<std::mutex> lk(g_mutex);
  std::string content = ReadFile(in_ass);
  if (content.empty()) return -1;

  std::vector<std::string> lines = SplitLines(content);
  size_t events_start = std::string::npos;
  for (size_t i = 0; i < lines.size(); ++i) {
    if (lines[i].rfind("[Events]", 0) == 0) { events_start = i; break; }
  }
  if (events_start == std::string::npos) return -1;

  std::string header;
  for (size_t i = 0; i <= events_start + 1 && i < lines.size(); ++i)
    header += lines[i] + "\n";

  const std::string target_name = LangName(target_lang ? target_lang : "zh");

  // 预扫描源语用字：中日韩等不分词语言默认关闭整句聚合
  int script_cjk = 0, script_latin = 0;
  for (size_t i = events_start + 2; i < lines.size(); ++i) {
    if (lines[i].rfind("Dialogue:", 0) != 0) continue;
    std::vector<std::string> parts = SplitN(lines[i], ',', 10);
    if (parts.size() < 10) continue;
    for (const auto& ch : Utf8Split(CleanAssText(parts[9]))) {
      unsigned int c = Utf8Decode(ch);
      if (IsCjk(c)) ++script_cjk;
      else if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')) ++script_latin;
    }
  }
  int grp_env = EnvInt("SUB_GROUP", -1);
  bool grouping = (grp_env < 0) ? (script_cjk <= script_latin) : (grp_env != 0);

  const double pause_sec = EnvDouble("SUB_PAUSE", 0.7);
  const int max_lines = grouping ? EnvInt("SUB_MAX_LINES", 8) : 1;
  const int max_chars = EnvInt("SUB_MAX_CHARS", 400);

  std::string events;
  int count = 0;
  std::vector<DialogueRow> group;

  auto flush = [&]() {
    if (group.empty()) return;
    ProcessGroup(group, target_name, events, count);
    group.clear();
  };

  for (size_t i = events_start + 2; i < lines.size(); ++i) {
    const std::string& line = lines[i];
    if (line.rfind("Dialogue:", 0) != 0) {
      flush();
      events += line + "\n";
      continue;
    }
    std::vector<std::string> parts = SplitN(line, ',', 10);
    if (parts.size() < 10) {
      flush();
      events += line + "\n";
      continue;
    }

    DialogueRow r;
    for (int k = 0; k < 9; ++k) r.prefix += parts[k] + ",";
    r.original = parts[9];
    r.src = CleanAssText(r.original);
    r.actor = parts[4];
    r.start = ParseAssTime(parts[1]);
    r.end = ParseAssTime(parts[2]);

    if (r.src.empty()) {  // 无文本：原样输出，不与相邻聚合
      flush();
      events += r.prefix + r.original + "\n";
      ++count;
      continue;
    }

    if (!group.empty()) {
      const DialogueRow& p = group.back();
      bool boundary = p.actor != r.actor || (r.start - p.end) >= pause_sec ||
                      EndsSentence(p.src) || (int)group.size() >= max_lines;
      if (boundary) flush();
    }
    group.push_back(r);

    size_t gl = 0;
    for (const auto& x : group) gl += Utf8Split(x.src).size();
    if ((int)gl >= max_chars) flush();
  }
  flush();

  std::string result = header + events;
  FILE* f = std::fopen(out_ass, "wb");
  if (!f) return -1;
  const unsigned char bom[3] = {0xEF, 0xBB, 0xBF};
  std::fwrite(bom, 1, 3, f);
  std::fwrite(result.data(), 1, result.size(), f);
  std::fclose(f);
  return count;
}
