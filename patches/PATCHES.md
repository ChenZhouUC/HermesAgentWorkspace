# 本地补丁记录

> 本文件集中记录所有本地补丁。`hermes-agent/` 工程内语义补丁统一汇总到 `local-patches.diff` replay bundle；`~/.hermes` 配置仓库用户插件补丁单独标注，由外层 Git 与 `hermes-update.sh` Step 8e verifier 管理。
>
> **AI 维护规范**（详细工作流见 `~/.hermes/hermes-update.md` § Step 4）：
>
> - **每次升级后**重写 `## 当前版本：vX.Y.Z (upstream `main` `<SHA>`，YYYY-MM-DD)` header 与下方"最近一次升级"摘要；摘要遵循 5 段结构（上游主线 / patch apply / 依赖 / 已知摩擦 / 配置漂移）。
> - **新补丁**：使用稳定的语义 ID（`PATCH-<DOMAIN>-<INVARIANT>`），在 `## 当前版本` 节下新增一块 2-row 表（`文件 / 状态`）和 `问题 / 修复 / 验证 / 上游吸收判断` 四段。编号不表达顺序，禁止用 A/B 子编号承载不同吸收单元。
> - **边界判定**：一个补丁只能有一个可独立说明的责任边界、一个对应生命周期 gate（Step 3/4/7/8b/8e）和一个上游吸收条件。能被不同上游 PR 分别吸收的能力必须拆开；只有必须一起回滚、一起验收、一起吸收的改动才能合并。
> - **上游合并某补丁**：把该补丁块整体移动到对应 archive 节，记录吸收 commit 和保留的回归 sentinel；同步更新 `PATCHED_FILES`、验证 gate 和 replay bundle。
> - **每个语义 ID 的定义块在整份 PATCHES.md 里仅出现一次**——要么活跃、要么归档；依赖、验证和历史摘要可以引用 ID，但不得复制定义块。
> - **分类结构**：所有活跃定义必须连续放在首个 `## Archive` 之前，按职责类别分组；所有 Archive 统一后置。禁止在 Archive 之后用“活跃定义续接”标题重新打开活跃区，避免活跃状态与生命周期位置错位。
> - **审计叙事不累积**：升级期外的运行态审计/修复可在 `## 当前版本` 节下以带日期段落临时记录，但只存续到下一次"最近一次升级"摘要重写——重写时把仍有价值的事实并入 README 当周 row 后删除该段落；同一事件的长期容器只有 README 周 row（详见 playbook Step 4 叙事段生命周期规则）。
> - `completions/_hermes` 类**工程外补丁**：由 `hermes-update.sh` Step 7 inline Python 在补全脚本生成后检测并修复；上游修好后脚本自动跳过、检测块保留为回归 sentinel（PATCH-ZSH-COMPLETION-SYNTAX 即此类）。

---

## 补丁管理机制

### 总体架构

所有针对 `hermes-agent/` 源码的补丁以**单一 unified diff replay bundle** 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理。语义补丁是独立的行为与吸收单元；replay bundle 只是原子回放载体。多个补丁共享 `adapter.py`、`gateway/run.py` 等文件，强拆物理 diff 会引入脆弱的 hunk 顺序依赖，因此当前保持一个回放包，但 Step 8b 对每个语义补丁分别设 gate。

四类补丁走不同管道：

| 类型                 | 代表                                   | 管理方式                                                                                                                                                                                                 |
| -------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁**       | 当前清单中标记为“未上游合并”的源码补丁 | 统一 replay bundle (`local-patches.diff`) + `PATCHED_FILES` + 每补丁独立 invariant gate；完整行为由 playbook Step 2c 回归证明                                                                            |
| **配置仓库用户插件** | `PATCH-FEISHU-GROUP-SANDBOX`           | 外层 Git 跟踪 `config.yaml` / `plugins/` / `my-skills/`；Step 8e 强制校验配置、真实 toolset、行为测试和运行时注册，失败则整次升级非零退出                                                                |
| **运行时补丁**       | `PATCH-NPM-DEPENDENCY-HYGIENE` 等      | 由 `hermes-update.sh` 的明确步骤重建并验证，不进入 replay bundle；事务/完整性 gate 失败必须令整轮非零，npm audit 被上游 lock/range 阻塞且不影响飞书主链路时归为 P2，保留明确 warning/action 并在摘要定性 |
| **已上游合并**       | 文末 Archive                           | 保留吸收来源和回归 sentinel；不计入活跃补丁清单                                                                                                                                                          |

### 更新生命周期（关键步骤）

```
Transaction: fixed upstream snapshot（PATCH-UPDATE-TRANSACTION-PIN）
  ├─ `--update`：新事务执行 scoped official fetch；若 acquisition 从未取得 SHA、状态仍为 pending，可恰好恢复一次同一获取
  ├─ fetch 写专用事务 ref 后立即固定 TARGET_SHA；失败/中断以 0600 状态文件持久化
  ├─ 官方 updater 经临时 Git 代理消费 TARGET_SHA（内置 fetch no-op，origin/main 被替换）
  ├─ 默认/`--reconcile`：只围绕 TARGET_SHA 做本地收敛，禁止网络获取
  ├─ 未完成事务已有 target 时，即使再次传 `--update` 也只接管固定 SHA；无 target 时不得改用 reconcile 伪造完成
  └─ 仅整支脚本 exit 0 删除事务状态；origin/main 后续前进留给下一次用户升级

Step 2: Save & Clean
  ├─ 要求 index 干净；若仅部分 PATCHED_FILES 有 diff，fail closed，不覆盖完整旧 bundle
  ├─ git diff --full-index HEAD -- PATCHED_FILES → .tmp
  ├─ .tmp 必须通过 cached 正向 + worktree 反向 replay check，才原子替换 local-patches.diff
  ├─ _restore_patched_files_to_head PATCHED_FILES  ← 逐路径还原且保护同名 untracked 文件
  └─ 设置 _PATCHES_REVERTED=true（包括接管“裸 worktree + 完整 bundle”的中断现场）

Step 3: acquire once or reconcile pinned target
  ├─ 先 stash PATCHED_FILES 之外的额外改动（含 untracked）
  ├─ 新事务 `--update`：在干净工作区上执行唯一一次 upstream update
  │   └─ 仅尚未取得目标 SHA 的早期 GitHub fetch transport 失败最多重试 3 次
  ├─ 未完成事务/`--reconcile`：校验或本地 fast-forward 到 TARGET_SHA，不 fetch/pull
  └─ 随后 pop 回额外改动；若冲突则保留 stash 供手动恢复

Step 4b: Skills 镜像同步
  └─ rsync -a --delete hermes-agent/skills/ → ~/.hermes/skills/
      ├─ 新增 skill：自动复制到本地
      ├─ 更新 skill：覆盖本地旧版本
      ├─ 删除 skill：清理上游已移除但本地残留的孤儿
      ├─ 排除 .bundled_manifest / .curator_state / .usage.json / .hub / .archive 等本地 runtime state
      └─ rsync 非零：FINAL_RC=1
      （my-skills/ 为独立目录，不受此步骤影响）

Step 8: Re-apply & Verify（核心）
  ├─ 8a. Apply saved diff
  │   ├─ 前置检查：patch 文件自身是否含 conflict marker → 含则跳过
  │   ├─ 尝试 1: git apply --check + git apply（干净 apply）
  │   ├─ 尝试 2: git apply --3way（上游改了同区域但无冲突）
  │   ├─ 3-way 成功后立即 restore --staged，终态 index 不干净也视为失败
  │   ├─ 失败: git restore --source=HEAD 回滚所有 PATCHED_FILES
  │   └─ 成功后: _has_conflict_markers() 扫描 → 含标记则回滚
  │
  ├─ 8b. Patch invariant gates（structural sentinels + smoke checks）
  │   ├─ PATCH-SKILL-CREATE-ROOT: Python import + 调用 _resolve_skill_dir()，检查返回路径
  │   ├─ PATCH-DOCTOR-ENABLED-TOOLSETS: grep _get_platform_tools in doctor.py（✅ 已上游合并 v0.18.0）
  │   ├─ PATCH-ZSH-COMPLETION-SYNTAX: Step 7 中对 `){-h,--help}` / `){-V,--version}` / `){-p,--profile}` 做回归检测（✅ 已上游合并 v0.13.0）
  │   ├─ PATCH-DASHBOARD-BUILD-CACHE: grep _web_ui_build_needed in main.py（✅ 已上游合并，仅验证）
  │   ├─ PATCH-DELEGATE-ACP-ROUTING: grep override_acp_command + copilot-acp（✅ 已上游合并，仅验证）
  │   ├─ PATCH-GEMINI-THOUGHT-SIGNATURE: grep ToolCall.extra_content + 对应回归测试（✅ 已上游合并，仅验证）
  │   ├─ PATCH-FEISHU-SOCKS-DEPENDENCY: Feishu extra 与 lazy deps 均声明 python-socks
  │   ├─ PATCH-OPENCLAW-TOKEN-MIGRATION: 迁移器不再生成废弃 gateway token
  │   ├─ PATCH-FEISHU-GROUP-ADMISSION: 群触发/上下文/当前发言人/显式 wiki 路径
  │   ├─ PATCH-FEISHU-MISSED-EVENT-BACKFILL: 断线/重连漏消息补偿（群+主会话 DM）与 quote 覆盖去重
  │   ├─ PATCH-FEISHU-GROUP-SCOPE: feishu_group capability namespace 与 DM 隔离
  │   ├─ PATCH-PLATFORM-CAPABILITY-SCOPE: 平台 skill allowlist + 只读 skill/file toolset
  │   ├─ PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY: 冗余 tool_call 包装安全解一层
  │   ├─ PATCH-FEISHU-GROUP-APPROVAL: 群聊危险命令审批硬拦
  │   ├─ PATCH-FEISHU-NORMAL-REPLY: 普通引用回复，不进入 thread/topic lane
  │   ├─ PATCH-FEISHU-FINAL-ONLY: Feishu 最终内容优先，长任务通用心跳
  │   ├─ PATCH-GATEWAY-FAILOVER-STATUS-SILENCE: 主模型/fallback 路由状态只进日志
  │   ├─ PATCH-FEISHU-RESPONSE-BUDGET: 可配置聊天软字数预算 + 单条 post 硬兜底
  │   ├─ PATCH-LOCAL-PROFILES: 人物/群画像、来源保密与可见输出过滤
  │   ├─ PATCH-FEISHU-RESOURCE-ACCESS: 附件回看、合并转发完整引用、Drive/doc access
  │   ├─ PATCH-DOCUMENT-EXTRACTION: PDF/HTML/Office/OpenDocument 可信抽取（XLSX/DOCX/IPYNB 已上游）
  │   ├─ PATCH-FEISHU-MARKDOWN: 标题/引用提升与 strong flanking 归一化
  │   ├─ PATCH-FEISHU-SSRF-TEST-SYSPROXY: SSRF rebind 测试对宿主系统代理 hermetic
  │   ├─ PATCH-VERTEX-HIDDEN-THOUGHTS: Vertex thought 文本不进入可见内容
  │   ├─ PATCH-VERTEX-DOCTOR: doctor 识别官方 Vertex profile
  │   ├─ PATCH-DOCTOR-TEST-NETWORK-ISOLATION: doctor 单测不访问真实网络/宿主命令
  │   ├─ PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY: Gemini fallback 接受其他模型产生的无签名工具历史
  │   ├─ PATCH-LAUNCHD-WRAPPER-SUPERVISOR: launchd stderr wrapper 保留受监管身份（✅ 已上游合并 v0.20.4）
  │   ├─ PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION: 不继承 shell/~/.secrets 的 Hermes 凭据
  │   ├─ PATCH-MODEL-CONFIGURED-ONLY: /model 只访问主模型与 fallback 配置集合
  │   ├─ PATCH-TRUNCATED-TOOL-CALL-RECOVERY: 隐藏截断的工具参数提高预算后重试
  │   ├─ PATCH-IMAGE-NATIVE-ROUTING: 主力模型图片能力识别（Gemini 3.x + azure-foundry）
  │   ├─ PATCH-VERTEX-VIDEO-ROUTING: Gemini 视频 native routing
  │   ├─ PATCH-MULTIMODAL-SIDECAR: 主力读不了媒体时旁路到链上能读的档（全局，不切主 provider）
  │   ├─ PATCH-LAZY-ACTIVATION: 上游首项依赖身份锚点回归 sentinel（✅ 已归档）
  │   ├─ PATCH-HISTORY-RETENTION: 平台级回放时间窗/条数上界
  │   ├─ PATCH-APPROVAL-DARWIN-TMP: Darwin 临时路径别名归一化
  │   └─ PATCH-FTS5-CJK-DARWIN: Darwin CJK FTS 扩展构建/加载
  │
  └─ 8c. Refresh saved diff
      ├─ 前提: _PATCH_APPLY_OK && 全部 _*_PATCH_OK 为 true
      ├─ 再次 _has_conflict_markers() → 不干净则拒绝刷新
      ├─ 每个 PATCHED_FILES 都必须有 live diff；部分/全部为零均阻断并要求吸收归类
      ├─ 用 --full-index 生成临时 bundle，自动执行逐字节/cached 正向/worktree 反向/index-clean 闭环
      ├─ 全绿后才原子写 local-patches.diff + .local-patches.base
      ├─ 干净但无 diff: 提示 "patches may have been absorbed" 并返回非零
      └─ apply / sentinel / conflict 任一失败: FINAL_RC=1

Step 8d: Gateway restart（post-patch）
  └─ 前提: _PATCH_APPLY_OK == true && transaction runtime_dirty == 1 && gateway 正在运行
      └─ 记录 old PID → PATCH-GATEWAY-RESTART-CLEANUP dry-run/apply（script + ignored keep/remove/review 全分类）
          → drain-aware `hermes gateway restart`
          → 按 `gw_restart_wait_seconds()`（native exit-wait budget 优先、drain 回落，+30s）轮询 different new PID
          ├─ 成功后清 runtime_dirty；未替换或未恢复: FINAL_RC=1
          └─ HEAD/overlay 均未变化的 reconcile 明确跳过重启，不制造 PID
      （hermes update 在 step 3 重启 gateway 时补丁尚未 apply，
       Python 进程 sys.modules 缓存旧模块，需重启才能加载补丁代码；
       planned restart 给在途 agent run 完整排空预算；macOS stop 路径短宽限后
       会 SIGKILL，不能用来做常规重载，也不能把仍存活的 old PID 误认成加载成功）

Step 8e: User-plugin verification
  ├─ verifier 文件必须存在且可执行
  ├─ PATCH-FEISHU-GROUP-SANDBOX: YAML 契约 + owner/group 真实 toolset + 42 个行为测试 + launchd wrapper / 真实 Gateway 子进程双层 runtime trace
  └─ 任一 verifier 非零 → FINAL_RC=1，整次升级不得报告成功
```

### 安全机制（及设计原因）

#### 1. 冲突标记检测：`_has_conflict_markers()` 而非 `git diff --check`

`git diff --check` 同时报告冲突标记**和** trailing whitespace / indent 问题。上游代码风格变化（如多一个尾部空格）就会触发误报，导致功能完好的 patch 被回滚。

外层仓库用 `.gitattributes` 对 `patches/*.diff` 设置 `-whitespace`：unified diff 里的合法空白上下文行可能表现为 `+ ` / ` `，不应让 `git diff --check` 把 patch 文件自身误判为 trailing whitespace。patch 文件有效性仍以 `git apply --check`、冲突标记扫描和重新生成 diff 比较为准。

`_has_conflict_markers()` 只用 grep 精确匹配 `<<<<<<<`、`=======`、`>>>>>>>` 三种标记的标准格式，避免误判：

```bash
grep -qE '^(<<<<<<<($| )|=======$|>>>>>>>($| ))' "$_f"
```

> **历史教训**：v0.9.0 → v0.10.0 升级时，旧版脚本使用 `git diff --check` 导致 3-way merge 后因 whitespace 报错而回滚全部 patch，整个更新流程失败。

#### 2. 原子写入 patch 文件

所有写 `local-patches.diff` 的路径（Step 2 保存 + Step 8c 刷新）都先写 `file.tmp`；临时 bundle 通过 conflict-marker、cached 正向和 worktree 反向 replay check 后才 `mv -f` 替换 canonical 文件，Step 8c 还会复核 full-index live diff 逐字节一致与 index-clean。这样 `git diff` 中断、磁盘写失败或半套 overlay 都不会静默截断/降级已知完整的 replay bundle。

#### 3. Patch 文件毒化检测

Step 8a 开头先扫描 `local-patches.diff` 自身是否含 conflict marker（`^\+?(<<<<<<<|=======|>>>>>>>)`）。如果上一次脚本异常退出时 3-way merge 的冲突结果被误写入 diff 文件，这步会拦截，避免把冲突标记 apply 到源码里。

恢复方法：`cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff`

#### 4. EXIT trap 补丁恢复

Step 2 还原 patch 后设置 `_PATCHES_REVERTED=true`；接管“worktree 已经等于 HEAD、但完整 bundle 仍存在”的中断现场时也会重新武装该标志。恢复窗口覆盖 Step 2 之后直到 Step 8a 做出 apply 决策（成功重贴或有意回滚）为止：期间任何崩溃（含 Step 4–7 的裸树阶段）EXIT trap 都会自动尝试 clean/3-way replay；3-way 成功会清 staged index，失败或出现 conflict marker 会把所有受管路径恢复到确定的裸 upstream 状态，同时保留 canonical bundle 供下一轮 AI 重解，避免遗留半合并 index。Step 8a 决策后清除该标志，正常退出与失败回滚都不会重复 apply。

#### 5. 额外改动保护

Step 3 只负责 `PATCHED_FILES` 之外的临时改动。脚本会用 `git stash push -u` 保存这些额外改动（包含 untracked 文件），再运行 `hermes update`；如果 stash 失败，脚本直接停止且不执行清理，避免误删未跟踪文件。若 update 后 `stash pop` 与上游冲突，脚本保留 stash 并提示用 `git stash list` 手动恢复。

#### 6. 上游 base commit 追踪

每次 Step 8c 成功刷新 diff 后，将当前 `hermes-agent` 的 HEAD SHA + UTC 时间戳写入 `patches/.local-patches.base`。当下次 update 补丁 apply 失败时，可以对比这个 base 和新的 HEAD 来定位是哪些上游 commit 引入了冲突：

```bash
# 查看自上次 patch 刷新以来上游改了哪些相关文件
BASE=$(cut -d' ' -f1 ~/.hermes/patches/.local-patches.base)
cd ~/.hermes/hermes-agent && git log --oneline ${BASE}..HEAD -- tools/skill_manager_tool.py tests/tools/test_skill_manager_tool.py hermes_cli/doctor.py pyproject.toml tools/lazy_deps.py plugins/platforms/feishu/adapter.py gateway/run.py agent/skill_utils.py tools/skills_tool.py toolsets.py
```

#### 7. 上游吸收检测

Step 2 若发现 canonical bundle 已存在、但只有部分 `PATCHED_FILES` 相对 HEAD 有 diff，会在写 bundle 前 fail closed，防止中断现场把完整包降级为残缺快照。Step 8c 对逐文件覆盖再做一次硬门禁：全部无差异表示补丁可能整体被吸收；只有部分无差异则逐条报告 zero-diff path，要求按语义块判断“完全吸收 / 部分吸收 / 补丁丢失”并同步 `PATCHED_FILES`/注册表后再刷新，不能静默把该文件从物理包里漏掉。

#### 8. 单次 upstream 快照与事务恢复

官方仓库获取和本地 patch 收敛使用两个不同入口：只有显式 `--update` 可以在新事务中执行一次 scoped fetch；获得 commit 后立即写专用事务 ref 和状态文件，再让官方 updater 通过临时 Git 代理只消费固定 SHA（其强制 fetch 变成成功 no-op，`origin/main` 参数被替换为 `TARGET_SHA`）。默认无参数和 `--reconcile` 均不得执行网络探测、fetch 或 pull。脚本不调用带隐式 update-check 的 `hermes --version`，而直接从 checkout 读取版本元数据。

失败/中断时，`.hermes-update-transaction` 保存 `old_sha`、`origin_before`、固定 `target_sha`、阶段和 `runtime_dirty`。文件用 temp + rename 原子发布、权限 `0600`、内容逐字段验证且永不 source。若进程在 fetch 更新专用 ref 后、正常状态发布之前退出，下一次从该 ref 重建目标；已有目标时任何复跑（包括误传 `--update`）都走 no-network reconcile。只有完整 exit 0 才删除状态与专用 ref。这样一轮升级面对的是不可变输入，远端后续提交不会让回归审计无限续跑。

### 已知局限

| 局限                            | 说明                                                                                                                                                                                                                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **单体 diff，不支持逐文件降级** | 所有 patch 在一个 diff 中。如果 5 个文件中只有 1 个冲突，整体 apply 失败，其余 4 个也不会被应用。`git apply --3way` 覆盖了大部分上下文偏移的情况；真冲突时需要手动 `git apply --reject` 逐文件处理。未来如果冲突频繁，考虑拆成 per-file diff 或改用 Python 脚本做更细粒度的 apply。 |
| **行为化验证依赖特征字符串**    | PATCH-DELEGATE-ACP-ROUTING 与已归档 PATCH 的 sentinel 验证是 grep 固定字符串。如果上游重构了函数但保留了行为，grep 会误报 "inactive"。PATCH-SKILL-CREATE-ROOT 用了真实 Python import + 调用，是最稳的方式；其他 patch 条件允许时应向这个模式靠拢。                                  |
| **工程外补丁无版本对齐**        | PATCH-ZSH-COMPLETION-SYNTAX 的 inline Python 替换依赖 `hermes completion zsh` 输出的固定格式。如果上游改了补全生成逻辑但仍有 bug，替换可能失效。目前有 "skip if already correct" 逻辑兜底。                                                                                         |

### 受 `PATCHED_FILES` 管理的文件

```bash
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "pyproject.toml"
    "uv.lock"
    "tools/lazy_deps.py"
    "optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"
    "website/docs/guides/migrate-from-openclaw.md"
    "website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md"
    "gateway/authz_mixin.py"
    "gateway/config.py"
    "gateway/display_config.py"
    "plugins/platforms/feishu/adapter.py"
    "skills/research/llm-wiki/SKILL.md"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/slash_commands.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "gateway/stream_consumer.py"
    "hermes_cli/doctor.py"
    "hermes_cli/env_loader.py"
    "hermes_cli/model_switch.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/skill_utils.py"
    "tools/approval.py"
    "tests/tools/test_approval.py"
    "tools/skills_tool.py"
    "tests/tools/test_skills_tool.py"
    "toolsets.py"
    "tools/feishu_doc_tool.py"
    "tests/tools/test_feishu_tools.py"
    "tools/read_extract.py"
    "tests/tools/test_read_extract.py"
    "tests/gateway/feishu_helpers.py"
    "tests/gateway/test_config.py"
    "tests/gateway/test_display_config.py"
    "tests/gateway/test_feishu.py"
    "tests/gateway/test_document_context_note.py"
    "tests/gateway/test_feishu_bot_admission.py"
    "tests/gateway/test_feishu_bot_auth_bypass.py"
    "tests/gateway/test_session.py"
    "tests/gateway/test_session_env.py"
    "tests/gateway/test_run_progress_topics.py"
    "tests/gateway/test_background_command.py"
    "tests/gateway/test_verbose_command.py"
    "tests/gateway/test_stream_consumer_silence.py"
    "tests/gateway/test_telegram_audio_vs_voice.py"
    "tests/gateway/test_telegram_noise_filter.py"
    "tests/hermes_cli/test_doctor.py"
    "tests/hermes_cli/test_env_loader.py"
    "tests/hermes_cli/test_skills_config.py"
    "tests/hermes_cli/test_tools_config.py"
    "website/docs/reference/environment-variables.md"
    "website/docs/user-guide/configuration.md"
    "website/docs/user-guide/messaging/feishu.md"
    "plugins/model-providers/vertex/__init__.py"
    "tests/hermes_cli/test_vertex_provider.py"
    "agent/image_routing.py"
    "agent/models_dev.py"
    "agent/transports/chat_completions.py"
    "tests/agent/transports/test_chat_completions.py"
    "tests/agent/test_image_routing.py"
    "tests/gateway/test_image_input_routing_runtime.py"
    "tools/vision_tools.py"
    "tests/tools/test_video_analyze.py"
    "agent/replay_cleanup.py"
    "tests/agent/test_replay_cleanup.py"
    "tests/run_agent/test_provider_fallback.py"
    "tests/run_agent/test_compressor_fallback_update.py"
    "tests/gateway/test_stale_confirmation_expiry.py"
    "agent/conversation_loop.py"
    "agent/tool_executor.py"
    "agent/mcp_task_protocol.py"
    "tools/mcp_tool.py"
    "tools/mcp_tasks_extension.py"
    "tests/run_agent/test_tool_call_incremental_persistence.py"
    "tests/run_agent/test_run_agent.py"
    "tests/tools/test_mcp_tasks_extension.py"
    "tests/tools/test_mcp_utility_capability_gating.py"
    "tests/tools/test_mcp_tool.py"
    "tools/tool_search.py"
    "tests/tools/test_tool_search.py"
    "website/docs/user-guide/features/mcp.md"
    "native/fts5_cjk/build.sh"
)
```

> 以上为 `hermes-update.sh` 中数组的快照（85 文件，2026-08-20 与脚本核对一致）。**脚本数组是唯一权威来源**；增删补丁文件后请同步刷新本快照。机器读取请用 `bash ~/.hermes/hermes-update.sh --print-patched-files`，不要解析本快照。

### 手动恢复

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突（推荐）：git apply --3way 留下 <<<<<<< 标记逐处解决（多为"并存"型冲突），
#   然后 git add <冲突文件> && git restore --staged -- <冲突文件> 清索引，
#   再运行 bash ~/.hermes/hermes-update.sh --reconcile，固定 TARGET_SHA 走完整验证
#   （2026-07-13 轮实测流程；注意 git apply 输出别接 head 截断，SIGPIPE 会中断 apply）
# 或：git apply --reject && 手动解决 .rej，再运行 --reconcile

# 若 patch 文件自身已被 conflict marker 污染，可先恢复入库版本
cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff

# 查看 patch 基于的上游版本
cat ~/.hermes/patches/.local-patches.base
```

---

## 当前版本：v0.20.4 (upstream `main` `13ce0c5c675e843af70d19c9e5144249cd51c8d1`，2026-08-20)

**活跃补丁**：当前共 42 个语义补丁。34 个工程内补丁由 Step 8b/8c 管理；`PATCH-NPM-DEPENDENCY-HYGIENE`、`PATCH-REPLAY-BUNDLE-FULL-INDEX`、`PATCH-UPDATE-GATE-EXIT-STATUS`、`PATCH-UPDATE-GIT-FETCH-RETRY`、`PATCH-UPDATE-TRANSACTION-PIN`、`PATCH-SKILLS-MIRROR-METADATA`、`PATCH-GATEWAY-RESTART-CLEANUP` 是运行时补丁，由对应 update step 管理；`PATCH-FEISHU-GROUP-SANDBOX` 是配置仓库用户插件补丁、由 Step 8e 管理。完整活跃 ID 以上方执行链清单为准；Archive 中的定义只保留历史与重新启用条件，不计入活跃数。

**2026-08-20 运行态审计：SpaceSight 国内业务群创建需求文档失败**：请求已进入 Agent，但 Azure 主模型两次 90s stale kill 后切 Bedrock；模型随后生成大段文档工具参数时触及默认 4096-token 输出预算，且 provider 把未闭合 JSON 标为 `tool_calls`，旧路径不提高预算重试而直接回 `Response truncated due to output length limit`。终态失败 flush 又把 `Primary model failed — switching to fallback...` 内部状态发进群；正常的 8,397 / 8,703 / 11,351 字符回复也因 Feishu adapter 固定 8,000 字符预算被主动拆段。新增三个独立工程补丁：隐藏聊天面的模型路由状态、为隐藏截断的工具参数执行 8k→16k→32k 有界重试、提供 `display.platforms.<feishu|feishu_group>.response_char_limit`（本机 3000）生成侧软预算并把单条 post 硬兜底提高到 16,000 字符。

**2026-08-20 运行态审计：财务群引用 PDF 后长时间无响应**：飞书真实群历史证明 PDF 引用、附件回填和文本抽取均成功，12:19:49 也确实发送了 1,829 字最终回复并创建飞书文档 `QHCOdMaZNoVTU8xcCtlcAmxPnhg`；问题是整轮耗时 1,163.6 秒且群聊 long-running notification 被 final-only 策略完全关闭。模型在 12:03 已发现 HyperTeX create 工具，却生成 `tool_call({name:"tool_call", arguments:{name:"mcp__hypertex__hypertex_create_case",...}})` 双层 envelope，旧 bridge 在读内层 target 前按递归拒绝，导致异步 HyperTeX 未启动，Agent 跨 Azure→Bedrock→Vertex 手工生成本地 83KB HTML，最终只能发飞书大纲与不可直接访问的缓存文件说明。新增 `PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY` 安全剥离一层冗余 envelope；同时把 `feishu_group.long_running_notifications` 改为 `generic`、`gateway_notify_interval` 调为 180 秒，保留最终内容优先但不再让 19 分钟任务完全静默。`response_char_limit` 仅约束最终聊天气泡，明确不限制文档、HTML、附件、Markdown 源稿或工具 payload；12k 单条 post 回归同时证明标题、引用与 strong flanking 格式化仍生效。终态 **42 active / 34 engineering patches / 85 files / 39 tests**；受管测试 **1654 passed / 0 failed / 3 skipped**（另 8 subtests），sandbox **42 passed**，85-file bundle cached 正向 / worktree 反向 / conflict-marker / index-clean 全绿；Gateway planned restart 后运行于 PID 35792。

**2026-08-20 运行态审计：Data Pipeline Workshop 可信维护者删除文档被误拒**：真实入站与 state.db 均证明当前发言人的 tenant `user_id=5397e1a2` 已命中 delete 白名单；失败发生在 provenance 层。Feishu/Gateway 把引用回复中的文档链接规范化成 Markdown `[URL](URL)`，旧 `_FEISHU_URL_RE` 把两段 URL 连同中间 `](` 粘成一个畸形 `URL](URL`，导致 doc token 未进入 `_current_resource_refs`，而身份拒绝与目标未引用又共用同一错误文案，模型遂误报“当前身份不是维护者”。现正则在 Markdown `]` 前终止、两段 URL 分别规范化；trust 与 target-reference 使用独立错误消息和结构化 reason 日志。新增回归从真实 `[URL](URL)` reply 形状穿过 `pre_gateway_dispatch`、deferred `tool_call`、pre-tool hook 与 handler（trusted script 用 fake runner，零真实删除），sandbox 终态 **42 passed**。同轮仓库审计还发现 quote-chain 与 compaction 两个 Step 8b flag 虽设为 true 却未进入 8c 总条件；现已补接并新增 `--self-test-patch-gates`，每轮 preflight 自动证明 34 个活跃工程 gate 与 6 个归档 gate 均“声明、可成功、被总闸门消费”。终态按 Step 5b 排空重载，launchd wrapper PID 50624、真实 Gateway 子进程 PID 50625；新 PID 下 verifier 42 passed，cleanup review=0 / candidate=0。

**最近一次升级（v0.20.1 → v0.20.4，+836 commits，basis `8ad055414bcae75486952c5080d366679e074c1b` → `13ce0c5c675e843af70d19c9e5144249cd51c8d1`，2026-08-19）要点**：

- 上游主线：发布 **v0.20.2 → v0.20.3 → v0.20.4**（`df4b65147` / `7339f5f16` / `7e05e9080`），main 前进 836 commits。MCP 迁移到 2.x SDK 并接入 2026-07-28 stateless protocol、OAuth user-agent/CIMD（`11a9dcf56` / `382060f02` / `a6bada232` / `0b588cb3a`）；Skills 新增 project-local discovery、trust/quarantine、安装安全与文件 mode 保留（`f891d702d` / `6e22d2658` / `183f18d53` / `968853c5b`）；Gateway/session 加入 profile-aware key、恢复笔记、DB off-loop 与 launchd wrapper supervisor 正式修复（`21260c328` / `0cc26777b` / `8e81e2aaa` / `7008fb81b`）；模型/provider catalog、Desktop 多 source/Bot Mode/preview/browser/tour 与 Nix Home Manager 持续演进（`fa1bb88e3` / `d354af5e1` / `018176915` / `d5a9c2ba6`）。
- patch apply / registry：84-file bundle 在 `prompt_builder.py`、`skill_utils.py`、`hermes_cli/gateway.py`、`tools/approval.py`、`tools/mcp_tool.py` 发生真实 3-way 冲突；project skill 与平台 allowlist、single-query approval 与 Feishu group hard floor、MCP 2.x 字段/API 与 Tasks extension 均按“并存”重解。`PATCH-LAUNCHD-WRAPPER-SUPERVISOR` 经裸 upstream 实现 + 14 条官方回归证明完全吸收并移入 Archive，本地 hunk/旧测试退出 bundle；08-20 运行态与仓库审计后新增四个输出/工具稳健性补丁，修复群文档 Markdown provenance，并补齐 quote-chain/compaction 两个 8c gate 与机器自测。终态 **42 active / 34 engineering patches / 85 files / 39 tests**，受管 runner **1654 passed / 0 failed / 3 skipped**，sandbox **42 passed**，85-file replay 闭环全绿。
- 依赖：venv 原地升级，Python 3.12.13 / SQLite 3.53.1 保持；Hermes 0.20.1 → 0.20.4，MCP 1.28.1 → 2.0.0，idna 3.15 → 3.18，pip 26.2 → 26.2.1，并新增 `httpx2` / `mcp-types` / `truststore` 等上游 pin；20 个 active lazy backend 全部 current。官方 updater 更新 4 个 bundled skills，终态 mirror `+0/~1/-0` 且 runtime metadata 保留。root `npm audit` 仍为 **6 high**：Electron 40.10.2 / extract-zip 需越 stated range 到 40.10.6，postcss 8.5.23 → nanoid 3.3.17 被 override/lock 阻挡；均属 Desktop/Web build-chain P2，不影响飞书 gateway，未使用 `--force`。`package-lock.json` 仅 workspace hoist / peer 标记归一化，继续排除出 replay bundle。
- 已知摩擦：唯一 `--update` 固定 `TARGET_SHA=13ce0c5c675e` 后，所有复跑均为 no-network reconcile。cleanup 先暴露未完成事务文件未分类，后又在全量回归预编译后暴露新 `website/scripts/__pycache__`；现已把事务状态/锁成对列为 keep、website 文档脚本缓存精确列为 remove，并补 7 条清理器回归。MCP 2.0 将 `CallToolResult.isError` 属性改名为 `is_error`，Tasks extension 已改为 snake/camel 双读并新增 success/error validation 反例。可信删除误拒证明裸 URL fixture 不能替代 Gateway 规范化后的 Markdown reply；gate 漏接则证明“flag 存在”不能替代聚合条件集合相等。两类经验已分别落入 sandbox 真实边界回归与 `--self-test-patch-gates` preflight。一次 Doctor Bedrock TLS 证书错配在无配置变更的立即复跑中恢复，归类为瞬时网络/DNS 噪音；最终 Azure/Bedrock 均通过。reconcile exit 0、无 `✗`，事务清除，Gateway planned restart 与 sandbox 42 passed 绑定最终真实子进程。
- 配置漂移：主配置仍为 v37，无 migration 或 deprecated key；Azure → Bedrock → Vertex fallback、Vertex compression、统一 700k threshold、`browser.backend: 'off'` 与 Feishu owner/group sandbox 边界均保持。Doctor 仅保留上述 P2 npm build-chain 和未配置的可选 provider/toolset P3，不存在可修而未修的 P0/P1。

---

## 活跃 PATCH 定义（按类别）

**类别：MCP 协议与异步任务**

### [PATCH-MCP-TASKS-ASYNC-HANDOFF] 标准异步 task handle 即时回执

| 字段     | 内容                                                                                                                                                                                                                                                                                                                           |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `agent/{conversation_loop.py,tool_executor.py,mcp_task_protocol.py}`, `tools/{mcp_tool.py,mcp_tasks_extension.py}`, `tests/run_agent/test_tool_call_incremental_persistence.py`, `tests/tools/{test_mcp_tasks_extension.py,test_mcp_utility_capability_gating.py,test_mcp_tool.py}`, `website/docs/user-guide/features/mcp.md` |
| **状态** | 🟡 未上游合并：当前 upstream MCP client 只把 `tools/call` 解析成普通 `CallToolResult`，Agent 工具轮后仍无条件进入下一次模型调用；没有标准 Tasks extension capability negotiation、task lifecycle utilities 或确定性 receipt 终止路径。                                                                                         |

**问题**：MCP 长任务即使在 server 侧已异步入队并立即返回 durable handle，Hermes 仍把结果当普通工具文本追加到上下文，再发起一次 LLM 调用组织回复。真实飞书 turn 中 HyperTeX `tools/call` 仅 0.54s，第二次 Azure Responses 推理却 120s 无 SSE，导致用户 160.5s 后才收到 task ID；同类 provider 抖动会把“任务已受理”伪装成主会话卡死。依靠特定 server/tool 名称短路会把第三方产品耦合进 core，也无法覆盖其它符合 MCP Tasks 规范的 server。MCP SDK 2.x 另有一层更早的假阴性：握手时代协议把 `tools/call` 返回值预校验为普通 `CallToolResult`，该校验先于调用方传入的 raw result model；因此 server 已创建 task 并返回 `resultType="task"` 后，Hermes 仍会因缺少 `content` 抛 `ValidationError`，丢失 task handle 并让模型误以为创建失败。修复回执后又暴露 ID provenance 缺口：task/job/case 是三套独立 ID，财务群用户明确问 task `8` 时模型仍从历史 case 状态取 `job 99` 调 `tasks_get(99)`，把 caller error 报成“task not found”。

**修复**：新增窄协议模块 `tools/mcp_tasks_extension.py`，在 server 广告 `io.modelcontextprotocol/tasks` 时给 `tools/call` 注入 per-request client capability，并用 raw typed result 同时接受普通 result 与 `resultType="task"`。`tools/call` 请求必须使用 SDK 正式 `CallToolRequest` / `CallToolRequestParams`：MCP SDK 2.x 的 `send_request()` 会在序列化前读取请求类协议元数据，旧 generic `RootModel` 缺少 `name_param`，会在请求到达 server 前抛 `AttributeError`；只有自定义 `tasks/get|update|cancel` 继续使用 raw request，并显式声明 `name_param=None`。SDK 2.x 握手时代连接还会在 caller result model 前强制执行 core result surface 校验，因此仅在“server 已广告 Tasks + negotiated version 属于 handshake era + SDK 暴露 dispatcher/stamp seam”三条件同时成立时，Hermes 走一个窄 raw-dispatch bypass：逐项保留 SDK 的 protocol stamp、请求类 name metadata 处理、session timeout 与负 TTL floor，然后由本模块严格二选一校验普通 `CallToolResult` 或 `resultType="task"`；现代协议和 SDK 1.x 仍走公开 `send_request()`。Tasks utility schema 明确要求 exact taskId，用户点名时逐字复制，禁止以 case/job/run 等业务 ID 代替；当 server 对只读 `tasks/get` 明确返回唯一 `suggestedTaskId` 时只重试一次，`tasks_cancel` / `tasks_update` 绝不自动改 ID。普通 `CallToolResult` 的错误位兼容 MCP SDK 1.x `isError` 与 2.x `is_error`，成功结果优先走 SDK 2.x 公共 `validate_tool_result`、回落旧版 `_validate_tool_result`，错误结果不误触发验证。基于同一 capability 动态注册通用 `tasks_get` / `tasks_update` / `tasks_cancel` utilities。`agent/mcp_task_protocol.py` 只认 MCP 前缀工具的标准 task shape，不识别任何 server、tool 或业务字段：创建时只返回 task ID；查询时只以外层 `Task.status` 为权威，返回 task ID、最小生命周期句子和从任意 final result JSON/content 中递归提取并去重的 HTTP(S) 链接。业务 payload 内的 `status/error` 与 `CallToolResult.is_error/isError` 不得改写 Task 状态；`cancelled` 有独立回执；`input_required` 保留给正常 model/client 路径处理 `inputResponses → tasks/update`；同批混入普通工具结果时也不短路。Streamable HTTP 的 `tasks/get|update|cancel` 由 same-origin request hook 注入规范 `Mcp-Name=taskId` / `Mcp-Method=method` 路由头，跨源 redirect 同 authorization 一起剥离。server/tool 名称、poll interval、原始 status、`structuredContent`、内部 ID 与业务 payload 一律不进入普通前台回执。串行/并行 executor 都把 task metadata 绑定到已持久化 tool message，conversation loop 在 guardrail 与增量持久化成功后追加最终 assistant receipt 并退出本轮，保持角色配对与 prompt cache，不自动轮询、不再调用 LLM。普通 MCP 结果、未广告 extension 的 server 和非 MCP 工具行为不变。

**验证**：Step 8b 同时锚定 extension ID、task-aware dispatch、SDK 正式 `CallToolRequest`、custom request `name_param=None`、SDK 2.x legacy core-result bypass、exact taskId schema、只读 suggested-ID 单次重试与 mutation 不纠错反例、MCP 1.x/2.x 错误字段/结果校验兼容、动态 `tasks_get` schema、HTTP routing hook、conversation-loop `direct_task_response` 和行为测试。2026-08-19 财务群真实 create/list 在入队前均复现 `AttributeError: name_param`，HyperTeX `active-jobs=[]`，证明首层故障位于 Hermes request construction 而非 worker；修复后第二次真实 create 已在 HyperTeX 建立 case/job，但 Hermes 复现 `CallToolResult.content Field required`，证明 SDK core-result 预校验发生在 task-aware parser 之前。2026-08-20 财务群又实抓用户问 task `8`、模型误传 job `99`；Data Pipeline task `9` 首次超时但后续同 ID 成功，证明 ID 错误与 transport 卡顿是两类独立故障。`test_mcp_task_handle_ends_turn_without_second_model_call` 在最初修复前真实得到 4 次 API 调用（第二次断言失败后进入 3 次 retry），修复后严格为 1；`test_mcp_tasks_extension.py` 使用无产品语义的 `demo` server/payload，既在 fake session 中执行 SDK 2.x 同款 `type(request).name_param` 访问，也用真实 SDK 2.x `ClientSession` + fake dispatcher/adopted `2025-11-25` session 复现并锁死 legacy prevalidation：task handle 必须成功返回、wire 必须保留 protocol stamp 与 request body tool name，缺失 `content` 的伪普通结果仍必须被拒绝；同文件另断言 server 建议 `99 → 8` 时 `tasks/get` 只重试一次，而 cancel 不跟随建议。其余测试继续覆盖 custom task request 显式 opt-out、公共/旧版 validation 两代路径、错误字段双拼写、创建回执只含 task ID、完成回执只含 task ID + 去重链接、无链接时隐藏业务 payload、cancelled 独立表达、`input_required`/混合工具批次不短路，以及三种 lifecycle request 的标准 HTTP 路由头与非法 header 值反例；`test_mcp_tool.py` 另锁定跨源 redirect 剥离 task routing headers；`test_mcp_utility_capability_gating.py` 覆盖仅广告 Tasks 时三工具注册、exact-ID 文案及配置关闭。规范 runner、full-index bundle、cached 正向、worktree 反向、index-clean 与最终 Gateway PID 下的 MCP/sandbox verifier 共同构成终态门禁。

**上游吸收判断**：当 upstream Hermes MCP client 原生支持当前 `io.modelcontextprotocol/tasks` extension 的 capability negotiation、`CreateTaskResult`/`tasks/get|update|cancel` 生命周期和 capability-gated model tools，并且 Agent 在标准 task handle 已持久化后能用确定性回执结束交互 turn、无需第二次 LLM 调用，同时有等价的串行/并行与角色配对回归时，可删除本补丁。仅 SDK 出现 Task 类型、仅 server 返回自定义 `task_id`、或仅 UI 提前显示工具结果都不算吸收。

---

**类别：技能写入与治理**

### [PATCH-SKILL-CREATE-ROOT] 自定义 skill 创建到用户目录

| 字段     | 内容                                                                    |
| -------- | ----------------------------------------------------------------------- |
| **文件** | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 未上游合并（`_resolve_skill_dir()` 仍只用 `SKILLS_DIR / name`）      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：让 `_resolve_skill_dir()` 直接按配置顺序读取 `skills.external_dirs`，第一个非官方目录作为新 skill 的基准路径；即使目录尚不存在也由 create 建立，避免 discovery helper 只返回既存目录时错误回落官方 root。`_create_skill()` / `_delete_skill()` 同步适配，并加 `tests/tools/test_skill_manager_tool.py` 回归测试覆盖 external dir 路由、缺失目录创建与删除。

**验证**：Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("_patch_test")`，**严格断言**返回路径 startswith `~/.hermes/my-skills/`（2026-08-07 审计修复：旧断言含 `or "/skills/_patch_test" not in result` 的 fail-open 分支，官方 skills root 改名时会把回落误报为 active，已删除）。行为回归 `test_create_uses_first_external_dir` + `test_delete_skill_created_in_external_dir`（2026-08-07 补齐 delete 侧缺口）。

**上游吸收判断**：仅当上游 create 路径已支持把首个 external skill root 作为默认写入目录，且对应创建/删除测试覆盖不存在目录时，才可移除本补丁；当前上游仍固定写入 `SKILLS_DIR / name`。**语义张力提示**（2026-08-03 审计）：post-26e0b1c 上游新增 `_background_review_write_guard()`，经 `is_external_skill_path()` 将 external_dirs 视为"externally owned、对自主 curation 只读"。该 guard 目前只作用于 background review fork，与本补丁的前台 create 不互斥；但上游把 external 当只读、本补丁把它当默认写入目标，方向相反——每轮升级须复核该 guard 的作用范围未扩大到 create 路径，若扩大则需与上游治理策略重新对齐而不是静默让 create 失败。

---

**类别：升级事务、回放与依赖卫生**

### [PATCH-NPM-DEPENDENCY-HYGIENE] npm 漏洞修复与 install-script policy

| 字段     | 内容                                                                                 |
| -------- | ------------------------------------------------------------------------------------ |
| **文件** | `hermes-update.sh` + `node_modules/`（gitignored）                                   |
| **状态** | 🟢 自动化（Step 4 `npm audit fix`；install-script 策略已由上游 `allowScripts` 吸收） |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。Node 26 / npm 12 进一步默认阻止未经审核的 dependency lifecycle scripts；历史上本仓 update 的 root + ui-tui/web 安装会反复提示 `agent-browser` / `esbuild` / `fsevents` / `unicode-animations` 未被允许清单覆盖。

**修复**：保留 Step 4 的 `npm audit fix --quiet`。audit 非零时完整输出进入升级日志，action 改为 `npm audit --json` 定性且明确禁止 `--force`；不再建议机械重跑刚刚失败的同一 fix 命令。上游 lock/range 暂无非破坏解且不影响飞书主链路时归为 P2，允许 warning + 落盘摘要收敛；命令未执行、产物缺失、影响飞书主链路或出现不可解释 drift 才是事务失败。**install-script 策略片段已退役（2026-08-08）**：上游 `package.json` 自带钉版 `allowScripts` 允许清单（agent-browser/esbuild/fsevents 双版/node-pty/electron\*，`unicode-animations` 显式 false），npm ≥12 将其视为权威并以 "being ignored" 警告忽略任何 .npmrc/global `allow-scripts`；本地临时 global-config 分支因此从 Step 3 删除（退役实现见外层 Git pre-2026-08-08 历史），仅保留空 `_NPM_POLICY_ENV` 声明与惰性清理守卫。

**验证**：`hermes update` 的 root + workspace 安装在上游 `allowScripts` 下无 `install scripts blocked` / `not covered by allowScripts`，且日志不再出现本地 policy 的 "being ignored" 警告；audit 恢复完整 workspace 产物，`agent-browser`、`esbuild`、`require("fsevents")` 可用，package.json / lockfile 无 tracked drift。隔离 fake 令 audit 非零时，日志必须保留原始诊断、action 只建议 `npm audit --json` 且包含 `do not use --force`，不得再次建议无条件 `npm audit fix`。

**上游吸收判断**：install-script allowlist 片段已由上游 `package.json.allowScripts` 吸收（≤`863e31318` 引入，本机 npm 升至 12 后生效确认）。剩余本地不变量只有"升级后自动 `npm audit fix` + 失败分级定性"；上游升级器原生提供等价的 audit/修复流程后可整体归档本补丁。若上游未来移除 `allowScripts`，从外层 Git 历史恢复临时 policy 分支。

---

### [PATCH-REPLAY-BUNDLE-FULL-INDEX] replay bundle 使用稳定对象 ID

| 字段     | 内容                                         |
| -------- | -------------------------------------------- |
| **文件** | `hermes-update.sh`, `local-patches.diff`     |
| **状态** | 🟢 自动化（Step 2 / Step 8c `--full-index`） |

**问题**：`git diff` 默认按对象库规模自动决定 `index` 行的 SHA 缩写长度。bundle 生成后即使源码 hunk 完全不变，后续 fetch/apply 增加对象也可能让 live diff 从 9 位变成 10 位，导致 playbook 要求的逐字节 `cmp` 失败；只刷新一次默认缩写 bundle 仍会复发。2026-08-18 新增文件又暴露另一个物理缺口：`git diff HEAD -- <untracked>` 为空，因此合法的 new-file hunk 虽已进入 canonical bundle，回贴后 Step 8c 仍把三个新文件误报为 zero-diff，得到 81/84 partial coverage。

**修复**：Step 2 保存与 Step 8c 刷新统一使用 `git diff --full-index`，playbook 的 live-diff 核验也固定同一参数。bundle 的对象 ID 始终写完整 SHA，不再依赖仓库当前的自动缩写宽度。2026-08-06 收尾审计把原先仅由 playbook 人工执行的物理闭环下沉进两个 bundle 发布点：临时包必须通过 conflict-marker、index-clean（2026-08-07 起 Step 2 链内显式 `git diff --cached --quiet`，不再只依赖 preflight 继承）、cached 正向、worktree 反向检查，Step 8c 再与现场 full-index diff 逐字节比较；只有全绿才替换 canonical bundle/base。2026-08-18 起 Step 2/8c 不再依赖真实 index 的 ITA 可见性：`_managed_path_differs_from_head` 显式把「HEAD 不存在 + 工作树存在」判为 new-file diff，`_write_managed_bundle` 则从 HEAD 在临时 index 中精确 add/rm 本轮路径后生成 cached full-index diff，同时覆盖 tracked 修改、删除、untracked 新文件和 upstream-ignored 但已登记的 skill；真实 index 始终不变。裸窗口的逐路径 restore 只接受 `PATCHED_FILES`，因此可安全删除上游不存在的精确 replay-created 文件，不会扫描其它 untracked 路径。注意 8c 的 cmp 是"刷新输出 vs canonical 写入"的一致性闸，当 `_REFRESHED` 与 `PATCHED_FILES` 全等时两侧同源，不能替代 playbook Step 3 的独立现场复核。Step 2 另要求已有 bundle 时全部受管路径都有 live diff，禁止用中断产生的部分 overlay 覆盖完整旧包。

**验证**：`bash hermes-update.sh --print-patched-files` 输出必须与 bundle path 集合、live modified 集合一一相等；脚本 Step 2/8c 日志必须明确报告完整文件数，Step 8c 报 `refreshed and replay-verified`。独立复核时用与脚本相同的临时-index full-index 生成器与 `patches/local-patches.diff` 比较，正向 cached、反向 worktree 与两次真实 index-clean check 必须同时通过。隔离构造 61/62 的部分 overlay 时 Step 2 必须在写 canonical bundle 前非零退出；Step 8c 的单个 zero-diff path 也必须阻断刷新并点名该路径。对上游不存在的受管新文件，修复前必须稳定复现 81/84 partial coverage，修复后 Step 2/8c 都必须报 84/84，bundle 包含每个 `new file mode`，并且真实 index 在 capture/apply/refresh 前后均保持 clean。

**上游吸收判断**：这是外层 replay bundle 的本地持久化格式；只有未来迁移到不含动态缩写元数据的等价稳定格式，或不再维护本地 replay bundle 时，才可归档。

---

### [PATCH-UPDATE-GATE-EXIT-STATUS] 升级 gate 失败必须非零退出

| 字段     | 内容                                 |
| -------- | ------------------------------------ |
| **文件** | `hermes-update.sh`                   |
| **状态** | 🟢 自动化（Step 8 transaction gate） |

**问题**：旧脚本在 patch apply、Step 8b sentinel、冲突标记或意外空 diff 失败时只追加 warning/action 并跳过 Step 8c，没有设置 `FINAL_RC=1`。Step 8d 也只检查“存在任意 Gateway PID”：若 stop/start 没有真正替换旧进程，仍会把磁盘上已更新、运行时未加载的补丁误报为 active。即使后来补了 PID 替换门禁，macOS 的 `gateway stop` 仍会在短固定宽限后 SIGKILL，绕过 `agent.restart_drain_timeout`，本轮真实飞书任务因此被中断并进入恢复路径。结果既可能运行旧代码，也可能为了加载新代码破坏在途 turn，而脚本仍有机会把表面新 PID 当成功。可重入审计又发现四个同类缺口：把可执行脚本 `source` 后调用预算函数会直接启动整轮升级；3-way apply 失败后的单次批量 restore 会因任一上游已删除 path 令整个 pathspec 失败；3-way 成功隐式留下 staged index；以及接管“bundle 存在、worktree 已裸”的中断现场时没有重新武装 EXIT trap。更严重的是，Step 2 会把仅部分受管文件存在的 diff 当成新 canonical bundle，可能把完整本地不变量集合永久降级为残缺快照。2026-08-15 又实抓一处同类运行态假阳性：Step 5 只因 Gateway 进程正在运行就跳过 plist freshness 检查，最终 status 已明确显示 service definition stale；首次修复又只等待 plist 文件变 current，未等 launchd 重新加载并产生新 PID，导致 verifier 在 reload 窗口拿不到当前进程。**2026-08-20 AI 自演进审计再抓一处聚合假阳性**：`_FEISHU_QUOTE_CHAIN_SESSION_PATCH_OK` 与 `_COMPACTION_LIFECYCLE_SILENCE_PATCH_OK` 均有声明、真实 sentinel 和 `=true` 路径，却漏出 Step 8c 的长条件；两者即使失败，bundle/base 仍可刷新。现有 PATCH 数量/SHA/路径 hygiene 全部通过也没有发现它，证明“定义存在”与“总闸门实际消费”必须机器比较。

**修复**：Step 8c 总条件失败直接设置非零；条件通过后发现 conflict marker、部分或全部受管 diff 意外为空、byte/cached/reverse replay 任一失败也设置非零。Step 8d 仅在事务 `runtime_dirty=1` 时捕获旧 PID、走排空感知的 `hermes gateway restart`，等待预算优先取更新后运行时的 `_get_restart_exit_wait_budget()`（上游 `db3f7e4eb` 起原生覆盖 drain + after-turn 两段），旧运行时回落 `restart_drain_timeout`，再统一加 30 秒 supervisor 余量；只有命令成功且轮询到不同的新 PID 才确认 patched modules 已加载并清脏标记。旧 PID 未替换、Gateway 未恢复或 restart 非零都会设置 `FINAL_RC=1`，且不再建议 stop/start 强杀；`runtime_dirty=1` 但当前无 Gateway PID 时同样 `FINAL_RC=1` 并保留脏标记（2026-08-07 审计补：此前静默跳过整个 8d 块）；等待预算的解释器不可用 fallback 为 930s（本机 drain 900+30，2026-08-07 起替换与任何公式都不符的旧值 210）；HEAD/overlay 未变化的 reconcile 明确跳过重启。Step 5 在 patch 还原窗口只做 plist 快照、不得改写最终定义；Step 8 回贴全部源码后再走官方 `gateway start` 自愈，并按同一动态预算等待“definition current + launchd wrapper supervised PID + real Gateway child PID”同时成立，任何超时或 verifier 抢跑都使整轮失败。Step 7 补全脚本生成失败（sentinel 无法运行）同样设置非零。playbook Step 5b 再把同一规则设为所有后续代码/配置修复后的终态写屏障。脚本新增 side-effect-free `--print-restart-wait-seconds` / `--print-patched-files` / `--print-patched-tests` / `--transaction-status` 与隔离事务 self-test，并在任何状态变更前拒绝 bash/zsh source 及 dirty index；patch rollback 改为逐路径恢复，HEAD 已删除的受管文件只在 apply 确实把它放入 index 时才清除，遇到同名 untracked 文件 fail closed。自动 3-way 成功后立即清 staged index；EXIT trap 在裸树接管时保持武装，恢复失败会清理半合并态并保留 bundle。Step 2 对部分 overlay fail closed，只有完整且可正反向 replay 的临时包才允许替换 canonical bundle。2026-08-20 起 Step 8c 补接 quote-chain/compaction 两个遗漏变量，并新增 side-effect-free `--self-test-patch-gates`：从脚本现场解析 Step 8b 的全部 `*_PATCH_OK` 与 `_ARCHIVED_*_OK` 声明，证明每个变量均存在 `=true` 路径、且集合与 Step 8c 聚合条件逐项相等；preflight 在任何 patch/事务变更前强制执行，漏接或幽灵变量均非零退出。具体 PATCH warning 继续保留用于定位，退出码成为可供自动化和下一轮 agent 信任的总闸门。

**验证**：静态检查 Step 8c 的总条件 `else`、conflict-marker、partial/empty `_REFRESHED` 和 replay-integrity 分支都包含 `FINAL_RC=1`；`bash hermes-update.sh --self-test-patch-gates` 必须报告当前 **34 active engineering gates / 6 archived regression gates**，且从条件中移除任意一个声明变量或加入未声明变量都必须失败。Step 8d 在 `runtime_dirty=1` 时必须调用 `hermes gateway restart`、不得调用 `gateway stop`，等待预算来自 `gw_restart_wait_seconds()`（native exit-wait budget 优先、drain 回落，+30s），并同时比较 `_GW_OLD_PID` / `_GW_NEW_PID`；`runtime_dirty=0` 必须跳过 PID churn。stale-plist 真机验证必须证明：裸 upstream 窗口只快照，补丁回贴后才生成最终 plist；只有 status 报 current definition + supervised wrapper PID，且 `gateway.status.get_running_pid()` 返回真实子进程，才允许进入 verifier。任一 gate 为 false、restart/refresh 非零、超时或返回相同/空 PID 都必须得到非零终态；全部 gate 为 true 且 PID 替换后才允许报告 patched modules active。所有只读入口只输出现场状态且不改变仓库/Gateway；bash/zsh source 和 dirty index 在任何 update mutation 前返回非零；逐路径 restore 的 present/deleted/untracked 三种路径分别恢复、删除 apply 产物、保护用户文件。另以临时 Git repo 覆盖完整 overlay、61/62 部分 overlay、裸树 + bundle、3-way staged/冲突清理及 bundle byte/cached/reverse gate。终态若发生 Step 8d 后的运行时修改，还必须按 playbook Step 5b 重启并让 verifier 绑定最终 runtime PID。

**上游吸收判断**：这是外层升级 wrapper 的事务语义；只有 wrapper 被替换，且新入口能对 replay apply、全部 sentinel、冲突和空 bundle 提供等价非零总闸门时，才可归档。**排空子项已被上游替代并完成对接**（2026-08-03，本轮升级已跨过 `db3f7e4eb`）：`hermes gateway restart` 原生排空——SIGUSR1 先拒新 turn、按 `agent.restart_after_turn_timeout` 等 in-flight 归零才 stop，`restart_drain_timeout` 收窄为 stop 内强杀预算。上游 `0c6761c51` 已把 after-turn 默认值从 6h 收窄到 30min；本地 `gw_restart_wait_seconds()` 经 `_get_restart_exit_wait_budget()` 读取原生合并预算，本轮新运行时实测 **2745s = 900 + 1800 + 15 + 30**。等待预算必须始终以只读入口当前输出为准，不在 wrapper 内复制默认值；本补丁剩余职责为退出码总闸门与 PID 替换硬校验。

---

### [PATCH-GATEWAY-RESTART-CLEANUP] Gateway 重启前脚本与 ignored 文件审计清理

| 字段     | 内容                                                                                                                                                                  |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `scripts/{cleanup_transient_artifacts.py,cleanup_policy.json,test_cleanup_transient_artifacts.py}`, `hermes-update.sh`, `hermes-update.md`, `.gitignore`, `README.md` |
| **状态** | 🟢 自动化（每轮 preflight dry-run 审计；Step 8d restart 前 apply）                                                                                                    |

**问题**：AI/浏览器/测试会话会在共享 `~/.hermes` 工作区留下 pager/slide 验证脚本、pytest/ruff 缓存、`__pycache__` 与 `.DS_Store`。只按文件名临时删除既可能漏掉被 `.gitignore` 隐藏的新产物，也可能误删并发 session 或正式运维脚本；仅依赖会话记忆判断“哪个脚本有用”又无法跨 AI 重建。Gateway restart 是运行态写屏障，如果重启前不先清理和审计，旧临时文件会跨 PID 延续并污染后续 diff、工具发现或下一轮自动化判断。

**修复**：新增 policy 驱动的清理器。`cleanup_policy.json` 对 outer 运维脚本和 `plugins/*/verify.sh` 做显式白名单（keep）/临时脚本黑名单（remove），所有未分类 script-like 文件进入 review；同时读取 outer 与 inner Git 的 `status --ignored`，把每个 ignored 路径按运行态/密钥/依赖白名单、缓存黑名单或 review 三态分类。持久化恢复状态 `.hermes-update-transaction`、原子锁目录 `.hermes-update-transaction.lock/` 与 0600 `.skills_prompt_snapshot.json` 都必须显式 keep：事务文件保存固定 `TARGET_SHA`，skills snapshot 保存经 manifest 校验的冷启动 prompt 元数据，不能因只在特定运行阶段出现就落入 review 或被清理。规范 runner 预编译产生的 apps/evals/optional-skills/scripts/skills/tests/website 文档脚本 `__pycache__` 属确定可再生的 remove 类，运行时 agent/gateway/hermes_cli/tools/plugin 字节码则保持 keep。默认 dry-run，`--json` 输出完整 script/ignored audit、候选大小、跳过原因与 policy error；`--apply` 只把 remove 项移动到带时间戳的 macOS Trash 并保留相对路径，永不自动删除 review。近期临时脚本受 age gate 保护，Git-tracked 文件永不清理，pytest/CDP 等活跃进程会阻断 apply。`hermes-update.sh` preflight 每轮运行清理器自测与 `--dry-run --fail-on-review`；Step 8d 的唯一 restart 调用统一经过 `gateway_restart_with_cleanup()`，先 apply 再排空重启，清理失败、policy 漂移或未知 ignored/script 均使整轮非零。

**验证**：`scripts/test_cleanup_transient_artifacts.py` 覆盖 keep/remove/review 脚本分类、仅黑名单移动、review 阻断 apply、required 脚本缺失/未跟踪、ignored keep/remove/review 分类、事务状态/锁与 skill prompt snapshot 均显式 keep、runtime cache keep 与 tests/website build cache remove，以及 Trash 相对路径保留。现场存在未完成事务或 skills snapshot 时，`--dry-run --json --fail-on-review` 仍必须得到 `script_review=0`、`ignored_review=0`、`policy_errors=[]` 并列出全部被审计脚本/ignored 路径；`--apply --fail-on-review` 后重复 dry-run 的 remove 候选为 0。Step 8d 静态检查不得再直接调用 `hermes gateway restart`，只能调用 cleanup wrapper；真机 restart 必须先输出 cleanup audit/apply，再证明 old PID → different new PID 和最终 verifier 通过。

**上游吸收判断**：这是外层工作区治理策略。只有未来 Gateway/update wrapper 原生提供可配置的脚本/ignored 三态清单、并发安全的可恢复清理、每次 restart 前强制执行和可供无状态 AI 消费的审计输出时，才可归档；单纯增加一个 `rm -rf cache` 命令不构成吸收。

---

### [PATCH-UPDATE-GIT-FETCH-RETRY] 升级 fetch 瞬时网络故障有界重试

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `hermes-update.sh`                                     |
| **状态** | 🟢 自动化（Step 3 早期 GitHub fetch 网络错误有界重试） |

**问题**：`hermes update` 在任何 checkout 或依赖变更前先 fetch `origin/main`，但本机到 GitHub 的直连与 LLM 专用代理都可能瞬时超时、TLS EOF 或 `SSL_ERROR_SYSCALL`。单次失败会让完整升级非零，即使下一次同一路径立即恢复；反过来无条件重跑整个 updater 又可能把认证、分叉、安装或迁移这类确定性错误重复三次，扩大副作用并掩盖根因。

**修复**：重试单元是首次 acquisition 的**裸 scoped fetch**（`git fetch --force origin main:refs/hermes-update/target`，`_acquire_upstream_target_with_retry`），不是整条 `hermes update`——官方 updater 在 PATCH-UPDATE-TRANSACTION-PIN 的固定 SHA 代理下运行、自身不做网络获取，因此无需也不得重试。仅当 fetch 日志命中 GitHub transport 特征（`Failed to connect to github.com`、`Could not resolve host: github.com`、同一行含 github.com 的 SSL/TLS EOF、Connection timed out/reset 等）且**不含**认证/权限特征（`Authentication failed`、`could not read Username`、`Permission denied (publickey)`、HTTP 401/403/407）时最多重试 3 次（2026-08-07 审计：删除只可能来自 Python CLI 的死分支 `Network error — cannot reach the remote repository`，并把裸 `Connection timed out|reset by peer` 收窄为须与 github.com 同行、新增认证负向前置过滤）。该失败点位于任何 checkout/venv/config 变更之前，动作可安全重入；一旦有效 SHA 写入专用 ref 即立刻固定、不再重试，后续错误只能进入 no-network reconcile。中间失败只显示简短 attempt 提示，远端 URL、Git config 和代理设置不在重试中持久修改。

**验证**：静态检查重试循环体只包含 `git fetch` + `rev-parse`、无 URL/config/代理写入；正则须含认证负向过滤（`! grep`）且不含上游 CLI 错误串。隔离验证可用 fake `git` 序列化：transport-fail → success 调用 2 次且 exit 0；连续 3 次 transport-fail 调用 3 次并保留非零；日志含 `Authentication failed` 时必须只调用 1 次。取得目标后再次执行必须走固定 SHA reconcile，fetch 计数不变（该场景已由 `--self-test-transaction` 的本地裸 remote 用例覆盖）。

**上游吸收判断**：当上游 `hermes update` 自身对 scoped Git fetch 提供等价的瞬时 transport 有界重试，且不会重试认证/安装/迁移错误时，可删除外层 Step 3 重试并归档。

---

### [PATCH-UPDATE-TRANSACTION-PIN] 单次升级固定 upstream 快照

| 字段     | 内容                                                                              |
| -------- | --------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `.gitignore`, `hermes-update.md`, `README.md`, macOS 运维文档 |
| **状态** | 🟢 自动化（显式 `--update` 获取一次；默认/`--reconcile` 固定 SHA、no-network）    |

**问题**：旧 playbook 同时要求 Step 1 先 `git fetch origin main`、Step 2 再执行自带 fetch 的 `hermes update`，又规定任何 patch/gate/脚本修复后必须重跑完整 updater。上游 main 持续前进时，同一次审计会依次纳入新的 commit，既不断改变 patch 基线，也触发重复依赖安装和 Gateway 重启；所谓“幂等复跑”实际变成一串新升级，无法定义本轮完成。`hermes --version` 还会隐式执行 update-check/fetch，使只读预检也可能越过获取边界。

**修复**：把官方获取和本地收敛拆为两个脚本模式。只有显式 `--update` 能在没有未完成事务时执行一次 `git fetch --force origin main:refs/hermes-update/target`，立即把专用 ref 固定为 `TARGET_SHA`；随后官方 updater 仍负责 merge、依赖、迁移、skills 和原生 restart，但通过临时 Git 代理执行——其内置 `fetch origin main` 成功 no-op，命令参数中的 `origin/main` 被替换为固定 SHA，因此不会发生第二次网络获取或目标竞态。默认无参数和 `--reconcile` 只校验/本地 fast-forward 到固定 `TARGET_SHA`，绝不做网络探测、fetch 或 pull。`.hermes-update-transaction` 以原子写 + `0600` 保存阶段、`old_sha`、`origin_before`、`target_sha` 和 `runtime_dirty`，逐字段验证且永不 source；失败/中断保留，完整 exit 0 才删除状态与专用 ref。若进程在 fetch 更新 ref 后、状态发布前退出，下一轮从专用 ref 重建目标；已有未完成事务时，即使误传 `--update` 也只能接管已有 SHA。无变化 reconcile 跳过 Gateway restart；HEAD/overlay 改变或失败事务留下运行态脏证据时才执行排空重载。版本摘要直接读取 checkout 的 `hermes_cli/__init__.py`，消除 `hermes --version` 的隐藏 fetch。

**验证**：`bash -n hermes-update.sh` 与 `bash hermes-update.sh --self-test-transaction` 必须通过；self-test 在临时文件 round-trip **全部 7 个字段**（phase/old_sha/origin_before/target_sha/started_at/runtime_dirty + version 经 `_load_transaction` 校验）并断言权限 `0600`，另含两个 fail-closed 负例——symlink 状态文件与追加多余行的篡改文件都必须被 `_load_transaction` 拒绝（2026-08-07 补齐，此前仅断言 3 字段）；还用 fake real-git 证明 wrapper 的 fetch 不下传、`HEAD..origin/main` 被改写为固定 SHA。补充边界：pinned wrapper 只对精确的 `fetch origin main` no-op，带 `--depth` 的 fetch 或 fork 同步的 `fetch upstream main` 会命中 exit 97 阻断分支（fail-closed 而非静默放网络），本机 origin 为官方仓库、fork 路径不可达。`--transaction-status` 无状态输出 `none`，有状态只打印经校验字段。静态检查默认/`--reconcile` 分支不调用 acquisition fetch、curl 或 `hermes --version`；只有 `_ACQUIRE_UPSTREAM=true` 能写专用 ref。隔离 fake 覆盖：首次 `--update` 固定目标、失败保留状态、相同事务再次 `--update` 不增加 fetch 计数、`--reconcile` 在 remote-tracking ref 前进后仍保持原目标、exit 0 删除状态/ref、非法/符号链接状态 fail closed。现场 no-change reconcile 必须明确输出 `no fetch/pull` 与 restart skipped，且 HEAD/PID 不变。

**上游吸收判断**：这是外层升级事务边界。只有未来官方 updater/wrapper 原生支持“单次获取后返回不可变 target token、失败跨进程恢复、后续 no-network reconcile、成功清理事务、无变化不重启”，并且 playbook 不再需要本地状态层时，才可归档。

---

### [PATCH-SKILLS-MIRROR-METADATA] Skills 镜像保留本地 runtime 状态

| 字段     | 内容                                    |
| -------- | --------------------------------------- |
| **文件** | `hermes-update.sh`, `~/.hermes/skills/` |
| **状态** | 🟢 自动化（Step 4b rsync gate）         |

**问题**：Step 4b 原先用裸 `rsync -a --delete` 把上游 skills 镜像到运行目录，会删除源树中不存在的 `.bundled_manifest`、`.curator_state`、`.usage.json` / `.usage.json.lock`、`.hub` 和 `.archive` 等本地运行态。前者被迫反复重建，`.curator_state` 会丢失 curator 的 pause/run count/last-run 状态，`.usage.json` 会丢失每个 skill 的 usage、pin、sync 和 curator 生命周期记录；同时 `|| true` 吞掉 rsync 非零，复制失败也可能被显示成“已同步”。测试或运行时在 `hermes-agent/skills` 下生成的 `__pycache__/` / `*.pyc` 也会被误当作上游内容镜像到 runtime skills，导致同一 SHA 因执行顺序不同出现 `+70` 这类假漂移。

**修复**：从 delete 集合排除根级 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.curator_backups` / `.curator_suppressed` / `.hub` / `.archive`，并排除 `__pycache__/` / `*.pyc`，只镜像上游拥有的 skill 内容；显式捕获 rsync 退出码，失败时记录输出、设置 `FINAL_RC=1`，成功时继续报告 `+/~/-` 并确认 runtime state 与可再生 bytecode cache 保留/排除策略生效；bundled skills 源目录整体缺失同样 `FINAL_RC=1`（2026-08-07 审计补：属"命令未执行/产物缺失"级事务失败，此前仅 warn 且会连带静默跳过 Step 8c 的 llm-wiki 再播种）。（2026-08-06 并入）成功路径把 `--itemize-changes` 中每条新文件 `>f+++` 与删除 `*deleting` 分别以 `+ added:` / `- deleted:` 留存到升级日志：此前同日两轮各出现 `-94`、终态同 SHA 复跑又出现 `+70` 而无路径记录，事后无法判定具体变更集合；双向清单让下一位无状态 AI 能把批量消失/恢复与同期进程日志关联。

**验证**：在隔离临时目录预置完整 runtime state、一个待新增文件、一个上游孤儿和 `__pycache__` / `.pyc` 缓存，执行脚本同款 rsync 后必须保留 runtime state、复制新增项、删除孤儿、不复制 bytecode cache 并保持内容不变；把源目录改为不可读或传入无效 rsync 参数时必须走非零 gate。现场 dry-run 不得再出现删除 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.hub` / `.archive` 等本地状态，也不得把 `__pycache__` / `.pyc` 计入 `+/~/-`。清单分支以模拟 `>f+++` / `*deleting` 混合输出隔离验证：`_ADDED` / `_DELETED` 计数与逐行 `+ added:` / `- deleted:` 输出一致，updated/目录行不误报。

**上游吸收判断**：当上游同步器原生提供“官方 skill 内容镜像 + 本地 manifest/curator/usage/hub state 保留 + bytecode cache 排除 + 失败非零”的等价行为，外层不再需要 Step 4b wrapper 时可归档。

---

**类别：运行依赖与迁移兼容**

### [PATCH-FEISHU-SOCKS-DEPENDENCY] Feishu 代理依赖声明

| 字段     | 内容                                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock`（feishu extra 的 requires-dist 行，与 PATCH-DOCUMENT-EXTRACTION 共享同一批 hunk） |
| **状态** | 🟡 未上游合并                                                                                                                       |

**问题**：`feishu` optional extra 和 `tools/lazy_deps.py` 的 `platform.feishu` 上游当前都只声明 `lark-oapi==1.6.8` + `qrcode==7.4.2`。代理网络下 `lark-oapi` 的 WebSocket 连接需要 SOCKS 支持，缺 `python-socks` 时 gateway 起来后报 `connecting through a SOCKS proxy requires python-socks` 并反复重连失败。

**修复**：在 `pyproject.toml` 的 `feishu` extra 和 `tools/lazy_deps.py` 的 `LAZY_DEPS["platform.feishu"]` 都加 `"python-socks==2.8.1"`。手动 `.[feishu]`、`.[all,feishu]`、和上游 lazy install 三条路径都能拿到 SOCKS。版本钉死风格与上游 2026-05-14 起 messaging extras `==X.Y.Z` 约定一致（避免 `>=2.0,<3` 被 `uv lock --check` 报漂移）。

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在。

**上游吸收判断**：当上游 `feishu` extra 与 `LAZY_DEPS["platform.feishu"]` 都显式声明兼容的 SOCKS 依赖，并通过代理连接回归后，才可移除本补丁；任一路径缺失都必须保留。

---

### [PATCH-OPENCLAW-TOKEN-MIGRATION] OpenClaw 迁移不写废弃 gateway token

| 字段     | 内容                                                                                                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md`, `website/i18n/zh-Hans/.../guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                                                                                         |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；英文迁移文档与 zh-Hans 翻译（2026-08-07 审计补齐——此前中文文档仍保留该映射行、且全树仅剩这一处引用）同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本、英文文档与 zh-Hans 文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token` / `Gateway 认证 token`。

**上游吸收判断**：当上游迁移脚本不再写入废弃的 `HERMES_GATEWAY_TOKEN`，且迁移文档同步移除该映射后，才可移除本补丁；当前上游两处仍未吸收。

---

### [PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION] Hermes 不继承用户 shell 凭据

| 字段     | 内容                                                                                  |
| -------- | ------------------------------------------------------------------------------------- |
| **文件** | `hermes_cli/env_loader.py`, `tests/hermes_cli/test_env_loader.py`, 外层 `config.yaml` |
| **状态** | 🟡 本地安全边界；`secrets.ignore_ambient_credentials: true` 时启用                    |

**问题**：用户的 shell 会 source `~/.secrets`，其中的 `DASHSCOPE_API_KEY`、`GEMINI_API_KEY` 等变量随父进程进入 Hermes。旧 `load_hermes_dotenv()` 只清理少数 profile routing key，有意保留所有 shell provider 凭据；credential pool 随后把这些用户侧变量自动 seed 为 Hermes 模型凭据。结果是未写入 `~/.hermes/.env`、未进入 `config.yaml` 主链的 provider 仍可被模型选择与辅助路由消费，跨越了用户侧环境与 Hermes 配置的所有权边界。

**修复**：新增 opt-in `secrets.ignore_ambient_credentials`。启用后，加载 `~/.hermes/.env` 之后、执行 Hermes 显式 secret sources 之前，删除所有不在该 profile `.env` 中声明的已知 Hermes provider/tool 环境变量，并覆盖 `GOOGLE_APPLICATION_CREDENTIALS`、AWS credential chain 等 SDK 直读键；`PATH`、`HOME` 和无关用户环境变量不动。Bitwarden/OnePassword/managed env 等明确配置的 Hermes secret source 在清理后运行，仍可合法补回凭据。历史上由 ambient env seed 的 Alibaba、Gemini、Copilot pool 条目用 `hermes auth remove` 清理并 suppress，避免旧 token 继续被读取。

**验证**：`test_strict_profile_ignores_ambient_hermes_credentials` 证明 profile `.env` 中的 Azure key 保留，而 shell 的 DashScope/Gemini/Google credential path 被清除、无关变量不受影响；`test_strict_profile_allows_explicit_secret_source_after_scrub` 证明 Hermes 显式 secret source 可在清理后重新注入。Step 8b 同时检查配置开关、生产函数和测试名。终态 fresh process 中 `hermes auth list` 不再出现 Alibaba、Alibaba Coding Plan、Gemini 或 Copilot，只保留 Hermes 自有 Azure pool；Bedrock/Vertex 继续走 IAM role / service-account 路径。

**上游吸收判断**：上游提供 profile 级“只信任本 profile `.env` 与显式 secret sources、拒绝 ambient shell provider credentials”的等价开关，并覆盖 credential pool 自动 seed 与 SDK 直读键后可归档。

---

**类别：Feishu 接入、安全与会话语义**

### [PATCH-FEISHU-GROUP-ADMISSION] 群聊触发、上下文与当前发言人完整性

| 字段     | 内容                                                                                                                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `gateway/authz_mixin.py`, `gateway/run.py`（仅上游 `[New message]` 回归锚点，无本地 hunk）, `gateway/session.py`, `skills/research/llm-wiki/SKILL.md` 及对应 gateway 测试/文档 |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                              |

**问题**：群聊需要同时支持 `@bot` 与 `@配置本人账号` 触发、近期群消息回填和纯 @ 意图推断；共享 session 还必须防止 owner profile、引用内容、历史末位发言人或跨发送者 debounce 被误认成当前提问者。群授权也不能借通配符放开 DM。原纯 @ 分支硬编码排除 `p2p`，导致主会话里回复一条合并转发后只 @Bot 会在剥离 mention 后成为空文本并被静默丢弃。

**修复**：实现 assistant-user/configured-human 两类触发与身份说明、群历史回填、默认关闭且可配置的 `bare_mention_intent`、`FEISHU_GROUP_ALLOWED_CHATS` 群授权；把 bot mention 设为最高触发优先级，批处理合并判定纳入发送者（`_text_batch_is_compatible` 校验 user_id/user_id_alt/user_name；`_text_batch_key` 本身与上游一致），并在 system prompt 标注 current author（**user-turn 侧的 sender 前缀与 `[New message]` 拼接已被上游吸收**——d1afa160 起 `_prepare_inbound_message_text` 原生对 shared multi-user 会话做 `[sender]` 前缀与 channel-context 拼接，本地不再携带该 hunk，system prompt 的 current-author 块仍为本地）。开启 `bare_mention_intent` 后，群聊和 DM 中明确提及 bot 自身的纯 @ 都进入意图推断；引用消息时以引用内容为主题且只读取一次，未引用时使用既有会话历史，空文本但未 @Bot 仍丢弃。技术问题提示显式要求先读 `llm-wiki`，所有 wiki 文件调用必须携带 `~/.hermes/wiki` 路径，禁止用 terminal 探测；bundled skill 同步相同规则。

**验证**：Step 8b 独立 gate 检查 trigger/settings/history/bare-mention/wiki sentinels、DM 纯 @ 回归、group allowlist（含 `test_feishu_group_allowed_chats_wildcard_authorizes_groups_only`——wildcard 不放开 DM 的安全断言，2026-08-07 起入 gate）、current-author system prompt（本地）与 `[New message]` 上游 body-prefix 回归锚点、bot 优先级和跨发送者不合并测试。定向测试覆盖未 @ 静默、第三方 @本人代答、本人 @bot 不自我介绍、群聊与 DM 的纯 @ 引用/历史意图、DM 不被群 allowlist 放开，以及历史末位发言人与当前提问者不同时仍正确锚定当前作者。（2026-08-03 修正：旧哨兵 `_with_current_author_prefix` 在 v0.19.1 冲突解决轮已被重构移除，gate grep 一直误报 inactive；现改为真实锚点。）

**上游吸收判断**：上游同时具备等价的 Feishu 多触发 admission、群历史/纯 @ 意图、按发送者隔离的 batching 和多用户 current-author 契约后可归档；工具权限隔离不属于本补丁。body-prefix 子项已吸收（见修复段）；system prompt current-author 块与 Feishu admission 机制仍为本地。

---

### [PATCH-FEISHU-MISSED-EVENT-BACKFILL] Feishu 断线/重连漏消息补偿

| 字段     | 内容                                                                                                                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `tests/gateway/test_feishu.py`, `website/docs/user-guide/messaging/feishu.md`, `website/docs/user-guide/configuration.md`（本机 `config.yaml` 启用 6h 窗口与 60s/30s/10s WebSocket 恢复参数） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                             |

**问题**：Feishu `history_backfill` 只在 Hermes 已收到一条触发消息后补上下文，不能主动发现断网、睡眠或 stale WebSocket 期间漏掉的 `@Hermes` 触发事件。SDK 内部自动重连成功也不会通知 adapter 做补偿扫描，导致漏消息可能等 Feishu 服务端迟迟推送旧事件后才被回复；用户手动 quote 原消息再 @Hermes 触发回答后，旧事件晚到又会让 Hermes 重复回答同一问题。初版补丁另有一处主会话盲区（2026-08-08 修复）：回放重建事件用 `chat_id.startswith("oc_")` 推断 chat_type，而飞书 p2p 会话 ID 同为 `oc_` 前缀，owner DM（home channel）虽在扫描目标里，回放消息却被误标为 group、被群 mention gate 以 `trigger_mention_missing` 拒掉——主会话事实上没有恢复补偿；且 `get_chat_info` 读的 `chat_type` 是 private/public 可见性字段（DM 实测为 `None`），不能作判别源。

**修复**：新增 `missed_event_backfill` 独立恢复路径：启动、gateway reconnect 和 Lark SDK `on_reconnected` 后，在主 asyncio loop 上调度一次有界扫描。扫描目标只来自 `missed_event_backfill_chats`、Feishu home channel、显式 `group_rules` 以及 `~/.hermes/groups.yaml`，不把通配符 `group_rules: "*"` 当作租户枚举来源；每个目标 chat 通过 `im.v1.message.list` 拉取最近窗口，按时间正序只重放未见且通过原 `_admit()` 的消息，随后进入同一 `_handle_message_event_data()` / `_process_inbound_message()` 管道。手动 quote/reply 已触发的消息在 dispatch 后把 `parent_id` / `upper_message_id` / `root_id` 标记为已覆盖，使后续 delayed push 或恢复扫描命中原消息 ID 时被 dedup 跳过。配置桥接同时支持 `missed_event_backfill*` 和 `ws_reconnect_*` / `ws_ping_*` 顶层 `feishu:` 键。**主会话 DM 回放（2026-08-08 并入）**：`get_chat_info` 补采 `chat_mode`（p2p/group/topic，实测 DM 返回 `p2p`）存入 `raw_mode`；回放前按 chat 元数据解析 event chat_type，`raw_mode == "p2p"` 走 p2p lane（admit 与 session 路由和真实 DM 事件一致，不受群 mention gate 约束），元数据缺失/查询失败一律 fail-closed 按 group 处理，恢复扫描不可能放宽真实群的准入；DM 的 quote 覆盖去重由本就无条件执行的 `_mark_related_message_ids_covered` 自动继承。Hermes 自己的历史回复由 `_admit` 的 bot/self 分支拒绝，不会自我回放。已知并存（有意不动）：① 上游 `_fetch_last_message_in_thread` 仍有函数内局部 `ListMessageRequest` 导入，会遮蔽本补丁的懒加载全局——行为无差异，删除它要为纯整洁改写上游函数、扩大 diff 面，留待上游自行收敛；② `get_chat_info` 的 `type`/`raw_type` 仍源自 `chat_type` 可见性字段（实际恒映射为 `dm`），活跃入站路由由事件自带 chat_type 兜底、行为正确，纠正它会波及群/话题群既有路由面，本补丁只新增 `raw_mode` 不动旧键。

**验证**：Step 8b 单独检查 missed-event runner、per-chat backfill、SDK reconnected hook、quote-covered dedup helper、`ListMessageRequest is not None` fallback、`raw_mode` 采集与 `chat_info.get("raw_mode") == "p2p"` 判别锚点、config 桥接、用户文档和七条回归测试。测试覆盖：已知群里的未见 @ 消息会在 backfill 中触发一次 dispatch；quote+@ 覆盖的 parent 后续 backfill 不再 dispatch；SDK `on_reconnected` hook 保留原 callback 并调度 backfill；home channel DM 的未见普通消息（无 @）dispatch 一次且 source.chat_type 为 dm、bot 自身历史回复不回放（`test_missed_event_backfill_dispatches_unseen_dm_from_home_chat`）；DM quote 已答复的原消息不再 dispatch（`test_missed_event_backfill_dm_quote_covered_parent_not_redispatched`）；chat 元数据 fallback（无 `raw_mode`、`type` 声称 dm）时无 @ 消息不放行（`test_missed_event_backfill_unknown_chat_mode_falls_back_to_group_admission`）。`chat_mode` 字段语义已用真实 chat.get 对主会话/群各取证一次（2026-08-08：DM `chat_mode='p2p'`/`chat_type=None`，群 `chat_mode='group'`/`chat_type='private'`）。规范 runner 结果：`tests/gateway/test_feishu.py` 136 passed / 0 failed（2026-08-08），`tests/gateway/test_config.py` 57 passed / 0 failed（2026-08-05）。

**上游吸收判断**：上游 Feishu adapter 若提供等价的启动/重连后 missed trigger replay（含 DM/p2p 目标按 `chat_mode` 判别准入、失败 fail-closed 为 group）、SDK 内部 reconnect 通知接线、已 quote 触发回答的原消息 ID 覆盖去重、以及受控目标 chat 发现策略，可归档本补丁；单纯加强 WebSocket ping/reconnect 或上下文 `history_backfill` 不构成吸收。

---

### [PATCH-FEISHU-GROUP-SCOPE] 群聊独立 capability namespace

| 字段     | 内容                                                                                                                                                                                                                                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session_context.py`, `gateway/run.py`, `gateway/slash_commands.py`, `hermes_cli/tools_config.py`, `tests/gateway/test_session_env.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_background_command.py`, `tests/gateway/test_verbose_command.py`, `tests/hermes_cli/test_tools_config.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                             |

**问题**：Feishu DM 与群聊原本都只解析 `platform=feishu`，无法对同一 bot 的 owner DM 和共享群配置不同 toolsets/skills。初版补丁虽然新增了 source-aware helper，并把 session context 正确写成 `feishu_group`，但主 `_run_agent_inner`、busy ack、最终 reasoning/footer、proxy streaming、background task 和 slash commands 仍直接用 `source.platform` / `event.source.platform` 取 key。结果静态配置和 sandbox verifier 都显示群策略正确，真实群 Agent 却拿到 DM 的 terminal/drive 工具面与 `tool_progress: new`：工具调用链被发送到群里，受控文档入口 `feishu_doc_manage` 没有进入 Agent schema，模型转而调用 `terminal` / `feishu_drive_add_comment` 再被 sandbox 拦截；群内 `/verbose` 等命令还可能读写 DM 配置。

**修复**：新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`；Feishu group/forum/channel/thread 映射到 `feishu_group`，DM 仍为 `feishu`。所有按具体会话解析 display、toolsets、busy ack、reasoning/footer、proxy streaming、background task 和 slash-command 配置的运行路径统一调用 `_platform_config_key_for_source()`；仅 helper 内部允许退回通用 `_platform_config_key(source.platform)`。平台工具解析和保存逻辑识别该独立 key；群工具面不被默认能力补宽的机制是 `platform_toolset_options.<key>.recover_platform_tools: false` 的显式短路（`feishu_group` 不在 `PLATFORMS` 注册表内，靠该开关而非独立分支阻断 native recovery）。

**验证**：Step 8b 单独检查 session context key、`return "feishu_group"`、`run.py` / `slash_commands.py` 所有 source/event consumer 不再绕过 source-aware helper、tool recovery 开关，以及 `test_set_session_env_sets_feishu_group_config_key` / `test_get_platform_tools_feishu_group_uses_independent_config`。`test_feishu_group_runtime_scope_hides_progress_and_uses_group_tools` 穿过真实 `_run_agent` 边界作 DM 正例和两个群负例：DM 仍收到 `new` 工具卡并包含 `terminal`，群聊零 send/edit 且 Agent toolsets 包含承载 `feishu_doc_manage` 的 `sandbox_group`、不含 `terminal`。`test_successful_task_sends_result` 的 adapter fixture 显式把同步 `toolsets_for_source` 设为 `None`，防止 `AsyncMock` 自动生成 coroutine、掩盖 background source-aware 解析链。`test_feishu_group_updates_group_scope_without_mutating_dm` 从 `/verbose` 写回边界证明群配置独立更新、DM 值保持不变。

**上游吸收判断**：上游提供等价的 per-chat-type capability namespace，且 Feishu DM/group 可以独立解析工具配置时可归档。

---

### [PATCH-PLATFORM-CAPABILITY-SCOPE] 平台级 skill allowlist 与只读工具集

| 字段     | 内容                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `agent/prompt_builder.py`, `tools/skills_tool.py`, `toolsets.py` 及对应 tests/docs |
| **状态** | 🟡 未上游合并                                                                                              |

**问题**：`skills.disabled` 不能表达“某平台只允许指定 skill”；完整 `skills` toolset 又同时暴露 `skill_manage`。文件工具也缺少只读组合，平台配置容易无意带入写能力。

**修复**：新增 `skills.platform_allowed.<platform>`，并让 prompt、list/view 和 config-var discovery 共用同一解析；增加 `skills_readonly`（list/view）与 `file_readonly`（read/search）内部工具集。分类 skill 的规范名按短名匹配 allowlist，避免 `productivity:feishu-docs` 被错误拒绝。两个通配语义随实现存在并有测试覆盖：`platform_allowed: ["*"]` 为显式 allow-all 逃生口，`platform_disabled: ["*"]` 为全禁（`test_platform_disabled_wildcard`）；本机配置均未使用。

2026-08-19 与上游 project-local skill discovery 融合时，保留其 `project_dirs` cache key、trust/quarantine 与项目 skill 扫描，同时让 snapshot、cold scan 和 project scan 三条可见路径统一先过平台 allowlist/disabled 判定；两类治理是正交叠加，不得用其中一个覆盖另一个。

与上游 `skill_view` 的 repeat-view dedup 存根共存时必须保持**先 allowlist 过滤、后 dedup 存根**的执行顺序，防止被 allowlist 拒绝的 skill 因 dedup 缓存返回旧内容（2026-08 上游 `2a3a7e6f5` 融合时确立的顺序不变量，后续该函数任何 3-way 融合都必须复核）。

**验证**：Step 8b 独立检查 `get_allowed_skill_names` 的三个调用面、qualified-name 回归，并用 venv python **精确断言**两个只读工具集的成员列表（`skills_readonly == [skills_list, skill_view]`、`file_readonly == [read_file, search_files]`；2026-08-07 审计修复：旧 gate 对四个工具名的裸 grep 全部能被上游既有 `skills`/`file` 工具集满足，永远不会失败）；测试覆盖空 allowlist、命名 allowlist、`feishu_group` 独立配置、project skill 可见路径及只读工具集不被错误过滤。外层 `plugins/sandbox/verify.sh` 另做群工具面的成员/去写断言。

**上游吸收判断**：上游原生提供平台级 skill allowlist 和不含 manage/write 的只读 skill/file toolsets 后可归档。

---

### [PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY] 冗余 Tool Search 调用包装安全修复

| 字段     | 内容                                                      |
| -------- | --------------------------------------------------------- |
| **文件** | `tools/tool_search.py`, `tests/tools/test_tool_search.py` |
| **状态** | 🟡 未上游合并；上游仍把自包裹形状视为递归 bridge 调用     |

**问题**：Tool Search 要求 deferred tool 通过 `tool_call({name: target, arguments: {...}})` 调用。部分模型会把完整函数调用 envelope 再包一层，输出 `tool_call({name: "tool_call", arguments: {name: target, arguments: {...}}})`。旧 `resolve_underlying_call()` 在读取内层 target 前先执行 bridge recursion 拒绝，因此合法且已授权的 deferred tool 永远不会触发。2026-08-20 财务群 PDF→动态 HTML 任务已经成功发现 `mcp__hypertex__hypertex_create_case`，却因这一冗余包装被当作 `tool_call` 本身交给群沙箱并拒绝；Agent 随后跨三家 provider 手工生成 83KB HTML，但无法把本地文件真正交付给群成员。

**修复**：`resolve_underlying_call()` 在递归检查前只识别一种精确形状：外层 `name == tool_call`，`arguments` 是对象，且内层 `name` 是非 bridge 工具。仅剥离这一层后继续原有 deferrable 分类、session scoped catalog、required-schema probe、middleware 与 sandbox pre/post hooks；修复本身不扩大任何工具 universe。内层仍是 `tool_call` / `tool_search` / `tool_describe` 时保持原递归拒绝，双层以上不递归展开。

**验证**：回归测试使用本次真实 HyperTeX 工具名和参数形状，断言解析为 underlying target 与原始参数；负例把内层继续设为 `tool_call`，必须返回 bridge recursion 错误。Step 8b 单独运行两条测试，确保既能恢复一层模型格式偏差，又不会打开桥接递归或绕过 session/sandbox gate。

**上游吸收判断**：上游为 `tool_call` 提供等价的一层 envelope normalization，并保留 bridge recursion、scoped catalog 和底层 hook 权限语义后可归档。若仅在 prompt 中提醒模型不要双包，不构成确定性吸收。

---

### [PATCH-FEISHU-GROUP-APPROVAL] 群聊危险命令审批不可升级权限

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `tools/approval.py`, `tests/tools/test_approval.py`    |
| **状态** | 🟡 未上游合并；`PATCH-FEISHU-GROUP-SANDBOX` 的纵深防线 |

**问题**：旧群聊 terminal 路径曾进入 dangerous-command approval，群成员点击卡片后命令继续执行。即使当前群聊不再暴露 terminal，审批层若不区分 chat type，未来工具配置漂移仍可能重新形成提权路径。

**修复**：`_is_restricted_feishu_approval_session()` 对 Feishu group/forum/channel/thread 直接返回 `BLOCKED`，不通知、不入 pending queue、不发送审批卡；owner DM 继续走 manual approval。chat type 优先读 `HERMES_SESSION_CHAT_TYPE` ContextVar、仅在为空时回退解析 session key，使 cron/API/wake 等非规范 key 不会 fail-open。**2026-08-07 审计重排硬拦顺序**：此前硬拦位于 Phase 3，`is_approved()` 进程全局集（owner DM "always" 审批 + `command_allowlist`）、yolo/mode=off 与 smart approval 均在其前短路，配置漂移即可绕过；现改为三层——①主入口与 legacy 入口在 yolo/allowlist **之前**加早期硬地板（cheap `detect_dangerous_command`，危险即 `restricted_chat`）；②tirith 告警在受限会话不消费 `is_approved` 短路、smart approval 对受限会话整体跳过，使告警必达 Phase 3 既有硬拦；③`check_execute_code_guard` 第三入口同样无条件硬拦（整脚本审批卡同为提权面）。当前配置（manual + 空 allowlist）此前恰好兜住，现在不再依赖配置。

**验证**：Step 8b 检查 hard-block helper、`restricted_chat` 行为串、`hard floor` 注释锚点及五条测试：`test_feishu_group_dangerous_command_does_not_send_approval_card`（零通知零 queue）、`test_feishu_group_block_precedes_allowlist_and_prior_approvals`（approve_permanent + allowlist 双短路均不放行）、`test_feishu_group_block_skips_smart_approval`（smart 模式不询问 aux LLM 直接 BLOCKED）、`test_feishu_group_block_via_legacy_check_dangerous_command`、`test_feishu_group_execute_code_guard_blocked`、`test_feishu_group_chat_type_from_context_when_key_not_canonical`（非规范 key 走 ContextVar 不 fail-open）；Step 8e 再验证 owner DM 仍保留完整工具与人工审批策略。

**上游吸收判断**：上游 approval 原生按 chat type 禁止共享群创建或批准危险操作、同时不影响 owner DM 时可归档。

---

### [PATCH-FEISHU-NORMAL-REPLY] 回复始终留在普通聊天消息流

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：`root_id`/generic `metadata.thread_id` 会让普通引用回复被 Feishu 当作 thread/topic 投递，甚至在无有效引用锚点时把 thread id 当 receive id。

**修复**：发送出口固定 `reply_in_thread=False`；引用目标只取显式 `reply_to`/`reply_to_message_id`；create-message 分支忽略 generic thread metadata，缺引用锚点时回退主聊天普通消息。

**验证**：Step 8b 单独检查 `reply_in_thread = False`、忽略 thread metadata 的实现和回归测试，并带两条**负向锚点**（`! grep 'reply_in_thread = bool'`、`! grep '_build_create_message_request("thread_id"'`，2026-08-07 起）——正向锚点只证明本地行存在，无法发现 3-way 把上游 metadata-driven lane 在注释下方重新合入的对撞形态；覆盖普通引用、文档回复和无引用锚点三条路径。

**上游吸收判断**：上游提供明确的普通引用/话题开关并保证 generic thread metadata 不改变 Feishu 投递 lane 后可归档。**对撞警示**（2026-08-03 审计）：post-26e0b1c 上游在同一 send/reply-body 区域走**相反语义**——`reply_in_thread = bool(metadata.thread_id)`（metadata 驱动投递 lane），与本补丁"固定 `reply_in_thread=False`、忽略 generic thread metadata"直接冲突。下次升级该区域的 3-way 结果**不可信任自动合并**：必须人工按本补丁不变量重解（普通引用回复永不进 thread lane），并以现有回归测试三条路径复验后才能刷新 bundle。

---

### [PATCH-FEISHU-QUOTE-CHAIN-SESSION] 引用链不切分群会话

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并（上游入站仍 `thread_id or root_id`）                    |

**问题**：入站 `_process_inbound_message` 把 `thread_id` 解析为 `getattr(message,"thread_id") or getattr(message,"root_id")`。但飞书的 `root_id` 是**引用链根**，不是话题 id——群里每条未引用的发言都会开一个新 root。`build_session_key`（`gateway/session.py:1744`）看到 `thread_id` 就把它拼进 session key，于是**每条引用链各自切出一个独立 session**：明明没有任何 reset 生效（`session_reset.idle_minutes: 1440` 远未到），`SpaceSight技术分享专项群` 2026-08-12 两小时内产生 3 个 session（`...:om_x100b688abc...` / `...:om_x100b68f54d...` / `...:om_x100b68f5e9...`），与 8/07、8/11 干净的群级 key 形成对照。每个新 session 都从零重载 `llm-wiki`(22k) + `feishu-docs`(33k) 全文与 30 分钟历史回填，直接放大 compaction 压力（当日 15:04–15:06 两分钟内连压两次的成本来源）。上游自己知道这个 conflate——`adapter.py` 出站侧注释明写 "The inbound handler conflates root_id into thread_id"，但只在出站钉了 `reply_in_thread=False`（`PATCH-FEISHU-NORMAL-REPLY`），**入站的 session key 污染没有对应修复**。

**修复**：入站只取真正的 `thread_id`，删除 `root_id` 回退。飞书话题/thread lane 本机刻意不用（`thread_id` 实测恒为 None），因此这是纯粹移除一条错误回退，不改变任何既有可用行为。**引用链能力完整保留**：链条由第 3659 行独立计算的 `reply_to_message_id`（`parent_id` → `upper_message_id` → `root_id`）与 `reply_to_text` 承载，与本字段无关。`_resolve_channel_prompt(chat_id, thread_id)` 的第二参在 `feishu.channel_prompts` 未配置时（本机即未配置）不产生行为差异。

**验证**：`tests/gateway/test_feishu.py::test_quote_chain_root_id_does_not_become_thread_id_or_split_session` 构造带 `root_id="om_chain_root"` + `parent_id="om_quoted"` 的真实引用回复，断言三件事：`event.source.thread_id is None`；**用真实 `build_session_key` 求值**得到 `agent:main:feishu:group:oc_grp` 且不含 `om_chain_root`（行为断言而非 grep）；`reply_to_message_id` / `reply_to_text` 仍正确送达（证明只去掉会话切分、没有削弱引用能力）。测试为 load-bearing：恢复 `or root_id` 后该用例在 `assertIsNone(event.source.thread_id)` 失败。既有 14 处 `root_id=None` 用例判定不变，27 个受管测试文件 1042 passed / 0 failed / 3 skipped。

**上游吸收判断**：当上游入站不再把 `root_id` 当 `thread_id` 回退（或为飞书引入真正区分"话题 id"与"引用链根"的字段）时可归档。与 `PATCH-FEISHU-NORMAL-REPLY` 是同一 conflate 的两侧：那条守出站投递 lane，本条守入站 session 身份；两者可被不同上游 PR 分别吸收，故不合并为一个补丁。每轮升级须复核该行未被 3-way 恢复成 `or root_id` 形态。

---

### [PATCH-COMPACTION-LIFECYCLE-SILENCE] 自动 compaction 两端边界都不进聊天

| 字段     | 内容                                                                         |
| -------- | ---------------------------------------------------------------------------- |
| **文件** | `gateway/run.py`, `tests/gateway/test_telegram_noise_filter.py`              |
| **状态** | 🟡 未上游合并（上游 `ROUTINE_COMPRESSION_STATUS_SAMPLES` 仍只登记 start 边） |

**问题**：自动 compaction 生命周期有两条状态边——start（`COMPACTION_STATUS`）与 done（`COMPACTION_DONE_STATUS`，由 `_emit_compaction_done` 发出）。上游把 8 条 routine 状态登记进 `agent/conversation_compression.py` 的 `ROUTINE_COMPRESSION_STATUS_SAMPLES`，**唯独漏掉 done 边**。该元组既是 `_TELEGRAM_NOISY_STATUS_RE` 的耦合基准、又是 `_COMPRESSION_PROGRESS_STATUS_RE` 的构造来源，漏登记等于同时逃过噪声抑制和 `compression.progress_notices` 开关：start 被过滤、done 原文投递。2026-08-12 15:04:55 与 15:05:48，`✓ Context compaction complete — continuing turn...` 两次发进 `SpaceSight技术分享专项群`（`oc_9e0d0df1...`），把 Hermes 内部上下文管理暴露给同事。上游注释明确要求"reword 时同步更新正则"，说明作者意识到该耦合，只是漏了终止边。

**修复**：`_TELEGRAM_NOISY_STATUS_RE` 增加 `context\s+compaction\s+complete` 支路，令 done 边在所有聊天面被抑制；同时把 `COMPACTION_DONE_STATUS` 加入 `_COMPRESSION_PROGRESS_STATUS_RE` 的模板元组，使其与 start 边同受 `compression.progress_notices` opt-in 管辖——否则开启该开关的用户只会看到"开始"而永远收不到"完成"。故意不改 `agent/conversation_compression.py`：修在 gateway 投递边界，让上游补齐 samples 元组后本补丁可整块归档，且不与上游那份常量表产生 3-way 对撞。失败类通知（`⚠ Compression aborted` / 空转录 / blocked-overflow）与手动 `/compress` 反馈仍是刻意的可见性豁免，不受影响；本地/程序化面（CLI、TUI、API JSON、webhook）经 `_gateway_surface_passes_raw_text` 保持原始诊断流。

**验证**：`tests/gateway/test_telegram_noise_filter.py` 新增两组本补丁携带的测试——`test_both_auto_compaction_lifecycle_edges_suppressed`（参数化 start/done **源常量**而非字面量，三个聊天面各断言投递为 `None`）与 `test_both_auto_compaction_edges_are_progress_gated`（断言两边都被 `_COMPRESSION_PROGRESS_STATUS_RE` 命中，锁定 opt-in 对称性）。测试证明为 load-bearing：从正则移除新增支路后 done 边重新逃逸（`False` → `True` 对照已复核）。既有 `VISIBLE_COMPRESSION_MESSAGES` 11 条豁免与 8 条 routine samples 全部保持原判定，`test_telegram_noise_filter.py` 141 passed；27 个受管测试文件全量 1041 passed / 0 failed / 3 skipped（firecrawl 可选依赖基线）。

**上游吸收判断**：当上游把 `COMPACTION_DONE_STATUS` 补进 `ROUTINE_COMPRESSION_STATUS_SAMPLES`（从而自动进入两个正则），或以其他方式让 compaction 两端边界在聊天面对称静默时，可整块归档并保留两条测试作回归 sentinel。每轮升级须复核 done 边是否已被上游登记；若上游改为"routine 状态默认可见"，则本补丁的抑制方向需与新策略重新对齐，而不是静默保留。

---

### [PATCH-GATEWAY-FAILOVER-STATUS-SILENCE] 模型路由状态不进入聊天

| 字段     | 内容                                                            |
| -------- | --------------------------------------------------------------- |
| **文件** | `gateway/run.py`, `tests/gateway/test_telegram_noise_filter.py` |
| **状态** | 🟡 未上游合并；上游 fallback-observability 有意向用户 surface   |

**问题**：`_try_activate_fallback()` 同时维护两条内部状态：失败路径缓冲 `Primary model failed — switching to fallback...`，成功路径挂起 `Switched to fallback model: ... → ...`。成功时后者由 `_emit_pending_fallback_notice` 单独发出；终态失败时前者随 `_flush_status_buffer` 重放。Gateway 的聊天噪声过滤虽声称抑制 provider retry chatter，却没有匹配这两种文案。2026-08-20 SpaceSight 国内业务群的创建文档 turn 最终因工具参数截断失败，缓冲区 flush 后把完整 Bedrock inference-profile ARN 原样发进群，暴露了纯运维路由细节。

**修复**：只在共享的聊天 status 投递边界 `_prepare_gateway_status_message` 扩展 `_TELEGRAM_NOISY_STATUS_RE`，覆盖 `primary model failed...switching to fallback`、`switched to fallback model` 与通用 `switching to fallback model/provider`。Feishu、Telegram、Slack、Discord 等 human-facing chat 返回 `None`；local/TUI、API、webhook 继续保留原始状态，日志与模型使用统计也完全不变。最终失败正文仍照常投递，本补丁不吞错误本身，只吞独立的模型路由旁白。

**验证**：`test_telegram_noise_filter.py` 把本次真实失败文案和成功 one-shot 文案加入 `NOISY_STATUS_MESSAGES`，三个代表性聊天面均断言静默；`test_programmatic_surfaces_keep_raw_fallback_status` 反向证明 local/API/webhook 原样保留。Step 8b 直接调用真实 `_prepare_gateway_status_message` 覆盖五种聊天面与 local 负向边界。

**上游吸收判断**：上游若将 fallback observability 改为仅日志/结构化 telemetry，或在所有聊天 status 边界等价区分“用户可行动故障”与“内部模型路由”并默认隐藏后可归档。仅改变 fallback 文案不构成吸收，需同步更新源常量/测试或继续由正则覆盖。

---

### [PATCH-FEISHU-FINAL-ONLY] Feishu 默认最终内容优先，长任务保留通用心跳

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/display_config.py`, `tests/gateway/test_display_config.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_verbose_command.py`（本机 `config.yaml` 按 DM/group 显式覆盖）。运行 consumer 的 source-aware 解析 hunk（`gateway/run.py` / `gateway/slash_commands.py`）归属 `PATCH-FEISHU-GROUP-SCOPE`，此处仅为依赖 |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                |

**问题**：Feishu 默认 tool progress、streaming 和 interim bubbles 会把草稿、工具进度或思考式中间态暴露到群聊；这与消息是否进入 thread 无关，应独立控制。只验证 `display.platforms.feishu_group` 的静态值并不足够：运行 consumer 若错误使用 `feishu` key，群聊仍会继承 owner DM 的 `tool_progress: new`。初版为追求 final-only 同时关闭 long-running notification，真实 PDF 任务耗时 19 分 24 秒时群里全程无任何存活信号，用户合理判断为“引用 PDF 后没有响应”。

**修复**：Feishu 内置 display tier 继续默认关闭 tool progress、streaming、interim assistant messages、long-running notification 和 busy detail。当前本机让主会话 DM 使用 `tool_progress: new` 且不发心跳；群聊保持 `tool_progress: false`、关闭 streaming/interim/thinking/busy detail，但显式配置 `long_running_notifications: generic` 与 `agent.gateway_notify_interval: 180`。因此普通任务仍只显示最终内容；超过 3 分钟的任务只出现一条无工具名、模型名、迭代数的通用心跳，后续周期尽量 edit 同一条消息，不泄露内部执行链。所有运行时 display consumer 通过 `PATCH-FEISHU-GROUP-SCOPE` 的 source-aware key 解析。若 provider 把 thought 错塞进正文，由 `PATCH-VERTEX-HIDDEN-THOUGHTS` 请求侧抑制。

**验证**：Step 8b 检查 Feishu display defaults 与 `test_feishu_defaults_to_final_only`；本机策略校验 DM `tool_progress: new` + long-running false，群聊 `tool_progress: false` + long-running `generic` + 180 秒间隔，且两者的 streaming/thinking/interim/busy detail 均关闭。真实 `_run_agent` 边界测试继续证明群聊没有 tool progress/interim send；通用心跳使用既有 `allow_generic=True` 路径，不包含 activity detail。`/verbose` 测试证明群命令只读写 `feishu_group`。

**上游吸收判断**：上游 Feishu 提供等价的 final-answer-first profile：隐藏工具/思考/路由内部状态，同时允许可配置、无内部细节的长任务存活心跳后可归档。

---

### [PATCH-LOCAL-PROFILES] 本地人物/群画像与群聊输出保密

| 字段     | 内容                                                                                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `gateway/run.py`, `gateway/stream_consumer.py`, `plugins/platforms/feishu/adapter.py` 及对应测试；`people.yaml` / `groups.yaml` 为配置仓库数据 |
| **状态** | 🟡 本地个性化功能，不预期上游直接吸收                                                                                                                                |

**问题**：模型只凭 open_id/显示名无法按用户维护的人物背景和群人设调整表达；画像私有字段、数据来源和 `people.yaml` 文件名又绝不能在群聊泄露。工具受限时也必须披露证据边界，不能把未验证内容包装成结论。

**修复**：按 mtime 热加载 people/group profile；人物画像采用公开白名单：只有 `name`、`role`、`department`、`address` 可对外，所有已知私密字段和未来手工新增字段都进入模型可读的保密块并纳入确定性出站过滤；open_id/user_id/union_id/id 和未与公开字段重合的 aliases 只用于匹配，同样不得输出。群画像只控制风格、介绍、能力口径和提示性服务时间。所有 group/channel 无条件注入来源保密和工具限制声明；非 DM 的最终、流式、fallback、临时 assistant 消息、流式 TTS 和 `/background` 完成/失败通知等可见/可听文本统一经过 `redact_private_person_profile_text`/`text_filter`，后台完成通知不回显 prompt；redactor 自身内置 DM 早退（2026-08-07 加固：所有调用方虽已在外部按 chat_type 分流，但未来新增调用方漏掉分流时按构造即安全——群不漏、DM 不被误遮；`test_private_profile_redactor_leaves_dm_text_untouched` 锁定 DM 原样返回）。loader 缺文件或坏 YAML 时安全降级，DM 不注入群画像规则。`people.yaml` 与 `groups.yaml` 保持普通可编辑文件，owner 始终拥有读写权限；两个热加载器和升级 Step 8b 都会将其收敛并验证为 `0600`，因此同账号 VSCode 可照常编辑，而其他本机账号不可读。

聊天历史（群聊回填与合并转发展开共用的 `_history_sender_label`）此前只渲染 `ou_xxx` 裸 id 或缓存显示名，缓存未命中时模型无法分辨发言人。现复用同一份 `_lookup_person` 索引（open_id/user_id/union_id/name/aliases）把发送者 join 到 people.yaml：命中则用画像 `name`，并只追加公开面中的 `role`/`department` 作为限定语。历史会被回显进群聊回复，因此限定语字段是白名单而非黑名单，公开四项以外（含 `employee_no`、保密备注等）一律不进入 label；join 失败或 people.yaml 缺失时安全降级为原有 id/显示名。

**验证**：Step 8b 检查 profile loaders/lookups、公开 `address`、未知字段 private-by-default、技术 ID/未公开别名过滤、来源保密常量、私有值/文件名字面量 redactor、stream/TTS filter、后台/临时消息出站测试、后台不回显 prompt 断言，以及 `people.yaml` / `groups.yaml` 的 owner-rw `0600` 权限与热加载自愈测试；另加历史发送者 join 的 `_history_sender_person`/`_history_person_qualifier` 与两个回归测试（公开字段命中 + 保密字段不泄露 / lookup 抛错时降级）。验证只归属于画像与输出过滤；旧 terminal/script-root allowlist 已被删除，不再作为本补丁的实现或测试。

**上游吸收判断**：若上游提供等价的本地 per-sender/per-group profile 注入与全出站路径隐私过滤，可重新评估；否则保持本地补丁。

---

**类别：Feishu 资源、文档与渲染**

### [PATCH-FEISHU-RESOURCE-ACCESS] 附件回看、Drive 链接与 tenant 文档读取

| 字段     | 内容                                                                                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/run.py`, `gateway/platforms/base.py`, `tools/feishu_doc_tool.py`, `tests/gateway/test_feishu.py`, `tests/tools/test_feishu_tools.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                        |

**问题**：群聊媒体与 @mention 常分成两条消息，引用里的 `/file/<token>` 也不是 IM 附件；普通 gateway 工具调用没有 comment thread-local client 时，tenant 凭据明明存在却无法读取飞书文档。旧附件补丁还只允许群 `trigger_kind == bot` 且非 command 的回填：DM 显式引用、群 `@配置本人账号`、Feishu command composer 遗留的单独 `/` 均会只留下缓存路径而不把图片/视频交给模型；显式再次引用同一资源又会被本应只约束滑动窗口的去重缓存错误抑制。另外，被引用的合并转发消息在 webhook payload 里不带子消息体，上游只把它归一化成 `[Merged forward message]` 占位符，因此群里"引用合并记录 + @Bot"只能看到占位符，而私聊直发同一条合并记录却能正常展开。初次补上展开后仍有第二层截断：Gateway 对所有 `reply_to_text` 硬编码 `[:500]`，真实卡片的 12 条子消息虽已全部从 Feishu API 取回，送模时却在第 6 条中间静默截断，导致机器人错误声称后续内容不存在。2026-08-16 的真实 PDF 回填又暴露第三层：`_fetch_message_text` 为生成引用说明先下载一次附件并把绝对 cache path 写进 `reply_to_text`，随后 `_backfill_reply_attachments` 为真正送模再次下载，同一 PDF 产生两个缓存副本；sender-window 只接受 image/file/media、遗漏原生 audio，窗口与上限也不可配置，失败后静默按纯文本继续。

**修复**：将显式引用恢复与群聊同发送者滑动窗口回看拆开：DM 和已准入的 `bot`/`assistant_user` 群触发可恢复引用附件（整条恢复链以 `history_backfill: true` 为总开关且触发消息自身不带媒体时才扫描——本机已启用该开关；上游默认 false 时显式引用恢复不生效，属有意搭载而非"无条件始终"），显式重复引用不受窗口去重限制；窗口扫描仍仅限群聊并保持有界去重。把单独 `/` 归一为无实际命令的 bare mention，使引用主题进入同一意图链。扫描正文/引用中最多三个 Drive file token，以 tenant 身份下载并保留 MIME/文件名（`_MAX_DRIVE_LINK_BYTES` 100 MB 上限为下载完成后的事后校验、非流式截断——tenant 侧文件由管理员控制，暂不做流式守卫，留观）；普通网页链接原文保留。`feishu_doc_read` 缺 comment client 时从 env/`.env` 构建 tenant client。引用目标是 `merge_forward` 时，`_fetch_message_text` 复用直发路径的 `_expand_merge_forward_message` 展开子消息；`_collect_reply_attachments` 同时接受 `upper_message_id` 指向引用目标的子消息，使转发记录内的图片/文件也被下载。Gateway 识别仅由该展开器生成的 `[Merged forwarded messages]` 内部标记，把 Feishu 引用上下文上限从通用 500 提高到有界 20,000 字符；普通 Feishu 引用与其他平台仍保持 500，避免无关扩权。该补丁只负责取得资源字节/API 文本并完整交给模型，不负责解析文件格式。2026-08-16 进一步把 sender-window 扩为 image/file/media/audio，并把 window/messages/files/timeout 四个限制改为 Feishu 配置项（本机 300s / 3 / 6 / 8s）；引用/history 只生成 `[Image]` / `[Attachment: name]` 的 path-free 占位符，不再为了拼路径预下载资源，真正资源只由回填链下载一次。直接下载、引用回填或窗口回填失败会向当前 turn 注入明确、无宿主路径的失败状态，要求模型如实告知重发，不能静默假装读取。2026-08-05 对上游 `b51c4e6a7` / `e80b7aeda` 融合时，保留其线程锁保护的 SDK 延迟导入与 None 判定，删除重复 loader 形状，只在上游 `_load_lark_oapi()`/None 初始化集合中增加本补丁独有的 `DownloadFileRequest` / `ListMessageRequest`；资源访问的 admission、下载、展开、上界与 tenant fallback 均未被吸收。

**验证**：Step 8b 单独检查 sender/reply backfill、显式重复引用不被去重、单独 `/`、DM/两类群触发、Drive URL/download、tenant client fallback、引用 merge_forward 展开（`is_forward_child` + `_fetch_message_text` 展开分支）、Gateway 20,000 字符专用上限、`gateway/platforms/base.py` 的 `.odt` MIME 映射锚点及对应测试。`test_quoted_resource_matrix_reaches_event_across_dm_and_group_triggers` 从完整入站路由覆盖群图片、群视频、群音频、群 Drive/PDF、DM 网页和 DM Drive 链接；`test_explicit_requote_is_not_suppressed_and_media_video_is_preserved` 锁定重复引用与视频 MIME；`test_sender_window_backfill_includes_audio_and_uses_configured_window` 锁定 audio + 配置化窗口；`test_fetch_message_text_uses_path_free_attachment_placeholder` 证明引用文本不下载资源、不泄露绝对路径；直接下载与回填失败测试证明失败状态抵达 Gateway event。`test_feishu_merge_forward_reply_context_is_not_cut_at_generic_500_chars` 同时证明 12 条长转发的尾条保留、普通引用仍在 500 截断。真实 API 卡片返回 13 items（1 parent + 12 children、正文 915 字符），修复前 DB turn 在第 6 条中间止于 500 字符，修复后完整文本落入 user turn。

**上游吸收判断**：上游同时支持分离消息附件回看（含 audio、配置化有界窗口和显式失败）、Drive 正文链接下载、引用合并转发的子消息展开及完整有界送模、path-free 引用占位符与单次资源下载、无 comment-context 的 tenant doc client 时可归档；SDK 延迟导入本身不是该补丁的语义吸收条件。

---

### [PATCH-DOCUMENT-EXTRACTION] 可信文档文本抽取

| 字段     | 内容                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/run.py`, `tools/read_extract.py`, `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock` 及对应 tests                     |
| **状态** | 🟡 部分吸收（XLSX/DOCX/IPYNB 抽取、`read_file` 接线和 anydoc-only 扩展已上游合并；native PDF/HTML/PPTX/ODT 与入站接线仍本地） |

**问题**：附件成功下载后，PDF/HTML/PPTX/ODT 等二进制仍只给模型路径；群聊又不能临时执行解析脚本。上游 `tools/read_extract.py` 已覆盖 IPYNB/DOCX/XLSX，并在 `b2598b41e` 后通过可选 anydoc 覆盖 legacy Office/ODF/RTF/EPUB/PDF，但这些路径依赖可选转换器且没有替代本地 native PDF/HTML/PPTX/ODT、pypdf pin 与 Gateway 入站抽取。初版入站抽取虽把文本送进 prompt，仍同时暴露原始 cache 绝对路径，真实 `Data Pipeline Workshop` turn 因此在已经拿到 PDF 文本后又调用一次 `read_file` 并被群沙箱拒绝；同时“只要任意页有文字就算成功”的分支会漏掉混合 PDF 中占比较高的扫描/图片页。

**修复**：在上游 `read_extract.py` 抽取层上扩展 PDF（pypdf，兼容 PyMuPDF 安装）、HTML（移除主动内容）、PPTX、ODT，并对每文件/每轮文本做上界；上游 `file_tools.py` 的 `read_file` 接线按 `EXTRACTABLE_EXTENSIONS` 自动获得新格式，无需本地改动 `read_file` 主路径。`gateway/run.py` 新增 `_extract_inbound_document` 在线程池中抽取入站附件，向模型明确内容是不可信参考数据。成功抽取提示只说明“文本已在下方”，不再携带宿主/container cache path；加密、损坏、超限或不支持文档只给经过分类的 path-free `FAILED` 状态，精确异常保留日志。新增 `pdf_needs_visual_fallback()` 复用上游逐页 coverage 阈值：文本抽取成功但有意义的扫描/图片页缺口时，继续把当前 PDF 交给 `PATCH-MULTIMODAL-SIDECAR` 的首个 configured capable route；sidecar 失败仍保留已抽取文字并标记 `PDF visual coverage status: INCOMPLETE`，不得声称看过缺页。依赖在 project extra、lazy deps 与 lockfile 中固定。设计留观：`pypdf` pin 落在 `LAZY_DEPS["platform.feishu"]` 而非 `tool.doc_extract`（后者上游仍 anydoc-only）——本机 Feishu 栈必装故等价；非 Feishu 部署走 `read_file` 读 PDF 时不会触发懒装，若上游重写 feishu extra 需把 pin 迁到 `tool.doc_extract`。

**2026-08-03 收缩**：上游在 26e0b1c 已自带 `read_extract.py`（XLSX/DOCX/IPYNB）并经 `file_tools.py` 接进 `read_file`，本地曾并存的 `file_operations.py` `_read_spreadsheet` 第二条 XLSX 路径成为死代码（抽取分支先行拦截），已连同其测试一并删除；`tools/file_operations.py`、`tests/tools/test_file_operations.py` 移出 `PATCHED_FILES`。**2026-08-06 收缩**：上游 `b2598b41e` / `997a913` / `ffdbc88` 吸收 anydoc-only 格式、失败重试和 anydoc size cap；本地测试已把 anydoc-only 可用性（RTF/EPUB/DOC）与 native-overlap 可用性（PDF/PPTX/ODT）分离，防止上游 anydoc 语义重新压住本地 native 抽取。**2026-08-08 并存记录**：上游 `8de3ddb9e` / `89c14aeb9` / `765940df7` 新增 bytes 边界 `extract_document_bytes`（file backend 传输字节 → 私有 temp 文件物化）与扫描版 PDF 覆盖率警告（pdftotext 逐页计数、空页占比阈值提示）——与本地 hunk **正交不吸收**：本地入站接线（`_extract_inbound_document`）是 path-based（飞书媒体先落本地缓存），本地 native 抽取器/上界/zip 安全均不被替代。本轮 3-way 唯一真冲突即在该文件的 import 块与函数插入点，按并存解决（两侧全保留）；上游同轮为该文件新增约 15 条测试与本地测试并存运行。

**验证**：Step 8b 单独检查 common extractors（`_extract_pdf` / `_extract_html_file`）、`_extract_inbound_document`、`pdf_needs_visual_fallback`、pypdf 双路径依赖和 `TestCommonDocumentExtraction`，并锚定两条 2026-08-06 收缩测试（`test_native_overlap_formats_remain_extractable_without_anydoc` / `test_anydoc_only_formats_not_extractable_without_anydoc`）、入站 HTML、path-free document note、混合 PDF sidecar 和 `test_feishu_group_document_matrix_reaches_user_turn`。真实 extractor canary 覆盖 PDF、HTML、TXT、DOCX、XLSX、PPTX、ODT；群聊 consumer 矩阵证明七类内容进入 Feishu group user turn、标记为 untrusted reference data、不含缓存路径且不依赖 terminal；coverage 正反例与 mixed-PDF Gateway 测试证明纯文本不旁路、扫描缺口补读。已知留观（P3，本机不可达）：native 抽取失败时不回落 anydoc——`.pdf` 等双集合扩展名在 pypdf 缺失 ∧ anydoc 存在的配置下会直接报缺包而非尝试 anydoc；本机 pypdf 由 feishu lazy 栈钉死安装、anydoc 未装，路径死代码，待上游动该区域时一并处理。

**上游吸收判断**：上游 `EXTRACTABLE_EXTENSIONS` 以 native 或同等无需 prompt 的依赖策略覆盖 PDF/HTML/PPTX/ODT，并提供等价的 Gateway 入站附件抽取接线、prompt 上界、path-free 成功/失败状态与混合 PDF coverage→视觉补读后可归档；仅有 anydoc 可选转换不构成本地 native/inbound 语义吸收。资源获取能力独立留在 `PATCH-FEISHU-RESOURCE-ACCESS`。

---

### [PATCH-FEISHU-MARKDOWN] Feishu 出站 Markdown 归一化

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：飞书 post/md 元素能渲染行内标记（加粗 / 斜体 / 列表 / 链接 / 行内代码），但有三类格式无法渲染：①ATX 标题 `## heading` 与引用 `> quote` 以原始符号字面显示；②（2026-07-25 新增）飞书 md 解析器严格执行 CommonMark emphasis flanking 规则——`**` 内侧是标点且外侧紧贴文字时加粗不成立（如 `到**“端云通信协议”**的`）；③（2026-08-15 主会话复现）整行引用本身为粗体时，旧转换把 `> **问题**` 写成 `▎**问题**`，Feishu 因视觉 quote bar 后没有 token boundary 而原样显示星号。

**修复**：两处改动，均在 `_build_outbound_payload` 出站路径：

1. **标题 / 引用**：新增 fence-aware 预处理器 `_promote_block_markdown(content)`，将 post/md 渲染不出的块级语法转成等价可渲染形式：`## heading` → `**heading**`，`> quote` → `▎ quote`；视觉 quote bar 后始终保留一个空格，因此 `> **整行粗体**` 会稳定变成 `▎ **整行粗体**`。代码块内的 `#` / `>` 原样保留。

2. **行内加粗 flanking**（2026-07-25）：`_promote_block_markdown` 逐行（跳过代码块与行内代码 span）调用 `_fix_strong_flanking`：按 CommonMark 规则（标点=Unicode P*/S* 类）检测无法 open/close 的 `**span**`，仅把违规一侧的边缘标点连续段移出标记（`到**“x”**的` → `到“**x**”的`），字符序列不变；全标点 span 无法挽救时去掉标记。刻意不做"对称搬移"——那会把与 span 中部配对的括号也拽出粗体，产生更差的观感。合法 span（外侧为空白/标点/行边界，或内侧为文字）一律不动；内容无变化时保持返回原对象（fast path 身份语义不变）。

**表格子分支（已退役 2026-07-25）**：旧版补丁曾在检出 GFM 表格时先调 `convert_table_to_bullets()` 转成 `**行标题**` + bullet 组，规避早年"含表格的 post/md 整条空白"的客户端 bug。上游 #52786（2026-07-24 轮吸收 `prefer_post` 时的冲突来源）声称新版客户端已原生渲染表格；2026-07-25 真机实测「含 GFM 表格的 post/md 消息」正常渲染（不空白、单元格加粗正常）后，按既定计划撤除该子分支：`_build_outbound_payload` 恢复上游表格直传原文，补丁自有测试 `test_build_outbound_payload_table_converts_to_bullets_and_posts` 删除；`test_feishu.py` 中的 `test_build_outbound_payload_uses_post_for_markdown_table` 为**本地补回**的直传断言（上游已在 `6b81590c5` 低价值测试清理中删除该名字；上游现存表格测试是未改动的 `test_feishu_table_markdown.py::test_markdown_table_uses_post_not_text`）。若老客户端再现空白表格，可从外层仓历史恢复该分支（见 git log patches/local-patches.diff）。

**验证**：Step 8b 直接 import `_promote_block_markdown`，断言真实失败形状 `> **“用元层逻辑证明对象层逻辑可靠”…**` 精确输出为 `▎ **…**`；同时保留 helper、负向 `convert_table_to_bullets` 与 `test_promote_block_markdown_fixes_flanking_inside_quotes_and_headings` 锚点。规范 runner 的 `tests/gateway/test_feishu.py` 必须全绿；真机发送再确认 Feishu 客户端不显示原始 `**`。

**上游吸收判断**：若上游为飞书 post/md 原生补齐标题 / 引用渲染，或将回复改走 interactive card markdown 元素，可归档本补丁的 promote 分支；flanking 分支（修复 ②）在上游对出站 markdown 做等价 flanking 归一化前保持活跃。表格转 bullets 子分支已于 2026-07-25 真机验证原生表格渲染后撤除（该部分现与上游 #52786 行为一致，见上文"表格子分支（已退役）"）。

---

### [PATCH-FEISHU-RESPONSE-BUDGET] 生成侧软字数预算与发送侧单条 post 兜底

| 字段     | 内容                                                                                                                                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/{display_config.py,session.py,run.py}`, `plugins/platforms/feishu/adapter.py`, `tests/gateway/{test_display_config.py,test_session.py,test_feishu.py}`, Feishu/configuration 文档；外层 `config.yaml` |
| **状态** | 🟡 未上游合并；本机 `feishu` / `feishu_group` 均配置 `response_char_limit: 3000`                                                                                                                               |

**问题**：旧系统只有发送端硬切分：Feishu adapter 固定 `MAX_MESSAGE_LENGTH=8000`，任何更长回复都会在发送前拆成多条带序号消息。最近真实回复 8,397、8,703、11,351 字符均因此分段；模型在生成时不知道聊天面的阅读预算，也不会主动把长报告放进飞书文档。单纯提高硬上限只能减少分段，不能阻止冗长回答；单纯 prompt 限制又不可靠，模型偶尔超限时仍需可送达兜底。

**修复**：新增通用 `display.platforms.<platform>.response_char_limit`（整数，0=关闭，范围收敛到 0–100,000）。Gateway 按 source-aware key 区分 `feishu` DM 与 `feishu_group`，把解析值写入 `SessionContext` 并纳入 ephemeral prompt cache key；system prompt 要求最终聊天回复尽量控制在该 Unicode 字符预算内、结论优先、去重复。该预算**只约束最终飞书聊天气泡**，明确禁止据此缩短或截断飞书文档正文、HTML、附件、Markdown 源稿或工具调用 payload；这些交付物保持任务所需的完整长度。用户明确要求长报告/需求文档且有文档/文件工具时，全文写入交付物，群里只回摘要与链接/附件；不得主动把一个答案规划成多条聊天消息。发送侧独立保留硬兜底：Feishu 单条 post 保守预算从 8,000 提到 16,000，使近期 8–12k 回复即使模型没有收敛也能保持一个 post；超过 16k 仍走既有 fence-aware 切分，绝不静默丢内容。

**验证**：display 测试覆盖 DM/group 独立解析、字符串整数、负值关闭与其他平台不受影响；session 测试断言 3,000 字提示、长文档转交付物规则，并证明预算变化会改变 `_ephemeral_change_key`、不会被旧 pin 吃掉；Feishu adapter 测试构造 >8k 且 <16k 的 Markdown，只允许一次 `msg_type=post` 请求。Step 8b 同时 import resolver/prompt/adapter 三层并检查外层配置与三条回归锚点。发送端不做 live 真群探测，避免验证制造外部消息。

**上游吸收判断**：上游提供可配置、按聊天 source scope 生效的生成侧 response budget，并使 Feishu 8–12k Markdown 能单条稳定投递、超大回复仍安全切分后可归档。仅提高 adapter 常量或只加 prompt 文案都不构成完整吸收。

---

### [PATCH-FEISHU-SSRF-TEST-SYSPROXY] SSRF rebind 测试对宿主系统代理 hermetic

| 字段     | 内容                           |
| -------- | ------------------------------ |
| **文件** | `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                  |

**问题**：上游 `test_download_remote_document_blocks_connect_time_rebind` 只把 6 个代理**环境变量** patch 成空串来构造"无代理直连"场景，但 httpx `trust_env` 的代理解析走 `urllib.request.getproxies()`——env 为空时在 macOS 回落到 **scutil 系统代理配置**（Windows 回落注册表）。宿主开着系统级代理（本机 Clash Verge，127.0.0.1:7897）时，请求实际经代理外发，direct-connect SSRF 守卫按设计把最终目标解析委托给代理（"proxy = trusted egress boundary"，见 `create_ssrf_safe_async_client` docstring），测试预期的 `SSRFConnectionBlocked` 永不触发，收到裸 `httpx.ConnectError`。后果：只要跑回归时 Clash 系统代理开着，规范 runner（`scripts/run_tests.sh`）必然 1 failed，升级 playbook 的 "0 failed" 完成标准无法达成。此前摩擦表把该现象误诊为"跨文件测试状态依赖、批量跑通过"——实际变量是**跑测试那一刻宿主系统代理的开关状态**，与文件组合方式无关（2026-07-29 以 probe 插件证实测试内 HERMES_HOME 隔离与 allow_private 缓存均正常，failing connect 目标为 `127.0.0.1:7897`）。

**修复**：测试的 `with` 块内在 `patch.dict(os.environ, proxy_vars)` 之后追加 `patch("httpx._utils.getproxies", return_value={})`（httpx 0.28 在 `_utils` 模块顶部 `from urllib.request import getproxies`，client 构造时经 `get_environment_proxies()` 调用），把系统代理回落一并掐断，使测试语义回到其本意（无任何代理、纯直连路径校验 connect-time rebind 拦截）。生产代码零改动；env 变量 blank 保留（防护其他读取路径）。

**验证**：Step 8b grep `tests/gateway/test_feishu.py` 存在 `httpx._utils.getproxies` 且目标测试 `test_download_remote_document_blocks_connect_time_rebind` 仍在（2026-08-07 起——仅锚 patch 串时，rebind 测试被整体删除也会误报 active）。`tests/gateway/test_feishu.py` 全量 237 passed / 0 failed（2026-07-29，Clash 系统代理**开启**状态下经规范 runner 复跑通过；修复前同条件 1 failed，且单 pytest 进程多文件组合同样失败，证伪旧"批量通过"结论）。

**上游吸收判断**：上游为该测试补上系统代理中和（patch `getproxies` / `trust_env=False` / mounts 显式置空任一等价手段）后可归档本补丁；届时同步删除摩擦表对应 row。

---

**类别：Provider、模型与多模态路由**

### [PATCH-TRUNCATED-TOOL-CALL-RECOVERY] 隐藏截断的工具参数提高预算后重试

| 字段     | 内容                                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/conversation_loop.py`, `tests/run_agent/{test_tool_call_incremental_persistence.py,test_run_agent.py}` |
| **状态** | 🟡 未上游合并；上游 `finish_reason=tool_calls` + 未闭合 JSON 分支仍立即终止                                   |

**问题**：大段文档/文件写入会把正文放进工具参数 JSON。Bedrock Converse 默认 `max_tokens=4096`，参数超过预算时有的 provider 返回 `finish_reason=length`，有的 router 却改写成 `tool_calls` 并留下未闭合 JSON。前者已有 4 次有界重试并把输出预算指数提高到 8k/16k/32k；后者在 JSON 校验处直接返回 `Response truncated due to output length limit`，既不重试，也把不可靠的 finish reason 当成确定诊断。2026-08-20 创建飞书需求文档正是此路径：前序工具结果存在，下一次大参数调用被截断，创建脚本从未执行。

**修复**：抽出 `_raise_truncated_tool_call_output_cap()` 作为两类截断的单一预算函数。显式 `length` 与 `tool_calls`+未闭合 JSON 都复用同一 8k→16k→32k 上限与 4 次计数；每次从最后完整 transcript 重跑，不追加、不持久化、更不执行半截参数。若仍耗尽，关闭悬空 tool tail，并返回“工具参数无法完整生成、动作未执行”的准确错误，不再把未知 router 行为一律说成 output length。成功执行任一完整工具批次后，既有逻辑仍重置计数，单次截断不会污染后续 turn。

**验证**：新增端到端回归构造 `finish_reason=tool_calls` + 大段未闭合 JSON，断言第一次不 dispatch、第二次请求 cap 至少 8192、完整重试只执行一次工具并正常返回；既有“先成功工具、后连续隐藏截断”测试改为提供 4 次失败，断言总共 6 次 API 调用后 tool tail 闭合且明确声明动作未执行。Step 8b 单独运行这两条测试，防止 helper 存在但分支未接线。

**上游吸收判断**：上游让所有未闭合工具参数（不依赖 finish_reason 字面值）走统一的有界重试/预算提升并保持半截调用零副作用后可归档；若 provider 层能保证真实 `length`，仍需保留 router 改写的回归测试再判断是否收缩。

---

### [PATCH-MODEL-CONFIGURED-ONLY] `/model` 只访问配置内主模型与 fallback

| 字段     | 内容                                                                                                                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `hermes_cli/model_switch.py`, `gateway/slash_commands.py`, `tests/hermes_cli/test_tools_config.py`, `tests/gateway/test_config.py`, `tests/run_agent/test_provider_fallback.py`, `tests/run_agent/test_compressor_fallback_update.py`, 外层 `config.yaml` |
| **状态** | 🟡 本地模型访问边界；`model_catalog.configured_only: true` 时启用                                                                                                                                                                                         |

**问题**：无参数 `/model` 原生调用 `list_authenticated_providers()`，展示整台机器上检测到凭据迹象的 provider 及其在线/缓存模型目录，而不是当前 profile 的配置集合。shell secrets、credential pool 或普通 `GITHUB_TOKEN` 都可能制造链外模型入口；文本 `/model <name> --provider <slug>` 还能直接切换到这些链外 provider。用户要求 Hermes 只能访问 `config.yaml` 中显式声明的主模型与 `fallback_providers`，引入新模型必须先手工改配置。Gateway 另有一层 raw-YAML 快速读取：若 fallback model 写成 `${VAR}`，列表/预校验会看到占位符，而共享切换核心看到展开后的值，导致同一合法 route 自相拒绝。

**修复**：新增 configured-only 路由表，只从 `model.default/provider` 和有序 `fallback_providers` 构造模型 universe，不扫描 ambient credentials、auth pool、models.dev 或 provider `/models`。路由表复用配置层 `${VAR}` / `${env:VAR}` 展开语义，使 Gateway raw YAML、CLI `load_config()` 和共享核心比较同一 provider/model identity。无参数 `/model` 只显示这些精确 route；Gateway 文本/交互选择和共享 `switch_model()` 核心都只允许切换到同一集合，CLI/TUI/Dashboard 等其它入口同样无法绕过。链外 provider/model 直接拒绝，严格模式强制 session-scoped，并禁止 global switch 绕过手工配置边界。主动切换不改写 fallback 列表：primary 等于 fallback-A 时跳过重复 A、保留 B；primary 等于 fallback-B 时先回退 A、随后跳过重复 B。`auxiliary.compression` 继续读取独立配置，切换 primary 只改变摘要 route 失败时的 current-main fallback，不改变 compaction 首选 route。

**验证**：configured-only helper 使用通用 primary/fallback-A/fallback-B fixture，断言列表完全由传入 config 动态生成，并覆盖 `${VAR}` / `${env:VAR}` 展开、provider-only/唯一 model 解析与链外拒绝；Gateway 边界测试证明 `/model` 显示展开后的 route、不出现任何未配置 provider，链外与 `--global` 在调用 switch 前被拒绝；共享 core 测试证明非 Gateway 调用面也受到同一 guard。fallback 回归成对覆盖“primary 等于 fallback-A 时跳过 A、使用 B”和“primary 等于 fallback-B 时先使用 A”；compressor 回归证明 primary 切换后主 runtime 更新，但独立 `summary_model` 原值保持不变。当前生产 config 的 Azure/Bedrock/Vertex 只是该动态规则的一次实例，未来替换具体 provider/model 不需要改补丁或测试。Step 8b 将上述生产锚点和测试纳入 8c 总闸门。

**上游吸收判断**：上游提供 profile-owned configured-only picker/switch policy，能同时约束展示、typed switch、global persistence，并保留 primary/fallback 去重与 compaction 独立路由语义后可归档。

---

### [PATCH-VERTEX-HIDDEN-THOUGHTS] Vertex 保留 thinking 但隐藏 thought 文本

| 字段     | 内容                                                                                     |
| -------- | ---------------------------------------------------------------------------------------- |
| **文件** | `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🟡 未上游合并                                                                            |

**问题**：官方 `provider: vertex` 通过 Vertex OpenAI-compatible endpoint 调 Gemini 3.x 时，`reasoning_effort: high` 会映射到 `extra_body.google.thinking_config.include_thoughts=true`。实测 Vertex 这条 OpenAI-compatible 路径不会把 thought 拆成 Hermes 可隐藏的 `reasoning_content` 字段，而是把 thought text 直接拼进 `message.content`，飞书端会看到类似 `**Identifying Current Model**` 的思考段，即使 `display.show_reasoning=false`。

**（2026-07-07 修订·真实根因）**：初版把 `include_thoughts` 强制改 false 后返回 `{"extra_body": {"google": {...}}}`——**多包了一层 `extra_body` 键**。基类 `ProviderProfile.build_extra_body` 的约定是"返回值会被 merge 进 extra_body"，经 `_build_kwargs_from_profile` 后线上真正发出的是 `extra_body={"extra_body": {"google": {...}}}`；Vertex 不认这个顶层 `extra_body` 字段，直接忽略 → `include_thoughts` 回落默认 true → thought 仍进正文。初版的"真链路验证"用的是**手写单层** `extra_body={'google': {...}}`（未走 `build_kwargs` 组装），因此漏掉了这层 bug。飞书主会话据此泄漏大量 `**加粗标题** + "I'm diving into…"` 思考段。

**修复**：`build_extra_body` 改为返回**单层** `{"google": {"thinking_config": thinking_config}}`（与 qwen/nous 等 profile 的扁平返回约定一致），使线上 `api_kwargs["extra_body"]` 恰为 `{"google": {"thinking_config": {"include_thoughts": False, "thinking_level": "high"}}}`——Vertex 读到顶层 `google.thinking_config`，抑制生效。保留 `thinking_level=high` 让模型继续内部思考，只是不把 thought text 返回正文。附带 hunk：插件 alias 列表补 `"vertexai"`，与上游 `runtime_provider.py` 已收录的别名对齐（此前为未登记改动，2026-08-07 归属至此）。

**当前适用性（2026-08-15）**：主力为 `azure-foundry/gpt-5.5`，标准 `vertex/google/gemini-3.5-flash` 是末级 fallback、视频旁路与 compression provider。本补丁只在 `VertexProfile` 内生效，对 Azure/Bedrock 零作用面；一旦回退双层写法，Vertex 的 thought text 会重新混入飞书可见正文，因此仍必须保留。

**验证**：Step 8b grep `plugins/model-providers/vertex/__init__.py` 存在 `include_thoughts=true` 说明、`thinking_config["include_thoughts"] = False` 与**单层** `return {"google": {"thinking_config": thinking_config}}`；测试同时保留 profile 正反例，并以 `test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `ChatCompletionsTransport.build_kwargs()`，断言最终请求 kwargs 只有单层 `extra_body.google.thinking_config`。真链路 A/B 对比（Vertex OAuth token，同一 plan 类 prompt）：**A 单层 → 干净答案**；**B 双层（旧）→ `" Too simple, doesn't add value…"` 思考泄漏**。2026-08-03 主会话复测因 Google OAuth 链路瞬时 SSL EOF 自动回退到 Qwen，但仍证明出站最终 `content` 与隐藏 `reasoning` 分离；Vertex wire request 形状由规范 runner 的边界测试持续锁定。

**注**：`plugins/model-providers/gemini/__init__.py`（AI-Studio `gemini` provider）存在同构的双层写法，但本环境不走该 provider，暂不改动，待验证。

**上游吸收判断**：若上游能把 Vertex OpenAI-compatible 返回的 Gemini thoughts 解析并存入隐藏 reasoning 字段，或官方 Vertex profile 默认隐藏 thoughts 且保留 thinking level，可归档本补丁。**隐式合约依赖**：本补丁的单层返回形状依赖基类 `ProviderProfile.build_extra_body` 的"返回值 merge 进 extra_body"约定；每轮升级必须复核该基类合约未变（`test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `build_kwargs()` 锁定最终 wire 形状，合约变化会在该测试直接暴露）。2026-08-03 对 post-26e0b1c 上游复核：插件仍是双层包裹 bug 原样，未吸收。

---

### [PATCH-VERTEX-DOCTOR] Doctor 识别官方 Vertex provider

| 字段     | 内容                                                      |
| -------- | --------------------------------------------------------- |
| **文件** | `hermes_cli/doctor.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🟡 未上游合并                                             |

**问题**：切到官方 `model.provider: vertex` 后，实际 runtime provider 已能通过 `providers.get_provider_profile("vertex")` 和 `agent.vertex_adapter` 正常拿 OAuth token 调 Vertex OpenAI-compatible endpoint，但 `hermes doctor` 仍只看 auth/catalog provider 列表，不读 model-provider plugin registry，于是误报 `model.provider 'vertex' is not a recognised provider`。同时 `google/gemini-3.1-pro-preview` 这类 Vertex 官方 OpenAI-compatible 模型名被当作 OpenRouter 风格 vendor slug，额外误报应该切 openrouter 或去掉前缀。

**（2026-08-11 补·`.env` 检查是 provider-agnostic 缺口）**：`_PROVIDER_ENV_HINTS` 是 `_has_provider_env_config()` 对 `.env` 正文做的纯子串匹配，只认清单里字面列出的键。清单此前没有当前主力的 `AZURE_FOUNDRY_API_KEY`；本机之所以没报"没有 provider auth"，只是因为 `.env` 里恰好还有一个无关的 `DASHSCOPE_API_KEY`，属于**碰巧通过**。此外清单写的是 `VERTEX_LOCATION`，而 `agent/vertex_adapter.py` 的 `_resolve_region()` 实际读 `VERTEX_REGION`。

**修复**：doctor 在校验 provider 时补充读取 `providers.get_provider_profile()`，将 plugin profile 的 canonical name 加入可接受 provider id 集合，并让 vendor-slug 策略同时考虑原始 provider、auth runtime provider、catalog provider 与 plugin canonical provider。标准 `vertex` 被加入允许 `vendor/model` 形态的 provider 集合。

`.env` 健康检查（`_PROVIDER_ENV_HINTS`）补全为**覆盖整条实际链路**而非只覆盖 Vertex：`AZURE_FOUNDRY_API_KEY`（当前主力）、`GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT_ID`、`VERTEX_REGION`（adapter 真正读的名字，`VERTEX_LOCATION` 保留兼容旧 `.env`）。这一半是**通用化而非 Vertex 专属**：主力换 provider 时按同样口径往清单里补该 provider 的 key 即可，检查逻辑本身不需要改。

**验证**：Step 8b grep `hermes_cli/doctor.py` 中存在 `_get_provider_profile`、`GOOGLE_APPLICATION_CREDENTIALS`、`"vertex"` 与 `AZURE_FOUNDRY_API_KEY`，并 grep `tests/hermes_cli/test_doctor.py` 中存在 `test_run_doctor_accepts_vertex_provider_and_google_model_slugs`（parametrize 覆盖 `vertex` / `google-vertex`）与 `test_detects_vertex_region_the_adapter_actually_reads`。实际 `hermes doctor` 必须同时识别 Azure、Bedrock 与标准 Vertex，不得再依赖已移除的 DashScope/Gemini key 偶然通过。

**上游吸收判断**：若上游 doctor 原生读取 model-provider plugin registry，或官方 registry/catalog 把 `vertex` 与其 `google/*` OpenAI-compatible 模型名纳入健康检查策略，可归档本补丁。

---

### [PATCH-DOCTOR-TEST-NETWORK-ISOLATION] Doctor 配置测试不访问真实网络

| 字段     | 内容                                 |
| -------- | ------------------------------------ |
| **文件** | `tests/hermes_cli/test_doctor.py`    |
| **状态** | 🟡 未上游合并；测试 hermeticity 补丁 |

**问题**：`tests/hermes_cli/test_doctor.py` 的多数用例只验证配置、展示或单个 provider 分支，却会完整穿过宿主命令、npm audit 和 31 路 API Connectivity。`TestDoctorStaleMaxIterationsDrift` 还误以为 Tool Availability 阶段的 `SystemExit` 能短路网络，但该 section 实际更晚；同一 pytest 进程里由 `.env`、用户凭据或前序用例留下的 provider 状态因此触发真实 HTTP/SDK 探测。2026-08-16 升级到 `8ad055414` 后，规范 runner 首轮在 300 秒预算耗尽被杀，重试仍耗时 121 秒才通过，形成“0 failed 但有 flaky file”的不可接受终态。

**修复**：新增 file-local autouse fixture，为未显式 mock 的 `subprocess.run` / `httpx.get` 提供立即返回的中性结果，并默认关闭 ambient OpenRouter、Anthropic、Bedrock 探测；专门测试网络/gh/subprocess 行为的用例在 fixture 之后安装自己的 fake，仍走原断言。`TestDoctorStaleMaxIterationsDrift` 再额外清空 provider cache，保证写入的 fake `.env` 不会扩大 probe 列表。生产 doctor 零改动，所有真实分支顺序和配置解析保持。

**验证**：`test_drift_check_does_not_run_connectivity_probes` 把 `httpx.get` 改成调用即失败；规范 runner 中全文件 **57 passed / 13.7s**（修复前 121s，首轮曾 >300s），且专门的 Kimi/DashScope/OAuth/gh mock 用例继续通过。规范 runner 必须连续完成该文件且不出现 per-file kill / retry / FLAKY 标记。Step 8b 同时锚定 autouse fixture、负例测试名、provider cache 清空和禁止 HTTP 的断言文本，任一丢失都阻断 bundle 刷新。

**上游吸收判断**：上游为 doctor 单测提供等价的 file-wide hermetic fixture，或为 `run_doctor` 提供 section-scoped no-network/no-system-I/O 入口，并保留网络调用即失败的反例后可归档；仅提高 per-file 超时或依赖重试不算吸收。

---

### [PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY] Gemini fallback 接受跨模型工具历史

| 字段     | 内容                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------ |
| **文件** | `agent/transports/chat_completions.py`, `tests/agent/transports/test_chat_completions.py`        |
| **状态** | 🟡 未上游合并；独立于已归档的 `PATCH-GEMINI-THOUGHT-SIGNATURE`（保留已有签名 vs 补齐无签名历史） |

**问题**：Gemini 3 thinking 模型要求 replay 的每个 `functionCall` 携带 `thought_signature`。上游已能保留 Gemini 自己返回的真实签名，但当会话先由 Azure GPT-5.5 或 Bedrock Claude Opus 5 执行过工具、随后 fallback 到标准 `vertex/google/gemini-3.5-flash` 时，历史 tool call 天然没有 Gemini metadata。2026-08-14 的原始复现发生在旧 `vertex-fallback` 路径；provider 收敛后，同一跨模型历史不变量仍然成立。

**修复**：在 `ChatCompletionsTransport.convert_messages()` 的 Gemini-family 出站分支中，对缺少嵌套 `extra_content.google.thought_signature` 的历史 tool call 使用 copy-on-write 注入 Google 官方兼容哨兵 `skip_thought_signature_validator`；如果旧 adapter 留下直接位于 `extra_content.thought_signature` 的真实签名，则把原值规范化到 Google wire shape，不用哨兵覆盖。Gemini 已有真实签名保持原样，原始会话历史不被修改；非 Gemini 目标仍按上游既有逻辑剥离 `extra_content`，避免严格 OpenAI-compatible provider 拒绝未知字段。

**验证**：`tests/agent/transports/test_chat_completions.py` 通过真实 `build_kwargs()` 边界构造 Azure/Codex 风格的 `skill_view` tool call（含 `call_id` / `response_item_id`、无 Gemini metadata），断言最终 provider request 删除 Codex 私有字段并注入嵌套兼容签名，同时原 history 不变；另覆盖已有真实签名 identity-preserve 与 legacy direct signature 规范化。Step 8b 直接 import `ChatCompletionsTransport` 并执行无签名历史转换，不依赖私有 helper 名；补丁测试必须由 `scripts/run_tests.sh` 运行。

**上游吸收判断**：当上游 Chat Completions transport（或通用 provider-switch history adapter）原生在切换到 Gemini/Gemma 时，为所有无签名历史 function call 补充官方 skip-validator 哨兵，同时保持真实签名、非 Gemini 严格字段清理和 copy-on-write 不变量，并有跨 provider 回归测试后，可删除本地 hunk、Step 8b gate 和两个受管文件并将本块移入 Archive。仅有 `ToolCall.extra_content` 保留能力不算吸收。

### [PATCH-IMAGE-NATIVE-ROUTING] 主力模型图片能力识别与原生路由

| 字段     | 内容                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `agent/models_dev.py`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py` |
| **状态** | 🟡 未上游合并                                                                                                                             |

**问题**：`image_input_mode:auto` 只在能力**确认为 True** 时走 native，其余一律 `return "text"`（`image_routing.py` 决策尾部），退回 auxiliary `vision_analyze` 文本预分析。三个不同来源都会让能力"未知"：

- **Vertex**：OpenAI-compatible endpoint 没有可靠 `/models` discovery，模型目录也可能尚未收录 Gemini 3.x preview slug；Vertex-only 安装还没有辅助 vision 凭据，退化后直接失败。
- **azure-foundry**：`PROVIDER_TO_MODELS_DEV` 缺少该 provider 条目（2026-08-11 定位），`_get_provider_models()` 返回 None → `get_model_capabilities()` 返回 None → **该 provider 下所有模型的全部能力都查不到**（vision/tools/reasoning/limit）。gpt-5.5 因此被判 `image=text`，尽管目录里 `azure.gpt-5.5` 明确是 `modalities.input: [text, image, pdf]`、且实测 Responses API + `input_image` 原生读图正常（5.78s 正确识别）。后果不是失败而是静默绕路：同一模型被调两次（先 `vision_analyze` 生成描述、再拿二手描述回答），细节（小字、坐标、渐变）在中转丢失。
- **Bedrock Claude**：inference-profile ARN 把真实模型 ID 放在最后一个 `/` 后（如 `global.anthropic.claude-opus-5`），无法映射到 models.dev。Claude Opus 5 官方模型卡明确支持 Image、不支持 Video，本机又以合成红蓝图穿过实际 Bedrock wire 在 2.3s 返回正确结果；但能力未知使 Gateway 先用同一 Opus 做一次文本预分析，主 turn 又再次调用 `vision_analyze`，造成重复读图与长延迟。

**修复**：两个能力来源、一个不变量（主力模型能读图就必须原生读）：

- 窄口径 `_known_provider_model_supports_vision(provider, model)`：标准 Vertex Gemini 3.x，以及 Bedrock Claude 3+ Haiku/Sonnet/Opus 的 foundation ID、geo/global ID 与可解析 inference-profile ARN 返回 `True`；Claude v2、Nova Micro、opaque application-profile 名继续未知/fail-closed。显式 `supports_vision: false` 仍优先覆盖。
- `PROVIDER_TO_MODELS_DEV` 新增 `"azure-foundry": "azure"`。选 `azure` 而非 `azure-cognitive-services`：前者是后者的严格超集（+14 模型 / -0，gpt-5.x 覆盖一致）。这是**接目录**而非加白名单——一次修复该 provider 全部 82 个模型的 vision/tools/reasoning/limit，且随上游目录自动更新，不需要为每个新模型维护本地清单。上下文长度另有独立静态表（`model_metadata.py` 已含 `gpt-5.5: 1050000`），不受此缺口影响。

**验证**：Step 8b 锁定 known-provider helper、标准 `"vertex"`、Gemini 3.5 Flash slug、Bedrock Opus inference-profile 与 Gateway 真实边界测试、`"azure-foundry": "azure"` 映射及 Azure catalog 测试。`test_fallback_chain_models_all_route_images_natively` 证明当前 Azure GPT-5.5 → Bedrock Opus 5 → Vertex Gemini 3.5 Flash 三档图片全部 native；反例证明 Claude v2、opaque profile 与 Nova Micro 不被误开。

**上游吸收判断**：三个单元共享"auto 模式下主力模型图片能力识别"这一责任边界与同一 Step 8b gate，必须一起回滚验收。上游 capability catalog/provider profile 同时稳定声明 Vertex Gemini 3.x、azure-foundry 和 Bedrock inference-profile Claude 3+ 图片能力后可归档；只吸收部分 provider 则相应收缩本块。

---

### [PATCH-VERTEX-VIDEO-ROUTING] Gemini 视频原生路由

| 字段     | 内容                                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `agent/image_routing.py`, `gateway/run.py`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py` |
| **状态** | 🟡 未上游合并；依赖 `PATCH-IMAGE-NATIVE-ROUTING` 的 Vertex/Gemini 识别                                                               |

**问题**：上游视频只注入本地 path note，期望模型自行用 ffprobe/ffmpeg；群聊没有 terminal，因而即使附件已缓存也看不到视频内容。图片能力不能直接等同视频能力，且视频没有缩图重试，必须使用更窄的白名单和大小边界。

**修复**：新增 `decide_video_input_mode`、独立 Vertex+Gemini 3.x 视频白名单、magic-byte/MIME 校验和 14 MB 内联上限。支持的视频转换为 `data:video/*;base64` content part；gateway 用 session buffer 把 native video paths 传给 content builder，超限/不支持视频继续交给 `PATCH-MULTIMODAL-SIDECAR`，若仍失败则给 path-free `FAILED` 状态。无需给群聊放开任何命令工具。**2026-08-07 审计修复两处接线缺陷**：① gateway wrapper `_decide_image_input_mode` 曾把 `kind=kind` 直传给不接受该参数的 `decide_image_input_mode`（本地=上游签名均无 `kind`），TypeError 被 fail-open except 吞掉后**所有**网关图片/视频路由静默退化为 `"text"`——视频补丁在生产路径完全失效、图片路由连带破坏（上游 `test_pre_turn_named_custom_provider_identity_selects_vision_override` 在 worktree 上 1 failed，该文件当时不在补丁测试清单故 815/0 未暴露）；现 wrapper 内按 kind 分流，`kind=="video"` 直连 `decide_video_input_mode`（无网络 I/O，同时消除 async handler 内的同步阻塞隐患），图片路径恢复上游原签名调用。② 视频 buffer 补齐与图片路径对称的**每轮重置**（`_consume_pending_native_video_paths(session_key)`），杜绝被中止 turn 的视频泄漏进同会话下一轮。

**验证**：Step 8b 单独检查 video decision、native-video session buffer、**gateway 接线**（`return decide_video_input_mode(` 与 per-turn consume 锚点，2026-08-07 起——此前四个锚点全部只锚定义与测试名，功能整体失效时 gate 仍报 active）和 data-URL 回归；`test_gateway_kind_video_routes_through_video_decision_table` 从 runner 边界证明 kind="video" 真正抵达视频决策表（vertex+gemini-3 → native、非白名单 → text）；`test_prepare_resets_stale_video_buffer_per_turn` 穿过真实 `_prepare_inbound_message_text` 证明陈旧视频 buffer 与图片 buffer 一同被每轮重置；测试另覆盖 Vertex primary/fallback、非视频模型、显式配置、MIME/大小守卫和实际 content parts。

**上游吸收判断**：上游提供通用 native video routing、明确的视频 capability 和等价 MIME/size safety 后可归档。

---

### [PATCH-MULTIMODAL-SIDECAR] 主力模型读不了媒体时的旁路读取

| 字段     | 内容                                                                                                                                                                                                                                                |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `gateway/run.py`, `tools/vision_tools.py`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py`, `tests/gateway/test_telegram_audio_vs_voice.py`, `tests/tools/test_video_analyze.py` |
| **状态** | 🟡 未上游合并；主模型 native 优先，本补丁为图片/音频/视频/PDF 的有界旁路                                                                                                                                                                            |

**问题**：原 sidecar 只覆盖视频。普通音频附件只留下文件路径，语音 STT 失败后也没有媒体理解兜底；扫描 PDF/空文本 PDF 本地抽取失败后只能让 agent 再调工具；未知/文本型图片主模型还可能让 `vision_analyze:auto` 重新选择当前模型，重复分析。Google 官方 Gemini 3.5 Flash 模型卡实际支持 Text、Image、Audio、Video，并原生接受 `application/pdf`/`text/plain`；当前 Vertex OpenAI-compatible wire 已用合成 440Hz WAV（2.7s）和 ORCHID-42 PDF（3.8s）真调用验证 `image_url` + 对应 `data:` MIME 可用。初版泛化后仍把成功 sidecar 的 cache path 与具体 model ID/ARN写进主 turn，并在超限、不支持 MIME、reader 空结果时回落到“让模型自行打开绝对路径”；群聊沙箱正确拒绝该路径，却让用户看到“无法读取原文件”，也多耗一次工具调用。native content part 同样把本地路径作为文本 hint 暴露，即使媒体字节已经在相邻 data URL 中。

**修复**：把 picker/执行器泛化为 `pick_multimodal_sidecar_route(cfg, kind)` 与 `_enrich_message_with_multimodal_sidecar(..., kind=...)`，按 `get_fallback_chain()` 顺序为 image/audio/video/document 选择真实具备该模态的 route。主模型已确认 native 时不绕路；图片 text 档、普通音频附件、语音 STT 全失败、非 native 视频，以及 PDF/text 本地抽取为空或 coverage 发现扫描缺口时，才发送**单个媒体字节 + 本轮 caption/引用上下文**。Gemini Flash 支持的 inline MIME 统一使用 `image_url` + `data:<mime>;base64`；14 MB raw 上限与文件读安全守卫保持 fail-closed。native text part 改用 `[Image/Video attachment N included]` 序号，sidecar 成功只说“configured capable route 已读取”，不外显路径、provider/model/ARN；可信抽取、STT、vision 与所有 reader 失败也统一走 `_attachment_failure_note`，给 `FAILED + 分类原因 + 不得声称读过 + 请求重发`，不再提供群聊不可达的工具路径。文本与可提取文档继续本地处理，不无条件外发；DOCX/XLSX/PPTX 等模型卡未列的 MIME 不进入 sidecar。

关键取舍——**旁路而非切 provider**：整轮切到 Vertex 会重放全量 transcript，并可能跨 issuer 携带不可重放的 reasoning 载荷。sidecar 只发一次独立请求，主模型身份、工具、历史和 fallback 状态不变；输出以纯文本进入主会话。上下文统一上限 4,000 字；图片 120s、音频/PDF 180s、视频 420s。语音优先本地 STT，只有全失败才旁路，避免重复计费和双份转写。

附带修复（同一责任边界，故并入本补丁）：`video_analyze_tool` 原先只发 `video_url` content part，而 Vertex OpenAI-compat 端点直接 400 `Unrecognized 'type' field in an object element of an array 'content' field; found: 'video_url'`——agent 自己调 `video_analyze` 在 Vertex 上是**硬失败**。改为捕获该错误后以 `image_url` + `data:video/*;base64` 形状重试一次（Vertex 对所有内联媒体都用这个形状）。不做 per-provider 硬表：DashScope/Qwen-VL 确实要 `video_url`，只有 provider 明确拒绝时才换形状。

**验证**：Step 8b 锁定通用 picker、audio/document 能力、data URL 构造、四类生产接线、上下文上界、视频形状兼容重试、path-free content labels 与端到端测试。Gateway 回归分别穿过真实 `_prepare_inbound_message_text` 证明：视频→configured capable route、普通 WAV→capable route 且不进 STT、扫描 PDF 本地空结果→document route、混合 PDF 文本保留并补视觉读取；均断言 `data:video/audio/application-pdf` wire、无全 transcript、成功 prompt 不含原路径/具体 ARN。无能力 route、超限/不支持 MIME 与全部 reader 失败断言明确 `FAILED` 且不含路径；本地 STT 成功保持不旁路。Feishu group consumer 矩阵同样断言图片 native、音视频 sidecar、七类文档提取结果均 path-free。

**上游吸收判断**：若上游提供"能力不足时按 modality/capability 自动选辅助后端"的通用机制，覆盖图片、音频、视频与 PDF/text 文件，且保证 bounded current-turn context、native-first、无 transcript replay、无重复分析、path-free 成功提示和显式失败状态，可归档通用 picker/sidecar；provider profile 原生提供媒体 part 形状协商时可单独收缩兼容 hunk。picker 仍依赖 `get_fallback_chain()` 的 list[dict] 契约。

---

**类别：历史保留、审批与本地运行兼容**

### [PATCH-HISTORY-RETENTION] 平台级回放历史保留窗

| 字段     | 内容                                                                                                                                                                                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/replay_cleanup.py`, `gateway/run.py`, `tests/agent/test_replay_cleanup.py`, `tests/gateway/test_stale_confirmation_expiry.py`（配置键 `gateway.history_retention` 在 `~/.hermes/config.yaml`，非 PATCHED_FILES） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                           |

**问题**：（2026-07-14 复盘 SpaceSight Tech Sharing Group 历史污染）共享群 session 每轮把**全量** transcript 回放给模型（`load_transcript` → `_build_gateway_agent_history`），唯一的历史收敛机制是按 token 触发的 hygiene/压缩——大上下文模型（Gemini 3.1 Pro）上 94 条消息远够不到 85% 阈值，从不触发；且压缩是摘要不是丢弃。结果是 7 月 10 日 随消息入库的一次性 `[Feishu assistant mode]` 指令块 + 模型照做的范例，在 7 月 14 日 第三方 @bot（零注入分支）轮次里仍然整段可见，模型据此模式补全出「我是琛哥的赛博小助手…琛哥可能在忙」的代答口吻。缺一个与 token 无关的、按**墙钟时间和条数**的回放上界。

**修复**：`agent/replay_cleanup.py` 新增 `apply_history_retention(history, now, max_age_seconds, max_messages)`（sentinel `history-retention`）：视图级过滤——state.db 完整保留（审计 / `/resume` / 搜索不受影响），只裁剪发给模型的回放。语义：切点只落在**轮边界**（普通 user 行，`_retention_turn_starts`），绝不切断 assistant(tool_calls)→tool 配对；时间窗按整轮的开头 user 行 `timestamp` 判断，无时间戳的行视为"新"（兼容旧转录与内存脚手架，防止配置误伤成批丢历史）；条数上限向轮边界**向上取整**；最新一轮无论多旧/多长永远保留；两个限制同时配置取更严格的切点；无 user 行的退化历史原样返回。`gateway/run.py` 新增 `_history_retention_limits_for_source()`：从 `gateway.history_retention.<platform-key>` 读取限额，platform-key 复用工具/skill 配置同款 chat-scope 拆分（飞书群=`feishu_group`、私聊=`feishu`），未配置或值非法一律 fail-open 返回 None。注入点在 `_run_agent_inner` 的 cached-agent 守卫（`_select_cached_agent_history`）**之后**，单点同时覆盖「盘上转录」与「内存活转录」两条路径。本机 `config.yaml` 配置 `feishu_group: {max_age_seconds: 21600, max_messages: 30}`（6 小时 / 30 条），私聊与 CLI 不配置、行为不变。

**验证**：Step 8b grep `agent/replay_cleanup.py` 中存在 `def apply_history_retention`、`def _retention_turn_starts`，grep `gateway/run.py` 中存在 `_history_retention_limits_for_source`、`_apply_history_retention`，并 grep `tests/agent/test_replay_cleanup.py` 中的 `test_retention_never_splits_tool_call_blocks`、`test_retention_newest_turn_always_kept_even_if_too_old` 与 `tests/gateway/test_stale_confirmation_expiry.py` 中的 `test_retention_feishu_dm_not_covered_by_group_key`。定向测试覆盖：时间窗丢整轮、条数向轮边界取整、tool-call 块不被切断、最新一轮超龄/超量仍保留、无时间戳视为新、时间 + 条数组合取更严、未配置/畸形配置 fail-open、DM 不受群键影响（`test_replay_cleanup.py` 21 passed + `test_stale_confirmation_expiry.py` 15 passed；周边 `test_session.py` 167 passed + `test_feishu.py` 237 passed）。

**上游吸收判断**：若上游为 gateway 回放历史提供原生的时间窗/条数保留配置（或给共享群 session 引入等价的 per-platform replay 上界机制），可归档本补丁。

---

### [PATCH-APPROVAL-DARWIN-TMP] Darwin verify-artifact 临时路径归一化

| 字段     | 内容                                                                                                                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `tools/approval.py`（仅 `_is_verification_artifact_cleanup` 的 `allowed_spellings` hunk）, `tests/tools/test_approval.py`（仅 `test_darwin_private_alias_accepts_raw_temp_spelling`）——两文件的其余 hunk 属 `PATCH-FEISHU-GROUP-APPROVAL` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                             |

**问题**：上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 给 verify/ad-hoc 临时脚本的 `rm -f` 清理开豁免（不走审批），但实现只对 `tempfile.gettempdir()` 做 `realpath` 而不动 operand：Darwin 上 temp 路径全在 `/private` 别名后（`/tmp` → `/private/tmp`、`/var/folders/…` → `/private/var/folders/…`），运行时用 `gettempdir()` 原样拼出的清理命令**永远匹配不上**，豁免恒不生效、清理仍走审批（行为等同该修复落地前）；上游自带测试 `test_nonrecursive_verification_artifact_cleanup_is_not_dangerous` 在 macOS 恒失败（Linux CI 上 raw==canonical 测不出来）。同时上游另一测试 `test_symlinked_temp_dir_only_exempts_canonical_target` 锁定「一般 symlink temp 目录只豁免 canonical 拼写」，简单放开 raw 拼写会破坏该 fail-closed 语义。

**修复**：`_is_verification_artifact_cleanup` 中 operand 的合法拼写从「仅 canonical」扩展为 `allowed_spellings` 列表：canonical 拼写恒可；**仅当** `realpath(gettempdir()) == "/private" + gettempdir()`（即 Darwin 的 `/private` 系统别名，逐字符前缀判定）时才追加 raw 拼写。其余 symlink 场景（用户自建链接等）不放行，保持 fail-closed；后续的 operand realpath 包含性检查与 `hermes-(verify|ad-hoc)-` basename 正则不变。Linux 上 `realpath == raw`，条件不触发，行为与上游逐字节等价。

**验证**：Step 8b grep `tools/approval.py` 中存在 `f"/private{raw_temp_dir}"`、`allowed_spellings`，grep `tests/tools/test_approval.py` 中存在 `test_darwin_private_alias_accepts_raw_temp_spelling`。新增回归测试 `test_darwin_private_alias_accepts_raw_temp_spelling`（mock gettempdir + realpath 模拟 `/private` 别名，平台无关）：raw 与 canonical 拼写均豁免、`nested/..` 变体仍判危险；上游三件套全部转绿——`test_nonrecursive_verification_artifact_cleanup_is_not_dangerous`（macOS 上由恒败转过）、`test_symlinked_temp_dir_only_exempts_canonical_target`（fail-closed 语义保持）、`test_verification_cleanup_exemption_rejects_broader_deletions`（13 个越界变体全拒）。`tests/tools/test_approval.py` 全量 **316 passed / 0 failed**（2026-07-29；修复前 312 passed / 1 failed）。

**上游吸收判断**：上游对比较两侧统一 realpath（或等价归一化）并使其自带测试在 Darwin 通过后，可归档本补丁；届时同步删除摩擦表中 `test_approval.py` realpath row。

---

### [PATCH-FTS5-CJK-DARWIN] CJK FTS 扩展 Darwin 构建与加载

| 字段     | 内容                       |
| -------- | -------------------------- |
| **文件** | `native/fts5_cjk/build.sh` |
| **状态** | 🟡 未上游合并              |

**问题**：上游 fts5_cjk 扩展（PR #65544，中文/CJK 二元分词索引，修 1-2 字中文词在会话搜索里退化为 LIKE 全表扫）的 `build.sh` 是 Linux 写法，Darwin 上两连败：① 裸 `gcc -shared` 链接被 ld 拒绝（SQLite loadable extension 的 `sqlite3_*` 符号应由宿主进程在加载时提供，macOS 需显式 `-undefined dynamic_lookup`）；② 即使加了 dynamic_lookup，Apple SDK 的 `sqlite3ext.h` 宏映射不全，7 个 `sqlite3_*` 调用（step/prepare_v2/bind_pointer/finalize/malloc/free/mprintf）落成直连符号——而 uv-managed CPython 的 SQLite 是静态编入且**不导出**任何 `sqlite3_*` 符号，直连符号绑空指针，`load_extension` 时**段错误**。

**修复**：`build.sh` 增加 Darwin 分支：强制使用 vendored amalgamation 头（`-Ivendor`，使全部调用走 extension API 指针，`nm -u` 验证 0 个未定义 `sqlite3_*`）+ `-undefined dynamic_lookup` 链接。Linux 路径原逻辑不变。构建产物 `~/.hermes/lib/libfts5_cjk.so` 在仓库外，升级不受影响；仅上游改动 `fts5_cjk.c` 时需重跑 build.sh。

**验证**：Step 8b grep `build.sh` 锚定 **Darwin 分支本体**——`uname -s.*Darwin`、`LDFLAGS_EXTRA="-undefined dynamic_lookup"`、强制 `CFLAGS_EXTRA="-Ivendor"` 与链接行消费 `$LDFLAGS_EXTRA`（2026-08-07 修复：旧锚点 `Ivendor` 在裸上游的 Linux fallback 中同样存在、无判别力，丢失 Darwin 强制 vendored 头的部分回贴会通过旧 gate 并产出加载即段错误的扩展），并提示 `~/.hermes/lib/libfts5_cjk.so` 是否已构建。端到端（2026-07-25）：`load_fts5_cjk_extension()` 返回 True；`:memory:` 建 `tokenize='cjk_unicode61'` FTS5 表后二字中文词 `项目` 索引命中；`hermes sessions optimize-storage` 回填生产索引。

**上游吸收判断**：上游给 build.sh 加 Darwin 分支（或改用统一走 api 指针的构建方式）后，可归档本补丁。

---

**类别：外层插件与群聊能力边界**

### [PATCH-FEISHU-GROUP-SANDBOX] 群聊结构化 tmp 与固定文档动作边界

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | 配置仓库：`config.yaml`, `plugins/sandbox/{__init__.py,config.yaml,plugin.yaml,test_sandbox.py,verify.sh}`, `my-skills/productivity/{hypertex-mcp/SKILL.md,feishu-docs/{SKILL.md,scripts/create_new_doc_from_md.py,scripts/download_feishu_file.py,scripts/feishu_common.py,scripts/read_docx_to_markdown.py,scripts/read_feishu_url.py}}`, `memories/MEMORY.md`, `hermes-update.sh`, `hermes-update.md`, `README.md`（均不属于内层 `PATCHED_FILES`） |
| **状态** | 🟢 配置仓库用户插件补丁；升级保留，Step 8e 强制回归                                                                                                                                                                                                                                                                                                                                                                                                   |

**依赖**：`PATCH-FEISHU-GROUP-SCOPE` 提供 `feishu_group` namespace，并保证真实 Gateway consumer 使用该 key；`PATCH-PLATFORM-CAPABILITY-SCOPE` 提供只读工具集，`PATCH-FEISHU-GROUP-APPROVAL` 提供审批层纵深防线。依赖缺失时 Step 8b/8e 分别失败，不允许把插件显示为健康。

**问题**：旧版 sandbox 给 Feishu 群聊保留通用 `terminal`，再用命令字符串、脚本目录和下载目录 allowlist 约束用途。这个边界仍暴露 shell 解析面，无法从能力模型上禁止群成员创建脚本后执行，也无法限制被信任脚本及其子进程写入整个用户目录；`tmp` / `cache` 的用途和不同群之间的文件隔离也不明确。另一方面，群聊确实需要创建、追加、重建、删除和读取飞书文档，并需要一个可读写的临时数据区。主 Feishu DM 则必须继续获得默认完整工具面，危险命令走 owner 人工审批，不能被群聊策略误伤。

2026-08-16 全面审计又发现四个纵深缺口：① `clarify` 已在 `feishu_group` toolset 中却不在 hook allowlist，真实调用被误拦；② group hook 先检查 outsider-DM 基础 allowlist，导致群聊理论上可继承 `vision_analyze` / `image_generate`，与入站多模态链路分工不符；③ `feishu_doc_read` / `read_url` / `download_file` 可消费任意格式正确的 token/URL，文档 delete 没有可信 user 约束，形成 bot 凭据 confused-deputy 风险；④ `web_extract` 长页把全文写到全局 `cache/web` 后提示 `read_file` 分页，但群文件根正确阻断该路径，造成“短页可用、长页中段不可达”。

**修复**：从 `platform_toolsets.feishu_group` 删除 `terminal`，新增用户插件 toolset `sandbox_group`，仅暴露两个结构化入口：`group_cache` 在 `~/.hermes/tmp/group-workspaces/<chat-id-hash>/` 内执行文本文件 CRUD；`feishu_doc_manage` 将 `create/append/rebuild/delete/read_url/download_file` 六个 action 映射到管理员预装的固定脚本文件。模型不能提交 shell、脚本路径或原始 argv，工作区文件永远只作数据。工作区路径按群哈希隔离且校验相对路径、realpath 和 symlink containment；根目录权限为 `0700`；工具响应只返回相对路径和 `workspace_id`，不向群聊暴露宿主绝对路径。`tool_search` / `tool_describe` 作为只读工具目录桥在群聊显式放行，使 deferred 的 `group_cache` / `feishu_doc_manage` 能被发现和描述；`tool_call` 在 agent 执行器中先按当前 `feishu_group` toolset 解包为底层工具，再由 sandbox hook 看到真实工具名。脚本以 argv + `shell=False` 执行，macOS `sandbox-exec` profile 由插件生成并由整个子进程树继承：允许读取/执行/联网，但只允许写当前群工作区；OS 进程沙箱不可用或配置加载失败时 fail closed。群聊下载限制为单文件 50 MB，`TMPDIR` 和原子更新备份都重定向到当前群工作区；stdout/stderr 回传前统一脱敏 Bearer token、Feishu app secret 与 tenant token，上传失败也切断会暴露 curl Authorization argv 的异常链。wiki 仅可直接读取 `~/.hermes/wiki`；`skills` / `my-skills` 只能经 `skills_readonly` 查看 allowlist 中的 `llm-wiki` 与 `feishu-docs`，不能直接写。`known_plugin_toolsets` 把 `sandbox_group` 标记为已知但只在 `feishu_group` 显式启用；普通 `feishu` 不配置平台覆盖，owner chat 又在 `pre_tool_call` 最前面无条件放行，因此主私聊保留 terminal、文件读写、代码执行、skill 管理、浏览器和 cron 等完整默认工具面。`tmp` 不整目录删除，因为 `scripts/nightly_greeting.py` 仍使用 `tmp/nightly_report`；群聊统一使用上述 tmp 子树，不改用 cache。

**2026-08-18 owner DM HyperTeX 收紧；2026-08-19 群聊内测开放**：owner DM 的 `hypertex_create_case` / `hypertex_iterate_case` 固定 `hermes` Contributor、new case 的 `deck` 类型与当前 Feishu turn 附件；`agent` 不再由 Hermes 强制注入——create 省略后按 `hermes` 账号 Agentic 权重抽取，iterate 省略后沿用 case 已记录的 Agent，模型即使显式传入也会被 sandbox 删除。HyperTeX 原始工具面为 list/create/iterate/get_case，状态控制使用 MCP Tasks 协商生成的 `tasks_get/update/cancel`；每个入站 turn 最多一次 HyperTeX 调用。2026-08-19 将 `hypertex` MCP toolset 显式加入 `feishu_group` 供内测，但 hook 对全部 7 个工具再要求当前 `chat_id` 命中 `trusted_feishu_chat_ids_for_group_hypertex`、当前 `user_id` 命中 `trusted_feishu_user_ids_for_group_hypertex`，并复用同一 contributor/type、附件暂存和单调用边界；未开通群或未授权成员均 fail closed，避免读取或修改共享 `hermes` case。首批开通财务专享 AI 小助手、Data Pipeline Workshop、AI 解放生产力三个群。同日按用户明确授权，群文档 delete 与 HyperTeX 两套授信从仅周琛扩为周琛、孙可天、张文华、李冰洁四人；每人同时登记 Feishu `open_id` 与短 `user_id`。这套执行授信与 `feishu.assistant_user_ids` 解耦，后者仍只含周琛两种 ID，避免“新增 MCP/delete 维护者”意外扩大群聊 @人触发 Hermes 的 admission 面。

08-19 按用户明确边界将群文档动作拆开：create、append、rebuild 对群成员开放；append/rebuild 仍要求目标文档在当前消息或显式引用中出现；delete 同时要求目标引用和当前 `user_id` 位于 `trusted_feishu_user_ids_for_group_mutations`。群聊仍先应用独立 allowlist（明确包含 `clarify` / web / 只读知识 / 结构化工具），不继承 outsider-DM 的 vision/image 工具；图片、音频、视频和扫描 PDF 统一由 Gateway 入站 native/sidecar 处理。`pre_gateway_dispatch` 仅从当前 `event.text` 与显式 `reply_to_text` 收集飞书 URL/token，历史 `channel_context` 不授予权限；群文档读取/下载也必须命中该 provenance。相同判定在 hook 与 `feishu_doc_manage` handler 双层执行。`search_files` 缺省 `path="."` 安全重写为 wiki 根。`post_tool_call` 只解析本群 `web_extract` 的结构化结果，将本轮精确 `cache/web/<file>` 临时授权给该群，最多 5 个、新消息立即撤销、其他 cache/群均不可读。

**2026-08-20 Markdown 引用 provenance 修复**：Data Pipeline Workshop 真机复现可信维护者 `user_id=5397e1a2` 回复一条由 Hermes 发出的文档链接并要求删除；adapter/Gateway 的 `reply_to_text` 合法地将链接表示成 `[URL](URL)`，旧 sandbox 裸 URL 正则却跨过 Markdown `](`，把两段链接拼成无效 `URL](URL`，因此 doc token 未进入当前 turn 授权集。修复让 URL 扫描在 `]` 前终止并继续由 canonicalizer 去掉尾随 `)`，同一 Markdown link 的 label/target 都能独立产出 URL + token；裸 URL 行为不变。trust failure 与 target-not-referenced failure 改为独立配置文案，并记录 `untrusted_actor` / `target_not_referenced` reason，避免模型再把 provenance 故障误报为“用户不可信”。该修复不放宽授权来源：仍只读取当前 `text` / 显式 `reply_to_text`，`channel_context` 和历史链接继续无权。

`read_url` 依赖链另有一处解释器耦合：`read_feishu_url.py` 只借用 `read_docx_to_markdown.py` 的纯渲染函数 `parse_blocks`，但后者在模块顶层 `import requests`，因此任何缺 `requests` 的解释器执行该链都会整条失败（现场表现为 `ModuleNotFoundError: No module named 'requests'`，可追至 2026-05-18，与 v0.19.0 升级无关）。根因是 `SKILL.md` 长期把 `uv run --with requests python` 作为这些脚本的规范调用方式：`~/.hermes` 下没有 `pyproject.toml` / `.venv` / `.python-version`，`uv run python` 会自行拉起一个与 hermes venv 无关的临时解释器（实测 uv 0.11.32 选到 CPython 3.13.14），其中并无 `requests`，只有 `--with requests` 才被临时注入；venv 解释器本身是 3.12.13 且 `requests==2.33.0` 为 pin 死的直接依赖。因此凡是漏掉 `--with requests`（如原 `SKILL.md:188` 的裸 `python ... append_md_to_doc.py`），或该链上任何模块在顶层 import requests 时，都会退化成 `ModuleNotFoundError`。`__pycache__` 中并存 `cpython-313` / `cpython-314` 字节码正是这些非 venv 解释器执行过的物证。配套修正 `SKILL.md`：`188` 行改为 venv 绝对路径，`232` 行依赖说明改为「首选 `~/.hermes/hermes-agent/venv/bin/python`（已 pin `requests`，无需 `--with`）」并写明裸 `uv run python` 为何不可用。修复把 `import requests` 下移进 `get_tenant_access_token()` 与 `download_doc_to_md()` 两个真正联网的函数，使纯渲染路径回到 stdlib-only；同时 `_handle_feishu_doc_manage` 的 start/end 日志补记 `python=<解释器路径>`，让后续同类故障可从 `agent.log` 直接判定实际解释器。

**验证**：`plugins/sandbox/verify.sh` 作为 `hermes-update.sh` Step 8e 的硬门槛：结构化解析根/插件 YAML，确认群策略保持 `open + require_mention`、审批为 `manual`、launchd 未启用 YOLO、owner Feishu 无 `platform_toolsets.feishu` 收窄、群聊 toolset/delete 授信用户/HyperTeX 群与用户双 allowlist/固定脚本及原始工具集合均精确；真实解析 owner/group toolset，断言群聊不含 vision/image/terminal/write surface。除 search/describe 外，verifier 穿过真实 `handle_function_call("tool_call" → underlying)`，证明 bridge scope、底层 hook 和 handler：普通成员的 create/append/rebuild 在满足目标引用规则时可过，非可信 delete 在 handler 前被拦；可信 delete 使用真实 Gateway `[URL](URL)` reply 形状，经 `pre_gateway_dispatch` 生成 provenance 后穿过 deferred bridge 与 handler，trusted script 由 fake runner 代替，验证零外部删除。terminal scope 继续被拦。owner HyperTeX 另覆盖创建参数/附件固定、同轮查询拦截、新 turn `tasks_get` 原样参数；群聊 HyperTeX 覆盖“开通群 + 可信用户”正例、“开通群 + 非可信用户”和“未开通群 + 可信用户”两个反例。插件 **42 条**回归还覆盖跨群隔离、wiki/workspace symlink/path traversal、裸 URL + Markdown URL 资源 provenance、历史链接不授权、web_extract 精确临时文件授权/新消息撤销、固定 argv、凭据脱敏、50 MB 下载上限和真实进程沙箱外写拒绝。最终要求三个 hook/fire site、`ctx.register_tool()`、sandbox-exec 和当前 Gateway 真实子进程 PID 之后同时存在 `active=True` structured-tools trace（含 `hypertex_chats/users`）与 `mcp__hypertex__tasks_get/update/cancel` 注册 trace。任一失败设置升级 `FINAL_RC=1`。

**上游吸收判断**：如果上游原生提供按会话隔离的可写工作区、无 shell 的固定动作工具、子进程写范围沙箱、owner-DM/group 独立工具面、当前消息资源 provenance 与安全的 deferred-tool bridge，可迁移到上游能力并归档本补丁；在此之前不得恢复群聊通用 terminal，也不得开放全局 cache/任意 bot 可读文档。

---

## Archive — PATCH-LAUNCHD-WRAPPER-SUPERVISOR（上游 v0.20.4）

### [PATCH-LAUNCHD-WRAPPER-SUPERVISOR] launchd stderr wrapper 保留受监管身份

| 字段     | 内容                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------- |
| **文件** | 上游 `hermes_cli/gateway.py`, `tests/hermes_cli/test_gateway_external_supervisor.py`           |
| **状态** | ✅ 已上游合并（v0.20.4，commit `7008fb81b3`）；本地源码 hunk 与旧 `test_gateway.py` 回归已移除 |

**问题**：launchd plist 用 `hermes_cli.stderr_timestamp` 包裹真实 Gateway 后，原生 `XPC_SERVICE_NAME` 无法可靠传到二级子进程；wrapped child 会把自己误判为 shell 副本并因多写者保护退出，导致 launchd 反复拉起失败。

**修复**：上游 `7008fb81b3` 已在生成的 launchd wrapped child argv 上显式追加 `--external-supervisor`，同时让 `stderr_timestamp` 升级旧 plist 的 Hermes Gateway argv；未受 launchd 监管的 detached fallback 仍保持无标记。本地 `_gateway_run_command()` 参数扩展和旧测试 hunk 因此删除，`hermes_cli/gateway.py` 与 `tests/hermes_cli/test_gateway.py` 退出 `PATCHED_FILES`。

**验证**：上游 `tests/hermes_cli/test_gateway_external_supervisor.py` 覆盖 generated launchd inner argv 交还外部 supervisor、旧 plist wrapper 升级，以及无标记 detached watcher 反例；`hermes-update.sh` Step 8b 保留归档 sentinel，检查官方实现和这组正反例后才允许刷新 replay bundle。终态仍需真机证明 launchd definition current、supervisor PID 与真实 Gateway child PID 均健康。

**上游吸收判断**：已由 commit `7008fb81b3` 完全吸收。若官方实现或正反例回归被移除，归档 sentinel 必须阻断升级并重新评估是否恢复本地补丁。

---

## Archive — 本地模型链路收敛（2026-08-15）

### [PATCH-VERTEX-FALLBACK] 第二 Vertex 账号作为独立 fallback

| 字段     | 内容                                                                                                                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/vertex_adapter.py`, `hermes_cli/auth.py`, `hermes_cli/runtime_provider.py`, `agent/auxiliary_client.py`, `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🗄️ 已归档：当前只使用一个标准 Vertex 账号                                                                                                                                                                |

**归档原因（2026-08-15）**：模型链路已改为 Azure GPT-5.5 → Bedrock Claude Opus 5 → 标准 `vertex/google/gemini-3.5-flash`，视频旁路与 compression 也复用同一标准 Vertex 凭据。第二账号不再提供独立能力，继续维护会扩大 provider/凭据/gate 面；因此删除全部 `vertex-fallback` provider、别名、第二 SA/project 解析、回归、Step 8b gate 与 `.env` 变量。若未来再次需要同 provider 的 per-project 配额隔离，优先使用上游 credential pool；只有它仍无法表达 per-entry SA/project 时才重新评估本补丁。

**问题**（提出时的场景：主模型也是 Vertex 上的 `google/gemini-3.1-pro-preview`）：单账号/单 project 配额下频繁 `429 RESOURCE_EXHAUSTED`，回退到 Qwen 后行为与质量都跟主模型不一致。需求：fallback 换成**第二个 Vertex 账号**跑同一个 gemini-3.1-pro，行为与主模型一致，仅换账号绕开限额。两处架构约束使"同 provider 同模型换账号"无法直接配置：①`vertex` 不在 `hermes_cli.auth.PROVIDER_REGISTRY`（auto-extend 只收 `auth_type=="api_key"`），主模型靠 `resolve_runtime_provider()` 专门解析，而 **fallback 走 `resolve_provider_client()`，只从 `PROVIDER_REGISTRY.get()` 取 pconfig** → 现有 `auth_type=="vertex"` 分支对 fallback 是够不到的死代码；②fallback 去重（`chat_completion_helpers._try_activate_fallback`）对 `provider+model` 相同的条目直接跳过。此外 `get_vertex_credentials` 里 `_resolve_project_override()`（`VERTEX_PROJECT_ID`/config）会把任何账号的 token 重绑到主 project → 第二账号 403。

**修复**：新增独立 provider `vertex-fallback`，复用同一 `VertexProfile`（自动继承 `PATCH-VERTEX-HIDDEN-THOUGHTS` 的单层抑制 → 行为一致），只换凭证：

1. `agent/vertex_adapter.py`：新增 `get_vertex_fallback_config()` / `has_vertex_fallback_credentials()`，从 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（经 `_get_secret`）解析第二账号；给 `get_vertex_credentials`/`get_vertex_config` 加 `project_override`（显式项目优先）与 `apply_global_project_override=False`（不套用 `VERTEX_PROJECT_ID`），确保第二账号 token 锁在自己的 project；token 按 path 各自缓存 + 自动刷新（复用 `_creds_cache`）。
2. `hermes_cli/auth.py`：在 `PROVIDER_REGISTRY` 显式登记 `vertex-fallback`（`auth_type="vertex"`，别名 `vertex2`/`vertex-secondary`），使 `resolve_provider_client` 能取到 pconfig 并命中 vertex 分支。
3. `agent/auxiliary_client.py`：`resolve_provider_client` 的 `auth_type=="vertex"` 分支内，按 **registry 条目的 canonical id**（`pconfig.id == "vertex-fallback"`，2026-08-07 修复——此前按原始 provider 串判定，`vertex2`/`vertex-secondary` 别名会静默铸出主账号凭据，恰是配额耗尽的那个账号）改用 `get_vertex_fallback_config` / `has_vertex_fallback_credentials`。
4. `plugins/model-providers/vertex/__init__.py`：用同一 `VertexProfile` 类再 `register_provider` 一个 `name="vertex-fallback"` 实例，使 `get_provider_profile("vertex-fallback")` 可解析（fallback 激活后 `_build_request_kwargs` 走 profile 路径拿到单层抑制）。
5. `hermes_cli/runtime_provider.py`（2026-07-29 补缺口）：网关 fallback 链（`gateway/run.py` `_try_resolve_fallback_provider`）解析条目走 `resolve_runtime_provider(requested=...)` 而**不是** `resolve_provider_client`；其 Vertex 分支只认主账号 5 个别名，`vertex-fallback` 静默落到 generic 尾部解析器，"成功"返回 `provider="openrouter"` + **空 api_key**——网关据此打出误导性的 `Fallback provider resolved: vertex-fallback` 日志并把坏 kwargs 交给 `AIAgent`；init 因空 key 走 router 路径，又因 `openrouter` 在豁免集合（`{auto, openrouter, custom}`）里跳过 explicit fail-fast 与 init-time fallback，最终抛 `No LLM provider configured`，用户在群聊/私聊看到 "Sorry, I encountered an unexpected error"；且链上后续条目（末位的 DashScope 档，NO_PROXY 直连、代理瞬断时本可救场）永远轮不到。修复：在主 vertex 分支之后新增 `("vertex-fallback", "vertex2", "vertex-secondary")` 分支，经 `get_vertex_fallback_config()` 铸 token 返回 `provider="vertex-fallback"`；凭据不可解析时抛类型化 `AuthError`，使 fallback 链前进到下一条目。触发场景：本机代理（127.0.0.1:7897）瞬断时 `oauth2.googleapis.com` token 刷新失败（"No route to host" / SSL EOF，见 `logs/agent.log*`），主 Vertex 解析抛 AuthError 进入 fallback 链。

**归档前适用性（2026-08-11 历史）**：当时 `vertex-fallback` 是链上唯一具备视频能力的档，现 `PATCH-MULTIMODAL-SIDECAR` 的前身 `PATCH-VIDEO-SIDECAR` 直接依赖它。2026-08-15 已改由标准 `vertex/google/gemini-3.5-flash` 承担同一职责，本段仅保留当时为何继续维护第二账号的背景。

归档前配套（历史）：`~/.hermes/.env` 曾使用 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID` 管理第二账号；这些键已于 2026-08-15 从 `.env` 删除。

**验证**：Step 8b grep `agent/vertex_adapter.py` 存在 `def get_vertex_fallback_config` + `apply_global_project_override`；`hermes_cli/auth.py` 存在 `"vertex-fallback"`；`agent/auxiliary_client.py` 存在 `has_vertex_fallback_credentials`；`plugins/.../vertex/__init__.py` 存在 `name="vertex-fallback"`；`hermes_cli/runtime_provider.py` 存在 `"vertex-fallback", "vertex2", "vertex-secondary"` 分支；test 存在 `test_vertex_fallback_profile_registered` + `test_resolve_runtime_provider_vertex_fallback_mints_token` + `test_resolve_provider_client_alias_mints_fallback_credentials`（2026-08-07 新增：别名走 fallback 凭据、主账号铸 token 被断言不可达）。单测 14 passed / 0 failed（2026-08-07；含 7 条 fallback 回归）。真链路：`resolve_runtime_provider(requested='vertex-fallback')` 返回 `provider="vertex-fallback"`、base_url 锁定 `projects/gen-lang-client-0217395804`、api_key 为有效 OAuth token（修复前同调用返回 `provider="openrouter"` + 空 api_key）。真链路端到端：加载 `.env` 后 `get_vertex_fallback_config()` 返回 base_url 锁定 `projects/gen-lang-client-0217395804`（未被主 project 覆盖），`resolve_provider_client("vertex-fallback", model="google/gemini-3.1-pro-preview")` 返回可用 client 且真实调用返回干净答案（无 thought 段）。第二账号 SA 直连 Vertex `/v1`+`/v1beta1` global 均 200。

**上游吸收判断**：若上游为 Vertex/OAuth-token 类 provider 提供多凭证轮换池（credential pool），或让 fallback 条目原生携带 per-entry `credentials_path`/`project`，可归档本补丁改用原生机制。**候选替代已进入当前树**（2026-08-03，d1afa160 已含）：`agent/credential_pool.py`（`CredentialPool`/`PooledCredential`，支持 `AUTH_TYPE_OAUTH`，`hermes_cli/auth.py` 与 `runtime_provider.py` 已接入）提供同 provider 多凭证 failover，但按 token/api-key 条目存储，**尚无 per-entry SA 文件 + 独立 GCP project 语义**——本补丁"第二账号绕 per-project 配额"的需求暂不能直接表达，本轮判定为继续保留本地实现；后续每轮复核该池是否补齐 SA-file/project 语义，补齐即迁移。同时注意 `ca5ce1110` 已把 auxiliary-client 的 provider-key 读取改走 profile secret scope，与本补丁在 `auxiliary_client.py` 的改写区域重叠（本轮 3-way 已干净并存），后续冲突按 scoped-read 形式适配本地分支。

---

### [PATCH-GEMINI-CUSTOM-NATIVE-BASE] 自定义 Gemini gateway 保持原生 wire

| 字段     | 内容                                                                                                                                                                                                                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/gemini_native_adapter.py`, `agent/agent_runtime_helpers.py`, `agent/chat_completion_helpers.py`, `agent/auxiliary_client.py`, `agent/transports/chat_completions.py`, `hermes_cli/doctor.py`, `tests/agent/test_gemini_native_adapter.py`, `tests/hermes_cli/test_gemini_provider.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🗄️ 已归档：自动链路与 compression 均已迁移到标准 Vertex                                                                                                                                                                                                                                                                         |

**归档原因（2026-08-15）**：私有 native gateway 的短请求与 compression 可用，但 110k 级完整 Hermes `systemInstruction` 稳定读超时；同内容折叠到 user 虽可返回，却会降低系统指令优先级，不能作为安全修复。当前链路已用标准 Vertex Gemini 3.5 Flash 替代，完整 prompt + 29 tools 实测通过，因此删除 private-base helper、completed-stream fallback、doctor probe、相关测试/gate 与 `GEMINI_*` `.env` 变量。只有再次启用私有 Gemini gateway，且其原生 systemInstruction 兼容性得到验证时才重新评估。

**问题**：Hermes 文档把 `GEMINI_BASE_URL` 定义为 Google AI Studio / Gemini API 的 base URL override，但运行时只有域名包含 `generativelanguage.googleapis.com` 才创建 `GeminiNativeClient`。私有 Gemini gateway（例如 Gemini CLI 通过 `GOOGLE_GEMINI_BASE_URL=https://gateway.example` 使用的原生 `generateContent` 代理）因此被误判成 OpenAI-compatible endpoint，Hermes 会向不存在的 `/chat/completions` 发请求。2026-08-15 实测同一 gateway 的 `/v1beta/models/gemini-3.5-flash:generateContent` 返回 200，而 `/v1beta/openai/chat/completions` 返回 404、`/v1/chat/completions` 返回 503；仅复制 key/base 配置会让末级 fallback 与 compression 同时失效。

**修复**：新增 provider-aware `is_native_gemini_provider_base_url()`：当 canonical provider 是 `gemini` 时，任意合法自定义 host 默认沿用原生 Gemini wire；只有 base URL 显式以 `/openai` 结尾才选择兼容面。hostname-strict 的 `is_native_gemini_base_url()` 保持不变，避免把其他 custom provider 误判为 Gemini。主 agent client factory、stream options、auxiliary client/pool 和 transport extra-body 过滤统一接入 provider-aware 判定；`GeminiNativeClient` 继续使用 `x-goog-api-key` 与 `models/{model}:generateContent`。私有 gateway 若未实现 `streamGenerateContent?alt=sse`，client 在收到 `stream=True` 时直接返回一次非流式 `generateContent` 的完整 response；Relay 的既有 completed-response 分支会交付该结果并把当前 session 后续调用切成非流式，不引入 heartbeat 私有协议，也不会掩盖 DNS/连接异常。Google 官方 host 保留真 SSE，显式 `/openai` 用户保持兼容路径。Doctor 不再对私有 native gateway 做 Bearer-auth `/models` 探测，而是选取当前 compression/fallback/main 配置中的 Gemini 模型，用 `GeminiNativeClient` 做最小 `generateContent` 健康检查。

**验证**：`tests/agent/test_gemini_native_adapter.py` 断言私有 `/v1beta` 对 provider-aware helper 为 native、`/v1beta/openai` 为 compat，同时 generic helper 对私有 host 仍为 false；另用不实现 `.stream()` 的 fake HTTP client 证明私有 gateway 的 `stream=True` 走 `generateContent` 并直接返回含 content、finish reason 与 usage 的完整 response。`tests/hermes_cli/test_gemini_provider.py` 断言 `resolve_provider_client("gemini")` 在私有 `/v1beta` 创建 `GeminiNativeClient` 且不创建 OpenAI client，显式 `/openai` 反向成立；`tests/hermes_cli/test_doctor.py` 覆盖配置模型选择与 native doctor probe。Step 8b 真实 import helper、provider-client 构造和 doctor probe，不依赖 helper 名 grep；真实 gateway 接入验证使用 `~/.secrets` 的 key/base 映射到 `~/.hermes/.env` 后执行末级 fallback、compression 与顺序 failover。

**上游吸收判断**：当上游明确规定 `GEMINI_BASE_URL` 的自定义 host 默认使用 native Gemini wire、保留 `/openai` 显式兼容 opt-in，并在主 agent、auxiliary、streaming、transport extra-body 与 private-gateway 回归测试上覆盖同等行为后，可删除本地 hunk、Step 8b gate 和新增受管文件，将本块移入 Archive。

---

## Archive — PATCH-LAZY-ACTIVATION（上游 v0.19.0）

### [PATCH-LAZY-ACTIVATION] lazy backend 激活锚点

| 字段         | 内容                                                  |
| ------------ | ----------------------------------------------------- |
| **文件**     | `tools/lazy_deps.py`, `tests/tools/test_lazy_deps.py` |
| **状态**     | ✅ 已上游合并（v0.19.0，commit `2a55f3348`）          |
| **适用版本** | `2a55f3348` 之前需要本地 patch；之后由上游实现        |

**问题**：`active_features()` 原先只要某个 lazy feature 的任一声明依赖已安装，就把它视为“用户曾启用”并在 `hermes update` 中刷新。核心共享依赖会误激活未配置的 Matrix，反复拉取当前 macOS arm64 无法构建的 `python-olm`。

**修复**：上游 commit `2a55f3348` 将所有 lazy feature 的第一项声明依赖统一作为身份锚点；`platform.matrix` 第一项是 `mautrix[encryption]`，因此 `aiohttp`、`asyncpg` 等共享依赖不再造成误激活。该实现覆盖原本地专用 map，并对其他多依赖 feature 提供同一规则，本地源码 hunk 已删除。

**验证**：上游 `test_shared_dependency_does_not_activate_feature` 覆盖仅共享依赖存在时 Matrix 不 active；`hermes-update.sh` Step 8b 保留“首项依赖探测 + 上游回归测试”sentinel，并继续纳入 8c 总闸门。`tests/tools/test_lazy_deps.py` 仍由上游测试集覆盖，但不再属于本地 `PATCHED_FILES`。

**上游吸收判断**：已由 commit `2a55f3348` 完全吸收；若上游未来移除首项身份锚点或对应回归测试，Step 8b 必须阻断 bundle 刷新并重新评估补丁。

---

## Archive — PATCH-DOCTOR-ENABLED-TOOLSETS（上游 v0.18.0）

### [PATCH-DOCTOR-ENABLED-TOOLSETS] Doctor 只统计已启用工具集

| 字段         | 内容                                               |
| ------------ | -------------------------------------------------- |
| **文件**     | `hermes_cli/doctor.py`                             |
| **状态**     | ✅ 已上游合并（v0.18.0，commit `6b21a935a`）       |
| **适用版本** | v0.9.0–v0.17.0 需要本地 patch；v0.18.0+ 已上游修复 |

**问题（历史）**：`hermes doctor` 把所有注册但缺 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中用 `_get_platform_tools` 过滤出用户实际启用的 toolset，只对它们报 issue。

**上游追踪**：上游 commit `6b21a935a`（`fix(doctor): ignore disabled toolsets in missing-API-key summary`）合入等价逻辑，本地 `hermes_cli/doctor.py` 已从 `PATCHED_FILES` 移除。`hermes-update.sh` Step 8b 仍保留 grep `_get_platform_tools` 的存在性检查，用于在上游回滚时及时告警。

---

## Archive — PATCH-ZSH-COMPLETION-SYNTAX（上游 v0.13.0）

### [PATCH-ZSH-COMPLETION-SYNTAX] Zsh completion `_arguments` 语法

| 字段         | 内容                                                                            |
| ------------ | ------------------------------------------------------------------------------- |
| **文件**     | `completions/_hermes`（工程外，不在 `PATCHED_FILES` 中）                        |
| **状态**     | ✅ 已上游合并（v0.13.0，commit `fe61d95b4`）                                    |
| **适用版本** | v0.9.0–v0.12.0 需要本地 patch；v0.13.0+ 上游 `hermes completion zsh` 输出已正确 |

**问题（历史）**：在任何新终端按 Tab 键补全 `hermes` 命令，提示符短暂出现 `...` 随即消失，无任何补全菜单。`hermes completion zsh` 生成的 `_arguments` 规格将互斥说明符 `(...)` 和替代语法 `{...}` 混用，是无效语法：

```zsh
# 无效：zsh _arguments 不支持 (...){...} 组合写法
'(-h --help){-h,--help}[Show help and exit]'
```

**上游修复**：commit `fe61d95b4`（`fix(completion): use valid zsh _arguments exclusion-group syntax`，关闭 issue #22686）将生成器改为：

```zsh
'(-)'{-h,--help}'[Show help and exit]'
'(-)'{-V,--version}'[Show version and exit]'
'(-)'{-p,--profile}'[Profile name]:profile:_hermes_profiles'
```

利用 zsh brace expansion 把一行展开成两个独立规格，`(-)` 表示出现时排除其他所有选项。

**本地处置**：`hermes-update.sh` Step 7 中针对旧坏格式的 `grep -q '){-h,--help}'`、`grep -q '){-V,--version}'`、`grep -q '){-p,--profile}'` 检测块作为回归 sentinel 保留。新格式不会触发匹配，脚本日志直接输出 `PATCH-ZSH-COMPLETION-SYNTAX: upstream completion output already uses correct syntax — no fix needed`。如未来上游回滚到坏格式，inline Python rewrite 会自动重新介入。

---

## Archive — PATCH-DASHBOARD-BUILD-CACHE（上游 v0.11.x）

### [PATCH-DASHBOARD-BUILD-CACHE] Dashboard 避免无效重复构建

| 字段         | 内容                                                  |
| ------------ | ----------------------------------------------------- |
| **文件**     | `hermes_cli/main.py`                                  |
| **状态**     | ✅ 已上游合并（v0.11.x，commit `5b5a53a1`）           |
| **适用版本** | v0.9.0–v0.11.0 需要本地 patch；v0.11.x 之后已上游修复 |

**问题**：`hermes dashboard` 每次启动都在 `HERMES_WEB_DIST` 未设置时直接调用 `_build_web_ui()`；即使构建产物已存在，也会重复执行 `npm install + npm run build`，导致启动耗时数十秒。

**修复**：上游在 commit `5b5a53a155857e63ec7f7eeb373049ad224fc92f`（`fix(cli): check hermes_cli/web_dist/ not web/dist/ for build staleness`）中新增 `_web_ui_build_needed()` helper：以 `hermes_cli/web_dist/.vite/manifest.json`（fallback `index.html`）作 sentinel，并在 `_build_web_ui()` 内部判断 sentinel 是否新过所有 `.ts/.tsx/.js/.jsx/.css/.html/.vue` 源码及 `package.json/package-lock.json/vite.config.*` 等元数据；不需要重建直接早返。该实现比本地原 patch 更完整（额外覆盖 staleness），本地 PATCH-DASHBOARD-BUILD-CACHE 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：`hermes-update.sh` Step 8b 仍保留 grep `_web_ui_build_needed` 的存在性检查，用于在上游回滚时及时告警。

---

## Archive — PATCH-GEMINI-THOUGHT-SIGNATURE（上游 v0.11.0）

### [PATCH-GEMINI-THOUGHT-SIGNATURE] Gemini tool replay 保留 thought signature

| 字段         | 内容                                                                |
| ------------ | ------------------------------------------------------------------- |
| **文件**     | `agent/transports/types.py`, `tests/agent/transports/test_types.py` |
| **状态**     | ✅ 已上游合并（v0.11.0，commit `f5af6520`）                         |
| **适用版本** | v0.10.0 需要本地 patch；v0.11.0+ 已上游修复                         |

**问题**：Gemini 3.1 / Gemini 3 Flash 这类 thinking 模型在发出 tool call 后，下一轮 replay 必须把 tool call 上的 `thought_signature` 原样带回。当前版本已经把旧的 `_nr_to_assistant_message` shim 演进成 `ToolCall` dataclass + property 兼容层，但这里只暴露了 `call_id` / `response_item_id`，没有暴露 `extra_content`。于是 `run_agent.py` 中的 `getattr(tool_call, "extra_content", None)` 永远拿到 `None`，Gemini / Vertex 在 replay 下一轮直接返回 HTTP 400：`missing thought_signature`，然后触发 fallback 到 `qwen3-max`。

**修复**：上游在 commit `f5af6520d0bfac5b17c9ce460a5a06bf3249972c` 中给 `ToolCall` 增加了 `extra_content` 兼容属性，并补上了相应回归测试；本地 PATCH-GEMINI-THOUGHT-SIGNATURE 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：最初的等价修复线索来自上游 PR `#14423`；最终关闭本 issue 的是 commit `f5af6520`。当前 `main` / v0.11.0 已包含该修复，因此本地不再维护源码 patch；`hermes-update.sh` Step 8b 保留 `ToolCall.extra_content` + `test_extra_content_getattr_pattern` 回归 gate，并将其纳入 8c 刷新前提。

---

## Archive — PATCH-DELEGATE-ACP-ROUTING（上游 v0.10.0）

### [PATCH-DELEGATE-ACP-ROUTING] Delegate ACP 子进程路由

| 字段         | 内容                                         |
| ------------ | -------------------------------------------- |
| **文件**     | `tools/delegate_tool.py`                     |
| **状态**     | ✅ 已上游合并（v0.10.0，commit hash 未记录） |
| **适用版本** | v0.9.0 需要本地 patch；v0.10.0+ 已上游修复   |

**问题**：`delegate_task(acp_command="copilot")` 传入 ACP 命令后，子 agent 的 `provider` 仍继承父 agent（如 `gemini`），未切换为 `"copilot-acp"`。`AIAgent` 构造时只在 `provider == "copilot-acp"` 时启用 ACP subprocess 通道，导致 `acp_command`/`acp_args` 被存储但从未使用，子 agent 直接走父 agent 的 API（如 Gemini），最终超时失败。

**修复**：在 `_build_child_agent()` 解析 `effective_acp_command` 之后，检测 `override_acp_command` 是否被显式设置：若是，强制 `effective_provider = "copilot-acp"`、`effective_base_url = "acp://copilot"`，确保 `AIAgent.__init__` 走 `CopilotACPClient` 子进程通道。

**上游追踪**：v0.10.0 合入等价修复（具体吸收 commit 未在本地记录），本地 PATCH-DELEGATE-ACP-ROUTING 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。`hermes-update.sh` Step 8b 保留 grep `override_acp_command` + `copilot-acp` 的存在性检查，用于在上游回滚时及时告警。

---
