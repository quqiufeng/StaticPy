// whisper.h — C ABI around ctranslate2::models::Whisper for StaticPy FFI.
//
// 约定（见 StaticPy AGENTS.md §4）：
//   - 返回 const char*（静态字符串，Chez 会拷贝），永不返回 NULL
//   - 没有 void 返回
//   - 单线程调用（内部 mutex 串行化），模型实例故意不释放（CUDA teardown 问题）
//
// 依赖：libctranslate2.so（thirdparty/ctranslate2/lib）、fftw3f、ffmpeg（运行时解码音频）
//
// 环境变量：
//   WHISPER_MODEL_DIR  模型目录（默认 /data/models/faster-whisper-large-v3；日语自动用 kotoba）
//   WHISPER_DEVICE     设为 cpu 强制 CPU（默认 CUDA/FP16）
//   WHISPER_BEAM       束搜索宽度（默认 5；1=贪心，略快）
//   WHISPER_N_MELS     覆盖 mel 通道数
//   WHISPER_LANG       强制源语言（如 ja / zh / en），跳过自动检测
//   WHISPER_PROFILE    非空则打印分段耗时到 stderr
//   WHISPER_REPETITION_PENALTY / WHISPER_NO_REPEAT_NGRAM  抗复读
//   WHISPER_MAX_SEG_SEC  丢弃长于该秒数的段（整窗填充伪影），默认 15
//   WHISPER_VAD        设为 0 关闭 Silero VAD 语音门控（默认开）
//   WHISPER_VAD_MODEL  VAD 模型路径（默认 /data/models/silero-vad/silero_vad.onnx）
//   WHISPER_VAD_THRESHOLD  语音概率阈值，默认 0.5
//   WHISPER_VAD_MIN_SEC    段内最少语音秒数，低于此丢弃，默认 0.1
//
// 依赖 onnxruntime（Silero VAD）；无该库时自动编译为无 VAD 版本。
#ifndef MY_TRANS_WHISPER_H
#define MY_TRANS_WHISPER_H
#ifdef __cplusplus
extern "C" {
#endif

// 转写为纯文本（各段用 \n 连接）
const char* wh_transcribe(const char* audio_path);

// 检测语言（返回如 "en"），失败返回 ""
const char* wh_lang(const char* audio_path);

// 转写为 JSON：{"lang":"en","segments":[{"start":0.0,"end":2.5,"text":"..."}]}
const char* wh_transcribe_json(const char* audio_path);

// 转写并写成 ASS 双语/单语字幕（仓耳今楷02 字体）；返回段数，失败 -1
int wh_to_ass(const char* audio_path, const char* out_ass, double offset);

// 模型目录（默认 /data/models/faster-whisper-large-v3；日语自动用 kotoba，可用 WHISPER_MODEL_DIR 覆盖）
const char* wh_model_dir(void);

#ifdef __cplusplus
}
#endif
#endif
