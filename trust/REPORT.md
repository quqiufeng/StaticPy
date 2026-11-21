# 可信度报告（trust/REPORT）

> 本文只回答一个问题：**这个编译器，凭什么信？** 每一条主张都必须附一条可复现的命令，
> 没跑过的写"未证"。分级：**已证**（本仓一键可复现）／**部分**（只覆盖子集或有前提）／**未证**。

生成时间：2026-11-20。复现：`bash selfcheck.sh`；慢项 `TRUST_SLOW=1 TRUST_FIXPOINT=1 bash selfcheck.sh`。

---

## 0. 一句话结论

> **"自举成立"已证（含三阶段固定点）；"编译器输出可信"已证到 DDC 级别 —— 两份独立实现
> 在**全部 31 份语料**（含信任根本身）上产出 token 级相同 IR，**C2 能力未覆盖 0**。
> 仍未证的两件事：`.sp` 工具链二进制本身不可审计、两份实现并非完全独立作者。**
>
> **2026-11-20 修正**：此前报告的"7 个用例 C2 未覆盖"（lambda / 嵌套 def / `list` / `%`）
> **是假的**。根因不是 `staticc.sp` 缺语法，而是 `ddc.sh` 默认吃了一个**陈旧的预置二进制**
> （`spboot_self` 早于 `staticc.sp` 的修改时间），于是拿"新 C1 vs 旧 C2"比，把二进制落后
> 误报成"能力差"。改为**从源码现建 C2 并按 hash 绑定**后，gap 立刻归零。

---

## 1. 信任链与"到底信哪一字节"

```
staticc.sp（1653 行，人审计对象 = 信任根）
   ├─ 路径 A（种子）：static_translate.py(CPython+ast) 编 staticc.py → E0 → 编 staticc.sp → g1
   ├─ 路径 B（自举）：g1 → E1 → 编 staticc.sp → g2 → E2 → 编 staticc.sp → g3
   └─ 路径 C（异源）：C2(.sp 实现，源码现建) 编 staticc.sp → c2
```

已测：`g1 ≡ g2 ≡ g3`（token 级），且 `c1 ≡ c2`（token 级）。
**注意**：`g1` 与 `c1` 是同一份实现（`staticc.py`）的两种跑法，`c2` 是另一份实现（`staticc.sp`，经 `.sp` 工具链）。
三条路径对 `staticc.sp` 的 IR 完全一致 —— 这是本仓目前最强的证据。

字节数不同（g1/c1 66150 B vs g2/c2 65698 B）但 token 全同：差异只是换行/缩进风格。
判据用 `trust/normalize_scm.py`（正经 token 化，字符串里的 `;` 与空白不会被误折叠）。

---

## 2. 证据表

| # | 判据 | 覆盖什么 | 状态 | 命令 |
|---|---|---|---|---|
| E1 | 词法器差分（vs CPython `tokenize`） | 词法层与 CPython 一致 | 已证 | `bash staticpy/check_tokenize.sh <file>` |
| E2 | AST 形状差分（vs CPython `ast`） | 解析层与 CPython 一致 | 已证 | `bash staticpy/check_parse.sh <file>` |
| E3 | IR 逐字节差分（自举编译器 vs 冻结种子） | 环 2 自举不改语义 | 已证 | `bash staticpy/check_translate.sh` |
| E4 | 语义差分（CPython 跑 vs ELF 跑） | 产物行为一致 | 已证 | `python3 staticpy/semantics_diff.py` |
| E5 | **三阶段固定点** | 编译器复制自身稳定 | 已证 | `bash trust/fixpoint.sh` |
| E6 | **异源双编译 DDC** | 抗"自洽后门" | 部分（见 §4） | `bash trust/ddc.sh` |
| E7 | 算子级差分（Pillow/zlib/hashlib） | 真实程序的输出正确 | 已证（在各自覆盖内） | `python3 imgproc/difftest.py -v` 等 |
| E8 | 信任链清单 | 被信的文件没有悄悄漂移 | 已证 | `python3 trust/manifest.py --verify` |
| E9 | 单一真源一致性（`prelude ⇄ plugins`） | 生成物与插件切片同步 | 已证 | `python3 tools/split_plugins.py --check` |
| E10 | 原生面归因（C/C++ 源 + 依赖的系统 `.so`） | 手写/vendored 源码与 dlopen 的库都在账上，被换库即响 | 已证（哈希层） | `python3 trust/manifest.py --verify-libs` |
| **E11** | **后端替换演练**（坏的 Chez 编译出的产物） | **「可替换」是可复现事实**：谁喊、谁哑 | **已证（含负向核心结论）** | `bash trust/backend_drill.sh` |

### E5 实测（2026-11-20）

```
g1 66150 B  6d768543f45fbfd8   （种子产物）
g2 65698 B  bcb85087b53a145e
g3 65698 B  bcb85087b53a145e
固定点成立：g2 ≡ g3；附带 g1 ≡ g2
```

`g1 ≡ g2` 比"固定点"更强：不仅自举链收敛，**种子与自举编译器给出的 IR 也 token 全同**
（即环 2 的自举没有引入任何风格/语义漂移）。

**2026-11-21 复跑**（环 2 加了 class 成员分派之后）：三个产物字节数与哈希**与上表完全相同**
（g1 66150 B `6d768543f45fbfd8` / g2,g3 65698 B `bcb85087b53a145e`），
说明该改动对自举链本身是**语义惰性**的——只有源码里真的出现 `class` 时才走新分支，
未改变任何既有输入产出的 IR。（复现：`bash trust/fixpoint.sh`）

### E11 实测（2026-11-20，后端替换演练）

**下毒**：`CHEZ_SCHEME` 指向 wrapper，在真 Chez 编译前篡改 IR 两个字面量
（`"True"→"TruE"`、`"None"→"NonE"`）。产物**照常构建、照常运行、行为是错的**：

```
基线:   True None 3
下毒后: TruE NonE 3
```

| 判据 | 结果 | 为什么 |
|---|---|---|
| **E5 固定点** | **绿，哈希与基线一字不差**（`6d768543…` / `bcb85087…` / `bcb85087…`） | 固定点只问「能否稳定复制自己」；均匀下毒**恰恰是稳定的**。`fixpoint.sh` 头注释的警告在此得到实证 |
| **E3 IR 差分** | **红/绿取决于缓存** | 缓存里已有干净 boot → **绿**（`fail=0`）；空缓存让下毒后端建 boot → **红**（`fail=1`）。E3 比的是两份 **Python** 翻译器，本与后端无关 |
| **E4 语义差分** | **红（唯一硬报警）** | oracle 是 CPython，**不经过后端** |

**结论**：后端可替换性的唯一支撑是「存在一个不经过后端的参照物」（CPython / Pillow / zlib）。
E4/E7 不是补充判据，而是这条主张的地基；E5 对均匀下毒在**结构上**无能为力。

### E8 补强：证据装置自己也要在账上（2026-11-20，闭合缺口 9）

原先 `trust/` 下的判据脚本只有 4 个**手工登记**，`trust/` 目录在清单里的条目实测为 **0**——
偷改 `backend_drill.sh` 不会有任何报警。现在 `discover_harness()` 自动枚举
`trust/*.sh` 与 `trust/*.py`（已显式登记的不重复收），清单 **254 → 256 项**，
`trust/` 下 6 个脚本全部在账。

实测三种偷改，全部 `退出码=1`：

| 偷改目标 | 结果 |
|---|---|
| `trust/backend_drill.sh`（本次新增的证据脚本） | `[内容漂移] trust/backend_drill.sh  c3722e71… → 84838518…` |
| `trust/fixpoint.sh`（原先手工登记） | 退出码 1 |
| `trust/manifest.py`（**判据本体**） | 退出码 1 |

还原后 `信任链无漂移（256 项一致）`。要点：判据脚本是「约定」的一部分，
改判据与改实现同等严重，必须显式 `--write` 重签，并在提交信息里说明改了哪一环。

### E6 实测

```
DDC: IR 一致 25 / 负向拒绝 6 / 分叉 0 / C2 能力未覆盖 0
```

- **25 个正向用例**（含 `staticc.sp` 与 `staticc_split.sp` 自编译、`lambda`/闭包/嵌套 def/
  `list` 类型/`%`/示例 spark）→ 两份实现 IR token 全同。
- **6 个负向用例**（`*_err_*`）→ 两份实现都正确拒绝。
- **0 分叉**，**0 能力未覆盖**（31/31）。

### C2 来路必须与源码 hash 绑定

`ddc.sh` 现在默认**不用预置二进制**：用种子编 `staticc.py` → E0，E0 编 `staticc.sp` → `c2.scm`，
再 AOT 成 C2 ELF，并把 `sha256(staticc.sp)+sha256(staticc.py)` 写进 `c2.stamp`；
信任根一改，stamp 不匹配即自动重建。只有显式给 `SPSTATICC=` 才用外部二进制，
此时若其 mtime 早于 `staticc.sp` 会**大声警告**，且 gap>0 时以 `exit 3` 报"部分通过"，
不再把"覆盖不到"伪装成"通过"。

---

## 3. 为什么固定点**不能**单独算"可信"

固定点只证明 `C(C) ≡ C`：编译器能稳定复制自己。**Thompson 攻击**（"Reflections on Trusting
Trust"）正是构造一个自洽的后门 —— 它在编译自己时植入后门，编译别的程序时保持干净，于是
`sc1 ≡ sc2` 完美通过，而每一代都是被污染的。固定点是**必要条件，不是充分条件**。

出路是 DDC（Diverse Double-Compiling）：用**另一份独立实现**编同一个源，比对产物。
本仓过去只有"同源不同执行方式"的自比（selfcheck 的 `[4/4]`：`staticc.py` 由 CPython 跑
vs 由自己编译成 ELF 跑）——**同源自比挡不住 Thompson**，因为两份产物来自同一份代码。
`trust/ddc.sh` 补的正是这一环：C1 = `staticc.py`（Python 子集语法），C2 = `staticc.sp`
（S-表达式语法，另一份代码），异源互比。

---

### 本次一并修掉的真 bug（信任链自己漂移）

`trust/manifest.py` 一装上就抓到第一个真实漂移：`selfcheck.sh [0/4]` 长期红 ——
`plugins/ ⇄ staticpy/static_prelude.scm` 不同步。根因是提交 `b794a88`（"补齐位运算"）
改的是**生成物** `staticpy/static_prelude.scm`，而真源 `tools/seed/prelude.scm` 没动。

后果很严重：构建读生成物（绿的），但任何人按报错提示跑 `tools/split_plugins.py`
重新生成，位运算 6 个函数（`bitand/bitor/bitxor/lshift/rshift/Invert`）会**静默消失**，
且构建仍然成功 —— 直到运行时才炸。这就是"单一真源"主张假掉的样子。

已修：位运算块搬进 `tools/seed/prelude.scm` + 重新切分插件（生成物逐字节不变，
`git diff staticpy/static_prelude.scm` 为空），并加语义用例 `tests/semantics/bitops.static.py`
（含 `1<<70` 的 bignum 路径，与 CPython 逐行一致）钉死，防止再漂。

## 4. 诚实清单：还没证的东西

1. ~~**C2 的能力差**（7/31 用例）~~ → **已证伪（2026-11-20）**：那是陈旧二进制的假象，
   源码现建后 31/31 全覆盖。真正留下的教训是 **"被测对象必须证明自己由当前源码产出"**——
   DDC 已按 hash 绑定 C2 来路。同类风险仍在：任何"预置二进制 + 源码"的组合都可能悄悄错配。
2. **多样性的来源**。`staticc.sp` 据信是从 `staticc.py` 转写而来 —— 两位实现并非完全
   独立作者。共享的**设计误解**（两人都理解错同一个语义）DDC 抓不到，只有外部 oracle 能
   抓（E1/E2/E4 对 CPython 差分就是干这个的）。所以 DDC 与 oracle 差分**必须同时存在**。
3. **不可审计的二进制**：`~/iso_gen/spboot/spboot_self`（唯一一个）。
   **DDC 从不依赖它**：C2 从 `staticc.sp` 源码现建（种子 → `staticc.py` → E0 →
   `staticc.sp` → C2），链路全程可审计；`spboot_self` 只是产物，属"可选旁证"。
   2026-11-20 已按当前源码**重编**并绑定来路（`spboot_self.src` = 源 hash
   `33fa56a2b68015fb`），`run_sp_tests.sh` 27/27、`SPSTATICC=spboot_self bash trust/ddc.sh`
   25/25 零分叉。旧件已全部删除 —— 二进制是纯导出物，留它只会留下"重建不出来的字节"；
   该留的推导输入（源 hash + `c2_prev-<hash>.scm`）已落盘，随时可再生成。
   注意：重编解决的是**来路**，不是**可读性**——它仍是 4.3 MB 无 .sp 源可逐行读的 ELF，
   这一节的粗度不变。另外 `staticpy/spark` 曾并列于此，属**误记**：那是示例程序
   （`.spark` 矢量图 DSL → SVG）的产物，不在构建链上、且被 .gitignore，已从清单摘除。
4. **原生面已入账（E10）**。清单原只覆盖 Scheme/Python 层；`cpp/` 下 95 个手写
   C/C++、117 个 vendored 源（`cpp/thirdparty/stb`）以及 dlopen/DT_NEEDED 的 20 个系统
   `.so` 过去**不在账上**——那意味着"imgproc 的输出对不对"里有一半字节无人担保。
   现在它们都在 `trust/manifest.json` 里（soname→解析路径→sha256）：
   - `--verify` 覆盖仓库内文件（含 cpp/vendored），漂移退出码 1；
   - `--verify-libs` 只校验系统库：**装了就必须哈希一致**（`libgif`/`libwebp`/`libtiff`/
     `libfreetype`/`onnxruntime`… 按 pin 处理，不符即红）；没装算"本机没有"（可选依赖），
     不判漂移——所以换机器不会假红。
   - 平台 ABI（`libc`/`libm`/`libstdc++`/`ld-linux`…）只记账提示，升级是常态；
     `STRICT_LIBS=1` 才当错。
   闸门落在**构建**上：`imgproc/build.sh` 开编前先跑 `--verify-libs`，库被换就拒绝构建
   （`STATICPY_NO_LIB_GATE=1` 可临时绕过）。**未做**的是"运行时拒绝 load"：
   `load-shared-object` 在信任根里，为它塞一条哈希校验会改动被审计的那一小段，
   收益不抵代价——真要防运行期换库，走强分发包（`package.sh` 打包自带 `.so`）更实在。
5. **清单不是签名**。`trust/manifest.json` 是明文哈希，能被一起改。它防的是"悄悄漂移"，
   不防"恶意重构"。要防后者，得把清单哈希抄进提交信息 / 外部链（未做）。
6. **非确定性未系统探测**：固定点跑一次通过，但没有反复跑/换环境（locale、字典序、
   绝对路径、并行度）来验证确定性。

---

## 5. 复现

```bash
# 快（日常）
bash selfcheck.sh                                  # 含 manifest --verify + DDC
# 全（改信任根/发版前）
TRUST_FIXPOINT=1 bash selfcheck.sh                 # 再加三阶段固定点

# 单跑
bash trust/fixpoint.sh        # 固定点：g1/g2/g3 + token 级比对
bash trust/ddc.sh             # 异源双编译：两组实现逐文件互比
python3 trust/manifest.py --show     # 谁被信、多大、多少行、什么哈希
python3 trust/manifest.py --verify   # 漂移检测（CI 用，漂移退出码 1）
python3 trust/manifest.py --verify-libs  # 系统 .so 是否被换（含在 --verify 的 selfcheck 步骤里）
```

中间产物一律落 `~/iso_gen/trust/`（本仓禁止 `/tmp`，AGENTS.md §4）。

---

## 6. 下一步（按性价比排序）

1. 让 `spboot_self` 真正**可审计**：它现在来路已明确（由 `staticc.sp` 现建、
   hash 绑定），但仍是无 .sp 源可逐行读的 4.3 MB ELF。可行方向是把它从信任链上摘掉
   ——即让 C2 永远走"源码现建"，只在需要固定点比对时才生成二进制。
2. 补 C2 的 lambda / 嵌套 def / `list` 类型 → DDC 覆盖面从 18/31 → 接近全量。
3. 固定点跑 3 次 + 换 locale/工作目录，确认确定性（把"跑一次通过"变成"稳定通过"）。
4. 把 manifest 哈希写进提交信息（或 `trust/manifest.json.sig`），把"防漂移"升级成"防篡改"。
