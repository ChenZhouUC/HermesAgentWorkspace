# 本地补丁记录

> 本文件集中记录所有本地补丁。`hermes-agent/` 工程内语义补丁统一汇总到 `local-patches.diff` replay bundle；`~/.hermes` 配置仓库用户插件补丁单独标注，由外层 Git 与 `hermes-update.sh` Step 8e verifier 管理。
>
> **AI 维护规范**（详细工作流见 `~/.hermes/hermes-update.md` § Step 4）：
>
> - **每次升级后**重写 `## 当前版本：vX.Y.Z (upstream `main` `<SHA>`，YYYY-MM-DD)` header 与下方"最近一次升级"摘要；摘要遵循 5 段结构（上游主线 / patch apply / 依赖 / 已知摩擦 / 配置漂移）。
> - **新补丁**：使用稳定的语义 ID（`PATCH-<DOMAIN>-<INVARIANT>`），在 `## 当前版本` 节下新增一块 2-row 表（`文件 / 状态`）和 `问题 / 修复 / 验证 / 上游吸收判断` 四段。编号不表达顺序，禁止用 A/B 子编号承载不同吸收单元。
> - **边界判定**：一个补丁只能有一个可独立说明的责任边界、一个对应生命周期 gate（Step 3/4/7/8b/8e）和一个上游吸收条件。能被不同上游 PR 分别吸收的能力必须拆开；只有必须一起回滚、一起验收、一起吸收的改动才能合并。
> - **真实回归证据**：每个活跃/归档 PATCH 都必须在 `**验证**` 段落绑定真实测试、运行时边界或保留的上游回归。工程 PATCH 的验证函数由 full evidence 唯一解析成完整 pytest node ID，节点文件必须属于该 PATCH 的 `**文件**` 清单，并在隔离 JUnit 中真实 passed；同一个 node 不得被多个 PATCH 共用。full 模式同时记录 Python 调用轨迹，凡拥有 Python 生产代码的 PATCH，其 evidence 必须逐文件执行全部声明的 owned production `.py`，不能只靠命中同 PATCH 的任意一个文件整块放行；纯测试型 portability/hermeticity PATCH 才豁免，非 Python surface 继续由对应 runtime/gate contract 验收。同名歧义、跨 PATCH 复用、借用未登记测试文件、部分或完全未触达 owned implementation、未收集、skip、xfail、error 或 failure 均拒绝，不能借用相邻 gate 或相邻 PATCH 的 `test_*`。Archive 上游吸收项运行当前 pytest/CLI/行为探针；因需求退役项执行 secret-safe、provider/model-independent 的旧 capability/resolver/config-key surface 负向审计。`python3 scripts/test_patch_evidence.py --report-json <path>` 逐块输出 lifecycle、evidence type、完整 node、executed owned files、upstream overlap 与 outcome；`--final-audit --json` 再把 canonical suite、runtime/verifier/docs/cleanup 合成终态权威。
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

| 类型                 | 代表                                                     | 管理方式                                                                                                                                                                                                 |
| -------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁**       | 当前清单中标记为“未上游合并”的源码补丁                   | 统一 replay bundle (`local-patches.diff`) + `PATCHED_FILES` + 每补丁独立 invariant gate；完整行为由 playbook Step 2c 回归证明                                                                            |
| **配置仓库用户插件** | `PATCH-CLAUDE-SC-PROVIDER`、`PATCH-FEISHU-GROUP-SANDBOX` | 外层 Git 跟踪 `config.yaml` / `plugins/` / `my-skills/`；Step 8e 强制校验配置、provider/toolset 行为和运行时状态，失败则整次升级非零退出                                                                 |
| **运行时补丁**       | `PATCH-NPM-DEPENDENCY-HYGIENE` 等                        | 由 `hermes-update.sh` 的明确步骤重建并验证，不进入 replay bundle；事务/完整性 gate 失败必须令整轮非零，npm audit 被上游 lock/range 阻塞且不影响飞书主链路时归为 P2，保留明确 warning/action 并在摘要定性 |
| **已上游合并**       | 文末 Archive                                             | 保留吸收来源和回归 sentinel；不计入活跃补丁清单                                                                                                                                                          |

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
  │   ├─ PATCH-UPDATE-FLEET-RECEIPT-FRESHNESS: 当前 live fleet 已全量匹配 HEAD 时忽略陈旧失败 receipt
  │   ├─ PATCH-FEISHU-GROUP-ADMISSION: 群触发/本人代答策略/上下文/当前发言人/显式 wiki 路径
  │   ├─ PATCH-FEISHU-MISSED-EVENT-BACKFILL: 断线/重连漏消息补偿（群+主会话 DM）与 quote 覆盖去重
  │   ├─ PATCH-FEISHU-GROUP-SCOPE: feishu_group capability namespace 与 DM 隔离
  │   ├─ PATCH-PLATFORM-CAPABILITY-SCOPE: 平台 skill allowlist + 只读 skill/file toolset
  │   ├─ PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY: 冗余 tool_call 包装安全解一层
  │   ├─ PATCH-FEISHU-GROUP-APPROVAL: 群聊审批及卡片/文字出口硬拦
  │   ├─ PATCH-FEISHU-ADMIN-CONTROL-SCOPE: 群内 owner 新会话、主 DM Gateway 管理
  │   ├─ PATCH-FEISHU-NORMAL-REPLY: 普通引用回复，不进入 thread/topic lane
  │   ├─ PATCH-FEISHU-FINAL-ONLY: Feishu 最终内容优先，长任务通用心跳
  │   ├─ PATCH-GATEWAY-FAILOVER-STATUS-SILENCE: 主模型/fallback 路由状态只进日志
  │   ├─ PATCH-FEISHU-RESPONSE-BUDGET: 可配置聊天软字数预算 + 单条 post 硬兜底
  │   ├─ PATCH-LOCAL-PROFILES: 人物/群画像、来源保密与可见输出过滤
  │   ├─ PATCH-FEISHU-RESOURCE-ACCESS: 附件回看、合并转发完整引用、Drive/doc access
  │   ├─ PATCH-DOCUMENT-EXTRACTION: PDF/HTML/Office/OpenDocument 可信抽取（XLSX/DOCX/IPYNB 已上游）
  │   ├─ PATCH-FEISHU-MARKDOWN: 标题/引用、strong flanking 与 mention/block 边界归一化
  │   ├─ PATCH-FEISHU-SSRF-TEST-SYSPROXY: SSRF rebind 测试对宿主系统代理 hermetic
  │   ├─ PATCH-VERTEX-HIDDEN-THOUGHTS: Vertex thought 文本不进入可见内容
  │   ├─ PATCH-VERTEX-DOCTOR: doctor 识别官方 Vertex profile
  │   ├─ PATCH-DOCTOR-TEST-NETWORK-ISOLATION: doctor 单测不访问真实网络/宿主命令
  │   ├─ PATCH-TEST-RUNTIME-STATE-ISOLATION: pytest 不得写入真实 Gateway/process identity 状态
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
  │   ├─ PATCH-MCP-STDIO-WATCHER-LIFECYCLE: stdio RPC 只创建一个可等待的子进程 watcher
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
  ├─ PATCH-CLAUDE-SC-PROVIDER: 配置/密钥/注册/Claude Code 请求身份/推理/cache/工具/图片能力 + Gateway freshness
  ├─ PATCH-FEISHU-GROUP-SANDBOX: YAML 契约 + owner/group 真实 toolset + sandbox/身份/文档媒体行为测试 + launchd wrapper / 真实 Gateway 子进程双层 runtime trace
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
    "gateway/display_config.py"
    "plugins/platforms/feishu/adapter.py"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/run_agent_cache.py"
    "gateway/run_busy.py"
    "gateway/run_inbound.py"
    "gateway/run_turn.py"
    "gateway/run_turn_runner.py"
    "gateway/slash_commands.py"
    "gateway/slash_commands_model.py"
    "gateway/slash_commands_session.py"
    "gateway/slash_access.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "gateway/session_state.py"
    "gateway/stream_consumer.py"
    "gateway/stream_consumer_fallback.py"
    "gateway/stream_consumer_transport.py"
    "hermes_cli/doctor.py"
    "hermes_cli/doctor_config.py"
    "hermes_cli/env_loader.py"
    "hermes_cli/model_switch.py"
    "hermes_cli/config_defaults.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/auxiliary_client.py"
    "agent/session_persistence.py"
    "agent/skill_commands.py"
    "agent/skill_utils.py"
    "agent/turn_tool_round.py"
    "agent/turn_tool_validation.py"
    "agent/turn_truncation.py"
    "tools/approval.py"
    "tools/approval_detection.py"
    "tests/tools/test_approval.py"
    "tools/skills_tool.py"
    "tests/tools/test_skills_tool.py"
    "toolsets.py"
    "tools/feishu_doc_tool.py"
    "tests/tools/test_feishu_tools.py"
    "tools/read_extract.py"
    "tests/tools/test_read_extract.py"
    "tests/conftest.py"
    "tests/test_runtime_home_isolation.py"
    "tests/gateway/feishu_helpers.py"
    "tests/gateway/test_config.py"
    "tests/gateway/test_display_config.py"
    "tests/gateway/test_feishu.py"
    "tests/gateway/test_feishu_post_files.py"
    "tests/gateway/test_document_context_note.py"
    "tests/gateway/test_feishu_bot_admission.py"
    "tests/gateway/test_feishu_bot_auth_bypass.py"
    "tests/gateway/test_session.py"
    "tests/gateway/test_session_env.py"
    "tests/gateway/test_run_progress_topics.py"
    "tests/gateway/test_slash_access_dispatch.py"
    "tests/gateway/test_background_command.py"
    "tests/gateway/test_verbose_command.py"
    "tests/gateway/test_stream_consumer_silence.py"
    "tests/gateway/test_telegram_audio_vs_voice.py"
    "tests/gateway/test_telegram_noise_filter.py"
    "tests/hermes_cli/test_doctor.py"
    "tests/hermes_cli/test_env_loader.py"
    "tests/hermes_cli/test_skills_config.py"
    "tests/hermes_cli/test_tools_config.py"
    "hermes_cli/update_cmd_fleet.py"
    "tests/hermes_cli/test_update_receipt_live_freshness.py"
    "hermes_cli/prompt_size.py"
    "website/docs/reference/environment-variables.md"
    "website/docs/user-guide/configuration.md"
    "website/docs/user-guide/messaging/feishu.md"
    "plugins/model-providers/vertex/__init__.py"
    "tests/hermes_cli/test_vertex_provider.py"
    "agent/image_routing.py"
    "agent/models_dev.py"
    "agent/transports/chat_completions.py"
    "tests/agent/transports/test_chat_completions.py"
    "tests/agent/test_auxiliary_client.py"
    "tests/agent/test_codex_ttfb_watchdog.py"
    "tests/agent/test_image_routing.py"
    "tests/agent/test_skill_commands.py"
    "tests/gateway/test_image_input_routing_runtime.py"
    "tools/vision_tools.py"
    "tests/tools/test_video_analyze.py"
    "agent/replay_cleanup.py"
    "tests/agent/test_replay_cleanup.py"
    "tests/run_agent/test_provider_fallback.py"
    "tests/run_agent/test_primary_runtime_restore.py"
    "tests/run_agent/test_compressor_fallback_update.py"
    "tests/gateway/test_stale_confirmation_expiry.py"
    "agent/agent_runtime_helpers.py"
    "agent/chat_completion_helpers.py"
    "agent/chat_completion_nonstream.py"
    "agent/tool_executor.py"
    "agent/mcp_task_protocol.py"
    "hermes_state_messages.py"
    "tools/mcp_tasks_extension.py"
    "tools/mcp_tool_discovery.py"
    "tools/mcp_tool_errors.py"
    "tools/mcp_tool_handlers.py"
    "tools/mcp_tool_registration.py"
    "tools/mcp_tool_schema.py"
    "tools/mcp_tool_transport.py"
    "tests/run_agent/test_tool_call_incremental_persistence.py"
    "tests/run_agent/test_run_agent.py"
    "tests/tools/test_mcp_tasks_extension.py"
    "tests/tools/test_mcp_utility_capability_gating.py"
    "tests/tools/test_mcp_tool.py"
    "tools/tool_search_validation.py"
    "tests/tools/test_tool_search.py"
    "website/docs/user-guide/features/mcp.md"
    "native/fts5_cjk/build.sh"
)
```

> 以上为 `hermes-update.sh` 中数组的快照（122 文件，2026-09-12 与脚本核对一致）。**脚本数组是唯一权威来源**；增删补丁文件后请同步刷新本快照。机器读取请用 `bash ~/.hermes/hermes-update.sh --print-patched-files`，不要解析本快照。

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

## 当前版本：v0.21.1 (upstream `main` `3b45681c25a880477a2a806cdebe91d2f1bfe9ce`，2026-09-11)

**活跃补丁**：当前共 46 个语义补丁。37 个工程内补丁由 Step 8b/8c 管理；`PATCH-NPM-DEPENDENCY-HYGIENE`、`PATCH-REPLAY-BUNDLE-FULL-INDEX`、`PATCH-UPDATE-GATE-EXIT-STATUS`、`PATCH-UPDATE-GIT-FETCH-RETRY`、`PATCH-UPDATE-TRANSACTION-PIN`、`PATCH-SKILLS-MIRROR-METADATA`、`PATCH-GATEWAY-RESTART-CLEANUP` 是运行时补丁，由对应 update step 管理；`PATCH-CLAUDE-SC-PROVIDER` 与 `PATCH-FEISHU-GROUP-SANDBOX` 是配置仓库用户插件补丁、由 Step 8e 管理。完整活跃 ID 以上方执行链清单为准；Archive 中的定义只保留历史与重新启用条件，不计入活跃数。

**最近一次升级（v0.21.1，`79445a496c` → `3b45681c25`，+1732 commits，2026-09-11）要点**：

本轮为用户明确要求的同 SHA 全量审计：`HEAD=3b45681c25`，未调用 update/fetch/pull，未取得新上游提交。枚举 45 active + 10 Archive 后，基线 55 项全部通过；隔离负例进一步发现并修复群审批容器短路、Skills 缺省/非法配置，以及 unittest、镜像、原生构建三类证据假绿。实现、回归与原有 probe 共演进；随后按用户明确的管理边界新增 `PATCH-FEISHU-ADMIN-CONTROL-SCOPE`，登记公共命令权限模块与真实分派回归，管理员群内新会话与主 DM Gateway 管理分别验证。

- 上游主线：一次 acquisition 固定目标，后续均为 no-network `--reconcile`。Gateway 消息事件迁入 `gateway/platforms/event.py`（`ab2f4602de`），多 profile 凭据/授权与 Feishu WS context 隔离加强（`cbd03e6e4c`、`2952dc62bc`）；旧 receipt successor 判定（`89c85b8466`）、辅助模型路由（`7e0b5cd235`）、工具搜索/connector batch（`cf4b78e91f`、`b4d04eb8fd`）与 Collective Wisdom（`a6ee31f55a`）进入本轮目标。
- patch apply / registry：14 文件发生 3-way 冲突，按本地不变量与新调用链合并。媒体抽取/旁路迁入上游新 helper，引用正文在 @文件扩展之后注入，保留有界 Feishu 引用；WS 重连回填与 profile context 并存；流式 TTS 的新 commentary 路径仍先脱敏。watchdog 路由文案调用迁入新 nonstream 模块；工具冗余包装迁入单调用/batch 共用 normalization。`PATCH-UPDATE-FLEET-RECEIPT-FRESHNESS` 部分吸收，仅保留严格 PID inventory；删除已由上游实现的 `_BarrierDB.flush_token_counts` 重复 stub，其他 active PATCH 保留。受管文件由升级时 119 → 120，管理命令审计后为 122；规范测试 46 files 与 2 个 test support modules。
  上游重叠/吸收审查：本轮 35 个 active 与 75 个受管路径相交，7 个 Archive 与 13 个声明路径相交，active/Archive 去重后 81 条。相交路径全集：`agent/agent_runtime_helpers.py`、`agent/auxiliary_client.py`、`agent/chat_completion_helpers.py`、`agent/chat_completion_nonstream.py`、`agent/conversation_compression.py`、`agent/image_routing.py`、`agent/models_dev.py`、`agent/prompt_builder.py`、`agent/session_persistence.py`、`agent/skill_utils.py`、`agent/tool_executor.py`、`agent/transports/chat_completions.py`、`agent/turn_truncation.py`、`gateway/authz_mixin.py`、`gateway/platforms/base.py`、`gateway/run.py`、`gateway/run_agent_cache.py`、`gateway/run_busy.py`、`gateway/run_inbound.py`、`gateway/run_turn.py`、`gateway/run_turn_runner.py`、`gateway/session.py`、`gateway/session_context.py`、`gateway/slash_commands.py`、`gateway/slash_commands_model.py`、`gateway/slash_commands_session.py`、`gateway/stream_consumer.py`、`gateway/stream_consumer_fallback.py`、`gateway/stream_consumer_transport.py`、`hermes_cli/auth.py`、`hermes_cli/config_defaults.py`、`hermes_cli/env_loader.py`、`hermes_cli/gateway.py`、`hermes_cli/main.py`、`hermes_cli/model_switch.py`、`hermes_cli/runtime_provider.py`、`hermes_cli/tools_config.py`、`hermes_cli/update_cmd_fleet.py`、`hermes_state_messages.py`、`optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`、`plugins/platforms/feishu/adapter.py`、`pyproject.toml`、`tests/agent/test_auxiliary_client.py`、`tests/agent/test_codex_ttfb_watchdog.py`、`tests/agent/transports/test_chat_completions.py`、`tests/conftest.py`、`tests/gateway/test_background_command.py`、`tests/gateway/test_config.py`、`tests/gateway/test_document_context_note.py`、`tests/gateway/test_feishu.py`、`tests/gateway/test_image_input_routing_runtime.py`、`tests/gateway/test_run_progress_topics.py`、`tests/gateway/test_session.py`、`tests/gateway/test_slash_access_dispatch.py`、`tests/gateway/test_telegram_audio_vs_voice.py`、`tests/gateway/test_verbose_command.py`、`tests/hermes_cli/test_doctor.py`、`tests/hermes_cli/test_tools_config.py`、`tests/run_agent/test_provider_fallback.py`、`tests/run_agent/test_run_agent.py`、`tests/run_agent/test_tool_call_incremental_persistence.py`、`tests/tools/test_mcp_tool.py`、`tests/tools/test_skills_tool.py`、`tests/tools/test_tool_search.py`、`tools/approval.py`、`tools/approval_detection.py`、`tools/delegate_tool.py`、`tools/lazy_deps.py`、`tools/mcp_tool_discovery.py`、`tools/mcp_tool_handlers.py`、`tools/mcp_tool_registration.py`、`tools/skill_manager_tool.py`、`tools/skills_tool.py`、`tools/tool_search_validation.py`、`toolsets.py`、`uv.lock`、`website/docs/guides/migrate-from-openclaw.md`、`website/docs/reference/environment-variables.md`、`website/docs/user-guide/configuration.md`、`website/docs/user-guide/features/mcp.md`、`website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md`。
  吸收矩阵：`PATCH-FEISHU-ADMIN-CONTROL-SCOPE`=未吸收；`PATCH-APPROVAL-DARWIN-TMP`=未吸收；`PATCH-COMPACTION-LIFECYCLE-SILENCE`=完全吸收；`PATCH-DASHBOARD-BUILD-CACHE`=完全吸收；`PATCH-DELEGATE-ACP-ROUTING`=完全吸收；`PATCH-DOCTOR-TEST-NETWORK-ISOLATION`=未吸收；`PATCH-DOCUMENT-EXTRACTION`=部分吸收；`PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION`=未吸收；`PATCH-FEISHU-FINAL-ONLY`=未吸收；`PATCH-FEISHU-GROUP-ADMISSION`=未吸收；`PATCH-FEISHU-GROUP-APPROVAL`=未吸收；`PATCH-FEISHU-GROUP-SCOPE`=未吸收；`PATCH-FEISHU-MARKDOWN`=未吸收；`PATCH-FEISHU-MISSED-EVENT-BACKFILL`=未吸收；`PATCH-FEISHU-NORMAL-REPLY`=未吸收；`PATCH-FEISHU-QUOTE-CHAIN-SESSION`=未吸收；`PATCH-FEISHU-RESOURCE-ACCESS`=未吸收；`PATCH-FEISHU-RESPONSE-BUDGET`=未吸收；`PATCH-FEISHU-SOCKS-DEPENDENCY`=未吸收；`PATCH-FEISHU-SSRF-TEST-SYSPROXY`=未吸收；`PATCH-GATEWAY-FAILOVER-STATUS-SILENCE`=未吸收；`PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY`=未吸收；`PATCH-GEMINI-CUSTOM-NATIVE-BASE`=完全吸收；`PATCH-HISTORY-RETENTION`=未吸收；`PATCH-IMAGE-NATIVE-ROUTING`=未吸收；`PATCH-LAUNCHD-WRAPPER-SUPERVISOR`=完全吸收；`PATCH-LAZY-ACTIVATION`=完全吸收；`PATCH-LOCAL-PROFILES`=未吸收；`PATCH-MCP-STDIO-WATCHER-LIFECYCLE`=部分吸收；`PATCH-MCP-TASKS-ASYNC-HANDOFF`=未吸收；`PATCH-MODEL-CONFIGURED-ONLY`=未吸收；`PATCH-MULTIMODAL-SIDECAR`=未吸收；`PATCH-OPENCLAW-TOKEN-MIGRATION`=未吸收；`PATCH-PLATFORM-CAPABILITY-SCOPE`=未吸收；`PATCH-SKILL-CREATE-ROOT`=部分吸收；`PATCH-TEST-RUNTIME-STATE-ISOLATION`=未吸收；`PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY`=未吸收；`PATCH-TRUNCATED-TOOL-CALL-RECOVERY`=未吸收；`PATCH-UPDATE-FLEET-RECEIPT-FRESHNESS`=部分吸收；`PATCH-VERTEX-DOCTOR`=未吸收；`PATCH-VERTEX-FALLBACK`=完全吸收；`PATCH-VERTEX-VIDEO-ROUTING`=未吸收；无路径相交=11。
- 依赖：199 个既有 Python 包全部保留；仅 Hermes 0.21.0 → 0.21.1、brotlicffi 1.2.0.1 → 1.2.0.2。官方新增 1 个 skill、更新 4 个，wrapper 补齐原有 llm-wiki 镜像。npm 非破坏修复后仍为 11 项（2 moderate / 9 high），`npm explain` 均指向 dev Desktop/build/test 链；根依赖声明不变、workspace 归一化和传递依赖更新由双 SHA lock receipt 绑定。上游显式 cryptography>=50 override 与 Alibaba SDK <49 元数据产生 `uv pip check` 提示，遵循上游安全 pin，不降级。
- 已知摩擦：首次官方更新在 post-pull fleet 检查无 rows 后非零；固定 SHA 重入完成 pending restart，原有 lockfile stash 已精确恢复。嵌套 provider verifier、Wisdom runtime bytecode、新增 shared-state 协调数据库和 restart marker 已纳入审计/保留规则；新搜索器拒绝多能力混合 query，sandbox verifier 改为逐能力真实匹配。72 项 auditor 负向回归、22 项 cleanup 回归与 bare-upstream PID 漏报/探针故障注入闭合。P2 npm advisory 与上游声明 override 不影响飞书主链路；ChatBI 的 CLI 早期占位符提示经 secret-safe 复核属于加载时序噪音：profile dotenv 有非空值，正式 loader 后环境变量和认证 header 均正确解析，不能据此报告缺凭据。
- 配置漂移：v40 → v42；上游已取消 idle/daily 自动会话重置，删除失效 session_reset 配置并同步 README，压缩/归档与模型链保持既有配置。群审批补齐公共决策、实际发卡出口及纯扫描的免检分支：通用工具/通知新增 20 项正反边界，扫描新增 60 项 group/DM、allow/warn/block 与十种免检场景回归；共 34 个旧实现反例已拒绝，主私聊与无告警命令策略保留。自演进复核将旧登记承诺恢复为行为回归，再清理失效 Phase 描述；Wisdom 私有状态的真实 Git ignore/cleanup keep 双重回归已补齐。终态为 46 active + 10 Archive、56/56 full PATCH evidence、46 files / 2623 passed / 0 failed / 6 skipped、另有 2 个 test support modules、2629 collected、22/22 probe、122-file bundle、37 active + 7 archived gates、sandbox/identity-sync 161 passed；完成与运行态只以本轮最后一次 `--final-audit --json` 为准。

---

## 活跃 PATCH 定义（按类别）

**类别：MCP 协议与异步任务**

### [PATCH-MCP-TASKS-ASYNC-HANDOFF] 标准异步 task handle 即时回执

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/{tool_executor.py,mcp_task_protocol.py,session_persistence.py,turn_tool_round.py}`, `hermes_state_messages.py`, `tools/{mcp_tasks_extension.py,mcp_tool_errors.py,mcp_tool_handlers.py,mcp_tool_registration.py,mcp_tool_schema.py,mcp_tool_transport.py}`, `tests/run_agent/test_tool_call_incremental_persistence.py`, `tests/tools/{test_mcp_tasks_extension.py,test_mcp_utility_capability_gating.py,test_mcp_tool.py}`, `website/docs/user-guide/features/mcp.md` |
| **状态** | 🟡 未上游合并：当前 upstream MCP client 只把 `tools/call` 解析成普通 `CallToolResult`，Agent 工具轮后仍无条件进入下一次模型调用；没有标准 Tasks extension capability negotiation、task lifecycle utilities 或确定性 receipt 终止路径。                                                                                                                                                                                                                                        |

**问题**：MCP 长任务即使在 server 侧已异步入队并立即返回 durable handle，Hermes 仍把结果当普通工具文本追加到上下文，再发起一次 LLM 调用组织回复。真实飞书 turn 中 HyperTeX `tools/call` 仅 0.54s，第二次 Azure Responses 推理却 120s 无 SSE，导致用户 160.5s 后才收到 task ID；同类 provider 抖动会把“任务已受理”伪装成主会话卡死。依靠特定 server/tool 名称短路会把第三方产品耦合进 core，也无法覆盖其它符合 MCP Tasks 规范的 server。MCP SDK 2.x 另有一层更早的假阴性：握手时代协议把 `tools/call` 返回值预校验为普通 `CallToolResult`，该校验先于调用方传入的 raw result model；因此 server 已创建 task 并返回 `resultType="task"` 后，Hermes 仍会因缺少 `content` 抛 `ValidationError`，丢失 task handle 并让模型误以为创建失败。修复回执后又暴露 ID provenance 缺口：task/job/case 是三套独立 ID，财务群用户明确问 task `8` 时模型仍从历史 case 状态取 `job 99` 调 `tasks_get(99)`，把 caller error 报成“task not found”。

**修复**：新增窄协议模块 `tools/mcp_tasks_extension.py`，在 server 广告 `io.modelcontextprotocol/tasks` 时给 `tools/call` 注入 per-request client capability，并用 raw typed result 同时接受普通 result 与 `resultType="task"`。`tools/call` 请求必须使用 SDK 正式 `CallToolRequest` / `CallToolRequestParams`：MCP SDK 2.x 的 `send_request()` 会在序列化前读取请求类协议元数据，旧 generic `RootModel` 缺少 `name_param`，会在请求到达 server 前抛 `AttributeError`；只有自定义 `tasks/get|update|cancel` 继续使用 raw request，并显式声明 `name_param=None`。SDK 2.x 握手时代连接还会在 caller result model 前强制执行 core result surface 校验，因此仅在“server 已广告 Tasks + negotiated version 属于 handshake era + SDK 暴露 dispatcher/stamp seam”三条件同时成立时，Hermes 走一个窄 raw-dispatch bypass：逐项保留 SDK 的 protocol stamp、请求类 name metadata 处理、session timeout 与负 TTL floor，然后由本模块严格二选一校验普通 `CallToolResult` 或 `resultType="task"`；现代协议和 SDK 1.x 仍走公开 `send_request()`。Tasks utility schema 明确要求 exact taskId，用户点名时逐字复制，禁止以 case/job/run 等业务 ID 代替；当 server 对只读 `tasks/get` 明确返回唯一 `suggestedTaskId` 时只重试一次，`tasks_cancel` / `tasks_update` 绝不自动改 ID。普通 `CallToolResult` 的错误位兼容 MCP SDK 1.x `isError` 与 2.x `is_error`，成功结果优先走 SDK 2.x 公共 `validate_tool_result`、回落旧版 `_validate_tool_result`，错误结果不误触发验证。基于同一 capability 动态注册通用 `tasks_get` / `tasks_update` / `tasks_cancel` utilities。`agent/mcp_task_protocol.py` 只认 MCP 前缀工具的标准 task shape，不识别任何 server、tool 或任意业务字段：创建和查询回执均直接渲染为固定两列 GFM 表格，始终显示 task ID 与规范化状态，按状态补充 phase、error 及从 final result JSON/content 中递归提取、去重并按 HTML/PDF/Preview/Download/Result URL 分类的链接。该格式不经过第二次 LLM 改写，因而不随提问语言漂移，并由飞书既有 post/Markdown 后处理原生渲染。业务 payload 内的 `status/error` 与 `CallToolResult.is_error/isError` 不得改写 Task 状态；`cancelled` 有独立状态；`input_required` 保留给正常 model/client 路径处理 `inputResponses → tasks/update`；同批混入普通工具结果时也不短路。Streamable HTTP 的 `tasks/get|update|cancel` 由 same-origin request hook 注入规范 `Mcp-Name=taskId` / `Mcp-Method=method` 路由头，跨源 redirect 同 authorization 一起剥离。server/tool 名称、poll interval、`structuredContent`、内部 ID 与非链接业务 payload 一律不进入普通前台回执。串行/并行 executor 都把 task metadata 绑定到已持久化 tool message，conversation loop 在 guardrail 与增量持久化成功后追加最终 assistant receipt 并退出本轮，保持角色配对与 prompt cache，不自动轮询、不再调用 LLM。普通 MCP 结果、未广告 extension 的 server 和非 MCP 工具行为不变。

**2026-09-03 provenance 持久化加固**：普通 MCP JSON 即使伪造 `resultType/taskId/status` 也不可信；只有协商过 Tasks extension 的 handler 才能附加一次性、工具名绑定的内部 provenance。该 provenance 必须随 worker 返回父线程，并通过 `run_agent.py → hermes_state.py` 的内部 `display_metadata` sidecar 落入 SQLite；恢复会话时再提升为 `_mcp_task_result`，不会作为普通显示 metadata 暴露。这样 task handle 在并发 executor、进程内增量持久化和 SessionDB 重开后仍可被确定性识别，同时普通 JSON 不能冒充。

**验证**：Step 8b 同时锚定 extension ID、task-aware dispatch、SDK 正式 `CallToolRequest`、custom request `name_param=None`、SDK 2.x legacy core-result bypass、exact taskId schema、只读 suggested-ID 单次重试与 mutation 不纠错反例、MCP 1.x/2.x 错误字段/结果校验兼容、动态 `tasks_get` schema、HTTP routing hook、conversation-loop `direct_task_response` 和行为测试。`test_task_aware_call_advertises_extension_and_accepts_task_handle` 与 `test_task_aware_call_bypasses_sdk2_legacy_core_result_prevalidation` 直接执行 `tools/mcp_tasks_extension.py`；`test_mcp_task_provenance_survives_concurrent_worker_and_persistence` 真实穿过 concurrent worker、父 executor、SQLite flush、SessionDB 关闭/重开和 transcript 恢复，断言两个 task ID 顺序与内部 metadata 均保留；`test_task_metadata_requires_negotiated_result_provenance` 继续证明普通 JSON 不能伪造。2026-08-19 财务群真实 create/list 在入队前均复现 `AttributeError: name_param`，HyperTeX `active-jobs=[]`，证明首层故障位于 Hermes request construction 而非 worker；修复后第二次真实 create 已在 HyperTeX 建立 case/job，但 Hermes 复现 `CallToolResult.content Field required`，证明 SDK core-result 预校验发生在 task-aware parser 之前。2026-08-20 财务群又实抓用户问 task `8`、模型误传 job `99`；Data Pipeline task `9` 首次超时但后续同 ID 成功，证明 ID 错误与 transport 卡顿是两类独立故障。2026-08-24 又实抓英文群聊仍收到硬编码中文任务回执，定位到问题在 Hermes deterministic receipt formatter 而非 HyperTeX MCP server。`test_mcp_task_handle_ends_turn_without_second_model_call` 在最初修复前真实得到 4 次 API 调用（第二次断言失败后进入 3 次 retry），修复后严格为 1；`test_mcp_tasks_extension.py` 使用无产品语义的 `demo` server/payload，既在 fake session 中执行 SDK 2.x 同款 `type(request).name_param` 访问，也用真实 SDK 2.x `ClientSession` + fake dispatcher/adopted `2025-11-25` session 复现并锁死 legacy prevalidation：task handle 必须成功返回、wire 必须保留 protocol stamp 与 request body tool name，缺失 `content` 的伪普通结果仍必须被拒绝；同文件另断言 server 建议 `99 → 8` 时 `tasks/get` 只重试一次，而 cancel 不跟随建议。其余测试继续覆盖 custom task request 显式 opt-out、公共/旧版 validation 两代路径、错误字段双拼写、创建/查询回执的固定 GFM 表格、规范化状态、phase/error 选择、表格单元格转义、完成链接分类与去重、无链接时隐藏业务 payload、`input_required`/混合工具批次不短路，以及三种 lifecycle request 的标准 HTTP 路由头与非法 header 值反例；`tests/tools/test_mcp_tool.py::TestMCPServerTask::test_start_connects_and_discovers_tools` 穿过 transport，`tests/tools/test_mcp_tool.py::TestToolHandler::test_successful_call` 与 `tests/tools/test_mcp_tool.py::TestUtilityToolRegistration::test_utility_tools_registered` 分别执行 handler 和动态注册路径，`tests/tools/test_mcp_tool.py::TestRedirectHeaderStripper::test_default_strips_authorization_and_task_routing_headers` 锁定跨源剥离 task routing headers，`tests/tools/test_mcp_tool.py::TestUtilitySchemas::test_builds_resource_prompt_and_task_utility_schemas` 锁定 task utility schema；既有 Feishu table Markdown 回归证明该输出走 post 富文本而非 plain text；`test_mcp_utility_capability_gating.py` 覆盖仅广告 Tasks 时三工具注册、exact-ID 文案及配置关闭。规范 runner、full-index bundle、cached 正向、worktree 反向、index-clean 与最终 Gateway PID 下的 MCP/sandbox verifier 共同构成终态门禁。

**上游吸收判断**：当 upstream Hermes MCP client 原生支持当前 `io.modelcontextprotocol/tasks` extension 的 capability negotiation、`CreateTaskResult`/`tasks/get|update|cancel` 生命周期和 capability-gated model tools，并且 Agent 在标准 task handle 已持久化后能用确定性回执结束交互 turn、无需第二次 LLM 调用，同时有等价的串行/并行与角色配对回归时，可删除本补丁。仅 SDK 出现 Task 类型、仅 server 返回自定义 `task_id`、或仅 UI 提前显示工具结果都不算吸收。

---

### [PATCH-MCP-STDIO-WATCHER-LIFECYCLE] MCP stdio watcher 生命周期与进程身份回执

| 字段     | 内容                                                                                 |
| -------- | ------------------------------------------------------------------------------------ |
| **文件** | `tools/{mcp_tool_discovery.py,mcp_tool_handlers.py}`, `tests/tools/test_mcp_tool.py` |
| **状态** | 🟡 部分吸收（上游已修复并覆盖 PID liveness；watcher 工厂仍调用两次）                 |

**问题**：上游为 MCP stdio RPC 增加子进程死亡快速失败时，先调用一次异步 `_watch_stdio_children()` 检查返回值是否 awaitable，真正调度时又调用第二次；第一支 coroutine 从未被 await 或关闭，每个正常工具调用都会产生 `RuntimeWarning: coroutine ... was never awaited`。旧版同时存在 PID 存活判定反转，曾把健康 HyperTeX 子进程误报为退出；该子问题已由 upstream `98fce8e52d` / `2663117f72` 修复，并由 `ef46ec03e1` 增加 alive/dead/mixed 与 fail-open 回归，本地不再维护对应实现或重复测试。2026-08-30 深度审计又发现运行态 verifier 只按日志先后匹配 MCP 注册行：Gateway 本身注册失败时，后启动的 doctor/CLI 进程可能产生一条同名成功回执，造成跨进程借绿。

**修复**：在真实 RPC 开始前只调用一次 watcher 工厂，把结果保存为 `_watch_coro`；同一个 awaitable 同时用于能力判定与 `asyncio.ensure_future()`。普通 MCP `call_tool` 与 task-aware `call_task_aware_tool` 共用这条竞速路径。PID aggregate liveness、缺少 `psutil` 与 probe exception 的 fail-open 语义全部采用 upstream 当前实现。MCP server 注册成功日志同时写入 `os.getpid()`；Step 8e 只接受与当前 `gateway.status.get_running_pid()` 相同 PID 的 HyperTeX Tasks 注册回执，禁止其他 CLI/doctor 进程替 Gateway 借绿。

**验证**：`tests/tools/test_mcp_tool.py::TestToolHandler::test_stdio_child_watcher_is_created_once_without_leaking_probe_coroutine` 用带调用计数的真实 async watcher 穿过 `_make_tool_handler()`，断言一次 RPC 只构造一次 watcher；`tests/tools/test_mcp_tool.py::TestDiscoverAndRegister::test_registration_log_binds_tools_to_current_process` 锁定注册回执携带当前 PID。Step 8b 以严格 warning 策略运行这两个本地节点及 upstream stdio aggregate-liveness 回归；外层 toolchain fault injection 另证明删除 PID 约束会被拒绝。Step 8e 进一步要求真实 Gateway 子 PID 与 HyperTeX Tasks 注册回执一致；真机 canary 不执行 create/iterate mutation。

**上游吸收判断**：PID liveness 子项已由 upstream `98fce8e52d` / `2663117f72` / `ef46ec03e1` 完全吸收。剩余补丁仅在 upstream 的 stdio RPC 路径只实例化一次 child watcher、同一 awaitable 用于判定与调度，并让注册日志携带可由 runtime verifier 绑定的进程身份且有对应负向回归后可删除；当前 `3b45681c25` 仍缺少后两项，故继续保留最小 hunk。

---

**类别：技能写入与治理**

### [PATCH-SKILL-CREATE-ROOT] 自定义 skill 创建到用户目录

| 字段     | 内容                                                                                            |
| -------- | ----------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 部分吸收：上游已有显式 create_dir；本地保留 external 缺省与严格失败边界                      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：创建路径以显式 `skills.create_dir` 为最高优先级；未声明时，`get_skill_create_dir()` 从原始 `skills.external_dirs` 顺序选择第一个非官方 root，即使该目录尚不存在，也交给 create 建立，不借助只返回既存目录的 discovery。显式指定官方 root 仍是有效覆盖，不落回 external。严格创建路径拒绝损坏 YAML、非 mapping skills、错误 create_dir/external_dirs 类型，返回可诊断错误且不写任何目录。

**验证**：`test_create_defaults_to_first_external_dir_without_explicit_override` 用无 create_dir、缺失 external root、首项为官方 root 三种组合证明真实创建目标；`test_create_rejects_malformed_root_configuration_without_writing` 用实际 YAML 证明五种错误配置均不写入。既有显式 create_dir 回归改用不同 external 目录，锁定显式覆盖优先级。Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("_patch_test")`，**严格断言**返回路径 startswith `~/.hermes/my-skills/`（2026-08-07 审计修复：旧断言含 `or "/skills/_patch_test" not in result` 的 fail-open 分支，官方 skills root 改名时会把回落误报为 active，已删除）。行为回归 `test_create_uses_configured_create_dir`、`test_create_fails_closed_when_skill_root_config_cannot_be_read` 与 `test_delete_skill_created_in_external_dir`，同时锁定配置读取失败不得静默回退官方目录。

**上游吸收判断**：上游已支持显式 create_dir；首个 external 的缺省选择及严格配置失败处理尚未吸收。仅当上游 create 路径已支持把首个 external skill root 作为默认写入目录，且对应创建/删除测试覆盖不存在目录时，才可移除本补丁；当前上游未声明 create_dir 时仍写入官方 root。**语义张力提示**（2026-08-03 审计）：post-26e0b1c 上游新增 `_background_review_write_guard()`，经 `is_external_skill_path()` 将 external_dirs 视为"externally owned、对自主 curation 只读"。该 guard 目前只作用于 background review fork，与本补丁的前台 create 不互斥；但上游把 external 当只读、本补丁把它当默认写入目标，方向相反——每轮升级须复核该 guard 的作用范围未扩大到 create 路径，若扩大则需与上游治理策略重新对齐而不是静默让 create 失败。

---

**类别：升级事务、回放与依赖卫生**

### [PATCH-NPM-DEPENDENCY-HYGIENE] npm 漏洞修复与 install-script policy

| 字段     | 内容                                                                                                                                                                        |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `scripts/{final_upgrade_audit.py,test_patch_evidence.py,test_patch_evidence_auditor.py}`, `patches/package-lock.review` + `node_modules/`（gitignored） |
| **状态** | 🟢 自动化（Step 4 `npm audit fix`；install-script 策略已由上游 `allowScripts` 吸收）                                                                                        |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。Node 26 / npm 12 进一步默认阻止未经审核的 dependency lifecycle scripts；历史上本仓 update 的 root + ui-tui/web 安装会反复提示 `agent-browser` / `esbuild` / `fsevents` / `unicode-animations` 未被允许清单覆盖。

**修复**：保留 Step 4 的 `npm audit fix --quiet`。audit 非零时完整输出进入升级日志，action 改为 `npm audit --json` 定性且明确禁止 `--force`；不再建议机械重跑刚刚失败的同一 fix 命令。上游 lock/range 暂无非破坏解且不影响飞书主链路时归为 P2，允许 warning + 落盘摘要收敛；命令未执行、产物缺失、影响飞书主链路或出现不可解释 drift 才是事务失败。PATCH evidence 的 hermetic `npm audit --json` 对 `TimeoutExpired` 与非 JSON 输出统一返回结构化 `telemetry_unavailable`，不让外部 registry 抖动伪装成 PATCH evidence 缺失；成功解析后的 critical 数仍 fail closed。**install-script 策略片段已退役（2026-08-08）**：上游 `package.json` 自带钉版 `allowScripts` 允许清单（agent-browser/esbuild/fsevents 双版/node-pty/electron\*，`unicode-animations` 显式 false），npm ≥12 将其视为权威并以 "being ignored" 警告忽略任何 .npmrc/global `allow-scripts`；本地临时 global-config 分支因此从 Step 3 删除（退役实现见外层 Git pre-2026-08-08 历史），仅保留空 `_NPM_POLICY_ENV` 声明与惰性清理守卫。

**2026-09-03 lockfile 审核凭据加固**：旧 final-audit 只要求额外 `package-lock.json` 为 unstaged 且 JSON 可解析，任意版本、resolved URL 或 integrity 改写都能借“reviewed”例外置绿。现新增受 Git 管理的 `patches/package-lock.review`，精确绑定当前 upstream `HEAD:package-lock.json` blob SHA 与已人工审查的工作树 lockfile SHA-256；dirty lockfile 只有两者同时匹配才可进入 `reviewed_non_patch_paths`。上游 package-lock blob 或本地 lockfile 内容任一变化都会要求重新审查并更新回执。

**验证**：`hermes update` 必须实际执行 `npm audit fix`；root + workspace 安装在上游 `allowScripts` 下无 `install scripts blocked` / `not covered by allowScripts`，且日志不再出现本地 policy 的 "being ignored" 警告；audit 恢复完整 workspace 产物，`agent-browser`、`esbuild`、`require("fsevents")` 可用，`package.json` 无意外 drift。若 npm 对 lockfile 做可解释的 workspace 布局/安全版本归一化，`package-lock.json` 可作为唯一的非 bundle、仅 unstaged inner dirty 路径保留；final audit 必须验证 JSON、base blob 与 reviewed SHA-256 回执三者一致并在报告中显式列入 `reviewed_non_patch_paths`，任何其他 extra、staged lockfile、缺失或失配回执仍 fail closed。`test_dirty_package_lock_requires_matching_review_receipt` 锁定正确回执与错 base 反例；`test_npm_audit_timeout_is_reported_as_telemetry_unavailable` 锁定 hermetic audit 超时只降级为 P2 telemetry，不得伪装成 PATCH evidence 缺失。隔离 fake 令 audit 非零时，日志必须保留原始诊断、action 只建议 `npm audit --json` 且包含 `do not use --force`。PATCH evidence 的 offline contract 检查脚本行为与禁止 force；live `npm audit --json` 成功解析且出现 critical 才阻断，registry/telemetry 暂不可用按 P2 `telemetry_unavailable` 进入 final JSON，不能伪装成 PATCH 回归缺失。

**上游吸收判断**：install-script allowlist 片段已由上游 `package.json.allowScripts` 吸收（≤`863e31318` 引入，本机 npm 升至 12 后生效确认）。剩余本地不变量只有"升级后自动 `npm audit fix` + 失败分级定性"；上游升级器原生提供等价的 audit/修复流程后可整体归档本补丁。若上游未来移除 `allowScripts`，从外层 Git 历史恢复临时 policy 分支。

---

### [PATCH-REPLAY-BUNDLE-FULL-INDEX] replay bundle 使用稳定对象 ID

| 字段     | 内容                                                                                                                               |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `scripts/{final_upgrade_audit.py,test_patch_evidence_auditor.py}`, `local-patches.diff`, `.local-patches.base` |
| **状态** | 🟢 自动化（Step 2 / Step 8c `--full-index`）                                                                                       |

**问题**：`git diff` 默认按对象库规模自动决定 `index` 行的 SHA 缩写长度。bundle 生成后即使源码 hunk 完全不变，后续 fetch/apply 增加对象也可能让 live diff 从 9 位变成 10 位，导致 playbook 要求的逐字节 `cmp` 失败；只刷新一次默认缩写 bundle 仍会复发。2026-08-18 新增文件又暴露另一个物理缺口：`git diff HEAD -- <untracked>` 为空，因此合法的 new-file hunk 虽已进入 canonical bundle，回贴后 Step 8c 仍把三个新文件误报为 zero-diff，得到 81/84 partial coverage。

**修复**：Step 2 保存与 Step 8c 刷新统一使用 `git diff --full-index`，playbook 的 live-diff 核验也固定同一参数。bundle 的对象 ID 始终写完整 SHA，不再依赖仓库当前的自动缩写宽度。2026-08-06 收尾审计把原先仅由 playbook 人工执行的物理闭环下沉进两个 bundle 发布点：临时包必须通过 conflict-marker、index-clean（2026-08-07 起 Step 2 链内显式 `git diff --cached --quiet`，不再只依赖 preflight 继承）、cached 正向、worktree 反向检查，Step 8c 再与现场 full-index diff 逐字节比较；只有全绿才替换 canonical bundle/base。2026-08-18 起 Step 2/8c 不再依赖真实 index 的 ITA 可见性：`_managed_path_differs_from_head` 显式把「HEAD 不存在 + 工作树存在」判为 new-file diff，`_write_managed_bundle` 则从 HEAD 在临时 index 中精确 add/rm 本轮路径后生成 cached full-index diff，同时覆盖 tracked 修改、删除、untracked 新文件和 upstream-ignored 但已登记的 skill；真实 index 始终不变。裸窗口的逐路径 restore 只接受 `PATCHED_FILES`，因此可安全删除上游不存在的精确 replay-created 文件，不会扫描其它 untracked 路径。注意 8c 的 cmp 是"刷新输出 vs canonical 写入"的一致性闸，当 `_REFRESHED` 与 `PATCHED_FILES` 全等时两侧同源，不能替代 playbook Step 3 的独立现场复核。Step 2 另要求已有 bundle 时全部受管路径都有 live diff，禁止用中断产生的部分 overlay 覆盖完整旧包。

**2026-09-03 base 格式加固**：final-audit 不再只读取 `.local-patches.base` 的首 token；文件必须精确为单行 `<40位 SHA> <UTC timestamp>`，缺时间戳、错误格式或追加垃圾行全部拒绝，避免 provenance 元数据半损坏仍被当作有效基线。

**验证**：`bash hermes-update.sh --print-patched-files` 输出必须与 bundle path 集合、live modified 集合一一相等；脚本 Step 2/8c 日志必须明确报告完整文件数，Step 8c 报 `refreshed and replay-verified`。独立复核必须用临时 index 执行 `git diff --cached --full-index HEAD -- <PATCHED_FILES>` 与 `patches/local-patches.diff` 逐字节比较，并分别运行 `git apply --cached --check patches/local-patches.diff` 和 `git apply --check --reverse patches/local-patches.diff`；正向 cached、反向 worktree 与两次真实 index-clean check 必须同时通过。隔离构造 61/62 的部分 overlay 时 Step 2 必须在写 canonical bundle 前非零退出；Step 8c 的单个 zero-diff path 也必须阻断刷新并点名该路径。对上游不存在的受管新文件，修复前必须稳定复现 81/84 partial coverage，修复后 Step 2/8c 都必须报 84/84，bundle 包含每个 `new file mode`，并且真实 index 在 capture/apply/refresh 前后均保持 clean；`test_patch_base_requires_exact_sha_and_utc_timestamp` 锁定 base 单行格式。

**上游吸收判断**：这是外层 replay bundle 的本地持久化格式；只有未来迁移到不含动态缩写元数据的等价稳定格式，或不再维护本地 replay bundle 时，才可归档。

---

### [PATCH-UPDATE-GATE-EXIT-STATUS] 升级 gate 失败必须非零退出

| 字段     | 内容                                                                                                                                                                             |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `scripts/{final_upgrade_audit.py,test_patch_evidence.py,test_patch_evidence_auditor.py}`, `.github/copilot-instructions.md`, `hermes-update.md`, `README.md` |
| **状态** | 🟢 自动化（Step 8 transaction gate）                                                                                                                                             |

**问题**：旧脚本在 patch apply、Step 8b sentinel、冲突标记或意外空 diff 失败时只追加 warning/action 并跳过 Step 8c，没有设置 `FINAL_RC=1`。Step 8d 也只检查“存在任意 Gateway PID”：若 stop/start 没有真正替换旧进程，仍会把磁盘上已更新、运行时未加载的补丁误报为 active。即使后来补了 PID 替换门禁，macOS 的 `gateway stop` 仍会在短固定宽限后 SIGKILL，绕过 `agent.restart_drain_timeout`，本轮真实飞书任务因此被中断并进入恢复路径。结果既可能运行旧代码，也可能为了加载新代码破坏在途 turn，而脚本仍有机会把表面新 PID 当成功。可重入审计又发现四个同类缺口：把可执行脚本 `source` 后调用预算函数会直接启动整轮升级；3-way apply 失败后的单次批量 restore 会因任一上游已删除 path 令整个 pathspec 失败；3-way 成功隐式留下 staged index；以及接管“bundle 存在、worktree 已裸”的中断现场时没有重新武装 EXIT trap。更严重的是，Step 2 会把仅部分受管文件存在的 diff 当成新 canonical bundle，可能把完整本地不变量集合永久降级为残缺快照。2026-08-15 又实抓一处同类运行态假阳性：Step 5 只因 Gateway 进程正在运行就跳过 plist freshness 检查，最终 status 已明确显示 service definition stale；首次修复又只等待 plist 文件变 current，未等 launchd 重新加载并产生新 PID，导致 verifier 在 reload 窗口拿不到当前进程。**2026-08-20 AI 自演进审计再抓一处聚合假阳性**：`_FEISHU_QUOTE_CHAIN_SESSION_PATCH_OK` 与 `_COMPACTION_LIFECYCLE_SILENCE_PATCH_OK` 均有声明、真实 sentinel 和 `=true` 路径，却漏出 Step 8c 的长条件；两者即使失败，bundle/base 仍可刷新。现有 PATCH 数量/SHA/路径 hygiene 全部通过也没有发现它，证明“定义存在”与“总闸门实际消费”必须机器比较。**2026-08-26 冲突恢复又暴露顺序死锁**：preflight 的 quick PATCH evidence 在 Step 2 捕获人工解冲突后的新 overlay 之前执行 bundle byte parity，必然拿新现场对比旧 canonical bundle 并拒绝进入 Step 2，使 playbook 规定的 `git apply --3way` → 手工解决 → `--reconcile` 路径不可重入。同轮 final-audit 还把“当前版本号只能有一条 README row”误当规则；连续两个 ISO 周版本号未变化时会把合法周记录判成重复，和 README 的周度聚合契约冲突。**2026-08-27 Patch 轮询审计又发现两类证据假绿**：full evidence 只要求每个 source-owning PATCH 命中任意一个 owned production file，且没有约束证据 node 必须来自该 PATCH 登记的测试文件；多文件 Patch 因此可用一个浅层测试掩盖其余实现文件完全未执行，甚至可借用未归属的测试文件。进一步复核发现 runtime/dedicated/archive/external 四类证据的“登记、实际调用、报告置绿”由多个手写列表拼接，`contract_passed` 可在没有本轮专属探针回执时被 final-audit 批量升级为 passed；canonical runner 默认允许失败文件自动重跑一次，首轮失败、次轮通过也会 exit 0。

**2026-08-27 第二轮负向审计**继续发现七类可造成假绿的缺口：文件 ownership 使用子串匹配，`agent/x.py` 可被 `tests/agent/x.py` 冒认；active engineering PATCH 可以没有任何受管文件；Archive gate 没有与真实归档 ID 绑定，同一 gate 可重复置绿；所有 PATCH evidence node 共用一个 pytest 进程，后台线程可能跨 PATCH 借执行轨迹；纯模块 import 可冒充 production 行为执行；evidence 记录的升级范围没有强制终点等于当前 HEAD；final-audit 没把 canonical 完成数与 collect 数闭合，也没有在全部测试后重验 bundle、复跑 sandbox 或确认 `gateway_state.json` 属于当前 Gateway。现场已证实最后一项：生产 `gateway_state.json` 被已退出的 `pytest tests/gateway/test_feishu.py` PID 覆写后，旧 final-audit 仍返回 `status=ok`。

**2026-08-27 第三轮 PATCH 轮询审计**又发现六个边界：Archive/dedicated pytest 探针只看进程退出码，整组 skip/xfail 仍可置绿；PATCH 测试清单只比较总 collect，单个文件零收集可被其他文件掩盖；文档中的完整 node ID 被退化成裸函数名解析，路径/类名写错时可能借到同名测试；Archive overlap 被错误限制在当前 `PATCHED_FILES`，已上游吸收后退出 bundle 的路径反而不再参与后续升级轮询；Step 8e shell verifier 列表与 external evidence registry 没有机器对账；final-audit 在 cleanup 前核对 Gateway 且只比 PID、不比 start-time，也不证明审计期间外层工作树没有被测试改写。

**2026-08-29 深度审计新增假绿类别**：升级到 `e387cbc0aa` 后，`test_direct_session_db_flushes_share_marker_claim` 的测试桩没有随上游 `SessionDB.flush_token_counts()` 接口演进，后台线程抛出 `AttributeError`，主测试仍返回 passed，仅留下 `PytestUnhandledThreadExceptionWarning`。post-commit 深度审计继续以临时 pytest 文件注入 `__del__` 异常、未 await coroutine、测试函数返回 `False` 与同文件测试类部分未收集，确认旧严格探针会把对应 warning 全部接受为 passed/collect 成功。这证明 exit code、JUnit testcase 与 passed 数闭合仍不足以排除测试线程、对象终结器、coroutine 生命周期、断言语义或 collection 完整性已失效。收尾轮询还发现 PATCH 摘要虽列齐全部 overlap 路径并通过 presence gate，却把 active/Archive 路径数误写成 19/11、把去重全集误写成 33；真实 evidence 是 28/12、去重 35。仅校验“路径字符串都出现”不足以证明派生计数正确。

**修复**：unittest 探针只接受 stderr 中非零运行数量与最终无附加状态的 OK；skip 和 expected failure 即使进程 exit 0 也拒绝，stdout 不能冒充 runner 回执。Step 8c 总条件失败直接设置非零；条件通过后发现 conflict marker、部分或全部受管 diff 意外为空、byte/cached/reverse replay 任一失败也设置非零。Step 8d 仅在事务 `runtime_dirty=1` 时捕获旧 PID、走排空感知的 `hermes gateway restart`，等待预算优先取更新后运行时的 `_get_restart_exit_wait_budget()`（上游 `db3f7e4eb` 起原生覆盖 drain + after-turn 两段），旧运行时回落 `restart_drain_timeout`，再统一加 30 秒 supervisor 余量；只有命令成功且轮询到不同的新 PID 才确认 patched modules 已加载并清脏标记。旧 PID 未替换、Gateway 未恢复或 restart 非零都会设置 `FINAL_RC=1`，且不再建议 stop/start 强杀；`runtime_dirty=1` 但当前无 Gateway PID 时同样 `FINAL_RC=1` 并保留脏标记。Step 5 在 patch 还原窗口只做 plist 快照、不得改写最终定义；Step 8 回贴全部源码后再走官方 `gateway start` 自愈并验证 wrapper/child 双 PID。脚本提供 side-effect-free `--print-*` / `--transaction-status` / self-test 入口，拒绝 source 与 dirty index，保护 partial overlay、untracked 同名路径、3-way staged index 和 EXIT trap。preflight 的 `mode=quick` 只运行结构、专用探针、runtime contract 与 Archive 边界检查，不执行依赖当前 canonical bundle 的 parity；bundle byte/cached/reverse/index/base 只在 Step 2/8c 和 full/final audit 中验证，使人工解冲突后的完整 overlay 能先被安全捕获。final-audit 的 README 当前记录按执行日所在 ISO week 选取，并单独断言该周版本等于 checkout；同一版本跨周可并存，同一周重复仍由周键唯一门禁拒绝。2026-08-20 起 `--self-test-patch-gates` 机器比较 Step 8b 声明与 Step 8c 消费集合。2026-08-23 起新增 `--final-audit --json`：在最后一次 reconcile 与全部文档/脚本修改之后，单一入口运行精确 pytest node outcome、完整 canonical PATCH suite、9 个 Archive 探针、bundle closure、Wiki/README/Markdown 派生一致性、sandbox runtime trace、Gateway 双 PID 与最终 cleanup；任何子项失败均以结构化 `failed_step` 非零退出，取代靠 agent 手工拼装十余条命令的收尾方式。2026-08-27 起 full evidence 还强制证据 node 的测试文件属于对应 PATCH，并对该 PATCH 全部 owned production `.py` 做逐文件调用轨迹闭合；任何未执行文件都会列名失败，不再允许单点命中代表整块通过。非 pytest PATCH 的分类表、结构契约表与可调用探针表必须 key-set 完全一致，审计器按注册表自动逐项执行并记录本轮 `probe_results`；full 模式缺探针、重复/未知回执或 deferred 状态都拒绝生成绿报告，final-audit 不再批量改写 `contract_passed`。canonical 终态套件固定 `--file-retries 0`，并对任何残留 FLAKY 标记二次 fail-closed。2026-08-29 起 `hermes-update.sh` 直接 smoke gates、逐 PATCH、Archive/dedicated、Step 8e 和 canonical pytest 入口统一把 thread、unraisable、`RuntimeWarning`、return-not-none 与 collection warning 提升为错误；受影响的 session persistence 测试桩同步实现 `flush_token_counts()`，不再允许线程、对象终结器、未 await coroutine、返回值伪断言或部分未收集测试仍绿。runtime/external probe 还闭合直接 pytest 调用数与可审计命令数，并逐命令检查 update smoke gates 和 sandbox runner 保留五类 filter。final-audit 同时从 evidence 重新计算相交 active/Archive PATCH 数、各自唯一相交路径数与去重全集，并与 PATCHES 当前摘要的 5 个数字逐项相等；路径列齐但派生计数错误也会在 `derived-docs` 阶段失败。

本轮把上述第二、三轮缺口统一收敛到同一条链：ownership 只认反引号内展开后的完整路径，并拒绝零受管文件的 active engineering/dedicated PATCH；active 与 Archive gate header、唯一置绿变量、Step 8c 消费集合三方闭合；每个 PATCH 的 evidence node 在独立 pytest 进程执行，完整 node ID 精确绑定 path/class/function，调用轨迹忽略 `<module>` import；每个可执行 `test_*.py` 必须至少 collect 一个 node，`conftest.py` / helper 等 support module 不计入测试文件数、另做语法/ownership 校验；Archive/dedicated pytest 统一用 hermetic JUnit 严格拒绝 skip/xfail/xpass/零执行；Step 8e verifier 数组必须与 external registry 路径全集一致，verifier 只在全部 JUnit case clean passed 后发出唯一机器回执。PATCHES 当前摘要以 `` `PATCH-ID`=未吸收 | 部分吸收 | 完全吸收 `` 逐项登记全部 upstream-overlap PATCH，Archive overlap 直接来自其声明路径、不再依赖当前 bundle ownership，并记录无 overlap active 数；evidence range 必须为 ancestor→当前 HEAD。canonical `passed+skipped` 必须等于 full collect；final-audit 在 canonical 后再次执行 sandbox verifier 与 bundle byte/cached/reverse/index-clean，最终 cleanup 后再验证持久 `gateway_state.json` 的 PID/start-time/argv/code SHA 属于当前真实 Gateway，并比较审计前后外层 tracked/untracked fingerprint，spawn ledger 不含 pytest 记录。

**验证**：`test_unittest_probe_rejects_skips_and_expected_failures` 用真实 unittest CLI 生成 exit-0 的 skipped/expected-failure 结果，证明旧审计会误收、新审计拒绝。静态检查 Step 8c 的失败分支都设置 `FINAL_RC=1`；`bash hermes-update.sh --self-test-patch-gates` 必须证明声明/消费集合相等并能抓到 fault injection。Step 8d 必须只用 planned restart、比较 old/new PID，`runtime_dirty=0` 跳过 churn；stale plist 只有在 current definition + wrapper PID + real child PID 同时成立后才进入 verifier。临时 Git repo 覆盖完整/部分/裸 overlay、3-way staged/冲突和 byte/cached/reverse replay。`python3 scripts/test_patch_evidence_auditor.py` 以负例证明缺四段、同名测试歧义、跨 PATCH 共用同一 node、从未登记测试文件借证据、evidence 只命中部分 owned Python production file、skip outcome、quick 模式错误执行 bundle parity、runtime PATCH 漏登记实际 probe、full 报告试图提升未执行 probe、canonical flake retry 假绿、后台线程/对象终结器/未 await coroutine/返回值/collection warning 假绿、直接 pytest 命令绕过严格参数、overlap 路径派生计数漂移、同版本跨周记录误判，以及 tracked MCP literal credential 都会被拒绝；`test_final_audit_rejects_stale_managed_file_snapshot` 用临时仓库文档验证漏新文件、括注计数错误与快照顺序漂移均被现有 derived gate 拒绝；`test_final_audit_runs_independent_checks_concurrently` 用 barrier 证明四条只读分支确实并发启动，`test_patch_evidence_parallelism_is_bounded` 锁定逐 PATCH worker 的默认/上限与串行回退，`test_registered_patch_audits_run_concurrently_with_stable_results` 锁定 probe 并发与确定性结果顺序；`bash hermes-update.sh --final-audit --json` 必须输出 `status=ok`、完整逐 PATCH evidence（含 `executed_owned_files` / `probe_results`）、canonical suite 0 failed 且 file retry=0、文档/表格/周记录派生一致、Doctor 无 active advisory/config 漂移/deprecated key、runtime/verifier 健康、tracked config secret-safe、`phase_durations_seconds` 可观测和 cleanup candidate/review 归零。终态若发生 Step 8d 后的运行时修改，仍须先 reconcile/restart，再重新执行 final audit。

2026-08-30 深度审计新增 `test_sandbox_mcp_receipt_must_bind_current_gateway_pid`：删除 Step 8e 对 MCP 注册回执的 Gateway PID 绑定后必须非零，禁止后启动的 doctor/CLI 进程替当前 Gateway 借绿。

本轮负向回归进一步覆盖 ownership 子串、零 owner PATCH、归档 gate 错绑、gate 重复置绿、跨 PATCH pytest 进程隔离、import-only 伪覆盖、完整 node 路径错绑、单文件零 collect、Archive skip/xfail、external verifier 清单漂移、Archive overlap 漏报、canonical/collect 数量不一致、过期或非祖先 upgrade range、测试后 bundle/外层工作树漂移、staged lockfile、Gateway PID reuse 与 pytest runtime-state 污染；任一故障注入必须令对应审计非零。

**上游吸收判断**：这是外层升级 wrapper 的事务语义；只有 wrapper 被替换，且新入口能对 replay apply、全部 sentinel、冲突和空 bundle 提供等价非零总闸门时，才可归档。**排空子项已被上游替代并完成对接**（2026-08-03，本轮升级已跨过 `db3f7e4eb`）：`hermes gateway restart` 原生排空——SIGUSR1 先拒新 turn、按 `agent.restart_after_turn_timeout` 等 in-flight 归零才 stop，`restart_drain_timeout` 收窄为 stop 内强杀预算。上游 `0c6761c51` 已把 after-turn 默认值从 6h 收窄到 30min；本地 `gw_restart_wait_seconds()` 经 `_get_restart_exit_wait_budget()` 读取原生合并预算，本轮新运行时实测 **2745s = 900 + 1800 + 15 + 30**。等待预算必须始终以只读入口当前输出为准，不在 wrapper 内复制默认值；本补丁剩余职责为退出码总闸门与 PID 替换硬校验。

**2026-09-01 evidence trace 性能闭环**：full PATCH evidence 连续两次在同一四节点组超时，但普通 pytest 6 秒通过，证明失败来自审计 profiler 而非业务测试。`scripts/test_patch_evidence.py` 生成的 trace plugin 现缓存每个 code filename 的 realpath/relative 结果，保留逐 PATCH 进程隔离和 production-file 调用归属，同时消除每个函数调用重复访问文件系统的放大效应；`scripts/test_patch_evidence_auditor.py::PatchEvidenceAuditorTest::test_patch_trace_plugin_caches_code_filename_resolution` 锁定缓存与旧逐调用 `Path.resolve()` 反例。

**2026-09-02 tracked credential 负向闭环**：peer 迁移调试曾把一个可用 Bearer token 直接写进受 Git 管理的 `config.yaml`；运行时虽然成功，Git diff、备份与后续 peer 同步都会复制该凭据。现把实值迁入目标机 `0600` `.env`，配置只保留 `${env:VAR}`。`scripts/final_upgrade_audit.py` 解析全部 MCP headers，对 Authorization/API-key/token/secret 类字段只接受纯 env ref 或 Bearer/Basic/Token + env ref；`plugins/sandbox/verify.sh` 在 Step 8e 做同一运行前检查。auditor 以 literal Bearer fault injection 证明旧形态必然被拒绝，且错误只报告配置路径、不回显 secret。

**2026-09-03 终态审计并发与派生闭环**：`--final-audit` 过去在 updater 获取事务锁之前直接 `exec` Python，且 Python 只在开头读一次 transaction、结尾硬编码 `none`，存在与 update/reconcile 并发后混用 HEAD/bundle/runtime 仍置绿的窗口。现 shell 入口持有同一事务锁覆盖完整审计生命周期，Python 再首尾固定并复核 inner HEAD、base 原文、bundle SHA-256 与 transaction；任一漂移归入 `transaction-stability` 非零。派生文档检查同时新增 full collected、registered/executed/deferred probe 和 bundle 文件数闭合，`.local-patches.base` 必须是精确单行 SHA + UTC timestamp。对应 auditor 负例分别注入 snapshot 漂移、计数漂移和 malformed base。

---

### [PATCH-GATEWAY-RESTART-CLEANUP] Gateway 重启前脚本与 ignored 文件审计清理

| 字段     | 内容                                                                                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `scripts/{cleanup_transient_artifacts.py,cleanup_policy.json,final_upgrade_audit.py,test_cleanup_transient_artifacts.py}`, `hermes-update.sh`, `hermes-update.md`, `.gitignore`, `README.md` |
| **状态** | 🟢 自动化（每轮 preflight dry-run 审计；Step 8d restart 前 apply）                                                                                                                           |

**问题**：AI/浏览器/测试会话会在共享 `~/.hermes` 工作区留下 pager/slide 验证脚本、pytest/ruff 缓存、`__pycache__` 与 `.DS_Store`。只按文件名临时删除既可能漏掉被 `.gitignore` 隐藏的新产物，也可能误删并发 session 或正式运维脚本；仅依赖会话记忆判断“哪个脚本有用”又无法跨 AI 重建。Gateway restart 是运行态写屏障，如果重启前不先清理和审计，旧临时文件会跨 PID 延续并污染后续 diff、工具发现或下一轮自动化判断。

**修复**：新增 policy 驱动的清理器。`cleanup_policy.json` 对 outer 运维脚本和 `plugins/**/verify.sh` 做显式白名单（keep）/临时脚本黑名单（remove），所有未分类 script-like 文件进入 review；同时读取 outer 与 inner Git 的 `status --ignored`，把每个 ignored 路径按运行态/密钥/依赖白名单、缓存黑名单或 review 三态分类。持久化恢复状态 `.hermes-update-transaction`、原子锁目录 `.hermes-update-transaction.lock/`、0600 `.skills_prompt_snapshot.json`、Gateway graceful-exit receipt `.clean_shutdown`、machine-scoped `spawn-ledger.json*` 与 `config.yaml.corrupt.*.bak` 配置恢复快照都必须显式 keep：事务文件保存固定 `TARGET_SHA`，skills snapshot 保存经 manifest 校验的冷启动 prompt 元数据，`.clean_shutdown` 只在排空成功到下一次启动消费之间短暂存在、删除会把干净重启误判为 crash，spawn ledger 以 `(pid, create_time)` 证明可安全回收的 Hermes 子进程身份且损坏副本需保留审计，配置恢复快照则是用户可回滚证据；这些路径不能因只在异常或窄时间窗出现就落入 review 或被清理。当前上游 `WisdomStore` 在首次构造时惰性创建 `wisdom/`，其中数据库、SQLite journals、skill snapshots 与 consent/delivery state 属 profile 私有运行态，必须同时由 `.gitignore` 排除并由 policy keep；目录存在不构成启用共享的授权。规范 runner 预编译产生的 apps/evals/optional-skills/scripts/skills/tests/website 文档脚本 `__pycache__` 属确定可再生的 remove 类，运行时 agent/gateway/hermes_cli/tools/plugin 字节码则保持 keep。默认 dry-run，`--json` 输出完整 script/ignored audit、候选大小、跳过原因与 policy error；`--apply` 只把 remove 项移动到带时间戳的 macOS Trash 并保留相对路径，永不自动删除 review。近期临时脚本受 age gate 保护，Git-tracked 文件永不清理；pytest/CDP 等标记只在进程 cwd 位于当前 `~/.hermes` 根内或 argv 明确引用该根时阻断 apply，其他项目长期运行的 Codex/Claude/Gemini/Qwen 不得因 prompt 偶然含测试关键词误阻塞。`hermes-update.sh` preflight 每轮运行清理器自测与 `--dry-run --fail-on-review`；Step 8d 的唯一 restart 调用统一经过 `gateway_restart_with_cleanup()`，先 apply 再排空重启，清理失败、policy 漂移或未知 ignored/script 均使整轮非零。

**2026-09-03 process probe 加固**：活动进程探针过去把 `ps` 的 `OSError` 或非零退出当成空列表，使 cleanup apply 在“无法确认是否有并发测试/浏览器进程”时继续。现将两类错误都写入 `policy_errors` 并非零退出；只有探针成功且确认空列表时才允许清理。

**2026-09-03 workspace scope 收敛**：旧探针只在全机 `ps` 命令行做 marker 子串搜索，其他仓库的 AI review prompt 只要出现 `pytest` 等词就会阻断 Hermes restart；现场 `Astrolabe_2026H2` 的长期 `codex/claude/qwen` backfill 因而连续卡住 reconcile。现对候选 PID 继续 fail-closed 获取 cwd，并仅在 cwd 位于当前 Hermes 根、或 argv 明确引用该根时判为相关；进程已自然退出则忽略，cwd 探针不可用/报错仍阻断。这样既不干扰其他 workspace 的后台 agent，也不放过 Hermes 内部的测试/浏览器进程。

**2026-09-03 并发/终态二次加固**：事务锁不再发布“已 mkdir、owner 尚未写入”的半成品。acquire 先在私有 claim 目录写入 `pid + process-start fingerprint + random token`，再用原子目录 claim 建立所有权；缺失/损坏/stale owner 一律 fail closed，不自动抢占。release 只有在三元 owner 完全匹配时才删除自己的锁。stash apply 成功后再次确认 top OID，避免并发新 stash 被误删；EXIT 阶段 transaction/ref 删除或恢复状态写失败均令流程非零。final-audit 的首尾 snapshot 现绑定 outer HEAD/tree、inner HEAD/tree/index/worktree/untracked 内容、package-lock、review receipt、base 与 bundle；cleanup/runtime 后再次执行 repository checks，再比较最终 snapshot，关闭测试后 overlay/lockfile/clean commit 漂移窗口。进程 scope 同时改用路径边界与 cwd-relative argv 解析，`.hermes-copy` 不误拦、从父目录执行 `.hermes/tests` 不漏过。

**验证**：`scripts/test_cleanup_transient_artifacts.py` 另以临时双 Git 仓库证明嵌套 provider verifier 必须被审计、未知 verifier 为 review，以及 `fleet_restart_pending`、`shared-state.db*`、`wisdom/` 和 `hermes_wisdom/**/__pycache__` 分别保留为重启义务、协调数据库、私有 Wisdom 状态与运行时缓存。fixture 直接使用仓库 `.gitignore`，由真实 Git 证明 Wisdom 数据库及 WAL/SHM 不入库，再由真实 cleanup policy 证明 keep；缺少 ignore 或 keep 任一项均使回归失败。required scripts 显式覆盖 Step 8e 的 SC provider verifier。原有用例覆盖 keep/remove/review、仅黑名单移动、review 阻断、required 脚本缺失/未跟踪、事务/skill snapshot/`.clean_shutdown`/`spawn-ledger.json`/配置恢复快照 keep、runtime cache 与可再生测试缓存分流、`ps` 抛出异常和非零退出均 fail closed、外部 workspace agent 被忽略、Hermes cwd/argv/相对路径进程继续阻断，以及 Trash 相对路径。transaction self-test 覆盖 owner 原子发布、写失败、竞争者、错误 owner release、stash top 漂移与 EXIT 写删失败；auditor fault injection 覆盖 outer/inner HEAD/tree/index/worktree/untracked、package-lock/receipt、post-cleanup repository recheck 漂移，以及 Doctor 出现 pending gateway restart 告警时 final-audit 必须失败。preflight 成功时只打印 summary，失败时才展开 review/policy error。Step 8d restart 必须先 cleanup apply；Step 5d final-audit 在所有 pytest/formatter/verifier 之后再 apply，并以重复 dry-run 的 candidate/review/policy error 全 0 收尾。真机 restart 仍须证明 old PID → different new PID 和最终 verifier 通过。

**上游吸收判断**：这是外层工作区治理策略。只有未来 Gateway/update wrapper 原生提供可配置的脚本/ignored 三态清单、并发安全的可恢复清理、每次 restart 前强制执行和可供无状态 AI 消费的审计输出时，才可归档；单纯增加一个 `rm -rf cache` 命令不构成吸收。

---

### [PATCH-UPDATE-GIT-FETCH-RETRY] 升级 fetch 瞬时网络故障有界重试

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `hermes-update.sh`                                     |
| **状态** | 🟢 自动化（Step 3 早期 GitHub fetch 网络错误有界重试） |

**问题**：`hermes update` 在任何 checkout 或依赖变更前先 fetch `origin/main`，但本机到 GitHub 的直连与 LLM 专用代理都可能瞬时超时、TLS EOF 或 `SSL_ERROR_SYSCALL`。单次失败会让完整升级非零，即使下一次同一路径立即恢复；反过来无条件重跑整个 updater 又可能把认证、分叉、安装或迁移这类确定性错误重复三次，扩大副作用并掩盖根因。

**修复**：重试单元是首次 acquisition 的**裸 scoped fetch**（`git fetch --force origin main:refs/hermes-update/target`，`_acquire_upstream_target_with_retry`），不是整条 `hermes update`——官方 updater 在 PATCH-UPDATE-TRANSACTION-PIN 的固定 SHA 代理下运行、自身不做网络获取，因此无需也不得重试。仅当 fetch 日志命中 GitHub transport 特征（`Failed to connect to github.com`、`Could not resolve host: github.com`、同一行含 github.com 的 SSL/TLS EOF、Connection timed out/reset 等）且**不含**认证/权限特征（`Authentication failed`、`could not read Username`、`Permission denied (publickey)`、HTTP 401/403/407）时最多重试 3 次（2026-08-07 审计：删除只可能来自 Python CLI 的死分支 `Network error — cannot reach the remote repository`，并把裸 `Connection timed out|reset by peer` 收窄为须与 github.com 同行、新增认证负向前置过滤）。该失败点位于任何 checkout/venv/config 变更之前，动作可安全重入；一旦有效 SHA 写入专用 ref 即立刻固定、不再重试，后续错误只能进入 no-network reconcile。中间失败只显示简短 attempt 提示，远端 URL、Git config 和代理设置不在重试中持久修改。

**验证**：静态检查重试循环体只包含 `git fetch` + `rev-parse`、无 URL/config/代理写入；正则须含认证负向过滤（`! grep`）且不含上游 CLI 错误串。`bash hermes-update.sh --self-test-fetch-retry` 用 fake `git` 序列化：transport-fail → success 调用 2 次且 exit 0；连续 3 次 transport-fail 调用 3 次并保留非零；日志含 `Authentication failed` 时必须只调用 1 次。取得目标后再次执行必须走固定 SHA reconcile，fetch 计数不变（该场景已由 `--self-test-transaction` 的本地裸 remote 用例覆盖）。

**上游吸收判断**：当上游 `hermes update` 自身对 scoped Git fetch 提供等价的瞬时 transport 有界重试，且不会重试认证/安装/迁移错误时，可删除外层 Step 3 重试并归档。

---

### [PATCH-UPDATE-TRANSACTION-PIN] 单次升级固定 upstream 快照

| 字段     | 内容                                                                              |
| -------- | --------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `.gitignore`, `hermes-update.md`, `README.md`, macOS 运维文档 |
| **状态** | 🟢 自动化（显式 `--update` 获取一次；默认/`--reconcile` 固定 SHA、no-network）    |

**问题**：旧 playbook 同时要求 Step 1 先 `git fetch origin main`、Step 2 再执行自带 fetch 的 `hermes update`，又规定任何 patch/gate/脚本修复后必须重跑完整 updater。上游 main 持续前进时，同一次审计会依次纳入新的 commit，既不断改变 patch 基线，也触发重复依赖安装和 Gateway 重启；所谓“幂等复跑”实际变成一串新升级，无法定义本轮完成。`hermes --version` 还会隐式执行 update-check/fetch，使只读预检也可能越过获取边界。

**修复**：把官方获取和本地收敛拆为两个脚本模式。只有显式 `--update` 能在没有未完成事务时执行一次 `git fetch --force origin main:refs/hermes-update/target`，立即把专用 ref 固定为 `TARGET_SHA`；随后官方 updater 仍负责 merge、依赖、迁移、skills 和原生 restart，但通过临时 Git 代理执行——其内置 `fetch origin main` 成功 no-op，命令参数中的 `origin/main` 被替换为固定 SHA，因此不会发生第二次网络获取或目标竞态。默认无参数和 `--reconcile` 只校验/本地 fast-forward 到固定 `TARGET_SHA`，绝不做网络探测、fetch 或 pull。`.hermes-update-transaction` 以原子写 + `0600` 保存阶段、`old_sha`、`origin_before`、`target_sha` 和 `runtime_dirty`，逐字段验证且永不 source；失败/中断保留，完整 exit 0 才删除状态与专用 ref。若进程在 fetch 更新 ref 后、状态发布前退出，下一轮从专用 ref 重建目标；已有未完成事务时，即使误传 `--update` 也只能接管已有 SHA。无变化 reconcile 跳过 Gateway restart；HEAD/overlay 改变或失败事务留下运行态脏证据时才执行排空重载。版本摘要直接读取 checkout 的 `hermes_cli/__init__.py`，消除 `hermes --version` 的隐藏 fetch。

**2026-09-03 恢复与持久化加固**：pinned Git wrapper 现在先在完整 argv 中识别 network-capable 子命令，`git -C ... fetch`、`git -c ... ls-remote` 等 global-option 形态不再绕过网络门禁。每个关键 `_write_transaction` 都显式传播失败，HEAD 已前进但 `runtime_dirty` 未落盘时不得继续；重启成功后清 dirty 写失败同样令整轮非零。事务锁先在私有 claim 中写完整 `pid + process-start fingerprint + random token` owner，再原子建立 lock；缺失/损坏/stale owner fail closed，release 只删除三元身份匹配的自己。额外用户改动 stash 记录精确 OID，只恢复该对象；apply 前后都核对 top OID，冲突或并发新 stash 时保留现场、立即失败，不再 `reset --hard` 或误删他人 stash。成功 EXIT 的 transaction/ref 删除失败、失败 EXIT 的恢复状态写失败都转为非零。`--final-audit` 也持有同一事务锁，避免升级与审计并发。

**验证**：`bash -n hermes-update.sh` 与 `bash hermes-update.sh --self-test-transaction` 必须通过；self-test 在临时文件 round-trip **全部 7 个字段**（phase/old_sha/origin_before/target_sha/started_at/runtime_dirty + version 经 `_load_transaction` 校验）并断言权限 `0600`，另含 fail-closed 负例：symlink 状态、追加多余行、transaction 写失败、带 Git global options 的 fetch/ls-remote、锁 owner 半发布/写失败/竞争/错误 release、额外 stash 冲突与 apply 后 top OID 漂移、EXIT 写删失败和 final-audit 锁生命周期。wrapper 的 fetch 不下传、`HEAD..origin/main` 被改写为固定 SHA。补充边界：pinned wrapper 只对精确的 `fetch origin main` no-op，带 `--depth` 的 fetch 或 fork 同步的 `fetch upstream main` 会命中 exit 97 阻断分支（fail-closed 而非静默放网络），本机 origin 为官方仓库、fork 路径不可达。`--transaction-status` 无状态输出 `none`，有状态只打印经校验字段。静态检查默认/`--reconcile` 分支不调用 acquisition fetch、curl 或 `hermes --version`；只有 `_ACQUIRE_UPSTREAM=true` 能写专用 ref。隔离 fake 覆盖：首次 `--update` 固定目标、失败保留状态、相同事务再次 `--update` 不增加 fetch 计数、`--reconcile` 在 remote-tracking ref 前进后仍保持原目标、exit 0 删除状态/ref、非法/符号链接状态 fail closed。现场 no-change reconcile 必须明确输出 `no fetch/pull` 与 restart skipped，且 HEAD/PID 不变。

**上游吸收判断**：这是外层升级事务边界。只有未来官方 updater/wrapper 原生支持“单次获取后返回不可变 target token、失败跨进程恢复、后续 no-network reconcile、成功清理事务、无变化不重启”，并且 playbook 不再需要本地状态层时，才可归档。

---

### [PATCH-UPDATE-FLEET-RECEIPT-FRESHNESS] 陈旧失败 receipt 不得覆盖当前 live fleet 事实

| 字段     | 内容                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **文件** | `hermes_cli/update_cmd_fleet.py`, `tests/hermes_cli/test_update_receipt_live_freshness.py`                 |
| **状态** | 🟡 部分吸收：upstream `89c85b8466` 已按历史 profile 匹配 live successor；本地仅补严格 PID inventory 完整性 |

**问题**：`_pending_fleet_restart_needed()` 把 `logs/update_receipts/latest.json` 中未完成更新的旧 `plan.runtimes[].code_sha` 当作持久 restart 债务；如果后来通过外层 reconcile、人工 planned restart 或 supervisor 自愈让所有实际运行 Gateway 已加载当前 HEAD，但该历史 receipt 没有被重写，任何 `hermes` 命令仍反复提示“previous update ... did not restart”，`hermes update` 还会执行一次无必要 fleet restart。2026-09-05 深审现场复现：receipt 仍记录 2026-08-27 的旧 PID/SHA，而 control socket 返回的当前 Gateway PID `40781` 已明确为当前 `79445a496c...`，旧实现仍返回 pending。

**修复**：上游 `89c85b8466` 已提供 `_live_fleet_covers_receipt()`，按历史 runtime kind/profile 匹配当前 successor，并保留未知/缺失 profile 的义务。本地复用该判断，只在同一 live probe 内追加严格 PID 集合相等校验，删除原先重复的 pending 分支。显式 `fleet_restart_pending` marker 继续保持最高优先级并 fail closed；只有 fallback 来源是历史 receipt 时，额外读取当前 `collect_fleet_versions()`，并用严格的 `find_profile_gateway_processes()` 交叉核对实际 Gateway PID 集合。只有上游的历史 profile 覆盖成立，且该矩阵非空、PID 集合完整相等、每一行状态均为 `current` 且 `code_sha` 精确等于当前 checkout HEAD，才把旧 receipt 判为已被后续运行态收敛事实覆盖；空矩阵、探针异常、PID 集合不全、`unknown`、`stale`、`down` 或任一 SHA 缺失/不等仍保留 pending，避免用部分成功的探针消除真实 restart 债务。

**验证**：`tests/hermes_cli/test_update_receipt_live_freshness.py::test_startup_warn_ignores_stale_receipt_when_live_fleet_is_current` 构造旧失败 receipt 与新的完整 current fleet/PID 集合，旧实现会继续 warning，新实现必须让 `_pending_fleet_restart_needed()` 返回 false 且 startup 无输出；`tests/hermes_cli/test_update_receipt_live_freshness.py::test_stale_receipt_remains_pending_without_complete_current_fleet` 参数化覆盖空矩阵、unknown、stale、伪 current/wrong-SHA 与 mixed fleet，全部必须继续 pending。`test_receipt_successor_requires_complete_inventory_and_profile` 证明漏报 live PID、inventory 异常与错 profile 均保留 pending；在裸 upstream 函数上注入前两种故障会错误清除 pending，本地补充均拒绝。上游既有 receipt-skewed catch-up 回归继续覆盖 live matrix 无法证明新鲜时必须执行 restart。Step 8b 同时锚定严格 PID inventory、live fleet、`state=current`、HEAD SHA 与上述正反回归；full evidence 的调用轨迹必须触达生产模块。

**上游吸收判断**：历史 receipt 的 successor 判定已吸收；剩余严格 PID inventory 尚未吸收。当 upstream 的 pending-restart 判定原生以当前完整 live fleet 身份为终态权威，只在无法证明全部运行实例匹配 checkout 时才回退历史 marker/receipt，并有“旧失败 receipt + 当前全绿 fleet 不再告警/重启”的回归后，可删除本补丁。

---

### [PATCH-SKILLS-MIRROR-METADATA] Skills 镜像保留本地 runtime 状态

| 字段     | 内容                                    |
| -------- | --------------------------------------- |
| **文件** | `hermes-update.sh`, `~/.hermes/skills/` |
| **状态** | 🟢 自动化（Step 4b rsync gate）         |

**问题**：Step 4b 原先用裸 `rsync -a --delete` 把上游 skills 镜像到运行目录，会删除源树中不存在的 `.bundled_manifest`、`.curator_state`、`.usage.json` / `.usage.json.lock`、`.hub` 和 `.archive` 等本地运行态。前者被迫反复重建，`.curator_state` 会丢失 curator 的 pause/run count/last-run 状态，`.usage.json` 会丢失每个 skill 的 usage、pin、sync 和 curator 生命周期记录；同时 `|| true` 吞掉 rsync 非零，复制失败也可能被显示成“已同步”。测试或运行时在 `hermes-agent/skills` 下生成的 `__pycache__/` / `*.pyc` 也会被误当作上游内容镜像到 runtime skills，导致同一 SHA 因执行顺序不同出现 `+70` 这类假漂移。

**修复**：从 delete 集合排除根级 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.curator_backups` / `.curator_suppressed` / `.hub` / `.archive`，并排除 `__pycache__/` / `*.pyc`，只镜像上游拥有的 skill 内容；显式捕获 rsync 退出码，失败时记录输出、设置 `FINAL_RC=1`，成功时继续报告 `+/~/-` 并确认 runtime state 与可再生 bytecode cache 保留/排除策略生效；bundled skills 源目录整体缺失同样 `FINAL_RC=1`（2026-08-07 审计补：属"命令未执行/产物缺失"级事务失败，此前仅 warn 且会连带静默跳过 Step 8c 的 llm-wiki 再播种）。（2026-08-06 并入）成功路径把 `--itemize-changes` 中每条新文件 `>f+++` 与删除 `*deleting` 分别以 `+ added:` / `- deleted:` 留存到升级日志：此前同日两轮各出现 `-94`、终态同 SHA 复跑又出现 `+70` 而无路径记录，事后无法判定具体变更集合；双向清单让下一位无状态 AI 能把批量消失/恢复与同期进程日志关联。

**验证**：`audit_skills_mirror` 在独立 shell 与临时 HERMES_HOME/HERMES_AGENT 下执行 `hermes-update.sh` 实际 Step 4b；只替换日志函数，rsync、保护参数、删除与失败传播均来自生产代码，不另写参数副本。隔离临时目录验证新增/更新、孤儿清除、九类 runtime state 保留、现有热缓存保留与源端 bytecode 不传播。`test_skills_mirror_probe_executes_the_update_phase` 分别删除 usage 保护、pyc 排除或 stale 删除参数，均必须被原有 probe 拒绝。

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

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在；`scripts/test_patch_evidence.py::audit_socks_dependency` 在 Hermes venv 中真实导入 `socks` 并核对 `python-socks==2.8.1`，缺包或 pin 漂移均非零。

**上游吸收判断**：当上游 `feishu` extra 与 `LAZY_DEPS["platform.feishu"]` 都显式声明兼容的 SOCKS 依赖，并通过代理连接回归后，才可移除本补丁；任一路径缺失都必须保留。

---

### [PATCH-OPENCLAW-TOKEN-MIGRATION] OpenClaw 迁移不写废弃 gateway token

| 字段     | 内容                                                                                                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md`, `website/i18n/zh-Hans/.../guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                                                                                         |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；英文迁移文档与 zh-Hans 翻译（2026-08-07 审计补齐——此前中文文档仍保留该映射行、且全树仅剩这一处引用）同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本、英文文档与 zh-Hans 文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token` / `Gateway 认证 token`；`scripts/test_patch_evidence.py::audit_openclaw_token_migration` 用含 gateway auth token 的临时 OpenClaw fixture 执行 dry-run，断言迁移报告、环境目标和归档输出都不生成该废弃 token。

**上游吸收判断**：当上游迁移脚本不再写入废弃的 `HERMES_GATEWAY_TOKEN`，且迁移文档同步移除该映射后，才可移除本补丁；当前上游两处仍未吸收。

---

### [PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION] Hermes 不继承用户 shell 凭据

| 字段     | 内容                                                                                  |
| -------- | ------------------------------------------------------------------------------------- |
| **文件** | `hermes_cli/env_loader.py`, `tests/hermes_cli/test_env_loader.py`, 外层 `config.yaml` |
| **状态** | 🟡 本地安全边界；`secrets.ignore_ambient_credentials: true` 时启用                    |

**问题**：用户的 shell 会 source `~/.secrets`，其中的 `DASHSCOPE_API_KEY`、`GEMINI_API_KEY` 等变量随父进程进入 Hermes。旧 `load_hermes_dotenv()` 只清理少数 profile routing key，有意保留所有 shell provider 凭据；credential pool 随后把这些用户侧变量自动 seed 为 Hermes 模型凭据。结果是未写入 `~/.hermes/.env`、未进入 `config.yaml` 主链的 provider 仍可被模型选择与辅助路由消费，跨越了用户侧环境与 Hermes 配置的所有权边界。

**修复**：新增 opt-in `secrets.ignore_ambient_credentials`。启用后，加载 `~/.hermes/.env` 之后、执行 Hermes 显式 secret sources 之前，删除所有不在该 profile `.env` 中声明的已知 Hermes provider/tool 环境变量，并覆盖 `GOOGLE_APPLICATION_CREDENTIALS`、AWS credential chain 等 SDK 直读键；`PATH`、`HOME` 和无关用户环境变量不动。Bitwarden/OnePassword/managed env 等明确配置的 Hermes secret source 在清理后运行，仍可合法补回凭据。历史上由 ambient env seed 的 Alibaba、Gemini、Copilot pool 条目用 `hermes auth remove` 清理并 suppress，避免旧 token 继续被读取。

**2026-09-03 fail-closed 加固**：当 `config.yaml` 存在但语法损坏、不可读、顶层不是 mapping，或 `secrets` 节不是 mapping 时，不能把空 `{}` 当作“用户未启用严格模式”。这类异常现在统一按严格隔离处理，先 scrub ambient credentials；只有配置文件确实不存在时才保留旧的非严格默认。

**验证**：`test_strict_profile_ignores_ambient_hermes_credentials` 证明 profile `.env` 中的 Azure key 保留，而 shell 的 DashScope/Gemini/Google credential path 被清除、无关变量不受影响；`test_strict_profile_without_dotenv_still_ignores_ambient_credentials` 锁定 strict profile 没有 `.env` 时同样 scrub；`test_malformed_config_fails_closed_for_ambient_credentials` 对损坏/非 mapping 配置做 fault injection，证明 ambient key 不会复活；`test_strict_profile_allows_explicit_secret_source_after_scrub` 证明 Hermes 显式 secret source 可在清理后重新注入。Step 8b 同时检查配置开关、生产函数和测试名。终态 fresh process 中 `hermes auth list` 不再出现 Alibaba、Alibaba Coding Plan、Gemini 或 Copilot，只保留 Hermes 自有 Azure pool；Bedrock/Vertex 继续走 IAM role / service-account 路径。

**上游吸收判断**：上游提供 profile 级“只信任本 profile `.env` 与显式 secret sources、拒绝 ambient shell provider credentials”的等价开关，并覆盖 credential pool 自动 seed 与 SDK 直读键后可归档。

---

**类别：Feishu 接入、安全与会话语义**

### [PATCH-FEISHU-GROUP-ADMISSION] 群聊触发、本人代答策略与当前发言人完整性

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/auxiliary_client.py`, `plugins/platforms/feishu/adapter.py`, `gateway/{authz_mixin.py,platforms/base.py,run.py,run_inbound.py,run_turn.py,session.py,session_state.py}`, `tests/agent/test_auxiliary_client.py`, `tests/gateway/{feishu_helpers.py,test_feishu.py,test_feishu_bot_admission.py,test_feishu_bot_auth_bypass.py,test_session.py}`, `website/docs/{reference/environment-variables.md,user-guide/messaging/feishu.md}`；外层 `config.yaml`、私有 `people.yaml` 与 `my-skills/research/llm-wiki/SKILL.md` 不进 bundle |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |

**问题**：群聊需要同时支持 `@bot` 与 `@配置本人账号` 触发、近期群消息回填和纯 @ 意图推断；共享 session 还必须防止 owner profile、引用内容、历史末位发言人或跨发送者 debounce 被误认成当前提问者。第三方 `@配置本人账号` 时，旧策略会无条件替本人继续回答：当发送者把未披露的 AI 代写内容直接投给本人时，既浪费本人注意力，也让本人的助手继续参与这种不礼貌的沟通。群授权也不能借通配符放开 DM。原纯 @ 分支硬编码排除 `p2p`，导致主会话里回复一条合并转发后只 @Bot 会在剥离 mention 后成为空文本并被静默丢弃。

2026-09-04 在 Data Pipeline Workshop 实抓到身份豁免缺口：琛哥本人发送明显带 Markdown/规整列表的消息并 @自己时，旧实现因 `sender_is_configured_human` 直接跳过分类器，日志中没有任何评分记录；这不是阈值过高，也不是模型给了低分。门禁现改为对事不对人：任何发送者只要触发 `@配置本人账号` 且其本地阈值启用，就先评分；发送者是否为 configured human 不再构成绕过条件。

2026-09-05 在同一群的真实复测又暴露引用入口缺口：新消息正文只有 `@周琛`，但它直接引用了一段约 3,000 字、包含重复原生 Markdown 加粗和规整编号结构的内容。旧分类器虽收到了 quote，却被 system prompt 明确要求“只判断 current_message、quote 仅作上下文”，因此稳定返回 `0.0` 并继续代答；这不是阈值或运行态失效，而是把被主动投递给真人的正文放错了评分槽位。

**修复**：实现 assistant-user/configured-human 两类触发与身份说明、群历史回填、默认关闭且可配置的 `bare_mention_intent`、`FEISHU_GROUP_ALLOWED_CHATS` 群授权；把 bot mention 设为最高触发优先级，批处理合并判定纳入发送者（`_text_batch_is_compatible` 校验 user_id/user_id_alt/user_name；`_text_batch_key` 本身与上游一致），并在 system prompt 标注 current author（**user-turn 侧的 sender 前缀与 `[New message]` 拼接已被上游吸收**——d1afa160 起 `_prepare_inbound_message_text` 原生对 shared multi-user 会话做 `[sender]` 前缀与 channel-context 拼接，本地不再携带该 hunk，system prompt 的 current-author 块仍为本地）。第三方 `@配置本人账号` 新增本地 AI-authorship admission：独立的无工具辅助模型只接收匿名化后的当前 @消息正文与其直接 quote 的单条消息，quote 仅帮助判断自然承接，不评价 quote 作者，也不读取群历史、长期 session、sender ID、人物画像正文、个人阈值、附件回填或 Gödel 先前回答；模型请求的完整变量集合固定为 `current_message` + `quoted_message`，问话人 ID 只在本地精确匹配 `people.yaml` 后选取阈值，匹配记录和阈值绝不进入模型请求，同一消息与 quote 不因发送者画像而改变评分输入。模型按非穷举的飞书风格信号做整体概率判断，返回 `{probability, disclosed}` 后由 adapter 将任意有限数值执行 `clip(0,1) + round(...,1)`，再做本地阈值比较。全局 `assistant_user_ai_probability_threshold` 放在 `config.yaml`，`>=1.1` 关闭；当前问话人的 `people.yaml` 同名字段按 Feishu open_id/user_id/union_id 精确匹配并覆盖全局值，非法个人值回退全局。未披露且评分达到有效阈值时，本地代码在主 Agent/工具链之前尝试发送固定拒绝文案，不公开评分或检测细节；只有拒绝文案成功送达才短路并为该发送者启动 `assistant_user_ai_cooldown_seconds` 冷却。冷却期内，该发送者在任意群里再次以 `@配置本人账号`、`@Hermes` 或两者同时 @ 的方式触发时，都不调用分类器或主 Agent，而是从本地短句池随机选择一条拟人化、生气但不攻击个人的双语回复，中文在上、英文在下，并将动态剩余秒数加粗；未触发机器人的普通群消息和 DM 不受此冷却影响。计时从首次成功拒绝开始、不会因重复触发顺延、跨群按发送者生效，`0` 可关闭，Gateway 重启会清空。首次拒绝文案同样使用中文在上、英文在下，明确说明 AI 对 AI 的平等交流可以接受，引导使用 AI 的发送者直接艾特“我”，而不是把未披露的 AI 生成内容直接艾特琛哥；随后仅批评这种不透明行为、不攻击个人，并代表琛哥拒绝回答。分类器异常或超时、拒绝文案或冷却文案发送异常/失败时均 fail open，继续原代答链路；低于阈值或当前消息已明确披露 AI 使用时同样正常进入。具体人员阈值只保存在本机私有 `people.yaml`，受跟踪文档不登记姓名或 ID。开启 `bare_mention_intent` 后，群聊和 DM 中明确提及 bot 自身的纯 @ 都进入意图推断；引用消息时以引用内容为主题且只读取一次，未引用时使用既有会话历史，空文本但未 @Bot 仍丢弃。技术问题提示显式要求先读外部 `my-skills` 的 `llm-wiki`，所有 wiki 文件调用必须携带 `~/.hermes/wiki` 路径，禁止用 terminal 探测；官方 bundled `llm-wiki` 不再 patch，由 `skills.hide_bundled` 默认屏蔽。

判别调用本身按短路径执行：生产配置使用 `gpt-5.5`、`reasoning_effort: none`，超时通过公开配置 `auxiliary.feishu_ai_authorship.timeout` 控制，当前为 30 秒；调用显式关闭跨 provider fallback，也关闭同 provider transient retry，因此一次超时不会扩增成第二次 30 秒等待，并会直接回到正常回复链路。Markdown 校准不再要求消息同时“特别长”：重复原生 `**bold**` 与规整列表若再叠加平行句式、完整过渡或总结性收口，通常进入 `0.8–1.0`，不能因内容具体、承接上文或事实合理而自动降分。2026-09-04 用 Data Pipeline Workshop 实际漏判原文在独立、无画像 canary 中由旧 prompt 的 `0.3` 提升为 `0.9`；该实测只作为校准记录，运行时仍以每次实时模型结果为准。

直接引用的处理保持最小且可解释：正常含正文的 @消息仍只评分当前 prose，并把 quote 作为自然承接上下文；若当前正文去掉匿名化 `@person` 后只剩空白或标点，则该发送者实际上是在把直接引用内容投递给 configured human，adapter 将有界 quote 提升为 classifier 的 `current_message`，原 quote 槽清空。这个判断不推断 quote 作者身份，只判断被本次 @动作主动呈现的文本；无 quote、普通短句或显式 AI 披露仍走原逻辑。2026-09-05 对现场消息的只读 replay 在旧输入布局下为 `0.0`，提升引用后同一生产 classifier 返回 `0.9 / disclosed=false`。

**验证**：Step 8b 独立 gate 检查 trigger/settings/history/bare-mention/wiki sentinels、AI 阈值与冷却配置桥、`test_ai_probability_threshold_uses_people_override_before_global`、`test_ai_authorship_classifier_receives_only_current_and_direct_quote`、`test_ai_authorship_classifier_bounds_both_text_inputs` 与 `tests/gateway/test_feishu_bot_admission.py::test_process_inbound_message_high_ai_score_sends_local_refusal_with_quote_only`、DM 纯 @ 回归、group allowlist（含 `test_feishu_group_allowed_chats_wildcard_authorizes_groups_only`——wildcard 不放开 DM 的安全断言，2026-08-07 起入 gate）、current-author system prompt（本地）与 `[New message]` 上游 body-prefix 回归锚点、bot 优先级和跨发送者不合并测试。Full evidence 显式绑定按 ID 命中的个人覆盖、独立上下文分类和结构化解析；高分且拒绝发送成功才短路，`test_ai_authorship_classifier_failure_falls_back_to_normal_reply` 与 `test_ai_authorship_refusal_delivery_failure_falls_back_to_normal_reply` 锁定分类失败和投递失败均继续正常回复；`test_successful_ai_authorship_refusal_starts_sender_cooldown`、`test_ai_authorship_cooldown_response_pool_is_short_and_does_not_name_hermes`、`test_ai_authorship_cooldown_zero_does_not_skip_classifier`、`test_expired_ai_authorship_cooldown_runs_classifier_again`、`test_active_sender_cooldown_short_circuits_every_group_mention_trigger` 与 `test_active_sender_cooldown_does_not_affect_another_user` 锁定成功拒绝才启动冷却、双语随机短句与剩余秒数、冷却期不推理、`@本人`/`@Hermes`/双 @ 全覆盖、其他用户隔离、跨群按发送者生效、过期恢复和 `0` 关闭。`test_group_turn_body_keeps_current_author_next_to_question` 与 `test_admit_accepts_realistic_bot_at_bot_group_event` 确保 Gateway config bridge、people profile lookup、consumer、session/authz 与 Feishu adapter 都进入调用轨迹。其余定向测试覆盖全局 `1.1/1.2/2.0` 关闭、个人 `0.8` 覆盖、个人 `1.1` 反向关闭、非法值回退、控制字段不进入人物画像 prompt、分类器只收到当前句和直接 quote 且分别限制为 4000/2000 字符、任意有限分数经 `clip(0,1) + round(...,1)`、低分/显式披露进入 Agent、拒绝话术不公开概率且只批评行为不攻击个人。（2026-08-03 修正：旧哨兵 `_with_current_author_prefix` 在 v0.19.1 冲突解决轮已被重构移除，gate grep 一直误报 inactive；现改为真实锚点。）

引用入口新增 `tests/gateway/test_feishu_bot_admission.py::test_bare_human_mention_promotes_quoted_ai_prose_into_authorship_check`：用真实 text payload、configured-human mention 与 parent message 穿过 Feishu normalize、trigger、quote fetch、生产 classifier prompt 和本地 refusal，断言裸 @ 时 quote 被提升为唯一评分正文且高分后不进入主 Agent；既有 current-message + quote 用例继续证明当前消息有实质正文时 quote 只作上下文。

补充边界回归：低分或显式披露放行时，分类用的匿名副本不得覆盖原始消息；后续仍按原链路解析 sender/group 画像并进入主 Agent。隔离只约束前置分类器，不得削弱正常回复的画像与上下文能力。

辅助调用的单次预算由 `tests/agent/test_auxiliary_client.py::TestTransientTransportRetry::test_async_call_can_disable_same_provider_transient_retry` 锁定，`test_feishu_ai_authorship_uses_configured_timeout` 锁定公开 timeout 配置及显式调用覆盖优先级；本人自发并 @本人和第三方 @本人的高分短路由 `tests/gateway/test_feishu_bot_admission.py::test_process_inbound_message_high_ai_score_sends_local_refusal_with_quote_only` 的两个参数实例共同覆盖。

群回复的 @语义也归属于 admission/当前发言人完整性：当前 turn 单独保留发送者的 Feishu `open_id`，不改变 session identity；能通过热加载 people 索引解析到 open_id 的正文显式 `@姓名`/别名仍在原位置转换，但 transport metadata 指定的“当前消息者”是独立语义：无论模型是否又在正文开头、句中、表格单元格或多次写出该姓名，最终都只保留一个原生 mention，且位于第一条可见富文本内容的首位；正文中的重复目标改回普通姓名，其他人的显式 mention 仍留在原位置。普通 prose 把首位 mention 内联在同一 Markdown 流，避免无意义换行；正文以 GFM 表格、无序/有序/任务列表、分隔线或 fenced code 等块级 Markdown 开头时，mention 占独立 `md` 行，让正文的第一个块标记保持为首 token。2026-09-06 在 Data Pipeline Workshop 实抓的 Task 67 `working` / `failed` / `completed` 三条回包均为 `<at ...>姓名</at> | Field | Value |`，飞书因此把表格拆成普通 text/link 元素，证明旧内联策略破坏了表格块边界；扩展回归随后确认列表与分隔线存在同类风险。这里仍不使用独立 `at` + `md` post 元素；mention 行本身也是 `md`，post 被 API 拒绝后的 text fallback 保留相同原生语法。`tests/gateway/test_feishu.py` 的 reply-target、重复姓名/别名、块级 Markdown、formatter 组合、表格内其他人 mention、代码字面量、真实 `send()`、分块及 post→text fallback 用例共同锁定该契约；非 notify 的进度/状态消息不自动补 @。

**上游吸收判断**：上游同时具备等价的 Feishu 多触发 admission、全局默认 + people profile 按稳定 ID 覆盖的第三方 @本人 AI 代写评分/拒绝门禁、群历史/纯 @ 意图、按发送者隔离的 batching 和多用户 current-author 契约后可归档；工具权限隔离不属于本补丁。body-prefix 子项已吸收（见修复段）；system prompt current-author 块、AI 代写拒绝策略与 Feishu admission 机制仍为本地。

---

### [PATCH-FEISHU-MISSED-EVENT-BACKFILL] Feishu 断线/重连漏消息补偿

| 字段     | 内容                                                                                                                                                                                                                                                                              |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/{test_feishu.py,test_config.py}`, `website/docs/{reference/environment-variables.md,user-guide/messaging/feishu.md,user-guide/configuration.md}`（配置桥由插件 `_apply_yaml_config` 提供；本机 `config.yaml` 启用恢复参数） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                     |

**问题**：Feishu `history_backfill` 只在 Hermes 已收到一条触发消息后补上下文，不能主动发现断网、睡眠或 stale WebSocket 期间漏掉的 `@Hermes` 触发事件。SDK 内部自动重连成功也不会通知 adapter 做补偿扫描，导致漏消息可能等 Feishu 服务端迟迟推送旧事件后才被回复；用户手动 quote 原消息再 @Hermes 触发回答后，旧事件晚到又会让 Hermes 重复回答同一问题。初版补丁另有一处主会话盲区（2026-08-08 修复）：回放重建事件用 `chat_id.startswith("oc_")` 推断 chat_type，而飞书 p2p 会话 ID 同为 `oc_` 前缀，owner DM（home channel）虽在扫描目标里，回放消息却被误标为 group、被群 mention gate 以 `trigger_mention_missing` 拒掉——主会话事实上没有恢复补偿；且 `get_chat_info` 读的 `chat_type` 是 private/public 可见性字段（DM 实测为 `None`），不能作判别源。

**修复**：新增 `missed_event_backfill` 独立恢复路径：启动、gateway reconnect 和 Lark SDK `on_reconnected` 后，在主 asyncio loop 上调度一次有界扫描。扫描目标只来自 `missed_event_backfill_chats`、Feishu home channel、显式 `group_rules` 以及 `~/.hermes/groups.yaml`，不把通配符 `group_rules: "*"` 当作租户枚举来源；每个目标 chat 通过 `im.v1.message.list` 拉取最近窗口，按时间正序只重放未见且通过原 `_admit()` 的消息，随后进入同一 `_handle_message_event_data()` / `_process_inbound_message()` 管道。手动 quote/reply 已触发的消息在 dispatch 后把 `parent_id` / `upper_message_id` / `root_id` 标记为已覆盖，使后续 delayed push 或恢复扫描命中原消息 ID 时被 dedup 跳过。配置桥接同时支持 `missed_event_backfill*` 和 `ws_reconnect_*` / `ws_ping_*` 顶层 `feishu:` 键。**主会话 DM 回放（2026-08-08 并入）**：`get_chat_info` 补采 `chat_mode`（p2p/group/topic，实测 DM 返回 `p2p`）存入 `raw_mode`；回放前按 chat 元数据解析 event chat_type，`raw_mode == "p2p"` 走 p2p lane（admit 与 session 路由和真实 DM 事件一致，不受群 mention gate 约束），元数据缺失/查询失败一律 fail-closed 按 group 处理，恢复扫描不可能放宽真实群的准入；DM 的 quote 覆盖去重由本就无条件执行的 `_mark_related_message_ids_covered` 自动继承。Hermes 自己的历史回复由 `_admit` 的 bot/self 分支拒绝，不会自我回放。已知并存（有意不动）：① 上游 `_fetch_last_message_in_thread` 仍有函数内局部 `ListMessageRequest` 导入，会遮蔽本补丁的懒加载全局——行为无差异，删除它要为纯整洁改写上游函数、扩大 diff 面，留待上游自行收敛；② `get_chat_info` 的 `type`/`raw_type` 仍源自 `chat_type` 可见性字段（实际恒映射为 `dm`），活跃入站路由由事件自带 chat_type 兜底、行为正确，纠正它会波及群/话题群既有路由面，本补丁只新增 `raw_mode` 不动旧键。

**验证**：Step 8b 单独检查 missed-event runner、per-chat backfill、SDK reconnected hook、quote-covered dedup helper、`ListMessageRequest is not None` fallback、`raw_mode` 采集与 `chat_info.get("raw_mode") == "p2p"` 判别锚点、config 桥接、用户文档和七条回归测试。测试覆盖：已知群里的未见 @ 消息会在 backfill 中触发一次 dispatch；quote+@ 覆盖的 parent 后续 backfill 不再 dispatch；SDK `on_reconnected` hook 保留原 callback 并调度 backfill；home channel DM 的未见普通消息（无 @）dispatch 一次且 source.chat_type 为 dm、bot 自身历史回复不回放（`test_missed_event_backfill_dispatches_unseen_dm_from_home_chat`）；DM quote 已答复的原消息不再 dispatch（`test_missed_event_backfill_dm_quote_covered_parent_not_redispatched`）；chat 元数据 fallback（无 `raw_mode`、`type` 声称 dm）时无 @ 消息不放行（`test_missed_event_backfill_unknown_chat_mode_falls_back_to_group_admission`）。`test_bridges_feishu_history_backfill_from_config_yaml` 显式覆盖 `gateway/config.py` → adapter settings 的配置桥。`chat_mode` 字段语义已用真实 chat.get 对主会话/群各取证一次（2026-08-08：DM `chat_mode='p2p'`/`chat_type=None`，群 `chat_mode='group'`/`chat_type='private'`）。规范 runner 结果：`tests/gateway/test_feishu.py` 136 passed / 0 failed（2026-08-08），`tests/gateway/test_config.py` 57 passed / 0 failed（2026-08-05）。

**上游吸收判断**：上游 Feishu adapter 若提供等价的启动/重连后 missed trigger replay（含 DM/p2p 目标按 `chat_mode` 判别准入、失败 fail-closed 为 group）、SDK 内部 reconnect 通知接线、已 quote 触发回答的原消息 ID 覆盖去重、以及受控目标 chat 发现策略，可归档本补丁；单纯加强 WebSocket ping/reconnect 或上下文 `history_backfill` 不构成吸收。

---

### [PATCH-FEISHU-GROUP-SCOPE] 群聊独立 capability namespace

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/{session_context.py,run.py,run_busy.py,run_inbound.py,run_turn.py,run_turn_runner.py,slash_commands.py,slash_commands_model.py,slash_commands_session.py}`, `hermes_cli/tools_config.py`, `tests/gateway/test_session_env.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_background_command.py`, `tests/gateway/test_verbose_command.py`, `tests/hermes_cli/test_tools_config.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                                                                                     |

**问题**：Feishu DM 与群聊原本都只解析 `platform=feishu`，无法对同一 bot 的 owner DM 和共享群配置不同 toolsets/skills。初版补丁虽然新增了 source-aware helper，并把 session context 正确写成 `feishu_group`，但主 `_run_agent_inner`、busy ack、最终 reasoning/footer、proxy streaming、background task 和 slash commands 仍直接用 `source.platform` / `event.source.platform` 取 key。结果静态配置和 sandbox verifier 都显示群策略正确，真实群 Agent 却拿到 DM 的 terminal/drive 工具面与 `tool_progress: new`：工具调用链被发送到群里，受控文档入口 `feishu_doc_manage` 没有进入 Agent schema，模型转而调用 `terminal` / `feishu_drive_add_comment` 再被 sandbox 拦截；群内 `/verbose` 等命令还可能读写 DM 配置。

**修复**：新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`；Feishu group/forum/channel/thread 映射到 `feishu_group`，DM 仍为 `feishu`。所有按具体会话解析 display、toolsets、busy ack、reasoning/footer、proxy streaming、background task 和 slash-command 配置的运行路径统一调用 `_platform_config_key_for_source()`；仅 helper 内部允许退回通用 `_platform_config_key(source.platform)`。平台工具解析和保存逻辑识别该独立 key；群工具面不被默认能力补宽的机制是 `platform_toolset_options.<key>.recover_platform_tools: false` 的显式短路（`feishu_group` 不在 `PLATFORMS` 注册表内，靠该开关而非独立分支阻断 native recovery）。

**验证**：Step 8b 单独检查 session context key、`return "feishu_group"`、`run.py` 与拆分后的 `run_*` / `slash_commands_*` 所有 source/event consumer 不再绕过 source-aware helper、tool recovery 开关，以及 `test_set_session_env_sets_feishu_group_config_key` / `test_get_platform_tools_feishu_group_uses_independent_config`。`test_feishu_group_runtime_scope_hides_progress_and_uses_group_tools` 穿过真实 `_run_agent` 边界作 DM 正例和两个群负例：DM 仍收到 `new` 工具卡并包含 `terminal`，群聊零 send/edit 且 Agent toolsets 包含承载 `feishu_doc_manage` 的 `sandbox_group`、不含 `terminal`。`test_successful_task_sends_result` 的 adapter fixture 显式把同步 `toolsets_for_source` 设为 `None`，防止 `AsyncMock` 自动生成 coroutine、掩盖 background source-aware 解析链；`test_split_command_modules_keep_source_aware_platform_scope` 锁定 reasoning/manual-compression 两个拆分模块仍使用 source-aware key。`test_feishu_group_updates_group_scope_without_mutating_dm` 从 `/verbose` 写回边界证明群配置独立更新、DM 值保持不变。

**上游吸收判断**：上游提供等价的 per-chat-type capability namespace，且 Feishu DM/group 可以独立解析工具配置时可归档。

---

### [PATCH-PLATFORM-CAPABILITY-SCOPE] 平台级 skill allowlist 与只读工具集

| 字段     | 内容                                                                                                                                                                                                                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/{skill_utils.py,prompt_builder.py,skill_commands.py}`, `tools/skills_tool.py`, `hermes_cli/{config_defaults.py,prompt_size.py}`, `toolsets.py`, `tests/agent/test_skill_commands.py`, `tests/hermes_cli/test_skills_config.py`, `tests/tools/test_skills_tool.py` 及其他对应 tests/docs |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                  |

**问题**：`skills.disabled` 不能表达“某平台只允许指定 skill”；完整 `skills` toolset 又同时暴露 `skill_manage`。文件工具也缺少只读组合，平台配置容易无意带入写能力。

**修复**：严格读取统一验证 skills mapping、platform_allowed/platform_disabled mapping 与 skill-name 列表类型；冷读和已有 permissive cache 命中都执行同一校验。错误类型不等价于未配置：allowlist deny-all、disabled wildcard；合法缺省、空列表和显式通配语义继续保留。新增 `skills.platform_allowed.<platform>`，并让 prompt、list/view 和 config-var discovery 共用同一解析；增加 `skills_readonly`（list/view）与 `file_readonly`（read/search）内部工具集；新增 `skills.hide_bundled`（默认 `true`），官方 bundled Skills 仍由 updater 镜像但从正常发现、prompt、view 和 slash command 路径隐藏，配置的 external dirs（如 `~/.hermes/my-skills`）不受影响。分类 skill 的规范名按短名匹配 allowlist，避免 `productivity:feishu-docs` 被错误拒绝。两个通配语义随实现存在并有测试覆盖：`platform_allowed: ["*"]` 为显式 allow-all 逃生口，`platform_disabled: ["*"]` 为全禁（`test_platform_disabled_wildcard`）；本机配置均未使用。

2026-08-19 与上游 project-local skill discovery 融合时，保留其 `project_dirs` cache key、trust/quarantine 与项目 skill 扫描，同时让 snapshot、cold scan 和 project scan 三条可见路径统一先过平台 allowlist/disabled 判定；两类治理是正交叠加，不得用其中一个覆盖另一个。

2026-09-03 二次审计补齐 slash disabled 语义：扫描时显式传入 task-local `HERMES_SESSION_PLATFORM_CONFIG_KEY`，进程级 `HERMES_PLATFORM` 不得把 `feishu_group` 降回 `feishu`；`platform_disabled: ["*"]` 通过统一 helper 全禁。skill policy 配置存在但损坏时，allowlist 视为 deny-all、disabled 视为 wildcard，避免菜单/描述在异常窗口泄露。

与上游 `skill_view` 的 repeat-view dedup 存根共存时必须保持**先 allowlist 过滤、后 dedup 存根**的执行顺序，防止被 allowlist 拒绝的 skill 因 dedup 缓存返回旧内容（2026-08 上游 `2a3a7e6f5` 融合时确立的顺序不变量，后续该函数任何 3-way 融合都必须复核）。

**验证**：`test_malformed_config_fails_closed` 扩展为实际 YAML 的语法错误、非 mapping section、错误 allow/disabled mapping 和非名称列表，并先做 permissive 读取填充 cache，再经真实 skill tool 的 allow/disabled 入口断言失败时拒绝访问；合法空配置作为反例保留。Step 8b 独立检查 `get_allowed_skill_names` 的三个调用面、`hide_bundled` 默认/显式关闭、qualified-name 回归，并用 venv python **精确断言**两个只读工具集的成员集合（`skills_readonly == {skills_list, skill_view}`、`file_readonly == {read_file, search_files}`；2026-08-07 审计修复：旧 gate 对四个工具名的裸 grep 全部能被上游既有 `skills`/`file` 工具集满足，永远不会失败）；`test_hidden_bundled_skill_is_not_discovered_but_external_is`、`test_qualified_local_skill_allowed_by_bare_name`、`test_scan_uses_session_platform_config_key_allowlist`、`test_scan_uses_session_platform_config_key_disabled_rules` 与 `test_scan_fails_closed_when_skill_policy_config_is_malformed` 覆盖核心 allowlist/disabled/discovery、wildcard、损坏配置及 Feishu DM/group cache 隔离；`TestIsSkillDisabled::test_malformed_config_fails_closed` 锁定 view 路径同样拒绝异常配置。Full evidence 另显式绑定 `test_prompt_builder_prefers_session_platform_config_key`、`test_skill_command_cache_invalidates_when_hide_bundled_changes`、`test_default_config_hides_bundled_skills`、`test_prompt_size_uses_visible_skill_iterator`、`test_readonly_toolsets_are_exact`，逐项执行 `prompt_builder.py`、`skill_commands.py`、`config_defaults.py`、`prompt_size.py` 与 `toolsets.py`；外层 `plugins/sandbox/verify.sh` 再验证群工具面的成员/去写边界。

`hermes_cli/config_defaults.py` 的本地语义是模块级 `DEFAULT_CONFIG` 数据，没有可调用函数；因此它是 `MODULE_IMPORT_EVIDENCE` 中唯一显式登记的 import-level 例外。其他 production `.py` 仅被 import 不算执行证据，防止空断言借模块初始化假绿。

**上游吸收判断**：上游原生提供平台级 skill allowlist 和不含 manage/write 的只读 skill/file toolsets 后可归档。

---

### [PATCH-TOOL-CALL-DOUBLE-WRAP-RECOVERY] 冗余 Tool Search 调用包装安全修复

| 字段     | 内容                                                                 |
| -------- | -------------------------------------------------------------------- |
| **文件** | `tools/tool_search_validation.py`, `tests/tools/test_tool_search.py` |
| **状态** | 🟡 未上游合并；上游仍把自包裹形状视为递归 bridge 调用                |

**问题**：Tool Search 要求 deferred tool 通过 `tool_call({name: target, arguments: {...}})` 调用。部分模型会把完整函数调用 envelope 再包一层，输出 `tool_call({name: "tool_call", arguments: {name: target, arguments: {...}}})`。旧 `resolve_underlying_call()` 在读取内层 target 前先执行 bridge recursion 拒绝，因此合法且已授权的 deferred tool 永远不会触发。2026-08-20 财务群 PDF→动态 HTML 任务已经成功发现 `mcp__hypertex__hypertex_create_case`，却因这一冗余包装被当作 `tool_call` 本身交给群沙箱并拒绝；Agent 随后跨三家 provider 手工生成 83KB HTML，但无法把本地文件真正交付给群成员。

**修复**：`tools/tool_search_validation.py::normalize_tool_call_entries()` 在递归检查前只识别一种精确形状：外层 `name == tool_call`，`arguments` 是对象，且内层 `name` 是非 bridge 工具。单次调用与新版 `calls[]` 共用该入口；仅剥离这一层后继续原有 deferrable 分类、session scoped catalog、required-schema probe、middleware 与 sandbox pre/post hooks；修复本身不扩大任何工具 universe。内层仍是 `tool_call` / `tool_search` / `tool_describe` 时保持原递归拒绝，双层以上不递归展开。

**验证**：`test_resolve_underlying_call_repairs_one_redundant_bridge_envelope` 使用本次真实 HyperTeX 工具名和参数形状，成对覆盖旧单调用与新版单元素 `calls[]`，断言解析为 underlying target 与原始参数；`test_resolve_underlying_call_does_not_repair_nested_bridge_recursion` 把内层继续设为 `tool_call`，必须返回 bridge recursion 错误。Step 8b 单独运行这两条测试，确保既能恢复一层模型格式偏差，又不会打开桥接递归或绕过 session/sandbox gate。

**上游吸收判断**：上游为 `tool_call` 提供等价的一层 envelope normalization，并保留 bridge recursion、scoped catalog 和底层 hook 权限语义后可归档。若仅在 prompt 中提醒模型不要双包，不构成确定性吸收。

---

### [PATCH-FEISHU-GROUP-APPROVAL] 群聊不得审批或接收审批提示

| 字段     | 内容                                                                                                                                                                                                 |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `tools/approval.py`, `gateway/run_turn_runner.py`, `gateway/run_busy.py`, `tests/tools/test_approval.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_slash_access_dispatch.py` |
| **状态** | 🟡 未上游合并；`PATCH-FEISHU-GROUP-SANDBOX` 的纵深防线                                                                                                                                               |

**问题**：通用插件审批、纯安全扫描告警、原生 slash 确认及直接 MCP elicitation 都能进入通知路径；仅拦 terminal/execute_code 不能保证群聊不出现审批卡或文字批准提示。仅禁止发卡也不能阻止危险操作被 yolo/off、allowlist、历史批准或隔离后端提前放行。即使当前群聊不暴露 terminal，审批层仍须保住共享会话的权限边界，以免未来工具配置漂移重新形成提权路径。

**修复**：`_is_restricted_feishu_approval_session()` 优先读 `HERMES_SESSION_CHAT_TYPE` ContextVar，仅在为空时回退解析 session key，识别 Feishu group/forum/channel/thread。受限会话返回 `restricted_chat`、`approved=False`、`user_consent=False`，不通知、不等待批准。主命令入口与 legacy 入口的危险模式检查、execute_code 整脚本检查均先于隔离后端与审批免检分支；主入口的纯 Tirith warn/block 同样先于 yolo/off、command allowlist、session/permanent 批准和 Docker/Singularity/Modal/Daytona/Vercel 后端免检，扫描结果复用以避免重复扫描。无告警命令与 owner DM 的既有策略保留。

公共 `_run_approval_gate` 在 yolo/历史批准之前拒绝群聊请求，`_human_decision` 在 smart/transport/queue 之前拒绝群聊决策，覆盖通用插件审批、受保护写入与扫描告警。Gateway `_approval_notify_sync` 最终出口只允许 Feishu DM，群/话题/未知 scope 在创建卡片或文字 /approve 提示前明确 decline，由等待器立即清理队列；直接 MCP elicitation 也受此投递边界约束。原生短命令的 `_reject_shared_feishu_confirmation`、`_maybe_confirm_destructive_slash` 与 `_request_slash_confirm` 同样拒绝 Feishu 非 DM，在关闭确认的提前执行分支之前拦截，并清除旧 pending confirmation；卡片与文字 fallback 均不发送。这些修复继续维护“群聊不能审批或接收审批提示”的既有不变量，因此并入本 PATCH。管理员群内明确的新会话请求由 `PATCH-FEISHU-ADMIN-CONTROL-SCOPE` 校验后直接重置；命令发起权限不归本 PATCH，不能借此放行其他确认操作。

**验证**：`tests/gateway/test_slash_access_dispatch.py::test_feishu_shared_slash_confirmation_never_prompts_or_executes` 覆盖共享 scope/DM、卡片/文字出口及确认开关，旧实现 30 个反例会发卡、留 pending 或直接执行；修复后均拒绝并清队列，6 个 DM 正例保留。`test_feishu_group_generic_approval_never_notifies` 成对验证 plugin/scan 在 group 不通知、不排队、直接拒绝，而 DM 仍进入原审批；`test_feishu_group_plugin_approval_cannot_use_bypass` 覆盖 yolo 与历史批准。`tests/tools/test_approval.py::TestApprovalTimeoutIsNotConsent::test_feishu_scan_findings_precede_approval_bypasses` 经真实临时 config 与 allowlist 加载器，组合 group/DM、allow/warn/block 和十种免检场景；20 个群告警反例在旧实现错误放行，40 个 DM/无告警正例保留原策略。

`test_feishu_approval_delivery_rejects_shared_chats` 穿过真实 queue → Gateway notification → adapter 调用，覆盖卡片与纯文字出口：Feishu group/forum/channel/thread/未知 scope 均不发送且清空队列，Feishu DM 与其他平台的合法审批保留。`test_feishu_group_dangerous_command_does_not_send_approval_card`、`test_feishu_group_block_via_legacy_check_dangerous_command`、`test_feishu_group_execute_code_guard_blocked` 在 local 与五种隔离后端参数化；`test_feishu_owner_dm_keeps_isolated_backend_approval_policy` 对同样三入口证明 DM 策略保持。`test_feishu_group_block_precedes_allowlist_and_prior_approvals`、`test_feishu_group_block_skips_smart_approval`、`test_feishu_group_chat_type_from_context_when_key_not_canonical` 分别覆盖 allowlist/历史批准、smart 与非规范 session key。Step 8b 将 helper/结果与关键回归入口纳入现有 aggregate gate，full PATCH evidence 精确绑定这些节点并证明执行全部 owned 生产文件；Step 8e 验证 owner DM 与群聊实际工具边界。

**上游吸收判断**：上游在所有审批免检分支之前按 chat scope 拒绝共享群的危险模式、整脚本与纯扫描告警，且公共审批决策、原生 slash confirmation（含关闭确认分支）和 Gateway 实际投递均拒绝群审批及卡片/文字提示，覆盖通用工具、扫描告警和直接通知，并保留 owner DM 与无告警命令的正常策略时可归档。

---

### [PATCH-FEISHU-ADMIN-CONTROL-SCOPE] 管理员新会话与 Gateway 管理分域

| 字段     | 内容                                                                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `gateway/slash_access.py`, `gateway/platforms/base.py`, `gateway/run_busy.py`, `gateway/run_inbound.py`, `tests/gateway/test_slash_access_dispatch.py` |
| **状态** | 🟡 未上游合并；原生 opt-in slash policy 不提供本地 owner/主会话硬边界                                                                                  |

**问题**：群聊禁用 terminal 或拒绝工具审批，仍不能阻止原生短命令直接操作 Gateway。当前上游未配置 `group_allow_admin_from` 时默认允许任何已准入群成员 `/new`、`/reset` 或 `/restart`；空闲重置另走 `send_slash_confirm` 确认流程，而忙碌时 Base adapter 甚至会在 runner 拒绝后取消原任务。用户明确要求：新建/分支 session 可由管理员在群内发起，Gateway 重启只能由管理员在主私聊发起，两者不得混同。

**修复**：共享 `feishu_control_denial` 使用当前 profile 的 `feishu.assistant_user_ids` 首项作为 owner，按发送者 ID 精确匹配，显示名、其他 assistant 身份及缺失/错误配置均不能授予权限。`new`/`branch` 及注册表别名在共享群只允许 owner；`restart`/`update` 还必须同时是 owner 与配置中的 home DM。`sethome` 同受主 DM 限制，防止通过修改 home 位置绕过 Gateway 管理边界。已有普通私聊会话操作及非 Feishu 平台策略保留。

本项按新增语义 PATCH 登记：它维护“谁能在哪个会话发起管理命令”，可以在群聊审批已正确禁止时独立失效，也有独立的命令分派证据与上游吸收条件。`PATCH-FEISHU-GROUP-APPROVAL` 维护审批/确认请求的拒绝，`PATCH-FEISHU-GROUP-SANDBOX` 维护工具与工作区隔离，均不能替代本项。共享 `gateway/run_busy.py` 时，本项拥有 `_check_slash_access` 的命令授权改动；确认拒绝及 pending 清理属于审批 PATCH。共享测试文件中的两个管理权限节点归本项，原生确认节点归审批 PATCH，不能共用一份通过结果替代彼此的证据。

Base adapter 在活动会话取消/排队之前执行同一权限判断；runner 的空闲和忙碌分派再次消费它，所有别名先由真实 registry 归一。管理员在群内明确发送新会话命令即进入原 reset handler，不发确认卡或文字 approve 提示；主 DM 的原生重置确认策略保留。`branch`/`fork` 保留上游的忙碌时拒绝策略。Step 8e 用实际配置验证 owner 的身份、home DM 与 sandbox 唯一 owner DM 一致，并执行正反权限矩阵；不在代码或 fixture 硬编码真实人员 ID。

**验证**：`tests/gateway/test_slash_access_dispatch.py::test_feishu_control_scope_uses_identity_and_main_dm` 从真实临时 YAML 加载 Gateway 配置，穿过实际 `_handle_message`，按 registry 枚举 `new/reset`、`branch/fork`、`restart`、`update`、`sethome/set-home`，覆盖忙碌/空闲、管理员/普通人/无身份、同显示名冒充、额外 assistant 身份、空/错误 owner 配置、主/其他 DM 与缺失 home；分别断言执行、确认、拒绝且未中断任务。`tests/gateway/test_slash_access_dispatch.py::test_feishu_session_control_checks_access_before_adapter_cancellation` 穿过真实 Base adapter，证明普通群成员的 new/reset 不会调用 handler、取消任务、释放 guard 或遗留排队，管理员可正常通过。初始故障样本 76 个失败场景已复现；最终以 full PATCH evidence、canonical suite 和新 PID 下 sandbox verifier 为准。

**上游吸收判断**：只有上游在 Base adapter 取消/排队之前和 runner 空闲/忙碌分派共同提供 owner 身份地板、注册表别名覆盖、群内管理员无卡重置、主 DM Gateway 管理及 home 修改约束，并保留私聊确认与其他平台策略时可归档；只有 opt-in 的 general slash allowlist 不构成等价吸收。

---

### [PATCH-FEISHU-NORMAL-REPLY] 回复始终留在普通聊天消息流

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：`root_id`/generic `metadata.thread_id` 会让普通引用回复被 Feishu 当作 thread/topic 投递，甚至在无有效引用锚点时把 thread id 当 receive id。

**修复**：发送出口固定 `reply_in_thread=False`；引用目标只取显式 `reply_to`/`reply_to_message_id`；create-message 分支忽略 generic thread metadata，缺引用锚点时回退主聊天普通消息。

**验证**：Step 8b 单独检查 `reply_in_thread = False`、忽略 thread metadata 的实现和 `test_send_never_replies_in_thread_even_with_thread_metadata` / `test_send_ignores_thread_metadata_when_no_reply_anchor`，并带两条**负向锚点**（`! grep 'reply_in_thread = bool'`、`! grep '_build_create_message_request("thread_id"'`，2026-08-07 起）——正向锚点只证明本地行存在，无法发现 3-way 把上游 metadata-driven lane 在注释下方重新合入的对撞形态；这些测试覆盖普通引用、文档回复和无引用锚点三条路径。

**上游吸收判断**：上游提供明确的普通引用/话题开关并保证 generic thread metadata 不改变 Feishu 投递 lane 后可归档。**对撞警示**（2026-08-03 审计）：post-26e0b1c 上游在同一 send/reply-body 区域走**相反语义**——`reply_in_thread = bool(metadata.thread_id)`（metadata 驱动投递 lane），与本补丁"固定 `reply_in_thread=False`、忽略 generic thread metadata"直接冲突。下次升级该区域的 3-way 结果**不可信任自动合并**：必须人工按本补丁不变量重解（普通引用回复永不进 thread lane），并以现有回归测试三条路径复验后才能刷新 bundle。

---

### [PATCH-FEISHU-QUOTE-CHAIN-SESSION] 引用链不切分群会话

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并（上游入站仍 `thread_id or root_id`）                    |

**问题**：入站 `_process_inbound_message` 把 `thread_id` 解析为 `getattr(message,"thread_id") or getattr(message,"root_id")`。但飞书的 `root_id` 是**引用链根**，不是话题 id——群里每条未引用的发言都会开一个新 root。`build_session_key`（`gateway/session.py:1744`）看到 `thread_id` 就把它拼进 session key，于是**每条引用链各自切出一个独立 session**：明明没有任何 reset 生效（`session_reset.idle_minutes: 1440` 远未到），`SpaceSight技术分享专项群` 2026-08-12 两小时内产生 3 个 session（`...:om_x100b688abc...` / `...:om_x100b68f54d...` / `...:om_x100b68f5e9...`），与 8/07、8/11 干净的群级 key 形成对照。每个新 session 都从零重载 `llm-wiki`(22k) + `feishu-docs`(33k) 全文与 30 分钟历史回填，直接放大 compaction 压力（当日 15:04–15:06 两分钟内连压两次的成本来源）。上游自己知道这个 conflate——`adapter.py` 出站侧注释明写 "The inbound handler conflates root_id into thread_id"，但只在出站钉了 `reply_in_thread=False`（`PATCH-FEISHU-NORMAL-REPLY`），**入站的 session key 污染没有对应修复**。

**修复**：入站只取真正的 `thread_id`，删除 `root_id` 回退。飞书话题/thread lane 本机刻意不用（`thread_id` 实测恒为 None），因此这是纯粹移除一条错误回退，不改变任何既有可用行为。**引用链能力完整保留**：链条由第 3659 行独立计算的 `reply_to_message_id`（`parent_id` → `upper_message_id` → `root_id`）与 `reply_to_text` 承载，与本字段无关。`_resolve_channel_prompt(chat_id, thread_id)` 的第二参在 `feishu.channel_prompts` 未配置时（本机即未配置）不产生行为差异。

**验证**：`tests/gateway/test_feishu.py::TestAdapterBehavior::test_quote_chain_root_id_does_not_become_thread_id_or_split_session` 构造带 `root_id="om_chain_root"` + `parent_id="om_quoted"` 的真实引用回复，断言三件事：`event.source.thread_id is None`；**用真实 `build_session_key` 求值**得到 `agent:main:feishu:group:oc_grp` 且不含 `om_chain_root`（行为断言而非 grep）；`reply_to_message_id` / `reply_to_text` 仍正确送达（证明只去掉会话切分、没有削弱引用能力）。测试为 load-bearing：恢复 `or root_id` 后该用例在 `assertIsNone(event.source.thread_id)` 失败。既有 14 处 `root_id=None` 用例判定不变，27 个受管测试文件 1042 passed / 0 failed / 3 skipped。

**上游吸收判断**：当上游入站不再把 `root_id` 当 `thread_id` 回退（或为飞书引入真正区分"话题 id"与"引用链根"的字段）时可归档。与 `PATCH-FEISHU-NORMAL-REPLY` 是同一 conflate 的两侧：那条守出站投递 lane，本条守入站 session 身份；两者可被不同上游 PR 分别吸收，故不合并为一个补丁。每轮升级须复核该行未被 3-way 恢复成 `or root_id` 形态。

---

### [PATCH-GATEWAY-FAILOVER-STATUS-SILENCE] 模型路由状态不进入聊天

| 字段     | 内容                                                                                                                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/{agent_runtime_helpers.py,chat_completion_helpers.py,chat_completion_nonstream.py}`, `gateway/run.py`, `tests/agent/test_codex_ttfb_watchdog.py`, `tests/gateway/test_telegram_noise_filter.py`, `tests/run_agent/test_primary_runtime_restore.py` |
| **状态** | 🟡 未上游合并；上游 fallback-observability 有意向用户 surface                                                                                                                                                                                             |

**问题**：`_try_activate_fallback()` 同时维护两条内部状态：失败路径缓冲 fallback 切换状态，成功路径挂起 one-shot notice；成功时后者由 `_emit_pending_fallback_notice` 单独发出，终态失败时前者随 `_flush_status_buffer` 重放。Gateway 的聊天噪声过滤必须覆盖 producer 当前实际生成的每种格式。2026-08-20 首次补丁只登记了当时的 `Primary model failed — switching...` / `Switched to fallback model...` 两代文案。2026-08-27 11:41:40，SpaceSight Tech Sharing Group（`oc_1d81b1992a1cf99620bf815945782f27`）的 Azure `gpt-5.5` 连续两次 90 秒 stale 后切到当时的 Bedrock 路由；新 upstream producer 已改为 `⚠️ Model fallback: ... unavailable (...); using ...`，但 regex、测试与 Step 8b gate 仍只喂旧字符串。11:46:35 下一条真实群消息的引用上下文明确包含该独立 Gödel fallback 消息，证明现有 gate 假绿并泄露完整 inference-profile ARN。2026-09-04 15:36，“AI 解放生产力”实抓另一组漏网文案：Codex 首字节后 12 秒无 SSE event 的 reconnect notice 连续进入群聊；多级 provider 故障后，聊天面又收到通用 `The model provider failed after retries...`，没有任何正常 assistant 回答。

**修复**：上游拆分 `_NonStreamRequest` 后，watchdog 的调用点迁入 `agent/chat_completion_nonstream.py`，不在旧 facade 复活同名 class；回归穿过真实 worker 再检查聊天过滤。把 one-shot 文案集中到 `agent.chat_completion_helpers._format_fallback_notice()`；Codex 首字节超时/首字节后事件停滞和 non-streaming stale 文案分别集中到 `_format_codex_stream_stall_notice()` / `_format_nonstreaming_provider_stall_notice()`，生产逻辑、测试和聊天过滤器通过 `is_internal_provider_retry_status()` 共用同一 producer 语义。共享聊天 status 边界同时覆盖历史 fallback、当前 `model fallback:`、Codex reconnect 与普通 stream/no-output 形状。Feishu、Telegram、Slack、Discord 等 human-facing chat 对这些内部状态返回 `None`；local/TUI、API、webhook 继续保留原始状态，日志与模型使用统计不变。聊天面最终 provider-failed/auth/连接/限流错误也返回空串，且 empty-response fallback 不得把 raw error 重新拼回；程序化 surface 继续保留原始诊断。

2026-09-04 续审补齐两处根因：① `Primary model restored: ... fallback ... is no longer active` 原先由 `restore_primary_runtime()` 内联生成，未进入共享过滤语义；现集中到 `_format_primary_model_restored_notice()` 并纳入同一聊天抑制 predicate。② Codex Responses 在 `<10k` 估算输入时把“首字节后无 SSE event”默认阈值硬降到 12 秒，而同一模型在其他会话可正常返回；AI 解放生产力的两次失败分别约 8.4k/9.4k tokens，恰好落入该激进档并在 12 秒被本地 watchdog 主动断开。现取消 12 秒断崖，所有不超过 50k 的请求至少等待 60 秒；更大上下文仍按 120/180 秒分档，显式环境覆盖与 hard ceiling 保持不变。聊天 status 边界对 provider error 也直接返回 `None`，不再把原始错误替换成另一条通用错误文案继续发群。

**验证**：`tests/agent/test_codex_ttfb_watchdog.py::test_ttfb_includes_silent_hang_hint_for_gpt_5_5` 穿过真实 nonstream worker/watchdog，再验证产生的 notice 在聊天面被抑制而 local 保留；`test_generated_fallback_notice_suppressed_on_chat_surfaces` 调用生产 `_format_fallback_notice()` 生成 Azure→SC Claude timeout 形状；`test_generated_provider_stall_notices_suppressed_on_chat_surfaces` 调用两个 watchdog producer 生成用户实抓的 Codex/non-streaming 文案，并穿过真实 `_prepare_gateway_status_message`，断言 Feishu、`feishu_group`、Telegram、Slack、Discord 全部返回 `None`，local/API/webhook 原样保留。`test_telegram_final_response_sanitizes_raw_provider_errors`、`test_telegram_final_response_redacts_auth_secrets` 与 `test_suppressed_provider_failure_is_not_restored_from_raw_error` 证明聊天最终失败正文被吞且不会从 raw error 复活；普通回答与程序化 surface 反例保持可见。生成结果也进入 `NOISY_STATUS_MESSAGES` 的全聊天参数化回归。Step 8b 调用 producer 覆盖五种聊天面、最终失败与 local 负向边界；未来 producer 改词但 consumer 未同步时 gate 必须失败。

补充回归由同一个 generated-provider test 直接调用恢复文案 producer，并由 `tests/agent/test_codex_ttfb_watchdog.py::test_codex_event_stale_timeout_never_uses_twelve_second_cliff` 锁定 60/120/180 秒分档；`tests/run_agent/test_primary_runtime_restore.py::TestRestorePrimaryRuntime::test_emits_user_visible_primary_restore_notice` 继续锁定 CLI/operator 可见文案本身，确保只改变聊天出站策略、不删除本地诊断。`tests/agent/test_codex_ttfb_watchdog.py::test_large_codex_request_hard_ceiling_reclaims_silent_stall` 继续验证大请求的硬超时；持续时间与模拟阻塞期限用 monotonic 量测，保留原 30 秒断言上限，并在失败时同时输出 wall-clock 差值以区分主机时钟变化与真实延迟。

**上游吸收判断**：上游若将 fallback/watchdog observability 与最终 provider failure 改为仅日志/结构化 telemetry，或在所有聊天 status/final 边界等价区分“正常业务回答”与“内部模型路由/失败诊断”并默认隐藏后可归档。仅改变文案不构成吸收，需同步更新源 producer、分类器与测试。

---

### [PATCH-FEISHU-FINAL-ONLY] Feishu 默认最终内容优先，长任务保留通用心跳

| 字段     | 内容                                                                                                                                                                                                 |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/display_config.py`, `tests/gateway/test_display_config.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_verbose_command.py`（本机 `config.yaml` 按 DM/group 显式覆盖） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                        |

**问题**：Feishu 默认 tool progress、streaming 和 interim bubbles 会把草稿、工具进度或思考式中间态暴露到群聊；这与消息是否进入 thread 无关，应独立控制。只验证 `display.platforms.feishu_group` 的静态值并不足够：运行 consumer 若错误使用 `feishu` key，群聊仍会继承 owner DM 的 `tool_progress: new`。初版为追求 final-only 同时关闭 long-running notification，真实 PDF 任务耗时 19 分 24 秒时群里全程无任何存活信号，用户合理判断为“引用 PDF 后没有响应”。

**修复**：Feishu 内置 display tier 继续默认关闭 tool progress、streaming、interim assistant messages、long-running notification 和 busy detail。当前本机让主会话 DM 使用 `tool_progress: new` 且不发心跳；群聊保持 `tool_progress: false`、关闭 streaming/interim/thinking/busy detail，但显式配置 `long_running_notifications: generic` 与 `agent.gateway_notify_interval: 180`。因此普通任务仍只显示最终内容；超过 3 分钟的任务只出现一条无工具名、模型名、迭代数的通用心跳，后续周期尽量 edit 同一条消息，不泄露内部执行链。运行 consumer 的 `gateway/run.py` / `gateway/slash_commands.py` source-aware hunk 归属 `PATCH-FEISHU-GROUP-SCOPE`，本补丁仅依赖该能力，不把依赖文件伪登记为自身 ownership。若 provider 把 thought 错塞进正文，由 `PATCH-VERTEX-HIDDEN-THOUGHTS` 请求侧抑制。

**验证**：Step 8b 检查 Feishu display defaults 与 `test_feishu_defaults_to_final_only`；本机策略校验 DM `tool_progress: new` + long-running false，群聊 `tool_progress: false` + long-running `generic` + 180 秒间隔，且两者的 streaming/thinking/interim/busy detail 均关闭。真实 `_run_agent` 边界测试继续证明群聊没有 tool progress/interim send；通用心跳使用既有 `allow_generic=True` 路径，不包含 activity detail。`/verbose` 测试证明群命令只读写 `feishu_group`。

**上游吸收判断**：上游 Feishu 提供等价的 final-answer-first profile：隐藏工具/思考/路由内部状态，同时允许可配置、无内部细节的长任务存活心跳后可归档。

---

### [PATCH-LOCAL-PROFILES] 本地人物/群画像与群聊输出保密

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/{session.py,run.py,run_agent_cache.py,run_turn.py,run_turn_runner.py,stream_consumer.py,stream_consumer_fallback.py,stream_consumer_transport.py}`, `plugins/platforms/feishu/adapter.py`, `tests/gateway/{test_feishu.py,test_session.py,test_run_progress_topics.py,test_stream_consumer_silence.py}`；`people.yaml` / `groups.yaml` 为配置仓库数据 |
| **状态** | 🟡 本地个性化功能，不预期上游直接吸收                                                                                                                                                                                                                                                                                                                          |

**问题**：模型只凭 open_id/显示名无法按用户维护的人物背景和群人设调整表达；画像私有字段、数据来源和 `people.yaml` 文件名又绝不能在群聊泄露。工具受限时也必须披露证据边界，不能把未验证内容包装成结论。2026-09-08 又确认了一个称呼契约缺口：`address` 为空时，prompt 只暴露完整中英文姓名而没有稳定 fallback，新会话可称“安媛媛”，有历史示例的会话却称“媛媛”；这种依赖模型猜测和历史模仿的行为不是稳定人物契约。

**修复**：按 mtime 热加载 people/group profile；人物画像采用公开白名单：只有 `name`、`role`、`department`、`address` 可对外，所有已知私密字段和未来手工新增字段都进入模型可读的保密块并纳入确定性出站过滤；open_id/user_id/union_id/id 和未与公开字段重合的 aliases 只用于匹配，同样不得输出。`address` 显式配置时仍是唯一权威称呼；为空时由代码只基于公开 `name` 字段生成中/英文确定性默认值，prompt 只决定是否在当前语境自然使用。中文三字常见姓名取双字名，已知复姓只在剩余名至少两字时缩短；单字名、姓名布局低置信或无法解析时保留全名。英文按组织目录的 `Given FAMILY` 常规取 given name，兼容 `FAMILY Given` 的大写姓形式；单词姓名原样保留。括号昵称、aliases 和历史消息都不参与自动推导，避免将匹配别名、玩笑名或旧上下文升格为公开称呼。派生值同源于公开 `name`，并显式加入 redactor 的公开值集。群画像只控制风格、介绍、能力口径和提示性服务时间。所有 group/channel 无条件注入来源保密和工具限制声明；非 DM 的最终、流式、fallback、临时 assistant 消息、流式 TTS 和 `/background` 完成/失败通知等可见/可听文本统一经过 `redact_private_person_profile_text`/`text_filter`，后台完成通知不回显 prompt；redactor 自身内置 DM 早退（2026-08-07 加固：所有调用方虽已在外部按 chat_type 分流，但未来新增调用方漏掉分流时按构造即安全——群不漏、DM 不被误遮；`test_private_profile_redactor_leaves_dm_text_untouched` 锁定 DM 原样返回）。2026-08-28 修正短私密值误伤媒体控制路径：2–6 字符的纯 ASCII 数字/代号只在独立 token 边界出现时脱敏，且**永不进入 path-like ASCII run**（`_TECHNICAL_PATH_RUN_RE`：含两个及以上分隔符的路径/URL 片段），`下属29人` / `字段 29` / `29/50` 仍会隐藏，但时间戳、UUID、哈希、URL 以及生成图片路径里的片段不再被替换——脱敏发生在 `extract_media()` 之前，改一个字符就等于静默丢附件，而 `total_reports: 11` 这类两位数会与 `2026-11-28/` 日期目录逐日碰撞，仅靠 token 边界拦不住。CJK 与空白不属于路径字符类，所以中文正文里嵌路径时正文照常过滤；长 ID、完整备注和中文私密值继续严格精确过滤（含路径内）。loader 缺文件或坏 YAML 时安全降级，DM 不注入群画像规则。`people.yaml` 与 `groups.yaml` 保持普通可编辑文件，owner 始终拥有读写权限；两个热加载器和升级 Step 8b 都会将其收敛并验证为 `0600`，因此同账号 VSCode 可照常编辑，而其他本机账号不可读。

聊天历史（群聊回填与合并转发展开共用的 `_history_sender_label`）此前只渲染 `ou_xxx` 裸 id 或缓存显示名，缓存未命中时模型无法分辨发言人。现复用同一份 `_lookup_person` 索引（open_id/user_id/union_id/name/aliases）把发送者 join 到 people.yaml：命中则用画像 `name`，并只追加公开面中的 `role`/`department` 作为限定语。历史会被回显进群聊回复，因此限定语字段是白名单而非黑名单，公开四项以外（含 `employee_no`、保密备注等）一律不进入 label；join 失败或 people.yaml 缺失时安全降级为原有 id/显示名。

**验证**：Step 8b 检查 profile loaders/lookups、公开 `address`、默认称呼推导 helper 与 prompt 契约、未知字段 private-by-default、技术 ID/未公开别名过滤、来源保密常量、私有值/文件名字面量 redactor、stream/TTS filter、后台/临时消息出站测试、后台不回显 prompt 断言，以及 `people.yaml` / `groups.yaml` 的 owner-rw `0600` 权限与热加载自愈测试；`test_unset_address_derives_conservative_language_specific_defaults`、`test_parenthetical_nickname_is_not_an_automatic_address` 和 `test_derived_addresses_remain_public_but_other_aliases_stay_private` 锁定中文双字名/单字名/复姓、英文 given name/单词姓名、显式 address 优先级、括号昵称不自动晋升和派生公开值不被脱敏；`test_private_profile_redactor_keeps_public_fields`、`test_short_private_values_require_ascii_token_boundaries`、`test_private_values_never_rewrite_media_paths`、`test_non_dm_interim_direct_fallback_redacts_private_profile`、`test_history_sender_label_joins_people_profile` 和 `test_history_sender_label_survives_profile_lookup_failure` 分别锁定公开字段、短数字在普通文本继续隐藏但不破坏 `MEDIA:` 时间戳路径、私密值等于路径片段（`direct_reports: 28` vs `2026-11-28/`）时媒体路径逐字节不变而同条正文仍被过滤、非 DM 临时输出、历史发送者公开字段 join 与异常降级。验证只归属于画像与输出过滤；旧 terminal/script-root allowlist 已被删除，不再作为本补丁的实现或测试。

**上游吸收判断**：若上游提供等价的本地 per-sender/per-group profile 注入与全出站路径隐私过滤，可重新评估；否则保持本地补丁。

---

**类别：Feishu 资源、文档与渲染**

### [PATCH-FEISHU-RESOURCE-ACCESS] 附件回看、Drive 链接与 tenant 文档读取

| 字段     | 内容                                                                                                                                                                                                                                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/{run.py,run_inbound.py,platforms/base.py}`, `tools/feishu_doc_tool.py`, `tests/gateway/test_config.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_feishu_post_files.py`, `tests/tools/test_feishu_tools.py`, `website/docs/user-guide/messaging/feishu.md` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                        |

**问题**：群聊媒体与 @mention 常分成两条消息，引用里的 `/file/<token>` 也不是 IM 附件；普通 gateway 工具调用没有 comment thread-local client 时，tenant 凭据明明存在却无法读取飞书文档。旧附件补丁还只允许群 `trigger_kind == bot` 且非 command 的回填：DM 显式引用、群 `@配置本人账号`、Feishu command composer 遗留的单独 `/` 均会只留下缓存路径而不把图片/视频交给模型；显式再次引用同一资源又会被本应只约束滑动窗口的去重缓存错误抑制。另外，被引用的合并转发消息在 webhook payload 里不带子消息体，上游只把它归一化成 `[Merged forward message]` 占位符，因此群里"引用合并记录 + @Bot"只能看到占位符，而私聊直发同一条合并记录却能正常展开。初次补上展开后仍有第二层截断：Gateway 对所有 `reply_to_text` 硬编码 `[:500]`，真实卡片的 12 条子消息虽已全部从 Feishu API 取回，送模时却在第 6 条中间静默截断，导致机器人错误声称后续内容不存在。2026-08-16 的真实 PDF 回填又暴露第三层：`_fetch_message_text` 为生成引用说明先下载一次附件并把绝对 cache path 写进 `reply_to_text`，随后 `_backfill_reply_attachments` 为真正送模再次下载，同一 PDF 产生两个缓存副本；sender-window 只接受 image/file/media、遗漏原生 audio，窗口与上限也不可配置，失败后静默按纯文本继续。2026-09-03 的 53.8 MiB PPTX 现场又暴露配置桥缺口：`config.yaml` 已声明四个 `attachment_backfill_*` 键，但 `gateway/config.py` 没有把它们传入 `PlatformConfig.extra`，运行时始终退回 8 秒默认值；同一附件直接下载约 22 秒，引用与 sender-window 两条回填均稳定超时。

**修复**：将显式引用恢复与群聊同发送者滑动窗口回看拆开：DM 和已准入的 `bot`/`assistant_user` 群触发可恢复引用附件（整条恢复链以 `history_backfill: true` 为总开关且触发消息自身不带媒体时才扫描——本机已启用该开关；上游默认 false 时显式引用恢复不生效，属有意搭载而非"无条件始终"），显式重复引用不受窗口去重限制；窗口扫描仍仅限群聊并保持有界去重。把单独 `/` 归一为无实际命令的 bare mention，使引用主题进入同一意图链。扫描正文/引用中的 Drive file token，以 tenant 身份通过认证 HTTP 流式下载并保留 MIME/文件名：先校验 `Content-Length`，未知/不可信长度读取到 `limit + 1` 即停止，IM 与 Drive 均有 100 MiB 硬上限；普通网页链接原文保留。`feishu_doc_read` 缺 comment client 时从 env/`.env` 构建 tenant client。引用目标是 `merge_forward` 时，`_fetch_message_text` 复用直发路径的 `_expand_merge_forward_message` 展开子消息；`_collect_reply_attachments` 同时接受 `upper_message_id` 指向引用目标的子消息，使转发记录内的图片/文件也被下载。Gateway 识别仅由该展开器生成的 `[Merged forwarded messages]` 内部标记，把 Feishu 引用上下文上限从通用 500 提高到有界 20,000 字符；普通 Feishu 引用与其他平台仍保持 500，避免无关扩权。该补丁只负责取得资源字节/API 文本并完整交给模型，不负责解析文件格式。2026-08-16 进一步把 sender-window 扩为 image/file/media/audio，并把 window/messages/files/timeout 四个限制改为 Feishu 配置项；2026-09-03 补齐 `gateway/config.py` 对四个键的真实桥接，本机保持 300s / 3 / 6，并把有界总超时提高到 60s，使约 54 MiB、实测下载 22 秒的 PPTX 能完成，同时网络卡死仍会明确失败而非无限等待。direct post/merge-forward、显式 quote、sender-window 与 Drive 链接现共享同一个 `_AttachmentDownloadBudget`：每次尝试在请求前消耗 file budget，失败/超限也计数，全部路径共享单一 deadline；排队 future 在 executor shutdown 前被取消时会归还 admission permit。引用/history 只生成 path-free 占位符；直接、引用、merge 子附件、窗口或 Drive 全失败/被预算跳过均向当前 turn 注入明确 `Do not claim` 状态，不能静默假装读取。2026-08-05 对上游 `b51c4e6a7` / `e80b7aeda` 融合时，保留其线程锁保护的 SDK 延迟导入与 None 判定，删除重复 loader 形状，只在上游 `_load_lark_oapi()`/None 初始化集合中增加本补丁独有的 `DownloadFileRequest` / `ListMessageRequest`；资源访问的 admission、下载、展开、上界与 tenant fallback 均未被吸收。

2026-09-11 新版组合消息兼容：MKT AI Sparks 的两条实际 `post` 同时返回 `content`、`content_v2` 和顶层 `files[]`，附件引用在 `_to_post_payload()` 中被丢弃。已核对当日上游 `cbd03e6e4c` 仍缺失该能力，相关解析函数与当时安装基线 `79445a496c` 完全一致。现保留顶层 `files` 并归一到既有 `media_refs`，按 `file_key` 与旧内嵌引用去重；缺字段、非列表及无效条目不影响原正文。正文继续使用原 `content` 路径，不调整 Markdown、@mention、图片、Drive 链接、下载预算或文档格式抽取。显式引用及合并转发自动复用同一解析器；同发送者回看额外接受带附件的 `post`，纯文本 post 不占附件消息上限，原同群/同发送者/时间窗口/删除/去重限制继续生效。

**验证**：Step 8b 单独检查 sender/reply backfill、四个 attachment 配置键从根 YAML 进入 adapter、显式重复引用不被去重、单独 `/`、DM/两类群触发、Drive URL/download、tenant client fallback、引用 merge_forward 展开（`is_forward_child` + `_fetch_message_text` 展开分支）、Gateway 20,000 字符专用上限、`gateway/platforms/base.py` 的 `.odt` MIME 映射锚点及对应测试。`test_bridges_feishu_attachment_backfill_limits_into_adapter` 从真实临时 `config.yaml` 穿过 `load_gateway_config()` 与 `FeishuAdapter`，锁定 window/messages/files/timeout 四个值不会再静默回退默认；`test_failed_resources_still_consume_file_budget`、`test_direct_post_resources_share_one_deadline_and_surface_failure`、`test_merge_forward_enforces_one_budget_across_child_messages`、`test_drive_links_share_file_budget_even_when_downloads_fail` 与 `test_quote_and_sender_backfill_share_deadline_and_remaining_file_budget` 锁定整轮预算/deadline；`test_merge_forward_failed_child_resource_is_model_visible`、`test_merge_forward_lookup_failure_is_model_visible`、`test_quoted_attachment_all_downloads_failed_is_explicit` 锁定显式失败；`test_cancelled_queued_download_releases_admission_permit` 锁定 reconnect 不泄漏 permit。`test_quoted_resource_matrix_reaches_event_across_dm_and_group_triggers` 从完整入站路由覆盖群图片、群视频、群音频、群 Drive/PDF、DM 网页和 DM Drive 链接；`test_explicit_requote_is_not_suppressed_and_media_video_is_preserved` 锁定重复引用与视频 MIME；`test_sender_window_backfill_includes_audio_and_uses_configured_window` 锁定 audio + 配置化窗口；`test_fetch_message_text_uses_path_free_attachment_placeholder` 证明引用文本不下载资源、不泄露绝对路径；`test_doc_read_builds_env_client_outside_comment_context` 直接覆盖 `tools/feishu_doc_tool.py` 的 tenant client fallback。`test_feishu_merge_forward_reply_context_is_not_cut_at_generic_500_chars` 同时证明 12 条长转发的尾条保留、普通引用仍在 500 截断。真实 API 卡片返回 13 items（1 parent + 12 children、正文 915 字符），修复前 DB turn 在第 6 条中间止于 500 字符，修复后完整文本落入 user turn。

新增 `test_post_files_preserve_legacy_text_media_and_mentions` 覆盖平铺/多语言/嵌套 post、畸形 files、正文/@/图片保持及新旧字段去重；`test_post_files_reach_existing_document_pipeline` 从临时根 config.yaml 加载配置，以真实消息事件穿过 `_handle_message_event_data`、admission、SDK request builder、资源下载器、本地缓存、HTML 抽取和 Gateway 私聊/群聊入站预处理，贯通直发/引用/合并转发/同发送者回看，四条路径同时覆盖新 files、旧内嵌、旧独立 file 和两种字段并存，验证一个文件只请求一次、文本进入 user turn、缓存路径不暴露，同时覆盖未 @ 群消息、DM 不扫描发送者窗口、同一事件重复投递和新事件再次引用同一文件。

**上游吸收判断**：上游同时支持新版顶层 `files[]` 与旧内嵌文件去重、分离消息附件回看（含 audio、配置化有界窗口和显式失败）、Drive 正文链接下载、引用合并转发的子消息展开及完整有界送模、path-free 引用占位符与单次资源下载、无 comment-context 的 tenant doc client 时可归档；SDK 延迟导入本身不是该补丁的语义吸收条件。

---

### [PATCH-DOCUMENT-EXTRACTION] 可信文档文本抽取

| 字段     | 内容                                                                                                                                                                                                                                   |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/{run.py,run_inbound.py}`, `tools/read_extract.py`, `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock`, `tests/gateway/{test_document_context_note.py,test_image_input_routing_runtime.py}`, `tests/tools/test_read_extract.py` |
| **状态** | 🟡 部分吸收（XLSX/DOCX/IPYNB、`read_file` 接线、bundled anydoc/typed OCR 已上游合并；native PDF/HTML/PPTX/ODT 与入站接线仍本地）                                                                                                       |

**问题**：附件成功下载后，PDF/HTML/PPTX/ODT 等二进制仍只给模型路径；群聊又不能临时执行解析脚本。上游 `tools/read_extract.py` 已覆盖 IPYNB/DOCX/XLSX，并通过 anydoc 覆盖 legacy Office/ODF/RTF/EPUB/PDF，但没有替代本地 native PDF/HTML/PPTX/ODT、pypdf pin 与 Gateway 入站抽取。初版入站抽取虽把文本送进 prompt，仍同时暴露原始 cache 绝对路径，真实 `Data Pipeline Workshop` turn 因此在已经拿到 PDF 文本后又调用一次 `read_file` 并被群沙箱拒绝；同时“只要任意页有文字就算成功”的分支会漏掉混合 PDF 中占比较高的扫描/图片页。

**修复**：在上游 `read_extract.py` 抽取层上扩展 PDF（pypdf，兼容 PyMuPDF 安装）、HTML（移除主动内容）、PPTX、ODT，并对每文件/每轮文本做上界；XLSX 使用独立 50 MiB 输入上限，其他结构化文档保持 100 MiB 与 archive 展开上限。上游 `file_tools.py` 的 `read_file` 接线按 `EXTRACTABLE_EXTENSIONS` 自动获得新格式，无需本地改动 `read_file` 主路径。`gateway/run.py` 新增 `_extract_inbound_document` 在线程池中抽取入站附件，向模型明确内容是不可信参考数据。成功抽取提示只说明“文本已在下方”，不再携带宿主/container cache path；加密、损坏、超限或不支持文档只给经过分类的 path-free `FAILED` 状态，精确异常保留日志。新增 `pdf_needs_visual_fallback()` 复用上游逐页 coverage 阈值：文本抽取成功但有意义的扫描/图片页缺口时，继续把当前 PDF 交给 `PATCH-MULTIMODAL-SIDECAR` 的首个 configured capable route；sidecar 失败仍保留已抽取文字并标记 `PDF visual coverage status: INCOMPLETE`，不得声称看过缺页。PPTX 原生抽取把任意 picture/`a:blip`/chart/graphic frame/OLE 页列为视觉覆盖缺口，即使同页已有标题或说明文字；混合 deck 保留文字并列出缺失页，纯图片 deck 同样返回 `PPTX visual coverage status: INCOMPLETE`，明确禁止声称已检查视觉内容。这不把 PPTX 外发给未声明支持该 MIME 的模型。依赖在 project extra、lazy deps 与 lockfile 中固定。设计留观：`pypdf` pin 落在 `LAZY_DEPS["platform.feishu"]` 而非 `tool.doc_extract`（后者上游仍 anydoc-only）——本机 Feishu 栈必装故等价；非 Feishu 部署走 `read_file` 读 PDF 时不会触发懒装，若上游重写 feishu extra 需把 pin 迁到 `tool.doc_extract`。

**2026-08-03 收缩**：上游在 26e0b1c 已自带 `read_extract.py`（XLSX/DOCX/IPYNB）并经 `file_tools.py` 接进 `read_file`，本地曾并存的 `file_operations.py` `_read_spreadsheet` 第二条 XLSX 路径成为死代码（抽取分支先行拦截），已连同其测试一并删除；`tools/file_operations.py`、`tests/tools/test_file_operations.py` 移出 `PATCHED_FILES`。**2026-08-06 收缩**：上游 `b2598b41e` / `997a913` / `ffdbc88` 吸收 anydoc-only 格式、失败重试和 anydoc size cap；本地测试已把 anydoc-only 可用性（RTF/EPUB/DOC）与 native-overlap 可用性（PDF/PPTX/ODT）分离，防止上游 anydoc 语义重新压住本地 native 抽取。**2026-08-08 并存记录**：上游 `8de3ddb9e` / `89c14aeb9` / `765940df7` 新增 bytes 边界 `extract_document_bytes`（file backend 传输字节 → 私有 temp 文件物化）与扫描版 PDF 覆盖率警告（pdftotext 逐页计数、空页占比阈值提示）——与本地 hunk **正交不吸收**：本地入站接线（`_extract_inbound_document`）是 path-based（飞书媒体先落本地缓存），本地 native 抽取器/上界/zip 安全均不被替代。**2026-08-29 再收缩**：上游 `a9e72f1b58` 已把 `firecrawl-anydoc==0.2.4` 变成 core dependency，并吸收缺包教学、typed `NeedsOcrError`、direct `FIRECRAWL_API_KEY` hosted-OCR gate 与动态 schema 文案；这些内容不再计作本地实现。3-way 冲突按并存解决，只保留上游 `_check_document_size` 与本地 native extractors。新上游的 bytes 路径仍优先 anydoc，和“native overlap 格式不依赖 anydoc”的本地不变量冲突；现已改为 PDF/PPTX/ODT 等 native 格式在 path/bytes 两条入口都优先本地解析，PDF bytes 的 coverage warning 仍显示 backend-visible path。

**验证**：Step 8b 单独检查 common extractors（`_extract_pdf` / `_extract_html_file`）、`_extract_inbound_document`、`pdf_needs_visual_fallback`、PPTX incomplete marker、XLSX 50 MiB 上限、pypdf 双路径依赖和 `TestCommonDocumentExtraction`，并锚定 `test_native_overlap_formats_remain_extractable_without_anydoc`、`test_native_pdf_remains_extractable_when_anydoc_is_unavailable`、`test_anydoc_only_formats_not_extractable_without_anydoc`、`test_pptx_visual_only_slides_are_explicitly_incomplete`、`test_pptx_pure_image_deck_returns_coverage_marker`、`test_pptx_text_plus_visual_is_explicitly_incomplete`、`test_xlsx_uses_format_specific_fifty_mib_limit`、入站 HTML、path-free document note、混合 PDF sidecar、`test_feishu_group_document_matrix_reaches_user_turn` 和 `test_feishu_group_pptx_visual_marker_reaches_user_turn`。`test_anydoc_only_extensions_track_availability` 继续区分仅 anydoc 格式与 native overlap 格式。真实 extractor canary 覆盖 PDF、HTML、TXT、DOCX、XLSX、PPTX、ODT；群聊 consumer 矩阵证明七类内容进入 Feishu group user turn、标记为 untrusted reference data、不含缓存路径且不依赖 terminal；coverage 正反例与 mixed-PDF Gateway 测试证明纯文本不旁路、扫描缺口补读，PPTX 图片页回归证明纯图片和混合 deck 都不会被误报为完整读取。真实 53.8 MiB 现场 deck 现在明确列出视觉缺口页 1-2、6-8、13-16、26-27；现场 XLSX 继续成功抽取。anydoc 现在是 core dependency，但故障/冷却状态下 native overlap 的 path 与 backend-bytes 回归仍必须通过。

**上游吸收判断**：上游 `EXTRACTABLE_EXTENSIONS` 以 native 或同等无需 prompt 的依赖策略覆盖 PDF/HTML/PPTX/ODT，并提供等价的 Gateway 入站附件抽取接线、prompt 上界、path-free 成功/失败状态与混合 PDF coverage→视觉补读后可归档；仅有 anydoc 可选转换不构成本地 native/inbound 语义吸收。资源获取能力独立留在 `PATCH-FEISHU-RESOURCE-ACCESS`。

---

### [PATCH-FEISHU-MARKDOWN] Feishu 出站 Markdown 归一化

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：飞书 post/md 元素能渲染行内标记（加粗 / 斜体 / 列表 / 链接 / 行内代码），但有四类格式边界需要本地归一化：①ATX 标题 `## heading` 与引用 `> quote` 以原始符号字面显示；②（2026-07-25 新增）飞书 md 解析器严格执行 CommonMark emphasis flanking 规则——`**` 内侧是标点且外侧紧贴文字时加粗不成立（如 `到**“端云通信协议”**的`）；③（2026-08-15 主会话复现）整行引用本身为粗体时，旧转换把 `> **问题**` 写成 `▎**问题**`，Feishu 因视觉 quote bar 后没有 token boundary 而原样显示星号；④（2026-09-06 Data Pipeline Workshop 实抓）后加的自动 `@消息者` 把原本位于首 token 的表格 header 改成 `<at>姓名</at> | Field | Value |`，导致表格退化成普通文本，同样会破坏位于正文开头的列表、分隔线等块级语法。

**修复**：三处改动，均在 `_build_outbound_payload` 出站路径：

1. **标题 / 引用**：新增 fence-aware 预处理器 `_promote_block_markdown(content)`，将 post/md 渲染不出的块级语法转成等价可渲染形式：`## heading` → `**heading**`，`> quote` → `▎ quote`；视觉 quote bar 后始终保留一个空格，因此 `> **整行粗体**` 会稳定变成 `▎ **整行粗体**`。代码块内的 `#` / `>` 原样保留。

2. **行内加粗 flanking**（2026-07-25）：`_promote_block_markdown` 逐行（跳过代码块与行内代码 span）调用 `_fix_strong_flanking`：按 CommonMark 规则（标点=Unicode P*/S* 类）检测无法 open/close 的 `**span**`，仅把违规一侧的边缘标点连续段移出标记（`到**“x”**的` → `到“**x**”的`），字符序列不变；全标点 span 无法挽救时去掉标记。刻意不做"对称搬移"——那会把与 span 中部配对的括号也拽出粗体，产生更差的观感。合法 span（外侧为空白/标点/行边界，或内侧为文字）一律不动；内容无变化时保持返回原对象（fast path 身份语义不变）。

3. **自动 mention 与块级 Markdown 边界**（2026-09-06）：`_inject_native_post_mentions` 对普通 prose 仍在同一 `md.text` 内前置 `<at>`；若首个 Markdown 块是 GFM 表格、无序/有序/任务列表、thematic break 或 fenced code，则先插入仅含 `<at>` 的独立 `md` 行，正文块保持逐字不变。transport 指定的当前消息者即使已在正文句中或表格单元格出现，也会被提升为首位且只生成一次原生 mention，原位置保留普通姓名；其他人的显式 `@姓名` 仍原位替换。fenced/inline code 中的字面 `@name` 不参与搬移或替换。

**表格子分支（已退役 2026-07-25）**：旧版补丁曾在检出 GFM 表格时先调 `convert_table_to_bullets()` 转成 `**行标题**` + bullet 组，规避早年"含表格的 post/md 整条空白"的客户端 bug。上游 #52786（2026-07-24 轮吸收 `prefer_post` 时的冲突来源）声称新版客户端已原生渲染表格；2026-07-25 真机实测「含 GFM 表格的 post/md 消息」正常渲染（不空白、单元格加粗正常）后，按既定计划撤除该子分支：`_build_outbound_payload` 恢复上游表格直传原文，补丁自有测试 `test_build_outbound_payload_table_converts_to_bullets_and_posts` 删除；`test_feishu.py` 中的 `test_build_outbound_payload_uses_post_for_markdown_table` 为**本地补回**的直传断言（上游已在 `6b81590c5` 低价值测试清理中删除该名字；上游现存表格测试是未改动的 `test_feishu_table_markdown.py::test_markdown_table_uses_post_not_text`）。若老客户端再现空白表格，可从外层仓历史恢复该分支（见 git log patches/local-patches.diff）。

**验证**：Step 8b 直接 import `_promote_block_markdown`，断言真实失败形状 `> **“用元层逻辑证明对象层逻辑可靠”…**` 精确输出为 `▎ **…**`；同时保留 helper、负向 `convert_table_to_bullets`、标题/引用 flanking 测试，以及自动 mention × 表格/列表/分隔线/代码块的组合矩阵。reply target 位于正文开头、句中、重复姓名/别名、表格单元格、fenced/inline code 与长消息第二分块的用例共同断言它只在首块首位出现一次；其他人的显式 mention 保持原位。`test_send_notify_table_keeps_mention_outside_table_markdown` 穿过真实 `send()` request builder，`test_send_notify_table_fallback_preserves_mention` 再覆盖 post 被拒后的 text fallback。2026-09-06 11:31 在 Data Pipeline Workshop 发送四条真机 canary：表格 `om_x100b66f9a69d80a8b26aebc511f7ec3`、列表 `om_x100b66f9a693f0a8b04304dc7ba099f`、代码块 `om_x100b66f9a6a2d4a4b39385851fe72ea`、混合格式/正文重复当前消息者 `om_x100b66f9a6b390acb4cabcac3b39d39`；API 回读均为单一首位 native mention，后续块边界完整，经典结构分别识别出独立列表行、bold/link 与 `code_block`。随后按用户授权用孙可天、张文华完成多人真群测试：prose `om_x100b66f9b3cc98b0b1a5b69738b1bc7` 与 table `om_x100b66f9b3ddd8a4b3b10baeff87dac` 均保持当前消息者首位且仅一次，另外两人的 native mention 按正文顺序/表格单元格原位保留；inline-code `om_x100b66fa49d1d8a4b343bd336dfdc80` 同时证明正文 mention 原生化、反引号内同名 `@` 保持字面量。规范 runner 的 `tests/gateway/test_feishu.py` 必须全绿；真机发送再确认 Feishu 客户端不显示原始 `**` 或 pipe table 源码。

**上游吸收判断**：若上游为飞书 post/md 原生补齐标题 / 引用渲染，或将回复改走 interactive card markdown 元素，可归档本补丁的 promote 分支；flanking 分支（修复 ②）在上游对出站 markdown 做等价 flanking 归一化前保持活跃。表格转 bullets 子分支已于 2026-07-25 真机验证原生表格渲染后撤除（该部分现与上游 #52786 行为一致，见上文"表格子分支（已退役）"）。

---

### [PATCH-FEISHU-RESPONSE-BUDGET] 生成侧软字数预算与发送侧单条 post 兜底

| 字段     | 内容                                                                                                                                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/{display_config.py,session.py,run.py}`, `plugins/platforms/feishu/adapter.py`, `tests/gateway/{test_display_config.py,test_session.py,test_feishu.py}`, Feishu/configuration 文档；外层 `config.yaml` |
| **状态** | 🟡 未上游合并；本机 `feishu` / `feishu_group` 均配置 `response_char_limit: 3000`                                                                                                                               |

**问题**：旧系统只有发送端硬切分：Feishu adapter 固定 `MAX_MESSAGE_LENGTH=8000`，任何更长回复都会在发送前拆成多条带序号消息。最近真实回复 8,397、8,703、11,351 字符均因此分段；模型在生成时不知道聊天面的阅读预算，也不会主动把长报告放进飞书文档。单纯提高硬上限只能减少分段，不能阻止冗长回答；单纯 prompt 限制又不可靠，模型偶尔超限时仍需可送达兜底。

**修复**：新增通用 `display.platforms.<platform>.response_char_limit`（整数，0=关闭，范围收敛到 0–100,000）。Gateway 按 source-aware key 区分 `feishu` DM 与 `feishu_group`，把解析值写入 `SessionContext` 并纳入 ephemeral prompt cache key；system prompt 要求最终聊天回复尽量控制在该 Unicode 字符预算内、结论优先、去重复。该预算**只约束最终飞书聊天气泡**，明确禁止据此缩短或截断飞书文档正文、HTML、附件、Markdown 源稿或工具调用 payload；这些交付物保持任务所需的完整长度。用户明确要求长报告/需求文档且有文档/文件工具时，全文写入交付物，群里只回摘要与链接/附件；不得主动把一个答案规划成多条聊天消息。发送侧独立保留硬兜底：Feishu 单条 post 保守预算从 8,000 提到 16,000，使近期 8–12k 回复即使模型没有收敛也能保持一个 post；超过 16k 仍走既有 fence-aware 切分，绝不静默丢内容。

**验证**：`test_response_char_limit_is_platform_scoped_and_normalised` 覆盖 DM/group 独立解析、字符串整数、负值关闭与其他平台不受影响；`test_feishu_response_char_limit_is_injected_and_cache_keyed` 断言 3,000 字提示、长文档转交付物规则，并证明预算变化会改变 `_ephemeral_change_key`、不会被旧 pin 吃掉；`test_send_keeps_recent_twelve_k_markdown_reply_in_one_post` 构造 >8k 且 <16k 的 Markdown，只允许一次 `msg_type=post` 请求。Step 8b 同时 import resolver/prompt/adapter 三层并检查外层配置与三条回归锚点。发送端不做 live 真群探测，避免验证制造外部消息。

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

| 字段     | 内容                                                                                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/{chat_completion_helpers.py,turn_tool_round.py,turn_tool_validation.py,turn_truncation.py}`, `tests/run_agent/{test_tool_call_incremental_persistence.py,test_run_agent.py}` |
| **状态** | 🟡 未上游合并；上游 `finish_reason=tool_calls` + 未闭合 JSON 分支仍立即终止                                                                                                         |

**问题**：大段文档/文件写入会把正文放进工具参数 JSON。参数超过预算时有的 provider 返回 `finish_reason=length`，有的 router 却改写成 `tool_calls` 并留下未闭合 JSON。前者已有 4 次有界重试并把输出预算指数提高到 8k/16k/32k；后者在 JSON 校验处直接返回 `Response truncated due to output length limit`，既不重试，也把不可靠的 finish reason 当成确定诊断。2026-08-20 创建飞书需求文档正是此路径：前序工具结果存在，下一次大参数调用被截断，创建脚本从未执行。

**修复**：抽出 `_raise_truncated_tool_call_output_cap()` 作为两类截断的单一预算函数。显式 `length` 与 `tool_calls`+未闭合 JSON 都复用同一 8k→16k→32k 上限与 4 次计数；每次从最后完整 transcript 重跑，不追加、不持久化、更不执行半截参数。若仍耗尽，关闭悬空 tool tail，并返回“工具参数无法完整生成、动作未执行”的准确错误，不再把未知 router 行为一律说成 output length。成功执行任一完整工具批次后，既有逻辑仍重置计数，单次截断不会污染后续 turn。当前 `claude-sc` 走 Chat Completions facade，沿用同一 one-shot output-cap 消费路径；Codex Responses 的独立 native transport 同样消费并立即清空该值。

**验证**：`test_hidden_truncated_tool_arguments_retry_with_larger_cap_and_recover` 构造 `finish_reason=tool_calls` + 大段未闭合 JSON，断言第一次不 dispatch、第二次请求 cap 至少 8192、完整重试只执行一次工具并正常返回；`test_truncated_tool_json_after_tool_batch_retries_then_closes_tool_tail` 提供 4 次连续失败，断言总共 6 次 API 调用后 tool tail 闭合且明确声明动作未执行。`test_claude_sc_consumes_ephemeral_output_cap` 与 `test_codex_responses_consumes_ephemeral_output_cap` 穿过真实 `_build_api_kwargs()`，分别断言 8192 cap 到达当前 SC fallback 路径与 Codex native transport，且一次性状态被清空。Step 8b 单独运行这四条测试，防止 helper 存在但分支未接线或 provider 分支忽略提升值。

**上游吸收判断**：上游让所有未闭合工具参数（不依赖 finish_reason 字面值）走统一的有界重试/预算提升并保持半截调用零副作用后可归档；若 provider 层能保证真实 `length`，仍需保留 router 改写的回归测试再判断是否收缩。

---

### [PATCH-MODEL-CONFIGURED-ONLY] `/model` 只访问配置内主模型与 fallback

| 字段     | 内容                                                                                                                                                                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `hermes_cli/model_switch.py`, `gateway/{run.py,slash_commands.py,slash_commands_model.py}`, `tests/hermes_cli/test_tools_config.py`, `tests/gateway/test_config.py`, `tests/run_agent/test_provider_fallback.py`, `tests/run_agent/test_compressor_fallback_update.py`, 外层 `config.yaml` |
| **状态** | 🟡 本地模型访问边界；`model_catalog.configured_only: true` 时启用                                                                                                                                                                                                                          |

**问题**：无参数 `/model` 原生调用 `list_authenticated_providers()`，展示整台机器上检测到凭据迹象的 provider 及其在线/缓存模型目录，而不是当前 profile 的配置集合。shell secrets、credential pool 或普通 `GITHUB_TOKEN` 都可能制造链外模型入口；文本 `/model <name> --provider <slug>` 还能直接切换到这些链外 provider。用户要求 Hermes 只能访问 `config.yaml` 中显式声明的主模型与 `fallback_providers`，引入新模型必须先手工改配置。Gateway 另有一层 raw-YAML 快速读取：若 fallback model 写成 `${VAR}`，列表/预校验会看到占位符，而共享切换核心看到展开后的值，导致同一合法 route 自相拒绝。

**修复**：新增 configured-only 路由表，只从 `model.default/provider` 和有序 `fallback_providers` 构造模型 universe，不扫描 ambient credentials、auth pool、models.dev 或 provider `/models`。路由表复用配置层 `${VAR}` / `${env:VAR}` 展开语义，使 Gateway raw YAML、CLI `load_config()` 和共享核心比较同一 provider/model identity。无参数 `/model` 只显示这些精确 route；Gateway 文本/交互选择和共享 `switch_model()` 核心都只允许切换到同一集合，CLI/TUI/Dashboard 等其它入口同样无法绕过。链外 provider/model 直接拒绝，严格模式强制 session-scoped，并禁止 global switch 绕过手工配置边界。主动切换不改写 fallback 列表：primary 等于 fallback-A 时跳过重复 A、保留 B；primary 等于 fallback-B 时先回退 A、随后跳过重复 B。`auxiliary.compression` 继续读取独立配置，切换 primary 只改变摘要 route 失败时的 current-main fallback，不改变 compaction 首选 route。

**2026-09-03 route identity 加固**：配置存在但 YAML 顶层为 list/scalar 时与语法损坏一样 fail closed，不能退化成空 mapping 后重新开放 ambient catalog。完整 configured route 若自带 `base_url + key_env`，直接使用该 endpoint/credential，不先依赖普通 provider resolver；同 provider/model 的多个 endpoint 生成稳定的 `configured-route:<index>:<provider>` selector，picker、Gateway 预校验和共享 switch 全链保留。过期/无效 selector 或缺少当前 endpoint 的歧义输入均拒绝，不猜测第一条 route。

**验证**：`test_configured_model_picker_contains_only_config_models` 使用通用 primary/fallback-A/fallback-B fixture，断言列表完全由传入 config 动态生成，并覆盖 `${VAR}` / `${env:VAR}` 展开、provider-only/唯一 model 解析与链外拒绝；`test_configured_model_routes_preserve_endpoint_identity_and_overrides`、`test_switch_model_uses_complete_configured_route` 锁定 endpoint/auth/request 元数据；`test_configured_model_picker_exposes_duplicate_endpoints_as_unique_routes`、`test_switch_model_uses_picker_selector_for_duplicate_endpoint` 与 `test_model_command_preserves_duplicate_endpoint_selector` 锁定多 endpoint 可见、可选且不丢 selector；`test_complete_configured_route_bypasses_ambient_provider_resolver` 证明 route 自带 endpoint/key 时不受 ambient resolver 故障影响；`test_model_command_fails_closed_when_config_is_unparseable`、`test_model_command_fails_closed_when_config_root_is_not_mapping` 与 `test_switch_model_fails_closed_when_policy_config_cannot_be_loaded` 锁定配置读取失败不放开 catalog；`test_model_command_lists_only_configured_routes` 证明 `/model` 显示展开后的 route、不出现任何未配置 provider，链外与 `--global` 在调用 switch 前被拒绝；共享 core 测试证明非 Gateway 调用面也受到同一 guard。`test_primary_fallback_a_skips_duplicate_and_falls_to_b` / `test_primary_fallback_b_uses_a_before_skipping_duplicate` 成对覆盖 primary 与 fallback 去重；compressor 回归证明 primary 切换后主 runtime 更新，但独立 `summary_model` 原值保持不变。当前生产 config 的 Azure/SC Claude/Vertex 只是该动态规则的一次实例，未来替换具体 provider/model 不需要改补丁或测试。Step 8b 将上述生产锚点和测试纳入 8c 总闸门。

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

**当前适用性（2026-09-10）**：主力为 `azure-foundry/gpt-5.5`，`claude-sc/claude-fable-5-1` 是首级 fallback，标准 `vertex/google/gemini-3.7-flash` 是末级 fallback、视频旁路与 compression provider。本补丁只在 `VertexProfile` 内生效，对 Azure/SC Claude 零作用面；一旦回退双层写法，Vertex 的 thought text 会重新混入飞书可见正文，因此仍必须保留。

**验证**：Step 8b grep `plugins/model-providers/vertex/__init__.py` 存在 `include_thoughts=true` 说明、`thinking_config["include_thoughts"] = False` 与**单层** `return {"google": {"thinking_config": thinking_config}}`；测试同时保留 profile 正反例，并以 `test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `ChatCompletionsTransport.build_kwargs()`，断言最终请求 kwargs 只有单层 `extra_body.google.thinking_config`。真链路 A/B 对比（Vertex OAuth token，同一 plan 类 prompt）：**A 单层 → 干净答案**；**B 双层（旧）→ `" Too simple, doesn't add value…"` 思考泄漏**。2026-08-03 主会话复测因 Google OAuth 链路瞬时 SSL EOF 自动回退到 Qwen，但仍证明出站最终 `content` 与隐藏 `reasoning` 分离；Vertex wire request 形状由规范 runner 的边界测试持续锁定。

**注**：`plugins/model-providers/gemini/__init__.py`（AI-Studio `gemini` provider）存在同构的双层写法，但本环境不走该 provider，暂不改动，待验证。

**上游吸收判断**：若上游能把 Vertex OpenAI-compatible 返回的 Gemini thoughts 解析并存入隐藏 reasoning 字段，或官方 Vertex profile 默认隐藏 thoughts 且保留 thinking level，可归档本补丁。**隐式合约依赖**：本补丁的单层返回形状依赖基类 `ProviderProfile.build_extra_body` 的"返回值 merge 进 extra_body"约定；每轮升级必须复核该基类合约未变（`test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `build_kwargs()` 锁定最终 wire 形状，合约变化会在该测试直接暴露）。2026-08-03 对 post-26e0b1c 上游复核：插件仍是双层包裹 bug 原样，未吸收。

---

### [PATCH-VERTEX-DOCTOR] Doctor 识别官方 Vertex provider

| 字段     | 内容                                                                         |
| -------- | ---------------------------------------------------------------------------- |
| **文件** | `hermes_cli/{doctor.py,doctor_config.py}`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🟡 未上游合并                                                                |

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

### [PATCH-TEST-RUNTIME-STATE-ISOLATION] pytest 不得污染真实运行态文件

| 字段     | 内容                                                        |
| -------- | ----------------------------------------------------------- |
| **文件** | `tests/conftest.py`, `tests/test_runtime_home_isolation.py` |
| **状态** | 🟡 未上游合并；测试基础设施安全补丁                         |

**问题**：全局 pytest fixture 会把 `HERMES_HOME` 重定向到每测试临时目录，但大量 legacy 测试在函数体内使用 `patch.dict(os.environ, {}, clear=True)`，会在 fixture 生效后再次清空 `HERMES_HOME` 与 `HERMES_TEST_ISOLATION`。`gateway.status._get_process_hermes_home()` 随即回落到真实 `~/.hermes`；v0.20.6 新增的 machine-root `hermes_cli.process_identity._ledger_path()` 也绕过 profile sandbox。2026-08-27 的 canonical/final audit 实际把生产 `gateway_state.json` 覆写为已退出的 `pytest tests/gateway/test_feishu.py` PID，同时测试进程可向真实 `spawn-ledger.json` 写入条目；所有测试仍为绿色，属于运行态污染型假绿。

**修复**：`tests/conftest.py::_hermetic_environment` 除设置环境变量外，再用 pytest `monkeypatch` 将两个动态写路径 chokepoint 固定到当前测试的 `fake_hermes_home`，因此测试体即使清空整个环境也无法回退生产根目录；fixture 返回该路径供边界回归直接核对。改动只影响 pytest 进程，生产路径解析保持 upstream 原样。

**验证**：`tests/test_runtime_home_isolation.py::test_runtime_identity_paths_stay_sandboxed_when_environment_is_cleared` 在 autouse fixture 完成后再次清空 `os.environ`，先断言 Gateway 状态与 spawn ledger 路径仍指向本轮临时目录，再真实写入两种状态文件并验证落点。Step 8b 独立运行该节点；final-audit 还必须在 canonical suite 之后核对生产 `gateway_state.json` 的 PID、argv 与 `code_sha` 属于当前真实 Gateway，而不是 pytest。

**上游吸收判断**：当 upstream 测试基础设施能在任意测试级环境清空后仍强制所有 Gateway/process-identity 写路径落入隔离目录，并带等价的双文件真实写入回归时，可删除本补丁。仅在 fixture 开头设置 `HERMES_HOME`、但允许测试体随后清空它，不构成吸收。

---

### [PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY] Gemini fallback 接受跨模型工具历史

| 字段     | 内容                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------ |
| **文件** | `agent/transports/chat_completions.py`, `tests/agent/transports/test_chat_completions.py`        |
| **状态** | 🟡 未上游合并；独立于已归档的 `PATCH-GEMINI-THOUGHT-SIGNATURE`（保留已有签名 vs 补齐无签名历史） |

**问题**：Gemini 3 thinking 模型要求 replay 的每个 `functionCall` 携带 `thought_signature`。上游已能保留 Gemini 自己返回的真实签名，但当会话先由 Azure GPT-5.5 或 SC Claude Fable 5.1 执行过工具、随后 fallback 到标准 `vertex/google/gemini-3.7-flash` 时，历史 tool call 天然没有 Gemini metadata。2026-08-14 的原始复现发生在旧 `vertex-fallback` 路径；provider 收敛后，同一跨模型历史不变量仍然成立。

**修复**：在 `ChatCompletionsTransport.convert_messages()` 的 Gemini-family 出站分支中，对缺少嵌套 `extra_content.google.thought_signature` 的历史 tool call 使用 copy-on-write 注入 Google 官方兼容哨兵 `skip_thought_signature_validator`；如果旧 adapter 留下直接位于 `extra_content.thought_signature` 的真实签名，则把原值规范化到 Google wire shape，不用哨兵覆盖。Gemini 已有真实签名保持原样，原始会话历史不被修改；非 Gemini 目标仍按上游既有逻辑剥离 `extra_content`，避免严格 OpenAI-compatible provider 拒绝未知字段。

**验证**：`tests/agent/transports/test_chat_completions.py` 的 `test_gemini_fallback_adds_signature_to_cross_provider_tool_history` 通过真实 `build_kwargs()` 边界构造 Azure/Codex 风格的 `skill_view` tool call（含 `call_id` / `response_item_id`、无 Gemini metadata），断言最终 provider request 删除 Codex 私有字段并注入嵌套兼容签名，同时原 history 不变；`test_gemini_fallback_preserves_real_signature` 与 `test_gemini_fallback_normalizes_legacy_direct_signature` 分别覆盖已有真实签名 identity-preserve 与 legacy direct signature 规范化。Step 8b 直接 import `ChatCompletionsTransport` 并执行无签名历史转换，不依赖私有 helper 名；补丁测试必须由 `scripts/run_tests.sh` 运行。

**上游吸收判断**：当上游 Chat Completions transport（或通用 provider-switch history adapter）原生在切换到 Gemini/Gemma 时，为所有无签名历史 function call 补充官方 skip-validator 哨兵，同时保持真实签名、非 Gemini 严格字段清理和 copy-on-write 不变量，并有跨 provider 回归测试后，可删除本地 hunk、Step 8b gate 和两个受管文件并将本块移入 Archive。仅有 `ToolCall.extra_content` 保留能力不算吸收。

### [PATCH-IMAGE-NATIVE-ROUTING] 主力模型图片能力识别与原生路由

| 字段     | 内容                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `agent/models_dev.py`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py` |
| **状态** | 🟡 未上游合并                                                                                                                             |

**问题**：`image_input_mode:auto` 只在能力**确认为 True** 时走 native，其余一律 `return "text"`（`image_routing.py` 决策尾部），退回 auxiliary `vision_analyze` 文本预分析。当前路由需要从三个来源明确能力：

- **Vertex**：OpenAI-compatible endpoint 没有可靠 `/models` discovery，模型目录也可能尚未收录 Gemini 3.x preview slug；Vertex-only 安装还没有辅助 vision 凭据，退化后直接失败。
- **azure-foundry**：`PROVIDER_TO_MODELS_DEV` 缺少该 provider 条目（2026-08-11 定位），`_get_provider_models()` 返回 None → `get_model_capabilities()` 返回 None → **该 provider 下所有模型的全部能力都查不到**（vision/tools/reasoning/limit）。gpt-5.5 因此被判 `image=text`，尽管目录里 `azure.gpt-5.5` 明确是 `modalities.input: [text, image, pdf]`、且实测 Responses API + `input_image` 原生读图正常（5.78s 正确识别）。后果不是失败而是静默绕路：同一模型被调两次（先 `vision_analyze` 生成描述、再拿二手描述回答），细节（小字、坐标、渐变）在中转丢失。
- **SC Claude**：用户级 provider 插件声明 Fable 5.1 支持图片，但该私有模型不在 models.dev；因此生产配置通过 `providers.claude-sc.models.claude-fable-5-1.supports_vision: true` 使用 Hermes 原生 capability override，避免先做有损文本预分析。

**修复**：三个能力来源、一个不变量（主力模型能读图就必须原生读）：

- 窄口径 `_known_provider_model_supports_vision(provider, model)`：标准 Vertex Gemini 3.x 返回 `True`；其他未知 provider/model 继续 fail-closed。显式 `supports_vision: false` 仍优先覆盖。
- `PROVIDER_TO_MODELS_DEV` 新增 `"azure-foundry": "azure"`。选 `azure` 而非 `azure-cognitive-services`：前者是后者的严格超集（+14 模型 / -0，gpt-5.x 覆盖一致）。这是**接目录**而非加白名单——一次修复该 provider 全部 82 个模型的 vision/tools/reasoning/limit，且随上游目录自动更新，不需要为每个新模型维护本地清单。上下文长度另有独立静态表（`model_metadata.py` 已含 `gpt-5.5: 1050000`），不受此缺口影响。
- SC Claude 走上游已有的 per-provider/per-model capability override；配置只声明当前实测通过的 `claude-fable-5-1.supports_vision: true`，不在核心代码硬编码私有 provider 或域名。

**验证**：Step 8b 锁定 known-provider helper、标准 `"vertex"`、Gemini 3.5 Flash slug、SC Fable 的配置能力覆盖与 Gateway 真实边界测试、`"azure-foundry": "azure"` 映射及 Azure catalog 测试。`test_fallback_chain_models_all_route_images_natively` 证明当前 Azure GPT-5.5 → SC Claude Fable 5.1 → Vertex Gemini 3.5 Flash 三档图片全部 native；`test_auto_native_for_azure_foundry_gpt55_from_catalog` 直接执行 `agent/models_dev.py` 的 Azure catalog 映射。

**上游吸收判断**：三个单元共享"auto 模式下主力模型图片能力识别"这一责任边界与同一 Step 8b gate，必须一起回滚验收。上游 capability catalog/provider profile 同时稳定声明 Vertex Gemini 3.x 与 azure-foundry 图片能力后可归档对应源码 hunk；SC Claude 使用上游已有的显式 capability override，不构成新的内层 patch。

---

### [PATCH-VERTEX-VIDEO-ROUTING] Gemini 视频原生路由

| 字段     | 内容                                                                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `gateway/{run.py,run_inbound.py,run_turn_runner.py,session_state.py}`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py` |
| **状态** | 🟡 未上游合并；依赖 `PATCH-IMAGE-NATIVE-ROUTING` 的 Vertex/Gemini 识别                                                                                                                    |

**问题**：上游视频只注入本地 path note，期望模型自行用 ffprobe/ffmpeg；群聊没有 terminal，因而即使附件已缓存也看不到视频内容。图片能力不能直接等同视频能力，且视频没有缩图重试，必须使用更窄的白名单和大小边界。

**修复**：新增 `decide_video_input_mode`、独立 Vertex+Gemini 3.x 视频白名单、magic-byte/MIME 校验和 14 MB 内联上限。支持的视频转换为 `data:video/*;base64` content part；gateway 用 session buffer 把 native video paths 传给 content builder，超限/不支持视频继续交给 `PATCH-MULTIMODAL-SIDECAR`，若仍失败则给 path-free `FAILED` 状态。无需给群聊放开任何命令工具。**2026-08-07 审计修复两处接线缺陷**：① gateway wrapper `_decide_image_input_mode` 曾把 `kind=kind` 直传给不接受该参数的 `decide_image_input_mode`（本地=上游签名均无 `kind`），TypeError 被 fail-open except 吞掉后**所有**网关图片/视频路由静默退化为 `"text"`——视频补丁在生产路径完全失效、图片路由连带破坏（上游 `test_pre_turn_named_custom_provider_identity_selects_vision_override` 在 worktree 上 1 failed，该文件当时不在补丁测试清单故 815/0 未暴露）；现 wrapper 内按 kind 分流，`kind=="video"` 直连 `decide_video_input_mode`（无网络 I/O，同时消除 async handler 内的同步阻塞隐患），图片路径恢复上游原签名调用。② 视频 buffer 补齐与图片路径对称的**每轮重置**（`_consume_pending_native_video_paths(session_key)`），杜绝被中止 turn 的视频泄漏进同会话下一轮。

**验证**：Step 8b 单独检查 video decision、native-video session buffer、**gateway 接线**（`return decide_video_input_mode(` 与 per-turn consume 锚点，2026-08-07 起——此前四个锚点全部只锚定义与测试名，功能整体失效时 gate 仍报 active）和 data-URL 回归；`test_gateway_kind_video_routes_through_video_decision_table` 从 runner 边界证明 kind="video" 真正抵达视频决策表（vertex+gemini-3 → native、非白名单 → text）；`test_prepare_resets_stale_video_buffer_per_turn` 穿过真实 `_prepare_inbound_message_text` 证明陈旧视频 buffer 与图片 buffer 一同被每轮重置；`test_turn_runner_attaches_buffered_native_video_once` 直接执行 v0.21 拆分后的 `TurnRunner._native_image_run_message()`，锁定视频 buffer 只消费一次并传给 native content builder；测试另覆盖 Vertex primary/fallback、非视频模型、显式配置、MIME/大小守卫和实际 content parts。

**上游吸收判断**：上游提供通用 native video routing、明确的视频 capability 和等价 MIME/size safety 后可归档。

---

### [PATCH-MULTIMODAL-SIDECAR] 主力模型读不了媒体时的旁路读取

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                   |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/{auxiliary_client.py,image_routing.py}`, `gateway/{run.py,run_inbound.py,session_state.py}`, `tools/vision_tools.py`, `tests/agent/{test_auxiliary_client.py,test_image_routing.py}`, `tests/gateway/test_image_input_routing_runtime.py`, `tests/gateway/test_telegram_audio_vs_voice.py`, `tests/tools/test_video_analyze.py` |
| **状态** | 🟡 未上游合并；主模型 native 优先，本补丁为图片/音频/视频/PDF 的有界旁路                                                                                                                                                                                                                                                               |

**问题**：原 sidecar 只覆盖视频。普通音频附件只留下文件路径，语音 STT 失败后也没有媒体理解兜底；扫描 PDF/空文本 PDF 本地抽取失败后只能让 agent 再调工具；未知/文本型图片主模型还可能让 `vision_analyze:auto` 重新选择当前模型，重复分析。Google 官方 Gemini 3.5 Flash 模型卡实际支持 Text、Image、Audio、Video，并原生接受 `application/pdf`/`text/plain`；当前 Vertex OpenAI-compatible wire 已用合成 440Hz WAV（2.7s）和 ORCHID-42 PDF（3.8s）真调用验证 `image_url` + 对应 `data:` MIME 可用。初版泛化后仍把成功 sidecar 的 cache path 与具体 model ID/ARN写进主 turn，并在超限、不支持 MIME、reader 空结果时回落到“让模型自行打开绝对路径”；群聊沙箱正确拒绝该路径，却让用户看到“无法读取原文件”，也多耗一次工具调用。native content part 同样把本地路径作为文本 hint 暴露，即使媒体字节已经在相邻 data URL 中。

**修复**：把 picker/执行器泛化为 `pick_multimodal_sidecar_route(cfg, kind)` 与 `_enrich_message_with_multimodal_sidecar(..., kind=...)`，按 `get_fallback_chain()` 顺序为 image/audio/video/document 选择真实具备该模态的 route。主模型已确认 native 时不绕路；图片 text 档、普通音频附件、语音 STT 全失败、非 native 视频，以及 PDF/text 本地抽取为空或 coverage 发现扫描缺口时，才发送**单个媒体字节 + 本轮 caption/引用上下文**。Gemini Flash 支持的 inline MIME 统一使用 `image_url` + `data:<mime>;base64`；14 MB raw 上限与文件读安全守卫保持 fail-closed。native text part 改用 `[Image/Video attachment N included]` 序号，sidecar 成功只说“configured capable route 已读取”，不外显路径、provider/model/ARN；可信抽取、STT、vision 与所有 reader 失败也统一走 `_attachment_failure_note`，给 `FAILED + 分类原因 + 不得声称读过 + 请求重发`，不再提供群聊不可达的工具路径。文本与可提取文档继续本地处理，不无条件外发；DOCX/XLSX/PPTX 等模型卡未列的 MIME 不进入 sidecar。

**2026-09-03 显式路由隐私语义**：`auxiliary.vision.provider` 一旦显式配置，就是唯一允许接收当前媒体的 outbound route；即使 model 留空或 capability 元数据未知，也先尝试该 route，失败时返回显式 `FAILED/INCOMPLETE`，不得重新调用 auto/ambient provider。sync 与 async client 都固定 `allow_provider_fallback=False`，Gateway sidecar 调用也必须原样传递；这是“可能少读一次”优先于“把媒体发给未授权 provider”的隐私边界。

关键取舍——**旁路而非切 provider**：整轮切到 Vertex 会重放全量 transcript，并可能跨 issuer 携带不可重放的 reasoning 载荷。sidecar 只发一次独立请求，主模型身份、工具、历史和 fallback 状态不变；输出以纯文本进入主会话。上下文统一上限 4,000 字；图片 120s、音频/PDF 180s、视频 420s。语音优先本地 STT，只有全失败才旁路，避免重复计费和双份转写。

附带修复（同一责任边界，故并入本补丁）：`video_analyze_tool` 原先只发 `video_url` content part，而 Vertex OpenAI-compat 端点直接 400 `Unrecognized 'type' field in an object element of an array 'content' field; found: 'video_url'`——agent 自己调 `video_analyze` 在 Vertex 上是**硬失败**。改为捕获该错误后以 `image_url` + `data:video/*;base64` 形状重试一次（Vertex 对所有内联媒体都用这个形状）。不做 per-provider 硬表：DashScope/Qwen-VL 确实要 `video_url`，只有 provider 明确拒绝时才换形状。

**验证**：Step 8b 锁定通用 picker、audio/document 能力、data URL 构造、四类生产接线、上下文上界、视频形状兼容重试、path-free content labels 与端到端测试。`test_pinned_vision_route_does_not_fall_back_to_auto` 与 `test_pinned_async_vision_route_does_not_fall_back_to_auto` 分别锁定 sync/async 显式 auxiliary route 不会在缺凭据或失败时外溢到 ambient provider；`test_prepare_runs_video_sidecar_when_main_model_lacks_video` 额外断言 Gateway 传递 `allow_provider_fallback=False`。`test_prepare_runs_audio_sidecar_for_audio_attachment`、`test_prepare_runs_pdf_sidecar_when_local_extraction_is_empty` 与 `test_prepare_adds_pdf_visual_sidecar_when_text_coverage_has_gaps` 分别穿过真实 `_prepare_inbound_message_text` 证明音频/PDF 路由；均断言 `data:video/audio/application-pdf` wire、无全 transcript、成功 prompt 不含原路径/具体 ARN。`test_video_url_rejection_retries_as_image_url` 直接执行 `tools/vision_tools.py` 的 provider video-part 兼容重试。`test_prepare_reports_path_free_failure_when_no_link_can_read_video` 等反例对无能力 route、超限/不支持 MIME 与全部 reader 失败断言明确 `FAILED` 且不含路径；本地 STT 成功保持不旁路。`test_feishu_group_image_native_and_audio_video_sidecars` 锁定 Feishu group consumer 的图片 native、音视频 sidecar 与 path-free 交付。

**上游吸收判断**：若上游提供"能力不足时按 modality/capability 自动选辅助后端"的通用机制，覆盖图片、音频、视频与 PDF/text 文件，且保证 bounded current-turn context、native-first、无 transcript replay、无重复分析、path-free 成功提示和显式失败状态，可归档通用 picker/sidecar；provider profile 原生提供媒体 part 形状协商时可单独收缩兼容 hunk。picker 仍依赖 `get_fallback_chain()` 的 list[dict] 契约。

---

**类别：历史保留、审批与本地运行兼容**

### [PATCH-HISTORY-RETENTION] 平台级回放历史保留窗

| 字段     | 内容                                                                                                                                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/replay_cleanup.py`, `gateway/{run.py,run_turn_runner.py}`, `tests/agent/test_replay_cleanup.py`, `tests/gateway/test_stale_confirmation_expiry.py`（配置键 `gateway.history_retention` 在 `~/.hermes/config.yaml`，非 PATCHED_FILES） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                |

**问题**：（2026-07-14 复盘 SpaceSight Tech Sharing Group 历史污染）共享群 session 每轮把**全量** transcript 回放给模型（`load_transcript` → `_build_gateway_agent_history`），唯一的历史收敛机制是按 token 触发的 hygiene/压缩——大上下文模型（Gemini 3.1 Pro）上 94 条消息远够不到 85% 阈值，从不触发；且压缩是摘要不是丢弃。结果是 7 月 10 日 随消息入库的一次性 `[Feishu assistant mode]` 指令块 + 模型照做的范例，在 7 月 14 日 第三方 @bot（零注入分支）轮次里仍然整段可见，模型据此模式补全出「我是琛哥的赛博小助手…琛哥可能在忙」的代答口吻。缺一个与 token 无关的、按**墙钟时间和条数**的回放上界。

**修复**：`agent/replay_cleanup.py` 新增 `apply_history_retention(history, now, max_age_seconds, max_messages)`（sentinel `history-retention`）：视图级过滤——state.db 完整保留（审计 / `/resume` / 搜索不受影响），只裁剪发给模型的回放。语义：切点只落在**轮边界**（普通 user 行，`_retention_turn_starts`），绝不切断 assistant(tool_calls)→tool 配对；时间窗按整轮的开头 user 行 `timestamp` 判断，无时间戳的行视为"新"（兼容旧转录与内存脚手架，防止配置误伤成批丢历史）；条数上限向轮边界**向上取整**；最新一轮无论多旧/多长永远保留；两个限制同时配置取更严格的切点；无 user 行的退化历史原样返回。`gateway/run.py` 新增 `_history_retention_limits_for_source()`：从 `gateway.history_retention.<platform-key>` 读取限额，platform-key 复用工具/skill 配置同款 chat-scope 拆分（飞书群=`feishu_group`、私聊=`feishu`），未配置或值非法一律 fail-open 返回 None。注入点在 `_run_agent_inner` 的 cached-agent 守卫（`_select_cached_agent_history`）**之后**，单点同时覆盖「盘上转录」与「内存活转录」两条路径。本机 `config.yaml` 配置 `feishu_group: {max_age_seconds: 21600, max_messages: 30}`（6 小时 / 30 条），私聊与 CLI 不配置、行为不变。

**验证**：Step 8b grep `agent/replay_cleanup.py` 中存在 `def apply_history_retention`、`def _retention_turn_starts`，grep `gateway/run.py` 中存在 `_history_retention_limits_for_source`，并 grep `gateway/run_turn_runner.py` 中的实际应用点；`tests/agent/test_replay_cleanup.py` 的 `test_retention_never_splits_tool_call_blocks`、`test_retention_newest_turn_always_kept_even_if_too_old` 与 `tests/gateway/test_stale_confirmation_expiry.py` 的 `test_retention_feishu_dm_not_covered_by_group_key` / `test_turn_runner_applies_history_retention_before_media_scan` 覆盖时间窗丢整轮、条数向轮边界取整、tool-call 块不被切断、最新一轮超龄/超量仍保留、未配置/畸形配置 fail-open、DM 不受群键影响及 v0.21 split owner 接线。

**上游吸收判断**：若上游为 gateway 回放历史提供原生的时间窗/条数保留配置（或给共享群 session 引入等价的 per-platform replay 上界机制），可归档本补丁。

---

### [PATCH-APPROVAL-DARWIN-TMP] Darwin verify-artifact 临时路径归一化

| 字段     | 内容                                                                                                                                                                                                                                                  |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `tools/approval_detection.py`（仅 `_is_verification_artifact_cleanup` 的 `allowed_spellings` hunk）, `tests/tools/test_approval.py`（仅 `test_darwin_private_alias_accepts_raw_temp_spelling`）——测试文件的其余 hunk 属 `PATCH-FEISHU-GROUP-APPROVAL` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                         |

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

**验证**：Step 8b 继续检查 Darwin/vendored-header/linker 锚点；full `scripts/test_patch_evidence.py::audit_fts5_build` 把当前 native 源码与实际 build.sh 复制到隔离临时目录，执行真实构建/安装，再在独立进程加载新产物并创建 `cjk_unicode61` FTS 表验证中文索引命中。若本机 lib 目录已有安装产物，也对它做同样的只读加载/查询。随后运行严格 JUnit 的 `tests/test_fts_cjk_bigram.py`，覆盖 SessionDB 集成；不能用测试自带的另一套 gcc 参数替生产 build.sh 证明。`test_fts5_probe_rejects_a_broken_actual_build_script` 注入 build exit 23 和不可加载的已安装产物，两者均拒绝。

**上游吸收判断**：上游给 build.sh 加 Darwin 分支（或改用统一走 api 指针的构建方式）后，可归档本补丁。

---

**类别：外层插件与群聊能力边界**

### [PATCH-CLAUDE-SC-PROVIDER] SC Claude 用户级 provider 接入

| 字段     | 内容                                                                                                                                                                                                                |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | 配置仓库：`.env.example`, `config.yaml`, `plugins/model-providers/claude-sc/{__init__.py,plugin.yaml,verify.sh}`, `README.md`, `hermes-update.sh`, `scripts/test_patch_evidence.py`（均不属于内层 `PATCHED_FILES`） |
| **状态** | 🟢 配置仓库用户插件；升级保留，Step 8e 强制回归                                                                                                                                                                     |

**问题**：原 fallback[0] 使用 Hermes 原生 Bedrock provider 与 inference-profile ARN。切换到 `~/bin/claude-sc` 同源服务时，普通 `provider: anthropic + base_url` 会让 Python Anthropic SDK 对第三方 host 使用 `x-api-key`，而 SC 实测要求 Bearer token、Claude Code 客户端身份和 JavaScript SDK 的 `x-stainless-*` 请求指纹；直接配置会稳定返回 HTTP 401/403。把 SC 域名硬编码进 `hermes-agent` 核心会新增难维护的私有 provider patch，并在上游升级时扩大冲突面。

**修复**：使用 Hermes 原生 `$HERMES_HOME/plugins/model-providers/` 扩展点注册 `claude-sc`。插件从 profile `.env` 读取 `CLAUDE_SC_BASE_URL` / `CLAUDE_SC_AUTH_TOKEN`，通过请求 hook 强制 Bearer、Claude Code `User-Agent`/`x-app`/session id 和对应 Stainless 身份，再复用 Hermes 已有 `AnthropicAuxiliaryClient` 完成 Messages 转换、tool_use/tool_result、reasoning 与响应归一化。profile 以 `create_client` 扩展点接入主模型和 fallback 共用路径；`config.yaml` 将 fallback[0] 固定为 `claude-sc/claude-fable-5-1`，并通过上游已有的 per-model capability override 声明已实测图片能力。原 Bedrock 专项图片 ARN 识别、Bedrock output-cap 补线和状态样例从内层 replay bundle 移除；通用 fallback、截断恢复、跨 provider 工具历史、Vertex 末级回退和 compression 均保留。

**验证**：`plugins/model-providers/claude-sc/verify.sh` 由 `hermes-update.sh` Step 8e 强制执行，并由 `scripts/test_patch_evidence.py::audit_claude_sc_provider_verifier` 在 full evidence 中记录结果。verifier 检查 fallback 顺序、Fable 5.1 图片 capability、`.env` 权限与凭据存在性、provider 注册、`~/bin/claude-sc` 可执行性、runtime 解析，以及离线 mock request 的 Bearer-only 认证、Claude Code/JavaScript SDK 请求身份、OAuth-compatible system/tool 名转换、high reasoning 与 prompt-cache marker；同时要求当前 Gateway 子进程晚于 plugin/config 修改时间。人工真链路 canary 另覆盖文本、工具调用、原生图片和“主路由失败 → SC 接管”。

**上游吸收判断**：当 Hermes 的 `ProviderProfile` 原生支持可配置的 Anthropic Bearer 认证、请求身份/header hook，并且该能力同时贯通主 agent、fallback、辅助调用、工具、图片和 prompt caching 时，可删除本插件并改回纯声明式 provider 配置；此前不得把 SC 降级为普通 `x-api-key` Anthropic endpoint，也不得为私有域名修改内层源码。

---

### [PATCH-FEISHU-GROUP-SANDBOX] 飞书会话结构化 tmp 与固定文档动作边界

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | 配置仓库：`.env.example`, `config.yaml`, `plugins/sandbox/{__init__.py,config.yaml,plugin.yaml,test_sandbox.py,verify.sh}`, `my-skills/creative/{image-generation/SKILL.md,chart-generation/SKILL.md}`, `my-skills/productivity/{hypertex-mcp/SKILL.md,feishu-docs/{SKILL.md,references/document-images.md,scripts/create_new_doc_from_md.py,scripts/download_feishu_file.py,scripts/feishu_common.py,scripts/manage_doc_image.py,scripts/read_docx_to_markdown.py,scripts/read_feishu_url.py,scripts/stage_remote_images.py,scripts/test_manage_doc_image.py,scripts/test_read_feishu_url.py,scripts/test_stage_remote_images.py}}`, `scripts/{pull_feishu_people.py,test_pull_feishu_people.py}`, `memories/MEMORY.md`, `hermes-update.sh`, `hermes-update.md`, `README.md`（均不属于内层 `PATCHED_FILES`） |
| **状态** | 🟢 配置仓库用户插件补丁；升级保留，Step 8e 强制回归                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

**2026-09-01 owner DM 飞书文档插图桥接增量**：主会话真实 Task 62/64 暴露了群聊素材桥未覆盖 owner DM：模型已导出图片并把 6 个路径写入 iterate 参数，但旧 bridge 仍以当前消息附件覆盖调用方路径，`media=0` 时实际传入空数组。现让固定 `feishu_doc_manage(read_url, include_images=true)` 在 owner DM 中把图片写入 `~/.hermes/tmp/feishu-doc-assets/<chat-id-hash>/`，仅返回相对 `image_path`；HyperTeX 只接受该精确会话 workspace 内的普通文件并再次复制到私有 staging。一次性历史目录 `~/.hermes/tmp/hypertex_doc_assets/` 明确不纳入信任根、不迁移旧素材。插件现有 **129 条**回归覆盖 owner reader 正例、私有 workspace → staging 正例、历史目录与任意外部路径反例；新任务必须重新走固定 reader，不能复用偶发手工路径。

**2026-09-03 当前消息 Markdown 资源引用增量**：真实群消息使用 `[标题](https://.../sheets/TOKEN)正文`，旧裸 URL 扫描会跨过 Markdown 右括号并把紧随的 CJK 正文吞进 URL，导致精确 provenance 白名单错误拒绝。插件 `0.7.14` 在不读取 `channel_context`、不扩张域名的前提下，解析 Markdown destination 与裸资源 URL，并把 `/wiki/`、`/sheets/`、`/base/`、`/slides/` 纳入同一 URL/token canonicalization；未知资源和历史链接继续 fail closed。共享 `(chat_id, turn_id, capability)` 原子 claim 同时封住跨 worker 的 HyperTeX/图片/图表重复调用；未完成/未过期 claim 不按 2048 容量驱逐，满载时新调用 fail closed，明确 `post_llm_call` 完成后释放，异常遗留仅在 7 天 TTL 后退场。固定文档脚本输出先将当前 workspace 相对化，再把其他 `HERMES_HOME` 路径统一改写成 `<HERMES_HOME>/...`，真实 traceback 不泄露宿主脚本/插件/venv 绝对路径；`/slides/` 返回结构化 unsupported 而非伪成功。对应正反例覆盖当前/历史资源边界、并发 worker、超过旧容量的长 turn、完成/TTL 释放、真实失败 traceback 与 unsupported 状态。

**依赖**：`PATCH-FEISHU-GROUP-SCOPE` 提供 `feishu_group` namespace，并保证真实 Gateway consumer 使用该 key；`PATCH-PLATFORM-CAPABILITY-SCOPE` 提供只读工具集，`PATCH-FEISHU-GROUP-APPROVAL` 提供审批层纵深防线；`PATCH-FEISHU-ADMIN-CONTROL-SCOPE` 将群内 owner 新会话与主 DM Gateway 管理分开，verifier 同时核对实际 owner 身份、home DM 与 sandbox 唯一主私聊一致。依赖缺失时 Step 8b/8e 分别失败，不允许把插件显示为健康。

**问题**：旧版 sandbox 给 Feishu 群聊保留通用 `terminal`，再用命令字符串、脚本目录和下载目录 allowlist 约束用途。这个边界仍暴露 shell 解析面，无法从能力模型上禁止群成员创建脚本后执行，也无法限制被信任脚本及其子进程写入整个用户目录；`tmp` / `cache` 的用途和不同群之间的文件隔离也不明确。另一方面，群聊确实需要创建、追加、重建、删除和读取飞书文档，并需要一个可读写的临时数据区。主 Feishu DM 则必须继续获得默认完整工具面，危险命令走 owner 人工审批，不能被群聊策略误伤。

2026-08-16 全面审计又发现四个纵深缺口：① `clarify` 已在 `feishu_group` toolset 中却不在 hook allowlist，真实调用被误拦；② group hook 先检查 outsider-DM 基础 allowlist，导致群聊理论上可继承 `vision_analyze` / `image_generate`，与入站多模态链路分工不符；③ `feishu_doc_read` / `read_url` / `download_file` 可消费任意格式正确的 token/URL，文档 delete 没有可信 user 约束，形成 bot 凭据 confused-deputy 风险；④ `web_extract` 长页把全文写到全局 `cache/web` 后提示 `read_file` 分页，但群文件根正确阻断该路径，造成“短页可用、长页中段不可达”。

**修复**：从 `platform_toolsets.feishu_group` 删除 `terminal`，新增用户插件 toolset `sandbox_group`，仅暴露两个结构化入口：`group_cache` 在 `~/.hermes/tmp/group-workspaces/<chat-id-hash>/` 内执行文本文件 CRUD；`feishu_doc_manage` 将 `create/append/rebuild/delete/read_url/download_file/insert_image/set_cover` 八个 action 映射到管理员预装的固定脚本文件。模型不能提交 shell、脚本路径或原始 argv，工作区文件永远只作数据。工作区路径按群哈希隔离且校验相对路径、realpath 和 symlink containment；根目录权限为 `0700`；工具响应只返回相对路径和 `workspace_id`，不向群聊暴露宿主绝对路径。`tool_search` / `tool_describe` 作为只读工具目录桥在群聊显式放行，使 deferred 的 `group_cache` / `feishu_doc_manage` 能被发现和描述；`tool_call` 在 agent 执行器中先按当前 `feishu_group` toolset 解包为底层工具，再由 sandbox hook 看到真实工具名。脚本以 argv + `shell=False` 执行，macOS `sandbox-exec` profile 由插件生成并由整个子进程树继承：允许读取/执行/联网，但只允许写当前群工作区；OS 进程沙箱不可用或配置加载失败时 fail closed。群聊下载限制为单文件 50 MB，`TMPDIR` 和原子更新备份都重定向到当前群工作区；stdout/stderr 回传前统一脱敏 Bearer token、Feishu app secret 与 tenant token，上传失败也切断会暴露 curl Authorization argv 的异常链。wiki 仅可直接读取 `~/.hermes/wiki`；`skills` / `my-skills` 只能经 `skills_readonly` 查看 allowlist 中的 `llm-wiki` 与 `feishu-docs`，不能直接写。`known_plugin_toolsets` 把 `sandbox_group` 标记为已知但只在 `feishu_group` 显式启用；普通 `feishu` 不配置平台覆盖，owner chat 又在 `pre_tool_call` 最前面无条件放行，因此主私聊保留 terminal、文件读写、代码执行、skill 管理、浏览器和 cron 等完整默认工具面。`tmp` 不整目录删除，因为 `scripts/nightly_greeting.py` 仍使用 `tmp/nightly_report`；群聊统一使用上述 tmp 子树，不改用 cache。

**2026-08-18 owner DM HyperTeX 收紧；2026-08-19 群聊内测开放（历史阶段，现行工具面和路由契约见 2026-08-28 条目）**：owner DM 的 `hypertex_create_case` / `hypertex_iterate_case` 固定 `hermes` Contributor、new case 的 `deck` 类型与当前 Feishu turn 附件；`agent` 不再由 Hermes 强制注入——create 省略后按 `hermes` 账号 Agentic 权重抽取，iterate 省略后沿用 case 已记录的 Agent，模型即使显式传入也会被 sandbox 删除。HyperTeX 原始工具面为 list/create/iterate/get_case，状态控制使用 MCP Tasks 协商生成的 `tasks_get/update/cancel`；每个入站 turn 最多一次 HyperTeX 调用。2026-08-19 将 `hypertex` MCP toolset 显式加入 `feishu_group` 供内测，但 hook 对全部 7 个工具再要求当前 `chat_id` 命中 `trusted_feishu_chat_ids_for_group_hypertex`、当前 `user_id` 命中 `trusted_feishu_user_ids_for_group_hypertex`，并复用同一 contributor/type、附件暂存和单调用边界；未开通群或未授权成员均 fail closed，避免读取或修改共享 `hermes` case。首批开通财务专享 AI 小助手、Data Pipeline Workshop、AI 解放生产力三个群。同日按用户明确授权，群文档 delete 与 HyperTeX 两套授信从仅周琛扩为周琛、孙可天、张文华、李冰洁四人；每人同时登记 Feishu `open_id` 与短 `user_id`。这套执行授信与 `feishu.assistant_user_ids` 解耦，后者仍只含周琛两种 ID，避免“新增 MCP/delete 维护者”意外扩大群聊 @人触发 Hermes 的 admission 面。

08-19 按用户明确边界将群文档动作拆开：create、append、rebuild 对群成员开放；append/rebuild 仍要求目标文档在当前消息或显式引用中出现；delete 同时要求目标引用和当前 `user_id` 位于 `trusted_feishu_user_ids_for_group_mutations`。群聊仍先应用独立 allowlist（明确包含 `clarify` / web / 只读知识 / 结构化工具），不继承 outsider-DM 的 vision/image 工具；图片、音频、视频和扫描 PDF 统一由 Gateway 入站 native/sidecar 处理。`pre_gateway_dispatch` 仅从当前 `event.text` 与显式 `reply_to_text` 收集飞书 URL/token，历史 `channel_context` 不授予权限；群文档读取/下载也必须命中该 provenance。相同判定在 hook 与 `feishu_doc_manage` handler 双层执行。`search_files` 缺省 `path="."` 安全重写为 wiki 根。`post_tool_call` 只解析本群 `web_extract` 的结构化结果，将本轮精确 `cache/web/<file>` 临时授权给该群，最多 5 个、新消息立即撤销、其他 cache/群均不可读。

**2026-08-20 Markdown 引用 provenance 修复**：Data Pipeline Workshop 真机复现可信维护者 `user_id=5397e1a2` 回复一条由 Hermes 发出的文档链接并要求删除；adapter/Gateway 的 `reply_to_text` 合法地将链接表示成 `[URL](URL)`，旧 sandbox 裸 URL 正则却跨过 Markdown `](`，把两段链接拼成无效 `URL](URL`，因此 doc token 未进入当前 turn 授权集。修复让 URL 扫描在 `]` 前终止并继续由 canonicalizer 去掉尾随 `)`，同一 Markdown link 的 label/target 都能独立产出 URL + token；裸 URL 行为不变。trust failure 与 target-not-referenced failure 改为独立配置文案，并记录 `untrusted_actor` / `target_not_referenced` reason，避免模型再把 provenance 故障误报为“用户不可信”。该修复不放宽授权来源：仍只读取当前 `text` / 显式 `reply_to_text`，`channel_context` 和历史链接继续无权。

`read_url` 依赖链另有一处解释器耦合：`read_feishu_url.py` 只借用 `read_docx_to_markdown.py` 的纯渲染函数 `parse_blocks`，但后者在模块顶层 `import requests`，因此任何缺 `requests` 的解释器执行该链都会整条失败（现场表现为 `ModuleNotFoundError: No module named 'requests'`，可追至 2026-05-18，与 v0.19.0 升级无关）。根因是 `SKILL.md` 长期把 `uv run --with requests python` 作为这些脚本的规范调用方式：`~/.hermes` 下没有 `pyproject.toml` / `.venv` / `.python-version`，`uv run python` 会自行拉起一个与 hermes venv 无关的临时解释器（实测 uv 0.11.32 选到 CPython 3.13.14），其中并无 `requests`，只有 `--with requests` 才被临时注入；venv 解释器本身是 3.12.13 且 `requests==2.33.0` 为 pin 死的直接依赖。因此凡是漏掉 `--with requests`（如原 `SKILL.md:188` 的裸 `python ... append_md_to_doc.py`），或该链上任何模块在顶层 import requests 时，都会退化成 `ModuleNotFoundError`。`__pycache__` 中并存 `cpython-313` / `cpython-314` 字节码正是这些非 venv 解释器执行过的物证。配套修正 `SKILL.md`：`188` 行改为 venv 绝对路径，`232` 行依赖说明改为「首选 `~/.hermes/hermes-agent/venv/bin/python`（已 pin `requests`，无需 `--with`）」并写明裸 `uv run python` 为何不可用。修复把 `import requests` 下移进 `get_tenant_access_token()` 与 `download_doc_to_md()` 两个真正联网的函数，使纯渲染路径回到 stdlib-only；同时 `_handle_feishu_doc_manage` 的 start/end 日志补记 `python=<解释器路径>`，让后续同类故障可从 `agent.log` 直接判定实际解释器。

**2026-08-20 HyperTeX 附件名 CJK 折叠修复**：财务专享 AI 小助手把《销售财务思维培训 20260821.pdf》作为 iterate 素材上传，投递链路本身完整——sandbox 暂存、`asset_paths` 注入、case `assets/` 落盘、18 页 PDF digest 与 `asset_manifest.json` 的 `ai_read_order` 均正确，RuntimeAgent 也确实读了 digest 与 18 张页图。缺陷在命名层：`_hypertex_asset_name()` 把整个文件名一次性折叠成 ASCII 再 `.strip(" ._")`，中文字符先变下划线、随后连同分隔点一起被剥掉，该附件落盘为 `20260821.pdf`，而 prompt 引用的是原名，素材已无法从文件名追溯到来源。更严重的是纯中文名会连扩展名一起丢失（`销售培训.pdf` → `pdf`、`财务.xlsx` → `xlsx`），而 HyperTeX `asset_processor` 按 `Path.suffix` 判定素材类型，此类附件会静默降级为无类型文件：拷进 case 但永不生成 digest，且不报错、不进 `errors`，从群聊侧完全不可见。修复改为 stem 与扩展名分开清洗——扩展名只保留 `[A-Za-z0-9.]` 且不再被 strip 吃掉，stem 白名单放宽到 `\w` 以保留 CJK 字形，先截断再 strip，空 stem 回退 `attachment`，并统一 NFC 归一化以对齐 APFS 的规范化保留语义。放行非 ASCII 字母不越界：HyperTeX 侧 `fsutils.processed_key_for_source()` / `safe_processed_segment()` 对自己派生的 `_processed` / `_pdf` 路径独立折叠，`assets/_generated/` 早已在写中文目录名。防护面不变，均有反例回归：路径穿越（`a/../../etc/passwd` → `passwd`）、bidi override（`‮cod.exe` → `cod.exe`，Cf 类不属于 `\w`）、全标点名（`...` → `attachment`），`_path_within` 与 50 MB / 6 附件上限兜底不变。

**2026-08-20 HyperTeX 授信扩张：沈舒仪 + SpaceSight Tech Sharing Group**：按用户明确授权，群 allowlist 增开 `oc_1d81b1992a1cf99620bf815945782f27`（SpaceSight Tech Sharing Group，由沈舒仪创建），用户 allowlist 增加沈舒仪。本次首次出现**两套授信不再等值**：此前 `trusted_feishu_user_ids_for_group_hypertex` 与 delete-only 的 `trusted_feishu_user_ids_for_group_mutations` 成员完全相同，verifier 也图省事把两者断言成同一个 `expected_trusted_users`；用户只授权 MCP、未授权文档删除，因此 HyperTeX 集现为 mutations 集的真超集。verifier 相应拆成 `expected_hypertex_users`，并新增一条**反向断言**证明沈舒仪不在 mutations 集内——避免今后"加 MCP 维护者"被同一个共享集合悄悄顺带授予删除权。`feishu.assistant_user_ids` 保持只含周琛两种 ID 不变，新增授信不扩大群聊 @人 admission 面。**同轮按用户指示把文档删除授信收回到仅 owner**：`trusted_feishu_user_ids_for_group_mutations` 从周琛、孙可天、张文华、李冰洁四人收窄为**仅周琛**。理由是删除对群侧不可逆，不随 HyperTeX 授信一起扩张。至此两套授信不再有共享期望集：verifier 改为分别用 `expected_mutation_users`（1 人）与 `expected_hypertex_users`（5 人）两个**独立字面量**断言，并新增 `mutation_users < hypertex_users` 严格子集断言与"仅 owner 持有删除权"断言，取代原先 `expected_trusted_users | {…}` 的超集算术——后者会让任一集合的改动悄悄传染另一集合。收窄方向 fail-closed，只减少命中。

**2026-08-20 中间态误判（已撤销）**：曾因 `agent.log` 的发送者字段始终显示 `ou_…`，把该展示值误当成沙箱实际使用的主身份，于是将授信配置收敛为单一 open_id，并错误判断 tenant `user_id` 从未到达。这个中间态只维持到同日下午的 Data Pipeline Workshop 真实复现；它不再是现行规则，也不得作为后续删减身份字段的依据。

**2026-08-20 Data Pipeline Workshop 现场纠正：授信必须归一 Feishu 的多种精确身份**：此前把 `logs/agent.log` 的 `sender=user:ou_…` 当成沙箱实际使用 open_id 的证据，但 adapter 的两条优先级恰好相反——日志展示 `open_id or user_id`，`SessionSource.user_id` 则取 `user_id or open_id`。真实事件同时携带 `open_id=ou_33ee…` 与 tenant `user_id=5397e1a2`；15:16 从授信配置移除短 ID 后，新会话在 16:08–16:17 连续 8 次调用 `list/iterate/get_case` 均于 0.00 秒被本地 hook 误拒，MCP 服务端没有收到请求。修复不把双份 ID 重新塞回 allowlist：`pre_gateway_dispatch` 从原始、已签名 Feishu `sender_id` 收集 `open_id/user_id/union_id`，文档删除与 HyperTeX 对该集合和单一 open_id allowlist 做精确交集，不使用可改名的 display name；拒绝日志附 `actor_ids`。`scripts/pull_feishu_people.py` 同时把 tenant `user_id` 作为 Feishu 权威字段写入 `people.yaml`，真实拉取 218/218 人完整且唯一，缺失或重复会在写 draft 前整轮失败。回归使用真实 `raw_message.event.sender.sender_id` 形状，并同时覆盖 HyperTeX 与 delete 授权，避免以后再被展示日志误导。

**2026-08-22 HyperTeX case-type discovery 纳入同级可信边界**：用户在 MCP `include` 中启用 `hypertex_list_case_types` 后，真实群聊模型 schema 会立即发现该工具；仅依赖 `pre_tool_call` 拒绝会制造“看得见但必失败”的工具，并让 verifier 的 YAML 精确契约非零。该调用虽不带参数且只读取 case type，但返回 owner 的 active freestyle engines，不能降级为普通群工具。修复把它加入 `_HYPERTEX_TOOLS` 与插件精确 allowlist，使其和既有 list/create/iterate/get/task 工具共用“开通群 + 可信 actor + 每轮一次”门禁；owner/private 保持空参数原样传递。新增 owner 正例和群聊非可信反例，verifier 同时断言根 MCP include、群 toolset 与 hook allowlist 三层一致，避免以后只改 `config.yaml` 造成 schema/权限漂移。

**2026-08-28 HyperTeX 公共面与服务端路由契约收口**：现行 Hermes 仅开放 `hypertex_create_case`、`hypertex_iterate_case` 与只读 `tasks_get` 三个入口；list/get_case/case-type discovery、task update/cancel 等历史入口不再属于调用侧工作流。执行器身份、模型/provider、会话、权重、粘性选择、路由决策与诊断元数据均为 HyperTeX WebApp/worker 私有信息，MCP 响应不提供这些信息属于正常契约。sandbox 对旧客户端或模型幻觉产生的 `agent` / `agent_key` / `agent_name` / `model` / `provider` / `executor` / `execution_backend` / `routing` 做防御性删除，只固定 `hermes` Contributor、new case 的 `freestyle` 类型与本轮安全暂存附件；Gateway 注册日志使用 `hypertex_routing_policy=server-owned/non-observable`。skill、README、升级手册和 verifier 必须保持同一口径，不能从历史说明恢复调用侧路由猜测。

**2026-08-29 飞书文档图片与封面写入契约**：`group_image_generate` 与 `group_chart_generate` 的相对 `workspace_path` 可直接作为 `feishu_doc_manage` 的受控图片来源；当前消息或显式回复中的图片则只能按 image-only `attachment_index` 选择。两者互斥，禁止任意绝对路径、旧历史附件或 URL 进入群文档写入面。`insert_image` 采用“创建空 Image Block → `docx_image` 素材上传 → `replace_image` → 版本表”并支持 top-level index、唯一文本锚点、对齐、caption 与尺寸；`set_cover` 采用“以 document ID 为上传点并携带 `drive_route_token` → PATCH `update_cover` → 版本表”，支持裁切偏移。文件再次校验普通文件、symlink、magic 与 20 MiB 上限；失败时正文路径删除本次图片块，封面路径恢复旧 cover，并尽力恢复修改前版本表。Agent/CLI 升级契约不依赖外部 `lark-cli`：Step 8e verifier 精确检查八 action、schema、脚本存在性、飞书 endpoint/payload 哨兵、离线 API 行为测试及当前 Gateway 注册日志中的 `doc_media_actions`/上限，任何一层漂移都使升级非零。

**2026-08-29 真实图文文档回归修正**：主会话生成的 16:9 封面源图为 `2048×1152`，正文插入仅指定 `width=900` 后，Feishu 图片块却保留 `height=1152`，形成 `900×1152` 的竖向容器和大面积上下留白。`manage_doc_image.py` 现在用 core Pillow 读取源像素；仅提供一个显示维度时自动按原比例补齐另一个维度（该现场变为 `900×506`），两个维度都显式提供时仍尊重调用者。同期图表现场暴露两处契约漂移：schema 合法的 `palette_preset=blue` 被错误小写为 Matplotlib 不识别的 `blues`，以及缺省 legend 固定放顶部导致宽图主绘图区从约半高处才开始。renderer 现将 `blues/greens` 映射回大小写敏感色图名；`legend_position=auto` 先使用 Matplotlib 自身的 `best` 候选与 artist 几何在绘图区内寻找不遮挡数据的位置；只有检测到柱、线、散点或标注相交时才外置——横向画布固定右侧、纵向画布固定底部，外置 legend 的对应宽/高占比不得超过绘图区的 `0.20`；长 legend 通过重建紧凑 handle/padding、换行、缩小字号和最终省略来满足预算，不因排版约束让整张图失败。内部字段标题 `series` 被移除；显式 right/bottom/best 保持调用者选择，历史 top 的现行兼容规则见下方 2026-08-30 修正。renderer 回执增加最终 `legend_position` 与 `legend_extent_fraction`，便于 Agent 和回归验证真实布局而非只看输入参数。同期修复 stdin 单次 `os.read` 可能只读到 16 KiB 分片的问题：入口现在循环读取至 EOF 并维持 512 KiB 总上限，复杂 records 请求不再随机报半截 JSON。最终 `tight_layout` 后还会按实际字体像素测量坐标轴 tick-label 带宽：Y 轴不超过绘图区宽度 10%，X 轴不超过绘图区高度 10%；X 标签先尝试 30° 倾斜，仍超限时与长 Y 标签一样使用省略号，回执通过 `axis_label_layout` 给出旋转、截断数量和最终占比。

**2026-08-30 legend、新建文档媒体与版本 turn 闭环**：真实主会话再次由模型主动传入 `legend_position=top`，绕过 auto 的图内/右侧/底部策略；现从工具 schema 移除 `top`，renderer 对历史 `top` 输入 fail-safe 归一为 `auto`，因此宽图只能图内或右置、竖图只能图内或下置。Data Pipeline Workshop 同轮 `create` 成功后，紧接的 `set_cover` 因新 token 不在入站消息 provenance 中被 `target_not_referenced` 拦截；首轮虽在日志记录 grant，却只写入 create worker 的 ContextVar，下一工具 worker 看不到，暴露出同线程测试假绿。现由 `post_tool_call` 仅解析固定 `feishu_doc_manage(create)` 的 `success=true`、`returncode=0` 结果，将精确 docx token 存入 `(chat_id, agent turn_id)` 线程安全短期 capability；pre hook 把同一 turn ID 作为隐藏参数送入 handler，下一 turn、失败创建、其他工具/文档均不授权。主会话文本 batch 又会丢失平台 message ID，使版本 ledger 没有键；owner terminal 现在仅对固定飞书文档脚本注入 hook 自带的内部 agent turn ID，群固定脚本复用同一 ID，因此一个 turn 内 rebuild/cover/多次 insert 最多新增一行。同期 value label 在显式 `y_max=5` 后越过 axes 的现场改为最终 `tight_layout` 后按实际像素检测 bar/waterfall/lollipop 标注，只扩展对应数值轴直至全部回到绘图区，回执增加 `value_label_layout`。

**2026-09-01 图表信息密度、网格与完整标签修复**：主会话连续两张客流折线图暴露了同一布局问题：29 个日期在旧 10% X tick-label 预算下全部变成 `08-…`，而显式右置 legend 一方面已被 `tight_layout` 计入 artist bounds，另一方面 `_legend_layout_rect()` 又固定把右边界压到 `0.82`，形成重复预留；suptitle 同样既保留显式顶部 rect、又继续参与 tight-layout 计算。备注区域还固定从 `0.11` 起步，最终使主绘图区仅约占画布宽度 63%、高度 51%。现将 X/Y tick-label 预算统一提高到 20%，完全取消 tick 文本省略：X 轴在 0°/30°/45° 中选择保留完整标签最多的方案，再按步长降低密度并保留首尾及高亮项；Y 轴先按真实像素宽度完整换行，发生纵向重叠时再降低密度。外置 legend 不再叠加固定 18%/20% gutter，suptitle/副标题/备注退出自动 layout 后只由紧凑 rect 各预留一次，`tight_layout` padding 从默认 1.08 收紧到 0.55。笛卡尔图所有 visual preset 默认同时启用 X/Y major grid，并通过 rcParams 与最终 `tick_params` 双层显式开启底部 X / 左侧 Y major ticks，避免 Seaborn style 将已配置尺寸的 tick line 隐藏；pie/donut 继续关闭网格。新增与现场一致的 29 日期布局回归，以及 hidalgo/presentation/minimal/statistical 四种模板的双轴网格与 tick 可见性回归。

**2026-08-30 远程 sourced 图片导入闭环**：Data Pipeline Workshop 新文档 `QNmtdx2xqoBkrWxf2KmcC8mjnJf` 把两个 xAI CDN URL 直接写进 Markdown；飞书 import task 整体返回成功，却把 hero 与 Search Arena 都替换为同一张 `1460×220`、SHA-256 `c1263e…` 的“无法导入该图片”占位 PNG。后续 AI 封面和 6 张图表经 `docx_image` 本地上传均正常，证明缺陷只在远程 Markdown 图片代抓链；旧 `read_url` 又完全忽略 image block，导致视觉验证假绿，最终回复还过度声称插入了实际并不存在于 Markdown 的 Text Arena。现新增固定 `stage_remote_images.py` 与 `stage_image_urls`：每次最多 8 个公共 HTTPS URL，拒绝 credential/query secret，初始及每次 redirect 均走 Hermes SSRF/连接期 IP 策略（云 metadata 永久拒绝，private URL 行为服从 operator 的统一安全配置），限制单图 20 MiB/单次 50 MB，校验 raster magic、Pillow 可解码性与尺寸后才原子写入当前群 workspace。create/append/rebuild 对 Markdown/HTML image syntax fail closed，要求先 staging、创建后再 `insert_image`；`replace_image` 可在验证目标为当前文档 top-level image block 后原位修复并保留同 turn 单版本与失败回滚。`read_url` 对已知飞书错误占位图下载取证并输出 `[IMAGE_IMPORT_ERRORS]` + block IDs，禁止再将文本回读当作视觉通过。现场两个 block 已原位替换为真实 `1200×675` 与 `1200×612` 图片，回读错误计数归零，版本仅由 `.01ed` 增至 `.02ed`。

**2026-08-30 飞书文档素材到 HyperTeX 的安全桥接闭环**：Data Pipeline Workshop task `59` 的模型调用明确提交 1 张 AI 封面、4 张图表和 3 张 sourced 图片，但旧 `_prepare_hypertex_call()` 无条件用“当前入站消息附件”覆盖调用方 `asset_paths`；该消息 `media=0`，HyperTeX 数据库最终记录 `asset_paths=[]`，job 日志显示 `Staged 0 MCP assets for preprocessing`。同时 `read_url` 的 Markdown 渲染忽略普通 image block，只下载特殊尺寸图片用于错误占位识别，导致从任意既有飞书文档生成 deck 时也没有可复用图片路径。修复把可信群的素材来源扩展为“当前消息附件 + 当前群隔离工作区内显式路径”：绝对或相对路径都必须 realpath 落在本群 workspace，symlink、缺失文件、跨群/任意宿主路径全部拒绝，之后仍复制到 HyperTeX 私有 staging，不把原路径直接交给服务；单轮素材上限从 6 调整为 12，以覆盖常见的封面 + 四图表 + 三场景图组合。`feishu_doc_manage(action="read_url", include_images=true)` 新增受限图片导出：最多按同一上限下载 docx/wiki 的封面与内嵌 raster，校验 magic、单图 20 MiB 和总量 50 MB，已知错误占位与失败块只进入 `errors`，成功项写入本群 `feishu-doc-images/<doc-token>/` 并在 `[DOCUMENT_IMAGES]` JSON 中返回相对 `image_path`；封面标记为 `role="cover"` 且排在正文图片之前，可直接交给 HyperTeX bridge。默认文本读取保持不下载图片，避免无关读取扩大耗时与落盘。

**2026-08-31 素材容量边界扩展**：按 operator 明确要求，把可信群 HyperTeX 单轮素材上限从 12 提高到 20、单素材上限从 50 MB 提高到 100 MB，并把显式飞书 `/file/` 下载上限同步到 100 MB，避免文件已获授权却在落入群工作区前被旧下载门槛拒绝。数量限制仍对“当前消息附件 + 当前群工作区显式文件”的合并集合生效，21 个素材 fail closed；每个文件仍需通过 realpath、普通文件、symlink、存在性和私有 staging 校验。该扩容不改变飞书文档图片上传、远程 sourced 图片 staging、图片生成输入等独立媒体边界，它们继续保持 20 MiB 单图限制；docx/wiki 图片导出的数量随 HyperTeX 上限提高到 20，总下载预算随群文件预算提高到 100 MB。

**2026-09-02 peer-machine 自演进**：旧 verifier 把来源机器的 owner、HyperTeX 用户与群 ID 写成重复常量，导致迁往独立身份/群边界的 peer 时只能改校验器才能通过；旧迁移文档又建议整目录覆盖，和目标机状态保留冲突。现改为从 `people.yaml` 首位与 `feishu.assistant_user_ids` 精确闭合 owner、从 `groups.yaml` / `people.yaml` 验证 trust-list 引用合法性，并按根配置决定 HyperTeX 是否存在；具体授权意图仍只由 plugin config 的显式列表声明，verifier 不从 roster 自动授予权限。未部署 HyperTeX 的机器必须完整删除 server/toolset/tools/trust 四个暴露面。tracked MCP sensitive headers 只能使用环境变量引用，防止迁移或提交时复制 literal credential。

**验证**：工具搜索按上游新契约一项能力一条查询，并校验对应 JSON `results[].matches`，不再把跨能力混合 query 的空结果误报为权限丢失。`plugins/sandbox/verify.sh` 作为 `hermes-update.sh` Step 8e 的硬门槛，并由 `scripts/test_patch_evidence.py::audit_sandbox_verifier` 在 full 逐 PATCH 轮询中实际执行、记录本轮 pytest count：Step 8e verifier 数组与 external evidence registry 必须机器精确相等；行为套件启用 `xfail_strict=true`、写入隔离 JUnit，只有全部 case clean passed 且 skip/failure/error 均为 0 才输出唯一 `PATCH_VERIFY_RESULT` 回执。其余结构化验证继续解析根/插件 YAML、groups.yaml 与 people.yaml 的 open_id↔user_id 完整唯一映射/0600 权限，确认群策略保持 `open + require_mention`、审批为 `manual`、launchd 未启用 YOLO、owner Feishu 无 `platform_toolsets.feishu` 收窄、群聊 toolset、唯一 owner 删除授权、固定脚本及原始工具集合均精确；所有 MCP sensitive headers 必须使用 env ref。HyperTeX MCP 启用时继续验证 server/toolset/群工具存在、双 trust list 非空且只引用当前 roster/groups，未配置时则要求前三个运行时暴露面全部缺席且 trust lists 为空；trust-list 是否应扩大仍由配置 diff 人工审批。真实解析 owner/group toolset，断言群聊不含 vision/image/terminal/write surface，并用当前批量 schema `tool_search(queries=[...])` / `tool_describe(names=[...])` 证明结构化工具仍可发现和描述（2026-08-26 上游从单数参数迁移后同步）。除 search/describe 外，verifier 穿过真实 `handle_function_call("tool_call" → underlying)`，并让 create 与 set_cover 分别运行在两个独立 `copy_context()` 中，证明 bridge scope、底层 hook、跨 worker turn capability 和 handler 全部执行；下一 turn 精确反例必须重新拒绝。owner 路径通过真实 hook dispatcher 断言固定飞书 terminal 命令收到内部 agent turn ID；`feishu_common` 再证明同 ID 多次修改只写一行。HyperTeX 启用时，素材回归还必须证明当前群 workspace 的相对/绝对文件可私有暂存、8 个素材不会被旧 6 项上限截断、任意 workspace 外路径与 symlink 均 fail closed；飞书读取回归证明 `include_images` 固定 argv、raster magic、错误占位排除和相对路径 manifest。远程图片回归覆盖 staging 相对路径、batch 原子失败、HTTPS/credential 拒绝、Markdown image 硬拦、existing-block replace、错误占位 hash 识别与真实 xAI 下载/现场替换。图表回归复用现场 `y_max=5` 请求，要求 `value_label_layout.outside_before=1` 且 `outside_after=0`，同时继续覆盖历史 `top` 归一、横图右置/竖图下置与 0.20 外置上限。runtime trace 必须同时匹配当前真实 Gateway child PID 与 `plugin.yaml` 版本及四个 `doc_media_actions`；仅有同 PID 的旧格式注册行或当前文件通过单测都不能证明新插件已加载。回执搜索覆盖 `agent.log` 及轮转文件，按时间选择当前 PID 最新注册；仅当 HyperTeX 启用时才要求同 PID、同启动窗口内的 MCP Tasks 回执。其余媒体 API、身份同步、路径/附件/沙箱边界继续按既有契约执行，任一失败设置升级 `FINAL_RC=1`。

**上游吸收判断**：如果上游原生提供按会话隔离的可写工作区、无 shell 的固定动作工具、子进程写范围沙箱、owner-DM/group 独立工具面、当前消息资源 provenance、安全的 deferred-tool bridge，以及等价的生成媒体/当前附件到飞书正文图片和封面的受控写入与失败补偿，可迁移到上游能力并归档本补丁；在此之前不得恢复群聊通用 terminal，也不得开放全局 cache、任意 bot 可读文档、任意宿主图片路径或无约束 URL 下载。

---

## Archive — PATCH-COMPACTION-LIFECYCLE-SILENCE（上游 v0.20.6）

### [PATCH-COMPACTION-LIFECYCLE-SILENCE] 自动 compaction 两端边界都不进聊天

| 字段         | 内容                                                                                                             |
| ------------ | ---------------------------------------------------------------------------------------------------------------- |
| **文件**     | 上游 `agent/conversation_compression.py`, `gateway/run.py`, `tests/gateway/test_compression_progress_notices.py` |
| **状态**     | ✅ 已上游合并（v0.20.6，commit `7a21bfe68a`）；本地源码 hunk 与重复回归已移除                                    |
| **适用版本** | `7a21bfe68a` 之前需要本地 patch；之后由上游 routine sample、chat-noise regex 与 progress gate 共同实现           |

**问题**：自动 compaction 生命周期有 start（`COMPACTION_STATUS`）与 done（`COMPACTION_DONE_STATUS`）两条状态边。旧 upstream 只把 start 登记为 routine status，导致 done 既逃过聊天噪声抑制，也不受 `compression.progress_notices` 开关控制；2026-08-12 曾把完成通知原样发进 Feishu 工作群。

**修复**：上游 commit `7a21bfe68a` 已把 `COMPACTION_DONE_STATUS` 加入 `ROUTINE_COMPRESSION_STATUS_SAMPLES`、`_TELEGRAM_NOISY_STATUS_RE` 和 `_COMPRESSION_PROGRESS_STATUS_RE`，并补充完成边的 opt-in 回归；覆盖范围与本地不变量等价且更集中。本地显式 regex hunk、模板元组 hunk 和两组重复测试已删除。

**验证**：`scripts/test_patch_evidence.py::audit_archived_compaction_lifecycle_silence` 每轮真实运行上游 `tests/gateway/test_telegram_noise_filter.py::test_all_routine_compression_statuses_suppressed_from_source_constants`、`tests/gateway/test_compression_progress_notices.py::test_compaction_completion_notice_respects_progress_notices_gate` 与 `test_progress_regex_covers_every_routine_sample`。`hermes-update.sh` Step 8b 另保留行为 sentinel，确认 start/done 在所有聊天面默认静默、done 受 opt-in 控制、失败类通知与 local/programmatic diagnostics 不被误吞。

**上游吸收判断**：已由 commit `7a21bfe68a` 完全吸收；若 routine sample、共享 chat-noise regex、progress gate 或对应行为回归任一退化，归档审计必须失败并重新评估是否恢复最小本地补丁。

---

## Archive — PATCH-LAUNCHD-WRAPPER-SUPERVISOR（上游 v0.20.4）

### [PATCH-LAUNCHD-WRAPPER-SUPERVISOR] launchd stderr wrapper 保留受监管身份

| 字段     | 内容                                                                                           |
| -------- | ---------------------------------------------------------------------------------------------- |
| **文件** | 上游 `hermes_cli/gateway.py`, `tests/hermes_cli/test_gateway_external_supervisor.py`           |
| **状态** | ✅ 已上游合并（v0.20.4，commit `7008fb81b3`）；本地源码 hunk 与旧 `test_gateway.py` 回归已移除 |

**问题**：launchd plist 用 `hermes_cli.stderr_timestamp` 包裹真实 Gateway 后，原生 `XPC_SERVICE_NAME` 无法可靠传到二级子进程；wrapped child 会把自己误判为 shell 副本并因多写者保护退出，导致 launchd 反复拉起失败。

**修复**：上游 `7008fb81b3` 已在生成的 launchd wrapped child argv 上显式追加 `--external-supervisor`，同时让 `stderr_timestamp` 升级旧 plist 的 Hermes Gateway argv；未受 launchd 监管的 detached fallback 仍保持无标记。本地 `_gateway_run_command()` 参数扩展和旧测试 hunk 因此删除，`hermes_cli/gateway.py` 与 `tests/hermes_cli/test_gateway.py` 退出 `PATCHED_FILES`。

**验证**：`scripts/test_patch_evidence.py::audit_archived_launchd_wrapper_supervisor` 每轮真实运行上游 `tests/hermes_cli/test_gateway_external_supervisor.py`，覆盖 generated launchd inner argv 交还外部 supervisor、旧 plist wrapper 升级，以及无标记 detached watcher 反例；`hermes-update.sh` Step 8b 另保留归档 sentinel，检查官方实现后才允许刷新 replay bundle。终态仍需真机证明 launchd definition current、supervisor PID 与真实 Gateway child PID 均健康。

**上游吸收判断**：已由 commit `7008fb81b3` 完全吸收。若官方实现或正反例回归被移除，归档 sentinel 必须阻断升级并重新评估是否恢复本地补丁。

---

## Archive — 本地模型链路收敛（2026-08-15）

### [PATCH-VERTEX-FALLBACK] 第二 Vertex 账号作为独立 fallback

| 字段     | 内容                                                                                                                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/vertex_adapter.py`, `hermes_cli/auth.py`, `hermes_cli/runtime_provider.py`, `agent/auxiliary_client.py`, `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🗄️ 已归档：当前只使用一个标准 Vertex 账号                                                                                                                                                                |

**问题**：2026-08-15 归档审计确认模型链路已改为 Azure GPT-5.5 → Bedrock Claude Opus 5 → 标准 `vertex/google/gemini-3.5-flash`，视频旁路与 compression 也复用同一标准 Vertex 凭据。第二账号不再提供独立能力，继续维护会扩大 provider/凭据/gate 面；因此归档后的当前不变量是 `vertex-fallback` provider、别名、第二 SA/project 解析、专用 gate 与 `.env` 变量保持退役，标准 Vertex 路由继续存在。

提出时的历史场景（主模型也是 Vertex 上的 `google/gemini-3.1-pro-preview`）：单账号/单 project 配额下频繁 `429 RESOURCE_EXHAUSTED`，回退到 Qwen 后行为与质量都跟主模型不一致。需求是用第二个 Vertex 账号运行同一模型，仅换账号绕开限额；当时 provider registry、fallback 去重和全局 project override 共同阻断了该表达。

**修复**：新增独立 provider `vertex-fallback`，复用同一 `VertexProfile`（自动继承 `PATCH-VERTEX-HIDDEN-THOUGHTS` 的单层抑制 → 行为一致），只换凭证：

1. `agent/vertex_adapter.py`：新增 `get_vertex_fallback_config()` / `has_vertex_fallback_credentials()`，从 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（经 `_get_secret`）解析第二账号；给 `get_vertex_credentials`/`get_vertex_config` 加 `project_override`（显式项目优先）与 `apply_global_project_override=False`（不套用 `VERTEX_PROJECT_ID`），确保第二账号 token 锁在自己的 project；token 按 path 各自缓存 + 自动刷新（复用 `_creds_cache`）。
2. `hermes_cli/auth.py`：在 `PROVIDER_REGISTRY` 显式登记 `vertex-fallback`（`auth_type="vertex"`，别名 `vertex2`/`vertex-secondary`），使 `resolve_provider_client` 能取到 pconfig 并命中 vertex 分支。
3. `agent/auxiliary_client.py`：`resolve_provider_client` 的 `auth_type=="vertex"` 分支内，按 **registry 条目的 canonical id**（`pconfig.id == "vertex-fallback"`，2026-08-07 修复——此前按原始 provider 串判定，`vertex2`/`vertex-secondary` 别名会静默铸出主账号凭据，恰是配额耗尽的那个账号）改用 `get_vertex_fallback_config` / `has_vertex_fallback_credentials`。
4. `plugins/model-providers/vertex/__init__.py`：用同一 `VertexProfile` 类再 `register_provider` 一个 `name="vertex-fallback"` 实例，使 `get_provider_profile("vertex-fallback")` 可解析（fallback 激活后 `_build_request_kwargs` 走 profile 路径拿到单层抑制）。
5. `hermes_cli/runtime_provider.py`（2026-07-29 补缺口）：网关 fallback 链（`gateway/run.py` `_try_resolve_fallback_provider`）解析条目走 `resolve_runtime_provider(requested=...)` 而**不是** `resolve_provider_client`；其 Vertex 分支只认主账号 5 个别名，`vertex-fallback` 静默落到 generic 尾部解析器，"成功"返回 `provider="openrouter"` + **空 api_key**——网关据此打出误导性的 `Fallback provider resolved: vertex-fallback` 日志并把坏 kwargs 交给 `AIAgent`；init 因空 key 走 router 路径，又因 `openrouter` 在豁免集合（`{auto, openrouter, custom}`）里跳过 explicit fail-fast 与 init-time fallback，最终抛 `No LLM provider configured`，用户在群聊/私聊看到 "Sorry, I encountered an unexpected error"；且链上后续条目（末位的 DashScope 档，NO_PROXY 直连、代理瞬断时本可救场）永远轮不到。修复：在主 vertex 分支之后新增 `("vertex-fallback", "vertex2", "vertex-secondary")` 分支，经 `get_vertex_fallback_config()` 铸 token 返回 `provider="vertex-fallback"`；凭据不可解析时抛类型化 `AuthError`，使 fallback 链前进到下一条目。触发场景：本机代理（127.0.0.1:7897）瞬断时 `oauth2.googleapis.com` token 刷新失败（"No route to host" / SSL EOF，见 `logs/agent.log*`），主 Vertex 解析抛 AuthError 进入 fallback 链。

归档前适用性（2026-08-11 历史）：当时 `vertex-fallback` 是链上唯一具备视频能力的档，现 `PATCH-MULTIMODAL-SIDECAR` 的前身 `PATCH-VIDEO-SIDECAR` 直接依赖它。2026-08-15 已改由标准 `vertex/google/gemini-3.5-flash` 承担同一职责，本段仅保留当时为何继续维护第二账号的背景。

归档前配套（历史）：`~/.hermes/.env` 曾使用 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID` 管理第二账号；这些键已于 2026-08-15 从 `.env` 删除。

**验证**：`scripts/test_patch_evidence.py::audit_archived_vertex_fallback` 不绑定当前生产 provider/model：它以 names-only 方式读取 `.env` / `.env.example` 键名，不加载或输出 secret 值，并对历史涉及的五个源码入口、当前配置和 replay bundle 做负向审计；随后穿过真实 provider registry/profile resolver，断言 `vertex-fallback`、`vertex2`、`vertex-secondary` 与第二账号凭据键都未被静默复活。用户以后把主模型或 fallback 换成其他合法 provider 不会误触发本归档审计。历史实现与 2026-08-07 的通过数字只作背景，不再冒充当前回归证据。

**上游吸收判断**：本补丁是因需求退场而归档，并非被上游完全吸收。只有未来再次需要同 provider 的 per-project 配额隔离时才重新评估：优先使用上游 credential pool；仅当它仍无法表达 per-entry service-account 文件与独立 project，且真实需求重新出现时，才恢复新的最小补丁与回归，不能直接复活历史 hunk。

---

### [PATCH-GEMINI-CUSTOM-NATIVE-BASE] 自定义 Gemini gateway 保持原生 wire

| 字段     | 内容                                                                                                                                                                                                                                                                                                                            |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/gemini_native_adapter.py`, `agent/agent_runtime_helpers.py`, `agent/chat_completion_helpers.py`, `agent/auxiliary_client.py`, `agent/transports/chat_completions.py`, `hermes_cli/doctor.py`, `tests/agent/test_gemini_native_adapter.py`, `tests/hermes_cli/test_gemini_provider.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🗄️ 已归档：自动链路与 compression 均已迁移到标准 Vertex                                                                                                                                                                                                                                                                         |

**问题**：2026-08-15 归档审计确认私有 native gateway 的短请求与 compression 可用，但 110k 级完整 Hermes `systemInstruction` 稳定读超时；把同内容折叠到 user 会降低系统指令优先级，不能作为安全修复。当前链路已用标准 Vertex Gemini 3.5 Flash 替代，因此归档后的当前不变量是 private-base helper、completed-stream fallback、doctor probe、专用 gate 与 `GEMINI_*` 配置保持退役，同时标准 Gemini native client 仍有真实回归。

历史问题：Hermes 文档把 `GEMINI_BASE_URL` 定义为 Gemini API 的 base URL override，但运行时曾只按官方域名选择 `GeminiNativeClient`，使私有原生 `generateContent` gateway 被误判为 OpenAI-compatible `/chat/completions` endpoint。

**修复**：新增 provider-aware `is_native_gemini_provider_base_url()`：当 canonical provider 是 `gemini` 时，任意合法自定义 host 默认沿用原生 Gemini wire；只有 base URL 显式以 `/openai` 结尾才选择兼容面。hostname-strict 的 `is_native_gemini_base_url()` 保持不变，避免把其他 custom provider 误判为 Gemini。主 agent client factory、stream options、auxiliary client/pool 和 transport extra-body 过滤统一接入 provider-aware 判定；`GeminiNativeClient` 继续使用 `x-goog-api-key` 与 `models/{model}:generateContent`。私有 gateway 若未实现 `streamGenerateContent?alt=sse`，client 在收到 `stream=True` 时直接返回一次非流式 `generateContent` 的完整 response；Relay 的既有 completed-response 分支会交付该结果并把当前 session 后续调用切成非流式，不引入 heartbeat 私有协议，也不会掩盖 DNS/连接异常。Google 官方 host 保留真 SSE，显式 `/openai` 用户保持兼容路径。Doctor 不再对私有 native gateway 做 Bearer-auth `/models` 探测，而是选取当前 compression/fallback/main 配置中的 Gemini 模型，用 `GeminiNativeClient` 做最小 `generateContent` 健康检查。

**验证**：`scripts/test_patch_evidence.py::audit_archived_gemini_custom_native_base` 以 names-only 方式检查 `config.yaml`、`.env` / `.env.example`、源码与 bundle 未恢复 `GEMINI_BASE_URL` / `GOOGLE_GEMINI_BASE_URL` 私有链路或 `is_native_gemini_provider_base_url` helper，不读取 secret 值；同时真实运行 `test_native_client_uses_x_goog_api_key_and_native_models_endpoint` 与 `test_gemini_resolve_provider_client_uses_native_client`，证明通用标准 Gemini native wire 仍健康。历史私有 gateway 结果仅作归档背景。

**上游吸收判断**：本补丁因私有 gateway 退场而归档，并非上游完整吸收。只有再次启用私有 Gemini gateway，且其完整 `systemInstruction`、工具 schema、streaming 与 `/openai` opt-in 均通过真实回归时才重新评估；不能仅凭短请求成功恢复旧 helper。

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

**验证**：`scripts/test_patch_evidence.py::audit_archived_lazy_activation` 每轮真实运行上游 `tests/tools/test_lazy_deps.py::TestActiveFeatures::test_shared_dependency_does_not_activate_feature`，覆盖仅共享依赖存在时 Matrix 不 active；`hermes-update.sh` Step 8b 另保留“首项依赖探测 + 上游回归测试”sentinel，并继续纳入 8c 总闸门。

**上游吸收判断**：已由 commit `2a55f3348` 完全吸收；若上游未来移除首项身份锚点或对应回归测试，Step 8b 必须阻断 bundle 刷新并重新评估补丁。

---

## Archive — PATCH-DOCTOR-ENABLED-TOOLSETS（上游 v0.18.0）

### [PATCH-DOCTOR-ENABLED-TOOLSETS] Doctor 只统计已启用工具集

| 字段         | 内容                                               |
| ------------ | -------------------------------------------------- |
| **文件**     | `hermes_cli/doctor.py`                             |
| **状态**     | ✅ 已上游合并（v0.18.0，commit `6b21a935a`）       |
| **适用版本** | v0.9.0–v0.17.0 需要本地 patch；v0.18.0+ 已上游修复 |

**问题**：`hermes doctor` 曾把所有注册但缺 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中用 `_get_platform_tools` 过滤出用户实际启用的 toolset，只对它们报 issue。

上游追踪：commit `6b21a935a`（`fix(doctor): ignore disabled toolsets in missing-API-key summary`）合入等价逻辑，本地 `hermes_cli/doctor.py` 已从 `PATCHED_FILES` 移除。

**验证**：`scripts/test_patch_evidence.py::audit_archived_doctor_enabled_toolsets` 每轮真实运行 `tests/hermes_cli/test_doctor.py::TestDoctorToolAvailabilitySummary::test_missing_api_key_summary_ignores_disabled_toolsets`；本地 Step 8b sentinel 同时检查 `_get_platform_tools` 仍存在，任一回归都会阻断收敛。

**上游吸收判断**：已由 commit `6b21a935a` 完全吸收；若上游实现或对应行为测试被移除，归档审计必须失败并重新评估是否恢复本地补丁。

---

## Archive — PATCH-ZSH-COMPLETION-SYNTAX（上游 v0.13.0）

### [PATCH-ZSH-COMPLETION-SYNTAX] Zsh completion `_arguments` 语法

| 字段         | 内容                                                                            |
| ------------ | ------------------------------------------------------------------------------- |
| **文件**     | `completions/_hermes`（工程外，不在 `PATCHED_FILES` 中）                        |
| **状态**     | ✅ 已上游合并（v0.13.0，commit `fe61d95b4`）                                    |
| **适用版本** | v0.9.0–v0.12.0 需要本地 patch；v0.13.0+ 上游 `hermes completion zsh` 输出已正确 |

**问题**：在任何新终端按 Tab 键补全 `hermes` 命令时，旧生成器曾将 `_arguments` 的互斥说明符 `(...)` 和替代语法 `{...}` 混用，提示符短暂出现 `...` 随即消失，无任何补全菜单：

```zsh
# 无效：zsh _arguments 不支持 (...){...} 组合写法
'(-h --help){-h,--help}[Show help and exit]'
```

**修复**：commit `fe61d95b4`（`fix(completion): use valid zsh _arguments exclusion-group syntax`，关闭 issue #22686）将生成器改为：

```zsh
'(-)'{-h,--help}'[Show help and exit]'
'(-)'{-V,--version}'[Show version and exit]'
'(-)'{-p,--profile}'[Profile name]:profile:_hermes_profiles'
```

利用 zsh brace expansion 把一行展开成两个独立规格，`(-)` 表示出现时排除其他所有选项。

本地处置：`hermes-update.sh` Step 7 中针对旧坏格式的三个检测块作为回归 sentinel 保留；如未来上游回滚，inline Python rewrite 会自动重新介入。

**验证**：`scripts/test_patch_evidence.py::audit_archived_zsh_completion_syntax` 每轮真实执行当前 checkout 的 `hermes completion zsh`，要求生成结果同时命中 help/version/profile 三个 `(-)` brace-expansion 形态且不命中旧坏格式；Step 7 仍保留自动修复反例，生成失败直接令升级非零。

**上游吸收判断**：已由 commit `fe61d95b4` 完全吸收；若真实 completion 输出重新退化为旧组合语法，归档审计与 Step 7 必须失败并恢复本地修复。

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

上游追踪：`hermes-update.sh` Step 8b 仍保留 `_web_ui_build_needed` 的存在性检查，用于在上游回滚时及时告警。

**验证**：`scripts/test_patch_evidence.py::audit_archived_dashboard_build_cache` 每轮真实运行 `tests/hermes_cli/test_web_ui_build.py::TestWebUIBuildNeeded::test_mtime_only_change_is_not_stale`，证明仅 mtime 漂移不会触发重建；Step 8b 同时检查 helper 存在，未来上游回滚时阻断 bundle 刷新。

**上游吸收判断**：已由 commit `5b5a53a1` 的内容哈希/staleness 实现完全吸收；若 helper 或行为测试退化，归档审计必须失败并重新评估补丁。

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

上游追踪：最初的等价修复线索来自上游 PR `#14423`；最终关闭本 issue 的是 commit `f5af6520`。当前 `main` 已包含该修复，因此本地不再维护源码 patch。

**验证**：`scripts/test_patch_evidence.py::audit_archived_gemini_thought_signature` 每轮真实运行 `tests/agent/transports/test_types.py::TestToolCallBackwardCompat::test_extra_content_getattr_pattern`，证明 `getattr(tool_call, "extra_content", None)` 仍返回 provider data；Step 8b 另检查实现与测试锚点并纳入 8c 总闸门。

**上游吸收判断**：已由 commit `f5af6520` 完全吸收；若 `ToolCall.extra_content` 或其行为回归被移除，归档审计必须失败并重新评估补丁。

---

## Archive — PATCH-DELEGATE-ACP-ROUTING（上游 v0.10.0）

### [PATCH-DELEGATE-ACP-ROUTING] Delegate ACP 子进程路由

| 字段         | 内容                                         |
| ------------ | -------------------------------------------- |
| **文件**     | `tools/delegate_tool.py`                     |
| **状态**     | ✅ 已上游合并（v0.10.0，commit hash 未记录） |
| **适用版本** | v0.9.0 需要本地 patch；v0.10.0+ 已上游修复   |

**问题**：`delegate_task(acp_command="copilot")` 传入 ACP 命令后，子 agent 的 `provider` 仍继承父 agent（如 `gemini`），未切换为 `"copilot-acp"`。`AIAgent` 构造时只在 `provider == "copilot-acp"` 时启用 ACP subprocess 通道，导致 `acp_command`/`acp_args` 被存储但从未使用，子 agent 直接走父 agent 的 API（如 Gemini），最终超时失败。

**修复**：在 `_build_child_agent()` 解析 `effective_acp_command` 之后，检测 `override_acp_command` 是否被显式设置：若是，强制 `effective_provider = "copilot-acp"` 并把 `effective_api_mode` 固定为兼容构造值，同时把 `acp_command` 原样交给 child。当前 `AIAgent` 以 provider + command 选择 `CopilotACPClient` 子进程通道，继承的 HTTP `base_url` 不参与该分支路由，因此不再把某个 base URL 字面量当成吸收条件。

上游追踪：v0.10.0 合入等价修复（具体吸收 commit 未在本地记录），本地 PATCH-DELEGATE-ACP-ROUTING 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**验证**：`scripts/test_patch_evidence.py::audit_archived_delegate_acp_routing` 使用审计器自建的最小 parent fixture，不导入上游测试文件的私有 helper；它穿过真实 `_build_child_agent()`、有效 ACP 命令探针和 mock child constructor，断言 `override_acp_command="copilot"` 确定性产生 `provider="copilot-acp"` 且保留命令。Step 8b 同时检查两个实现锚点，任一缺失即阻断升级收敛。

**上游吸收判断**：已由 v0.10.0 上游实现完全吸收；若行为探针或实现锚点回归，归档审计必须失败并重新评估补丁。

---
