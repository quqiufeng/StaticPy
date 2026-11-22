# HOTATTR — 让 trace 里的 `[anon]+0x…` 变成"能改的那段代码"

`tools/hotattr.static.py`（StaticPy 自举工具，不是 Python 脚本）。

## 为什么需要它

StaticPy 的产物是「Chez AOT `.so` + 独立 ELF」。AOT 机器码落在**匿名可执行区**：

```
42895000-428d7000 rwxp            ← 没有路径名，perf 只能叫它 [anon]
```

`lite trace` 采到的用户态栈因此长这样——知道"20% 的时间花在 `[anon]+0xc1159`"，
却不知道那是哪个 Scheme 函数里的哪一行：

```
23.6%  [anon]+0x57119
16.9%  [anon]+0x57140
```

更麻烦的是：**这个偏移每次运行都漂移**（链接/分配顺序变，实测 `0xc4159 → 0xc2159`，
本例 `0x59000 → 0x56000`）。拿上一轮的偏移去下一轮翻代码，必然翻错地方。

`hotattr` 的策略：**不在两轮之间搬运坐标，而是在当次进程里给地址起名字**。
它只做两件事——读 `/proc/<pid>/maps`，写 `/tmp/perf-<pid>.map`
（perf 的 JIT 地址表格式：`起始地址 长度 名字`，engine 的 `perf_map()` 会读它）。

## 三段式

```bash
# 0. 目标进程先跑起来（要活到采样结束）
# 1. 粗标：整个代码区按 4K 切块命名
./dist/hotattr map $PID
lite trace/oncpu pid=$PID duration=2 sym=true      # → 100% A0_56000

# 2. 细标：只在该偏移 ±0x800 内按 64B 命名
./dist/hotattr drill $PID A0_56000                 # 也可以写 0x56000
lite trace/oncpu pid=$PID duration=2 sym=true      # → 50.7% A0_d_56140 / 49.3% A0_d_56100

# 3. 看机器码：dump 那段字节 + 给现成的反汇编命令
./dist/hotattr bytes $PID A0_d_56100 96
#   → 82 ba 05 00 00 49 8b 75 48 49 89 74 24 07 …
#   → objdump -D -b binary -m i386:x86-64 --adjust-vma=0x42815100 ~/iso_gen/hotattr-*.bin
```

第四个子命令用来**分辨真热点和漂移噪声**（多轮采集一起看）：

```bash
./dist/hotattr diff run1.json run2.json run3.json      # --gran=0x400 --top=20
# block              #0     #1     #2   anon%      Δ
# +0x2e800            0     64     61   41.2%     61
# +0xd5000           40      0      0    0.0%    -40
```

`anon%` 按最后一轮的匿名样本计，`Δ = 最后一轮 − 第一轮`：Δ 为正且逐轮上升的块才是
真热点；只在某一轮出现的多半是布局漂移或不同程序。

## 读表须知

| 现象 | 含义 / 下一步 |
|---|---|
| `A0_56000` 占 100% | 采样窗口内只有一个环在跑 → `drill` 收窄 |
| `A0_d_56100` + `A0_d_56140` 各占一半 | 典型 fixnum 循环体：比较+分支 与 累加 各一条 |
| 两轮热块偏移差 ±0x2000 | 那是漂移，不是代码变了；永远按"当次"的名字走 |
| 采样全是 `[anon]+0x…`（没有 `A0_*`） | `sym=true` 没传，或 map 文件写在了别的 pid 下 |
| `样本=0` | 进程在睡（sleep/等 IO）：换 CPU 密集的阶段再采 |

## 局限（别硬扛）

- `bytes` 读 `/proc/<pid>/mem`：别人的进程要权限（`sudo` 或 `ptrace_scope=0`）。
- perf map 只覆盖**匿名可执行区**。有路径名的 `.so`/ELF 本来就由 engine 的
  `elf_lookup()` 用 dynsym 符号化，不需要抢。
- 名字是**窗口内**的坐标：`drill` 换别的偏移就要重跑；每次 map/drill 都会**重写**整张表。
- 它只回答"哪段字节在跑"，不回答"该不该优化"。判据永远是：改完重编、重跑
  差分/微基准（`imgproc/difftest.py`、`~/iso_gen` 的 min-of-N 计时），热块消失才算数。

## 实测（Chez fixnum 循环，`s = s + i * 3`）

```
map   → 100%   A0_56000            （4K 块）
drill → 50.7%  A0_d_56140  / 49.3% A0_d_56100   （64B 块）
bytes → 49 83 6e 68 01 0f 84 …     （dec/je：fixnum 递减与分支）
```

三轮之间热块从 `0x59000` 漂到 `0x56000` —— 这正是"必须当次取名"的证据。

## 构建

```bash
bash staticpy/static_build_comfycli.sh tools/hotattr.static.py hotattr
./dist/hotattr                     # 打 usage
```

## 更省事的路径：产物自己报名字（perfmap 自报）

`hotattr` 是**外部**贴标签（按 4K/64B 切块，名字是坐标）。若你愿意重编一次产物，
可以让产物**运行期**把自己的每个顶层过程的 code entry 写进同一张表，名字就是函数名：

```bash
STATICPY_PERFMAP=1 ./dist/translator app.static.py > ~/iso_gen/app.code.scm
bash staticpy/static_build_comfycli.sh ~/iso_gen/app.code.scm app   # 构建期门禁
```

原理只有一条：Chez 的 `(environment-symbols (interaction-environment))` 在 AOT 产物里
**能枚举到全部顶层命名空间**（程序自己的 + 内联的 prelude），`top-level-value` 对未绑定名
抛普通条件（`guard` 兜得住），`(object->reference-address p)` 掩掉低 3 位就是 code entry。
于是**不需要任何名字表**：构建期不猜存在性，运行期枚举即可（translator 实测 399 → 2283 条）。

写给别的项目的同一段代码不在 StaticPy 里，而是 lite 的通用件
`lib/chez-perfmap.scm`（66 行，只依赖 Chez 自带过程）：

```scheme
(load "chez-perfmap.scm")
...  (main) ...
(chez-perfmap-publish!)     ; 必须放在最后：函数跑过一轮，首字才指向代码段
```

固有上限：只有**顶层过程**有名，lambda/内联展开的代码仍是 `[anon]`（translator 实测
`[jit]` 25.3% / `[anon]` 45.8%）；行级归因仍走 `STATICPY_PROFILE=source` + `dist/sprof`。
