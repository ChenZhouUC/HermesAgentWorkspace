# Hermes 升级 Playbook

> **用法**：在 Claude Code 会话中说一句 `阅读 ~/.hermes/hermes-update.md 按计划做`，agent 即按本 playbook 一条龙完成"升级内层官方源码 checkout + 回贴本地 patch + 依赖自愈 + 补丁回归修到全绿 + 对齐外层监管记录/文档 + playbook 自身增补/清理/修订自审"，中途不打断、不追问，**收尾零遗留**。
>
> 若用户说“本轮做一次深度 PATCH/toolchain 审计”“审计 PATCH 假绿”或同义表述，视为启用下文 **深度 toolchain 审计模式**：agent 无需用户重述历史背景，直接从 Git、PATCH 注册表、bundle、执行脚本、测试与运行态重建上下文；除非同一句同时明确要求更新 upstream，否则不得 fetch/pull，只审计当前 checkout。该请求同时授权在既有安全边界内修复发现的审计链缺口、补负向回归并同步 playbook；引入新依赖、扩大权限/外部副作用或 push 仍需单独授权。
>
> **权威来源分工**：`hermes-update.sh` 是升级执行与回放 gate 的权威，`patches/PATCHES.md` 是语义 PATCH 注册表的权威，`patches/local-patches.diff` 是工程内补丁的唯一物理回放包。三者必须闭环一致；本 playbook 用**发现规则 + 决策规则**驱动，不复制一份会过期的补丁清单。

---

## 持久化演进幂等与跨会话收敛

本 playbook 所说的幂等不是“同一版本重复执行后所有文件字节完全不变”，而是**持久化演进幂等**：Hermes upstream 会持续变化，但本地语义不变量、功能与安全边界不能因升级丢失。任何新的 AI 会话只依赖仓库与运行环境中的持久化状态，完整读取本 playbook 后，都能重建当前升级阶段，安全接管中断现场，对新的 upstream 重新求解“上游已经提供什么、本地还必须补什么”，并按同一决策规则自主收敛；不得依赖上一轮对话记忆、临时推理、人工逐轮指挥或某个 agent 私有的补丁清单。

这里必须同时满足两层不同的幂等，不能混为一谈：

- **单次事务幂等**：一次用户明确发起的升级只允许建立一个官方 acquisition 结果。首次 `--update` 获取成功后立刻把目标 commit 固定为 `TARGET_SHA`；同一任务中的冲突修复、脚本修订、回归重跑和跨会话接管只能使用 `--reconcile`，不得再次 fetch/pull、不得因 `origin/main` 后续前进而移动本轮目标。唯一恢复例外是 acquisition 进程在**尚未取得任何 SHA**时失败，事务显示 `phase=acquiring / target_sha=pending`：此时按脚本提示恰好再用一次 `--update` 接管同一事务、完成尚未建立的 acquisition；这不是第二个 target，也不能在已有 target 后使用。失败或中断时，`~/.hermes/.hermes-update-transaction` 以 `0600` 保存阶段、旧 HEAD、固定目标和运行态脏标记；每次原子写、权限收敛或 rename 失败都必须使当前操作非零，不能继续使用旧状态。`--update`、`--reconcile` 与 `--final-audit` 共用同一事务锁，任何并发入口拿不到锁都应停止；只有整支 reconcile/update exit 0 才删除事务。已有 target 时误传 `--update` 必须自动复用它而不是开启第二次获取。
- **跨事务演进幂等**：本轮完整成功、事务状态清除后，下一次用户明确发起的新升级才允许重新读取新的 `origin/main`，并基于新的 upstream 重算最小剩余 patch 集。新 upstream 属于下一次事务，不能在当前事务的“最终验证”里顺手纳入。

每次升级都应视为下面这个持续迁移，而不是把旧 diff 机械贴到新代码上：

```text
旧 upstream + 已登记的本地语义不变量
    → 读取新 upstream 的实现与测试
    → 对每个 PATCH 判定：未吸收 / 部分吸收 / 完全吸收
    → 新 upstream + 最小剩余本地 patch 集 + 对齐后的验证与监管状态
```

- **状态可重建**：每轮从外层/内层 Git 状态、事务文件中的固定 `TARGET_SHA`（如存在）、bundle/base、PATCH 注册表、执行 gate、日志和当前运行态重新发现事实；“上次报告已完成”不能替代现场检查。事务存续时 `origin/main` 只是一条可能继续前进的远端引用，不是本轮目标权威。
- **动作可重入**：已完成步骤允许再次执行；脚本必须保护非 patch 用户改动、失败时恢复或保留可接管现场，agent 按实际状态跳过、重试或修复，不能靠固定步骤编号猜测进度。重入默认执行 `--reconcile`，只在没有未完成事务且用户明确开始下一次升级时执行一次 `--update`。
- **本地不变量跨版本保持**：不能以“上游升级了”或“旧 hunk 贴不上”为理由静默丢弃本地功能。未被上游吸收的 PATCH 必须适配新接口后重新打入；冲突由 AI 按语义解决，并以行为测试证明不变量仍成立。
- **PATCH 集合随上游进化**：每轮必须逐个读取活跃 PATCH 的 `上游吸收判断`，不能用 apply 成功或 sentinel 通过代替吸收判定。未吸收的继续保留；部分吸收的删除冗余 hunk、收缩四段定义与验证；完全吸收的先在裸 upstream 证明等价行为和测试，再删除本地 hunk 并移动到 Archive。目标是维护**最小剩余 patch 集**，既不漏补丁，也不永久背负已被上游替代的实现。
- **结果可收敛**：本轮 `TARGET_SHA` 一经取得即不可变；重复 reconcile 可以更新审计时间、日志、Gateway PID 或可再生依赖状态，但终态必须重新满足 Step 2c、Step 3、Step 5（含运行态闭环）和 Step 8e 的全部不变量。相同的“固定 TARGET_SHA + 本地语义不变量”应收敛到等价的最小 patch 状态，而不取决于由哪个 AI、从哪次中断开始执行；期间 upstream 新增提交不属于本轮输入。
- **运行态可证明**：磁盘 patch 正确不等于当前进程已加载。升级和任何后续运行时代码/配置修复都必须经过排空感知的 planned restart，以 `old PID → different new PID`、新 PID 下的 plugin verifier 和最终 status 作为终态证据；禁止用会在短固定宽限后强杀在途任务的 `gateway stop && gateway start` 充当常规重载，也禁止在运行态闭环之后继续修改运行时输入而不重新闭环。
- **经验要落盘**：发现新的上游冲突、依赖摩擦、恢复路径或完成标准缺口时，必须在当轮按责任边界同步到执行脚本、PATCH 注册表、replay bundle、playbook 摩擦表或对应文档。只写在会话总结里等同于未修复；下一轮 AI 必须能仅凭仓库文件复现该判断。
- **权威源不分叉**：执行行为写进 `hermes-update.sh`，PATCH 生命周期写进 `PATCHES.md`，工程内物理改动写进 bundle，决策与恢复规则写进本 playbook。不得为一次升级另建会过期的平行清单，也不得把普通审计噪音误登记为语义 PATCH。
- **默认自主完成**：上述吸收判定、冲突适配、patch 新增/合并/归档、依赖自愈、测试修复和文档对齐都属于升级流程本身，按本 playbook 的既定边界自主完成，不要求用户每轮人工介入。只有引入全新依赖、改变安全边界或遇到本地不可修的外部阻塞时，才按文末行为约束留案。

因此，持久化演进幂等的验收不是内容指纹零变化，而是：“换一个没有会话记忆的 AI，面对任意后继 upstream，只从当前磁盘状态和本文件出发，仍能保住所有尚未被上游吸收的本地不变量，移除已经等价吸收的本地实现，并通过同一组闭环验证。”

---

## 仓库模型与目标

本目录有两个职责不同的 Git 仓库，升级时必须分开判断：

- `~/.hermes`：用户的 Hermes 配置备份仓库。它监管 `hermes-update.sh`、`patches/local-patches.diff`、`patches/PATCHES.md`、`config.yaml`、`plugins/`、`my-skills/`、README/wiki 等升级记录；**升级完成后只在这个外层仓库提交**。其中 `PATCH-FEISHU-GROUP-SANDBOX` 这类用户插件安全补丁不进入内层 unified diff，而由外层 Git + Step 8e 强制 verifier 监管。
- `~/.hermes/hermes-agent`：官方 `NousResearch/hermes-agent` 源码 checkout。升级目标在这里；本地 patch 以 modified files 形式应用在这里，但**不要在这个内层仓库提交**，除非用户另行明确要求维护 fork。

默认升级来源是 `~/.hermes/hermes-agent` 的官方 `origin/main`。新事务的唯一一次 `--update` 先用 scoped fetch 把当时最新 main 写入专用事务 ref 并原子固定为 `TARGET_SHA`，随后让官方 updater 在临时 Git 代理下只消费这个 SHA：其内置 `fetch origin main` 被置为 no-op，所有 `origin/main` 比较/merge 被替换为固定 SHA，因此整轮网络获取仍然只有一次。此后即使远端 main 继续前进，本轮也只围绕这个 SHA 收敛。如用户明确要求稳定 release/tag，不要把它混同于默认流程：先记录目标 tag/branch，并确认 `hermes-update.sh`/patch 回贴流程是否支持该目标后再执行。

### Peer machine 能力层迁移边界

peer machine 部署不是把来源 `~/.hermes` 克隆成相同机器，而是把可复用能力迁入另一份独立状态。完整操作步骤以 `README.md` 的“整机迁移”章节为权威；本 playbook 只固定与升级、自演进和终态证据有关的不变量：

- 禁止用整目录 `rsync --delete` 覆盖已有目标目录；来源 `.env`、整目录 credentials、SOUL、memory、sessions、数据库、cron live store、cache/log、PID/lock、LaunchAgent、venv/node_modules 和机器二进制默认不迁移。
- replay bundle、PATCH 注册表、updater、用户插件实现/verifier、自定义 skills、受管脚本、wiki 与通用文档属于能力层；目标机自己的 `config.yaml`、插件配置、people/groups 和身份文件采用字段级合并，不能用来源文件整体替换。
- owner 身份只在目标配置中声明：`feishu.assistant_user_ids` 是人员同步置顶 owner 的机器级来源，sandbox owner DM、删除授权、可选 MCP 授信与 groups allowlist 必须同步复核；不得在共享脚本或 verifier 中硬编码来源机器 ID。
- 可选 MCP 未部署时必须同时移除 server、platform toolset、群工具和 trust lists。`people.yaml` / `groups.yaml` 只证明被授权对象存在，显式 trust lists 才是权限权威；新增或扩大授权必须在 Git diff 中人工审查。
- 目标机必须独立固定/取得所需 upstream SHA、重建运行环境并执行 no-network `--reconcile` 与 `--final-audit --json`；来源机器或另一 peer 的测试、Gateway PID、runtime trace 和 final-audit JSON 不能作为目标机证据。
- 若迁移过程暴露新的配置形态、身份耦合、可选组件或验证缺口，按 Step 5c 在当轮同步修改对应权威文件；只写迁移日志不构成自演进完成。

### 补丁模型（本轮重构后的固定边界）

- **语义层**：每个 `PATCH-<DOMAIN>-<INVARIANT>` 是独立的问题、回滚、验证和上游吸收单元；语义定义只在 `PATCHES.md` 出现一次。
- **物理层**：所有工程内源码补丁合并存放在一个 `local-patches.diff`。这是有意设计：多个语义补丁会共享同一文件，强拆物理 diff 会制造 hunk 顺序依赖；不能因为物理上只有一个 bundle 就把逻辑补丁合并成一个生命周期。
- **外层插件层**：`PATCH-FEISHU-GROUP-SANDBOX` 等配置仓库补丁由外层 Git 和独立 `verify.sh` 监管，不得进入内层 `PATCHED_FILES` 或 replay bundle。
- **运行时层**：`PATCH-NPM-DEPENDENCY-HYGIENE`、`PATCH-REPLAY-BUNDLE-FULL-INDEX`、`PATCH-UPDATE-GATE-EXIT-STATUS`、`PATCH-UPDATE-TRANSACTION-PIN`、`PATCH-SKILLS-MIRROR-METADATA`、`PATCH-GATEWAY-RESTART-CLEANUP` 等升级期策略由 `hermes-update.sh` 对应步骤重建，不以源码 hunk 或 Step 8b gate 表示。
- **归档层**：上游已吸收的补丁移入 Archive；如仍保留回归 sentinel，该 sentinel 与本地源码 hunk 是两回事，不能因此继续把补丁算作活跃。归档 sentinel 本身也有生命周期：当上游自带回归（已在 Step 2c 规范套件内运行）覆盖同一行为并稳定通过后，应在 Step 5c 清理中从脚本退役该 sentinel，并在 Archive 块记录退役日期与依据——归档层不无限累积，脚本体量受补丁生命周期约束。

---

## Agent 执行流程（一次跑完）

### Step 1 — 状态快照

记录以下用于后续摘要：

- `cd ~/.hermes/hermes-agent && git rev-parse HEAD` → 当前内层源码 `HEAD`（记为 `OLD_SHA`）。**这里禁止先跑 `git fetch`、`hermes update --check` 或会触发 update-check 的 `hermes --version`**；本轮唯一官方仓库获取必须留给 Step 2 的显式 `--update`
- `bash ~/.hermes/hermes-update.sh --transaction-status` → 若存在未完成事务，记录其中的阶段与固定 `TARGET_SHA`，本轮直接接管，不得另开获取
- 从 `hermes-agent/hermes_cli/__init__.py` 读取 `__version__` / `__release_date__` → 仅作安装展示摘要。不要在事务快照里调用 `hermes --version`，其 update-check 可能自行 fetch，破坏“官方仓库只获取一次”的边界
- `hermes doctor` 头部摘要
- `hermes gateway status` → 当前 PID + launchd 监管状态；若输出包含 LastExitStatus 一并记录
- `cd ~/.hermes && git status` → 外层配置备份仓库状态，区分"升级相关监管文件"和"用户在编辑的其他东西"
- `cd ~/.hermes/hermes-agent && git status -sb` → 内层官方源码仓库状态，区分"本地 patch modified files"和"非 patch 的用户改动"
- `python3 ~/.hermes/scripts/cleanup_transient_artifacts.py --dry-run --json --fail-on-review` → 输出 outer/inner 全部运维脚本与 ignored 路径的 `keep/remove/review` 分类；任何 policy error 或 review 项先按 `cleanup_policy.json` 归类，不得直接删除或进入 restart
- 当天日期（记为 `OLD_DATE` 用于 grep；本次升级新日期记为 `NEW_DATE`）

如果用户明确要求“更新到最新”，不要在 Step 1 预判远端是否有新提交；直接把唯一发现机会交给 Step 2 的 `--update`。如果用户只要求对当前 checkout 做 patch 审计/收敛，则使用 `--reconcile`，其目标固定为现有 HEAD 且绝不访问 origin。完全只读且运行态输入未变化时不为制造新 PID 而重启；如果接管中断现场后无法证明当前 PID 晚于最后一次运行态修改，则按 Step 5b 执行终态运行屏障。不要因为 `hermes --version` 显示 `Up to date` 就跳过本地闭环检查。

### Step 2 — 跑升级脚本

```bash
bash ~/.hermes/hermes-update.sh --update
```

`--update` 是唯一允许接触官方仓库的入口。正常情况在同一次用户升级任务中只显式调用一次：若没有未完成事务，就执行 scoped fetch、立即固定 commit，再运行被 SHA 约束且禁止网络 fetch 的官方 updater。若首次 acquisition 在拿到任何 SHA 前失败，`--transaction-status` 会显示 `target_sha=pending`，脚本会明确要求**一次**恢复性 `--update`；它只补完同一 acquisition。已有 target 后即使再次传 `--update` 也只能复用固定目标，不会二次 fetch/pull。除此之外默认无参数与 `--reconcile` 等价，只围绕事务 `TARGET_SHA`（无事务时为当前 HEAD）重跑本地 patch、依赖修复、gate、镜像、verifier 和健康闭环。

日志可使用 background + tee，但**任何管道都必须由启用 `pipefail` 的 shell 执行**，并以该 shell 或 `wait` 的退出码为准；`tee` 成功不代表升级成功。等待预算和所有数量均从只读入口或最终 JSON 动态读取，不在 playbook 长期正文复制当前值：

```bash
bash ~/.hermes/hermes-update.sh --print-restart-wait-seconds
bash ~/.hermes/hermes-update.sh --print-patched-files
bash ~/.hermes/hermes-update.sh --print-patched-tests
```

Preflight 的 `--self-test-patch-evidence` 是 **quick 模式**：它校验四段结构与 gate ownership，并按统一 probe registry 自动轮询所有 quick-eligible 的 runtime/dedicated/archive 探针；依赖终态 overlay 的 bundle parity 与外部 runtime verifier 明确标为 `deferred_full`。输出必须带 `"mode": "quick"`，不得作为最终行为回归，也**不得在 Step 2 捕获现场之前要求 live overlay 与旧 canonical bundle 逐字节一致**——手工解冲突后的 overlay 必然暂时领先于 bundle，这条 parity 只在 Step 2/8c 和 full/final audit 执行。完整证据由 `~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/scripts/test_patch_evidence.py --report-json <path>` 生成；不要假设系统 `python3` 已安装 PyYAML/pytest。每个 active 工程 PATCH 的完整 node ID 必须精确绑定 path/class/function；裸函数名仅在全局唯一时允许解析，节点文件必须出现在该 PATCH 的 `文件` 清单，并在隔离环境中通过 JUnit 证明 outcome 为 passed；同一个 node 不得被多个 PATCH 共用，以免相邻补丁借绿。每个可执行 `test_*.py` 必须至少 collect 一个 node，不能由其他文件的测试总数掩盖零收集；`conftest.py` / helper 等 support module 从 runnable 计数中剥离，继续保留在 bundle/ownership 并做 Python 语法检查。full 模式还用标准库调用轨迹记录每个 node 实际执行的仓库文件：凡声明拥有 Python 生产代码的 PATCH，证据节点必须逐个触达全部 owned production `.py`，不能只命中其中一个就整块放行；仅拥有测试文件的 hermetic/portability PATCH 才免除此项。runtime/dedicated/archive/external PATCH 的分类、结构契约和 callable probe 三套 key 必须闭合，Step 8e verifier 数组还必须与 external registry 路径全集相等；审计器从注册表逐项调用并写入 `probe_results`，缺失、重复、未知或未在本轮执行的 probe 不能生成 passed。Archive/dedicated pytest 探针统一使用 credential-free 环境、`xfail_strict=true` 与 JUnit，零执行、skip、xfail、xpass、error 或 failure 均阻断；Archive upstream overlap 直接按定义中的声明路径计算，不依赖该路径是否仍在当前 `PATCHED_FILES`。因需求退役项只证明旧 capability/resolver/config-key surface 未复活，names-only 检查不得读取 secret 值，也不得硬编码当前生产 provider/model。isolated bundle/mirror/trace/JUnit 临时目录必须自动回收。

Step 8b sentinel 只证明关键实现锚点存在，Step 2c canonical runner 证明完整文件行为，PATCH evidence 证明逐 PATCH 精确 node outcome；三者互不替代。full evidence 的 ownership 只认 `文件` 段反引号中的完整路径，不做子串推断；每个 active engineering/dedicated PATCH 必须至少拥有一个 `PATCHED_FILES` 路径。各 PATCH 的 node 在独立 pytest 进程中执行，调用轨迹忽略纯 `<module>` import，避免相邻 PATCH 的后台线程或仅导入模块替未执行行为借绿。所有 patch、gate、执行/审计脚本与 playbook 共演进修改结束后，先完成最终 `--reconcile`，再由 Step 5d 的单一 `--final-audit --json` 给出终态权威。**不要 source `hermes-update.sh`**；忙时段升级要接受动态排空预算，不得强杀在途任务。

**收敛循环**：apply 失败、gate 失败或任何修复之后，都必须运行 `bash ~/.hermes/hermes-update.sh --reconcile`，直到一次完整本地收敛运行 exit 0 且无 `✗`；**禁止为收尾证据再次运行新的 `--update`**。逐项人工验证（定向测试、手动重启、单独跑 verifier）可以用于定位问题，但不能替代 reconcile 闸门作为收尾证据——8b 哨兵与实现的漂移只有跑脚本才会暴露（2026-08-03 实例：`_with_current_author_prefix` 哨兵在一轮"定向测试 + 手动重启"收尾后失效 14 小时无人发现）。脚本失败/中断时保留事务文件；reconcile 成功退出后才自动删除。此后本任务若又发现本地问题，继续用 `--reconcile`（它会重新以当前 HEAD 建立无网络本地事务），仍不得更新 upstream。

退出码 0 不代表完美。**通读输出**，特别关注：

- 各 PATCH 结构化 sentinel / smoke gate 是否 OK（行为正确性另以 Step 2c 为准）
- Step 8d 在事务 `runtime_dirty=1` 时是否走 `hermes gateway restart` 的排空路径并明确报告 Gateway `old PID → new PID`；相同 PID、无新 PID 或回退到短宽限强杀都不得作为 patched modules active。无变化 reconcile 应明确报告跳过重启
- Step 8e 的每个用户插件 verifier 是否存在、可执行且返回 0；任一失败都必须使整次升级返回非零
- Skills mirror 的 `+/~/-` 数字
- 任何 `⚠` 或 `✗` 行
- `Recommended actions:` 区
- `uv` 是否走了 `--python venv/bin/python` fallback（频繁触发，正常自愈，记下次数即可）

脚本结束后从 `cd ~/.hermes/hermes-agent && git rev-parse HEAD` 取新的实际源码 `HEAD`，记为 `NEW_SHA`；它必须等于本轮日志固定的 `TARGET_SHA`。版本展示值只从 checkout 内 `hermes_cli/__init__.py` 读取，不作为 SHA 权威来源。

### Step 2b — 依赖自愈（常设授权，不追问）

升级可能重建/漂移 venv 与 node_modules（见摩擦表 runtime repair row）。每轮固定检查并自动修复，目标是**恢复升级前既有能力**，在跑回归前完成：

- 升级日志出现 venv 重建 / runtime repair 时：对比旧 venv（`venv.stale.*/bin/python -m pip list --format=freeze`）与新 venv 包清单。版本回到 uv.lock pin 的**回锁差异不动**；整包丢失的按序回装——① 补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"`（拿补丁态依赖元组，补回 PATCH pin 的 python-socks / pypdf 等）；② dev 工具链按 pyproject `[dev]` extra 的 pin；③ 其余按旧 venv 精确 pin `uv pip install --python venv/bin/python <pkg>==<ver>`。
- `hermes doctor` 报 npm 声明依赖缺失（如 agent-browser）→ 仓库根 `npm install`。
- **授权边界**：恢复"此前已存在"的包/工具属**用户常设授权**（2026-07-25 起），直接执行不追问；引入旧环境从未有过的**全新**依赖不在授权内，留报告等用户。
- 环境残留清理：误建的 `.venv`（uv 默认项目环境，会让 `uv run` 跑错解释器）直接删除；`venv.stale.*` 用 `lsof +D` 确认无进程占用后删除，有占用则报告待删。
- 依赖恢复完成后重新运行 `bash ~/.hermes/plugins/sandbox/verify.sh`（以及 Step 8e 登记的其他 verifier）。这一步不能省：若 Step 8e 先前仅因 venv 重建丢失 pytest 而失败，恢复依赖后必须重新证明 `PATCH-FEISHU-GROUP-SANDBOX` 的 YAML、toolset、行为测试和 runtime trace 全绿；runtime trace 必须绑定 `hermes gateway status` 返回的**当前 PID**，不能用任意一条历史注册日志代替。
- 处置结果写进升级摘要与摩擦表。

### Step 2c — 补丁功能回归（终态必须 0 failed）

patch 回贴 + 依赖自愈后，用脚本权威数组动态运行全部 `tests/**`（包含测试 helper，文件数也必须与摘要一致）：

```bash
bash -lc '
patch_tests=()
while IFS= read -r file; do patch_tests+=("$file"); done \
  < <(bash "$HOME/.hermes/hermes-update.sh" --print-patched-tests)
cd "$HOME/.hermes/hermes-agent"
./scripts/run_tests.sh --file-retries 0 "${patch_tests[@]}" -- \
  -W error::pytest.PytestUnhandledThreadExceptionWarning \
  -W error::pytest.PytestUnraisableExceptionWarning \
  -W error::RuntimeWarning \
  -W error::pytest.PytestReturnNotNoneWarning \
  -W error::pytest.PytestCollectionWarning
'
```

测试文件清单与上轮外层提交中的 `hermes-update.sh` 对比，passed 数与 `PATCHES.md` § 当前版本摘要对比。禁止直接调用 `pytest`；runner 会隔离 HOME/凭据、固定时区/locale，并逐测试文件放进独立子进程，结果才与 Hermes CI 口径一致。PATCH 终态显式使用 `--file-retries 0`，并把 unhandled-thread、unraisable、`RuntimeWarning`、test-return-value 与 collection warning 五类执行完整性信号提升为错误：普通开发套件可以把 pass-on-retry 标成 FLAKY 供定位，但升级验收不得让首轮失败被自动重跑洗绿，也不得把测试线程、对象终结器、未 await coroutine、返回值伪断言或部分未收集测试留作 warning 后仍计为 passed。**回归终态 0 failed 是必要条件，不是充分条件**：passed 数只是遥测，数量下降、测试文件消失、collection 异常或关键用例被改名/跳过都必须逐项解释，不能拿“仍然 0 failed”掩盖覆盖面退化。出现新失败先定性、再按分支当轮修到转绿，不留遗留：

1. **环境缺口**（依赖缺失 / 解释器变化）→ 回到 Step 2b 补装后复跑；
2. **上游自身 bug**（`git stash push -- <相关源文件+测试>` 后在裸上游复跑同样失败）：影响本部署行为或本回归套件的，**本地补丁修复**——按 Step 4 的补丁归并原则决定并入现有语义 PATCH 还是新增语义 PATCH，同步 sentinel / PATCHED_FILES / PATCHES.md / 快照，修到转绿；确实不影响本部署行为且测试不在本套件内的，才允许只记摩擦表；
3. **补丁真回归**（仅打补丁后失败）→ 修补丁本身。

凡是由真实平台事件暴露的缺陷，新增回归必须落在**最高有效边界**：至少用平台真实 payload 形状穿过完整 adapter 入站路由，并断言最终 Gateway event / provider request / 出站消息中真正需要保持的不变量；只测新 helper 或 grep sentinel 不算回归完成。若同一 transport 会按 chat type / profile / tenant 映射不同配置 namespace，测试还必须穿过实际 consumer，成对断言各 scope 最终拿到的 toolsets/display policy 与真实出站 send/edit，不能用“配置文件值正确”或“selector helper 单测通过”替代。测试同时要有正例、不会误触发的反例，以及问题涉及重试、去重、重复引用或恢复时的重入例。能对用户已置于本次范围内的既有消息做只读 API replay 时可作为额外证据；没有明确授权时不要为了 canary 主动向外部会话发消息，fixture 级边界回归仍是硬门禁。

**模型切换后的多模态验收（长期硬门槛）**：`config.model`、`fallback_providers` 或其具体型号/ARN 发生变化时，不得仅凭旧 catalog、provider 名或历史结论推断能力。对每条配置 route 至少用合成、无敏感内容的最小 canary 穿过真实 provider wire，分别验证官方声明支持的 image/audio/video/PDF 输入；官方明确不支持的模态必须保持 fail-closed，不得用强制 native 掩盖。运行时遵循 native-first：主模型真实支持就直接接收原始媒体；不支持或本地可信抽取/STT 全失败时，才把**单个当前媒体 + 有界 caption/引用上下文**交给 fallback 链中首个具备该模态的 route，禁止切换整轮 provider、禁止重放 transcript、禁止同一媒体先预分析后再重复调用工具。成功的 native、可信抽取和 sidecar 结果不得向模型暴露宿主 cache 绝对路径，也不得诱导再次 `read_file`/媒体工具；全部 reader 失败必须给当前 turn 一个明确、可测试的 `FAILED` 状态，说明不能声称读过并要求用户重发，禁止静默丢附件或退化为群聊不可达的 path note。PDF 还必须成对覆盖“纯文本只抽取”和“抽取有扫描/图片页缺口时补充 sidecar”两条路径。每轮升级和每次模型链调整都要证明 native route、sidecar route、可信抽取、视觉缺口补读、path-free 成功提示与显式失败反例；结论写入对应 PATCH 与测试，不能只留在会话记忆。

**附件取得与 @mention 验收（长期硬门槛）**：Feishu 群的独立附件消息无法携带 @Bot，因此资源 PATCH 必须同时证明三条入口：同一 post 内附件+mention、显式回复附件+mention、同一发送者在配置化有界窗口内先发附件后 mention。窗口扫描必须覆盖 image/file/media/audio，限制消息数、文件数与超时；显式回复不受窗口去重抑制。所有 `attachment_backfill_*` 用户配置必须从根 `config.yaml` 穿过 `load_gateway_config()` 进入 adapter 实例，不能只证明 adapter 直接接收手工构造的 `PlatformConfig.extra`；现场出现大附件时，用真实大小/耗时校准本机有界 timeout，仍保留失败可见性，禁止改成无限等待。引用/history 文本只保留 path-free 附件占位符，资源字节由当前/引用附件链恰好下载一次；下载、回填或解码失败必须进入上述显式 `FAILED` 状态。测试至少穿过 Feishu 真实 payload → adapter event → Gateway provider/user turn，成对覆盖主私聊与群聊，并断言模型可见文本不含 `~/.hermes/cache`、`/Users/.../.hermes/cache` 或容器映射路径。

**资源 provenance 的规范化形态同样属于真实边界**：Feishu/Gateway 会把出站回复中的裸链接回填为 Markdown `[URL](URL)`，用户也会发送 `[标题](URL)紧接正文`；任何群文档 read/append/rebuild/delete 的当前消息/显式引用授权测试，都必须同时覆盖规范化 `reply_to_text` 和 Markdown destination 后无空格紧接 CJK 正文的当前消息形态，并穿过 `pre_gateway_dispatch → deferred tool_call → pre_tool hook → handler`。URL parser 只能补出当前消息真实 destination，不能把 `channel_context` 或另一资源纳入授权；`/docx/`、`/docs/`、`/wiki/`、`/sheets/`、`/base/`、`/file/`、`/slides/` 的 URL/token canonicalization 必须同源。只把裸 URL/token 直接塞进 ContextVar 的 fixture 不足以证明生产链路。身份授权与目标引用失败必须返回不同 reason/message，避免把 parser/provenance 故障误诊为用户不可信。

工具注意：pytest 若因 venv 重建暂缺，可先 `pip install --target /tmp/... --no-deps pytest==<pin> pytest-asyncio==<pin>` + `PYTHONPATH` 叠加做初步定性（不污染 venv），但最终文件清单和数字必须用 `./scripts/run_tests.sh` 复跑得出；**禁止用 `uv run` 跑回归**——它会挂到 `.venv`（uv 默认项目环境）而不是 hermes 的 `venv`，产生成批假失败。

### Step 3 — 审查 patch & 脚本

`patches/local-patches.diff` + `patches/.local-patches.base` 由脚本自动刷新，属于外层 `~/.hermes` 仓库的监管记录。不能只看 patch apply 成功；本轮重构后，每次升级必须完成下面的仓库级闭环：

| 层面              | 终态必须成立                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **事务目标**      | 本轮至多一次显式 `--update`；失败/中断后的事务文件固定同一个 `TARGET_SHA`，所有后续执行均为 `--reconcile` 且日志明确 `no fetch/pull`。终态 `HEAD == TARGET_SHA`；事务文件只能在整支脚本 exit 0 后消失。`origin/main` 在事务期间即使被其他进程刷新也不得改变当前目标。update/reconcile/final-audit 共用同一原子锁，事务写失败即非零；不得让审计与回贴并发观察到半写状态。                                                                                                                                                                                                                                                                                              |
| **受管文件集合**  | 用 `bash ~/.hermes/hermes-update.sh --print-patched-files` 读取权威 `PATCHED_FILES`，不得依赖文档快照或 source 脚本。每个受管文件都应有预期内 diff；任一 zero-diff path 必须判定为吸收、漏补或 stale registry，不能让 bundle 静默少一项。内层其他 modified/untracked 文件逐项归类。`package-lock.json` 只有在 `patches/package-lock.review` 同时记录当前 `HEAD:package-lock.json` blob SHA 与工作树文件 SHA-256、且两者与现场逐字匹配时才可作为唯一 bundle 外差异；仅能 JSON parse 或手工口头确认不构成审核回执。                                                                                                                                                     |
| **上游交叉矩阵**  | full `scripts/test_patch_evidence.py --report-json` 必须从每个 PATCH 的 `文件` 字段解析 owned files，证明所有 `PATCHED_FILES` 至少有一个活跃 owner，并为每个 PATCH 输出本轮 `OLD_SHA..NEW_SHA` 的 `upstream_overlap`。所有相交路径必须出现在 `PATCHES.md` 当前升级摘要，agent 逐个读取对应 `上游吸收判断` 后给出未吸收/部分吸收/完全吸收结论；“无路径相交”只能作为低风险信号，不能替代语义判定。文件字段禁止只写“及对应 tests/docs”而不列出受管路径，否则 ownership gate 应失败。                                                                                                                                                                                     |
| **bundle 一致性** | 从 `HEAD` 建立**独立临时 index**，对每个 `PATCHED_FILES`：工作树存在则 `git add -f`，不存在则 `git rm --cached --ignore-unmatch`，再用该 index 执行 `git diff --cached --full-index HEAD -- <PATCHED_FILES>`；结果与 `patches/local-patches.diff` 必须**逐字节一致**。仅当确认全部受管路径都已被 HEAD 跟踪时，才可简化为普通 `git diff --full-index HEAD`。临时 index 是必要条件：受管 new/ignored 文件不会出现在普通 worktree diff 中。必须固定 `--full-index`，避免 Git 对象库增长导致自动缩写位数变化；文件数量、行数或“看起来一样”都不能替代 `cmp`。脚本 Step 2/8c 已 fail-closed 自动执行同一物理 gate，升级审计仍须独立复核输出与现场，防止脚本自身被错误修订。 |
| **可回放性**      | 确认内层 index 干净后，`git -C ~/.hermes/hermes-agent apply --cached --check ../patches/local-patches.diff` 对 HEAD 正向通过；当前已打补丁的 worktree 上执行 `git -C ~/.hermes/hermes-agent apply --check --reverse ../patches/local-patches.diff` 通过。两项分别证明“下次能贴”和“当前 bundle 确实描述现状”。                                                                                                                                                                                                                                                                                                                                                         |
| **基线来源**      | `patches/.local-patches.base` 必须严格只有两列：第一列为 40 位小写十六进制 SHA 且等于内层 `git rev-parse HEAD`，第二列为可解析的 UTC `Z` 时间戳；多列、短 SHA、无时区或尾随内容都 fail closed。                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **语义注册表**    | `PATCHES.md` 中活跃 + Archive ID 全局唯一；活跃块各有且仅有 `问题`、`修复`、`验证`、`上游吸收判断` 四段；不得出现 `LEGACY`、纯数字或 A/B 变体命名。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **执行链注册**    | 每个活跃补丁按类型有唯一执行链：工程内补丁对应 Step 8b 独立 sentinel/gate 并进入 8c 总闸门；运行时补丁对应明确 update step；外层插件补丁对应 Step 8e verifier。Archive sentinel 也必须保留明确执行链：Step 8b 的进入 8c 总闸门，工程外 sentinel（如 Step 7 completion）留在其原步骤并影响整次升级结果。                                                                                                                                                                                                                                                                                                                                                               |
| **外层安全补丁**  | `PATCH-FEISHU-GROUP-SANDBOX` 检查外层 diff + `plugins/<name>/verify.sh`；`config.yaml` / `plugins/` / `my-skills/` 不得伪造进内层 replay bundle。verifier 必须先证明 launchd wrapper 受监管，再用 `gateway.status.get_running_pid()` 取得真实 Gateway 子进程并核对其注册日志，证明实际运行进程已加载新策略。                                                                                                                                                                                                                                                                                                                                                          |
| **画像隐私边界**  | `people.yaml` 必须被 Git 忽略；`people.yaml` / `groups.yaml` 都保持 owner 可读写的普通文件并由热加载器与 Step 8b 收敛为 `0600`，不得用只读位或 immutable 破坏同账号 VSCode 手工编辑。人物字段采用公开白名单，只有 `name` / `role` / `department` / `address` 可输出，任何未来新增字段必须默认“模型可读、输出禁止”，技术 ID 与未公开别名只用于匹配。`PATCH-LOCAL-PROFILES` 的行为回归还必须覆盖当前问话人匹配、历史/合并转发发送者仅渲染公开白名单，以及 final、stream、fallback、interim、streaming TTS、`/background` 等独立可见/可听文本路径的脱敏。只检查普通 final reply 不足以证明“只能使用、不能外显”。                                                         |

任何一项不成立都先修复再进入文档对齐，不能把不闭合的 bundle 或注册表写成“升级成功”。此外：

- `~/.hermes/hermes-agent` 里被 patch 修改的文件保持为 modified，不在内层仓库提交；外层 patch diff 才是可提交记录。
- `git diff` 检查 index hash / 行号漂移是否来自本次上游变化；共享文件上的 hunk 必须按语义 PATCH 分别解释。
- `hermes-update.sh` 顶部注释里的 baseline SHA 是**手写**的，本步骤手动改成 `NEW_SHA`。
- 如脚本本身在升级过程中暴露了会破坏既有升级不变量的兼容性问题（例如强杀在途任务、失败仍返回 0、重载后仍是旧 PID），属于流程本身的修复范围：按运行时 PATCH 归并原则当轮修脚本、PATCH 注册表、README 与本 playbook，并完成相应静态/隔离验证。只有引入新工作流目标或扩大安全边界时才留给用户决策；不能一边把缺口写进报告，一边保留下一轮必然复发的执行路径。

### Step 4 — 文档对齐（发现式，不用预设清单）

用 grep 在仓库里找所有引用 `OLD_SHA` / `OLD_DATE` 的位置：

```bash
cd ~/.hermes && grep -rln -E "<OLD_SHA>|<OLD_DATE>" \
  --include="*.md" --include="*.sh" --include="*.py" \
  --include="*.yaml" --include="*.yml" --include="*.toml" . 2>/dev/null | \
  grep -v -E "^\./(hermes-agent|tmp|sessions|logs|state-snapshots|memories|\.git|skills|cron|db_workspace|completions/_hermes)"
```

对每个命中文件，按下表决定改不改：

| 命中位置类型                                                       | 处置                                                         |
| ------------------------------------------------------------------ | ------------------------------------------------------------ |
| "当前版本" / "适用版本" / "本手册基于" / "baseline" 类**现状陈述** | **改**，更新到 NEW_SHA/NEW_DATE                              |
| "basis OLD → NEW" / "较 OLD 前进 N commits" 类**差量描述**         | **不改**（历史差量）                                         |
| README 版本记录中与 `NEW_DATE` 同一 ISO 周的**当前周 row**         | **改**，合并本轮结果；保留该周最早 basis，只推进周内最新终点 |
| 版本记录 / changelog / 升级历史表里的**已结束周 row**              | **不改**（周度历史快照；仅事实纠错或规则迁移可重整）         |
| 不带版本号的概念性文档（实体定义、抽象架构）                       | 不会命中；命中说明是无关引用                                 |
| 命中任何 `wiki/**` 路径                                            | 见下方 **Wiki 编辑规范**（按 Layer 分别处置，不要一刀切）    |

**新增或更新内容**（属于"对齐"的一部分）：

- `README.md` 版本记录表 → 按下方周度聚合规则新增或更新唯一周 row
- `patches/PATCHES.md` § 当前版本 → 重写 header + "最近一次升级"摘要

#### README 版本记录周度聚合规则

版本记录使用 ISO 自然周（周一至周日，键为 `ISO year-Wweek`），**每周最多一条**，不按每次 update 追加流水账：

1. 现场解析 README 现有版本 row 的日期并计算 ISO week；不要按相邻行、月份或自然年周数猜测，跨年周以 Python `date.isocalendar()` 的 ISO year 为准。
2. **当周已有 row**：重写这条 row，不新增。版本和日期更新为当周最后一次升级；upstream 范围保留该周第一次升级前的最早 SHA，只把终点推进到最新 `NEW_SHA`，不能把周度 basis 重置成本次 `OLD_SHA`。把本轮新事实合入原周摘要。
3. **当周没有 row**：在表顶新增一条，版本/日期取本轮终态，upstream 范围从本轮 `OLD_SHA → NEW_SHA` 开始；本周后续升级继续更新此 row。
4. 周摘要只保留五类可跨会话复用的信息：周内 upstream 首尾范围与主要主题；PATCH 新增/并入/部分吸收/归档；真实冲突及语义解决原则；周末最终回归/闭环；重大依赖、配置或运行态摩擦。重复的 clean apply、每次 Skills 数字、瞬时 PID、重复 Doctor 输出和中间测试数字不逐轮堆叠，只保留周末终态或确有诊断价值的异常→修复链。单周 row 以约 1500 字为上界，超出即按五类信息回炉压缩，不得靠堆叠事件叙事膨胀。
5. 已结束周 row 是历史快照，普通升级不得回写；只有事实纠错或版本记录规则本身迁移时可重整，并须在最终报告说明。`PATCHES.md` 的“最近一次升级”仍按**本轮**写 5 段，不受 README 周度聚合影响。
6. **叙事段生命周期（防三重叙述）**：同一事件只允许一个长期容器——README 周 row。升级期外的重大运行态审计/修复可在 `PATCHES.md` § 当前版本下以带日期段落临时记录，但该段落只存续到下一次"最近一次升级"摘要重写：重写时把仍有跨会话价值的事实并入当周 README row，然后**删除**该段落，不得让审计叙事在 PATCHES.md 里无限累积、被后续 AI 误读为现状。

文档对齐结束后必须在 Step 5 运行周键唯一性检查；发现重复周先合并，不能带重复 row 收尾。

摘要写作 5 段固定结构（保持跨升级一致）：

1. **上游主线**：按分类列改动（安全 / Gateway / Skills / Desktop / 模型 / Email / Web / Dashboard / 等），每条附 PR# 或 commit hash 短前缀
2. **patch apply / registry**：clean / 3-way / 冲突、Step 3 闭环结果、锚点漂移 `OLD → NEW`，以及本轮新增 / 部分吸收 / 归档的语义 PATCH ID
3. **依赖**：venv 包升降级 + `npm audit fix` 结果 + Skills mirror `+/~/-`，并写清剩余告警属于 P0/P1/P2/P3 哪类
4. **已知摩擦**：复发的 uv / launchd / npm / patch 问题 → 本次处置；P2/P3 留案必须说明“不影响飞书主链路”或具体受影响的可选能力
5. **配置漂移**：`hermes doctor` 报的 `Config version` 状态 + 是否需要 `--fix`；不要把 P2/P3 当成待修 P0 混写

#### 升级问题分级与处置口径

每轮 `hermes-update.sh` 的 `⚠` / `Recommended actions` / `npm audit` / verifier 输出都必须先分级，再决定是否修复或留案。最终报告和 README 当前周 row 都按这个分类写，不要只堆原始 warning。

| 级别                         | 判定                                                                                                                                                                                    | 处置                                                                                                                                                                         |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0 主链路阻断 / 安全边界** | 影响飞书 gateway 主链路、owner/group sandbox 边界、认证/secret、patch replay、事务固定 SHA、gateway planned restart、运行时代码 import、必需依赖、用户插件 verifier、数据丢失或配置迁移 | 当轮必须修复并回归；未修复不得声称完成。最终报告写明修了哪些、对应验证和残余风险                                                                                             |
| **P1 本地可修但非主链路**    | 不直接影响飞书主链路，但本机有低风险明确修法，如缺 Playwright 浏览器、根 npm 依赖未安装、metadata mirror 排除缺口、文档/版本记录漂移                                                    | 能修就当轮修；修完报告“已修”和验证。若修复会引入新依赖或改变安全边界，升级报告单列等待用户决策                                                                               |
| **P2 上游阻挡且非主链路**    | 仅影响 Web/UI/Desktop/browser tooling/build chain 等可选路径，或 npm advisory 只能靠 `--force`、越界 lock/range、上游 peer 冲突解决；无证据影响飞书 gateway 主链路                      | 不用 `--force`、不倒退大版本、不手搓 lockfile 越界修复。保留 `npm audit --json` / `npm explain` 定性，在最终报告和 README row 写“等待上游 lock/range bump，不影响飞书主链路” |
| **P3 可选能力缺口 / 未配置** | 未登录 provider、可选工具缺 API key、Desktop/Web/TUI/browser 能力未准备，而当前用户主链路不依赖                                                                                         | 不阻塞升级；只报告影响范围和需要该能力时的下一步。若用户明确要求该能力，再提升为 P1/P0 处理                                                                                  |

分类规则：凡是会让飞书私聊/群聊收不到、错发、越权、泄密、丢工具边界或让升级事务无法完整收敛的，一律按 P0；能本地无风险修的不要留给报告；只有 P2/P3 可以留案，而且必须写明为何不影响当前运行主链路。

#### 语义 PATCH 块的组织原则（写入 `patches/PATCHES.md` 时严格遵守）

每个 `### [PATCH-<DOMAIN>-<INVARIANT>]` 定义块在整份 `PATCHES.md` 里**仅出现一次**，并且必须各有且仅有 `**问题**`、`**修复**`、`**验证**`、`**上游吸收判断**` 四段。ID 描述稳定的不变量，禁止 `LEGACY`、纯数字、A/B 子编号或按升级批次命名。

每轮升级必须逐个读取活跃块的 `上游吸收判断`，对新 upstream 实现和测试做核验。**apply 成功只能证明 hunk 还能贴，不能证明补丁未被上游吸收；sentinel 通过只能证明行为存在，也不能区分行为来自上游还是本地 patch。** 判定后二选一：

- **仍活跃或仅部分吸收** → 留在 `## 当前版本` 节下；部分吸收时删除已冗余 hunk，更新四段使其只描述剩余本地不变量，然后重新生成 bundle。
- **本轮完全吸收** → 先在裸 upstream 状态证明行为和测试成立，再把整个语义 PATCH 块从当前节**移动**（不是复制）到一个 `## Archive — PATCH-<DOMAIN>-<INVARIANT>` 归档节，并记录上游吸收版本/commit；删除该补丁独有 hunk，仅当某文件不再被任何活跃补丁触及时才从 `PATCHED_FILES` 移除；若脚本保留 sentinel 作为回归 guard，在归档节里注明，并保留在对应执行链和总闸门中。

升级摘要里只**提及**本轮新吸收的 PATCH（例如“`PATCH-FOO-BAR` 已被上游吸收并移入 Archive”），不要把 PATCH 块的内容复述进摘要。这样 `PATCHES.md` 始终是“活跃补丁 + 归档补丁”的并列结构，定义块不会在多处重复。

**新增 vs 并入（补丁归并原则）**：Step 2c 回归或摩擦驱动出新修复时，先扫一遍现有 PATCH 清单再落位，agent 自行判定、不请示——

- **并入现有语义 PATCH**：修复与该补丁共享同一不变量、必须一起回滚/验收，且预期上游会在同一个 PR 中吸收。例如新的 Feishu strong-flanking case 归入 `PATCH-FEISHU-MARKDOWN`。更新问题/修复/验证/上游吸收判断四段与 sentinel，不创建变体编号。
- **新增语义 PATCH**：能独立失效、独立回滚或被不同上游 PR 吸收的关注点必须拆开，即使改同一文件。例如 `PATCH-FEISHU-GROUP-APPROVAL` 与 `PATCH-APPROVAL-DARWIN-TMP` 都改 `approval.py`，但安全不变量和吸收条件完全不同。ID 使用 `PATCH-<DOMAIN>-<INVARIANT>`，禁止 A/B 子编号。
- 工程内补丁无论新增还是并入，**五处**同步缺一不可：新触及文件加入 `PATCHED_FILES`（已有文件免）；sentinel 块（新增 PATCH 时含 gate 变量并纳入 8c 刷新条件）；`PATCHES.md` 对应块；`PATCHES.md` §「受 `PATCHED_FILES` 管理的文件」的**快照数组与其后括注的文件数**（2026-08-11 实抓：受管文件 64 → 67 后只改了脚本数组，快照与注数字停留在 64，Step 5 断言才拦下）；`local-patches.diff` / `.local-patches.base` 用与脚本 8c 相同的命令刷新，并按 Step 3 完成闭环核对。快照按 `bash ~/.hermes/hermes-update.sh --print-patched-files` 的输出整块重建，不要手工增删单行。
- **哨兵锚点选择与共演进**：新写 grep 哨兵优先锚定**测试名或行为特征串**（测试名受 Step 2c 保护、很少被重构改名），避免锚定私有 helper 名——上游或本地重构最容易杀死后者（2026-08-03 实例：`_with_current_author_prefix` 被冲突轮重构移除，gate 误报 14 小时）。配置驱动的补丁还必须让测试 fixture、测试名和 gate 使用 `primary` / `fallback-A` / `fallback-B` 这类角色语义，不能把当前生产 config 的 provider/model 名写成补丁契约；否则未来只换配置也会留下伪失效的执行链。Requirement-retired Archive 的负向审计同样不得要求“当前替代者必须是 provider X/model Y”：它只验证旧 registry/resolver/schema/config-key surface 未复活，dotenv 仅 names-only 读取；当前主/fallback/compression 的健康由动态 route/runtime 总闸门证明。行为探针必须自建稳定 fixture 或调用 public API，不得 import 上游测试文件的私有 helper。条件允许时向 PATCH-SKILL-CREATE-ROOT 的真实 import + 调用模式靠拢。**冲突解决或重构触及文件 X 后，必须核对 8b 中所有针对 X 的哨兵仍能命中**——最省事的核对方式就是按收敛循环重跑脚本。
- 运行时补丁不进入 `PATCHED_FILES` / replay bundle，但必须在 `hermes-update.sh` 有明确步骤、可审计输出和验证口径，并在 `PATCHES.md` 登记生命周期；不要为凑 Step 8b gate 制造空源码 hunk。
- 配置仓库用户插件补丁（当前 `PATCH-FEISHU-GROUP-SANDBOX`）不进入 `PATCHED_FILES` / `local-patches.diff`。它必须同时具备：外层 Git 跟踪的插件/配置/skill 文件；独立 `verify.sh`；`hermes-update.sh` Step 8e 固定登记；verifier 缺失、不可执行或失败时 `FINAL_RC=1`；`PATCHES.md` 对应块。verifier 至少结构化解析 YAML、解析真实平台 toolset、跑行为测试，核对 launchd wrapper 受监管，并把注册日志绑定到 `gateway.status.get_running_pid()` 返回的真实 Gateway 子进程。对渐进式工具披露还必须穿过真实 `handle_function_call(tool_call → underlying)`，证明 scope gate、底层 hook 和 handler 全部执行；枚举 model-facing 直接工具并逐项确认 hook 不会误拦。凡工具结果要求后续 `read_file` 分页，verifier 还必须证明 continuation 文件只对当前会话/群精确授权，不能靠开放整个全局 cache 解决。

只要本步骤新增、合并、部分吸收或归档了工程内补丁，就必须回到 Step 2c 重跑受影响测试并再次执行 Step 3 全闭环；涉及外层插件时还要重跑 Step 8e verifier。不能用“仅改注册表/仅删冗余 hunk”为理由沿用变更前的测试结果。

#### Wiki 编辑规范（命中 `wiki/**` 时严格遵守）

Wiki 有独立的分层与硬约束体系，**结构会演进**——layer 定义、路径约定、frontmatter 必填字段、wikilink 规则、注册表 / 操作日志要求**统一以 `~/.hermes/wiki/SCHEMA.md` 为单一权威来源**。Playbook 只锁语义原则、不冻结路径；**进入 Step 4 文档对齐前必须先 `Read ~/.hermes/wiki/SCHEMA.md`**，按当前 schema 把仓库里的 wiki 子树映射到下表语义类别后再做分流。

| 语义类别（具体路径与判定规则查 SCHEMA）                        | 升级期间处置                                                                                                                               |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **用户私有运维 / 部署笔记**（user-maintained source layer）    | **可改**，但只更新 frontmatter `updated` 字段 + 正文里的 SHA / 日期 / 版本号字符串；不动叙事段落、不加 wikilinks、不重构标题或目录         |
| **外部素材 / 原始引用层**（external snapshot / raw reference） | **不改**（agent 不维护，保持来源忠实）                                                                                                     |
| **Agent 维护的知识图谱节点**（active knowledge nodes）         | **理论上不该命中**版本号——这些是概念性页面；若命中多半是该页措辞把版本写死了的 wiki 自身 bug，**报告给用户**、**不在**升级 commit 里顺手改 |
| **Meta 页**（schema 自身、节点注册表、结构性操作日志）         | **不动**                                                                                                                                   |
| **归档层**                                                     | **不动**                                                                                                                                   |

**两条硬边界**：

1. 任何**超出"字符串替换"范围**的 wiki 改动（新增页 / 重命名 / 删除 / 改 wikilink / 改 frontmatter 字段 / 改 layer 归属 / 重排目录结构等）**一律剥离**出本次升级 commit，在最终报告单列一节、建议用户单独发起 wiki 编辑会话；动手前**再次完整** `Read SCHEMA.md` 逐条对照硬约束
2. 用户私有运维笔记层改完后跑 `python3 ~/.hermes/scripts/wiki_lint.py`（stdlib only，零依赖），确认 active 层未被意外波及

> SCHEMA 加新层 / 重命名目录 / 改 lint 规则——playbook 不用动，agent 每轮重读 SCHEMA 即自动跟进。本规范只保证语义不变量：**升级仅触碰用户运维层的字符串、其余层一律避让、超范围改动单独走流程**。

### Step 5 — 复扫遗漏

文档改完后**再跑一次** Step 4 的 grep，逐条人工确认：剩余命中应**全部**是"差量描述"或"历史 row"。任何"现状陈述"型命中漏掉 = bug，要补改。

同时机械校验**派生一致性**（周键唯一 + 数字/SHA 不失同步），并运行 `python3 scripts/test_patch_evidence.py` 做逐 PATCH 真实回归证据审计。Step 4 的 grep 只能发现 SHA 字符串，发现不了"脚本数组 64 但快照注仍写 63"这类数字漂移（2026-08-03 实抓一起），也不能发现某个 PATCH 只剩 grep sentinel 而没有测试边界；因此以下断言与 PATCH evidence 审计每轮必跑、任一失败先修再收尾：

```bash
python3 - <<'PY'
from collections import Counter
from datetime import date
from pathlib import Path
import re
import subprocess

# 1) README 版本记录每个 ISO week 至多一条
readme = Path("README.md").read_text()
days = re.findall(r"(?m)^\|\s*v[^|]*\|\s*(\d{4}-\d{2}-\d{2})\s*\|", readme)
weeks = [f"{(iso := date.fromisoformat(d).isocalendar()).year}-W{iso.week:02d}" for d in days]
dup = {w: c for w, c in Counter(weeks).items() if c > 1}
assert not dup, f"duplicate README version weeks: {dup}"

# 2) PATCHED_FILES：脚本数组 == PATCHES.md 快照清单 == 快照注数字
script = Path("hermes-update.sh").read_text()
arr = re.findall(r'^\s+"([^"]+)"', script.split("PATCHED_FILES=(")[1].split(")")[0], re.M)
patches = Path("patches/PATCHES.md").read_text()
snap_sec = patches.split("受 `PATCHED_FILES` 管理的文件")[1].split("> 以上")
snap = re.findall(r'"([^"]+)"', snap_sec[0])
note_n = int(re.search(r"（(\d+) 文件", snap_sec[1]).group(1))
assert arr == snap, f"array({len(arr)}) != snapshot({len(snap)}): {set(arr) ^ set(snap)}"
assert note_n == len(arr), f"snapshot note says {note_n}, array has {len(arr)}"

# 3) 活跃 PATCH 计数与生命周期分区：定义块数 == 注册表口径 == README 口径；
#    所有活跃定义必须连续位于首个 Archive 之前，Archive 后不得再续接活跃区。
active_text, archive_sep, archive_text = patches.partition("\n## Archive")
assert archive_sep, "PATCHES.md is missing Archive boundary"
assert "## Active PATCH definitions (continued)" not in patches, \
    "active PATCH definitions must not resume after Archive"
active_blocks = re.findall(r"^### \[PATCH-", active_text, re.M)
stated = int(re.search(r"当前共 (\d+) 个语义补丁", patches).group(1))
readme_n = int(re.search(r"(\d+) 个按职责命名的活跃语义补丁", readme).group(1))
assert len(active_blocks) == stated == readme_n, \
    f"active blocks={len(active_blocks)}, PATCHES.md says {stated}, README says {readme_n}"

# 3b) Step 8b 声明的所有活跃/归档 gate 必须有成功赋值，并被 8c 聚合条件逐项消费。
gate_start = re.search(r"^# -- 8b\. Patch invariant gates.*$", script, re.M)
gate_end = re.search(r"^# -- 8c\. Refresh saved diff.*$", script, re.M)
assert gate_start and gate_end and gate_start.start() < gate_end.start(), "missing/misordered Step 8b/8c markers"
gate_region = script[gate_start.start():gate_end.start()]
active_gates = set(re.findall(r"^(_[A-Z0-9_]+_PATCH_OK)=false$", gate_region, re.M))
archived_gates = set(re.findall(r"^(_ARCHIVED_[A-Z0-9_]+_OK)=false$", gate_region, re.M))
declared_gates = active_gates | archived_gates
never_true = {
    name for name in declared_gates
    if re.search(rf"^\s*{re.escape(name)}=true$", gate_region, re.M) is None
}
assert not never_true, f"patch gates never set true: {sorted(never_true)}"
aggregate = re.search(r"^if \$_PATCH_APPLY_OK && .+?; then$", script[gate_end.start():], re.M)
assert aggregate, "missing Step 8c aggregate gate"
consumed_gates = {
    token[1:] for token in re.findall(r"\$_[A-Z0-9_]+_OK", aggregate.group(0))
    if token != "$_PATCH_APPLY_OK"
}
assert declared_gates == consumed_gates, \
    f"Step 8c gate drift: missing={sorted(declared_gates-consumed_gates)}, " \
    f"unknown={sorted(consumed_gates-declared_gates)}"

archive_defs = list(re.finditer(r"^### \[(PATCH-[A-Z0-9-]+)\].*$", archive_text, re.M))
for i, match in enumerate(archive_defs):
    block = archive_text[match.start():archive_defs[i + 1].start() if i + 1 < len(archive_defs) else len(archive_text)]
    status = re.search(r"\|\s*\*\*状态\*\*\s*\|\s*([^|\n]+)", block)
    if status:
        assert "已归档" in status.group(1) or "已上游合并" in status.group(1), \
            f"active-looking PATCH definition placed under Archive: {match.group(1)}"

# 4) base SHA 三处一致：.local-patches.base == PATCHES.md header == README 现状陈述 == 脚本头注释
base_sha = Path("patches/.local-patches.base").read_text().split()[0]
for label, pat, text in [
    ("PATCHES.md header", r"## 当前版本：\S+ \(upstream `main` `([0-9a-f]+)`", patches),
    ("README 补丁章", r"当前基线为上游 `([0-9a-f]+)`", readme),
    ("脚本头注释", r"As of \S+ / main ([0-9a-f]+)", script),
]:
    sha = re.search(pat, text).group(1)
    assert base_sha.startswith(sha), f"{label} SHA {sha} != base {base_sha[:12]}"

# 5) 外层插件 verifier 回归条数：PATCHES.md 验证字段 == README Step 8e == 真实 pytest 收集数。
#    verify.sh / hermes-update.sh 都只看 pytest 退出码、不看条数，所以这两处"活契约"数字
#    可以无限期静默失真（2026-08-20 实抓：修 HyperTeX 附件名后回归 42 → 52，两处仍写 42，
#    任何机械 gate 都没报）。这里把文档数字绑回真实收集数，纳入 Step 5 数字漂移防线。
plugin_pat_n = int(re.search(r"插件 \*\*(\d+) 条\*\*回归", patches).group(1))
plugin_readme_n = int(re.search(r"运行 (\d+) 条行为测试", readme).group(1))
collected = subprocess.run(
    ["hermes-agent/venv/bin/python", "-m", "pytest", "--collect-only", "-q",
     "plugins/sandbox/test_sandbox.py"],
    capture_output=True, text=True, timeout=180).stdout
plugin_real_n = int(re.search(r"(\d+) tests? collected", collected).group(1))
assert plugin_pat_n == plugin_readme_n == plugin_real_n, \
    f"plugin regression count drift: PATCHES.md={plugin_pat_n}, " \
    f"README={plugin_readme_n}, collected={plugin_real_n}"

# 6) Feishu 身份自演进链：sandbox verifier 必须同时消费组织同步回归，
#    防止 people.yaml 的 user_id 生成契约只存在于一次性人工验证中。
verifier = Path("plugins/sandbox/verify.sh").read_text()
assert '"${PLUGIN_TEST}" "${PEOPLE_TEST}"' in verifier, \
    "sandbox verifier no longer runs the Feishu identity-sync regression suite"
people_collected = subprocess.run(
    ["hermes-agent/venv/bin/python", "-m", "pytest", "--collect-only", "-q",
     "scripts/test_pull_feishu_people.py"],
    capture_output=True, text=True, timeout=180).stdout
people_real_n = int(re.search(r"(\d+) tests? collected", people_collected).group(1))
assert people_real_n > 0, "Feishu identity-sync regression suite collected no tests"

print(f"derived-consistency OK: {len(weeks)} weekly rows unique; "
      f"{len(arr)} managed files; {stated} active patches; "
      f"{len(active_gates)} active + {len(archived_gates)} archived gates; "
      f"{plugin_real_n} plugin behavior + {people_real_n} identity-sync tests; "
      f"base {base_sha[:9]}")
PY
```

> 断言口径变了（如快照注措辞、README 表述）就同步改这段脚本——它与被校验文本共演进，属于 Step 4 文档对齐的一部分。

#### Step 5b — 终态运行屏障

Step 2c/4/5 期间只要修改过 `hermes-agent` 运行时代码、`config.yaml`、`.env` 或 `plugins/`，Step 8d 的 PID 证据就立即失效。所有代码、配置、测试、bundle 和文档修改结束后，必须把 planned restart 当作一次**终态写屏障**。记录旧 PID 前先运行：

```bash
python3 ~/.hermes/scripts/cleanup_transient_artifacts.py --dry-run --json --fail-on-review
python3 ~/.hermes/scripts/cleanup_transient_artifacts.py --apply --fail-on-review
```

dry-run 必须把 `scripts/`、`hermes-update.sh`、插件 verifier 及 outer/inner `git status --ignored` 的全部条目分类为 `keep/remove/review`；`review`、policy error、required script 未跟踪、当前 Hermes 工作区内的活跃 pytest/CDP 进程或 apply 失败均阻断 restart。进程 marker 只能在候选 PID 的 cwd 位于本 Hermes 根、或 argv 明确引用该根时生效；其他 workspace 长期运行的 Codex/Claude/Gemini/Qwen 不得因 prompt 中偶然包含 `pytest` 等词阻塞本流程。进程枚举与 cwd 归属本身仍是安全探针：`ps`/PID/cwd 查询抛错、返回非预期状态或无法证明候选进程已退出时必须 fail closed，不能把“探针坏了”当成“没有活跃进程”。apply 只移动 blacklist 项到 Trash，不能删除 review 或 tracked 文件。清理通过后记录 `hermes gateway status` 的当前 supervisor PID，执行 `hermes gateway restart`，按脚本 `gw_restart_wait_seconds()` 同款预算（新运行时的 `_get_restart_exit_wait_budget()` 优先，旧运行时回落 `restart_drain_timeout`，+30s）轮询到不同的新 supervisor PID，再在新 PID 下重跑全部 Step 8e verifier 和 `hermes gateway status`。新 launchd plist 可能直接监管 `hermes_cli.stderr_timestamp` wrapper；此时 status PID 是 wrapper，verifier 必须另用 `gateway.status.get_running_pid()` 取得真实 Gateway 子进程并把注册 trace 绑定后者。两层 PID 都必须健康。如果 barrier 之后又改了任何运行时输入，必须重新执行本步骤；完全只读的“已是最新”审计且能证明当前进程晚于最后一次运行态修改时可跳过。

不要把 `plugins/<name>/verify.sh` 的通过结果单独当作运行态新鲜度证明：verifier 会做磁盘代码测试和当前日志匹配，但如果 Gateway 子进程是本轮插件修改前启动的，进程内 handler 仍可能是旧代码。凡本轮碰过 `plugins/`，收尾证据必须同时包含“旧 supervisor PID → 新 supervisor PID”、新 wrapper 下的真实 Gateway 子进程 PID，以及该子进程对应的 verifier 结果；缺任一项都按 Step 5b 未完成处理。

禁止用 `hermes gateway stop && hermes gateway start` 代替 planned restart：macOS stop 路径在短固定宽限后会强杀进程，可能把正在处理的飞书 turn 变成中断恢复任务并产生非预期回复。若排空超过预算或 PID 未替换，本轮必须非零/阻塞收尾，保留旧进程与日志供诊断，不能为了得到新 PID 直接强杀。

#### Step 5c — Playbook 持续演进自审（每轮必做）

Step 6 报告前，以本轮实际执行为镜，把本 playbook（含摩擦表）当作与代码同级的可维护资产，做一轮完整的**增补 + 清理 + 修订**三操作审计。playbook 不是只追加的日志：只增不减会让规则密度稀释、失效条目与现行条目混杂，后续轮次的执行效能逐轮退化——**"本轮没有可清理/可修订项"必须是审计后的结论，不能是默认假设**：

清理器本身属于本步骤的共演进资产：每轮都要审查 `scripts/cleanup_policy.json` 的 required script 白名单、临时脚本/ignored 黑名单和 review 输出。新增、重命名或退役任何 outer 运维脚本、插件 verifier、ignored runtime 路径时，必须同步 policy、`test_cleanup_transient_artifacts.py`、`PATCH-GATEWAY-RESTART-CLEANUP` 与本 playbook；禁止为了让 restart 通过而把未知路径机械加入 keep，也禁止把并发 session 产物直接加入 remove。`--dry-run --json --fail-on-review` 为机械下界，语义理由仍须写入 policy 的 reason 字段。

1. **增补（新现象清点）**：列出本轮出现而 playbook / 摩擦表未预见或描述不准的现象（新 doctor 检查、新迁移形态、新冲突型、新警告类别、脚本或官方 updater 的新行为、测试口径变化）。逐项按"权威源不分叉"判定归属——执行行为 → `hermes-update.sh`，PATCH 生命周期 → `PATCHES.md`，物理改动 → replay bundle，决策/恢复规则与摩擦 → 本 playbook——并**当轮落盘**；只写进最终报告或会话总结等同于未修复。
2. **清理（时效退场）**：逐段扫描 playbook 正文与摩擦表，识别并删除：① **已被消费的一次性预案**——针对特定未来 upstream 范围写的冲突/行为预告，该范围已跨过、预案已兑现或证伪；② **指向已不存在事物的陈述**——引用已归档 PATCH、已移除机制、已被上游取代的行为；③ **连续多轮未触发且非结构性的条目**——结构性/周期复发的知识（如 lock 噪音、镜像振荡）保留，纯历史巧合退场。仍有历史价值的事实并入 README 对应周 row 后再删，不在 playbook 里留尸体；摩擦表每个 row 都必须能回答"什么条件下删除本 row"，新增 row 时把退场条件写进处置栏。`hermes-update.sh` 的归档 sentinel 同属清理对象（见补丁模型归档层）。
3. **修订（规则时效核查）**：抽查本 playbook 引用的锚点、命令、路径、默认值与当前脚本/上游是否仍一致（如 `--print-*` 只读入口、gate 名称、doctor 输出口径、wiki SCHEMA 路径映射）；描述已不准确的段落**就地重写**，不另开平行段落、不保留旧措辞注释。失效即当轮修订，不留给下一轮撞上。
4. **验收自问**：换一个没有会话记忆的 AI，面对任意后继 upstream，仅从当前磁盘状态和本文件出发，能否重建本轮全部判断（含本轮新增的判定规则）？任何"必须靠本次会话记忆才能答对"的知识点，都必须补写进对应权威文件后本步骤才算通过。
5. **结果入报告**：Step 6 报告必须单列本步骤结论——增补、清理、修订各做了什么/为何，任一类为空时写明"审计后无该类变更"及依据；该结论缺失视为升级未完成。

##### 深度 toolchain 审计：触发、周期与收敛边界

每轮升级都必须执行上面的常规自审，但**常规自审不等于每轮都要修改 toolchain**。只有满足以下任一条件时，agent 才自动升级为深度审计；不满足时应明确记录“本轮未触发深度审计”，不得为了显示有工作量而继续叠加同义 gate：

1. **事故触发**：任一真实回归、漏补丁、越权、状态污染或运行态旧代码发生在当时已报告绿色之后；这类 post-green 事故一律视为 assurance failure，而不仅是业务代码 bug。
2. **审计基础设施变更**：本轮修改或上游重构涉及 `hermes-update.sh`、canonical test runner、pytest/conftest 隔离、PATCH evidence/final-audit、cleanup、Gateway/process identity、Step 8e verifier，或新增一种 PATCH/evidence/gate 类型。
3. **覆盖异常**：测试文件数、collect/passed/skipped/xfail、probe/gate/PATCH 数量、bundle 路径数异常下降或变化无法由本轮 diff 完整解释；出现 retry 后转绿、零 collect、deferred、重复/未知回执、手工豁免或新的 allowlist/exception。
4. **执行链出现人工补洞**：升级需要跳过既定步骤、临时改命令、手工拼接多段“绿灯”、从旧 JSON/日志取证，或出现 playbook 未描述的恢复路径。
5. **用户显式触发**：用户要求“深度 PATCH/toolchain 审计”“PATCH 假绿审计”“审计升级链路”或同义任务时，无论周期是否到期都执行。
6. **周期触发**：没有事故和结构变化时，自最近一次成功深度审计起，每累计 **4 次不同 upstream SHA 的成功升级**或经过 **90 天**（先到者）执行一次。每轮 Step 1 从下方游标和 `git log -p -- patches/.local-patches.base` 重建计数；同一 SHA 的 reconcile、文档修订和重复验证不计为新升级。游标缺失、格式损坏、对应 commit 不可达或无法可靠计数时 fail-safe 视为到期。

深度审计按固定威胁模型执行，避免无边界漫游：

1. **枚举完整性**：从 PATCH 定义出发，核对 active/archive/runtime/external 分类、owned paths、测试/support files、gate、probe、verifier 和报告记录是否一一闭合；同时从执行入口反向查找无 PATCH owner 的 gate/probe/verifier。
2. **真实执行与归属**：检查 node path/class/function 精确绑定、逐 PATCH 进程隔离、每个 runnable 文件真实 collect、support module 有消费者、Archive/dedicated probe 拒绝 skip/xfail/xpass/零执行，且同一结果不能跨 PATCH 复用。
3. **聚合与时序**：检查失败退出码能否穿过 shell/管道/重试到达最终状态；最终报告必须来自本轮，canonical/evidence 数量闭合，并在最后测试之后复核 bundle、sandbox、工作树和 Gateway 进程身份。
4. **负向 fault injection**：每个新发现的假绿类别先在临时文件/临时 Git 仓库或 mock 边界构造“旧实现会绿”的最小失败样本，再修执行链并保留该负例。不得在真实用户数据、生产会话或远端仓库上做破坏性注入。
5. **独立性检查**：避免 producer、consumer、测试 fixture 和 gate 复制同一常量后共同漂移；优先让测试穿过真实 public boundary。不能自动化的外部 canary 必须记录原因、最小人工证据和退场条件。
6. **复杂度约束**：新增 gate 必须对应一个具体失效模型，具备确定输入、唯一失败信号、负向回归、可接受耗时和退场条件；能加强或替换已有检查时不平行叠加。不得仅因“还能想到更多检查”延长审计。

一次深度审计在同时满足以下条件后即收敛并停止：所有发现均完成“失败复现 → 最小修复 → 负向回归 → 权威文档落盘”；P0/P1 无遗留，P2/P3 已说明影响面和退场条件；最后一次 `--reconcile` 晚于全部执行链修改；pre-commit 与 post-commit final-audit 均通过；没有下一轮必须依赖本次会话记忆才能知道的步骤。**没有发现新缺口是合法且优先的结果**，不要求为了刷新游标而改动实现。

深度审计成功后更新下方持久化游标；普通升级不得改动 `last_deep_audit_*`。如果深度审计与一次 upstream 更新合并执行，游标记录该固定 `TARGET_SHA`；如果只审计当前 checkout，则记录当前内层 HEAD。

```yaml
toolchain_audit_state:
  schema_version: 1
  last_deep_audit_date: 2026-09-03
  last_deep_audit_upstream_sha: 11c8c05dc31c6e49ddef16dae8695a708d6bce6a
  last_deep_audit_outer_commit: 13fc28a7c3f4a8f6f01f4d90cb86e0bd9325f1d4
  trigger: full-patch-risk-remediation-and-pipeline-hardening
```

深度审计报告除 Step 6 常规内容外，还必须列出：触发原因；检查过的失效类别；新增负例与 toolchain 改动；明确未改动的类别；剩余不可机械证明的风险；更新后的审计游标。若因触发条件自动进入深度审计，agent 在开始时告知用户即可，不为既有范围内的只读检查和修复逐项追问。

清理与修订的机械下界由下面的 playbook-hygiene 断言块保证（在 `~/.hermes` 下运行，每轮必跑、任一失败先修再收尾）；它只能抓"引用已不存在的事物"这类硬失效，语义级的过时判断仍靠上面 1–4 条人工审计。断言口径与被校验文本共演进——新增引用形态时同步扩展本块：

```bash
cd ~/.hermes && python3 - <<'PY'
from pathlib import Path
import re
pb = Path("hermes-update.md").read_text()
patches = Path("patches/PATCHES.md").read_text()
script = Path("hermes-update.sh").read_text()

# 1) playbook 引用的 PATCH ID 必须存在于 PATCHES.md（教学示例 PATCH-FOO-BAR 除外）
known = set(re.findall(r"^### \[(PATCH-[A-Z0-9-]+)\]", patches, re.M))
refs = set(re.findall(r"PATCH-[A-Z0-9][A-Z0-9-]*[A-Z0-9]", pb)) - {"PATCH-FOO-BAR"}
dangling = refs - known
assert not dangling, f"playbook references unknown PATCH ids: {sorted(dangling)}"

# 2) playbook 引用的脚本只读入口/函数必须仍存在于 hermes-update.sh
entries = set(re.findall(r"--(?:print-[a-z-]+|transaction-status|self-test-(?:transaction|fetch-retry|patch-gates|patch-evidence)|final-audit)\b", pb))
entries |= {"gw_restart_wait_seconds", "_get_restart_exit_wait_budget"}
missing = {e for e in entries if e not in script}
assert not missing, f"playbook references missing script entries: {sorted(missing)}"

# 3) playbook 反引号内的具体仓库路径必须存在（模板路径如 plugins/<name>/… 天然跳过）
for p in set(re.findall(r"`((?:plugins|patches|scripts|wiki)/[A-Za-z0-9_./-]+)`", pb)):
    assert Path(p).exists() or Path("hermes-agent", p).exists(), f"missing path: {p}"
print("playbook-hygiene OK")
PY
```

#### Step 5d — 单一终态审计（每轮必做）

Step 5c 完成后，如果修改过任何 patch、gate、`hermes-update.sh`、`scripts/final_upgrade_audit.py`、`scripts/test_patch_evidence.py`、cleanup policy/verifier 或其他升级执行脚本，必须先再跑一次完整 no-network `--reconcile`；docs-only 修改不要求制造新的 Gateway PID，但仍由本步骤检查派生一致性。随后运行：

```bash
bash ~/.hermes/hermes-update.sh --final-audit --json \
  > /tmp/hermes-final-audit.json
```

这是最终报告的唯一机器权威，取代 agent 手工拼装多段摘要。它必须在一个调用中完成：

- 完整 PATCH evidence matrix：每个 active PATCH 的唯一 pytest node outcome、每个 Archive PATCH 的当前行为/退役探针，以及 runtime/dedicated/external probe 的本轮 `probe_results`；full 模式不允许 `contract_passed`、`deferred_full` 或无执行回执
- canonical `--print-patched-tests` 文件套件，固定 `--file-retries 0` 且 0 failed；`passed + skipped` 必须与 full evidence 的 collect 数完全一致，skip/xfail 不能充当某个 PATCH 的唯一 evidence，pass-on-retry/FLAKY 不得作为终态绿灯
- patch gate/transaction/fetch self-test、bundle byte/cached/reverse/index/base 闭环；active/Archive gate header、唯一置绿变量与 8c 消费集合必须一一对应；inner 只允许完整 `PATCHED_FILES` overlay，另可保留唯一、带双 SHA 审核回执且仅 unstaged 的 `package-lock.json` npm 归一化差异，其他 extra/staged 路径仍 fail closed；canonical 与 verifier 全部结束后必须再次执行 bundle 物理闭环，封死测试后漂移窗口
- README 周键唯一与当前周摘要有效内容不超过 1500 字；`PATCHED_FILES` 数组/快照/注数一致；全部 active + Archive 定义精确四段；PATCH evidence 的 upgrade range 终点必须等于当前 HEAD，所有 upstream-overlap PATCH 必须在当前摘要以 `` `PATCH-FOO-BAR`=未吸收 | 部分吸收 | 完全吸收 `` 唯一登记，并核对无路径相交 active 数；playbook 摩擦表列结构与 Wiki lint 正常
- `hermes doctor` 的无 active security advisory、config up-to-date、无 deprecated key；canonical 后再次运行 sandbox verifier；launchd supervisor PID、真实 Gateway child PID 与 `gateway_state.json` 的 PID/argv/code SHA 必须一致，spawn ledger 不得残留 pytest 记录；transaction=`none`
- 受 Git 管理的 `config.yaml` 不得在 MCP sensitive headers 中保存 literal credential；Authorization/API-key/token/secret 类 header 只能引用 `${VAR}` / `${env:VAR}`，实值保留在目标机 `.env` 或 secret backend
- 所有测试/formatter/verifier 完成后的最终 cleanup apply，再 dry-run 证明 candidate/review/policy error 为 0

JSON 必须为 `status=ok`、`mode=full`，包含逐 PATCH `patches[]` 明细和 `failed_step` 可定位失败；只看到 aggregate 数字、quick mode 或单独运行的若干绿灯不能替代本步骤。final-audit 自己完成最后 cleanup，因此成功后只允许只读检查和报告；如果又运行 pytest、py_compile、formatter、verifier 或任何会生成缓存的命令，必须重新运行 final-audit。

final-audit 不是旁观者：它必须先取得与 update/reconcile 相同的事务锁。锁 owner 以 `pid + process-start fingerprint + random token` 完整发布；缺失/损坏/stale owner 不允许自动抢占，release 也只能删除三元身份完全匹配的自己。审计开始与结束必须分别绑定 outer HEAD/tree、inner HEAD/tree/index/worktree/untracked 内容、transaction、bundle/base、`package-lock.json` 与 review receipt；cleanup/runtime 后再跑一次完整 repository check，任一字段漂移都判定本轮证据失效。这样可阻止审计期间另一进程刷新 bundle、提交 outer、修改 live overlay 或改写 lockfile 后仍拼出绿色 JSON。

#### Step 5e — 用户明确要求提交时的可选闭环

默认仍不自动提交。只有用户明确要求 commit 时，才在 Step 5d `status=ok` 后执行：

1. 检查 outer/inner `git status`、staged/unstaged diff、文档/ignore/workflow/changelog 是否齐全；只 stage 外层 `~/.hermes` 的升级监管文件，内层完整 `PATCHED_FILES` overlay 不提交。若 outer 另有与本任务无关的用户改动，先按明确路径暂存到独立 stash、记录精确 stash OID；不得使用宽泛 stash 或 `reset --hard`。
2. 运行 `$HOME/.config/git/hooks/copilot-git-approve commit`，随后创建引用 upstream SHA 与受影响语义 PATCH ID 的 commit；不得绕过 hook。
3. 检查 pre-commit formatter 是否改写文件和 commit 后工作树是否干净。若 hook 后仍有 diff，先审计、复验并再次 approval 后再 amend/补交，不能把格式化后的未验证内容留在工作树。
4. 对已提交内容运行 `bash ~/.hermes/hermes-update.sh --final-audit --json --require-clean-outer`；post-commit JSON 仍须 `status=ok`，outer clean、inner 仅为预期 overlay。该调用会清理 commit hook/pytest 新产生的缓存，并机械阻断 hook 遗留 diff。
5. 若第 1 步暂存过无关用户改动，post-commit audit 通过后只按记录的精确 OID `git stash apply <oid>` 恢复；冲突时非零停止并保留 stash/冲突现场，禁止 reset。恢复后只做只读 `git status`/diff 核对，明确说明“已提交内容在 clean outer 上审计通过，随后恢复了用户原改动”；不得把恢复后的预期 dirty 误报成 hook 遗留。
6. push 是独立动作：先汇总 branch/outgoing commits 并向在场用户确认，再运行 `$HOME/.config/git/hooks/copilot-git-approve push`；commit 授权不自动包含 push。

### Step 6 — 收尾报告

向用户报告（**不要自动提交**）：

- **完成标准**：首次官方获取至多调用一次 `--update`；最后一次完整 `--reconcile` exit 0 且晚于最后 patch/gate/执行脚本修改，所有复跑固定同一 `TARGET_SHA`；Step 5c 自审已落盘；最末一次 Step 5d `--final-audit --json` 为 `status=ok / mode=full`，逐 PATCH evidence matrix、canonical tests、Archive 探针、bundle、docs/Wiki、runtime/verifier、transaction 和最终 cleanup 全部闭合。用户要求 commit 时，post-commit final-audit 也必须通过且 outer clean。任何一项不成立都不得声称完成
- 升级 `OLD_SHA → NEW_SHA`，`+N commits`
- 问题分级结果：P0 修复项与验证、P1 已修或决策项、P2 上游等待项、P3 可选缺口；P2/P3 必须说明是否影响飞书主链路
- 文档对齐了哪些文件（列文件名 + 改动类别一句话，不展开内容）
- README 版本记录周键检查结果：当周是新增还是合并、当前总周数、是否存在重复 ISO week
- Gateway / Doctor 现状（异常项展开，正常项一行带过）；安全插件需报告 verifier 对照的当前 PID，以及 owner 主会话与群聊实际 toolset 是否仍满足边界
- 持久化演进接管性：报告活跃 PATCH 的未吸收 / 部分吸收 / 完全吸收判定及相应状态变化；列出本轮新发现的冲突、摩擦或规则缺口分别落盘到哪个权威文件，如没有新增经验也明确写“无”。确认不存在下一轮升级必需、但只保留在本次会话或临时日志中的恢复知识
- Step 5c playbook 自审结论：增补 / 清理 / 修订三类各做了什么及依据，任一类为空写明"审计后无该类变更"；playbook-hygiene 断言块运行结果
- 深度 toolchain 审计决策：本轮由事故/结构变化/覆盖异常/人工补洞/用户/周期中的哪一项触发，或为何未触发；若执行则报告负向 fault injection、修复、剩余风险与更新后的 `toolchain_audit_state`
- Step 5d final-audit JSON 的 run time、target SHA、逐 PATCH 通过数、canonical suite、Gateway 双 PID、cleanup 终态与失败项（正常时明确 `failed_step` 不存在）
- 工作树里哪些是“升级相关”、哪些是“用户先前在编辑的其他东西”，提示后者保持不动；明确说明内层受管 modified files 是预期 patch overlay，外层 bundle 才是待提交记录
- 若 Step 2/3 中发现脚本侧的新兼容性问题，单列一节描述给用户决策
- 提醒：若用户随后明确要求提交，只提交外层 `~/.hermes` 仓库里的升级监管改动；不要在 `~/.hermes/hermes-agent` 创建 commit

---

## 已知摩擦速查（用户可补充）

| 现象                                                                                              | 处置                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` 报 "No virtual environment ... `~/.local/share/uv/python`"                                   | 脚本固化了 `--python venv/bin/python` fallback，会自愈                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `hermes update` 访问 PyPI / GitHub 反复 `tls handshake eof` / `SSL_ERROR_SYSCALL`                 | `hermes_cli.env_loader` 会以 `override=True` 载入 `~/.hermes/.env`，所以仅在父 shell 临时改代理无效。先用直连与当前代理分别 `curl -I` 定性；若代理失败，把 `pypi.org,files.pythonhosted.org,github.com,api.github.com,raw.githubusercontent.com` 追加到 `.env` 的 `NO_PROXY`（保留现有条目）。直连 GitHub 也可能瞬时超时，`PATCH-UPDATE-GIT-FETCH-RETRY` 因此只对首次 acquisition 中上游 CLI 明确报告的**尚未取得目标 SHA 的早期 GitHub fetch 网络错误**做最多 3 次有界重试；一旦取得 `TARGET_SHA`，后续失败只允许 `--reconcile`，不能借网络重试推进目标。认证、分叉、安装、迁移等错误不得重试。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 首轮 updater 已拉到新源码，却在 post-pull restart / fleet 核验阶段非零退出                        | 这是 acquisition 已成功、运行态收敛尚未完成的可恢复窗口，不是“完全没升级”。先核对事务文件已固定 `TARGET_SHA` 且 `HEAD == TARGET_SHA`；禁止再次获取 upstream。若 EXIT trap 因真实 patch 冲突无法回贴，按本表 3-way 流程恢复 overlay，再运行 `bash ~/.hermes/hermes-update.sh --reconcile`，由新进程完成 patch、plist、planned restart、fleet/Doctor/verifier 闭环。2026-08-20 实抓旧进程 `line_input` ImportError；2026-08-27 从 `9aa7530f7b` 到 `8966b0a700` 又实抓官方 updater 已报告 update complete，但 fleet version check 返回空行，固定事务经一次 reconcile 完整恢复。若官方 updater 能在 post-pull 自举失败与短暂 fleet 空窗下自行恢复且稳定返回正确退出码，可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 从 shell 风格 `~/.secrets` 映射 Vertex 凭据后报 `File $HOME/... was not found`                    | shell wrapper 会展开 `$HOME`，但 `python-dotenv` 只读出字面值，`agent.vertex_adapter` 又只做 `expanduser()`，不会做 `expandvars()`。从 `~/.secrets` 注入 `~/.hermes/.env` 时必须先对路径执行环境变量 + `~` 展开并写入绝对路径，只检查文件存在性、不得把路径内容或凭据值打印到会话；终态用标准 `vertex` 真调用验证。若上游 adapter 原生支持 `$VAR` 路径展开，或 `~/.secrets` 永久改为绝对路径，可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 同一升级审计反复拉到更新的 `origin/main`                                                          | `PATCH-UPDATE-TRANSACTION-PIN` 把官方获取与本地收敛分成 `--update` / `--reconcile`：同一用户任务只调用一次前者；`~/.hermes/.hermes-update-transaction` 在失败/中断时以 `0600` 固定目标、运行态脏标记和恢复阶段，exit 0 才删除。默认无参数也是 no-network reconcile；预检禁止 `git fetch`、`hermes update --check` 和带隐式 update-check 的 `hermes --version`。事务存在时误传 `--update` 也只能接管固定 SHA。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 新增 self-test 在 `--reconcile` 中污染请求模式，误开 acquisition                                  | self-test 必须通过独立脚本进程执行，不能把 `_REQUESTED_MODE`、`_ACQUIRE_UPSTREAM`、`HERMES_AGENT` 或事务字段留在主流程；`--self-test-patch-evidence` 只启动 quick evidence，后者再分别调用 side-effect-free 的 `--self-test-transaction` / `--self-test-fetch-retry` / `--self-test-patch-gates`，不 source 主脚本。回归命令：先执行 `bash hermes-update.sh --self-test-patch-evidence`，再在无事务现场执行 `bash hermes-update.sh --reconcile`，日志必须为 `Starting local reconciliation ... (no fetch/pull)`，且不得创建 `refs/hermes-update/target`。2026-08-20 曾因 `_self_test_transaction` 把 `_REQUESTED_MODE=update` 留在父 shell，导致一次 `--reconcile` 错误固定 `c47f0b4590e`；现已修复并将该事件写入周摘要。若未来新增 self-test 修改全局 shell 状态，必须继续注册为独立入口，或显式做状态快照/恢复。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `/model` 出现未配置 provider，或配置的 AWS fallback 反而不显示                                    | 原生 `/model` 是“机器级 credential discovery + provider catalog”，不是 profile 配置视图：shell/`~/.secrets` 的 API key、auth pool、普通 `GITHUB_TOKEN` 都可能制造模型入口；反过来，非当前 Bedrock 的 IAM-role 凭据因 picker 避免 IMDS 探测而可能不显示。Gateway 还用 raw YAML 快速读取，`${VAR}` 模型值若不按 config 层展开，会出现“列表显示占位符、共享核心比较展开值”的自相拒绝。处置：`PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION` 拒绝 profile `.env` 外的已知 Hermes 环境变量并清理旧 ambient pool；`PATCH-MODEL-CONFIGURED-ONLY` 从 `config.model + fallback_providers` 动态生成并统一展开展示/可切换集合，链外和 `--global` fail closed。主动切换 primary 时 fallback 用 backend identity 跳过重复项，compression 独立配置不变。上游提供等价 profile-owned model universe 与 ambient isolation 后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 群聊仍出现 `Model fallback: ... unavailable ... using ...`，但 fallback-silence gate 全绿         | 这是 producer/consumer 契约漂移：上游把 one-shot 文案从 `Switched to fallback model...` 改成 `Model fallback: ...`，旧 regex、测试与 Step 8b gate 都只复制历史字面量，因此一起假绿。2026-08-27 SpaceSight Tech Sharing Group 实抓 Azure 连续两次 90s stale 后切 Bedrock，下一条消息引用上下文确认完整 inference-profile ARN 已作为独立 Gödel 消息投递。处置：fallback 文案由 `agent.chat_completion_helpers._format_fallback_notice()` 单点生成，生产逻辑、测试与 gate 都调用同一 producer；真实生成结果必须穿过 `_prepare_gateway_status_message`，聊天面返回 `None`、local/API/webhook 原样保留。以后同类状态不要只写 consumer 字符串 fixture。上游改用稳定结构化 status kind/metadata、consumer 不再依赖自然语言匹配后可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| 切换模型后图片/音频/视频变慢、重复分析或只剩路径提示                                              | 先区分“模型官方支持”与“Hermes capability metadata 已识别”：2026-08-16 实抓 Bedrock Opus 5 官方/真 wire 支持图片，但 inference-profile ARN 未被 catalog 识别，导致同一图片先预分析、主 turn 又调一次 `vision_analyze`；其官方 Video/Audio 为不支持，GPT-5.5 同样只支持 Text+Image，Gemini 3.5 Flash 支持 Text/Image/Audio/Video 及 PDF/text 文件。处置：按 Step 2c 多模态硬门槛对每条新 route 跑无敏感合成 canary；支持的走 native，不支持的由 `PATCH-MULTIMODAL-SIDECAR` 仅发送当前媒体 + 有界上下文给链上 capable route，STT/本地文档抽取成功则不旁路。上游提供统一、可探测且带真实 provider-wire 回归的 modality routing 后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `npm audit` 报 Desktop/build 链高危或 hermetic telemetry 超时                                     | 先按 P2 定性：Desktop/Electron/web/ui-tui 的 build-chain advisory 不在飞书 gateway 主链路上，修复需 `--force` 越 stated range 或受上游 override/lock 阻挡时不阻塞；最终报告和 README row 只留案说明“不影响飞书主链路”。每轮必须以 `npm audit --json` + `npm explain` 重新判定，不能沿用上轮包名：2026-08-16 / `8ad055414` 实测 root 仍为 6 high——`electron@40.10.2` 两条 GHSA + 其 `extract-zip` 路径遍历需越 stated range 到 40.10.6，另有 `postcss@8.5.23 → nanoid@3.3.17` 经 sanitize-html/vite 进入 Desktop/web build 链且被上游 override 锁住；doctor 分别报告 web 4 high、ui-tui 3 high。2026-09-04 实抓同机手工 audit 十余秒返回、PATCH evidence 的 hermetic 子进程却连续两次 180 秒超时；超时/非 JSON 只记 `telemetry_unavailable`，不得冒充 PATCH 回归缺失，成功解析后的 critical 仍必须阻断。若 `npm explain` 证明任一 high 进入 gateway runtime 或飞书消息处理路径，立即提升为 P0。相关链全部被上游 bump 到修复版且 registry telemetry 稳定后删除本 row。                                                                                                                                                                                                                                                                                                                                           |
| PATCH 行号漂移                                                                                    | `hermes-update.sh` Step 8 自动 rebase；摘要里写 `OLD → NEW` 即可                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Step 8d/终态重载打断飞书任务或留下旧 PID                                                          | 常规更新只用排空感知的 `hermes gateway restart`，等待预算与脚本 `gw_restart_wait_seconds()` 一致（native exit-wait budget 优先、drain 回落，+30s），并硬性核对 old PID → different new PID；不得用 macOS 上短宽限后会 SIGKILL 的 `gateway stop && gateway start`。Step 8d 后若又修了运行时代码/配置，按 Step 5b 再做一次终态屏障并在新 PID 下重跑 plugin verifier；超时则失败留案，不强杀换取表面成功。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| restart 前 cleanup policy 出现 review / required script 未跟踪                                    | `PATCH-GATEWAY-RESTART-CLEANUP` 故意 fail closed：先查看 `scripts/cleanup_transient_artifacts.py --dry-run --json` 的完整 `script_audit` / `ignored_audit`，确认新路径是必须保留、确定可清还是并发/未知产物；把理由写入 `cleanup_policy.json` 并补测试后再 reconcile。未完成事务才出现的 `.hermes-update-transaction` 是固定 `TARGET_SHA` 的持久恢复状态，必须和 `.hermes-update-transaction.lock/` 一样显式 keep；`.skills_prompt_snapshot.json` 是 manifest 校验的 0600 冷启动 prompt 元数据，也必须 keep；`.clean_shutdown` 是 Gateway 排空成功后写、下次启动消费的 graceful-exit receipt，必须 keep，删除或让其卡在 review 都会破坏 crash/restart 判定。规范 runner 预编译新出现的 `hermes-agent/website/**/__pycache__/` 属文档构建缓存，应精确列为 remove，不能把整个 website 树机械放行。禁止直接删 review、用宽泛 glob 把未知项全标 remove，或为通过 gate 把整个目录标 keep。该 row 在 cleanup policy 仍由本地外层脚本维护时长期有效；未来若上游提供等价三态治理与 restart gate，可随 PATCH 一并删除。                                                                                                                                                                                                                                                                                                 |
| 外层用 tee 记录 `hermes-update.sh` 输出后显示 exit 0，但日志末尾保留事务                          | 管道默认返回最后一个命令的状态；`tee` 写日志成功不能证明升级成功。所有带 tee 的前台/后台入口必须置于 `bash -o pipefail -c '...'` 中，并以该 shell / `wait` 的状态为权威；随后用 `--transaction-status` 复核，事务仍存在即按固定 SHA `--reconcile`，绝不能因为外层 0 再跑 `--update`。当调用器原生逐进程保留首命令退出码、不再通过 shell 管道采集日志时可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `local-patches.diff` 自身带 conflict marker                                                       | 脚本会拦截；`git restore --source=HEAD -- patches/local-patches.diff` 恢复入库版本后运行 `bash ~/.hermes/hermes-update.sh --reconcile`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Step 2 报 staged index / `Partial patch overlay detected`                                         | 这是跨会话恢复硬门禁，不是可忽略 warning：staged index 先逐项归类并用 `git restore --staged -- <paths>` 只清 index；部分 overlay 逐个对照 `--print-patched-files`、canonical bundle 与 `PATCHES.md` 吸收条件，判断是中断漏贴、手工删 hunk 还是上游吸收。脚本会在覆盖 bundle 前退出，旧完整包仍在；禁止为“继续更新”而删 bundle 或把缺项快照强行保存。若现场是全部受管文件等于 HEAD + bundle 存在，则属于可重入裸树接管，脚本会保持 EXIT trap 武装并在 8a 回放。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 手工解决 3-way 冲突后，preflight 报 `isolated full-index live diff differs from canonical bundle` | 这是 quick/full 职责倒置：人工解冲突后的完整 live overlay 在 Step 2 捕获前必然与旧 bundle 不同，若 quick evidence 先执行 `audit_bundle()`，文档规定的 `git apply --3way` → 解冲突 → `--reconcile` 路径会永久卡死。处置：`--quick` 只审四段结构、gate/专用探针、runtime contract 与 Archive 边界；bundle byte/cached/reverse/index/base 仅在 Step 2/8c 及 full/final audit 检查。`scripts/test_patch_evidence_auditor.py::test_quick_mode_defers_bundle_parity_until_full_audit` 锁定这一顺序。若未来 preflight 被重排到 Step 2 成功捕获之后，或引入独立的“resolved overlay”事务状态让 quick 能区分合法领先与篡改，可重新评估本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| final-audit 报 `current README row count ... count=2`，但同周并无重复记录                         | 版本号可以跨 ISO 周保持不变，不能用“当前 checkout 版本号全表仅出现一次”代替周键规则。处置：先按日期计算执行日的 ISO year/week，只选该周唯一 row，再断言该 row 的版本号等于 checkout；历史周使用相同版本是合法的。`scripts/test_patch_evidence_auditor.py::test_current_week_readme_rows_allow_same_version_across_weeks` 锁定该边界。若版本记录不再按 ISO 周聚合，必须与 README 周度规则和 final-audit 一起迁移后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 某个活跃 PATCH 疑似已被上游吸收                                                                   | 不依赖脚本自动标 `retired`；逐个按该块的 `上游吸收判断` 在裸 upstream 验证。完全吸收后删除其独有 hunk、移动定义块到 `## Archive — PATCH-...`，仅在文件不再被其他活跃补丁触及时移出 `PATCHED_FILES`；部分吸收则保留活跃块并收缩 hunk/四段描述，最后重跑 Step 3 闭环                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 新增本地补丁                                                                                      | 先按 Step 4 判断并入还是新增语义 PATCH；工程内补丁同步 `PATCHED_FILES`、独立 sentinel/gate、`PATCHES.md` 四段和 replay bundle/base；运行时或外层插件补丁走各自管道。不能只等下次 Step 2 自动 capture                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 用户插件 verifier 缺失或失败                                                                      | `PATCH-FEISHU-GROUP-SANDBOX` 类外层安全补丁不得继续显示升级成功。恢复 `plugins/<name>/verify.sh` 的文件/执行位，修复根配置、插件配置或上游 hook/toolset 兼容性，直到 Step 8e 对照当前 Gateway PID 返回 0；不要把外层文件加入内层 `PATCHED_FILES`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 用户插件 verifier 只测 resolver/dispatch、没穿过完整执行链                                        | 2026-08-12 实抓：`tool_search/describe` resolver 可用但 hook 误拦。2026-08-16 续审又抓到 `clarify` 已在群 toolset 却不在 allowlist、群聊继承 outsider-DM 的 vision/image 放行、飞书资源 token 无当前消息 provenance、非可信用户可删除文档，以及长 `web_extract` 虽成功却因全局 cache 被沙箱阻断而无法续读。处置：verifier 必须覆盖 YAML 精确集合、model-facing 直接工具、真实 `tool_call → underlying → hook → handler`、scope 越权反例、资源 provenance，并成对证明普通群成员 create/append/rebuild（后两者要求当前目标引用）可过、非可信 delete 被拦、可信 delete 可过；还要覆盖跨群/路径/symlink、长结果 continuation 的精确临时授权、新事件撤销和最终 PID runtime trace。运行态 trace 必须显式证明 `doc_delete_only=True`，只证明 helper、schema 或 hook 单层可用都不算闭环。该 row 长期有效，除非上游提供统一的端到端 capability/sandbox simulator 与会话级 artifact grants。                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 飞书当前消息含资源链接却被判“未引用”，或大附件回填稳定超时                                        | 2026-09-03 在 SpaceSight 国内业务交流实抓 `[标题](https://.../sheets/TOKEN)正文`：旧裸 URL 正则把 Markdown 右括号后的 CJK 一起吞入 URL，精确 provenance 因而拒绝；同日在 SpaceSight Tech Sharing Group 实抓 53.8 MiB PPTX，直接下载约 22 秒，而四个 `attachment_backfill_*` 键未从根 YAML bridge 到 adapter，运行时固定落回 8 秒并连续超时。处置：资源授权额外解析 Markdown destination，支持当前 Feishu 资源 URL/token 规范化但仍不读取 `channel_context`；配置回归必须从临时根 YAML 穿过 `load_gateway_config()` 到 adapter，本机 timeout 以 60 秒有界覆盖 100 MB 级附件，失败状态保持显式。若上游提供结构化 message link entities 与按响应体大小/进度控制的附件 deadline，可迁移后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 配置文件损坏或顶层为 list/scalar 后，凭据隔离或 configured-only 静默关闭                          | “YAML 可解析”不等于配置有效：安全策略读取必须区分“文件不存在”和“文件存在但不可读/语法错误/根非 mapping/目标 section 非 mapping”。后者统一 fail closed：ambient provider key 先 scrub，`/model` 拒绝打开 catalog。完整 configured route 若自带 endpoint/key 不依赖普通 provider resolver；同 provider/model 多 endpoint 必须有唯一 selector，不能按 model 字符串去重。回归同时覆盖语法错误、合法非 mapping、resolver 故障、重复 endpoint picker/Gateway/core switch。上游提供 schema-validated atomic config loader 与 route identity picker 后可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Feishu 附件上限只统计成功数，或 merge/PPTX 有占位符却无显式缺失状态                               | 文件预算必须在每次网络尝试前消耗，失败/超限同样计数；direct post、merge-forward、quote、sender-window 与 Drive 链接共享整 turn deadline 和 file budget。明确含资源但全部下载失败、子附件失败或 merge 查询失败时，必须注入 path-free `Do not claim` 状态。PPTX 只要页面含 picture/blip/chart/OLE 就标记视觉覆盖 `INCOMPLETE`，即使同页已有标题文字；不得只检查纯图片页。上游提供结构化资源实体、统一流式预算/deadline 与文档视觉 coverage API 后可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| MCP task 回执在 worker 中可信、写入 SQLite 后却丢失 provenance                                    | task shape 只有在 server 已协商 Tasks extension 且 handler 附加内部 marker 时可信；marker 必须随 worker 返回父线程，并通过内部 persistence sidecar 落盘，SessionDB 重开后恢复，同时不得进入普通可见 metadata。Full evidence 必须包含真实 concurrent worker → incremental persistence → DB reopen 节点，单纯 `record → attach` 同栈测试或 Step 8b grep 不足。上游原生持久化 typed task result 并拒绝普通 JSON 冒充后可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 事务锁目录已创建但 owner 尚未写入，或 final-audit 只快照 bundle                                   | 锁必须以完整 `pid + process-start fingerprint + random token` 原子发布；缺失/损坏/stale owner fail closed，release 只删除自己的三元身份。final-audit 首尾同时绑定 outer HEAD/tree、inner HEAD/tree/index/worktree/untracked、package-lock/receipt、base/bundle，并在 cleanup/runtime 后重跑 repository checks。stash apply 后也要二次核对 top OID。上游提供等价 OS lock 与不可变审计 workspace 后可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 改了 `plugins/` 后只跑 verifier、未重启 gateway                                                   | verifier 会加载磁盘插件跑测试并核对当前日志，但不会让已启动的 gateway 进程自动替换已 import 的 handler。处置：按 Step 5b planned restart，记录旧 PID → 新 PID，再在新 PID 下复跑 `plugins/<name>/verify.sh` 和 `hermes gateway status`；这类 row 长期有效，除非插件热重载机制能证明代码对象随文件变更自动替换。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| planned restart 后 verifier 立即查 MCP 注册出现短窗误报                                           | 2026-08-18 实抓：Gateway 真实子进程先打印 `sandbox: registered (pid=...)`，HyperTeX stdio discovery 约 5s 后才打印 `mcp__hypertex__tasks_get/update/cancel`；Step 8e 单次 grep 在两者之间执行，把健康启动误报为能力缺失。处置：先用当前真实 Gateway PID 定位 sandbox trace 行，再只在该行之后做最多 10s/0.5s 间隔的有界等待；禁止匹配旧进程历史 MCP trace。该 row 在 MCP discovery 仍为异步启动时长期有效；若未来 Gateway readiness 信号已包含全部 MCP server registration，可删除等待并退役本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 补丁整体 apply 失败（上游真实冲突，脚本已回滚）                                                   | 手工 `cd hermes-agent && git apply --3way ~/.hermes/patches/local-patches.diff`，解决带 `<<<<<<<` 标记的文件（多为"并存"型：上游新增与补丁插入同位），`git add <冲突文件> && git restore --staged -- <所有 staged patch 文件>` 只清 index，然后运行 `bash ~/.hermes/hermes-update.sh --reconcile`——Step 2 会从工作树捕获已解决的 diff 并围绕固定 `TARGET_SHA` 走完整验证，不再获取 upstream。若宿主安全策略拒绝 `git restore --staged`，先用 `git diff --cached --name-only` 人工确认 staged 全部属于本次 patch；确认后可用 `git read-tree HEAD` 仅把 index 恢复为 HEAD，工作树中的冲突解保持不变，若存在任何非 patch staged 项则必须停止。zsh 中循环/轮询变量不要使用 `path`、`status` 等特殊参数名：`path` 会联动覆盖 `PATH`，`status` 是只读参数；统一使用 `patch_file`、`gw_status` 等任务专用名。注意：`git apply` 输出别接 `head` 截断，SIGPIPE 会中断 apply。该 fallback 在宿主允许标准 restore 后可删除。                                                                                                                                                                                                                                                                                                                                                                                              |
| `package-lock.json` 在 npm audit fix 后 dirty                                                     | 本机 npm 可能归一化 workspace 布局 / `peer` 标记，也可能把传递依赖推进到 audit 可用的补丁版本。每轮必须先审查实际 diff：确认 `package.json` 无意外语义变化、记录版本升降和剩余 advisory，再把可解释的 lock drift 保留在内层工作树且排除出 replay bundle；不得一律按“无版本变化噪音”跳过。final-audit 只允许这一条额外路径，且要求它是 unstaged、JSON 可解析，并由 `patches/package-lock.review` 精确绑定当前 `HEAD:package-lock.json` blob SHA 与工作树 SHA-256；任一 SHA 不匹配、receipt 格式错误或 package.json 同步出现未登记语义变化都 fail closed。若未来 npm/updater 不再产生可解释 drift，或 lockfile 被纳入独立持久化通道，可收紧回零并删除本例外。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Doctor 提示 `npx playwright install` 但根 CLI 不存在                                              | 根 `npm install` 后先检查 `node_modules/.bin/playwright` 与各 workspace 的 `.bin/playwright`。当 Playwright 仅由 Desktop workspace 安装时，根 `npx playwright install chromium` 会报 `playwright: command not found`；使用同一 lockfile 已安装的 `apps/desktop/node_modules/.bin/playwright install chromium`，然后以 `hermes doctor` 的 `Playwright Chromium` 转 ✓ 为终态验证，不为此新增根依赖。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `test_approval.py` 的 verifier temp cleanup 测试在 macOS 失败                                     | 上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 对 temp_dir 做 `realpath`（`/tmp`→`/private/tmp`）而 operand 不做，Darwin 上恒不匹配，其自带测试预期失败；裸上游同样失败、与本地 patch 无关。由 `PATCH-APPROVAL-DARWIN-TMP` 仅对 `/private` 系统别名放行 raw 拼写，其余 symlink 保持 fail-closed。上游统一 realpath 后归档该补丁并删除本 row                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `test_feishu.py` 的 SSRF connect-time rebind 测试偶发失败                                         | 真实原因（2026-07-29 定性，推翻旧"跨文件状态"结论）：上游测试只 blank 代理 env 变量，httpx `trust_env` 在 env 为空时经 `urllib.request.getproxies()` 回落 macOS **系统代理配置**——宿主 Clash 系统代理开着就必失败（守卫按设计把解析委托给代理，收到裸 `httpx.ConnectError`），关着就通过，与批量/单跑无关；裸上游同样失败，与本地 patch 无关。已由 `PATCH-FEISHU-SSRF-TEST-SYSPROXY` 在测试内补 `patch("httpx._utils.getproxies", return_value={})` 修 hermetic；上游吸收后归档该补丁并删除本 row                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| MCP SDK 主版本升级后本地 extension 仍使用旧字段、非正式请求类型或错误的结果入口                   | 2026-08-19 从 MCP 1.28.1 升到 2.0.0 后实抓三层兼容问题：① Pydantic 模型把 `CallToolResult.isError` 属性改名为 `is_error`，camelCase 只保留序列化 alias；② SDK 2.x `ClientSession.send_request()` 在序列化前读取 `type(request).name_param`，generic `RootModel` 会让所有 task-aware tools/call 在到达 server 前报 `AttributeError: name_param`；③ 即使 caller 传 raw result model，SDK 2.x 仍先按 negotiated core surface 校验 server result，handshake-era `tools/call` 只接受普通 `CallToolResult`，所以 server 已创建 task 后 `resultType=task` 会因缺 `content` 假失败。处置：错误字段双拼写读取；tools/call 始终使用 SDK 正式 `CallToolRequest`，只有 custom task methods 用显式 `name_param=None` 的 raw request；仅对“server 广告 Tasks + handshake-era + SDK 2 dispatcher/stamp 可用”走 scoped raw dispatch，完整保留 protocol stamp、request-class name metadata、timeout 与 TTL 处理后再严格验证 task 或普通结果，现代协议与 SDK 1.x 不绕行；结果校验优先公共 `validate_tool_result`、回落旧私有方法。测试必须同时覆盖请求类元数据访问和真实 SDK 2.x `ClientSession` 的 legacy prevalidation，不能只 fake `send_request()` 或保存 `model_dump()`。上游原生吸收 `PATCH-MCP-TASKS-ASYNC-HANDOFF`、SDK 为 legacy extension 提供公开 result-claim 入口，或 extension 不再自行构造请求/结果后删除本 row。 |
| MCP stdio 正常启动却立即报 `subprocess ... has exited`，或每次调用产生未 await watcher 警告       | 先核对 MCP stderr 的启动/初始化、agent fast-fail 时间和随后 idle recycle，不能把 1–2 秒错误当作工具 timeout 或服务崩溃。PID aggregate liveness 已由 upstream `98fce8e52d` / `2663117f72` 修正，并由 `ef46ec03e1` 覆盖 alive/dead/mixed、watcher consumer 与 probe fail-open；本地对应 hunk/重复测试已在 v0.20.6 升级中删除。当前剩余缺口是 RPC 路径先调用 `_watch_children()` 做 awaitable 探测、随后又调用一次交给 `ensure_future()`，第一支 coroutine 泄漏；`PATCH-MCP-STDIO-WATCHER-LIFECYCLE` 仅保留“一次实例化、同一 awaitable 被调度”的最小修复和 `-W error::RuntimeWarning` 回归。上游修正 watcher 单次物化并补调用次数/RuntimeWarning 测试后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| MCP task 查询把 job/case ID 当成 taskId                                                           | 2026-08-20 财务群实抓：用户明确问“任务 8”，模型却从 case 列表取 `job 99` 调 `tasks_get(99)`；真实映射是 task `8` → jobs `99/100` → case `103`。Data Pipeline 的 task `9` 传参正确，首次超时后同一 ID 后续正常，证明两类故障不能混判。处置：Tasks utility schema 必须要求 exact taskId、用户点名时逐字复制并明示 job/case/run ID 不可替代；若 server 对只读 `tasks/get` 的 JSON-RPC error 提供唯一 `suggestedTaskId`，Hermes 仅重试一次该读请求，`tasks/cancel` / `tasks/update` 永不自动纠正。测试覆盖建议 ID 重试和 mutation 反例。上游提供等价的 task-handle provenance/typed lifecycle schema 与安全只读纠错后删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 截断重试日志显示提高 output cap，但 native transport 的 wire 仍用旧值                             | `_ephemeral_max_output_tokens` 是一次性跨重试状态，新增/重构 API mode 时必须逐分支确认它被请求构造消费并立即清空；不能只测 conversation-loop 设置了字段。2026-08-22 审计发现 Anthropic/Chat Completions 已消费，但 Bedrock Converse 与 Codex Responses 仍传 `agent.max_tokens`，使 8k/16k/32k 日志与真实请求不一致。处置：两条 native 分支都优先传 ephemeral cap 并清空，Step 8b 运行 `test_bedrock_consumes_ephemeral_output_cap` 与 `test_codex_responses_consumes_ephemeral_output_cap`。当上游统一 output-cap 组装为单一、覆盖全部 transport 的入口后，可收缩本 row 与本地接线。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| HyperTeX MCP 调用侧重新暴露或猜测内部执行路由                                                     | 2026-08-28 契约复核：MCP 只公开提交、修订、任务状态、版本、交付物和已清洗错误；执行器身份、模型/provider、会话、权重、路由决策及诊断元数据均为 WebApp/worker 私有信息。Hermes 只启用 `hypertex_create_case`、`hypertex_iterate_case` 与只读 `tasks_get` 工作流；skill 不得询问、推断或复述执行路由，sandbox 对旧客户端或模型幻觉产生的 `agent`/`model`/`provider`/`executor`/`routing` 参数做防御性删除，只固定 `hermes` contributor、new case `freestyle` 类型和安全暂存附件。最终 Gateway trace 必须含 `hypertex_routing_policy=server-owned/non-observable`。若未来 HyperTeX 公开契约变化，按最新 schema 重新审计，不能从内部日志或旧字段恢复调用侧路由认知。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| `hermes update` 的 runtime repair（E-949）整体重建 venv                                           | 2026-07-25 首现：SQLite 缺陷版本触发私有 runtime 重建，只按 uv.lock 装包——dev 工具链、`PATCH-FEISHU-SOCKS-DEPENDENCY` / `PATCH-DOCUMENT-EXTRACTION` 的依赖 pin、文档/STT/平台 lazy 栈可能丢失；lazy refresh 又可能在补丁还原态误判 current。补救（常设授权，Step 2b 当轮自动执行）：补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"` 恢复 lazy 栈，再恢复 pytest 工具链；旧 venv 停放 `venv.stale.runtime-*`，旧进程退净后可删。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| GitHub HTTPS `LibreSSL SSL_ERROR_SYSCALL` / connect timeout                                       | 先用 `curl` 与 `ssh -T -p 443 git@ssh.github.com` 区分网络和 Git TLS 故障；SSH 443 可用时，用进程级 `GIT_CONFIG_COUNT/KEY/VALUE` 注入 `url.ssh://git@ssh.github.com:443/.insteadOf=https://github.com/`，不要永久改 remote。若首次 acquisition 已取得 SHA，后续只能 `--reconcile`；若它在 3 次 transport retry 后仍是 `phase=acquiring / target_sha=pending`，按脚本 recovery clause 恰好再用一次带该进程配置的 `--update` 接管同一 acquisition。上游 CLI 会把 rewrite 后的等价 URL 误判为 fork：拒绝新增 `upstream`，收尾确认 remote URL 未变、`HEAD == TARGET_SHA`，并删除交互在调用目录产生的 `.skip_upstream_prompt`。2026-08-16 实例即由 HTTPS 75s connect timeout 改走 SSH 443 后固定 `8ad055414`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Feishu 普通引用回复 lane 与上游 metadata 驱动语义对撞                                             | **高危语义冲突**（post-26e0b1c）：上游 `reply_in_thread = bool(metadata.thread_id)`（metadata 驱动投递 lane）与 `PATCH-FEISHU-NORMAL-REPLY` 的"固定 False、忽略 generic thread metadata"方向相反，同一 send/reply-body 区域的 3-way 结果不可信任自动合并。必须人工按本地不变量重解（普通引用永不进 thread lane），复验补丁自有三条路径回归后才能刷新 bundle；详见 PATCHES.md 该补丁块对撞警示。**同一 conflate 有入站侧孪生**（2026-08-12 起）：入站 `thread_id = ... or root_id` 由 `PATCH-FEISHU-QUOTE-CHAIN-SESSION` 单独守护——`root_id` 是引用链根而非话题 id，回退它会让每条引用链切出独立 session。两侧必须一起复核：3-way 触及 `plugins/platforms/feishu/adapter.py` 后同时核对出站 `reply_in_thread = False` 与入站不含 `root_id` 两个锚点。2026-08-12 实测本轮上游未触及该文件，预案未被消费、继续有效。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |

| config 迁移一次性重置用户可见状态（如 v34 personality reset） | 迁移本身属 P0 当轮执行（`hermes doctor --fix`），但遇到"上游有意重置用户状态"的迁移时**不回写旧值**——那会复活迁移要消灭的歧义态。记录旧值与官方恢复命令，在最终报告显著提示由用户决定是否恢复。v34 实例（2026-08-10）：`display.personality: kawaii → none`（该值自 2026-04-15 初始提交未变），恢复用 `/personality kawaii`；迁移伴随的 YAML 引号/列表风格重排为语义无变化噪音。 |
| `hermes doctor --fix` 报 `platform 'X' references unknown toolset` | 该校验（`hermes_cli/toolset_validation.py`，#38798 动机）仅在 `--fix`/迁移路径运行，普通 doctor 不报。先分流：**插件运行时注册名**（如 `sandbox_group`）在 CLI 上下文未加载网关插件属预期误报，不修；**真实死条目**（如 `vision_tools`——注册名实为 `vision`，`resolve_toolset` 恒返回空）按群聊工具两层一致原则处置——沙箱 allowlist 本就不放行的能力直接删条目（运行时行为零变化），确需该能力才改正名并同步 allowlist。凡触及 `plugins/sandbox/verify.sh` 期望契约的改动必须复跑 Step 8e verifier。2026-08-10 已删 `vision_tools` 死条目。 |
| doctor 报 `⚠ browser (system dependency not met)` 而 agent-browser/Playwright 均 ✓ | Browser Use CLI 模式的表象而非依赖缺失：`browser.backend` 未设时，只要 browser-use CLI"可运行"（含仅有 `uvx` 在 PATH，首用才从 PyPI 临时拉包）即接管默认后端（上游 `a1835c8c1`/`8d8bc85dc`，2026-08-11 起），内建 browser\_\* 整体隐藏、由 `browser_exec` 替代。本机以 `browser.backend: 'off'` 锁回内建工具（YAML 值必须加引号，裸 `off` 会被解析成布尔 False 走回默认判定）；启用 Browser Use 属引入全新依赖，须用户明确 opt-in 并本机验证。用户启用后或上游改为要求真实安装二进制时，删除或改写本 row。 |
| 改了 `config.yaml` 的群聊能力面后 Step 8e verifier 失败 | `plugins/sandbox/verify.sh` 对**群可读 skill allowlist**（`skills.platform_allowed.feishu_group`）、群 toolset 集合与固定 Feishu script action 集做**精确相等**断言，不是子集断言。这是刻意设计：扩大群聊可读/可用面必须是显式且被验证的动作，不能靠改一处配置静默生效。2026-08-12 实抓：给 `config.yaml` 增开 `excel-processing` 未同步 verifier，整轮升级非零、事务保留。处置：先判定该能力是否真的不扩大工具面（本例 `excel-processing` 只有 `scripts/`，而群聊无 `terminal`/`process`/`code_execution`、`feishu_doc_manage` 只映射 `feishu_doc_scripts_root` 下固定 action，故只读知识、不扩面），把结论写进 verifier 断言旁的注释再同步契约；若该能力**确实**新增可执行面，必须同时评估沙箱 allowlist 与 `PATCH-FEISHU-GROUP-SANDBOX` 的边界描述。凡改动 `config.yaml` 的 `skills.platform_allowed` / `platform_toolsets` / `plugins/sandbox/config.yaml` 三者之一，都要预期本 verifier 需同步。上游无关，本 row 长期有效，除非 verifier 改为子集语义（那会削弱边界，不应主动做）。 |
| Agent/CLI 更新后飞书文档图片或封面入口仍可发现，但上传/PATCH 适配已失效 | 2026-08-29 将生成图片、生成图表及当前 turn 图片附件接入 `feishu_doc_manage` 后，不能只验证 schema 里还看得到媒体 action：本地 CLI、Gateway tool bridge 或飞书 SDK/API 元数据变化都可能让固定 argv、附件 provenance、`docx_image` 上传点、`drive_route_token`、`replace_image`、`update_cover` 或 runtime 注册中的 action 集单独漂移。处置：`PATCH-FEISHU-GROUP-SANDBOX` 的 Step 8e verifier 必须精确断言十个文档 action、图片来源字段、20 MiB 上限与当前 Gateway `doc_media_actions` trace；同时运行文档图片、远程 staging、回读占位识别与 sandbox 行为回归。真实主会话已证明“入口可用、调用成功”仍不足：只传 `width` 会让 Feishu 保留源 `height` 而产生竖向留白，schema 允许的 lowercase palette alias 也可能在 Matplotlib 处失败，顶部 legend 还会被 `tight_layout` 当作大块垂直占位。图内 `best` 无遮挡时应优先保留，发生 artist 碰撞后才按横图右置/竖图下置并限制外置占比；外置 legend 已参与 `tight_layout` 时不得再固定切走 18%–20% gutter，标题也不得同时由显式 rect 与 suptitle layout 重复占位。笛卡尔图默认必须同时显示 X/Y major grid，并显式开启底部 X / 左侧 Y major ticks，不能依赖 Seaborn style 的隐式 tick 可见性；X/Y tick-label 带宽上限统一为绘图区对应尺寸的 20%，完整文本优先通过旋转、换行和降低刻度密度适配，不得用省略号制造一排无意义的同前缀标签。不得把外部 `lark-cli` 作为运行时依赖；它只作为上游契约参考。任一哨兵或行为失败均使升级非零，不允许因普通文档读写仍绿而放过媒体能力退化。若未来 Hermes upstream 原生提供同等受控的文档媒体工具，且 Step 8e 改为直接验证其公开接口及真实运行态，可迁移后删除本 row。 |
| 飞书文档已含图片、模型也传了 `asset_paths`，但 HyperTeX case 显示 `Staged 0 MCP assets` | sandbox 过去会无条件以“当前入站消息附件”覆盖模型提交的 `asset_paths`；引用文档但未重新附图时 `media=0`，因此安全层静默把素材清空。可信群现可提交当前群隔离 workspace 内的受控文件；owner DM 则必须先用 `feishu_doc_manage(action="read_url", include_images=true)` 把 docx/wiki 图片重新导出到 `private_doc_workspace_root/<chat-id-hash>/`，再消费 `[DOCUMENT_IMAGES]` 中的相对 `image_path`。两条路径都要经过 realpath containment、symlink、普通文件、单文件大小、总数量检查并复制进 HyperTeX 私有 staging；任意宿主/跨会话路径明确拒绝。**不要为兼容一次性手工产物把旧 `tmp/hypertex_doc_assets/` 纳入信任根**：2026-09-01 首轮修复虽通过单测和 runtime verifier，真实主会话仍复用了旧绝对路径并被拒，证明正例只覆盖新 workspace 不足；回归必须同时包含 owner fixed-reader 正例、chat-hash workspace → staging 正例、旧手工根与任意外部路径反例。当前 operator 边界为单轮 20 个、每个 100 MB，21 个或单文件超限必须 fail closed；飞书文档图片上传与远程图片 staging 仍保留独立 20 MiB 限制。若未来上游提供带 same-turn provenance 的 owner/group 文档媒体句柄并由 HyperTeX 原生消费，可迁移后删除本 row。 |
| 主会话重绘请求失败，看起来像“三档图片 fallback 全挂” | 2026-08-30 真实主会话 `20260825_214025_ed84285b` 中，请求在任何 `secure_image_generate` / `secure_chart_generate` 工具调用前就失败，不能归因于媒体模型。实际主推理链逐档为：Azure GPT-5.5 首次连接已建立但 120s 无首字节、第二次 ConnectError；Bedrock Claude Opus 5 已激活但连续 3 次各 300s 无 stream event；Vertex Gemini 3.5 Flash 在 credential/project 解析时遭 `ConnectionResetError`，当轮不可用。该请求携带 384 条消息、约 333k tokens、1.20 MB serialized body，虽未达到 700k compression threshold，却会放大 TTFB 与跨 provider 传输成本；随后同机 Feishu WebSocket ping timeout、HTTPS SSL EOF 进一步证明是广域网络抖动。处置：先看是否存在媒体工具 receipt；没有 receipt 时只诊断 Agent provider chain。网络恢复后重试，长主会话优先 `/compact` 或新会话携带目标文档链接，避免重复发送 300k+ 上下文；不要因此修改图片模型 fallback。若未来 Gateway 为每次失败返回结构化 route-attempt telemetry，并能在大 payload fallback 前自动做可靠 compaction，可删除本 row。 |
| MCP `tools.include` 新增工具后 verifier 或真实群聊出现“可发现但必拒绝” | MCP server include 会先把新工具注册进共享 toolset；即使 sandbox `pre_tool_call` 最终拒绝，群模型 schema / `tool_search` 仍可能看到它，形成能力面漂移和无效调用。2026-08-22 实抓 `hypertex_list_case_types`：根配置已启用，插件 allowlist 与 `_HYPERTEX_TOOLS` 未同步，Step 8e 精确契约非零，真实群聊也先发现再被 0.00s 拒绝。处置：先审计返回数据敏感度与副作用；若应对群开放，必须同步 MCP include、插件精确 allowlist、hook 分类、skill 说明、正反例和 runtime trace，并复用已有 trusted chat/actor/one-call 门禁；若不应开放，则必须用真正的 session/toolset schema 过滤移出群模型面，不能满足于“调用时会拦”。当上游提供稳定的 per-platform/per-session MCP 单工具 schema exclude 后，可改用原生隔离并删除本 row。 |
| cleanup 审计把 `config.yaml.corrupt.*.bak` 判为 review | 这是 Hermes 配置解析/恢复留下的 operator-owned 回滚证据，不是可再生缓存；未知即阻断 restart 是正确行为，但不得为了过 gate 删除它。将该模式显式加入 `cleanup_policy.json` keep，并在 `test_cleanup_transient_artifacts.py` 锁定；仍未知的其他 `*.bak` 继续 fail closed，不做宽泛白名单。若上游为配置恢复快照提供独立受管目录与生命周期，可迁移后删除本 row。 |
| upstream 新增 `spawn-ledger.json` 后外层仓库出现未跟踪运行态文件 | v0.20.6 的 process identity layer 在 machine Hermes root 持久化 `(pid, create_time, purpose, spawner)`，供 updater/Desktop 在无法读取进程环境时安全识别与回收 Hermes 子进程；损坏账本会被隔离为 `spawn-ledger.json.corrupt`。这是必须保留的运行态状态，不是提交资产或可再生缓存。处置：精确加入 `.gitignore`，并把 `spawn-ledger.json*` 登记为 cleanup policy keep、补主文件与 quarantine 回归；不得把通配扩大到其他 JSON。若 upstream 将账本迁入既有已忽略 runtime 目录，或不再使用文件账本，可同步删除本 row、ignore 与 policy 条目。 |
| PATCH evidence 缺少本补丁测试/实际 probe 却被相邻结果借绿 | 旧 `scripts/test_patch_evidence.py` 在验证段没有测试 token 时，会从 PATCH ID 周围固定字符窗口寻找任意 `test_*`；相邻 gate 足以制造假阳性，且裸文件名 typo 也未验证。后续版本虽补了 pytest node/owned-file 约束，但完整 node ID 一度仍退化成裸函数解析，单个 PATCH test file 零 collect 可被总数掩盖，Archive/dedicated pytest 也只看退出码而接受 skip/xfail；runtime/dedicated/archive/external 则曾靠“分类表 + 手写 main 调用 + 无条件 passed”拼接，新 PATCH 可登记后漏执行；canonical runner 的默认 file retry 还会把首轮红、二轮绿洗成 exit 0。处置：工程 PATCH 显式绑定真实测试路径/函数，完整 node 精确匹配，所有 PATCH test file 至少 collect 一个 node；非 pytest PATCH 的 classification/artifact/probe key-set 必须相等，由统一 registry 自动逐项调用并把本轮回执写入 `probe_results`，full 缺回执即失败；Archive/dedicated 探针用 strict JUnit；Step 8e verifier 数组与 external registry 同集；Step 8b gate header 每块只能激活一个未重复 gate，映射全集等于声明全集；终态 canonical 固定 `--file-retries 0`。负例至少覆盖删/拼错测试名、完整 node 错路径、单文件零 collect、Archive skip、runtime 漏 probe、external 清单漂移、full 提升未执行 probe 与 FLAKY 绿输出。若未来注册表迁为机器可读 schema，可把这些关系整体迁入 schema 后删除本 row。 |
| pytest 后台线程或对象终结器异常只发 warning，PATCH/canonical 仍计为 passed | 2026-08-29 升级到 `e387cbc0aa` 时，`test_direct_session_db_flushes_share_marker_claim` 的 `_BarrierDB` 未跟进上游新增的 `SessionDB.flush_token_counts()`，工作线程抛出 `AttributeError`，pytest 主断言仍通过并只发 `PytestUnhandledThreadExceptionWarning`；后续深度 fault injection 又证明 `__del__` 抛异常、未 await coroutine、测试函数错误返回非 `None`、测试类部分未收集，分别产生 unraisable、`RuntimeWarning`、return-not-none 与 collection warning，都会被旧严格探针接受为 passed。若只看 exit code、JUnit testcase outcome 或 passed 数会形成真实假绿。处置：补齐 fixture 的 no-op `flush_token_counts()`，并由 `hermes-update.sh` 的直接 smoke gates、`scripts/test_patch_evidence.py` 的逐 PATCH/Archive/dedicated pytest、`scripts/final_upgrade_audit.py` 的 canonical runner 和 `plugins/sandbox/verify.sh` 统一把五类 warning 提升为错误；runtime/external probe 还要求发现的直接 pytest 调用数等于可审计命令数，并逐命令校验没有漏掉任一过滤器，`test_patch_evidence_auditor.py` 分别用真实后台线程、对象终结器、未 await coroutine、返回值伪断言与部分 collection fault injection 证明旧行为会被拒绝。若未来 pytest 默认把这五类执行完整性异常都作为失败且所有受管 runner 可证明继承该默认值，可删除显式 warning filter 与本 row。 |
| PATCHES 已列齐所有 overlap 路径，但摘要里的路径计数仍可写错 | 2026-08-29 收尾轮询发现：presence gate 能证明 35 条相交路径都在摘要出现，却没有复算“26 active/28 path、7 Archive/12 path、去重 35”这 5 个数字；文档一度误写 19/11/33 仍通过终审。处置：`final_upgrade_audit.py` 从逐 PATCH evidence 分别重算相交 PATCH 数、active/Archive 唯一路径数和 union，并强制匹配 PATCHES 当前摘要；auditor 注入错误 union 数必须失败。若未来当前摘要完全由 evidence 机器生成且不再手写这些计数，可删除此门禁与本 row。 |
| 重写 `PATCHES.md` §「最近一次升级」摘要后活跃 PATCH 少一个 | 2026-08-11 实抓：按 `s.index("\n---", i)` 定界旧摘要会**跨过紧随其后的 `### [PATCH-*]` 定义块**（摘要与下一个补丁块之间的 `---` 不是摘要的结束符），一次替换静默吞掉 `PATCH-SKILL-CREATE-ROOT` 整块，Step 5 第 3 条断言（活跃块数 vs 注册表口径）才暴露。改写摘要时定界必须用**下一个 `### [PATCH-` 标题**而非 `---`；**且该标题必须锚定行首**（`re.compile(r"^### \[PATCH-", re.M).search(s, i)`）——2026-08-12 实抓续集：裸 `s.index("### [PATCH-", i)` 会命中「活跃补丁」段落里的**行内字面量** `` `### [PATCH-*]` 定义块 ``（该句就在摘要自身内部），使定界点落在摘要中途、`rindex` 找不到分隔线而抛 `ValueError`。写前抛错是幸运情形（本次未落盘）；若字面量出现在分隔线之后就会静默截断。若已吞块，从 `git show HEAD:patches/PATCHES.md` 取回该块按原顺序插回，再复跑 Step 5 断言。上游吸收无关，本 row 长期有效，除非摘要节与补丁定义节被拆成两个文件。 |
| Feishu 日志显示 open_id，但群聊授信仍报“不是维护者” | `adapter.py` 的入站日志用 `open_id or user_id` 展示发送者，实际 `SessionSource.user_id` 却用 `user_id or open_id`；因此“日志 100% 是 `ou_`”不能证明运行态鉴权也使用 open_id。2026-08-20 现场即为同一事件日志显示 `ou_33ee…`、沙箱 actor 实为 `5397e1a2`，在授信名单收敛为单一 open_id 后导致 Data Pipeline Workshop 连续 8 次 HyperTeX 调用于 0.00 秒本地拒绝。**处置**：sandbox 的 `pre_gateway_dispatch` 从原始、已签名 Feishu sender 对象收集 `open_id/user_id/union_id`，授权对精确 ID 集合做交集且不使用姓名；配置仍只登记 people.yaml 的 open_id。`pull_feishu_people.py` 同时拉取并校验每位员工的 tenant user_id，缺失或重复即整轮中止，people.yaml 保留 open_id+user_id 供审计。**判定**：拒绝日志现在带 `actor_ids=[…]`，可直接看三种形态；若其中已有允许的 open_id 仍被拒绝，才是新回归。**退场条件**：上游 SessionSource 原生保留全部平台身份并为插件提供稳定集合后，本地 raw sender 归一可删除。 |
| 活跃 PATCH 定义误放进 Archive、再用续接标题接回 | 2026-08-15 实抓：`PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY` 状态、源码 hunk、Step 8b gate 和回归都仍活跃，却夹在两个已归档模型补丁之间；随后再开一个活跃续接标题，导致文档阅读顺序与生命周期边界错位，且“首个 Archive 前定义数”只有 32、注册表/README 却写 33。处置：所有活跃定义连续放在首个 Archive 前并按职责类别分组，所有 Archive 统一后置；Step 5 同时断言不得出现续接标题，并检查 Archive 下带状态表的定义只能是“已归档/已上游合并”。若未来 PATCH 注册表拆成机器可读索引 + 独立定义文件，可按新结构改写或删除本 row。 |
| PATCH evidence 的文件/进程/吸收矩阵只做宽松关联 | 2026-08-27 第二、三轮负向审计发现：路径子串可冒认 ownership，active PATCH 可零受管文件，Archive gate 可错绑，多个 PATCH 共用 pytest 进程时后台线程可串证据，纯 import 可冒充行为执行，旧/非祖先升级范围也能继续产出“当前”overlap；Archive 定义一旦退出当前 `PATCHED_FILES`，其 upstream 路径相交还会被旧算法静默忽略。处置：ownership 只认反引号完整路径；非 runtime/external 的 active PATCH 必须拥有受管路径；active/Archive gate header、唯一置绿变量与 8c consumer 一一对应；每 PATCH 独立 pytest 进程且忽略 `<module>` trace；Archive overlap 直接匹配其声明路径；PATCHES 当前摘要登记每个 overlap PATCH 的显式 verdict 和无 overlap 数；evidence range 必须是 ancestor→当前 HEAD。若未来 PATCH 注册表迁为机器可读 schema，应把 owner、gate、verdict 和 evidence node 全部并入同一 schema，再删除本 row。 |
| final-audit 全绿但测试已改写真实 `gateway_state.json` | canonical 测试会在 fixture 后执行 `patch.dict(os.environ, {}, clear=True)`；旧隔离只靠 `HERMES_HOME`，环境被清空后动态状态路径回退生产根，2026-08-27 实际留下了 pytest PID，但旧 final-audit 只看 live PID 查询而未核对持久状态文件。处置：`PATCH-TEST-RUNTIME-STATE-ISOLATION` 在 autouse fixture 中直接钉住 Gateway status 与 spawn-ledger 路径；final-audit 在 canonical 后复跑 sandbox，并要求 `gateway_state.json` 的 PID/start-time/argv/code SHA 属于 cleanup 后仍存活的当前 Gateway、spawn ledger 无 pytest 记录，同时再次验证 bundle，并比较审计前后外层 tracked/non-ignored-untracked fingerprint。若 upstream 测试隔离原生覆盖所有 process-state chokepoint 且 final audit 持续核对运行态身份，可归档本 row。 |
| 更新后 launchd 下位于 Desktop/Documents/Downloads 的 stdio MCP 入口卡在握手超时 | macOS TCC 把受保护目录授权绑定到进程身份；updater 首次把 uv-managed `venv/bin/python` 符号链接物化为稳定 anchor 后，旧解释器路径已有的目录授权不会自动迁移。典型证据是交互 shell 中同一 MCP 握手秒回，launchd Gateway 日志只有 `CancelledError`，`mcp-stderr.log` 只有 server header，进程采样显示入口 shell 阻塞在 `open()`，而 TCC 数据库尚无新 anchor 的 allow 记录。不得修改 TCC 数据库、放宽 runtime verifier、移动用户工程或保留未经验证的 interpreter workaround；等待用户在系统设置中允许新的 `venv/bin/python` 访问对应目录（或授予 Full Disk Access），确认 TCC allow 后执行排空感知 restart，并要求同一真实 Gateway PID 下出现完整 MCP 注册回执。若 upstream 能在 anchor 迁移前检测并引导受保护目录授权、或 stdio MCP 不再从受保护目录启动，可删除本 row。 |

| 横图仍出现顶部 legend，或群聊新建文档后不能立即插图/设封面 | 两者都是“schema 可见但运行时契约不闭合”：模型可主动传 `legend_position=top` 绕过 auto 的图内/横右/竖下预算；群文档 `create` 的成功 token 又未进入只从入站消息构造的 provenance。首轮修复只把 token 写进 `post_tool_call` 所在线程的 ContextVar，日志虽显示 grant，下一次工具调用换到复制的 worker context 后仍会 `target_not_referenced`，同线程单测因此假绿。处置：工具 schema 不再暴露 `top`，renderer 对旧 `top` fail-safe 归一为 `auto`；create grant 改为由 hook 自带的 agent `turn_id` 与 chat ID 联合索引的线程安全短期 capability，pre hook 再把同一 turn ID 注入隐藏 handler 参数，失败结果、其他工具/文档和下一 turn 均不授权，图片来源边界保持不变。回归必须用两个独立 `copy_context()` 穿过真实 `handle_function_call(tool_call → underlying)`，同时覆盖旧 top 不再返回 top、成功 create 后精确 token 可写及下一 turn 反例。外层插件变化不会进入内层 `runtime_dirty` 判定，因此注册回执还必须同时绑定真实 Gateway child PID 与 `plugin.yaml` 版本；漏重启时 Step 8e 必须拒绝假绿。注册回执可能在 full audit 期间跨过 5 MiB 日志轮转边界，verifier 必须扫描 `agent.log` 与轮转文件、按时间选择当前 PID 的最新回执，并只接受该回执之后的同 PID MCP Tasks 注册。若未来 upstream 提供不可绕过的 legend policy、原生 per-turn resource capability 与外部插件 generation/version attestation，可迁移并删除本 row。 |
| 同一 Feishu turn 的版本表仍新增多行，或柱顶数字越过绘图区 | 真实主会话的入站消息经文本 batch 后丢失 `platform_message_id`，以 `HERMES_SESSION_MESSAGE_ID` 作为版本键时 ledger 根本不创建；同一 turn 的 rebuild/cover/insert 因而各写一行。图表侧先给 value label 增加 headroom，随后显式 `y_max`/`x_max` 又覆盖该范围，最大值标签被推到 axes 外。处置：owner terminal 对固定飞书文档脚本使用 `pre_tool_call` 已有的内部 agent `turn_id` 注入版本环境，群固定脚本也从隐藏的同一 turn 参数取值；不依赖平台 message ID。renderer 在最终 `tight_layout` 后按实际像素检测 bar/waterfall/lollipop 数值标签，只扩展对应数值轴直到标签回到绘图区，并以 `value_label_layout` 回报前后越界数。若 upstream 原生提供稳定 turn ID 子进程桥与 annotation-bound layout，可迁移并删除本 row。 |
| 飞书文档创建成功，但 sourced 图片显示“无法导入该图片” | 飞书 Markdown import 会自行抓取 `![alt](https://...)`；远程 CDN 图片即使当前 HTTP 200，import task 仍可能整体成功却把图片替换为固定错误位图。旧 `read_url` 忽略 image block，Agent 因而把文本回读和后续本地图表上传误当成全部图片成功。处置：create/append/rebuild 禁止 Markdown/HTML 图片语法；公共图片先经 `stage_image_urls` 在当前群 workspace 做 HTTPS、credential、SSRF/redirect/connect、单图/总量、magic/Pillow/尺寸校验，再用 `insert_image` 上传。已存在占位块用 `replace_image` 原位修复；`read_url` 识别已知错误位图 hash 并输出 `[IMAGE_IMPORT_ERRORS]`。若未来 Feishu importer 提供可验证的远程图片事务结果，或 upstream 原生实现等价 staging + block-level image audit，可迁移并删除本 row。 |

| full PATCH evidence 的单组节点普通 pytest 很快，但 `patch_trace_plugin` 固定 300 秒超时 | 先用失败命令的同组 node 在无 trace 条件下隔离复现；若普通 pytest 快、full trace 连续超时，不得提高预算或把局部重跑当终态绿灯。2026-09-01 实抓 profiler 对每个 Python `call` 都执行 `Path(...).resolve()`，配置/回退测试的高调用量被放大到 300 秒；修复应缓存 code filename → repo 相对路径映射，保留逐 PATCH 独立进程与真实调用归属，并用 auditor 负例禁止恢复逐调用 resolve。若未来证据采集改用低开销 coverage/monitoring API 且不再生成该 profiler，可删除本 row。 |

> 这张表是**可扩展也可收缩**的：发现新摩擦就追加 row，且每个 row 的处置栏必须包含（显式一句或隐含于修法的）退场条件；Step 5c 每轮按退场条件审计本表——已消费的一次性预案、引用已归档/已移除事物的 row、连续多轮未触发的非结构性 row 当轮删除。

---

## 行为约束

- **同一次用户升级任务只允许一个官方 target**：首次使用 `--update`；取得 `TARGET_SHA` 后，无论修了 patch、脚本、测试还是文档，都只使用 `--reconcile`。只有 `target_sha=pending`（从未取得 SHA）的失败 acquisition 可按脚本提示再用一次恢复性 `--update`，且必须仍属于同一事务。不得为了“确认最新”再次 fetch/pull，也不得在事务中途把新出现的 `origin/main` 提交纳入本轮；它们属于下一次用户明确发起的升级
- **不要自动提交**。升级结束先报告；按全局 guardrail 等用户明示"提交一下"再走外层 `~/.hermes` 仓库的 `copilot-git-approve` 流程
- **不要在 `~/.hermes/hermes-agent` 提交**。该仓库是官方源码 checkout，本地 patch 由外层 `patches/local-patches.diff` 监管；除非用户明确要求维护 fork，否则内层只允许 fast-forward/checkout 和 modified patch files
- **不要修改**README 版本记录表里的已结束周 row、PATCHES.md 升级摘要里的 "basis OLD → NEW" 句子（都是历史差量）；当前 ISO 周 row 必须按 Step 4 聚合更新，同周不得追加第二条
- **不要触碰**已 modified 但与升级无关的工作树文件（如 `memories/USER.md` 的用户编辑、未跟踪笔记）
- **不要后台跑** `gh copilot` / `claude` / `codex` 等 AI CLI
- **不要中途追问**用户，也**不要把可修的问题留到报告里等确认**。回归失败、依赖缺口、doctor 可修 P0/P1 一律当轮按 Step 2b/2c 的分支修复到位（依赖自愈与回归所需的本地补丁均已常设授权）。只有两类允许留案并在最终报告单列：① 本地确实不可修且不影响飞书主链路的 P2 上游阻塞（如 npm lock/range 高危待上游 bump）；② 引入全新依赖或改变安全边界的决策
- **不要扩大范围**。本 playbook 仅做"对齐到新上游"；任何顺手优化 / 重构 / 文档大改都不要做，留给用户单独发起（Step 2b/2c 的依赖自愈、为回归全绿所需的本地补丁，以及 **Step 5c 对本 playbook 自身的增补 / 清理 / 修订**属份内事，不算扩大范围——本条约束的对象是工程与用户文档，不是 playbook 的自维护）
