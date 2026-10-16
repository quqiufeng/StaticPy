// feat.h — 音频解码 + Whisper log-mel 前端
#ifndef MY_TRANS_FEAT_H
#define MY_TRANS_FEAT_H
#include <string>
#include <vector>

struct MelConfig {
  int n_mels;
  int n_fft;
  int hop;
  int sample_rate;
  int n_frames;
};

// 用 ffmpeg 解码任意音频/视频为 16k 单声道 float32
std::vector<float> LoadAudio16kMono(const char* path);

// 读取 preprocessor_config.json（缺省 large-v3：128 mel / 400 / 160 / 16000 / 3000）
MelConfig ReadMelConfig(const std::string& model_dir);

// 返回 [n_mels, out_frames] 行主序；out_frames 为真实帧数
std::vector<float> LogMel(const std::vector<float>& audio, const MelConfig& cfg, int& out_frames);

#endif
