# Hermes 升级 Playbook

> **用法**：在 Claude Code 会话中说一句 `阅读 ~/.hermes/hermes-update.md 按计划做`，agent 即按本 playbook 一条龙完成"升级内层官方源码 checkout + 回贴本地 patch + 依赖自愈 + 补丁回归修到全绿 + 对齐外层监管记录/文档"，中途不打断、不追问，**收尾零遗留**。
>
> **权威来源分工**：`hermes-update.sh` 是升级执行与回放 gate 的权威，`patches/PATCHES.md` 是语义 PATCH 注册表的权威，`patches/local-patches.diff` 是工程内补丁的唯一物理回放包。三者必须闭环一致；本 playbook 用**发现规则 + 决策规则**驱动，不复制一份会过期的补丁清单。

---

## 仓库模型与目标

本目录有两个职责不同的 Git 仓库，升级时必须分开判断：

- `~/.hermes`：用户的 Hermes 配置备份仓库。它监管 `hermes-update.sh`、`patches/local-patches.diff`、`patches/PATCHES.md`、`config.yaml`、`plugins/`、`my-skills/`、README/wiki 等升级记录；**升级完成后只在这个外层仓库提交**。其中 `PATCH-FEISHU-GROUP-SANDBOX` 这类用户插件安全补丁不进入内层 unified diff，而由外层 Git + Step 8e 强制 verifier 监管。
- `~/.hermes/hermes-agent`：官方 `NousResearch/hermes-agent` 源码 checkout。升级目标在这里；本地 patch 以 modified files 形式应用在这里，但**不要在这个内层仓库提交**，除非用户另行明确要求维护 fork。

默认升级目标是 `~/.hermes/hermes-agent` 的官方 `origin/main`，即让内层 checkout 与 `origin/main` 拉平。`hermes update` 当前默认也是 `--branch main`，会 fetch/pull `origin/main`。如用户明确要求稳定 release/tag，不要把它混同于默认流程：先记录目标 tag/branch，并确认 `hermes-update.sh`/patch 回贴流程是否支持该目标后再执行。

### 补丁模型（本轮重构后的固定边界）

- **语义层**：每个 `PATCH-<DOMAIN>-<INVARIANT>` 是独立的问题、回滚、验证和上游吸收单元；语义定义只在 `PATCHES.md` 出现一次。
- **物理层**：所有工程内源码补丁合并存放在一个 `local-patches.diff`。这是有意设计：多个语义补丁会共享同一文件，强拆物理 diff 会制造 hunk 顺序依赖；不能因为物理上只有一个 bundle 就把逻辑补丁合并成一个生命周期。
- **外层插件层**：`PATCH-FEISHU-GROUP-SANDBOX` 等配置仓库补丁由外层 Git 和独立 `verify.sh` 监管，不得进入内层 `PATCHED_FILES` 或 replay bundle。
- **运行时层**：`PATCH-NPM-DEPENDENCY-HYGIENE` 等升级期策略由 `hermes-update.sh` 对应步骤重建，不以源码 hunk 或 Step 8b gate 表示。
- **归档层**：上游已吸收的补丁移入 Archive；如仍保留回归 sentinel，该 sentinel 与本地源码 hunk 是两回事，不能因此继续把补丁算作活跃。

---

## Agent 执行流程（一次跑完）

### Step 1 — 状态快照

记录以下用于后续摘要：

- `cd ~/.hermes/hermes-agent && git fetch origin main && git rev-parse HEAD origin/main && git rev-list --count HEAD..origin/main` → 当前内层源码 `HEAD`（记为 `OLD_SHA`）、目标 `origin/main`、落后 commit 数
- `hermes --version` → 仅作安装展示摘要；**不要**用它决定是否跳过升级（它可能展示已 fetch 的 upstream SHA，而不是内层 checkout 的实际 HEAD）
- `hermes doctor` 头部摘要
- `hermes gateway status` → 当前 PID + launchd 监管状态；若输出包含 LastExitStatus 一并记录
- `cd ~/.hermes && git status` → 外层配置备份仓库状态，区分"升级相关监管文件"和"用户在编辑的其他东西"
- `cd ~/.hermes/hermes-agent && git status -sb` → 内层官方源码仓库状态，区分"本地 patch modified files"和"非 patch 的用户改动"
- 当天日期（记为 `OLD_DATE` 用于 grep；本次升级新日期记为 `NEW_DATE`）

只有当 `~/.hermes/hermes-agent` 相对目标 `origin/main` 落后 0 commits，且外层 patch 快照/文档没有需要刷新的现状陈述时，才允许跳过实际更新、依赖恢复、功能回归和文档改写；但仍须执行 Step 3 的只读闭环检查，并运行所有 Step 8e verifier 核对当前 Gateway PID 后，才能到 Step 6 报告“已是最新”。不要因为 `hermes --version` 显示 `Up to date` 就跳过。

### Step 2 — 跑升级脚本

```bash
bash ~/.hermes/hermes-update.sh
```

建议 background + tee 日志，超时 ≥ 600s。脚本自带：preflight / 内层 patch 存档到外层 `patches/local-patches.diff` / `hermes update` 拉平内层官方 checkout / npm audit / skills 镜像 / gateway plist / 补全脚本 / patch 回贴 + 行为化验证 / gateway 重启 / 用户 plugin verify / 健康检查。

退出码 0 不代表完美。**通读输出**，特别关注：

- 各 PATCH 行为化验证是否 OK
- Step 8e 的每个用户插件 verifier 是否存在、可执行且返回 0；任一失败都必须使整次升级返回非零
- Skills mirror 的 `+/~/-` 数字
- 任何 `⚠` 或 `✗` 行
- `Recommended actions:` 区
- `uv` 是否走了 `--python venv/bin/python` fallback（频繁触发，正常自愈，记下次数即可）

脚本结束后从 `cd ~/.hermes/hermes-agent && git rev-parse HEAD` 取新的实际源码 `HEAD`，记为 `NEW_SHA`；可同时记录 `hermes --version` 的展示值，但它不是 `NEW_SHA` 的权威来源。

### Step 2b — 依赖自愈（常设授权，不追问）

升级可能重建/漂移 venv 与 node_modules（见摩擦表 runtime repair row）。每轮固定检查并自动修复，目标是**恢复升级前既有能力**，在跑回归前完成：

- 升级日志出现 venv 重建 / runtime repair 时：对比旧 venv（`venv.stale.*/bin/python -m pip list --format=freeze`）与新 venv 包清单。版本回到 uv.lock pin 的**回锁差异不动**；整包丢失的按序回装——① 补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"`（拿补丁态依赖元组，补回 PATCH pin 的 python-socks / pypdf 等）；② dev 工具链按 pyproject `[dev]` extra 的 pin；③ 其余按旧 venv 精确 pin `uv pip install --python venv/bin/python <pkg>==<ver>`。
- `hermes doctor` 报 npm 声明依赖缺失（如 agent-browser）→ 仓库根 `npm install`。
- **授权边界**：恢复"此前已存在"的包/工具属**用户常设授权**（2026-07-25 起），直接执行不追问；引入旧环境从未有过的**全新**依赖不在授权内，留报告等用户。
- 环境残留清理：误建的 `.venv`（uv 默认项目环境，会让 `uv run` 跑错解释器）直接删除；`venv.stale.*` 用 `lsof +D` 确认无进程占用后删除，有占用则报告待删。
- 依赖恢复完成后重新运行 `bash ~/.hermes/plugins/sandbox/verify.sh`（以及 Step 8e 登记的其他 verifier）。这一步不能省：若 Step 8e 先前仅因 venv 重建丢失 pytest 而失败，恢复依赖后必须重新证明 `PATCH-FEISHU-GROUP-SANDBOX` 的 YAML、toolset、行为测试和 runtime trace 全绿；runtime trace 必须绑定 `hermes gateway status` 返回的**当前 PID**，不能用任意一条历史注册日志代替。
- 处置结果写进升级摘要与摩擦表。

### Step 2c — 补丁功能回归（终态必须 0 failed）

patch 回贴 + 依赖自愈后，用 `scripts/run_tests.sh` 批量跑 `PATCHED_FILES` 里全部 `tests/**` 文件，与 `PATCHES.md` § 当前版本摘要里记录的上轮基准（passed 数）对比。禁止直接调用 `pytest`；runner 会隔离 HOME/凭据、固定时区/locale，并逐测试文件放进独立子进程，结果才与 Hermes CI 口径一致。**回归终态 0 failed 是本 playbook 的完成标准**——出现新失败先定性、再按分支当轮修到转绿，不留遗留：

1. **环境缺口**（依赖缺失 / 解释器变化）→ 回到 Step 2b 补装后复跑；
2. **上游自身 bug**（`git stash push -- <相关源文件+测试>` 后在裸上游复跑同样失败）：影响本部署行为或本回归套件的，**本地补丁修复**——按 Step 4 的补丁归并原则决定并入现有语义 PATCH 还是新增语义 PATCH，同步 sentinel / PATCHED_FILES / PATCHES.md / 快照，修到转绿；确实不影响本部署行为且测试不在本套件内的，才允许只记摩擦表；
3. **补丁真回归**（仅打补丁后失败）→ 修补丁本身。

工具注意：pytest 若因 venv 重建暂缺，可先 `pip install --target /tmp/... --no-deps pytest==<pin> pytest-asyncio==<pin>` + `PYTHONPATH` 叠加做初步定性（不污染 venv），但最终数字必须用 `scripts/run_tests.sh` 复跑得出；**禁止用 `uv run` 跑回归**——它会挂到 `.venv`（uv 默认项目环境）而不是 hermes 的 `venv`，产生成批假失败。

### Step 3 — 审查 patch & 脚本

`patches/local-patches.diff` + `patches/.local-patches.base` 由脚本自动刷新，属于外层 `~/.hermes` 仓库的监管记录。不能只看 patch apply 成功；本轮重构后，每次升级必须完成下面的仓库级闭环：

| 层面              | 终态必须成立                                                                                                                                                                                                                                                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **受管文件集合**  | 从 `hermes-update.sh` 现场解析 `PATCHED_FILES`，不得依赖文档快照。每个受管文件都应有预期内 diff；内层其他 modified/untracked 文件逐项归类。已知 `package-lock.json` npm 归一化噪音可保留，但不得混入 replay bundle。                                                                                          |
| **bundle 一致性** | `git -C ~/.hermes/hermes-agent diff HEAD -- <PATCHED_FILES>` 与 `patches/local-patches.diff` **逐字节一致**。文件数量、行数或“看起来一样”都不能替代 `cmp`。                                                                                                                                                   |
| **可回放性**      | 确认内层 index 干净后，`git -C ~/.hermes/hermes-agent apply --cached --check ../patches/local-patches.diff` 对 HEAD 正向通过；当前已打补丁的 worktree 上执行 `git -C ~/.hermes/hermes-agent apply --check --reverse ../patches/local-patches.diff` 通过。两项分别证明“下次能贴”和“当前 bundle 确实描述现状”。 |
| **基线来源**      | `patches/.local-patches.base` 第一列 SHA 等于内层 `git rev-parse HEAD`；时间戳只作审计信息。                                                                                                                                                                                                                  |
| **语义注册表**    | `PATCHES.md` 中活跃 + Archive ID 全局唯一；活跃块各有且仅有 `问题`、`修复`、`验证`、`上游吸收判断` 四段；不得出现 `LEGACY`、纯数字或 A/B 变体命名。                                                                                                                                                           |
| **执行链注册**    | 每个活跃补丁按类型有唯一执行链：工程内补丁对应 Step 8b 独立 sentinel/gate 并进入 8c 总闸门；运行时补丁对应明确 update step；外层插件补丁对应 Step 8e verifier。Archive sentinel 也必须保留明确执行链：Step 8b 的进入 8c 总闸门，工程外 sentinel（如 Step 7 completion）留在其原步骤并影响整次升级结果。       |
| **外层安全补丁**  | `PATCH-FEISHU-GROUP-SANDBOX` 检查外层 diff + `plugins/<name>/verify.sh`；`config.yaml` / `plugins/` / `my-skills/` 不得伪造进内层 replay bundle。verifier 必须核对当前 Gateway PID 的注册日志，证明运行进程已加载新策略。                                                                                     |

任何一项不成立都先修复再进入文档对齐，不能把不闭合的 bundle 或注册表写成“升级成功”。此外：

- `~/.hermes/hermes-agent` 里被 patch 修改的文件保持为 modified，不在内层仓库提交；外层 patch diff 才是可提交记录。
- `git diff` 检查 index hash / 行号漂移是否来自本次上游变化；共享文件上的 hunk 必须按语义 PATCH 分别解释。
- `hermes-update.sh` 顶部注释里的 baseline SHA 是**手写**的，本步骤手动改成 `NEW_SHA`。
- 如脚本本身在升级过程中报了新的兼容性问题（新 uv 报错、新 step），**记录在最终报告里**，不要自行扩展脚本的工作流逻辑（按补丁归并原则为新语义 PATCH 添加 sentinel 块与 gate 变量属既定补丁工作流，不在此限）。

### Step 4 — 文档对齐（发现式，不用预设清单）

用 grep 在仓库里找所有引用 `OLD_SHA` / `OLD_DATE` 的位置：

```bash
cd ~/.hermes && grep -rln -E "<OLD_SHA>|<OLD_DATE>" \
  --include="*.md" --include="*.sh" --include="*.py" \
  --include="*.yaml" --include="*.yml" --include="*.toml" . 2>/dev/null | \
  grep -v -E "^\./(hermes-agent|tmp|sessions|logs|state-snapshots|memories|\.git|skills|cron|db_workspace|completions/_hermes)"
```

对每个命中文件，按下表决定改不改：

| 命中位置类型                                                       | 处置                                                      |
| ------------------------------------------------------------------ | --------------------------------------------------------- |
| "当前版本" / "适用版本" / "本手册基于" / "baseline" 类**现状陈述** | **改**，更新到 NEW_SHA/NEW_DATE                           |
| "basis OLD → NEW" / "较 OLD 前进 N commits" 类**差量描述**         | **不改**（历史差量）                                      |
| 版本记录 / changelog / 升级历史表里的**旧 row**                    | **不改**（历史快照）                                      |
| 不带版本号的概念性文档（实体定义、抽象架构）                       | 不会命中；命中说明是无关引用                              |
| 命中任何 `wiki/**` 路径                                            | 见下方 **Wiki 编辑规范**（按 Layer 分别处置，不要一刀切） |

**新增内容**（属于"对齐"的一部分）：

- `README.md` 版本记录表 → 顶端插入本次升级 row
- `patches/PATCHES.md` § 当前版本 → 重写 header + "最近一次升级"摘要

摘要写作 5 段固定结构（保持跨升级一致）：

1. **上游主线**：按分类列改动（安全 / Gateway / Skills / Desktop / 模型 / Email / Web / Dashboard / 等），每条附 PR# 或 commit hash 短前缀
2. **patch apply / registry**：clean / 3-way / 冲突、Step 3 闭环结果、锚点漂移 `OLD → NEW`，以及本轮新增 / 部分吸收 / 归档的语义 PATCH ID
3. **依赖**：venv 包升降级 + `npm audit fix` 结果 + Skills mirror `+/~/-`
4. **已知摩擦**：复发的 uv / launchd / npm / patch 问题 → 本次处置
5. **配置漂移**：`hermes doctor` 报的 `Config version` 状态 + 是否需要 `--fix`

#### 语义 PATCH 块的组织原则（写入 `patches/PATCHES.md` 时严格遵守）

每个 `### [PATCH-<DOMAIN>-<INVARIANT>]` 定义块在整份 `PATCHES.md` 里**仅出现一次**，并且必须各有且仅有 `**问题**`、`**修复**`、`**验证**`、`**上游吸收判断**` 四段。ID 描述稳定的不变量，禁止 `LEGACY`、纯数字、A/B 子编号或按升级批次命名。

每轮升级必须逐个读取活跃块的 `上游吸收判断`，对新 upstream 实现和测试做核验。**apply 成功只能证明 hunk 还能贴，不能证明补丁未被上游吸收；sentinel 通过只能证明行为存在，也不能区分行为来自上游还是本地 patch。** 判定后二选一：

- **仍活跃或仅部分吸收** → 留在 `## 当前版本` 节下；部分吸收时删除已冗余 hunk，更新四段使其只描述剩余本地不变量，然后重新生成 bundle。
- **本轮完全吸收** → 先在裸 upstream 状态证明行为和测试成立，再把整个语义 PATCH 块从当前节**移动**（不是复制）到一个 `## Archive — PATCH-<DOMAIN>-<INVARIANT>` 归档节，并记录上游吸收版本/commit；删除该补丁独有 hunk，仅当某文件不再被任何活跃补丁触及时才从 `PATCHED_FILES` 移除；若脚本保留 sentinel 作为回归 guard，在归档节里注明，并保留在对应执行链和总闸门中。

升级摘要里只**提及**本轮新吸收的 PATCH（例如“`PATCH-FOO-BAR` 已被上游吸收并移入 Archive”），不要把 PATCH 块的内容复述进摘要。这样 `PATCHES.md` 始终是“活跃补丁 + 归档补丁”的并列结构，定义块不会在多处重复。

**新增 vs 并入（补丁归并原则）**：Step 2c 回归或摩擦驱动出新修复时，先扫一遍现有 PATCH 清单再落位，agent 自行判定、不请示——

- **并入现有语义 PATCH**：修复与该补丁共享同一不变量、必须一起回滚/验收，且预期上游会在同一个 PR 中吸收。例如新的 Feishu strong-flanking case 归入 `PATCH-FEISHU-MARKDOWN`。更新问题/修复/验证/上游吸收判断四段与 sentinel，不创建变体编号。
- **新增语义 PATCH**：能独立失效、独立回滚或被不同上游 PR 吸收的关注点必须拆开，即使改同一文件。例如 `PATCH-FEISHU-GROUP-APPROVAL` 与 `PATCH-APPROVAL-DARWIN-TMP` 都改 `approval.py`，但安全不变量和吸收条件完全不同。ID 使用 `PATCH-<DOMAIN>-<INVARIANT>`，禁止 A/B 子编号。
- 工程内补丁无论新增还是并入，四处同步缺一不可：新触及文件加入 `PATCHED_FILES`（已有文件免）；sentinel 块（新增 PATCH 时含 gate 变量并纳入 8c 刷新条件）；`PATCHES.md` 对应块；`local-patches.diff` / `.local-patches.base` 用与脚本 8c 相同的命令刷新，并按 Step 3 完成闭环核对。
- 运行时补丁不进入 `PATCHED_FILES` / replay bundle，但必须在 `hermes-update.sh` 有明确步骤、可审计输出和验证口径，并在 `PATCHES.md` 登记生命周期；不要为凑 Step 8b gate 制造空源码 hunk。
- 配置仓库用户插件补丁（当前 `PATCH-FEISHU-GROUP-SANDBOX`）不进入 `PATCHED_FILES` / `local-patches.diff`。它必须同时具备：外层 Git 跟踪的插件/配置/skill 文件；独立 `verify.sh`；`hermes-update.sh` Step 8e 固定登记；verifier 缺失、不可执行或失败时 `FINAL_RC=1`；`PATCHES.md` 对应块。verifier 至少结构化解析 YAML、解析真实平台 toolset、跑行为测试并核对**当前 Gateway PID** 的注册日志。

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

### Step 6 — 收尾报告

向用户报告（**不要自动提交**）：

- **完成标准**：补丁回归 **0 failed**、Step 3 七层仓库闭环全部成立、所有用户插件 verifier 绑定当前 Gateway PID 通过、doctor 无可修而未修的 ⚠、无环境残留。达不到时不得声称完成，单列阻塞项、原因与建议
- 升级 `OLD_SHA → NEW_SHA`，`+N commits`
- 文档对齐了哪些文件（列文件名 + 改动类别一句话，不展开内容）
- Gateway / Doctor 现状（异常项展开，正常项一行带过）；安全插件需报告 verifier 对照的当前 PID，以及 owner 主会话与群聊实际 toolset 是否仍满足边界
- 工作树里哪些是“升级相关”、哪些是“用户先前在编辑的其他东西”，提示后者保持不动；明确说明内层受管 modified files 是预期 patch overlay，外层 bundle 才是待提交记录
- 若 Step 2/3 中发现脚本侧的新兼容性问题，单列一节描述给用户决策
- 提醒：若用户随后明确要求提交，只提交外层 `~/.hermes` 仓库里的升级监管改动；不要在 `~/.hermes/hermes-agent` 创建 commit

---

## 已知摩擦速查（用户可补充）

| 现象                                                            | 处置                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` 报 "No virtual environment ... `~/.local/share/uv/python`" | 脚本固化了 `--python venv/bin/python` fallback，会自愈                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `hermes doctor` 报 web / ui-tui build-tool 高危                 | npm arborist crash 已知 bug，待上游 lockfile bump，不阻塞                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| launchd `Bootstrap failed: 5`                                   | 上游 PR #40831 已修，基线 ≥ `d62979a6` 后不复现                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| PATCH 行号漂移                                                  | `hermes-update.sh` Step 8 自动 rebase；摘要里写 `OLD → NEW` 即可                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `local-patches.diff` 自身带 conflict marker                     | 脚本会拦截；`git restore --source=HEAD -- patches/local-patches.diff` 恢复入库版本后重跑                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 某个活跃 PATCH 疑似已被上游吸收                                 | 不依赖脚本自动标 `retired`；逐个按该块的 `上游吸收判断` 在裸 upstream 验证。完全吸收后删除其独有 hunk、移动定义块到 `## Archive — PATCH-...`，仅在文件不再被其他活跃补丁触及时移出 `PATCHED_FILES`；部分吸收则保留活跃块并收缩 hunk/四段描述，最后重跑 Step 3 闭环                                                                                                                                                                                                                                        |
| 新增本地补丁                                                    | 先按 Step 4 判断并入还是新增语义 PATCH；工程内补丁同步 `PATCHED_FILES`、独立 sentinel/gate、`PATCHES.md` 四段和 replay bundle/base；运行时或外层插件补丁走各自管道。不能只等下次 Step 2 自动 capture                                                                                                                                                                                                                                                                                                      |
| 用户插件 verifier 缺失或失败                                    | `PATCH-FEISHU-GROUP-SANDBOX` 类外层安全补丁不得继续显示升级成功。恢复 `plugins/<name>/verify.sh` 的文件/执行位，修复根配置、插件配置或上游 hook/toolset 兼容性，直到 Step 8e 对照当前 Gateway PID 返回 0；不要把外层文件加入内层 `PATCHED_FILES`                                                                                                                                                                                                                                                          |
| 补丁整体 apply 失败（上游真实冲突，脚本已回滚）                 | 手工 `cd hermes-agent && git apply --3way ~/.hermes/patches/local-patches.diff`，解决带 `<<<<<<<` 标记的文件（多为"并存"型：上游新增与补丁插入同位），`git add <冲突文件> && git reset` 清索引，然后**重跑脚本**——Step 2 会从工作树捕获已解决的 diff 并走完整验证。注意：`git apply` 输出别接 `head` 截断，SIGPIPE 会中断 apply                                                                                                                                                                           |
| `package-lock.json` 在 npm audit fix 后 dirty                   | 本机 npm 可能归一化排序 / `peer` 标记，也可能把传递依赖推进到 audit 可用的补丁版本。每轮必须先审查实际 diff：确认 `package.json` 无意外语义变化、记录版本升降和剩余 advisory，再把可解释的 lock drift 保留在内层工作树且排除出 replay bundle；不得一律按“无版本变化噪音”跳过。                                                                                                                                                                                                                            |
| `test_approval.py` 的 verifier temp cleanup 测试在 macOS 失败   | 上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 对 temp_dir 做 `realpath`（`/tmp`→`/private/tmp`）而 operand 不做，Darwin 上恒不匹配，其自带测试预期失败；裸上游同样失败、与本地 patch 无关。由 `PATCH-APPROVAL-DARWIN-TMP` 仅对 `/private` 系统别名放行 raw 拼写，其余 symlink 保持 fail-closed。上游统一 realpath 后归档该补丁并删除本 row                                                                                                                                                      |
| `test_feishu.py` 的 SSRF connect-time rebind 测试偶发失败       | 真实原因（2026-07-29 定性，推翻旧"跨文件状态"结论）：上游测试只 blank 代理 env 变量，httpx `trust_env` 在 env 为空时经 `urllib.request.getproxies()` 回落 macOS **系统代理配置**——宿主 Clash 系统代理开着就必失败（守卫按设计把解析委托给代理，收到裸 `httpx.ConnectError`），关着就通过，与批量/单跑无关；裸上游同样失败，与本地 patch 无关。已由 `PATCH-FEISHU-SSRF-TEST-SYSPROXY` 在测试内补 `patch("httpx._utils.getproxies", return_value={})` 修 hermetic；上游吸收后归档该补丁并删除本 row         |
| 升级窗口内 Matrix 重进 lazy refresh 并报 ⚠                      | Step 3 期间补丁处于还原态、`PATCH-LAZY-ACTIVATION` 锚点暂不生效，属固有时序；refresh 失败本身是 python-olm 构建问题，backend 保留既装版本，回贴后恢复，忽略即可                                                                                                                                                                                                                                                                                                                                           |
| Skills mirror 每轮报 `+0/~1/-1`（llm-wiki）                     | 固定振荡，非漂移：Step 4b 在补丁还原态把镜像 llm-wiki 刷回上游版（~1）并删 manifest 基线（-1），Step 8c 再回同步补丁版 + re-baseline。每轮出现属预期，终态始终为补丁版                                                                                                                                                                                                                                                                                                                                    |
| `hermes update` 的 runtime repair（E-949）整体重建 venv         | 2026-07-25 首现：SQLite 缺陷版本触发私有 runtime 重建，只按 uv.lock 装包——dev 工具链、`PATCH-FEISHU-SOCKS-DEPENDENCY` / `PATCH-DOCUMENT-EXTRACTION` 的依赖 pin、文档/STT/平台 lazy 栈可能丢失；lazy refresh 又可能在补丁还原态误判 current。补救（常设授权，Step 2b 当轮自动执行）：补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"` 恢复 lazy 栈，再恢复 pytest 工具链；旧 venv 停放 `venv.stale.runtime-*`，旧进程退净后可删。 |
| GitHub HTTPS `LibreSSL SSL_ERROR_SYSCALL`                       | 先用 `curl` 与 `ssh -T -p 443 git@ssh.github.com` 区分网络和 Git TLS 故障；SSH 443 可用时，仅对本轮进程设置 `url.ssh://git@ssh.github.com:443/.insteadOf=https://github.com/`，不要永久改 remote。上游 CLI 会把 rewrite 后的等价 URL 误判为 fork：拒绝新增 `upstream`，收尾确认 `origin` 未变、`HEAD == origin/main`，并删除交互在调用目录产生的 `.skip_upstream_prompt`。                                                                                                                                |

> 这张表是**可扩展**的：发现新摩擦就追加 row。

---

## 行为约束

- **不要自动提交**。升级结束先报告；按全局 guardrail 等用户明示"提交一下"再走外层 `~/.hermes` 仓库的 `copilot-git-approve` 流程
- **不要在 `~/.hermes/hermes-agent` 提交**。该仓库是官方源码 checkout，本地 patch 由外层 `patches/local-patches.diff` 监管；除非用户明确要求维护 fork，否则内层只允许 fast-forward/checkout 和 modified patch files
- **不要修改**版本记录表里的旧 row、PATCHES.md 升级摘要里的 "basis OLD → NEW" 句子（都是历史差量）
- **不要触碰**已 modified 但与升级无关的工作树文件（如 `memories/USER.md` 的用户编辑、未跟踪笔记）
- **不要后台跑** `gh copilot` / `claude` / `codex` 等 AI CLI
- **不要中途追问**用户，也**不要把可修的问题留到报告里等确认**。回归失败、依赖缺口、doctor 可修 ⚠ 一律当轮按 Step 2b/2c 的分支修复到位（依赖自愈与回归所需的本地补丁均已常设授权）。只有两类允许留案并在最终报告单列：① 本地确实不可修的上游阻塞（如 npm lockfile 高危待上游 bump）；② 引入全新依赖或改变安全边界的决策
- **不要扩大范围**。本 playbook 仅做"对齐到新上游"；任何顺手优化 / 重构 / 文档大改都不要做，留给用户单独发起（Step 2b/2c 的依赖自愈与为回归全绿所需的本地补丁属份内事，不算扩大范围）
