// llm_capi.cpp — Hunyuan-MT (llama.cpp 服务) 的 C ABI 封装
//
// 自写最小 HTTP/1.1 POST 客户端（POSIX socket），无 libcurl 依赖；
// JSON 用 nlohmann/json 构造与解析。流程对齐 my-trans/llm.py。
#include "llm.h"

#include <nlohmann/json.hpp>

#include <sys/socket.h>
#include <netdb.h>
#include <unistd.h>

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

std::string TranslateOne(const std::string& text, const std::string& target_name) {
  json payload;
  payload["model"] = Model();
  payload["messages"] = json::array(
      {{{"role", "user"},
        {"content", "Translate the following segment into " + target_name +
                        ", without additional explanation.\n\n" + text}}});
  payload["max_tokens"] = 1024;
  payload["temperature"] = 0;

  std::string resp;
  if (!HttpPost(BaseUrl().base + "/chat/completions", payload.dump(), resp)) return "";
  try {
    json j = json::parse(resp);
    if (!j.contains("choices") || j["choices"].empty()) return "";
    return Trim(j["choices"][0]["message"]["content"].get<std::string>());
  } catch (const std::exception&) {
    return "";
  }
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

  std::string events;
  int count = 0;
  for (size_t i = events_start + 2; i < lines.size(); ++i) {
    const std::string& line = lines[i];
    if (line.rfind("Dialogue:", 0) != 0) continue;
    std::vector<std::string> parts = SplitN(line, ',', 10);
    if (parts.size() < 10) { events += line + "\n"; continue; }

    std::string prefix;
    for (int k = 0; k < 9; ++k) prefix += parts[k] + ",";
    std::string original = parts[9];
    std::string src = CleanAssText(original);
    std::string trans = src.empty() ? "" : TranslateOne(src, target_name);
    if (trans.empty() || trans == src)
      events += prefix + original + "\n";
    else
      events += prefix + original + "\\N" + trans + "\n";
    ++count;
  }

  std::string result = header + events;
  FILE* f = std::fopen(out_ass, "wb");
  if (!f) return -1;
  const unsigned char bom[3] = {0xEF, 0xBB, 0xBF};
  std::fwrite(bom, 1, 3, f);
  std::fwrite(result.data(), 1, result.size(), f);
  std::fclose(f);
  return count;
}
