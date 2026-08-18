# Hermes 升级 Playbook

> **用法**：在 Claude Code 会话中说一句 `阅读 ~/.hermes/hermes-update.md 按计划做`，agent 即按本 playbook 一条龙完成"升级内层官方源码 checkout + 回贴本地 patch + 依赖自愈 + 补丁回归修到全绿 + 对齐外层监管记录/文档 + playbook 自身增补/清理/修订自审"，中途不打断、不追问，**收尾零遗留**。
>
> **权威来源分工**：`hermes-update.sh` 是升级执行与回放 gate 的权威，`patches/PATCHES.md` 是语义 PATCH 注册表的权威，`patches/local-patches.diff` 是工程内补丁的唯一物理回放包。三者必须闭环一致；本 playbook 用**发现规则 + 决策规则**驱动，不复制一份会过期的补丁清单。

---

## 持久化演进幂等与跨会话收敛

本 playbook 所说的幂等不是“同一版本重复执行后所有文件字节完全不变”，而是**持久化演进幂等**：Hermes upstream 会持续变化，但本地语义不变量、功能与安全边界不能因升级丢失。任何新的 AI 会话只依赖仓库与运行环境中的持久化状态，完整读取本 playbook 后，都能重建当前升级阶段，安全接管中断现场，对新的 upstream 重新求解“上游已经提供什么、本地还必须补什么”，并按同一决策规则自主收敛；不得依赖上一轮对话记忆、临时推理、人工逐轮指挥或某个 agent 私有的补丁清单。

这里必须同时满足两层不同的幂等，不能混为一谈：

- **单次事务幂等**：一次用户明确发起的升级只允许建立一个官方 acquisition 结果。首次 `--update` 获取成功后立刻把目标 commit 固定为 `TARGET_SHA`；同一任务中的冲突修复、脚本修订、回归重跑和跨会话接管只能使用 `--reconcile`，不得再次 fetch/pull、不得因 `origin/main` 后续前进而移动本轮目标。唯一恢复例外是 acquisition 进程在**尚未取得任何 SHA**时失败，事务显示 `phase=acquiring / target_sha=pending`：此时按脚本提示恰好再用一次 `--update` 接管同一事务、完成尚未建立的 acquisition；这不是第二个 target，也不能在已有 target 后使用。失败或中断时，`~/.hermes/.hermes-update-transaction` 以 `0600` 保存阶段、旧 HEAD、固定目标和运行态脏标记；只有整支脚本 exit 0 才删除。已有 target 时误传 `--update` 必须自动复用它而不是开启第二次获取。
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

### 补丁模型（本轮重构后的固定边界）

- **语义层**：每个 `PATCH-<DOMAIN>-<INVARIANT>` 是独立的问题、回滚、验证和上游吸收单元；语义定义只在 `PATCHES.md` 出现一次。
- **物理层**：所有工程内源码补丁合并存放在一个 `local-patches.diff`。这是有意设计：多个语义补丁会共享同一文件，强拆物理 diff 会制造 hunk 顺序依赖；不能因为物理上只有一个 bundle 就把逻辑补丁合并成一个生命周期。
- **外层插件层**：`PATCH-FEISHU-GROUP-SANDBOX` 等配置仓库补丁由外层 Git 和独立 `verify.sh` 监管，不得进入内层 `PATCHED_FILES` 或 replay bundle。
- **运行时层**：`PATCH-NPM-DEPENDENCY-HYGIENE`、`PATCH-REPLAY-BUNDLE-FULL-INDEX`、`PATCH-UPDATE-GATE-EXIT-STATUS`、`PATCH-UPDATE-TRANSACTION-PIN`、`PATCH-SKILLS-MIRROR-METADATA` 等升级期策略由 `hermes-update.sh` 对应步骤重建，不以源码 hunk 或 Step 8b gate 表示。
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
- 当天日期（记为 `OLD_DATE` 用于 grep；本次升级新日期记为 `NEW_DATE`）

如果用户明确要求“更新到最新”，不要在 Step 1 预判远端是否有新提交；直接把唯一发现机会交给 Step 2 的 `--update`。如果用户只要求对当前 checkout 做 patch 审计/收敛，则使用 `--reconcile`，其目标固定为现有 HEAD 且绝不访问 origin。完全只读且运行态输入未变化时不为制造新 PID 而重启；如果接管中断现场后无法证明当前 PID 晚于最后一次运行态修改，则按 Step 5b 执行终态运行屏障。不要因为 `hermes --version` 显示 `Up to date` 就跳过本地闭环检查。

### Step 2 — 跑升级脚本

```bash
bash ~/.hermes/hermes-update.sh --update
```

`--update` 是唯一允许接触官方仓库的入口。正常情况在同一次用户升级任务中只显式调用一次：若没有未完成事务，就执行 scoped fetch、立即固定 commit，再运行被 SHA 约束且禁止网络 fetch 的官方 updater。若首次 acquisition 在拿到任何 SHA 前失败，`--transaction-status` 会显示 `target_sha=pending`，脚本会明确要求**一次**恢复性 `--update`；它只补完同一 acquisition。已有 target 后即使再次传 `--update` 也只能复用固定目标，不会二次 fetch/pull。除此之外默认无参数与 `--reconcile` 等价，只围绕事务 `TARGET_SHA`（无事务时为当前 HEAD）重跑本地 patch、依赖修复、gate、镜像、verifier 和健康闭环。

建议 background + tee 日志；外层任务超时不要用固定数字：Step 8d 的等待预算用 `bash ~/.hermes/hermes-update.sh --print-restart-wait-seconds` 只读获取（底层为脚本 `gw_restart_wait_seconds()`；新运行时 = drain + `restart_after_turn_timeout` + 余量）。上游 `0c6761c51` 已把 after-turn 默认值从 6h 收窄到 30min，本轮新运行时当前输出为 2745s ≈ 45.8min；用户配置仍可覆盖，因此外层超时必须大于该入口的**现场输出**，不能抄默认数字。同一只读入口还提供 `--print-patched-files` / `--print-patched-tests`，供 Step 2c/3 读取脚本现场数组；**不要 `source hermes-update.sh` 取函数或数组**——该文件是可执行升级入口，不是函数库，source 会被拒绝。忙时段升级前先确认在途任务量或接受长排空，不得因等待排空而误判脚本卡死、更不得强杀。脚本自带：preflight / 事务 SHA 固定 / 内层 patch 存档到外层 `patches/local-patches.diff` / 首轮 `hermes update` 或后续无网络 reconcile / npm audit / skills 镜像 / gateway plist / 补全脚本 / patch 回贴 + 结构化 sentinel 验证 / replay bundle 逐字节与正反向完整性 gate / 按运行态脏标记决定的排空感知 planned restart / 用户 plugin verify / 健康检查。Step 8b sentinel 只证明关键实现锚点存在，不能替代 Step 2c 的行为回归。需要重载时必须观察到 PID 从旧值替换为新值；无变化 reconcile 明确跳过重启，不能为“证明执行过”制造 PID。

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
./scripts/run_tests.sh "${patch_tests[@]}"
'
```

测试文件清单与上轮外层提交中的 `hermes-update.sh` 对比，passed 数与 `PATCHES.md` § 当前版本摘要对比。禁止直接调用 `pytest`；runner 会隔离 HOME/凭据、固定时区/locale，并逐测试文件放进独立子进程，结果才与 Hermes CI 口径一致。**回归终态 0 failed 是必要条件，不是充分条件**：passed 数只是遥测，数量下降、测试文件消失、collection 异常或关键用例被改名/跳过都必须逐项解释，不能拿“仍然 0 failed”掩盖覆盖面退化。出现新失败先定性、再按分支当轮修到转绿，不留遗留：

1. **环境缺口**（依赖缺失 / 解释器变化）→ 回到 Step 2b 补装后复跑；
2. **上游自身 bug**（`git stash push -- <相关源文件+测试>` 后在裸上游复跑同样失败）：影响本部署行为或本回归套件的，**本地补丁修复**——按 Step 4 的补丁归并原则决定并入现有语义 PATCH 还是新增语义 PATCH，同步 sentinel / PATCHED_FILES / PATCHES.md / 快照，修到转绿；确实不影响本部署行为且测试不在本套件内的，才允许只记摩擦表；
3. **补丁真回归**（仅打补丁后失败）→ 修补丁本身。

凡是由真实平台事件暴露的缺陷，新增回归必须落在**最高有效边界**：至少用平台真实 payload 形状穿过完整 adapter 入站路由，并断言最终 Gateway event / provider request / 出站消息中真正需要保持的不变量；只测新 helper 或 grep sentinel 不算回归完成。若同一 transport 会按 chat type / profile / tenant 映射不同配置 namespace，测试还必须穿过实际 consumer，成对断言各 scope 最终拿到的 toolsets/display policy 与真实出站 send/edit，不能用“配置文件值正确”或“selector helper 单测通过”替代。测试同时要有正例、不会误触发的反例，以及问题涉及重试、去重、重复引用或恢复时的重入例。能对用户已置于本次范围内的既有消息做只读 API replay 时可作为额外证据；没有明确授权时不要为了 canary 主动向外部会话发消息，fixture 级边界回归仍是硬门禁。

**模型切换后的多模态验收（长期硬门槛）**：`config.model`、`fallback_providers` 或其具体型号/ARN 发生变化时，不得仅凭旧 catalog、provider 名或历史结论推断能力。对每条配置 route 至少用合成、无敏感内容的最小 canary 穿过真实 provider wire，分别验证官方声明支持的 image/audio/video/PDF 输入；官方明确不支持的模态必须保持 fail-closed，不得用强制 native 掩盖。运行时遵循 native-first：主模型真实支持就直接接收原始媒体；不支持或本地可信抽取/STT 全失败时，才把**单个当前媒体 + 有界 caption/引用上下文**交给 fallback 链中首个具备该模态的 route，禁止切换整轮 provider、禁止重放 transcript、禁止同一媒体先预分析后再重复调用工具。成功的 native、可信抽取和 sidecar 结果不得向模型暴露宿主 cache 绝对路径，也不得诱导再次 `read_file`/媒体工具；全部 reader 失败必须给当前 turn 一个明确、可测试的 `FAILED` 状态，说明不能声称读过并要求用户重发，禁止静默丢附件或退化为群聊不可达的 path note。PDF 还必须成对覆盖“纯文本只抽取”和“抽取有扫描/图片页缺口时补充 sidecar”两条路径。每轮升级和每次模型链调整都要证明 native route、sidecar route、可信抽取、视觉缺口补读、path-free 成功提示与显式失败反例；结论写入对应 PATCH 与测试，不能只留在会话记忆。

**附件取得与 @mention 验收（长期硬门槛）**：Feishu 群的独立附件消息无法携带 @Bot，因此资源 PATCH 必须同时证明三条入口：同一 post 内附件+mention、显式回复附件+mention、同一发送者在配置化有界窗口内先发附件后 mention。窗口扫描必须覆盖 image/file/media/audio，限制消息数、文件数与超时；显式回复不受窗口去重抑制。引用/history 文本只保留 path-free 附件占位符，资源字节由当前/引用附件链恰好下载一次；下载、回填或解码失败必须进入上述显式 `FAILED` 状态。测试至少穿过 Feishu 真实 payload → adapter event → Gateway provider/user turn，成对覆盖主私聊与群聊，并断言模型可见文本不含 `~/.hermes/cache`、`/Users/.../.hermes/cache` 或容器映射路径。

工具注意：pytest 若因 venv 重建暂缺，可先 `pip install --target /tmp/... --no-deps pytest==<pin> pytest-asyncio==<pin>` + `PYTHONPATH` 叠加做初步定性（不污染 venv），但最终文件清单和数字必须用 `./scripts/run_tests.sh` 复跑得出；**禁止用 `uv run` 跑回归**——它会挂到 `.venv`（uv 默认项目环境）而不是 hermes 的 `venv`，产生成批假失败。

### Step 3 — 审查 patch & 脚本

`patches/local-patches.diff` + `patches/.local-patches.base` 由脚本自动刷新，属于外层 `~/.hermes` 仓库的监管记录。不能只看 patch apply 成功；本轮重构后，每次升级必须完成下面的仓库级闭环：

| 层面              | 终态必须成立                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **事务目标**      | 本轮至多一次显式 `--update`；失败/中断后的事务文件固定同一个 `TARGET_SHA`，所有后续执行均为 `--reconcile` 且日志明确 `no fetch/pull`。终态 `HEAD == TARGET_SHA`；事务文件只能在整支脚本 exit 0 后消失。`origin/main` 在事务期间即使被其他进程刷新也不得改变当前目标。                                                                                                                                                                                                                                                                                                                                         |
| **受管文件集合**  | 用 `bash ~/.hermes/hermes-update.sh --print-patched-files` 读取权威 `PATCHED_FILES`，不得依赖文档快照或 source 脚本。每个受管文件都应有预期内 diff；任一 zero-diff path 必须判定为吸收、漏补或 stale registry，不能让 bundle 静默少一项。内层其他 modified/untracked 文件逐项归类。已知 `package-lock.json` npm 归一化噪音可保留，但不得混入 replay bundle。                                                                                                                                                                                                                                                  |
| **bundle 一致性** | `git -C ~/.hermes/hermes-agent diff --full-index HEAD -- <PATCHED_FILES>` 与 `patches/local-patches.diff` **逐字节一致**。必须固定 `--full-index`，避免 Git 对象库增长导致自动缩写位数变化；文件数量、行数或“看起来一样”都不能替代 `cmp`。脚本 Step 2/8c 已 fail-closed 自动执行同一物理 gate，升级审计仍须独立复核输出与现场，防止脚本自身被错误修订。                                                                                                                                                                                                                                                       |
| **可回放性**      | 确认内层 index 干净后，`git -C ~/.hermes/hermes-agent apply --cached --check ../patches/local-patches.diff` 对 HEAD 正向通过；当前已打补丁的 worktree 上执行 `git -C ~/.hermes/hermes-agent apply --check --reverse ../patches/local-patches.diff` 通过。两项分别证明“下次能贴”和“当前 bundle 确实描述现状”。                                                                                                                                                                                                                                                                                                 |
| **基线来源**      | `patches/.local-patches.base` 第一列 SHA 等于内层 `git rev-parse HEAD`；时间戳只作审计信息。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **语义注册表**    | `PATCHES.md` 中活跃 + Archive ID 全局唯一；活跃块各有且仅有 `问题`、`修复`、`验证`、`上游吸收判断` 四段；不得出现 `LEGACY`、纯数字或 A/B 变体命名。                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **执行链注册**    | 每个活跃补丁按类型有唯一执行链：工程内补丁对应 Step 8b 独立 sentinel/gate 并进入 8c 总闸门；运行时补丁对应明确 update step；外层插件补丁对应 Step 8e verifier。Archive sentinel 也必须保留明确执行链：Step 8b 的进入 8c 总闸门，工程外 sentinel（如 Step 7 completion）留在其原步骤并影响整次升级结果。                                                                                                                                                                                                                                                                                                       |
| **外层安全补丁**  | `PATCH-FEISHU-GROUP-SANDBOX` 检查外层 diff + `plugins/<name>/verify.sh`；`config.yaml` / `plugins/` / `my-skills/` 不得伪造进内层 replay bundle。verifier 必须先证明 launchd wrapper 受监管，再用 `gateway.status.get_running_pid()` 取得真实 Gateway 子进程并核对其注册日志，证明实际运行进程已加载新策略。                                                                                                                                                                                                                                                                                                  |
| **画像隐私边界**  | `people.yaml` 必须被 Git 忽略；`people.yaml` / `groups.yaml` 都保持 owner 可读写的普通文件并由热加载器与 Step 8b 收敛为 `0600`，不得用只读位或 immutable 破坏同账号 VSCode 手工编辑。人物字段采用公开白名单，只有 `name` / `role` / `department` / `address` 可输出，任何未来新增字段必须默认“模型可读、输出禁止”，技术 ID 与未公开别名只用于匹配。`PATCH-LOCAL-PROFILES` 的行为回归还必须覆盖当前问话人匹配、历史/合并转发发送者仅渲染公开白名单，以及 final、stream、fallback、interim、streaming TTS、`/background` 等独立可见/可听文本路径的脱敏。只检查普通 final reply 不足以证明“只能使用、不能外显”。 |

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
- **哨兵锚点选择与共演进**：新写 grep 哨兵优先锚定**测试名或行为特征串**（测试名受 Step 2c 保护、很少被重构改名），避免锚定私有 helper 名——上游或本地重构最容易杀死后者（2026-08-03 实例：`_with_current_author_prefix` 被冲突轮重构移除，gate 误报 14 小时）。配置驱动的补丁还必须让测试 fixture、测试名和 gate 使用 `primary` / `fallback-A` / `fallback-B` 这类角色语义，不能把当前生产 config 的 provider/model 名写成补丁契约；否则未来只换配置也会留下伪失效的执行链。条件允许时向 PATCH-SKILL-CREATE-ROOT 的真实 import + 调用模式靠拢。**冲突解决或重构触及文件 X 后，必须核对 8b 中所有针对 X 的哨兵仍能命中**——最省事的核对方式就是按收敛循环重跑脚本。
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

同时机械校验**派生一致性**（周键唯一 + 数字/SHA 不失同步）。Step 4 的 grep 只能发现 SHA 字符串，发现不了"脚本数组 64 但快照注仍写 63"这类数字漂移（2026-08-03 实抓一起），因此以下断言每轮必跑、任一失败先修再收尾：

```bash
python3 - <<'PY'
from collections import Counter
from datetime import date
from pathlib import Path
import re

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

print(f"derived-consistency OK: {len(weeks)} weekly rows unique; "
      f"{len(arr)} managed files; {stated} active patches; base {base_sha[:9]}")
PY
```

> 断言口径变了（如快照注措辞、README 表述）就同步改这段脚本——它与被校验文本共演进，属于 Step 4 文档对齐的一部分。

#### Step 5b — 终态运行屏障

Step 2c/4/5 期间只要修改过 `hermes-agent` 运行时代码、`config.yaml`、`.env` 或 `plugins/`，Step 8d 的 PID 证据就立即失效。所有代码、配置、测试、bundle 和文档修改结束后，必须把 planned restart 当作一次**终态写屏障**：记录 `hermes gateway status` 的当前 supervisor PID，执行 `hermes gateway restart`，按脚本 `gw_restart_wait_seconds()` 同款预算（新运行时的 `_get_restart_exit_wait_budget()` 优先，旧运行时回落 `restart_drain_timeout`，+30s）轮询到不同的新 supervisor PID，再在新 PID 下重跑全部 Step 8e verifier 和 `hermes gateway status`。新 launchd plist 可能直接监管 `hermes_cli.stderr_timestamp` wrapper；此时 status PID 是 wrapper，verifier 必须另用 `gateway.status.get_running_pid()` 取得真实 Gateway 子进程并把注册 trace 绑定后者。两层 PID 都必须健康。如果 barrier 之后又改了任何运行时输入，必须重新执行本步骤；完全只读的“已是最新”审计且能证明当前进程晚于最后一次运行态修改时可跳过。

不要把 `plugins/<name>/verify.sh` 的通过结果单独当作运行态新鲜度证明：verifier 会做磁盘代码测试和当前日志匹配，但如果 Gateway 子进程是本轮插件修改前启动的，进程内 handler 仍可能是旧代码。凡本轮碰过 `plugins/`，收尾证据必须同时包含“旧 supervisor PID → 新 supervisor PID”、新 wrapper 下的真实 Gateway 子进程 PID，以及该子进程对应的 verifier 结果；缺任一项都按 Step 5b 未完成处理。

禁止用 `hermes gateway stop && hermes gateway start` 代替 planned restart：macOS stop 路径在短固定宽限后会强杀进程，可能把正在处理的飞书 turn 变成中断恢复任务并产生非预期回复。若排空超过预算或 PID 未替换，本轮必须非零/阻塞收尾，保留旧进程与日志供诊断，不能为了得到新 PID 直接强杀。

#### Step 5c — Playbook 持续演进自审（每轮必做）

Step 6 报告前，以本轮实际执行为镜，把本 playbook（含摩擦表）当作与代码同级的可维护资产，做一轮完整的**增补 + 清理 + 修订**三操作审计。playbook 不是只追加的日志：只增不减会让规则密度稀释、失效条目与现行条目混杂，后续轮次的执行效能逐轮退化——**"本轮没有可清理/可修订项"必须是审计后的结论，不能是默认假设**：

1. **增补（新现象清点）**：列出本轮出现而 playbook / 摩擦表未预见或描述不准的现象（新 doctor 检查、新迁移形态、新冲突型、新警告类别、脚本或官方 updater 的新行为、测试口径变化）。逐项按"权威源不分叉"判定归属——执行行为 → `hermes-update.sh`，PATCH 生命周期 → `PATCHES.md`，物理改动 → replay bundle，决策/恢复规则与摩擦 → 本 playbook——并**当轮落盘**；只写进最终报告或会话总结等同于未修复。
2. **清理（时效退场）**：逐段扫描 playbook 正文与摩擦表，识别并删除：① **已被消费的一次性预案**——针对特定未来 upstream 范围写的冲突/行为预告，该范围已跨过、预案已兑现或证伪；② **指向已不存在事物的陈述**——引用已归档 PATCH、已移除机制、已被上游取代的行为；③ **连续多轮未触发且非结构性的条目**——结构性/周期复发的知识（如 lock 噪音、镜像振荡）保留，纯历史巧合退场。仍有历史价值的事实并入 README 对应周 row 后再删，不在 playbook 里留尸体；摩擦表每个 row 都必须能回答"什么条件下删除本 row"，新增 row 时把退场条件写进处置栏。`hermes-update.sh` 的归档 sentinel 同属清理对象（见补丁模型归档层）。
3. **修订（规则时效核查）**：抽查本 playbook 引用的锚点、命令、路径、默认值与当前脚本/上游是否仍一致（如 `--print-*` 只读入口、gate 名称、doctor 输出口径、wiki SCHEMA 路径映射）；描述已不准确的段落**就地重写**，不另开平行段落、不保留旧措辞注释。失效即当轮修订，不留给下一轮撞上。
4. **验收自问**：换一个没有会话记忆的 AI，面对任意后继 upstream，仅从当前磁盘状态和本文件出发，能否重建本轮全部判断（含本轮新增的判定规则）？任何"必须靠本次会话记忆才能答对"的知识点，都必须补写进对应权威文件后本步骤才算通过。
5. **结果入报告**：Step 6 报告必须单列本步骤结论——增补、清理、修订各做了什么/为何，任一类为空时写明"审计后无该类变更"及依据；该结论缺失视为升级未完成。

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
entries = set(re.findall(r"--(?:print-[a-z-]+|transaction-status)\b", pb))
entries |= {"gw_restart_wait_seconds", "_get_restart_exit_wait_budget"}
missing = {e for e in entries if e not in script}
assert not missing, f"playbook references missing script entries: {sorted(missing)}"

# 3) playbook 反引号内的具体仓库路径必须存在（模板路径如 plugins/<name>/… 天然跳过）
for p in set(re.findall(r"`((?:plugins|patches|scripts|wiki)/[A-Za-z0-9_./-]+)`", pb)):
    assert Path(p).exists() or Path("hermes-agent", p).exists(), f"missing path: {p}"
print("playbook-hygiene OK")
PY
```

### Step 6 — 收尾报告

向用户报告（**不要自动提交**）：

- **完成标准**：首次官方获取至多调用一次 `--update`；**最后一次 `hermes-update.sh --reconcile` 完整本地收敛运行 exit 0 且无 `✗`，并晚于本轮最后一次 patch / gate / 脚本修改**（逐项人工验证不能替代 reconcile 闸门，哨兵漂移只有跑脚本才会暴露），且日志/事务证据证明所有复跑固定同一 `TARGET_SHA`、未再次 fetch/pull；补丁回归 **0 failed 且测试清单/关键边界未退化**、Step 3 八层仓库闭环全部成立、Step 5 派生一致性断言通过、Step 5b 的终态 supervisor PID 晚于最后一次运行态修改、真实 Gateway 子进程 PID 可解析且所有用户插件 verifier 绑定该子进程通过、doctor/npm warning 已按 P0/P1/P2/P3 分级且无可修而未修的 P0/P1、无环境残留，且 **Step 5c playbook 自审已执行、结论已落盘**。达不到时不得声称完成，单列阻塞项、原因与建议
- 升级 `OLD_SHA → NEW_SHA`，`+N commits`
- 问题分级结果：P0 修复项与验证、P1 已修或决策项、P2 上游等待项、P3 可选缺口；P2/P3 必须说明是否影响飞书主链路
- 文档对齐了哪些文件（列文件名 + 改动类别一句话，不展开内容）
- README 版本记录周键检查结果：当周是新增还是合并、当前总周数、是否存在重复 ISO week
- Gateway / Doctor 现状（异常项展开，正常项一行带过）；安全插件需报告 verifier 对照的当前 PID，以及 owner 主会话与群聊实际 toolset 是否仍满足边界
- 持久化演进接管性：报告活跃 PATCH 的未吸收 / 部分吸收 / 完全吸收判定及相应状态变化；列出本轮新发现的冲突、摩擦或规则缺口分别落盘到哪个权威文件，如没有新增经验也明确写“无”。确认不存在下一轮升级必需、但只保留在本次会话或临时日志中的恢复知识
- Step 5c playbook 自审结论：增补 / 清理 / 修订三类各做了什么及依据，任一类为空写明"审计后无该类变更"；playbook-hygiene 断言块运行结果
- 工作树里哪些是“升级相关”、哪些是“用户先前在编辑的其他东西”，提示后者保持不动；明确说明内层受管 modified files 是预期 patch overlay，外层 bundle 才是待提交记录
- 若 Step 2/3 中发现脚本侧的新兼容性问题，单列一节描述给用户决策
- 提醒：若用户随后明确要求提交，只提交外层 `~/.hermes` 仓库里的升级监管改动；不要在 `~/.hermes/hermes-agent` 创建 commit

---

## 已知摩擦速查（用户可补充）

| 现象                                                                              | 处置                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` 报 "No virtual environment ... `~/.local/share/uv/python`"                   | 脚本固化了 `--python venv/bin/python` fallback，会自愈                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `hermes update` 访问 PyPI / GitHub 反复 `tls handshake eof` / `SSL_ERROR_SYSCALL` | `hermes_cli.env_loader` 会以 `override=True` 载入 `~/.hermes/.env`，所以仅在父 shell 临时改代理无效。先用直连与当前代理分别 `curl -I` 定性；若代理失败，把 `pypi.org,files.pythonhosted.org,github.com,api.github.com,raw.githubusercontent.com` 追加到 `.env` 的 `NO_PROXY`（保留现有条目）。直连 GitHub 也可能瞬时超时，`PATCH-UPDATE-GIT-FETCH-RETRY` 因此只对首次 acquisition 中上游 CLI 明确报告的**尚未取得目标 SHA 的早期 GitHub fetch 网络错误**做最多 3 次有界重试；一旦取得 `TARGET_SHA`，后续失败只允许 `--reconcile`，不能借网络重试推进目标。认证、分叉、安装、迁移等错误不得重试。                                                                                                                                                                                                                  |
| 从 shell 风格 `~/.secrets` 映射 Vertex 凭据后报 `File $HOME/... was not found`    | shell wrapper 会展开 `$HOME`，但 `python-dotenv` 只读出字面值，`agent.vertex_adapter` 又只做 `expanduser()`，不会做 `expandvars()`。从 `~/.secrets` 注入 `~/.hermes/.env` 时必须先对路径执行环境变量 + `~` 展开并写入绝对路径，只检查文件存在性、不得把路径内容或凭据值打印到会话；终态用标准 `vertex` 真调用验证。若上游 adapter 原生支持 `$VAR` 路径展开，或 `~/.secrets` 永久改为绝对路径，可删除本 row。                                                                                                                                                                                                                                                                                                                                                                                                      |
| 同一升级审计反复拉到更新的 `origin/main`                                          | `PATCH-UPDATE-TRANSACTION-PIN` 把官方获取与本地收敛分成 `--update` / `--reconcile`：同一用户任务只调用一次前者；`~/.hermes/.hermes-update-transaction` 在失败/中断时以 `0600` 固定目标、运行态脏标记和恢复阶段，exit 0 才删除。默认无参数也是 no-network reconcile；预检禁止 `git fetch`、`hermes update --check` 和带隐式 update-check 的 `hermes --version`。事务存在时误传 `--update` 也只能接管固定 SHA。                                                                                                                                                                                                                                                                                                                                                                                                     |
| `/model` 出现未配置 provider，或配置的 AWS fallback 反而不显示                    | 原生 `/model` 是“机器级 credential discovery + provider catalog”，不是 profile 配置视图：shell/`~/.secrets` 的 API key、auth pool、普通 `GITHUB_TOKEN` 都可能制造模型入口；反过来，非当前 Bedrock 的 IAM-role 凭据因 picker 避免 IMDS 探测而可能不显示。Gateway 还用 raw YAML 快速读取，`${VAR}` 模型值若不按 config 层展开，会出现“列表显示占位符、共享核心比较展开值”的自相拒绝。处置：`PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION` 拒绝 profile `.env` 外的已知 Hermes 环境变量并清理旧 ambient pool；`PATCH-MODEL-CONFIGURED-ONLY` 从 `config.model + fallback_providers` 动态生成并统一展开展示/可切换集合，链外和 `--global` fail closed。主动切换 primary 时 fallback 用 backend identity 跳过重复项，compression 独立配置不变。上游提供等价 profile-owned model universe 与 ambient isolation 后删除本 row。  |
| 切换模型后图片/音频/视频变慢、重复分析或只剩路径提示                              | 先区分“模型官方支持”与“Hermes capability metadata 已识别”：2026-08-16 实抓 Bedrock Opus 5 官方/真 wire 支持图片，但 inference-profile ARN 未被 catalog 识别，导致同一图片先预分析、主 turn 又调一次 `vision_analyze`；其官方 Video/Audio 为不支持，GPT-5.5 同样只支持 Text+Image，Gemini 3.5 Flash 支持 Text/Image/Audio/Video 及 PDF/text 文件。处置：按 Step 2c 多模态硬门槛对每条新 route 跑无敏感合成 canary；支持的走 native，不支持的由 `PATCH-MULTIMODAL-SIDECAR` 仅发送当前媒体 + 有界上下文给链上 capable route，STT/本地文档抽取成功则不旁路。上游提供统一、可探测且带真实 provider-wire 回归的 modality routing 后删除本 row。                                                                                                                                                                         |
| `npm audit` 报 Desktop/build 链高危                                               | 先按 P2 定性：Desktop/Electron/web/ui-tui 的 build-chain advisory 不在飞书 gateway 主链路上，修复需 `--force` 越 stated range 或受上游 override/lock 阻挡时不阻塞；最终报告和 README row 只留案说明“不影响飞书主链路”。每轮必须以 `npm audit --json` + `npm explain` 重新判定，不能沿用上轮包名：2026-08-16 / `8ad055414` 实测 root 仍为 6 high——`electron@40.10.2` 两条 GHSA + 其 `extract-zip` 路径遍历需越 stated range 到 40.10.6，另有 `postcss@8.5.23 → nanoid@3.3.17` 经 sanitize-html/vite 进入 Desktop/web build 链且被上游 override 锁住；doctor 分别报告 web 4 high、ui-tui 3 high。若 `npm explain` 证明任一 high 进入 gateway runtime 或飞书消息处理路径，立即提升为 P0。相关链全部被上游 bump 到修复版后删除本 row。                                                                                |
| PATCH 行号漂移                                                                    | `hermes-update.sh` Step 8 自动 rebase；摘要里写 `OLD → NEW` 即可                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Step 8d/终态重载打断飞书任务或留下旧 PID                                          | 常规更新只用排空感知的 `hermes gateway restart`，等待预算与脚本 `gw_restart_wait_seconds()` 一致（native exit-wait budget 优先、drain 回落，+30s），并硬性核对 old PID → different new PID；不得用 macOS 上短宽限后会 SIGKILL 的 `gateway stop && gateway start`。Step 8d 后若又修了运行时代码/配置，按 Step 5b 再做一次终态屏障并在新 PID 下重跑 plugin verifier；超时则失败留案，不强杀换取表面成功。                                                                                                                                                                                                                                                                                                                                                                                                           |
| launchd plist 刷新后 definition current、但 Gateway 无 PID                        | 2026-08-15 实抓三层问题：① wrapper 曾因“进程正在运行”跳过 freshness；② 在 patch 还原窗口刷新会用裸 upstream 定义覆盖最终 patch；③ 新上游用 `hermes_cli.stderr_timestamp` 包裹真实 Gateway，却未传 `--external-supervisor`，子进程误判成 shell 副本并 exit 1。由 `PATCH-LAUNCHD-WRAPPER-SUPERVISOR` 仅给 launchd wrapper 追加正式 marker，detached fallback 保持无标记；Step 5 只快照，Step 8 回贴后才要求 definition current + launchd wrapper PID + real Gateway child PID。status PID 是 wrapper，插件 trace 必须绑定 `gateway.status.get_running_pid()` 的子进程。上游补齐同等 argv/回归并吸收该 PATCH 后删除本 row。                                                                                                                                                                                          |
| `local-patches.diff` 自身带 conflict marker                                       | 脚本会拦截；`git restore --source=HEAD -- patches/local-patches.diff` 恢复入库版本后运行 `bash ~/.hermes/hermes-update.sh --reconcile`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Step 2 报 staged index / `Partial patch overlay detected`                         | 这是跨会话恢复硬门禁，不是可忽略 warning：staged index 先逐项归类并用 `git restore --staged -- <paths>` 只清 index；部分 overlay 逐个对照 `--print-patched-files`、canonical bundle 与 `PATCHES.md` 吸收条件，判断是中断漏贴、手工删 hunk 还是上游吸收。脚本会在覆盖 bundle 前退出，旧完整包仍在；禁止为“继续更新”而删 bundle 或把缺项快照强行保存。若现场是全部受管文件等于 HEAD + bundle 存在，则属于可重入裸树接管，脚本会保持 EXIT trap 武装并在 8a 回放。                                                                                                                                                                                                                                                                                                                                                    |
| 某个活跃 PATCH 疑似已被上游吸收                                                   | 不依赖脚本自动标 `retired`；逐个按该块的 `上游吸收判断` 在裸 upstream 验证。完全吸收后删除其独有 hunk、移动定义块到 `## Archive — PATCH-...`，仅在文件不再被其他活跃补丁触及时移出 `PATCHED_FILES`；部分吸收则保留活跃块并收缩 hunk/四段描述，最后重跑 Step 3 闭环                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 新增本地补丁                                                                      | 先按 Step 4 判断并入还是新增语义 PATCH；工程内补丁同步 `PATCHED_FILES`、独立 sentinel/gate、`PATCHES.md` 四段和 replay bundle/base；运行时或外层插件补丁走各自管道。不能只等下次 Step 2 自动 capture                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| 用户插件 verifier 缺失或失败                                                      | `PATCH-FEISHU-GROUP-SANDBOX` 类外层安全补丁不得继续显示升级成功。恢复 `plugins/<name>/verify.sh` 的文件/执行位，修复根配置、插件配置或上游 hook/toolset 兼容性，直到 Step 8e 对照当前 Gateway PID 返回 0；不要把外层文件加入内层 `PATCHED_FILES`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 用户插件 verifier 只测 resolver/dispatch、没穿过完整执行链                        | 2026-08-12 实抓：`tool_search/describe` resolver 可用但 hook 误拦。2026-08-16 续审又抓到 `clarify` 已在群 toolset 却不在 allowlist、群聊继承 outsider-DM 的 vision/image 放行、飞书资源 token 无当前消息 provenance、非可信用户可 mutation，以及长 `web_extract` 虽成功却因全局 cache 被沙箱阻断而无法续读。处置：verifier 必须覆盖 YAML 精确集合、model-facing 直接工具、真实 `tool_call → underlying → hook → handler`、scope 越权反例、资源 provenance、mutation 身份、跨群/路径/symlink、长结果 continuation 的精确临时授权、新事件撤销和最终 PID runtime trace；只证明 helper、schema 或 hook 单层可用都不算闭环。该 row 长期有效，除非上游提供统一的端到端 capability/sandbox simulator 与会话级 artifact grants。                                                                                          |
| 改了 `plugins/` 后只跑 verifier、未重启 gateway                                   | verifier 会加载磁盘插件跑测试并核对当前日志，但不会让已启动的 gateway 进程自动替换已 import 的 handler。处置：按 Step 5b planned restart，记录旧 PID → 新 PID，再在新 PID 下复跑 `plugins/<name>/verify.sh` 和 `hermes gateway status`；这类 row 长期有效，除非插件热重载机制能证明代码对象随文件变更自动替换。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| planned restart 后 verifier 立即查 MCP 注册出现短窗误报                           | 2026-08-18 实抓：Gateway 真实子进程先打印 `sandbox: registered (pid=...)`，HyperTeX stdio discovery 约 5s 后才打印 `mcp__hypertex__tasks_get/update/cancel`；Step 8e 单次 grep 在两者之间执行，把健康启动误报为能力缺失。处置：先用当前真实 Gateway PID 定位 sandbox trace 行，再只在该行之后做最多 10s/0.5s 间隔的有界等待；禁止匹配旧进程历史 MCP trace。该 row 在 MCP discovery 仍为异步启动时长期有效；若未来 Gateway readiness 信号已包含全部 MCP server registration，可删除等待并退役本 row。                                                                                                                                                                                                                                                                                                              |
| 补丁整体 apply 失败（上游真实冲突，脚本已回滚）                                   | 手工 `cd hermes-agent && git apply --3way ~/.hermes/patches/local-patches.diff`，解决带 `<<<<<<<` 标记的文件（多为"并存"型：上游新增与补丁插入同位），`git add <冲突文件> && git restore --staged -- <所有 staged patch 文件>` 只清 index，然后运行 `bash ~/.hermes/hermes-update.sh --reconcile`——Step 2 会从工作树捕获已解决的 diff 并围绕固定 `TARGET_SHA` 走完整验证，不再获取 upstream。若宿主安全策略拒绝 `git restore --staged`，可在确认 staged 全部属于本次 patch 后只恢复 index：`git diff --cached --name-only -z                                                                                                                                                                                                                                                                                      | while IFS= read -r -d '' patch_file; do git ls-tree HEAD -- "$patch_file"; done | git update-index --index-info`；zsh 中循环/轮询变量不要使用 `path`、`status` 等特殊参数名：`path`会联动覆盖`PATH`，`status`是只读参数；统一使用`patch_file`、`gw_status` 等任务专用名。注意：`git apply`输出别接`head` 截断，SIGPIPE 会中断 apply。该 fallback 在宿主允许标准 restore 后可删除。 |
| `package-lock.json` 在 npm audit fix 后 dirty                                     | 本机 npm 可能归一化排序 / `peer` 标记，也可能把传递依赖推进到 audit 可用的补丁版本。每轮必须先审查实际 diff：确认 `package.json` 无意外语义变化、记录版本升降和剩余 advisory，再把可解释的 lock drift 保留在内层工作树且排除出 replay bundle；不得一律按“无版本变化噪音”跳过。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Doctor 提示 `npx playwright install` 但根 CLI 不存在                              | 根 `npm install` 后先检查 `node_modules/.bin/playwright` 与各 workspace 的 `.bin/playwright`。当 Playwright 仅由 Desktop workspace 安装时，根 `npx playwright install chromium` 会报 `playwright: command not found`；使用同一 lockfile 已安装的 `apps/desktop/node_modules/.bin/playwright install chromium`，然后以 `hermes doctor` 的 `Playwright Chromium` 转 ✓ 为终态验证，不为此新增根依赖。                                                                                                                                                                                                                                                                                                                                                                                                                |
| `test_approval.py` 的 verifier temp cleanup 测试在 macOS 失败                     | 上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 对 temp_dir 做 `realpath`（`/tmp`→`/private/tmp`）而 operand 不做，Darwin 上恒不匹配，其自带测试预期失败；裸上游同样失败、与本地 patch 无关。由 `PATCH-APPROVAL-DARWIN-TMP` 仅对 `/private` 系统别名放行 raw 拼写，其余 symlink 保持 fail-closed。上游统一 realpath 后归档该补丁并删除本 row                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `test_feishu.py` 的 SSRF connect-time rebind 测试偶发失败                         | 真实原因（2026-07-29 定性，推翻旧"跨文件状态"结论）：上游测试只 blank 代理 env 变量，httpx `trust_env` 在 env 为空时经 `urllib.request.getproxies()` 回落 macOS **系统代理配置**——宿主 Clash 系统代理开着就必失败（守卫按设计把解析委托给代理，收到裸 `httpx.ConnectError`），关着就通过，与批量/单跑无关；裸上游同样失败，与本地 patch 无关。已由 `PATCH-FEISHU-SSRF-TEST-SYSPROXY` 在测试内补 `patch("httpx._utils.getproxies", return_value={})` 修 hermetic；上游吸收后归档该补丁并删除本 row                                                                                                                                                                                                                                                                                                                 |
| Skills mirror 每轮报 `+0/~1/-0`（llm-wiki）                                       | 固定源码振荡，非漂移：Step 4b 在补丁还原态把镜像 llm-wiki 刷回上游版（~1），Step 8c 再回同步补丁版 + re-baseline。`PATCH-SKILLS-MIRROR-METADATA` 会从 `rsync --delete` 排除 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.curator_backups` / `.curator_suppressed` / `.hub` / `.archive` / `__pycache__/` / `*.pyc`，不得再把 runtime state 或 Python 字节码缓存计入 mirror；rsync 非零必须使整轮失败                                                                                                                                                                                                                                                                                                                                                                           |
| `hermes update` 的 runtime repair（E-949）整体重建 venv                           | 2026-07-25 首现：SQLite 缺陷版本触发私有 runtime 重建，只按 uv.lock 装包——dev 工具链、`PATCH-FEISHU-SOCKS-DEPENDENCY` / `PATCH-DOCUMENT-EXTRACTION` 的依赖 pin、文档/STT/平台 lazy 栈可能丢失；lazy refresh 又可能在补丁还原态误判 current。补救（常设授权，Step 2b 当轮自动执行）：补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"` 恢复 lazy 栈，再恢复 pytest 工具链；旧 venv 停放 `venv.stale.runtime-*`，旧进程退净后可删。                                                                                                                                                                                                                                                                                                         |
| GitHub HTTPS `LibreSSL SSL_ERROR_SYSCALL` / connect timeout                       | 先用 `curl` 与 `ssh -T -p 443 git@ssh.github.com` 区分网络和 Git TLS 故障；SSH 443 可用时，用进程级 `GIT_CONFIG_COUNT/KEY/VALUE` 注入 `url.ssh://git@ssh.github.com:443/.insteadOf=https://github.com/`，不要永久改 remote。若首次 acquisition 已取得 SHA，后续只能 `--reconcile`；若它在 3 次 transport retry 后仍是 `phase=acquiring / target_sha=pending`，按脚本 recovery clause 恰好再用一次带该进程配置的 `--update` 接管同一 acquisition。上游 CLI 会把 rewrite 后的等价 URL 误判为 fork：拒绝新增 `upstream`，收尾确认 remote URL 未变、`HEAD == TARGET_SHA`，并删除交互在调用目录产生的 `.skip_upstream_prompt`。2026-08-16 实例即由 HTTPS 75s connect timeout 改走 SSH 443 后固定 `8ad055414`。                                                                                                         |
| Feishu 普通引用回复 lane 与上游 metadata 驱动语义对撞                             | **高危语义冲突**（post-26e0b1c）：上游 `reply_in_thread = bool(metadata.thread_id)`（metadata 驱动投递 lane）与 `PATCH-FEISHU-NORMAL-REPLY` 的"固定 False、忽略 generic thread metadata"方向相反，同一 send/reply-body 区域的 3-way 结果不可信任自动合并。必须人工按本地不变量重解（普通引用永不进 thread lane），复验补丁自有三条路径回归后才能刷新 bundle；详见 PATCHES.md 该补丁块对撞警示。**同一 conflate 有入站侧孪生**（2026-08-12 起）：入站 `thread_id = ... or root_id` 由 `PATCH-FEISHU-QUOTE-CHAIN-SESSION` 单独守护——`root_id` 是引用链根而非话题 id，回退它会让每条引用链切出独立 session。两侧必须一起复核：3-way 触及 `plugins/platforms/feishu/adapter.py` 后同时核对出站 `reply_in_thread = False` 与入站不含 `root_id` 两个锚点。2026-08-12 实测本轮上游未触及该文件，预案未被消费、继续有效。 |

| config 迁移一次性重置用户可见状态（如 v34 personality reset） | 迁移本身属 P0 当轮执行（`hermes doctor --fix`），但遇到"上游有意重置用户状态"的迁移时**不回写旧值**——那会复活迁移要消灭的歧义态。记录旧值与官方恢复命令，在最终报告显著提示由用户决定是否恢复。v34 实例（2026-08-10）：`display.personality: kawaii → none`（该值自 2026-04-15 初始提交未变），恢复用 `/personality kawaii`；迁移伴随的 YAML 引号/列表风格重排为语义无变化噪音。 |
| `hermes doctor --fix` 报 `platform 'X' references unknown toolset` | 该校验（`hermes_cli/toolset_validation.py`，#38798 动机）仅在 `--fix`/迁移路径运行，普通 doctor 不报。先分流：**插件运行时注册名**（如 `sandbox_group`）在 CLI 上下文未加载网关插件属预期误报，不修；**真实死条目**（如 `vision_tools`——注册名实为 `vision`，`resolve_toolset` 恒返回空）按群聊工具两层一致原则处置——沙箱 allowlist 本就不放行的能力直接删条目（运行时行为零变化），确需该能力才改正名并同步 allowlist。凡触及 `plugins/sandbox/verify.sh` 期望契约的改动必须复跑 Step 8e verifier。2026-08-10 已删 `vision_tools` 死条目。 |
| `test_read_extract.py` 报 3 skipped（firecrawl-anydoc not installed） | 上游 real-binding 测试类按设计在可选包 `firecrawl-anydoc` 缺失时跳过；本机未装，**3 skipped 是预期基线、不是回归**（2026-08-10 起）。安装该包属引入全新依赖，不在常设授权内；上游将 anydoc 转为必需依赖、或用户明确决定安装后，删除本 row 并更新基线。 |
| doctor 报 `⚠ browser (system dependency not met)` 而 agent-browser/Playwright 均 ✓ | Browser Use CLI 模式的表象而非依赖缺失：`browser.backend` 未设时，只要 browser-use CLI"可运行"（含仅有 `uvx` 在 PATH，首用才从 PyPI 临时拉包）即接管默认后端（上游 `a1835c8c1`/`8d8bc85dc`，2026-08-11 起），内建 browser\_\* 整体隐藏、由 `browser_exec` 替代。本机以 `browser.backend: 'off'` 锁回内建工具（YAML 值必须加引号，裸 `off` 会被解析成布尔 False 走回默认判定）；启用 Browser Use 属引入全新依赖，须用户明确 opt-in 并本机验证。用户启用后或上游改为要求真实安装二进制时，删除或改写本 row。 |
| 改了 `config.yaml` 的群聊能力面后 Step 8e verifier 失败 | `plugins/sandbox/verify.sh` 对**群可读 skill allowlist**（`skills.platform_allowed.feishu_group`）、群 toolset 集合与固定 Feishu script action 集做**精确相等**断言，不是子集断言。这是刻意设计：扩大群聊可读/可用面必须是显式且被验证的动作，不能靠改一处配置静默生效。2026-08-12 实抓：给 `config.yaml` 增开 `excel-processing` 未同步 verifier，整轮升级非零、事务保留。处置：先判定该能力是否真的不扩大工具面（本例 `excel-processing` 只有 `scripts/`，而群聊无 `terminal`/`process`/`code_execution`、`feishu_doc_manage` 只映射 `feishu_doc_scripts_root` 下固定 action，故只读知识、不扩面），把结论写进 verifier 断言旁的注释再同步契约；若该能力**确实**新增可执行面，必须同时评估沙箱 allowlist 与 `PATCH-FEISHU-GROUP-SANDBOX` 的边界描述。凡改动 `config.yaml` 的 `skills.platform_allowed` / `platform_toolsets` / `plugins/sandbox/config.yaml` 三者之一，都要预期本 verifier 需同步。上游无关，本 row 长期有效，除非 verifier 改为子集语义（那会削弱边界，不应主动做）。 |
| 重写 `PATCHES.md` §「最近一次升级」摘要后活跃 PATCH 少一个 | 2026-08-11 实抓：按 `s.index("\n---", i)` 定界旧摘要会**跨过紧随其后的 `### [PATCH-*]` 定义块**（摘要与下一个补丁块之间的 `---` 不是摘要的结束符），一次替换静默吞掉 `PATCH-SKILL-CREATE-ROOT` 整块，Step 5 第 3 条断言（活跃块数 vs 注册表口径）才暴露。改写摘要时定界必须用**下一个 `### [PATCH-` 标题**而非 `---`；**且该标题必须锚定行首**（`re.compile(r"^### \[PATCH-", re.M).search(s, i)`）——2026-08-12 实抓续集：裸 `s.index("### [PATCH-", i)` 会命中「活跃补丁」段落里的**行内字面量** `` `### [PATCH-*]` 定义块 ``（该句就在摘要自身内部），使定界点落在摘要中途、`rindex` 找不到分隔线而抛 `ValueError`。写前抛错是幸运情形（本次未落盘）；若字面量出现在分隔线之后就会静默截断。若已吞块，从 `git show HEAD:patches/PATCHES.md` 取回该块按原顺序插回，再复跑 Step 5 断言。上游吸收无关，本 row 长期有效，除非摘要节与补丁定义节被拆成两个文件。 |
| 活跃 PATCH 定义误放进 Archive、再用续接标题接回 | 2026-08-15 实抓：`PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY` 状态、源码 hunk、Step 8b gate 和回归都仍活跃，却夹在两个已归档模型补丁之间；随后再开一个活跃续接标题，导致文档阅读顺序与生命周期边界错位，且“首个 Archive 前定义数”只有 32、注册表/README 却写 33。处置：所有活跃定义连续放在首个 Archive 前并按职责类别分组，所有 Archive 统一后置；Step 5 同时断言不得出现续接标题，并检查 Archive 下带状态表的定义只能是“已归档/已上游合并”。若未来 PATCH 注册表拆成机器可读索引 + 独立定义文件，可按新结构改写或删除本 row。 |

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
