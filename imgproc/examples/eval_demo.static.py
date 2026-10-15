# 示例：Image.eval 等价——用 lambda 对每个像素做映射（这里是减半）
from pil_lib import img_open, img_save, img_free, pil_eval

def main():
    args = list_to_py_list(argv())
    im = img_open(py_list_ref(args, 1))
    out = pil_eval(im, lambda v: v // 2)
    img_save(out, py_list_ref(args, 2))
    img_free(im); img_free(out)
    print("eval ok")
