# docs/PERF.md — 常数因子基准（编译时间 / 体积 / 冷启动 / FFI 往返）

> 本仓的性能判据一直是「**同机同时段交替 A/B、取中位**」。但那套流程每次都要手搓命令、
> 手抄数字：换个会话就重新来一遍，也**没人会发现「冷启动悄悄变慢」「产物悄悄变胖」**这类回归。
> `tools/bench.sh` 把这件事固定成六个阶段，输入**确定性生成**，任何机器上跑都可比。

## 1 怎么跑

```bash
bash tools/bench.sh                      # 全量，取 3 次中位（约 30 s）
bash tools/bench.sh --quick              # 单次取数（约 12 s，看趋势用）
bash tools/bench.sh --json ~/iso_gen/bench/base.json          # 存基线
bash tools/bench.sh --baseline ~/iso_gen/bench/base.json      # 与基线逐项比对
```

- 工作目录 `~/iso_gen/bench`（**禁 `/tmp`**，可用 `STATICPY_BENCH_WORK` 改）；
  缓存仍走 `STATICPY_CACHE`（默认 `~/iso_gen/staticpy-cache`）。
- 输入由 `tests/bench/gen_bench_input.py` 生成：`big` ≈ 1.03 MB / 2200 函数，
  `mid` ≈ 92 KB / 200 函数，`small` 是冷启动专用（只跑 1000 次循环）。
- 结论口径：**单次 ±5% 内是噪声**；要判收益必须 `REPS≥3` 的中位，并按文档里的办法交替 A/B。

## 2 六个阶段量什么

| 阶段 | 输入 | 量什么 | 为什么单独量 |
|---|---|---|---|
| `translate-seed` | big | `python3 staticpy/static_translate.py` 中位秒数 | 种子是信任链起爆点，它变慢同样算退步 |
| `translate-boot` | big | `dist/translator` 中位秒数 | 自举收益的唯一可复现证据（与上一行比值） |
| `build-aot` | mid | 冷缓存完整构建：翻译 + Chez 编译 + 链接 | 用户体感的「编译一次要多久」；**每回次先清该目标缓存**，否则量到的是缓存命中 |
| `size` | mid | 产物 `ELF + .so` 字节 | 部署是强分发（AGENTS §7.5），体积是分发成本 |
| `cold-start` | small | 起进程 + 跑完，中位毫秒 | AOT 的核心卖点；退化没人察觉就会悄悄吃光「比 Python 快」的优势 |
| `ffi` | `tests/bench/ffi_roundtrip.static.py` | 每次 `foreign-procedure` 往返的纳秒数 | FFI 是挂 C 生态的唯一通道，开销必须钉住 |

`ffi` 样本用 `extern fn sqrt(x: float) -> float from "m"`（`STATICPY_LIB_M=libm.so.6`
由脚本注入，免去机器相关路径），循环 `N=2000000` 次只做 `s = s + sqrt(2.0)`，
所以这个数**含循环与浮点加法**，是同构对比的「调用+最小上下文」成本，不是纯 `call` 指令开销。

## 3 当前基线（2026-11-22，Linux x86_64，6 核，REPS=3）

```
  translate-seed  3411 ms   （big 1.03 MB）
  translate-boot  1811 ms   （自举 ELF，= 0.53× 种子）
  build-aot        863 ms   （mid 92 KB，冷缓存：翻译 + Chez 编译 + 链接）
  size            ELF 15 KB + .so 1599 KB = 1615 KB
  cold-start        58 ms   （中位，9 次）
  ffi               36 ns/次（2000000 次往返）
```

读法：

- **自举值一半时间**是自举翻译器的存在理由（`0.53×`），但它不是「快两倍」的承诺——
  这只说明「自举 ELF 比 CPython 种子快 1.9×」这一个数字，换输入要重测。
- `build-aot` 的 863 ms 里大头是 Chez `compile-file`，不是我们的翻译器；
  改翻译器能否缩短它，要看这行有没有动（±5% 以上才算）。
- `cold-start` 58 ms 里包含 Chez boot + 加载运行时 `.so` + 程序本身；
  真正的用户程序通常远小于 58 ms 的固定成本——**要降只能降运行时加载**。
- `ffi` 36 ns 是「调用 + 浮点加 + 循环」，量级上说明 FFI 不构成瓶颈；
  若某天它跳到 100 ns+，先查是不是把 `foreign-procedure` 放进了热循环内的重复解析。

## 4 与其它工具的分工

| 工具 | 回答的问题 | 层级 |
|---|---|---|
| `tools/bench.sh` | **整体快不快**（端到端常数因子） | 进程 / 全流水线 |
| `STATICPY_PROFILE=source` + `dist/sprof` | **哪条 py 语句、哪个运行时函数热** | Scheme 语句级 |
| `perfprobe`（采样 IP → 符号） | **哪个 `.so`/符号热**、`[anon]` 占比 | 机器码级 |
| `trace`（lite 侧） | 动态探针、off-CPU、火焰图 | 内核/进程级 |
| `semantics_diff.py` / `check_*.sh` | **对不对**（IR/语义一致性） | 正确性门禁 |

性能数字只在**正确性门禁全绿**的前提下才有意义：先 `check_*.sh` + `semantics_diff.py`，
再 `bench.sh`，最后才谈百分比。

## 5 反模式

- ❌ 用 `bench.sh --quick` 的单次数字下结论 → ✅ `REPS≥3` 中位，且与基线同机同时段比。
- ❌ 拿 `build-aot` 的热缓存数字当构建成本（脚本已替你清该目标缓存，别自己绕过）。
- ❌ 为了「数字好看」改基准输入（`big`/`mid` 由生成器固定）→ 要换规模就新增一档，并保留旧档。
- ❌ 在共享缓存目录里删 `boot_*` 求「冷构建」→ 那只量到运行时重建，与本项无关。
