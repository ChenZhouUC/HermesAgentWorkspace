---
name: feishu-people-search
description: 查同事的称谓/岗位/团队（姓名、称谓、岗位、团队四项，其余 PII 不展示）。唯一用法是用 terminal 跑下方脚本并传关键词；不要、也无法用 read_file / search_files 直接读 people.yaml 或翻 ~/.hermes（群聊沙箱会拦）。
---

# Feishu People Search

按姓名或关键词从 `~/.hermes/people.yaml` 查同事信息。

## 唯一用法：跑脚本（不要直接读文件）

把关键词作为参数，用 terminal 运行下面这条命令——**这是访问数据的唯一途径**：

```bash
~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/my-skills/productivity/feishu-people-search/scripts/search_people.py "关键词"
```

_(若装在全局，把 `my-skills` 换成 `skills`。)_

- ❌ **不要** `read_file ~/.hermes/people.yaml`、也不要 `search_files ~/.hermes`——`~/.hermes` 不在群聊只读根目录里，必被沙箱拦截；查不到 ≠ 没权限，而是没用对入口。
- ✅ 只要走上面这条 `python … search_people.py "关键词"`，脚本自身有完整读权限，会替你读 yaml 并返回结果。
- 关键词可填：姓名 / 别名 / 称谓 / 岗位 / 团队中的任意片段；含空格时整体加引号。

## 行为说明

- **返回字段**：仅 姓名、称谓、岗位、团队 四项；工号 / 司龄 / 上级 / 下属等敏感信息一律不展示。
- **匹配**：精确命中姓名或别名 → 返回单条最佳结果；部分/模糊命中 → 返回多个候选并附相关度分，由你挑选。
- **无结果**：脚本打印 `No matches found for query: '…'`，据此如实回复"未收录"，不要臆测。
- 依赖 `pyyaml`，Hermes venv 里已自带。
