// feat.cpp — 音频解码（ffmpeg）+ Whisper log-mel 特征提取（fftw3f）
//
// 对齐 openai-whisper / faster-whisper 的前端：
//   audio -> reflect pad(n_fft/2) -> Hann(periodic) STFT -> |X|^2
//         -> mel(slaney, n_mels) -> log10(clamp 1e-10) -> clamp(max-8) -> (x+4)/4
#include "feat.h"

#include <fftw3.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include <cmath>
#include <algorithm>

namespace {

std::string ReadFileToString(const char* path) {
  FILE* f = std::fopen(path, "rb");
  if (!f) return "";
  std::string s;
  char buf[4096];
  size_t n;
  while ((n = std::fread(buf, 1, sizeof(buf), f)) > 0) s.append(buf, n);
  std::fclose(f);
  return s;
}

int FindInt(const std::string& json, const std::string& key, int def) {
  const std::string k = "\"" + key + "\"";
  size_t p = json.find(k);
  if (p == std::string::npos) return def;
  p = json.find(':', p + k.size());
  if (p == std::string::npos) return def;
  return std::atoi(json.c_str() + p + 1);
}

// Slaney mel scale (librosa default, htk=False)
double HzToMel(double hz) {
  const double f_min = 0.0, f_sp = 200.0 / 3.0;
  double mel = (hz - f_min) / f_sp;
  const double min_log_hz = 1000.0;
  const double min_log_mel = (min_log_hz - f_min) / f_sp;  // 15
  const double logstep = std::log(6.4) / 27.0;
  if (hz >= min_log_hz) mel = min_log_mel + std::log(hz / min_log_hz) / logstep;
  return mel;
}

double MelToHz(double mel) {
  const double f_min = 0.0, f_sp = 200.0 / 3.0;
  double hz = f_min + f_sp * mel;
  const double min_log_hz = 1000.0;
  const double min_log_mel = (min_log_hz - f_min) / f_sp;
  const double logstep = std::log(6.4) / 27.0;
  if (mel >= min_log_mel) hz = min_log_hz * std::exp(logstep * (mel - min_log_mel));
  return hz;
}

// librosa.filters.mel(norm='slaney'), shape [n_mels, 1+n_fft/2]
std::vector<float> MelFilterbank(int n_mels, int n_fft, int sample_rate) {
  const int n_bins = 1 + n_fft / 2;
  std::vector<double> fft_freqs(n_bins);
  for (int i = 0; i < n_bins; ++i)
    fft_freqs[i] = (double)i * (sample_rate / 2.0) / (n_bins - 1);

  std::vector<double> mel_f(n_mels + 2);
  const double max_mel = HzToMel(sample_rate / 2.0);
  for (int i = 0; i < n_mels + 2; ++i)
    mel_f[i] = MelToHz(max_mel * i / (double)(n_mels + 1));

  std::vector<double> fdiff(n_mels + 1);
  for (int i = 0; i <= n_mels; ++i) fdiff[i] = mel_f[i + 1] - mel_f[i];

  std::vector<float> fb(n_mels * n_bins, 0.0f);
  for (int m = 0; m < n_mels; ++m) {
    for (int k = 0; k < n_bins; ++k) {
      double lower = (fft_freqs[k] - mel_f[m]) / fdiff[m];
      double upper = (mel_f[m + 2] - fft_freqs[k]) / fdiff[m + 1];
      double w = std::max(0.0, std::min(lower, upper));
      double enorm = 2.0 / (mel_f[m + 2] - mel_f[m]);  // slaney norm
      fb[m * n_bins + k] = (float)(w * enorm);
    }
  }
  return fb;
}

}  // namespace

std::vector<float> LoadAudio16kMono(const char* path) {
  // ffmpeg -> float32 little-endian, mono, 16k, stdout
  std::string cmd = "ffmpeg -nostdin -v error -i '";
  cmd += path;
  cmd += "' -f f32le -ac 1 -ar 16000 - 2>/dev/null";
  FILE* p = popen(cmd.c_str(), "r");
  std::vector<float> samples;
  if (!p) return samples;
  const size_t CHUNK = 1 << 16;
  std::vector<float> buf(CHUNK);
  size_t n;
  while ((n = std::fread(buf.data(), sizeof(float), buf.size(), p)) > 0)
    samples.insert(samples.end(), buf.begin(), buf.begin() + n);
  pclose(p);
  return samples;
}

MelConfig ReadMelConfig(const std::string& model_dir) {
  MelConfig c;
  c.n_mels = 128;
  c.n_fft = 400;
  c.hop = 160;
  c.sample_rate = 16000;
  c.n_frames = 3000;
  std::string json = ReadFileToString((model_dir + "/preprocessor_config.json").c_str());
  if (!json.empty()) {
    c.n_mels = FindInt(json, "feature_size", c.n_mels);
    c.n_fft = FindInt(json, "n_fft", c.n_fft);
    c.hop = FindInt(json, "hop_length", c.hop);
    c.sample_rate = FindInt(json, "sampling_rate", c.sample_rate);
    c.n_frames = FindInt(json, "nb_max_frames", c.n_frames);
  }
  if (const char* e = std::getenv("WHISPER_N_MELS")) c.n_mels = std::atoi(e);
  return c;
}

std::vector<float> LogMel(const std::vector<float>& audio, const MelConfig& cfg, int& out_frames) {
  const int n = (int)audio.size();
  const int pad = cfg.n_fft / 2;
  out_frames = 0;
  if (n <= 0) return {};

  // reflect pad
  std::vector<float> padded(n + 2 * pad);
  for (int i = 0; i < pad; ++i) padded[i] = audio[pad - i];
  std::memcpy(padded.data() + pad, audio.data(), sizeof(float) * n);
  for (int i = 0; i < pad; ++i) padded[pad + n + i] = audio[n - 2 - i];

  // periodic Hann window (torch.hann_window default)
  std::vector<float> win(cfg.n_fft);
  for (int i = 0; i < cfg.n_fft; ++i)
    win[i] = 0.5f * (1.0f - std::cos(2.0 * M_PI * i / cfg.n_fft));

  const int n_bins = 1 + cfg.n_fft / 2;
  int total_frames = 1 + (int)((padded.size() - cfg.n_fft) / cfg.hop);
  int frames = total_frames - 1;  // whisper drops the last frame
  if (frames <= 0) return {};

  std::vector<float> fb = MelFilterbank(cfg.n_mels, cfg.n_fft, cfg.sample_rate);

  float* in = fftwf_alloc_real(cfg.n_fft);
  fftwf_complex* out = fftwf_alloc_complex(n_bins);
  fftwf_plan plan = fftwf_plan_dft_r2c_1d(cfg.n_fft, in, out, FFTW_ESTIMATE);

  std::vector<float> mel(cfg.n_mels * frames, 0.0f);
  std::vector<float> power(n_bins);
  for (int t = 0; t < frames; ++t) {
    const int base = t * cfg.hop;
    for (int i = 0; i < cfg.n_fft; ++i) in[i] = padded[base + i] * win[i];
    fftwf_execute(plan);
    for (int k = 0; k < n_bins; ++k)
      power[k] = out[k][0] * out[k][0] + out[k][1] * out[k][1];
    for (int m = 0; m < cfg.n_mels; ++m) {
      const float* row = &fb[m * n_bins];
      float acc = 0.0f;
      for (int k = 0; k < n_bins; ++k) acc += row[k] * power[k];
      mel[m * frames + t] = acc;
    }
  }
  fftwf_destroy_plan(plan);
  fftwf_free(in);
  fftwf_free(out);

  // log10(clamp(1e-10)) -> clamp(max-8) -> (x+4)/4
  float mx = -1e30f;
  for (float& v : mel) {
    v = std::log10(std::max(v, 1e-10f));
    mx = std::max(mx, v);
  }
  const float floorv = mx - 8.0f;
  for (float& v : mel) v = (std::max(v, floorv) + 4.0f) / 4.0f;

  out_frames = frames;
  return mel;
}
