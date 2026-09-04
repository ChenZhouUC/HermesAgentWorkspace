---
title: Hermes Agent macOS Operations Runbook
created: 2026-05-14
updated: 2026-09-04
---

# Hermes Agent macOS 运维 Runbook（AI Agent 执行版）

> **主要读者**：负责 Hermes Agent 安装、配置、运行、排障、升级和迁移的 AI Agent。
>
> **主要目标**：让接手现场的 Agent 只依赖当前磁盘状态和本手册，就能完成安全诊断、最小修复、验证、恢复与交接。
>
> 本文以 Hermes Agent 日常运维为主；peer machine 迁移是其中一个低频、可回滚的发布流程。本文不是面向人类用户的逐屏安装教程，也不替代当前仓库中的升级 playbook、PATCH 注册表和真实配置 schema。

### Runbook 路由

| 当前任务                       | 首选入口                        | 完成标准                              |
| ------------------------------ | ------------------------------- | ------------------------------------- |
| 健康检查或状态确认             | §3 日常健康巡检                 | 当前运行态、配置和关键依赖有证据      |
| 线上故障或功能回归             | §3.4 事件处置闭环、§10 日志诊断 | 根因明确，最小修复和回归闭合          |
| 配置、凭据或模型变更           | §5–§7                           | 新配置真实生效，权限未扩大            |
| Gateway、插件、MCP 运维        | §4、§9                          | supervisor、子进程和能力注册一致      |
| upstream 升级或本地 PATCH 维护 | §11                             | reconcile、full audit 和 Git 记录闭合 |
| 迁移到 peer machine            | §12–§13                         | 目标状态保留，身份重建，切换可回滚    |

## 1. Agent 执行契约

开始操作前先读取现场文件和运行状态。本文提供稳定原则与检查顺序，不替代当前仓库、配置、lockfile 和服务定义。

执行优先级：

1. 用户本轮明确指令。
2. 目标机已有且要求保留的状态与凭据。
3. 当前源码、配置 schema 和服务定义。
4. 本文中的默认建议。

通用约束：

- 先只读检查，再修改；高风险步骤前记录回滚点。
- 不根据旧文档猜测当前版本、模型、路径、用户身份或服务状态。
- 不在命令、日志、测试报告或最终回复中打印密钥。
- 不用“进程存在”代替“服务健康”，也不用“版本满足”代替“依赖可用”。
- 不扩大用户授权范围；未明确授权的凭据、群、工具和任务默认不迁移。

### 1.1 标准决策循环

每个运维任务按以下顺序执行：

1. **Discover**：读取 outer/inner Git、配置、事务、服务 PID、日志和数据状态。
2. **Classify**：区分代码、配置、秘密、持久状态、运行态和可再生临时产物。
3. **Protect**：记录目标、回滚点和用户已有改动；确认允许修改的范围。
4. **Act**：执行最小、可逆、与任务直接相关的变更。
5. **Verify**：先跑便宜的定向检查，再按风险升级到真实 runtime、full audit 或 canary。
6. **Persist**：同步测试、PATCH、playbook、Wiki 和 Git 提交，使下一位 Agent 不依赖本次会话。
7. **Report**：说明结果、证据、未解决风险和是否发生外部副作用。

不得跳过 Discover 直接根据旧记录修复；不得只凭单个绿色命令宣称整条链路完成。

### 1.2 授权与停止条件

- 只读诊断、目标范围内的最小修复和必要测试可直接执行。
- push、扩大工具/群/凭据权限、引入新外部依赖、删除用户持久状态需要独立授权。
- 活跃任务、未知文件、未分类秘密或无法确认的 destructive target 会阻断修改。
- 同一失败连续出现时先重新定性，不机械重复命令。
- full audit 已闭合且无新证据时停止深挖；后续转为事故、结构变化和周期触发式审计。

### 1.3 证据优先级

从强到弱：

1. 当前目标机的真实运行态与端到端 canary。
2. 当前 checkout 上的完整测试、verifier 和 final audit。
3. 配置解析、静态 gate 和代码检查。
4. 历史日志、旧报告和文档描述。

低等级证据不能覆盖更高等级现场事实。来源机器、旧 PID 或另一 peer 的绿色报告不能替目标机背书。

## 2. Hermes 运行面与状态边界

### 2.1 运行面

Hermes 在 macOS 上通常包含：

- `hermes-agent/`：Git 源码、Python venv、Node workspace。
- `config.yaml`：模型、工具、平台、记忆和安全行为。
- `.env`：机器本地凭据与环境覆盖。
- `credentials/`：service-account 等文件型凭据。
- `plugins/` 与 `my-skills/`：自定义能力。
- `SOUL.md`、`memories/`、`sessions/`、`cron/`：长期状态。
- `logs/`、`cache/`、`tmp/`、lock/socket：运行态与短期状态。
- `ai.hermes.gateway`：macOS 常驻服务。

### 2.2 状态分类

| 类别       | 示例                                 | 生命周期       | 默认处理          |
| ---------- | ------------------------------------ | -------------- | ----------------- |
| 可复现代码 | Git checkout、lockfile、本地补丁     | 随版本演进     | 从明确基线重建    |
| 功能资产   | skills、插件、必要脚本、独立运行时   | 随功能演进     | 按 allowlist 同步 |
| 持久状态   | SOUL、memory、sessions、cron、数据库 | 属于当前用户   | 保留并备份        |
| 机器配置   | 路径、平台身份、群 ID、launchd       | 属于当前机器   | 就地生成或合并    |
| 秘密       | API key、token、service-account      | 独立轮换       | 按字段授权处理    |
| 临时状态   | cache、socket、测试 home、staging    | 可再生         | 确认 stale 后清理 |
| 过程材料   | patch 说明、部署报告、迁移归档       | 仅用于维护事务 | 验收后删除        |

任何批量同步命令都必须显式排除持久状态和秘密。目录同名不代表生命周期相同。

## 3. 日常健康巡检

### 3.1 最小巡检顺序

```bash
git -C ~/.hermes rev-parse HEAD
git -C ~/.hermes status --short
git -C ~/.hermes/hermes-agent rev-parse HEAD
git -C ~/.hermes/hermes-agent status --short
bash ~/.hermes/hermes-update.sh --transaction-status
hermes gateway status
hermes doctor
```

不要在升级 preflight 中用可能触发网络 update-check 的版本命令代替 checkout 事实。版本、upstream SHA、outer commit 和运行 PID 是不同对象，应分别记录。

随后按需检查：

- Gateway supervisor PID 与实际子进程。
- 最新错误日志和当前启动日志。
- 主模型、fallback、compression 与媒体路由。
- 最近 cron 执行状态及投递错误。
- 磁盘空间、数据库 WAL、缓存和临时目录增长。
- 插件加载记录、工具注册和权限拒绝日志。

### 3.2 健康判定

健康状态至少要求：

- 配置能被真实加载器解析，而不只是 YAML 语法正确。
- Python 环境没有阻断运行的依赖错误。
- 当前模型至少有一条可用路由；关键 fallback 独立验证。
- Gateway 由系统服务监督，不是遗留的 detached 进程。
- 必需插件成功注册，未启用集成不会持续重连或发送空认证头。
- cron 调度器读取的是当前任务库。
- 日志脱敏开启。

### 3.3 改动后的最小复核

| 改动          | 最低复核                                    |
| ------------- | ------------------------------------------- |
| `.env`        | 权限、变量存在性、真实调用、gateway restart |
| `config.yaml` | 解析、runtime resolution、相关功能测试      |
| 模型链        | 主模型、每个 fallback、辅助模型分别调用     |
| 飞书配置      | 私聊、群 at、发送、附件和权限拒绝路径       |
| skill/plugin  | 加载、工具注册、最小正向与负向测试          |
| cron          | 列表、next run、手动 dry-run、投递目标      |
| runtime       | import、依赖一致性、关键测试、服务重启      |

### 3.4 事件处置闭环

当用户报告“无法读取、没有回复、权限错误、工具失败或行为退化”时：

1. **固定现场**：记录绝对时间、平台、chat/session、输入类型、资源标识、当前 HEAD 和 Gateway PID。
2. **定位失败层**：区分消息准入、资源获取、内容解析、模型路由、工具执行、结果发送和前端展示。
3. **复现最小路径**：优先使用同一输入的只读路径；不要用扩大权限或关闭沙箱来证明功能“可以工作”。
4. **检查诚实状态**：确认系统返回 `SUCCESS`、`INCOMPLETE`、`FAILED` 或 `UNSUPPORTED` 的哪一种，而不是只看退出码。
5. **修最小责任层**：配置桥接问题不在解析器修；内容解析问题不通过延长无限 timeout 掩盖。
6. **补负向回归**：证明旧实现会失败或假绿，新实现会明确通过或 fail closed。
7. **重载运行态**：运行时代码或插件变化后完成 drain-aware restart，并绑定新 PID 验证。
8. **持久化经验**：同步 PATCH、playbook 或本 runbook 中可复用的判断规则。

### 3.5 变更风险分级

| 等级 | 示例                                                     | 运维要求                            |
| ---- | -------------------------------------------------------- | ----------------------------------- |
| P0   | Gateway 中断、越权、秘密泄露、状态丢失、补丁无法回放     | 当轮修复，未闭合不得报告完成        |
| P1   | 关键功能失败、配置 fail-open、错误成功语义、并发状态污染 | 当轮修复并增加回归                  |
| P2   | 非主链路依赖 advisory、受上游 range 阻挡的兼容问题       | 明确影响面、监控条件和退场条件      |
| P3   | 低风险维护性或文档精度问题                               | 顺手修复或进入明确待办，不伪装成 P0 |

## 4. Gateway 与 launchd

### 4.1 服务操作

优先使用 Hermes 自身命令管理服务：

```bash
hermes gateway status
hermes gateway restart
hermes gateway stop
hermes gateway start
```

安装或修复服务定义时，确保当前 shell 的 PATH 已包含项目 venv、项目 `node_modules/.bin`、Homebrew 和系统命令目录，再执行安装。安装完成后同时检查 plist 和 launchd domain。

### 4.2 Supervisor 与子进程

一个健康的 macOS 部署应满足：

- plist 指向当前 `~/.hermes/hermes-agent/venv/bin/python`。
- launchd 中存在 `ai.hermes.gateway`。
- wrapper 和 gateway 子进程均来自当前安装路径。
- 登录自启和崩溃拉起由 launchd 提供。

如果安装器因 `launchctl bootstrap` 失败而启动 detached fallback，Gateway 虽然暂时可用，但不算完成。应停止 fallback、bootout 旧 label、校验 plist 后重新 bootstrap/kickstart。

### 4.3 重启纪律

- 普通配置变更完成后重启 gateway。
- 长任务运行期间使用带 drain 的正常重启路径，不以 `stop && start` 的短宽限强杀替代。
- 重启后重新读取状态，不把命令成功返回当作服务已经稳定。
- 检查旧 PID 是否退出、新 PID 是否由 launchd 监督。
- 插件或运行时代码变化后，在新子进程 PID 下重新验证插件注册和关键工具。

进程保护必须按当前 Hermes workspace 归属判断。其他项目中长期运行的 Codex、Claude、Gemini、Qwen 或 pytest 不应阻塞本实例；当前 Hermes 根目录内、或 argv 明确指向本实例的进程则必须等待或明确处理。无法确定 cwd/owner 时 fail closed。

### 4.4 Gateway 写屏障

以下变化会使已有 PID 的验证证据失效：

- `hermes-agent` 运行时代码；
- `config.yaml` 或 `.env`；
- `plugins/`、toolset、MCP 配置；
- LaunchAgent plist、解释器或 PATH；
- 进程身份和状态文件实现。

完成这些变化后，最终证据应包含：旧 supervisor PID、新 supervisor PID、真实 Gateway 子 PID、子进程加载的代码 SHA/插件版本，以及新 PID 下的 health/verifier 结果。

## 5. 配置与凭据运维

### 5.1 配置职责

- `config.yaml` 保存行为、路由和环境变量引用。
- `.env` 保存机器本地秘密和环境覆盖。
- `credentials/` 保存文件型凭据。
- LaunchAgent 只保存启动所需环境，不复制整份秘密配置。

不要在多个位置同时保存同一密钥。重复来源会让轮换、诊断和删除变得不可验证。

配置异常应区分“文件不存在”和“文件存在但无效”。语法错误、顶层非 mapping、关键 section 类型错误不能静默退回宽松默认值；安全边界、凭据隔离、configured-only 和平台 allowlist 应 fail closed。修改配置时优先使用临时文件校验后原子替换，避免 Gateway 读到半写 YAML。

### 5.2 凭据变更

凭据新增、迁移或轮换时：

1. 确认授权来源和目标字段。
2. 在目标机内部读取并写回，避免明文经过输出通道。
3. 将配置中的内联凭据改为环境变量引用。
4. 将文件权限收紧到目标用户。
5. 通过哈希相等或真实请求验证，不输出值。
6. 重启 gateway，并检查日志脱敏。
7. 删除含旧秘密的临时文件和已获准删除的备份。

后续指令只覆盖明确点名的字段，不能据此恢复整个旧 `.env`。

### 5.3 空凭据处理

需要用户稍后填写的集成可以保留空占位，但必须满足：

- 密钥和 base URL 成对校验。
- 空凭据对应的插件或 MCP 暂时 disabled。
- 不构造空的 Authorization header。
- Gateway 能在缺少该可选集成时正常启动。

## 6. 模型路由与输出行为

### 6.1 路由原则

- 主模型、fallback 和 auxiliary task 使用显式 provider/transport。
- OpenAI Responses 兼容入口与 Anthropic Messages 兼容入口不能混用协议。
- 标准云认证优先使用 SDK 原生生命周期；短期 token 不应由外部 cron 或唤醒脚本维护。
- 移除一个 provider 时，同时检查主模型、fallback、辅助任务、环境变量和旧服务。
- `configured_only` 场景只允许配置中明确列出的 route；同 provider/model 的不同 endpoint 是不同身份，不能只按模型名去重。
- 显式 auxiliary/vision route 失败时不得把媒体自动发送给 ambient provider；失败应可见，但权限不能自动扩大。

### 6.2 验证模型

对每条模型路由发起最小、确定性响应请求，并记录：

- provider 与模型标识；
- 返回码；
- 是否命中预期文本；
- 耗时；
- 经脱敏后的错误类别。

供应商 `/models` 接口、手写 HTTP 请求和 CLI wrapper 可能使用不同认证头或兼容路径。最终以 Hermes 自身 transport 的端到端结果为准。

### 6.3 Thinking 与 reasoning

不希望向用户展示推理内容时，要同时检查：

- 全局 reasoning 显示开关；
- 各消息平台的 reasoning 显示开关；
- thinking progress；
- 流式事件中供应商特有的 reasoning 字段；
- 中间消息和最终消息是否经过相同过滤。

只关闭一个 UI 选项不足以证明所有供应商都不会泄露 thinking。

## 7. 飞书与身份数据

### 7.1 平台连通

飞书接入至少验证：

- App 凭据有效且应用版本已发布。
- WebSocket 或 webhook 连接方式与配置一致。
- bot 能接收私聊和群 at。
- 发送文本、图片和附件分别成功。
- 联系人权限能返回实际需要的字段。

图片生成成功不等于图片发送成功。应分别验证模型输出、文件落盘、资源上传权限和消息发送。

### 7.2 人员表同步

飞书 `open_id` 是应用作用域标识。更换 bot 应用后，即使员工不变，`open_id` 也可能全部变化。

人员合并顺序：

1. 使用目标应用拉取完整草稿。
2. 用 tenant `user_id` 匹配已有人员。
3. 更新为目标应用的新 `open_id`。
4. 新快照确实提供的组织字段作为权威值。
5. 保留称呼、背景、行为、态度和风险等人工字段。
6. 主人固定在首项，其余人员按稳定员工编号排序。
7. 验证 `open_id` 与 `user_id` 完整且唯一。

如果某字段在整份快照中都为空，应先判断为字段级权限不足。此时保留已有字段并告警；不能把权限收窄解释为所有员工同时丢失该属性。

### 7.3 身份文本边界

- 运行时 prompt 的主人称呼应适配目标机主人。
- 人物自己的称呼和别名留在对应人员条目中。
- 历史 session、memory、USER 和 SOUL 不做批量文本替换。
- 主人 open ID、平台 assistant ID 和沙箱 mutation trust 应一致。

### 7.4 群聊权限

- 群能力只对显式 allowlist 开放。
- 群存在于配置中，不代表 bot 已经入群。
- 人员存在于通讯录，不代表拥有高风险工具权限。
- 文档修改、删除、图片生成和其他副作用能力应分别授权。

### 7.5 附件与文档读取

把附件处理拆成两个独立阶段：

1. **Acquisition**：从当前消息、引用、sender window 或 Drive 获取受限字节。
2. **Interpretation**：从 PDF、Office、HTML、文本或媒体中提取模型可用内容。

两阶段分别设置文件数、单文件大小、总 deadline、并发 admission 和失败状态。预算必须在尝试下载前消耗；失败和超限也计入尝试，不能让大量无效资源绕过上限。

模型可见状态统一解释为：

- `SUCCESS`：目标内容已实际取得；
- `INCOMPLETE`：只得到部分内容，例如 PPTX 文字已读但图片/图表未读；
- `FAILED`：资源存在但获取或解析失败；
- `UNSUPPORTED`：当前能力明确不支持该格式或动作。

一页 PPT 有标题文字，不代表图表、截图或流程图已经读取。任何视觉元素缺口都应显式标记，不能用“文本抽取成功”替代完整阅读。生产 canary 要穿过真实消息获取、解析、prompt 注入和回复链路，而不是只单测 extractor。

## 8. Cron、记忆与会话

### 8.1 Cron

- Cron 属于目标机业务状态，升级和迁移默认保留。
- 不把源机 cron 复制到 peer。
- 升级前记录任务数量、启用状态、schedule、provider 覆写和投递目标。
- 升级后比较任务库哈希，并对关键任务做 dry-run。
- 不再需要的任务应通过明确删除操作移除，不能靠覆盖整个 cron 目录。

### 8.2 Memory、USER 与 SOUL

- SOUL 定义目标 agent 的长期人格与边界。
- USER 是目标用户画像，不应从另一台机器覆盖。
- MEMORY 是累积事实与偏好，应保持原内容和权限。
- 迁移代码中的身份词替换不应进入这些历史状态文件。

### 8.3 Sessions

- 切换前停止写入并记录文件数或数据库状态。
- 切换后验证会话仍可枚举和恢复。
- 测试必须使用隔离 home，避免产生混入正式目录的测试会话。
- 清理 staging 时确认其 session 属于测试，再删除。

## 9. Skills、插件、MCP 与媒体能力

### 9.1 Skills

- 上游 skills 与自定义 skills 分目录管理。
- 自定义 skills 按 allowlist 迁移，不假设每个目录都需要执行权限。
- skill 内 README、模板和参考文件可能是运行输入，不能按文件名批量删除。

### 9.2 插件与沙箱

- 插件必须同时验证注册 API、hook 存在、配置 schema 和运行时注册日志。
- 私聊、群聊和不同用户角色使用独立权限集合。
- 文件、网络、脚本和不可逆操作分别设边界。
- 配置要求但当前未启用的兼容字段可以保留惰性值，但不得重新暴露对应工具。
- 一轮一次的 capability claim 必须跨 worker 共享，且不能因容量上限驱逐仍在运行的 turn；满载时宁可拒绝新 claim。
- tool stdout、stderr 和 traceback 在进入模型前必须移除秘密和宿主绝对路径；正常输出脱敏不足以证明失败路径安全。
- verifier 必须同时证明 hook 已注册、真实执行点存在、行为测试通过，以及当前 Gateway 子进程加载了同一插件版本。

### 9.3 MCP

MCP 只定义能力接入协议，不负责调用授权和执行隔离。禁用一个 MCP 时同时处理：

- server 配置；
- 平台 toolset；
- 工具 allowlist；
- 用户/群信任列表；
- 关联 skill；
- 后台服务和缓存。

### 9.4 媒体与独立运行时

- 图片生成的 API key 和 base URL 必须成对存在。
- 图表渲染器可能拥有独立 Python venv，应单独迁移和测试。
- Playwright 包、浏览器缓存和 Electron 二进制是不同对象。
- 不需要浏览器自动化时可跳过浏览器下载，但不能误删其他媒体运行时。

## 10. 日志、诊断与故障处理

### 10.1 日志原则

- 优先查看当前启动后的日志窗口，避免被旧错误误导。
- 日志中出现 secret redaction disabled 必须先修复，再继续测试。
- 报告错误类型、状态码和调用阶段，不复制可能包含秘密的完整请求。
- Gateway、模型、MCP、媒体和 cron 的错误应分层定位。
- 同一错误的 producer、transport、consumer 和用户可见状态分别记录，避免把下载超时误诊为解析失败。
- 只引用当前启动 PID 之后的注册/错误日志；旧进程和 doctor 产生的同名日志不能为 Gateway 借绿。

### 10.2 最小证据包

一次可交接的故障记录至少包含：

- 发生时间、平台/chat/session 和输入类型；
- outer commit、inner upstream SHA、Gateway supervisor/child PID；
- 失败发生在 acquisition、interpretation、routing、execution 还是 delivery；
- 脱敏错误类别和用户可见状态；
- 最小复现与对应修复；
- 新增测试节点、verifier 或 canary 结果；
- 是否需要 restart、回滚或上游跟进。

### 10.3 常见故障矩阵

| 现象                              | 判断与处置                                                      |
| --------------------------------- | --------------------------------------------------------------- |
| 有 PID，但不能自启                | 区分 detached process 与 launchd supervisor，检查 domain 状态   |
| `launchctl bootstrap` 失败        | 停净 fallback，bootout 旧 label，校验 plist/PATH 后重新加载     |
| 模型目录可访问但推理失败          | 用 Hermes 实际 transport 发最小请求，检查协议、认证头与路由     |
| fallback 没有接管                 | 分别验证 provider identity、模型名、凭据和触发错误类型          |
| MCP 持续报非法 header             | 凭据为空时禁用 MCP，填写后再启用                                |
| 飞书能收消息但不能发图片          | 分开检查图片文件、资源上传权限、image key 和发送接口            |
| at 用户身份缺失                   | 检查事件权限、消息元数据、应用作用域 ID 和人员表映射            |
| 回复泄露 reasoning                | 检查全局/平台显示项和供应商流式事件过滤                         |
| Python 版本合规但启动失败         | 检查 venv 重复包、错误平台 wheel、native extra 和 editable path |
| shell 能找到 Node、launchd 找不到 | 修复 LaunchAgent PATH，并重新 bootstrap/kickstart               |

## 11. 升级、PATCH 与 Git 运维

### 11.1 仓库所有权

Hermes 本地部署有两个不同的 Git 语义：

- outer `~/.hermes`：保存配置仓库、升级脚本、PATCH 注册表、replay bundle、插件、运维文档和 Wiki，应正常 commit。
- inner `~/.hermes/hermes-agent`：保持官方 upstream HEAD；本地工程补丁以未提交 overlay 存在，由 outer 的 `patches/local-patches.diff` 持久化，默认不在 inner 创建 commit。

看到 inner 大量 modified 文件不等于工作树失控。先用 outer 的 `PATCHED_FILES`、bundle 和 package-lock review receipt 判断是否为完整预期 overlay；缺项、额外项或 staged index 才是异常。

### 11.2 升级事务入口

```bash
bash ~/.hermes/hermes-update.sh --transaction-status
bash ~/.hermes/hermes-update.sh --update       # 新事务唯一一次官方获取
bash ~/.hermes/hermes-update.sh --reconcile    # 固定 SHA 的本地收敛
bash ~/.hermes/hermes-update.sh --final-audit --json
```

规则：

- 没有未完成事务、且用户明确要求升级 upstream 时，才执行一次 `--update`。
- 一旦取得 target SHA，冲突修复、测试补洞、文档调整和跨会话接管都只运行 `--reconcile`。
- transaction 存在时不得再次 fetch/pull 或移动目标。
- update/reconcile/final-audit 使用同一所有权锁；锁 owner 不完整或无法确认时停止，不自动抢占。
- 其他 workspace 的 Agent 不阻塞本实例；当前 Hermes workspace 内的测试和任务需要排空。

完整升级算法和补丁吸收条件以 `~/.hermes/hermes-update.md` 与 `~/.hermes/patches/PATCHES.md` 为权威，本节只保留运维入口。

### 11.3 PATCH 重放与审计

- 在固定 upstream 基线上生成/校验完整 full-index bundle。
- 冲突按当前上游语义重新解决，不能机械选择 ours/theirs。
- 每个 active PATCH 都必须有 owner files、独立 gate、精确测试/probe 和上游吸收条件。
- 测试存在不等于 evidence 有效；节点必须实际执行该 PATCH 拥有的生产文件。
- final audit 首尾绑定 outer/inner HEAD、tree、index、worktree、untracked、bundle、base 和 reviewed lockfile。
- 插件变化必须在新 Gateway 子 PID 下复验，磁盘测试不能代替 runtime freshness。

### 11.4 提交纪律

用户明确要求 commit 时：

1. 区分本任务文件、inner overlay 和用户无关改动。
2. 先运行 full final audit。
3. 仅 stage 应进入 outer Git 的文件。
4. 执行本机 commit approval hook，再创建 commit。
5. 在 clean outer 上运行 post-commit `--require-clean-outer` final audit。
6. 临时 stash 的无关用户改动按精确 OID 恢复。

commit 不自动授权 push。push 前再次汇总 branch/outgoing commits，并取得用户确认。

### 11.5 回滚

回滚单位应包含源码、配置和必要运行时，但不能覆盖升级期间产生的新用户状态。优先把失败版本移出活动路径，再恢复先前已验证版本；不要使用会同时清除未知用户改动的宽泛 Git、`reset --hard` 或递归删除命令。PATCH 冲突、stash 恢复冲突和 transaction 写失败都应保留可接管现场并返回非零。

## 12. Peer 迁移

Peer 迁移是一次受控发布事务，不是目录镜像。详细方法已提炼到 Active Layer 2；本节只保留运维入口。

### 12.1 迁移原则

- 源码基线相同后再应用补丁。
- 功能资产按 allowlist 迁移。
- 目标持久状态原地保留。
- 配置按字段重建。
- 凭据按来源和授权逐项处理。
- 身份 ID 在目标应用下重新获取。
- 运行时通过实际依赖和测试决定复用或重建。
- 切换前保留回滚能力，验收后清理过程材料。

### 12.2 Git 较慢时

在源机从当前 HEAD 建立干净 clone，验证 patch 后打包包含 `.git` 的源码树。目标机校验归档哈希，从包内 Git 数据离线得到干净工作树，再执行 patch apply。完成后恢复真实上游 remote。

这种方法避免公网 Git 成为关键路径，同时保留“基线”和“补丁”两个可分别验证的层次。

### 12.3 暂存与切换顺序

1. 只读盘点目标机。
2. 创建受限权限的本地备份。
3. 在独立 staging 中组装代码、配置和运行时。
4. 完成测试、模型调用、身份和权限验证。
5. 停止 gateway 并保存最终状态快照。
6. 原子替换源码和明确授权的外围资产。
7. 重建 launchd 服务。
8. 对比状态不变量并复跑关键测试。

### 12.4 Peer 授权矩阵

迁移 Agent 在写入前生成逐项矩阵：

| 对象                   | 默认来源          | 是否复制         | 验证方式                         |
| ---------------------- | ----------------- | ---------------- | -------------------------------- |
| upstream checkout      | 固定官方 SHA      | 是，或目标机重建 | HEAD/remote/bundle               |
| 本地 PATCH             | 来源 outer bundle | 是               | apply/reverse/full audit         |
| plugins 与 my-skills   | 明确 allowlist    | 按需             | 注册、正例、拒绝反例             |
| SOUL、USER、MEMORY     | 目标机            | 否               | 哈希/内容不变量                  |
| sessions、cron、数据库 | 目标机            | 否               | 计数、哈希、可恢复性             |
| `.env` 与 credentials  | 单独授权          | 逐字段           | 引用存在、真实请求、不输出值     |
| 飞书人员和群 ID        | 目标应用重建      | 否               | tenant ID 映射、唯一性、权限拒绝 |
| cache/tmp/test home    | 不迁移            | 否               | 目标不存在或可再生               |

不能用“复制整个 `~/.hermes` 后再删不需要的文件”代替该矩阵。

### 12.5 切换验收与回滚条件

切换成功至少要求：

- target upstream SHA、PATCH bundle 和 runtime import 一致；
- 目标 SOUL、memory、sessions、cron、数据库未被来源覆盖；
- 主模型、每个关键 fallback 和 auxiliary route 通过 Hermes transport canary；
- 飞书 owner、群 allowlist、普通成员拒绝路径和附件链路通过；
- launchd supervisor 与 Gateway 子进程来自目标安装；
- 插件版本、MCP 工具集和 sandbox verifier 属于目标 PID；
- 迁移中间态没有混入 active runtime。

任一身份、持久状态或权限不变量不成立时立即回滚；可选 provider 或非主链路工具失败时可保留 staging、标记部分完成，不得把目标机切到未经验证的混合状态。

## 13. 迁移后清理

### 13.1 清理前置条件

只有满足以下条件才能删除回滚材料：

- 新代码和运行时可启动。
- 关键功能与模型调用通过。
- Gateway 已由 launchd 托管。
- SOUL、memory、sessions、cron 和数据库已验证未被覆盖。
- 用户明确确认不再需要迁移备份。

### 13.2 应删除

- staging、测试 home 和 model probe；
- 源码、运行时和依赖的传输归档及校验文件；
- 临时 patch/diff、apply 演练仓库和失败 venv；
- 旧源码副本与切换快照；
- 迁移脚本、部署报告、patch 说明和升级 playbook；
- 含旧秘密的环境或 credential 备份；
- 退役服务的脚本、plist、launchd 注册和进程；
- `.pytest_cache`、迁移产生的 `__pycache__` 和 `.DS_Store`。

### 13.3 不应删除

- 当前源码、`.git`、lockfile 和已应用功能改动；
- 官方仓库自带的 README、docs、测试和迁移模块；
- skill 运行所需的 README、模板和参考资料；
- 当前 venv、`node_modules` 和独立工具运行时；
- 当前配置、凭据、服务定义和有效日志；
- 目标 SOUL、memory、USER、sessions、cron 和业务数据库；
- 尚无法证明 stale 的缓存、锁、socket 和业务工作区。

不要仅凭文件名包含 `migration`、`patch` 或 `README` 就删除。先判断所属层级、Git 跟踪状态、运行时引用和数据所有权。

### 13.4 清理后的证明

- staging、迁移备份和旧迁移归档不存在。
- 活动目录外层没有 patch bundle、迁移 playbook、部署报告或旧配置备份。
- 退役服务没有文件、launchd 注册或进程残留。
- 当前 gateway、Git 状态和模型配置未被清理破坏。
- SOUL、memory、sessions、cron 和数据库仍存在且统计一致。

“像新安装一样”指没有迁移过程残留，不表示重置目标用户的持久状态，也不表示删除官方源码或功能依赖。

## 14. 最终验收与汇报

### 14.1 Agent 检查清单

- [ ] 用户授权边界已逐项落实。
- [ ] outer Git、inner upstream、PATCH overlay 和 reviewed lockfile 已正确区分。
- [ ] Git 基线、补丁集合、transaction 和 replay bundle 可证明。
- [ ] 当前配置不含未授权 provider、MCP 或内联秘密。
- [ ] 目标状态未被源机覆盖。
- [ ] 人员身份、主人排序、群聊与权限边界正确。
- [ ] Python、Node、npm 和独立运行时通过实际验证。
- [ ] 模型、平台、插件、媒体和 cron 的必要测试通过。
- [ ] Gateway 由唯一、正确的系统服务托管。
- [ ] supervisor PID、Gateway 子 PID、代码 SHA 和插件版本一致。
- [ ] 文档/媒体读取对缺失内容使用明确 `INCOMPLETE`、`FAILED` 或 `UNSUPPORTED`。
- [ ] cleanup 没有 candidate、review、policy error 或误阻塞其他 workspace。
- [ ] 旧服务与迁移过程材料已按授权删除。

### 14.2 汇报格式

最终报告只包含：

1. 完成、部分完成或阻塞状态。
2. outer commit、inner upstream SHA、PATCH/bundle/transaction 结果。
3. supervisor/child PID、运行时代码与插件版本。
4. 持久状态保护结果。
5. 身份、群聊、工具和凭据边界，不包含具体秘密。
6. 测试、verifier、final audit 和必要 canary 结果。
7. 发生的外部副作用、回滚状态和清理结果。
8. 仍需用户处理的事项及其风险等级。

不要把命令流水、调试噪音、密钥、个人标识或一次性迁移数字写成长期知识。
