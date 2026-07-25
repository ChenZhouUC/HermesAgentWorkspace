# Hermes 升级 Playbook

> **用法**：在 Claude Code 会话中说一句 `阅读 ~/.hermes/hermes-update.md 按计划做`，agent 即按本 playbook 一条龙完成"升级内层官方源码 checkout + 回贴本地 patch + 依赖自愈 + 补丁回归修到全绿 + 对齐外层监管记录/文档"，中途不打断、不追问，**收尾零遗留**。
>
> **稳定锚点**：仅 `hermes-update.sh`（本目录）。其余文档 / 脚本 / 代码会增删漂移，本 playbook 用**发现规则 + 决策规则**驱动，避免随时间过期。

---

## 仓库模型与目标

本目录有两个职责不同的 Git 仓库，升级时必须分开判断：

- `~/.hermes`：用户的 Hermes 配置备份仓库。它监管 `hermes-update.sh`、`patches/local-patches.diff`、`patches/PATCHES.md`、README/wiki 等升级记录；**升级完成后只在这个外层仓库提交**。
- `~/.hermes/hermes-agent`：官方 `NousResearch/hermes-agent` 源码 checkout。升级目标在这里；本地 patch 以 modified files 形式应用在这里，但**不要在这个内层仓库提交**，除非用户另行明确要求维护 fork。

默认升级目标是 `~/.hermes/hermes-agent` 的官方 `origin/main`，即让内层 checkout 与 `origin/main` 拉平。`hermes update` 当前默认也是 `--branch main`，会 fetch/pull `origin/main`。如用户明确要求稳定 release/tag，不要把它混同于默认流程：先记录目标 tag/branch，并确认 `hermes-update.sh`/patch 回贴流程是否支持该目标后再执行。

---

## Agent 执行流程（一次跑完）

### Step 1 — 状态快照

记录以下用于后续摘要：

- `cd ~/.hermes/hermes-agent && git fetch origin main && git rev-parse HEAD origin/main && git rev-list --count HEAD..origin/main` → 当前内层源码 `HEAD`（记为 `OLD_SHA`）、目标 `origin/main`、落后 commit 数
- `hermes --version` → 仅作安装展示摘要；**不要**用它决定是否跳过升级（它可能展示已 fetch 的 upstream SHA，而不是内层 checkout 的实际 HEAD）
- `hermes doctor` 头部摘要
- `hermes gateway status` → PID + LastExitStatus
- `cd ~/.hermes && git status` → 外层配置备份仓库状态，区分"升级相关监管文件"和"用户在编辑的其他东西"
- `cd ~/.hermes/hermes-agent && git status -sb` → 内层官方源码仓库状态，区分"本地 patch modified files"和"非 patch 的用户改动"
- 当天日期（记为 `OLD_DATE` 用于 grep；本次升级新日期记为 `NEW_DATE`）

只有当 `~/.hermes/hermes-agent` 相对目标 `origin/main` 落后 0 commits，且外层 patch 快照/文档没有需要刷新的现状陈述时，才直接跳到 Step 6 报告"已是最新"，跳过 2–5。不要因为 `hermes --version` 显示 `Up to date` 就跳过。

### Step 2 — 跑升级脚本

```bash
bash ~/.hermes/hermes-update.sh
```

建议 background + tee 日志，超时 ≥ 600s。脚本自带：preflight / 内层 patch 存档到外层 `patches/local-patches.diff` / `hermes update` 拉平内层官方 checkout / npm audit / skills 镜像 / gateway plist / 补全脚本 / patch 回贴 + 行为化验证 / gateway 重启 / 用户 plugin verify / 健康检查。

退出码 0 不代表完美。**通读输出**，特别关注：

- 各 PATCH 行为化验证是否 OK
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
- 处置结果写进升级摘要与摩擦表。

### Step 2c — 补丁功能回归（终态必须 0 failed）

patch 回贴 + 依赖自愈后，用 `venv/bin/python -m pytest -q` 批量跑 `PATCHED_FILES` 里全部 `tests/**` 文件，与 `PATCHES.md` § 当前版本摘要里记录的上轮基准（passed 数）对比。**回归终态 0 failed 是本 playbook 的完成标准**——出现新失败先定性、再按分支当轮修到转绿，不留遗留：

1. **环境缺口**（依赖缺失 / 解释器变化）→ 回到 Step 2b 补装后复跑；
2. **上游自身 bug**（`git stash push -- <相关源文件+测试>` 后在裸上游复跑同样失败）：影响本部署行为或本回归套件的，**本地补丁修复**——按 Step 4 的补丁归并原则决定并入现有 PATCH-N 还是新增 PATCH-N，同步 sentinel / PATCHED_FILES / PATCHES.md / 快照，修到转绿；确实不影响本部署行为且测试不在本套件内的，才允许只记摩擦表；
3. **补丁真回归**（仅打补丁后失败）→ 修补丁本身。

工具注意：pytest 若因 venv 重建暂缺，可先 `pip install --target /tmp/... --no-deps pytest==<pin> pytest-asyncio==<pin>` + `PYTHONPATH` 叠加做初步定性（不污染 venv），但最终数字必须用 venv 原生 pytest 复跑得出；**禁止用 `uv run` 跑回归**——它会挂到 `.venv`（uv 默认项目环境）而不是 hermes 的 `venv`，产生成批假失败。

### Step 3 — 审查 patch & 脚本

- `patches/local-patches.diff` + `patches/.local-patches.base` 由脚本自动刷新，属于外层 `~/.hermes` 仓库的监管记录 → `git diff` 看 index hash / 行号漂移是否在预期内
- `~/.hermes/hermes-agent` 里被 patch 修改的文件保持为 modified，不在内层仓库提交；外层 patch diff 才是可提交记录
- `hermes-update.sh` 顶部注释里的 baseline SHA 是**手写**的，本步骤手动改成 `NEW_SHA`
- 如脚本本身在升级过程中报了新的兼容性问题（新 uv 报错、新 step），**记录在最终报告里**，不要自行扩展脚本的工作流逻辑（按补丁归并原则为新 PATCH-N 添加 sentinel 块与 gate 变量属既定补丁工作流，不在此限）

### Step 4 — 文档对齐（发现式，不用预设清单）

用 grep 在仓库里找所有引用 `OLD_SHA` / `OLD_DATE` 的位置：

```bash
cd ~/.hermes && grep -rln -E "<OLD_SHA>|<OLD_DATE>" \
  --include="*.md" --include="*.sh" --include="*.py" \
  --include="*.yaml" --include="*.yml" --include="*.toml" . 2>/dev/null | \
  grep -v -E "^\./(hermes-agent|tmp|sessions|logs|state-snapshots|memories|\.git|skills|bot_feishu|cron|db_workspace|completions/_hermes)"
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
2. **patch apply**：clean / 3-way / 冲突；列锚点漂移 `OLD → NEW`
3. **依赖**：venv 包升降级 + `npm audit fix` 结果 + Skills mirror `+/~/-`
4. **已知摩擦**：复发的 uv / launchd / npm / patch 问题 → 本次处置
5. **配置漂移**：`hermes doctor` 报的 `Config version` 状态 + 是否需要 `--fix`

#### PATCH-N 块的组织原则（写入 `patches/PATCHES.md` 时严格遵守）

每个 `### [PATCH-N]` 块在整份 `PATCHES.md` 里**仅出现一次**，二选一：

- **仍活跃**（未被上游吸收）→ 留在 `## 当前版本` 节下
- **本轮被上游吸收** → 把整个 PATCH-N 块从当前节**移动**（不是复制）到一个 `## vX.Y.Z archive — PATCH-N 上游合并` 归档节，归档节按上游吸收所在的 release tag 命名；同步把该文件从 `hermes-update.sh` 的 `PATCHED_FILES` 数组移除；若脚本保留了 sentinel grep 作为回归 guard，在归档节里注明

升级摘要里只**提及**本轮新吸收的 PATCH（比如 "PATCH-X 于本轮上游合并，已归档至 vX.Y.Z 节"），不要把 PATCH 块的内容复述进摘要。这样 `PATCHES.md` 始终是"活跃补丁 + 历次归档"的并列结构，PATCH-N 不会在多处重复。

**新增 vs 并入（补丁归并原则）**：Step 2c 回归或摩擦驱动出新修复时，先扫一遍现有 PATCH 清单再落位，agent 自行判定、不请示——

- **并入现有 PATCH-N**：修复与该 PATCH 属同一问题域（同一功能关注点的又一处 case，预期上游会在同一个 PR 里吸收两者），如飞书出站渲染的新 case 并入 PATCH-16。并入时更新该块的 问题/修复/验证 三段与 sentinel 锚点，升级摘要提及，不新开编号。
- **新增 PATCH-N**：独立关注点，即使改的是同一文件（如 approval.py 上 PATCH-11 管群审批硬拦截、PATCH-23 管临时文件清理豁免）。判据：**上游吸收判断能否共用一句话**——预期上游会用不同 PR 分别修的，就分开编号。
- 无论哪种，四处同步缺一不可：新触及文件加入 `PATCHED_FILES`（已有文件免）；sentinel 块（新增 PATCH 时含 gate 变量并纳入 8c 刷新条件）；`PATCHES.md` 对应块；`local-patches.diff` / `.local-patches.base` 用与脚本 8c 相同的命令刷新，并与内层实际 diff 逐字节核对。

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

- **完成标准**：补丁回归 **0 failed**、doctor 无可修而未修的 ⚠、无环境残留。达不到时不得声称完成，单列阻塞项、原因与建议
- 升级 `OLD_SHA → NEW_SHA`，`+N commits`
- 文档对齐了哪些文件（列文件名 + 改动类别一句话，不展开内容）
- Gateway / Doctor 现状（异常项展开，正常项一行带过）
- 工作树里哪些是"升级相关"、哪些是"用户先前在编辑的其他东西"，提示后者保持不动
- 若 Step 2/3 中发现脚本侧的新兼容性问题，单列一节描述给用户决策
- 提醒：若用户随后明确要求提交，只提交外层 `~/.hermes` 仓库里的升级监管改动；不要在 `~/.hermes/hermes-agent` 创建 commit

---

## 已知摩擦速查（用户可补充）

| 现象                                                            | 处置                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` 报 "No virtual environment ... `~/.local/share/uv/python`" | 脚本固化了 `--python venv/bin/python` fallback，会自愈                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `hermes doctor` 报 web / ui-tui build-tool 高危                 | npm arborist crash 已知 bug，待上游 lockfile bump，不阻塞                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| launchd `Bootstrap failed: 5`                                   | 上游 PR #40831 已修，基线 ≥ `d62979a6` 后不复现                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| PATCH 行号漂移                                                  | `hermes-update.sh` Step 8 自动 rebase；摘要里写 `OLD → NEW` 即可                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `local-patches.diff` 自身带 conflict marker                     | 脚本会拦截；`git restore --source=HEAD -- patches/local-patches.diff` 恢复入库版本后重跑                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 某个 PATCH 上游已合并                                           | 脚本输出会标 "retired"；按 Step 4 的 **PATCH-N 组织原则**把该块从 `PATCHES.md` 当前节移动到 `## vX.Y.Z archive` 节，并从 `hermes-update.sh` 的 `PATCHED_FILES` 移除该文件                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 新增本地补丁                                                    | 在 `hermes-agent/` 直接改文件，下次升级 Step 2 自动 capture 进 `local-patches.diff`；同步把记录写入 `patches/PATCHES.md` 并加 verify 行为                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 补丁整体 apply 失败（上游真实冲突，脚本已回滚）                 | 手工 `cd hermes-agent && git apply --3way ~/.hermes/patches/local-patches.diff`，解决带 `<<<<<<<` 标记的文件（多为"并存"型：上游新增与补丁插入同位），`git add <冲突文件> && git reset` 清索引，然后**重跑脚本**——Step 2 会从工作树捕获已解决的 diff 并走完整验证。注意：`git apply` 输出别接 `head` 截断，SIGPIPE 会中断 apply                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `package-lock.json` 在 npm audit fix 后 dirty                   | 本机 npm 会把上游 lockfile 里 esbuild 平台条目的 `"peer": true` 归一化移除（无版本变化）。已知噪音：保留在内层工作树、不提交、不需处理；每轮 warning 复现属预期                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `test_approval.py` 的 verifier temp cleanup 测试在 macOS 失败   | 上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 对 temp_dir 做 `realpath`（`/tmp`→`/private/tmp`）而 operand 不做，Darwin 上恒不匹配，其自带测试预期失败；裸上游同样失败、与本地 patch 无关。2026-07-25 起由 **PATCH-23** 本地修复（仅对 `/private` 系统别名放行 raw 拼写，其余 symlink 保持 fail-closed），测试转绿、运行时清理豁免恢复。上游统一 realpath 后归档 PATCH-23 并删除本 row                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `test_feishu.py` 的 SSRF connect-time rebind 测试单跑失败       | `test_download_remote_document_blocks_connect_time_rebind` 依赖跨文件测试状态：23 个 patch 测试文件批量跑通过，单文件/单测跑失败（SSRF 守卫未触发，收到裸 `httpx.ConnectError`）；裸上游同样失败，与本地 patch 无关。回归统计以批量跑为准；上游修好测试隔离后删除本 row                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| 升级窗口内 Matrix 重进 lazy refresh 并报 ⚠                      | Step 3 期间补丁处于还原态、PATCH-21 锚点暂不生效，属固有时序；refresh 失败本身是 python-olm 构建问题，backend 保留既装版本，回贴后恢复，忽略即可                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| Skills mirror 每轮报 `+0/~1/-1`（llm-wiki）                     | 固定振荡，非漂移：Step 4b 在补丁还原态把镜像 llm-wiki 刷回上游版（~1）并删 manifest 基线（-1），Step 8c 再回同步补丁版 + re-baseline。每轮出现属预期，终态始终为补丁版                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `hermes update` 的 runtime repair（E-949）整体重建 venv         | 2026-07-25 首现：SQLite 缺陷版本触发私有 runtime 重建，只按 uv.lock 装包——dev 工具链（pytest 系 / ruff / ty / debugpy）、补丁 pin（python-socks / pypdf，PATCH-9/17）、PyMuPDF·openpyxl·python-pptx 文档栈、faster-whisper STT 栈、dingtalk 栈全部丢失；lazy refresh 又在补丁还原态按上游依赖元组判 "current" 不回装。补救（常设授权，Step 2b 当轮自动执行）：补丁回贴后跑 `venv/bin/python -c "from tools.lazy_deps import refresh_active_features; print(refresh_active_features())"` 恢复 lazy 栈，dev 工具链 `uv pip install --python venv/bin/python pytest==9.0.2 pytest-asyncio==1.3.0`；回归可先用 `pip install --target /tmp/... --no-deps` + `PYTHONPATH` 叠加临时跑。旧 venv 停放 `venv.stale.runtime-*`，旧进程退净后可删。（2026-07-25 同日经批准按此路径回装完毕，回归转绿；agent-browser 同因 node_modules 缺失、根目录 `npm install` 恢复） |

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
