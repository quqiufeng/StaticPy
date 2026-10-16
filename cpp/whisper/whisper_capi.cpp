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
#include <mutex>
#include <string>
#include <vector>
#include <algorithm>
#include <unordered_map>

using namespace ctranslate2;

namespace {

const char* const kDefaultModelDir = "/data/models/faster-whisper-large-v3-turbo";

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
bool g_ready = false;

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

// ---- 模型 / 特征 -------------------------------------------------------------

bool InitLocked() {
  if (g_ready) return true;
  const char* md = std::getenv("WHISPER_MODEL_DIR");
  std::string dir = md ? md : kDefaultModelDir;
  g_cfg = ReadMelConfig(dir);

  const char* de = std::getenv("WHISPER_DEVICE");
  bool want_cpu = de && std::strcmp(de, "cpu") == 0;
  try {
    if (want_cpu)
      g_model = new models::Whisper(dir, Device::CPU, ComputeType::FLOAT32);
    else
      g_model = new models::Whisper(dir, Device::CUDA, ComputeType::FLOAT16);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "[whisper] GPU 初始化失败(%s)，回退 CPU\n", e.what());
    try {
      g_model = new models::Whisper(dir, Device::CPU, ComputeType::FLOAT32);
    } catch (const std::exception& e2) {
      std::fprintf(stderr, "[whisper] 模型加载失败: %s\n", e2.what());
      return false;
    }
  }
  g_ready = true;
  return true;
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

std::string DetectLang(models::Whisper* model, const StorageView& feat) {
  auto futures = model->detect_language(feat);
  auto res = futures[0].get();
  if (res.empty()) return "en";
  std::string tok = res[0].first;  // 形如 "<|en|>"
  if (tok.size() >= 4) return tok.substr(2, tok.size() - 4);
  return tok;
}

Transcript TranscribeAudio(models::Whisper* model, const char* path) {
  Transcript out;
  double t_start = NowSec();
  std::vector<float> audio = LoadAudio16kMono(path);
  double t_load = NowSec();
  if (audio.empty()) return out;
  double t_mel = 0.0, t_gen = 0.0;

  const int sr = g_cfg.sample_rate;
  const int window = 30 * sr;  // 480000
  const long long total = (long long)audio.size();
  bool have_lang = false;
  std::string lang_tok;

  models::WhisperOptions opt;
  opt.beam_size = 5;
  opt.patience = 1.0f;
  opt.max_length = 448;
  if (const char* bs = std::getenv("WHISPER_BEAM")) opt.beam_size = std::atoi(bs);

  // faster-whisper 式长音频解码：滑动窗口，seek 前进到“最后一个时间戳”，
  // 使块边界处被截断的句子在下一窗口重新解码，避免丢句。
  long long seek = 0;
  while (seek < total) {
    const int len = (int)std::min<long long>(window, total - seek);
    std::vector<float> chunk(audio.begin() + seek, audio.begin() + seek + len);
    int frames = 0;
    double m0 = NowSec();
    std::vector<float> mel = LogMel(chunk, g_cfg, frames);
    if (frames <= 0) { seek += window; continue; }
    StorageView feat = MakeFeatures(mel, frames);
    t_mel += NowSec() - m0;

    if (!have_lang) {
      double d0 = NowSec();
      out.lang = DetectLang(model, feat);
      if (Profiling())
        std::fprintf(stderr, "[whisper] detect_lang(1 encoder pass)=%.2fs\n", NowSec() - d0);
      lang_tok = "<|" + out.lang + "|>";
      have_lang = true;
    }

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
    for (const std::string& t : toks) {
      double ts = 0.0;
      if (IsTimestamp(t, ts)) {
        if (have_start) {
          std::string text;
          // trim
          size_t a = buf.find_first_not_of(" \t\n");
          size_t b = buf.find_last_not_of(" \t\n");
          if (a != std::string::npos) text = buf.substr(a, b - a + 1);
          // 钳制到音频时长，避免静音区幻觉把末句拖到窗口边界
          double s = base + prev_ts;
          double e = std::min(base + ts, total_sec);
          if (!text.empty() && s < total_sec && e > s)
            out.segments.push_back({s, e, text});
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

    // 前进到最后一个时间戳；无时间戳则整窗前进，保证进度
    long long adv = last_end > 0.1 ? (long long)(last_end * sr) : window;
    seek = std::max(seek + 1, seek + adv);
  }
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
  if (!InitLocked()) return "";
  static thread_local std::string out;
  Transcript t;  // 仅需语言：跑第一块即可，这里直接复用整段（短音频开销可接受）
  // 为节省时间，只解码首 30s 做语言检测
  std::vector<float> audio = LoadAudio16kMono(audio_path);
  if (audio.empty()) { out = ""; return out.c_str(); }
  int len = std::min((int)audio.size(), 30 * g_cfg.sample_rate);
  std::vector<float> head(audio.begin(), audio.begin() + len);
  int frames = 0;
  std::vector<float> mel = LogMel(head, g_cfg, frames);
  out = frames > 0 ? DetectLang(g_model, MakeFeatures(mel, frames)) : "";
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
  if (t.segments.empty()) return 0;

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
    std::string text = s.text;
    for (char& c : text)
      if (c == '\n') c = ' ';
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
