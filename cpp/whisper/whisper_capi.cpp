// whisper_capi.cpp — ctranslate2 C++ Whisper 的 C ABI 封装（供 StaticPy FFI）
//
// 流程：ffmpeg 解码 16k 单声道 -> 30s 分块 -> log-mel(自写前端) -> CT2 generate
//       -> GPT-2 byte-level 去分词 -> 文本/JSON/ASS
#include "whisper.h"
#include "feat.h"

#include <ctranslate2/models/whisper.h>
#include <ctranslate2/storage_view.h>
#include <ctranslate2/types.h>
#include <ctranslate2/devices.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <chrono>
#include <cctype>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <algorithm>
#include <unordered_map>

#if defined(MYTRANS_HAVE_ORT)
#include <onnxruntime_cxx_api.h>
#endif

using namespace ctranslate2;

namespace {

const char* const kDefaultModelDir = "/data/models/faster-whisper-large-v3";
// 可选：日语专用模型（kotoba / whisper-ja 等）。默认与多语言相同；
// 需要时用 WHISPER_MODEL_DIR_JA 指定，检测到日语时自动切换（不存在则忽略）。
const char* const kDefaultJaModelDir = "/data/models/faster-whisper-large-v3";

bool FileExists(const std::string& p) {
  std::FILE* f = std::fopen(p.c_str(), "rb");
  if (f) { std::fclose(f); return true; }
  return false;
}

bool Profiling() {
  static bool p = std::getenv("WHISPER_PROFILE") != nullptr;
  return p;
}
double NowSec() {
  using namespace std::chrono;
  return duration<double>(steady_clock::now().time_since_epoch()).count();
}

std::mutex g_mutex;
models::Whisper* g_model = nullptr;
MelConfig g_cfg;
std::string g_dir;
bool g_ready = false;
// 语言检测缓存：wh_lang 算一次，TranscribeAudio 复用，避免重复跑 encoder
std::string g_detect_path;
std::string g_detect_lang;

// ---- GPT-2 byte-level 去分词 -------------------------------------------------

const std::unordered_map<uint32_t, uint8_t>& ByteDecoder() {
  static const std::unordered_map<uint32_t, uint8_t> m = [] {
    std::unordered_map<uint32_t, uint8_t> r;
    std::vector<int> bs, cs;
    for (int b = 33; b <= 126; ++b) bs.push_back(b);
    for (int b = 161; b <= 172; ++b) bs.push_back(b);
    for (int b = 174; b <= 255; ++b) bs.push_back(b);
    cs = bs;
    int n = 0;
    for (int b = 0; b < 256; ++b) {
      if (std::find(bs.begin(), bs.end(), b) == bs.end()) {
        bs.push_back(b);
        cs.push_back(256 + n);
        ++n;
      }
    }
    for (size_t i = 0; i < bs.size(); ++i) r[(uint32_t)cs[i]] = (uint8_t)bs[i];
    return r;
  }();
  return m;
}

// 把一段 byte-level token 字符串解码为 UTF-8 字节串
void AppendDecoded(const std::string& tok, std::string& out) {
  const auto& dec = ByteDecoder();
  size_t i = 0;
  while (i < tok.size()) {
    uint32_t cp = (unsigned char)tok[i];
    int len = 1;
    if (cp >= 0xF0) { cp &= 0x07; len = 4; }
    else if (cp >= 0xE0) { cp &= 0x0F; len = 3; }
    else if (cp >= 0xC0) { cp &= 0x1F; len = 2; }
    for (int k = 1; k < len && i + k < tok.size(); ++k)
      cp = (cp << 6) | ((unsigned char)tok[i + k] & 0x3F);
    i += len;
    auto it = dec.find(cp);
    if (it != dec.end())
      out.push_back((char)it->second);
  }
}

bool IsSpecial(const std::string& t) {
  return t.size() >= 4 && t[0] == '<' && t[1] == '|' && t[t.size() - 2] == '|' &&
         t[t.size() - 1] == '>';
}

bool IsTimestamp(const std::string& t, double& sec) {
  if (!IsSpecial(t)) return false;
  std::string inner = t.substr(2, t.size() - 4);
  if (inner.empty()) return false;
  bool has_dot = false;
  for (char c : inner) {
    if (c == '.') { has_dot = true; continue; }
    if (c < '0' || c > '9') return false;
  }
  if (!has_dot) return false;
  sec = std::atof(inner.c_str());
  return true;
}

// 解码一个 UTF-8 码点，返回其字节长度
size_t Utf8NextCp(const std::string& s, size_t i, uint32_t& cp) {
  unsigned char c = (unsigned char)s[i];
  if (c < 0x80) { cp = c; return 1; }
  if ((c >> 5) == 0x6 && i + 1 < s.size()) {
    cp = ((c & 0x1F) << 6) | ((unsigned char)s[i + 1] & 0x3F); return 2;
  }
  if ((c >> 4) == 0xE && i + 2 < s.size()) {
    cp = ((c & 0x0F) << 12) | (((unsigned char)s[i + 1] & 0x3F) << 6) |
         ((unsigned char)s[i + 2] & 0x3F); return 3;
  }
  if ((c >> 3) == 0x1E && i + 3 < s.size()) {
    cp = ((c & 0x07) << 18) | (((unsigned char)s[i + 1] & 0x3F) << 12) |
         (((unsigned char)s[i + 2] & 0x3F) << 6) | ((unsigned char)s[i + 3] & 0x3F); return 4;
  }
  cp = c; return 1;
}

// 最长“同一码点连续重复”的长度（用于识别 ああああ / はははは 等复读幻觉）
size_t MaxCodepointRun(const std::string& s) {
  size_t best = 0, run = 0, i = 0;
  uint32_t prev = 0;
  bool first = true;
  while (i < s.size()) {
    uint32_t cp;
    size_t len = Utf8NextCp(s, i, cp);
    if (!first && cp == prev) ++run; else { run = 1; prev = cp; first = false; }
    if (run > best) best = run;
    i += len;
  }
  return best;
}

// ---- 模型 / 特征 -------------------------------------------------------------

// 加载指定目录模型（失败则保持原模型不变）
bool LoadModelDir(const std::string& dir) {
  MelConfig cfg = ReadMelConfig(dir);
  const char* de = std::getenv("WHISPER_DEVICE");
  bool want_cpu = de && std::strcmp(de, "cpu") == 0;
  models::Whisper* m = nullptr;
  try {
    if (want_cpu)
      m = new models::Whisper(dir, Device::CPU, ComputeType::FLOAT32);
    else
      m = new models::Whisper(dir, Device::CUDA, ComputeType::FLOAT16);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "[whisper] GPU 初始化失败(%s)，回退 CPU\n", e.what());
    try {
      m = new models::Whisper(dir, Device::CPU, ComputeType::FLOAT32);
    } catch (const std::exception& e2) {
      std::fprintf(stderr, "[whisper] 模型加载失败 %s: %s\n", dir.c_str(), e2.what());
      return false;
    }
  }
  if (g_model) delete g_model;
  g_model = m;
  g_cfg = cfg;
  g_dir = dir;
  g_ready = true;
  return true;
}

// 返回日语专用模型目录（环境变量优先，其次默认路径，均需存在）
std::string JaModelDir() {
  const char* e = std::getenv("WHISPER_MODEL_DIR_JA");
  if (e && e[0]) return e;
  if (FileExists(std::string(kDefaultJaModelDir) + "/model.bin")) return kDefaultJaModelDir;
  return "";
}

bool InitLocked() {
  if (g_ready) return true;
  const char* md = std::getenv("WHISPER_MODEL_DIR");
  std::string dir = md ? md : kDefaultModelDir;
  // 已强制日语 → 直接用日语专用模型
  const char* fl = std::getenv("WHISPER_LANG");
  if (!md && fl && std::strcmp(fl, "ja") == 0) {
    std::string ja = JaModelDir();
    if (!ja.empty() && FileExists(ja + "/model.bin")) dir = ja;
  }
  if (Profiling()) std::fprintf(stderr, "[whisper] model dir = %s\n", dir.c_str());
  return LoadModelDir(dir);
}

StorageView MakeFeatures(const std::vector<float>& mel, int frames) {
  const int m = g_cfg.n_mels;
  const int nf = g_cfg.n_frames;
  StorageView fv({1, (dim_t)m, (dim_t)nf}, DataType::FLOAT32, Device::CPU);
  float* p = fv.data<float>();
  std::memset(p, 0, sizeof(float) * m * nf);
  const int copy = std::min(frames, nf);
  for (int mrow = 0; mrow < m; ++mrow)
    std::memcpy(p + (size_t)mrow * nf, mel.data() + (size_t)mrow * frames,
                sizeof(float) * copy);
  return fv;
}

struct Segment { double start, end; std::string text; };
struct Transcript {
  std::string lang;
  std::vector<Segment> segments;
};

#if defined(MYTRANS_HAVE_ORT)
// Silero VAD v5：16kHz、每帧 512 采样（+64 上下文 = 576 输入），输出逐帧语音概率
class SileroVad {
 public:
  bool Init(const std::string& path) {
    try {
      env_ = std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_ERROR, "mytrans-vad");
      Ort::SessionOptions so;
      so.SetIntraOpNumThreads(1);
      so.SetInterOpNumThreads(1);
      session_ = std::make_unique<Ort::Session>(*env_, path.c_str(), so);
      Ort::AllocatorWithDefaultOptions alloc;
      for (size_t i = 0; i < session_->GetInputCount(); ++i)
        in_names_.push_back(session_->GetInputNameAllocated(i, alloc).get());
      for (size_t i = 0; i < session_->GetOutputCount(); ++i)
        out_names_.push_back(session_->GetOutputNameAllocated(i, alloc).get());
      for (auto& s : in_names_) in_ptrs_.push_back(s.c_str());
      for (auto& s : out_names_) out_ptrs_.push_back(s.c_str());
      return true;
    } catch (const std::exception& e) {
      std::fprintf(stderr, "[vad] 加载 %s 失败: %s\n", path.c_str(), e.what());
      return false;
    }
  }

  std::vector<float> Probs(const std::vector<float>& a) {
    const int W = 512, CTX = 64;
    std::vector<float> probs;
    if (a.empty()) return probs;
    std::vector<float> state((size_t)2 * 128, 0.0f);
    std::vector<float> in((size_t)W + CTX, 0.0f);
    std::vector<float> ctx(CTX, 0.0f);
    std::vector<int64_t> in_shape{1, (int64_t)(W + CTX)};
    std::vector<int64_t> state_shape{2, 1, 128};
    int64_t sr = 16000;
    auto mi = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    probs.reserve(a.size() / W);
    for (size_t i = 0; i + W <= a.size(); i += W) {
      std::memcpy(in.data(), ctx.data(), CTX * sizeof(float));
      std::memcpy(in.data() + CTX, a.data() + i, W * sizeof(float));
      std::memcpy(ctx.data(), a.data() + i + W - CTX, CTX * sizeof(float));
      Ort::Value t_in = Ort::Value::CreateTensor<float>(mi, in.data(), in.size(),
                                                        in_shape.data(), in_shape.size());
      Ort::Value t_state = Ort::Value::CreateTensor<float>(mi, state.data(), state.size(),
                                                           state_shape.data(), state_shape.size());
      Ort::Value t_sr = Ort::Value::CreateTensor<int64_t>(mi, &sr, 1, nullptr, 0);
      std::vector<Ort::Value> inputs;
      inputs.push_back(std::move(t_in));
      inputs.push_back(std::move(t_state));
      inputs.push_back(std::move(t_sr));
      auto outs = session_->Run(Ort::RunOptions{nullptr}, in_ptrs_.data(), inputs.data(),
                                inputs.size(), out_ptrs_.data(), out_ptrs_.size());
      probs.push_back(outs[0].GetTensorData<float>()[0]);
      std::memcpy(state.data(), outs[1].GetTensorData<float>(), state.size() * sizeof(float));
    }
    return probs;
  }

 private:
  std::unique_ptr<Ort::Env> env_;
  std::unique_ptr<Ort::Session> session_;
  std::vector<std::string> in_names_, out_names_;
  std::vector<const char*> in_ptrs_, out_ptrs_;
};
#else
class SileroVad {
 public:
  bool Init(const std::string&) { return false; }
  std::vector<float> Probs(const std::vector<float>&) { return {}; }
};
#endif

std::unique_ptr<SileroVad> g_vad;  // 受 g_mutex 保护
bool g_vad_tried = false;

// Whisper byte-level BPE 可能吐出非法 UTF-8 字节序列；替换为 U+FFFD，避免下游 JSON 报错
void SanitizeUtf8(std::string& s) {
  std::string o;
  o.reserve(s.size());
  const size_t n = s.size();
  size_t i = 0;
  while (i < n) {
    unsigned char c = s[i];
    size_t len;
    if (c < 0x80) len = 1;
    else if ((c >> 5) == 0x06) len = 2;
    else if ((c >> 4) == 0x0E) len = 3;
    else if ((c >> 3) == 0x1E) len = 4;
    else { o += "\xEF\xBF\xBD"; ++i; continue; }
    if (i + len > n) { o += "\xEF\xBF\xBD"; ++i; continue; }
    bool ok = true;
    for (size_t k = 1; k < len; ++k)
      if (((unsigned char)s[i + k] & 0xC0) != 0x80) { ok = false; break; }
    if (!ok) { o += "\xEF\xBF\xBD"; ++i; continue; }
    o.append(s, i, len);
    i += len;
  }
  s.swap(o);
}

// 跨多个窗口投票检测语言（单窗易被开头音乐/静音带偏，曾把日语误判为 nn）
std::string DetectLanguageMulti(const std::vector<float>& audio) {
  const int sr = g_cfg.sample_rate;
  const int win = 30 * sr;
  const long long total = (long long)audio.size();
  const long long step = std::max<long long>(win, total / 8);
  std::unordered_map<std::string, double> votes;  // 软投票：累加各语言概率
  int samples = 0;
  for (long long s = 0; s < total && samples < 5; s += step) {
    const int l = (int)std::min<long long>(win, total - s);
    std::vector<float> ch(audio.begin() + s, audio.begin() + s + l);
    int fr = 0;
    std::vector<float> ml = LogMel(ch, g_cfg, fr);
    if (fr <= 0) continue;
    auto futures = g_model->detect_language(MakeFeatures(ml, fr));
    auto res = futures[0].get();
    std::string top;
    double topp = -1;
    for (const auto& p : res) {
      std::string t = p.first;
      if (t.size() >= 4) t = t.substr(2, t.size() - 4);
      votes[t] += p.second;
      if (p.second > topp) { topp = p.second; top = t; }
    }
    samples++;
    if (Profiling())
      std::fprintf(stderr, "[whisper] lang vote %s(%.2f) @%.0fs\n", top.c_str(), topp,
                   (double)s / sr);
  }
  std::string best = "en";
  double bc = -1;
  for (const auto& kv : votes)
    if (kv.second > bc) { bc = kv.second; best = kv.first; }
  return best;
}

Transcript TranscribeAudio(models::Whisper* model, const char* path) {
  Transcript out;
  double t_start = NowSec();
  std::vector<float> audio = LoadAudio16kMono(path);
  double t_load = NowSec();
  if (audio.empty()) return out;
  double t_mel = 0.0, t_gen = 0.0;

  const int sr = g_cfg.sample_rate;
  auto is_distil = [](const std::string& d) {
    return d.find("kotoba") != std::string::npos || d.find("distil") != std::string::npos;
  };
  double chunk_sec = is_distil(g_dir) ? 15.0 : 30.0;  // kotoba/distil 建议 15s 窗
  if (const char* v = std::getenv("WHISPER_CHUNK_SEC")) chunk_sec = std::atof(v);
  if (chunk_sec < 5.0) chunk_sec = 5.0;
  int window = (int)(chunk_sec * sr);
  const long long total = (long long)audio.size();

  // WHISPER_LANG 强制源语言（如 ja / zh / en），跳过自动检测，避免误检
  const char* forced_lang = std::getenv("WHISPER_LANG");
  if (forced_lang && !forced_lang[0]) forced_lang = nullptr;

  // ---- 语言检测：跨多个窗口投票取多数（单窗易被音乐/静音带偏，曾把日语误判为 nn）----
  if (forced_lang) {
    out.lang = forced_lang;
    if (Profiling()) std::fprintf(stderr, "[whisper] lang forced = %s\n", forced_lang);
  } else if (!g_detect_path.empty() && g_detect_path == path && !g_detect_lang.empty()) {
    out.lang = g_detect_lang;  // 复用 wh_lang 的检测结果，避免重复跑 encoder
    if (Profiling()) std::fprintf(stderr, "[whisper] lang = %s (cached)\n", out.lang.c_str());
  } else {
    out.lang = DetectLanguageMulti(audio);
    if (Profiling()) std::fprintf(stderr, "[whisper] lang = %s\n", out.lang.c_str());
  }

  // 日语 → 切换日语专用模型（kotoba-whisper）
  if (!forced_lang && !std::getenv("WHISPER_MODEL_DIR") && out.lang == "ja") {
    std::string ja = JaModelDir();
    if (!ja.empty() && ja != g_dir) {
      if (Profiling()) std::fprintf(stderr, "[whisper] switch JA model -> %s\n", ja.c_str());
      if (LoadModelDir(ja)) {
        model = g_model;
        if (!std::getenv("WHISPER_CHUNK_SEC")) {
          chunk_sec = is_distil(g_dir) ? 15.0 : 30.0;
          if (chunk_sec < 5.0) chunk_sec = 5.0;
          window = (int)(chunk_sec * sr);
        }
      }
    }
  }
  const std::string lang_tok = "<|" + out.lang + "|>";

  // ---- Silero VAD 门控：默认仅日语开启（日语 AV 音乐/呻吟多）；其它语言关闭，
  //      以免把轻声对白（如电影里的短句）误判为非语音而整段漏识别 ----
  const char* vv = std::getenv("WHISPER_VAD");
  bool vad_on = vv ? std::strcmp(vv, "0") != 0 : (out.lang == "ja");
  double vad_thr = 0.5;
  if (const char* v = std::getenv("WHISPER_VAD_THRESHOLD")) vad_thr = std::atof(v);
  std::vector<uint8_t> speech;   // 逐帧(512 采样)语音标志
  std::vector<int> speech_pref;  // 前缀和
  if (vad_on) {
    if (!g_vad_tried) {
      g_vad_tried = true;
      const char* mp = std::getenv("WHISPER_VAD_MODEL");
      std::string path = mp ? mp : "/data/models/silero-vad/silero_vad.onnx";
      auto v = std::make_unique<SileroVad>();
      if (v->Init(path)) g_vad = std::move(v);
      else std::fprintf(stderr, "[whisper] VAD 不可用，跳过语音门控\n");
    }
    if (g_vad) {
      std::vector<float> pr = g_vad->Probs(audio);
      speech.assign(pr.size(), 0);
      for (size_t i = 0; i < pr.size(); ++i) speech[i] = pr[i] >= vad_thr ? 1 : 0;
      speech_pref.assign(speech.size() + 1, 0);
      for (size_t i = 0; i < speech.size(); ++i) speech_pref[i + 1] = speech_pref[i] + speech[i];
      if (Profiling())
        std::fprintf(stderr, "[whisper] vad: %zu frames, %d speech (%.1f%%)\n", speech.size(),
                     speech_pref.back(),
                     100.0 * speech_pref.back() / (speech.empty() ? 1 : speech.size()));
    }
  }
  const double frame_sec = 512.0 / sr;
  auto speech_seconds_in = [&](double s, double e) -> double {
    if (speech.empty()) return -1.0;  // VAD 关闭
    long lo = (long)(s / frame_sec), hi = (long)std::ceil(e / frame_sec);
    if (lo < 0) lo = 0;
    if (hi > (long)speech.size()) hi = (long)speech.size();
    if (hi <= lo) return 0.0;
    return (speech_pref[hi] - speech_pref[lo]) * frame_sec;
  };

  models::WhisperOptions opt;
  opt.beam_size = 5;
  opt.patience = 1.0f;
  opt.max_length = 448;
  // 抗幻觉：惩罚重复、禁止复读 n-gram（静音/音乐段常触发“复读”幻觉）
  opt.repetition_penalty = 1.15f;
  opt.no_repeat_ngram_size = 3;
  if (const char* bs = std::getenv("WHISPER_BEAM")) opt.beam_size = std::atoi(bs);
  if (const char* rp = std::getenv("WHISPER_REPETITION_PENALTY"))
    opt.repetition_penalty = (float)std::atof(rp);
  if (const char* ng = std::getenv("WHISPER_NO_REPEAT_NGRAM"))
    opt.no_repeat_ngram_size = (size_t)std::atoi(ng);
  opt.return_no_speech_prob = true;
  opt.return_scores = true;
  float no_speech_threshold = 0.6f;
  if (const char* ns = std::getenv("WHISPER_NO_SPEECH_THRESHOLD"))
    no_speech_threshold = (float)std::atof(ns);
  // 与 whisper.cpp 一致：no_speech 高“且”置信度低才丢弃，避免误删真实对白
  float logprob_threshold = -1.0f;
  if (const char* lp = std::getenv("WHISPER_LOGPROB_THRESHOLD"))
    logprob_threshold = (float)std::atof(lp);

  // faster-whisper 式长音频解码：滑动窗口，seek 前进到“最后一个时间戳”，
  // 使块边界处被截断的句子在下一窗口重新解码，避免丢句。
  long long seek = 0;
  while (seek < total) {
    const int len = (int)std::min<long long>(window, total - seek);
    // 该窗完全无语音 → 跳过解码（既提速又杜绝幻觉）
    if (speech_seconds_in((double)seek / sr, (double)(seek + len) / sr) == 0.0) {
      seek += window;
      continue;
    }
    std::vector<float> chunk(audio.begin() + seek, audio.begin() + seek + len);
    int frames = 0;
    double m0 = NowSec();
    std::vector<float> mel = LogMel(chunk, g_cfg, frames);
    if (frames <= 0) { seek += window; continue; }
    StorageView feat = MakeFeatures(mel, frames);
    t_mel += NowSec() - m0;

    std::vector<std::vector<std::string>> prompts = {
        {"<|startoftranscript|>", lang_tok, "<|transcribe|>"}};
    double g0 = NowSec();
    auto futures = model->generate(feat, prompts, opt);
    auto result = futures[0].get();
    t_gen += NowSec() - g0;
    if (result.sequences.empty()) { seek += window; continue; }
    const auto& toks = result.sequences[0];

    const double base = (double)seek / sr;
    const double total_sec = (double)total / sr;
    double prev_ts = 0.0, last_end = 0.0;
    bool have_start = false;
    std::string buf;
    std::vector<Segment> win;
    for (const std::string& t : toks) {
      double ts = 0.0;
      if (IsTimestamp(t, ts)) {
        if (have_start) {
          std::string text;
          // trim
          size_t a = buf.find_first_not_of(" \t\n");
          size_t b = buf.find_last_not_of(" \t\n");
          if (a != std::string::npos) text = buf.substr(a, b - a + 1);
          SanitizeUtf8(text);
          // 钳制到音频时长，避免静音区幻觉把末句拖到窗口边界
          double s = base + prev_ts;
          double e = std::min(base + ts, total_sec);
          if (!text.empty() && s < total_sec && e > s)
            win.push_back({s, e, text});
        }
        buf.clear();
        prev_ts = ts;
        last_end = ts;
        have_start = true;
      } else if (IsSpecial(t)) {
        // <|startoftranscript|> / <|en|> / <|transcribe|> / <|endoftext|> 等
      } else {
        AppendDecoded(t, buf);
      }
    }

    if (Profiling())
      std::fprintf(stderr, "[whisper] win @%.1fs nsp=%.2f score=%.2f segs=%zu\n", base,
                   result.no_speech_prob, result.scores.empty() ? 0.0f : result.scores[0],
                   win.size());

    // 静音/音乐段幻觉：仅当“无语音概率高”且“置信度低”才丢弃整窗
    // （只看 no_speech 会误删真实对白，例如《The Reader》开头 nsp=0.62 但 score=-0.31）
    const float win_score = result.scores.empty() ? 0.0f : result.scores[0];
    if (result.no_speech_prob > no_speech_threshold && win_score < logprob_threshold) {
      if (Profiling())
        std::fprintf(stderr, "[whisper] drop window @%.1fs (no_speech=%.2f, score=%.2f, %zu segs)\n",
                     base, result.no_speech_prob, win_score, win.size());
    } else {
      for (Segment& s : win) out.segments.push_back(s);
    }

    // 前进到最后一个时间戳；无时间戳则整窗前进，保证进度
    long long adv = last_end > 0.1 ? (long long)(last_end * sr) : window;
    seek = std::max(seek + 1, seek + adv);
  }

  // ---- 幻觉过滤（结构性，不做文本黑名单）----
  // 真实语音段远短于一个解码窗；跨满整窗（≈window 秒）的单段是“无语音仍强制输出”
  // 的解码器伪影，直接丢弃。
  double max_seg = 25.0, vad_min = 0.1;  // 只丢接近整窗(~30s)的填充伪影，避免误删真实长句
  if (const char* v = std::getenv("WHISPER_MAX_SEG_SEC")) max_seg = std::atof(v);
  if (const char* v = std::getenv("WHISPER_VAD_MIN_SEC")) vad_min = std::atof(v);

  // 复读幻觉：同一字连续重复（ああああ / はははは 等）
  size_t max_char_run = 4;
  if (const char* v = std::getenv("WHISPER_MAX_CHAR_RUN")) max_char_run = (size_t)std::atoi(v);
  // 已知幻觉短语（片头片尾/音乐段常见）；WHISPER_DROP_PHRASES 覆盖该项（"-" 表示关闭）
  // 默认不做短语黑名单：仅凭文本无法区分「真的说了」与幻觉，误删真台词不可接受。
  // 需要时用 WHISPER_DROP_PHRASES="a,b" 显式开启（默认关闭）。
  std::vector<std::string> drop_phrases;
  if (const char* v = std::getenv("WHISPER_DROP_PHRASES")) {
    drop_phrases.clear();
    std::string s(v);
    if (s != "-") {
      size_t p = 0;
      while (p <= s.size()) {
        size_t q = s.find(',', p);
        std::string item = s.substr(p, q == std::string::npos ? std::string::npos : q - p);
        if (!item.empty()) drop_phrases.push_back(item);
        if (q == std::string::npos) break;
        p = q + 1;
      }
    }
  }
  const size_t before = out.segments.size();
  std::vector<Segment> filtered;
  filtered.reserve(before);
  size_t n_run = 0, n_phrase = 0;
  for (const Segment& s : out.segments) {
    if (s.end - s.start >= max_seg) continue;                          // 整窗填充伪影
    const double sp = speech_seconds_in(s.start, s.end);               // 落在非语音区则丢弃
    if (sp >= 0.0 && sp < vad_min) continue;
    if (!filtered.empty() && filtered.back().text == s.text) continue;  // 相邻重复
    if (max_char_run > 0 && MaxCodepointRun(s.text) >= max_char_run) { ++n_run; continue; }
    bool hit = false;
    for (const std::string& ph : drop_phrases)
      if (!ph.empty() && s.text.find(ph) != std::string::npos) { hit = true; break; }
    if (hit) { ++n_phrase; continue; }
    filtered.push_back(s);
  }
  if (Profiling())
    std::fprintf(stderr, "[whisper] hallucination filter: char-run=%zu phrase=%zu\n", n_run,
                 n_phrase);
  if (Profiling())
    std::fprintf(stderr, "[whisper] window-fill filter: %zu -> %zu\n", before, filtered.size());
  out.segments.swap(filtered);

  if (Profiling())
    std::fprintf(stderr, "[whisper] load=%.2fs mel=%.2fs gen=%.2fs total=%.2fs\n",
                 t_load - t_start, t_mel, t_gen, NowSec() - t_start);
  return out;
}

std::string JsonEscape(const std::string& s) {
  std::string o;
  for (char c : s) {
    switch (c) {
      case '"': o += "\\\""; break;
      case '\\': o += "\\\\"; break;
      case '\n': o += "\\n"; break;
      case '\r': o += "\\r"; break;
      case '\t': o += "\\t"; break;
      default:
        if ((unsigned char)c < 0x20) {
          char b[8];
          std::snprintf(b, sizeof(b), "\\u%04x", c);
          o += b;
        } else {
          o += c;
        }
    }
  }
  return o;
}

std::string FormatTimeAss(double seconds) {
  if (seconds < 0) seconds = 0;
  int h = (int)(seconds / 3600);
  int m = (int)((seconds - h * 3600) / 60);
  int s = (int)(seconds - h * 3600 - m * 60);
  int cs = (int)((seconds - (int)seconds) * 100);
  char b[32];
  std::snprintf(b, sizeof(b), "%d:%02d:%02d.%02d", h, m, s, cs);
  return b;
}

}  // namespace

// =============================== C ABI ======================================

const char* wh_model_dir(void) {
  const char* md = std::getenv("WHISPER_MODEL_DIR");
  return md ? md : kDefaultModelDir;
}

const char* wh_lang(const char* audio_path) {
  std::lock_guard<std::mutex> lk(g_mutex);
  static thread_local std::string out;
  // 强制源语言时直接返回（命名与转写一致，避免误检后缀）
  if (const char* forced = std::getenv("WHISPER_LANG")) {
    if (forced[0]) { out = forced; return out.c_str(); }
  }
  if (!InitLocked()) return "";
  std::vector<float> audio = LoadAudio16kMono(audio_path);
  if (audio.empty()) { out = ""; return out.c_str(); }
  // 与转写用同一套多窗投票，保证命名与转写语言一致
  out = DetectLanguageMulti(audio);
  g_detect_path = audio_path;
  g_detect_lang = out;
  return out.c_str();
}

const char* wh_transcribe(const char* audio_path) {
  std::lock_guard<std::mutex> lk(g_mutex);
  static thread_local std::string out;
  if (!InitLocked()) { out = ""; return out.c_str(); }
  Transcript t = TranscribeAudio(g_model, audio_path);
  out.clear();
  for (const auto& s : t.segments) {
    if (!out.empty()) out += "\n";
    out += s.text;
  }
  return out.c_str();
}

const char* wh_transcribe_json(const char* audio_path) {
  std::lock_guard<std::mutex> lk(g_mutex);
  static thread_local std::string out;
  if (!InitLocked()) { out = "{\"lang\":\"\",\"segments\":[]}"; return out.c_str(); }
  Transcript t = TranscribeAudio(g_model, audio_path);
  out = "{\"lang\":\"" + JsonEscape(t.lang) + "\",\"segments\":[";
  for (size_t i = 0; i < t.segments.size(); ++i) {
    const auto& s = t.segments[i];
    if (i) out += ",";
    char tm[64];
    std::snprintf(tm, sizeof(tm), "{\"start\":%.3f,\"end\":%.3f,\"text\":\"", s.start, s.end);
    out += tm;
    out += JsonEscape(s.text);
    out += "\"}";
  }
  out += "]}";
  return out.c_str();
}

int wh_to_ass(const char* audio_path, const char* out_ass, double offset) {
  std::lock_guard<std::mutex> lk(g_mutex);
  if (!InitLocked()) return -1;
  Transcript t = TranscribeAudio(g_model, audio_path);

  std::string ass =
      "[Script Info]\n"
      "Title: Auto Generated Subtitles\n"
      "ScriptType: v4.00+\n"
      "WrapStyle: 0\n"
      "PlayResX: 1920\n"
      "PlayResY: 1080\n"
      "ScaledBorderAndShadow: yes\n\n"
      "[V4+ Styles]\n"
      "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
      "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
      "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
      "Style: Default,仓耳今楷02,46,&H0000A5FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,"
      "100,100,0,0,1,2,2,2,10,10,10,1\n"
      "Style: Top,仓耳今楷02,40,&H0000A5FF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,"
      "100,100,0,0,1,2,2,9,10,10,10,1\n\n"
      "[Events]\n"
      "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n";

  int n = 0;
  for (const auto& s : t.segments) {
    if (s.text.empty()) continue;
    // 防止字幕文本中的 { } 触发 ASS override 标签
    std::string text;
    text.reserve(s.text.size());
    for (char c : s.text) {
      if (c == '\n') text += ' ';
      else if (c == '{') text += "\xEF\xBD\x9B";  // ｛
      else if (c == '}') text += "\xEF\xBD\x9D";  // ｝
      else text += c;
    }
    ass += "Dialogue: 0," + FormatTimeAss(s.start + offset) + "," +
           FormatTimeAss(s.end + offset) + ",Default,,0,0,0,," + text + "\\N\n";
    ++n;
  }

  FILE* f = std::fopen(out_ass, "wb");
  if (!f) return -1;
  const unsigned char bom[3] = {0xEF, 0xBB, 0xBF};
  std::fwrite(bom, 1, 3, f);
  std::fwrite(ass.data(), 1, ass.size(), f);
  std::fclose(f);
  return n;
}
