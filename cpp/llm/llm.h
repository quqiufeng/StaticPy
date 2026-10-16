// llm.h — Hunyuan-MT (llama.cpp OpenAI 兼容服务) 的 C ABI，供 StaticPy FFI
//
// 约定同 whisper.h：返回 const char*（静态串），永不 NULL，单线程，无 void 返回。
// 服务地址:- LLM_HOST (默认 http://127.0.0.1:8080/v1)
//         - LLM_MODEL (默认 hunyuan-mt)
#ifndef MY_TRANS_LLM_H
#define MY_TRANS_LLM_H
#ifdef __cplusplus
extern "C" {
#endif

// 翻译单条文本（target_name 如 "Chinese"），失败返回 ""
const char* llm_translate(const char* text, const char* target_name);

// 解析 in_ass 的 Dialogue 行，逐条翻译 target_lang(zh/en/ja/...)，写双语 out_ass
// 返回翻译条数，失败 -1
int llm_translate_ass(const char* in_ass, const char* out_ass, const char* target_lang);

// 当前服务地址
const char* llm_host(void);

#ifdef __cplusplus
}
#endif
#endif
