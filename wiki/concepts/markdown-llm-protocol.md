---
title: LLM Text Format Protocols
created: 2026-05-14
updated: 2026-07-13
type: concept
tags: [architecture, llm, protocol, markdown]
sources: [_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md]
confidence: high
---

# LLM 系统的文本格式协议

文本格式协议不是“选 Markdown 还是 JSON”这样一个孤立问题，而是规定信息如何在**长期存储、程序传输、Prompt 上下文、模型输出与最终执行**之间转换。普通文本进入模型时通常先被序列化为 Unicode 字符串，再由具体模型的 tokenizer 映射为离散 Token ID：

$$
\tau_m:\mathcal{U}^*\rightarrow\{0,1,\ldots,|V_m|-1\}^*,
\qquad
(i_1,\ldots,i_L)=\tau_m(s)
$$

Markdown 标题、JSON 花括号和 XML 标签因此首先是字符序列中的模式。宿主系统可以预先把 Markdown 解析成 AST、把 HTML 解析成 DOM、把 JSON 校验后重新序列化，但这属于应用协议，不是语言模型天然执行的固定步骤。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## 分层，而不是寻找单一最优格式

一个可靠系统至少区分以下层次：

| 层               | 核心问题                              | 常用表示                                     |
| ---------------- | ------------------------------------- | -------------------------------------------- |
| Canonical Source | 原始证据、版本和转换过程能否重建      | Markdown、JSON、CSV、原始附件                |
| Transport        | 数据能否完整、可幂等地跨 API/队列传递 | typed JSON、JSONL、二进制协议、文件引用      |
| Prompt Context   | 指令、数据、示例和来源是否边界清楚    | content blocks、简洁 Markdown、XML 风格标签  |
| Model Output     | 程序能否稳定解析模型结果              | JSON Schema constrained output、strict tools |
| Execution        | 值是否真实、合法且获得授权            | 领域对象、业务验证、事务和权限系统           |
| Presentation     | 人类是否易于阅读和交互                | HTML、原生 UI、图表和富文本                  |

同一份内容可以在不同层采用不同表示。服务间可以用 Protobuf 传输，Prompt 边界转换成结构化 content blocks，模型输出再受 JSON Schema 约束，最后渲染成 HTML；没有理由要求所有层共享一种文本格式。

## 格式选择可以写成损失函数

对候选格式 $f$，可按任务定义：

$$
J(f)=\alpha N_m(f(x))
+\beta P_{\mathrm{parse}}(f)
+\gamma P_{\mathrm{semantic}}(f)
+\delta C_{\mathrm{maintain}}(f)
+\epsilon C_{\mathrm{interop}}(f)
$$

$N_m$ 是目标模型下的 Token 数，$P_{\mathrm{parse}}$ 是语法解析失败概率，$P_{\mathrm{semantic}}$ 是“语法合法但含义错误”的概率，后两项分别表示维护与互操作成本。权重取决于风险：知识笔记重视可读、可 diff；付款、删除或外部工具调用重视 schema、语义验证和授权。

因此，“JSON 一定比 YAML 贵”或“Markdown 一定最省 Token”都不是普遍定律。Token 数取决于 tokenizer 和真实数据分布，格式优劣还取决于解析失败、歧义与维护成本，应该在目标模型和代表性样本上实测。

## 各格式的协议角色

| 格式               | 适合                                      | 主要边界                                      |
| ------------------ | ----------------------------------------- | --------------------------------------------- |
| Markdown           | 人机共读、知识沉淀、Prompt 模板、Git diff | 方言不同；不是 schema；视觉布局不是权限       |
| JSON + JSON Schema | 程序交换、受约束输出、工具参数            | 冗长；schema 合法不代表事实正确               |
| YAML/TOML          | 人类维护的配置                            | YAML 版本与隐式类型有歧义；执行前必须解析校验 |
| XML                | 深层嵌套、混合内容、显式标签边界          | 转义与解析器安全复杂；标签不提升指令权限      |
| CSV/TSV            | 规则二维数据                              | 方言、换行、缺失值和类型需另行约定            |
| JSONL/NDJSON       | 逐记录流式处理和失败恢复                  | 每行应是独立 JSON 值，不适合跨行嵌套对象      |
| HTML/UI            | 最终展示、交互和无障碍语义                | 展示 DOM 不宜直接作为规范知识源               |

Markdown 的优势来自源文本可读、标题和围栏结构清楚、工具链广泛，而不是“模型只偏爱 Markdown”。持久文档应声明 CommonMark、GFM、Obsidian 或 MDX 等方言及允许扩展；程序需要结构时应解析 AST，不用正则猜标题和代码块。

## Prompt 边界不等于安全边界

Markdown 标题、XML 标签和代码围栏能提高区域可辨识度，却不能改变 system/developer/user 的权限，也不能让不可信文档失去提示注入能力。长 Prompt 至少应区分 instructions、documents、examples、current query、output contract、tool policy 和 untrusted content；真正的安全边界由角色隔离、最小工具权限、HITL、输出验证与审计实现。

模板插值也必须使用结构化 builder 或 serializer。若把用户文本直接拼进 `<document>...</document>`，用户可注入闭合标签；若手写 JSON，用户内容中的引号、反斜杠和控制字符同样会破坏结构。

## 结构化输出的保证边界

可靠性由弱到强依次是：自由文本、Prompt 要求 JSON、JSON mode、JSON Schema 受约束输出、strict tool schema，以及应用侧解析、领域验证与授权。受约束解码在每一步仅允许 grammar/schema 当前状态接受的 Token。若合法集合为 $A_t\subseteq V$，则：

$$
p_G(v\mid x_{<t})=
\begin{cases}
\dfrac{p(v\mid x_{<t})}{\sum_{u\in A_t}p(u\mid x_{<t})},&v\in A_t\\
0,&v\notin A_t
\end{cases}
$$

它可以保证完成的输出属于受支持的语法语言，却不能保证金额、日期、资源 ID 或事实本身正确。应用仍需处理 refusal、截断、content filter、timeout 和 transport error，并在执行前完成 schema、领域不变量、身份权限、幂等性与并发检查。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## Unicode、RAG 与多模态边界

跨平台文本可采用 UTF-8、NFC、LF 和末尾换行作为规范基线；原始证据与规范化派生文本应分开保存。哈希、缓存和签名前还必须固定换行、Unicode normalization、尾随空白与 JSON canonicalization 规则。

RAG 文档应保留 `source_id`、父级对象、转换器版本和原始位置，并沿 `raw source -> parsed blocks -> normalized text -> chunks -> index` 记录血缘。Chunk 边界应尊重标题、代码围栏、表格、页面和说话人，而不是机械地按固定 Token 数截断。

文本协议只定义多模态消息的标签、说明、来源与逻辑顺序；媒体字节如何变成连续特征、沿哪个轴拼接以及使用 self-attention 还是 cross-attention，属于 [[lmm-input-mechanics|多模态输入机制]]。Markdown 中出现 `![图](path)` 也不表示模型已经读取图片，必须由宿主解析并构造显式媒体内容块。两者是相邻但不同的协议层。

## 决策规则

1. 先确定生产者、消费者、失败代价和执行权限，再选格式。
2. 知识协作优先可读、可 diff；机器执行优先 typed schema 与应用验证。
3. 明确格式方言、编码、换行、时间、单位、空值和 schema 版本。
4. 对文本块和媒体块使用稳定 ID，不用“上面第二张图”作为唯一引用。
5. 用目标模型、真实数据和故障样本评测 Token、解析率、语义正确率、成本与延迟。
