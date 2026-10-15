# 示例：逆向 deform（波纹）——用 lambda 给每个输出像素算源坐标
from pil_lib import img_open, img_save, img_free, img_width, img_height, pil_ops_deform

def main():
    args = list_to_py_list(argv())
    im = img_open(py_list_ref(args, 1))
    out = pil_ops_deform(im, lambda x, y: x + 5, lambda x, y: y)
    img_save(out, py_list_ref(args, 2))
    img_free(im); img_free(out)
    print("deform ok")
