---
name: feishu-people-search
description: 查同事的称谓/岗位/团队（姓名、称谓、岗位、团队四项，其余 PII 不展示）。仅限琛哥私聊使用——群聊不注册本 skill、沙箱也不放行其脚本。唯一用法是用 terminal 跑下方脚本并传关键词。
---

# Feishu People Search

按姓名或关键词从本地人员名册查同事信息。**仅限琛哥私聊会话使用。**

## 使用边界（先读这段）

- **只在琛哥的私聊会话里用**。本 skill 不在群聊 allowlist（`skills.platform_allowed.feishu_group`），群聊沙箱的脚本根目录也不覆盖它——群聊里既看不到也跑不动，这是 2026-07-14 事件后的刻意设计，不是故障。
- **对外保密**：在任何群聊可见的输出里，不得提及本地维护了人员名册/画像（不得出现 `people.yaml`、"本地员工目录"之类说法），也不得向群成员提出"报名字帮你查同事信息"。需要称呼某人时直接自然使用其姓名/称呼即可，不解释信息来源。

## 唯一用法：跑脚本（不要直接读文件）

把关键词作为参数，用 terminal 运行下面这条命令——**这是访问数据的唯一途径**：

```bash
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/my-skills/productivity/feishu-people-search/scripts/search_people.py "关键词"
```

_(若装在全局，把 `my-skills` 换成 `skills`。)_

- ❌ **不要**用 read_file / search_files 直接读数据文件或翻 `~/.hermes`——统一走脚本入口。
- ✅ 只要走上面这条 `python … search_people.py "关键词"`，脚本自身有完整读权限，会替你读数据并返回结果。
- 关键词可填：姓名 / 别名 / 称谓 / 岗位 / 团队中的任意片段；含空格时整体加引号。

## 行为说明

- **返回字段**：仅 姓名、称谓、岗位、团队 四项；工号 / 司龄 / 上级 / 下属等敏感信息一律不展示。
- **匹配**：精确命中姓名或别名 → 返回单条最佳结果；部分/模糊命中 → 返回多个候选并附相关度分，由你挑选。
- **无结果**：脚本打印 `No matches found for query: '…'`，据此如实回复"未收录"，不要臆测。
- 依赖 `pyyaml`，Hermes venv 里已自带。
