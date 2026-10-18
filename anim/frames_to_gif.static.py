# frames_to_gif.static.py — 帧序列 → 循环 GIF（StaticPy，编成 ELF）
#
# 用法:
#   frames_to_gif OUT.gif FPS f1.png f2.png ...
#     FPS: 帧率；delay = ceil(1000/fps) ms

extern fn img_set_delay(im: ptr, i: int, ms: int) -> int from "imgproc"
extern fn img_append_frame(a: ptr, b: ptr) -> ptr from "imgproc"


def ceil_div(a: int, b: int) -> int:
    q: int = 0
    t: int = a
    while t > 0:
        t = t - b
        q = q + 1
    return q


def main():
    args = list_to_py_list(argv())
    n: int = py_list_length(args)
    if n < 4:
        print("usage: frames_to_gif OUT.gif FPS f1.png f2.png ...")
        exit_program(1)
    out: str = py_list_ref(args, 1)
    fps: int = string_to_int(py_list_ref(args, 2))
    nframes: int = n - 3
    delay: int = ceil_div(1000, fps)

    gif = img_open(py_list_ref(args, 3))
    if gif is None:
        print("imgproc: cannot open first frame")
        exit_program(1)
    i: int = 1
    while i < nframes:
        f = img_open(py_list_ref(args, 3 + i))
        if f is not None:
            g2 = img_append_frame(gif, f)
            img_free(gif)
            img_free(f)
            gif = g2
        i = i + 1

    j: int = 0
    while j < nframes:
        img_set_delay(gif, j, delay)
        j = j + 1

    rc: int = img_save(gif, out)
    img_free(gif)
    if rc != 0:
        print("imgproc: save gif failed")
        exit_program(1)
    print("gif " + string_of_int(nframes) + " frames @" + string_of_int(fps) + "fps -> " + out)
