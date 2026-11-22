# SPROF — Scheme 层热点：不认地址，认计数

> 上一轮（[HOTATTR.md](./HOTATTR.md)）把 `[anon]+0x1e000` 钻到了指令；
> 但**机器码里没有名字**：Chez AOT 的代码落在匿名可执行区，偏移每次运行还漂 ±0x2000。
> 换个判据——**让编译器自己数每个表达式执行了多少次**。次数就是坐标，不需要地址。

Chez 自带这条路（`compile-profile`）：编译期在每个表达式插计数器，
运行期把计数器 dump 出来。StaticPy 把它包成三步：

```bash
# ① 剖析构建（计数版产物，慢 2~5 倍，只用来采样）
STATICPY_PROFILE=source bash staticpy/static_build.sh app.static.py app

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
STATICPY_PROFILE=block bash staticpy/static_build.sh app.static.py app
./dist/app

# 第二轮：带着画像重编（编译驱动里会先 (profile-load-data ...)）
STATICPY_PROFILE=block STATICPY_PGO=1 bash staticpy/static_build.sh app.static.py app
```

约束（Chez 的硬要求）：**被重编的代码必须逐字一致**——源文件、插件、
`optimize-level` 都不能变，否则块对不上，编译器会抛异常。
所以 PGO 只能在"同一份源码"上迭代，改代码就重新采。

### 实测收益（imgproc `pil resize`，2026-11-20）

同一份源、同一张 2000×1500 → 900×600 lanczos，基线/PGO **交替各跑两轮**，
每轮 10~12 次取均值（单次计时只有 10ms 分辨率，必须先跑总量再除）：

| 轮次 | 基线（普通构建） | PGO 构建 | 差 |
|---|---|---|---|
| 1 | 269 ms/次 | 252 ms/次 | −17 ms |
| 2（换序，各 12 次） | 275 / 272 ms/次 | 250 / 250 ms/次 | −22~25 ms |

**≈ 降 8%（约 20 ms）**，且两轮换序复测一致，不是噪声。
正确性同一关：PGO 版与基线的输出 PNG **逐字节相同**（`cmp` 通过，
md5 一致）——画像只改指令排布，不改语义，这条要每次重编都验。

这个数和上表「Scheme 包装层 ≈ 19 ms」几乎相等，说明 **PGO 吃到的就是
包装层那点预算**：C 侧 191 ms 不动，剩下的分派/参数解析/运行时路径被
块计数重排后省掉大半。**PGO 是免费的（不改一行代码），但它不可能把
C 的 191 ms 变成 100 ms**——那得改 C。

## 真实目标实测（imgproc，2026-11-20）

拿真库练一次，把「计数」和「墙钟」摆在一起——顺便说明**计数 ≠ 时间**。

靶：`imgproc` 的 `pil` CLI，`resize` 一张 2000×1500 JPEG → 900×600 lanczos
（C 侧 `libimgproc.so` 干活），min-of-N。

| 分段 | 墙钟 | 怎么测的 |
|---|---|---|
| 纯 C（直连 `libimgproc.so`，跳过 Scheme） | **191 ms** | ctypes 调 open+resize+save |
| 纯启动（`pilprof` 无参即退） | **50 ms** | Chez boot + ELF 装载 |
| StaticPy ELF 全程 | **260 ms** | `pilprof resize …` |
| ⇒ Scheme 包装层 | **≈ 19 ms**（约全程 7%） | 260 − 50 − 191 |

计数侧（`STATICPY_PROFILE=source`，同一次运行）：

```
总计 1789 hits，其中 1549 (86.6%) 落在运行时（prelude/stdlib）
用户代码仅 240 hits (13.4%)：main 141 / a 67 / ai 27
最热语句：a() 的函数体 48 hits，img_save 调用 11 hits
```

**两条结论，别混着用：**

1. **86.6% 的计数在运行时，但运行时只花了 19ms。** prelude 表达式多且每句都廉价，
   计数被它们刷满；真正的墙钟在 C 里。**要抓时间用 `trace oncpu` / 墙钟对照，
   要抓"哪段代码跑得最多、改它能省几次调用"才用 sprof。**
2. 对这个 workload，**Scheme 层最多能省 19ms**（改 `a`/`ai` 的参数解析、削 main 的
   字符串分派链）。想快得更多只有两条路：改 C，或减少跨 FFI 次数。
   这也印证了 AGENTS.md 的判断——**wrapper 优化有天花板，先看清天花板再动手**。

复现（三段都在仓库里，无外部依赖）：

```bash
python3 -c "…"                                   # 造图 → ~/iso_gen/bench.jpg
STATICPY_PROFILE=source bash imgproc/build_app.sh imgproc/pil_cli.static.py pilprof
LD_LIBRARY_PATH=cpp/imgproc/build ./dist/pilprof resize ~/iso_gen/bench.jpg out.png 900 600 lanczos
./dist/sprof ~/iso_gen/prof/pilprof.prof --top=12
```

### 回调热点：`pil deform`（lambda 路径，2026-11-20）

`ImageOps.deform` 是唯一「每输出像素各调一次 lambda」的算子（`pil_ops_deform`：
`fnx(x,y)` / `fny(x,y)` 各一次，w×h 次）。它正好验证补丁 7 的**一等函数调用**
在 Scheme 侧是真热点，而非 Python 侧假象。

```bash
# 带计数的构建（产物名分开，避免覆盖交付版）
STATICPY_PROFILE=source bash staticpy/static_build.sh \
    ~/iso_gen/staticpy-cache/pil.bundle.static.py imgproc/pilprof imgproc/imgproc_ffi.scm
LD_LIBRARY_PATH=cpp/imgproc/build ./imgproc/pilprof deform mid.png out.png half
./dist/sprof ~/iso_gen/prof/pilprof.prof --top=15
```

128×128 一条 `deform half` 的实测（总计 1,151,949 hits）：

| hits | 占比 | 落点 |
|---|---|---|
| 789,663 | 68.5% | `pil_ops_deform`（`pil.bundle.static.py:108`），内层 `csv` 拼接 + 两次 lambda 调用（`:120`） |
| 131,386 | 11.4% | `main`（CLI 分派） |
| 230,827 | 20.0% | 运行时（prelude/stdlib，无 py 归属） |

结论：热点的 68.5% 集中在 `csv = csv + format_float(fnx(x, y), 4) + "," + ...`
——**字符串拼接 + 两个回调**。若后续要提速，该改的是这行的数据通路
（先攒数组再一次 join，或把坐标生成下推到 C 侧 `img_warp`），而不是 `img_warp` 本身。

> 注意：source 级计数开销极大。同一算子 512×512 在剖剖析构建下**跑不完**
> （52 万次回调），采样必须缩图；要测大图请用 `block` 模式或 `hotattr`。

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
