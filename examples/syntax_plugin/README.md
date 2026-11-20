# 语法扩展插件模板

核心语法已冻结，**新语法一律走插件**，不往 `staticpy/static_translate.py` 加规则。

## 目录

```
examples/syntax_plugin/
  plugin.json        清单：kind=syntax + syntax=hooks.py
  hooks.py           四个钩子（rewrite / expr / stmt / infer）
  demo.static.py     用例
```

## 跑

```bash
STATICPY_PLUGINS_PATH=$PWD/examples \
python3 staticpy/static_translate.py --plugins syntax_plugin \
        examples/syntax_plugin/demo.static.py

# 出 ELF（构建脚本认 STATICPY_PLUGINS）
STATICPY_PLUGINS=syntax_plugin STATICPY_PLUGINS_PATH=$PWD/examples \
bash staticpy/static_build_comfycli.sh examples/syntax_plugin/demo.static.py demo
./dist/demo
```

## 钩子

| 钩子 | 时机 | 返回 |
|---|---|---|
| `k.rewrite(fn)` | `ast.parse` 之前，`fn(code) -> code` | 新源码（**别改行数**，行号=报错定位） |
| `k.expr(NodeType, fn)` | `translate_expr` 开头，优先于内核规则 | Scheme 字符串；`None` = 交回内核 |
| `k.stmt(NodeType, fn)` | `translate_stmt` 与**顶层语句** | 同上 |
| `k.infer(fn)` | `infer_expr_type` 开头 | 类型名 `"int"/"float"/...`；`None` = 交回内核 |

回调签名 `fn(node, kernel)`；递归翻译子节点用 `kernel.api["translate_expr"]`，
**不要** `import static_translate`（循环 import）。

## 铁律

- 不认识的形状**必须 `return None`**——`dispatch_*` 按注册顺序遍历、命中即返回，抢了别人的节点会静默改语义。
- 插件只在**插件链路**生效；自举环 2（`selfhost/staticc.py`）不带插件，别在环 2 依赖它。
- `selfcheck.sh` 的 `[0b/4]` 会跑本模板，钩子坏掉当场红。
