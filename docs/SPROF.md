# SPROF — Scheme 层热点：不认地址，认计数

> 上一轮（[HOTATTR.md](./HOTATTR.md)）把 `[anon]+0x1e000` 钻到了指令；
> 但**机器码里没有名字**：Chez AOT 的代码落在匿名可执行区，偏移每次运行还漂 ±0x2000。
> 换个判据——**让编译器自己数每个表达式执行了多少次**。次数就是坐标，不需要地址。

Chez 自带这条路（`compile-profile`）：编译期在每个表达式插计数器，
运行期把计数器 dump 出来。StaticPy 把它包成三步：

```bash
# ① 剖析构建（计数版产物，慢 2~5 倍，只用来采样）
STATICPY_PROFILE=source bash staticpy/static_build_comfycli.sh app.static.py app

# ② 跑一次，计数自动落盘到 ~/iso_gen/prof/app.prof
./dist/app

# ③ 出报告（已并回 Python 源行）
./dist/sprof                 # 读 ~/iso_gen/prof/last.txt 指向的那份
./dist/sprof --top=15
```

## 报告怎么读

```
  函数级（按计入的表达式 hits 排序）
   hits      占比  函数
    7200020    99.8%  hot_loop  (/opt/StaticPy/dist/phtest.static.py:4)
       6030     0.0%  main  (/opt/StaticPy/dist/phtest.static.py:17)

  语句级（hits 最高的 py 行 = 最该改的那一行）
    7200006    99.8%  /opt/StaticPy/dist/phtest.static.py:7
             | while i < n:
```

- **hits 是执行次数，不是时间**。它回答"这条语句被走过多少遍"，
  用来定位环路热点：次数爆炸的那行，就是 Scheme IR 该改的地方。
- `占比` 以**有 Python 归属**的计数为分母；`落在运行时` 那部分
  （prelude/stdlib 的表达式，没有 `;; file:line` 注释）单独报一行。
- 语句级下面 `| ...` 那行是直接从你的 `.static.py` 抓的源码，
  省得去 merged.ss 里翻行号。

## 行号是怎么折回来的

`merged.ss` = prelude + stdlib + 你的程序，计数行号指向它。
翻译器在每条语句前写 `;; <你的.py>:<行号>`；`sprof` 顺着这些注释把
Scheme 行号折回 Python 行号，并把 `(define (static_foo ...))` 之后的语句
都记到 `foo` 名下（函数级汇总）。

merged.ss 在 `~/iso_gen/staticpy-cache/`，清缓存会丢；要长期留就
`STATICPY_CACHE_KEEP=200` 或先 `cp` 一份，再用 `--ss=路径` 指过去。

## PGO 闭环：把画像喂回编译器

`source` 给人看；`block` 给**编译器**看（基本块计数 → 冷块外提、寄存器分配）。
Chez 原生流程是 dump → load → 重编，StaticPy 接成两个开关：

```bash
# 第一轮：采画像（~ /iso_gen/prof/app.pd）
STATICPY_PROFILE=block bash staticpy/static_build_comfycli.sh app.static.py app
./dist/app

# 第二轮：带着画像重编（编译驱动里会先 (profile-load-data ...)）
STATICPY_PROFILE=block STATICPY_PGO=1 bash staticpy/static_build_comfycli.sh app.static.py app
```

约束（Chez 的硬要求）：**被重编的代码必须逐字一致**——源文件、插件、
`optimize-level` 都不能变，否则块对不上，编译器会抛异常。
所以 PGO 只能在"同一份源码"上迭代，改代码就重新采。

## 与 hotattr 的分工

| 想知道 | 用 |
|---|---|
| 哪个 **Scheme 函数/源行**被跑了多少遍（改 IR 的入口） | `sprof`（计数，零地址） |
| 某个热块**具体是哪几条机器指令**（看后端生成质量） | `hotattr`（perf + 地址切块） |
| 机器码总体分布、漂移后的偏移 | `trace oncpu` |

顺序一般是：`sprof` 定行 → 看翻译器给这行生成了什么 IR → 改前端/翻译器 →
`sprof` 复测（hits 应不变，墙钟下降）→ 还嫌慢再 `hotattr` 钻指令。

## 坑

- 剖析构建**不是**交付产物：计数开销大，交付用普通构建（不带 `STATICPY_PROFILE`）。
- 缓存按 `STATICPY_PROFILE` / `STATICPY_PGO` / `static_prof.scm` 一起算 hash，
  两种模式互不污染；但改源码仍会重编。
- `(static-prof-report)` 只在**非库模式**构建时拼进去（库没有入口，
  由上层程序自己决定何时 dump）。
- 计数在进程退出前落盘；崩溃就丢——要边跑边采就自己在程序里调
  `(static-prof-report)`。
