# whisper.static.py — StaticPy 前端：CT2 C++ Whisper 本地转写（自写 log-mel 前端）
# 用法:
#   whisper lang  IN.mp4                 检测语言（如 en/zh）
#   whisper text  IN.mp4                 转写纯文本
#   whisper json  IN.mp4                 转写 JSON（含分段时间戳）
#   whisper ass   IN.mp4 [OUT.ass] [off] 写成 ASS 字幕（仓耳今楷02）
#   whisper model                        打印当前模型目录
# 环境: WHISPER_MODEL_DIR / WHISPER_DEVICE(cpu) / WHISPER_N_MELS
extern fn wh_lang(path: str) -> str from "whisper"
extern fn wh_transcribe(path: str) -> str from "whisper"
extern fn wh_transcribe_json(path: str) -> str from "whisper"
extern fn wh_to_ass(path: str, out: str, offset: double) -> int from "whisper"
extern fn wh_model_dir() -> str from "whisper"


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 2:
        print("usage: whisper <lang|text|json|ass|model> IN [OUT.ass] [offset]")
        exit_program(1)
    op: str = py_list_ref(args, 1)
    if op == "model":
        print(wh_model_dir())
        return
    if n < 3:
        print("usage: whisper <lang|text|json|ass> IN [OUT.ass] [offset]")
        exit_program(1)
    inp: str = py_list_ref(args, 2)
    if op == "lang":
        print(wh_lang(inp))
    elif op == "text":
        print(wh_transcribe(inp))
    elif op == "json":
        print(wh_transcribe_json(inp))
    elif op == "ass":
        out: str = inp + ".ass"
        off: float = 0.0
        if n >= 4:
            out = py_list_ref(args, 3)
        if n >= 5:
            off = string_to_float(py_list_ref(args, 4))
        rc: int = wh_to_ass(inp, out, off)
        if rc < 0:
            print("ass failed")
            exit_program(1)
        print("wrote " + out + " (" + string_of_int(rc) + " lines)")
    else:
        print("unknown op: " + op)
        exit_program(1)
