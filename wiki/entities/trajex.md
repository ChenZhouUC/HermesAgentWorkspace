---
title: trajex (ReID 感知层服务)
created: 2026-05-26
updated: 2026-05-26
type: entity
tags: [computer-vision, reid, pipeline, ops]
sources: [_living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex.md]
confidence: high
---

# trajex (ReID 感知层服务)

trajex 是 [[hidalgo|Hidalgo ReID 项目]]中的**感知层服务**：消费边缘相机上传的轨迹（时间戳 + 图像坐标 + 人体截图序列），通过模型推理生成下游 [[hidalgo|Hidalgo 计算层]] 所需的特征数据。它是整套 ReID 系统中"采集与计算前置"段的承载者。^[[[_living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex|ReID-Perception-Layer-trajex]]]

## 职责边界

trajex 只承担**逐轨迹特征化 + 角色 1-NN 判定**两件事；它**不做聚类、不分配行人 ID**——后者是下游 [[hidalgo]] 计算层的职责。这种分工见 [[trajex-vs-hidalgo]] 详细对比。

具体输出：

- 图像级特征（每条轨迹的多张代表帧各算一行，含上装检测/上装特征/角色标签）；
- 轨迹级特征（每条轨迹聚合一行，含行人特征向量 + 角色融合分）。

每行特征都带模型版本标签，形成完整的"哪个模型在哪一天产出"血缘。

## 关键设计模式

trajex 是若干通用 ML 工程方法学的实践载体：

- **库查询作为特征**：把"角色判定"以 1-NN 检索的形式烤进特征表，而非留给下游聚类——见 [[reid-library-lookup]]；
- **影子特征轴并行**：旧主 ReID 特征轴与新统一特征轴可以同时写入，cutover 是配置开关——见 [[model-shadow-deployment]]；
- **DDL 作为契约**：trajex 同时声明自己写的特征表和下游计算层写的结果表的 DDL，但权责由代码隔离——见 [[schema-as-handoff-contract]]。

## 运维面

trajex 包含三个独立运维面：

- **管理后台**：浏览轨迹、可视化、人工标注店员；
- **HTTP 接口**：暴露添加店员特征、分页查询轨迹等 API；
- **告警服务**：扫描"未匹配设备"集合，按组织分发告警。

回放工具链分三种：定时补漏、人工重跑、缓存重建；其中人工重跑绕过去重，缓存重建只修复去重态、不重算特征。

---

**相关概念**:

- [[reid-pipeline]]
- [[hidalgo]]
- [[trajex-vs-hidalgo]]
- [[reid-library-lookup]]
- [[model-shadow-deployment]]
- [[schema-as-handoff-contract]]
