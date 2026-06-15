# Hermes 升级 Playbook

> **用法**：在 Claude Code 会话中说一句 `阅读 ~/.hermes/hermes-update.md 按计划做`，agent 即按本 playbook 一条龙完成"升级到上游最新 + 对齐所有本地修改（patch + 文档）"，中途不打断、不追问。
>
> **稳定锚点**：仅 `hermes-update.sh`（本目录）。其余文档 / 脚本 / 代码会增删漂移，本 playbook 用**发现规则 + 决策规则**驱动，避免随时间过期。

---

## Agent 执行流程（一次跑完）

### Step 1 — 状态快照

记录以下用于后续摘要：

- `hermes --version` → 当前 release tag、upstream SHA（记为 `OLD_SHA`）、是否落后
- `hermes doctor` 头部摘要
- `hermes gateway status` → PID + LastExitStatus
- `cd ~/.hermes && git status` → 区分"升级相关"和"用户在编辑的其他东西"
- 当天日期（记为 `OLD_DATE` 用于 grep；本次升级新日期记为 `NEW_DATE`）

如果落后 0 commits，直接跳到 Step 6 报告"已是最新"，跳过 2–5。

### Step 2 — 跑升级脚本

```bash
bash ~/.hermes/hermes-update.sh
```

建议 background + tee 日志，超时 ≥ 600s。脚本自带：preflight / patch 存档 / `hermes update` / npm audit / skills 镜像 / gateway plist / 补全脚本 / patch 回贴 + 行为化验证 / gateway 重启 / 用户 plugin verify / 健康检查。

退出码 0 不代表完美。**通读输出**，特别关注：

- 各 PATCH 行为化验证是否 OK
- Skills mirror 的 `+/~/-` 数字
- 任何 `⚠` 或 `✗` 行
- `Recommended actions:` 区
- `uv` 是否走了 `--python venv/bin/python` fallback（频繁触发，正常自愈，记下次数即可）

从 `hermes --version` 取新的 upstream SHA，记为 `NEW_SHA`。

### Step 3 — 审查 patch & 脚本

- `patches/local-patches.diff` + `patches/.local-patches.base` 由脚本自动刷新 → `git diff` 看 index hash / 行号漂移是否在预期内
- `hermes-update.sh` 顶部注释里的 baseline SHA 是**手写**的，本步骤手动改成 `NEW_SHA`
- 如脚本本身在升级过程中报了新的兼容性问题（新 uv 报错、新 step），**记录在最终报告里**，不要自行扩展脚本逻辑

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

- 升级 `OLD_SHA → NEW_SHA`，`+N commits`
- 文档对齐了哪些文件（列文件名 + 改动类别一句话，不展开内容）
- Gateway / Doctor 现状（异常项展开，正常项一行带过）
- 工作树里哪些是"升级相关"、哪些是"用户先前在编辑的其他东西"，提示后者保持不动
- 若 Step 2/3 中发现脚本侧的新兼容性问题，单列一节描述给用户决策

---

## 已知摩擦速查（用户可补充）

| 现象                                                            | 处置                                                                                                                                                                      |
| --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv` 报 "No virtual environment ... `~/.local/share/uv/python`" | 脚本固化了 `--python venv/bin/python` fallback，会自愈                                                                                                                    |
| `hermes doctor` 报 web / ui-tui build-tool 高危                 | npm arborist crash 已知 bug，待上游 lockfile bump，不阻塞                                                                                                                 |
| launchd `Bootstrap failed: 5`                                   | 上游 PR #40831 已修，基线 ≥ `d62979a6` 后不复现                                                                                                                           |
| PATCH 行号漂移                                                  | `hermes-update.sh` Step 8 自动 rebase；摘要里写 `OLD → NEW` 即可                                                                                                          |
| `local-patches.diff` 自身带 conflict marker                     | 脚本会拦截；`git restore --source=HEAD -- patches/local-patches.diff` 恢复入库版本后重跑                                                                                  |
| 某个 PATCH 上游已合并                                           | 脚本输出会标 "retired"；按 Step 4 的 **PATCH-N 组织原则**把该块从 `PATCHES.md` 当前节移动到 `## vX.Y.Z archive` 节，并从 `hermes-update.sh` 的 `PATCHED_FILES` 移除该文件 |
| 新增本地补丁                                                    | 在 `hermes-agent/` 直接改文件，下次升级 Step 2 自动 capture 进 `local-patches.diff`；同步把记录写入 `patches/PATCHES.md` 并加 verify 行为                                 |

> 这张表是**可扩展**的：发现新摩擦就追加 row。

---

## 行为约束

- **不要自动提交**。按全局 guardrail 等用户明示"提交一下"再走 `copilot-git-approve` 流程
- **不要修改**版本记录表里的旧 row、PATCHES.md 升级摘要里的 "basis OLD → NEW" 句子（都是历史差量）
- **不要触碰**已 modified 但与升级无关的工作树文件（如 `memories/USER.md` 的用户编辑、未跟踪笔记）
- **不要后台跑** `gh copilot` / `claude` / `codex` 等 AI CLI
- **不要中途追问**用户。如脚本输出有不在已知摩擦清单里的新错误，采用最保守处置（保留现状、不自行扩展脚本逻辑）后写进最终报告
- **不要扩大范围**。本 playbook 仅做"对齐到新上游"；任何顺手优化 / 重构 / 文档大改都不要做，留给用户单独发起
