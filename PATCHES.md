# 编译器本地补丁清单（`staticpy/static_translate.py`）

`static_translate.py` = 上游 StaticPy 版本 **+ 下列本地补丁**。
升级上游时：覆盖 `static_prelude.scm`/`static_stdlib.scm` 可直接替换；
`static_translate.py` 覆盖后需**重放以下补丁**（对照 `diff` 定位）。

| # | 补丁 | 原因 |
|---|---|---|
| 1 | `is None` / `is not None` → `(eq? x #f)` | 上游未处理，会生成非法 `(None x y)` |
| 2 | `break` / `continue`（`call/cc` 实现） | 上游 while/for 只生成 `(let loop ...)`，无法提前退出 |
| 3 | 模块级变量进入 `module_env` 类型环境 | 上游只收 enum 常量，函数内引用模块变量被判 `undefined name` |
| 4 | 顶层 `AnnAssign`/`Assign`/`Expr` 语句翻译 | 上游丢弃顶层语句，bundle 头部会失效 |
| 5 | `float` 映射为 32 位 `float`（非 `double`） | C FFI 的 ABI 若是 32 位 float，用 double 会传垃圾值 |
| 6 | 类型收集递归进 `while`/`if`/`for`/`with` 体 | 上游只扫函数直层，控制流内的类型标注丢失 |
| 7 | **lambda 表达式 + 一等函数** | 语法不够兼容 Python：`lambda` 译成 `(lambda (args) body)`；函数值赋值记为 `fn`、参数名进 `CURRENT_PARAMS`，**调用不加 `static_` 前缀**（据此可实现 `Image.eval`/`deform` 等回调） |
| 8 | `generate_extern_ffi` 去硬编码路径 | 原表写死 xgboost/onnx/dgemm 绝对路径；改为 **soname + 环境变量 `STATICPY_LIB_<LIB>` 覆盖**，未知库默认 `lib<lib>.so` |

## 校验

```bash
# 语法/类型：翻译器自检
python3 staticpy/static_translate.py imgproc/mirror_gif.static.py | head
# 端到端：重建 + 回归
bash selfcheck.sh
```

## 相关新增的全局（供补丁 7 使用）

- `CURRENT_PARAMS`：当前作用域的参数名集合（调用时不加前缀）
- `TYPE_ENV[name] = "fn"`：函数值局部变量
