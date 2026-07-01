---
title: 如何排查 SpaceSight 出入口客流人数偏差
created: 2026-07-01
updated: 2026-07-01
type: query
tags: [spacesight, computer-vision, reid, ops]
sources:
  - _living/Whale-SpaceSight/SpaceSight-QA-List.md
  - _living/Whale-SpaceSight/Customer-Flow-Post-Processing.md
  - _living/Whale-SpaceSight/ReID-Pipeline-Architecture.md
confidence: high
---

# 如何排查 SpaceSight 出入口客流人数偏差

> **问题场景**：门店人工数出某天进店人数，与 SpaceSight 系统线上进店人数差异明显。如何快速判断是口径差异、算法误识、ReID 去重问题，还是人工抽样本身不可靠？

这个 SOP 串联 [[spacesight]]、[[reid-pipeline]] 与 [[customer-flow-post-processing]]：ReID 层产出行人 ID + 轨迹，后处理层再决定哪些轨迹算作业务客流。排查时必须先对齐分层边界，否则容易把后处理口径问题误判为模型问题。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

## Step 1：先对齐统计口径

先确认双方数的不是两个东西：

- 人工口径是否只数“顾客”，系统是否包含员工、短暂停留人员、反复进出人员；
- 人工是否按自然人去重，系统是否按批次 / 人次 / 轨迹去重；
- 时间窗是否严格一致，是否包含跨日、开闭店前后、系统延迟入库；
- 出入口区域是否一致，门框、店外徘徊区、店内深度区域是否被混用。

如果口径未对齐，不进入算法排障。先把业务口径写成可复查的统计定义。

## Step 2：抽样视频做 1v1 对标

选择 2-3 个具有代表性的时间段，至少覆盖：

- 高峰时段；
- 低峰时段；
- 出入口容易被遮挡或过店干扰的时段。

逐帧或按事件对齐系统轨迹与视频事实，把差异拆成四类：系统多算、系统少算、人工漏数、口径不一致。只有当同一类问题重复出现，才进入对应修复路径。

## Step 3：按误差类型定位层级

常见归因：

- **员工未过滤**：角色判定或店员库覆盖问题，回到 [[reid-pipeline]] 的角色判定链路；
- **过店误识进店**：出入口区域过小或门框几何导致，回到 [[customer-flow-post-processing]] 的客流过滤策略；
- **静态物体扰动**：假人、样品、海报等被检测框抖动生成伪轨迹，需要后处理多信号过滤；
- **重复进店未按口径去重**：属于人次 / 自然人 / 批次口径配置问题；
- **人工漏数**：高峰拥挤时人工数常低估，应以视频回放对齐而不是只采信人工总数。

## Step 4：灰度修复，不直接全局改参数

修复策略必须按店灰度：

- 先在问题门店开启或调整对应过滤配置；
- 复跑同一抽样时间段，验证误差类别是否收敛；
- 再扩展到相似门店，不把单店参数直接推成全局默认。

## 反模式

- 不看视频，只凭人工总数直接调阈值；
- 把员工过滤、过店过滤、ReID 去重、业务口径混在一个“准确率”里；
- 为了让某一天总数对齐而牺牲其他时间段稳定性；
- 把非标门店参数推广成全局默认。

**相关概念**:

- [[spacesight]]
- [[reid-pipeline]]
- [[customer-flow-post-processing]]
- [[hidalgo|HIDALGO]]
