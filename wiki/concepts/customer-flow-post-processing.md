---
title: Customer Flow Post-Processing (客流后处理与指标加工)
created: 2026-05-25
updated: 2026-07-02
type: concept
tags: [computer-vision, spacesight, pipeline]
sources: [_living/Whale-SpaceSight/Customer-Flow-Post-Processing.md]
confidence: high
---

# Customer Flow Post-Processing (客流后处理与指标加工)

线下零售门店 [[reid-pipeline|ReID 系统]] 的下游处理层：把轨迹与特征结果加工为可用于商业决策的业务指标（客流量、批次、接待）。
在 SpaceSight 架构中，客流加工呈现出严格的**三阶段顺序漏斗**：感知侧基础过滤 ➔ 中台二次清洗 ➔ 业务指标衍生。

> **代码边界说明**：第一阶段过滤由极前置的 [[edge-algo|Edge ALGO]] 与 [[hidalgo|HIDALGO]] 完成并落库。而本概念描述的**中台清洗**（营业时间、停留时长等）与**指标衍生**（接待识别、批次聚合），则运行在基于 Airflow 调度的自动化数据流中 (`airflow/analytics`)，属于数据中台范畴。

## 阶段一：感知侧基础过滤

依赖视觉信号与时空几何进行第一层"防脏水"拦截：

- **门框过店 (Passby)**：结合 [[edge-algo|Edge ALGO]] 平行投影比值与 [[hidalgo|HIDALGO]] 轨迹像素跨度，剔除未深入店内的徘徊轨迹。
- **静态与扰动剔除**：根据检测框尺寸稳定性、方向矢量及置信度，剔除假人、展车反射、嵌套检测（特殊发型误识）。
- **极早期身份拦截**：通过 1-NN 库检索与簇内多数表决，拦截确信度极高的店员与外卖员。

## 阶段二：中台二次清洗与过滤 (Airflow)

数据落库后，Airflow 清洗脚本引入强业务属性规则进行二次筛选：

- **营业时间与时区过滤**：排除闭店盘点、非营业时间段内的无效扰动轨迹。
- **停留时长过滤 (Stay Duration)**：按门店开关剔除逛店时间过短（极速穿堂）的记录。
- **进店次数去重 (Frequency)**：对于异常高频进店（如商场保洁、临近店员）通过次数阈值或跨天规则降权抹除。

## 阶段三：核心业务指标加工 (Airflow)

基于纯净的顾客底表，Airflow 核心算子衍生出高阶商业指标：

- **客流批次聚合 (Batch Flow)**：将同行时间窗交叠率高的多个离散顾客 ID 聚合成“家庭/同行批次”。
- **接待指标体系 (Reception)**：结合店员轨迹重叠与 Pad 埋点对齐，计算：
  - 接待人数 / 批次 (`acc_ped`, `acc_batch`)；
  - 及时接待率（进店时间与接待开始时间的响应差）；
  - 无人接待与深度接待批次。
- **在店与区域驻留 (Shop Stay & ROI)**：合并同批次内多次捕捉，计算顾客生命周期的在店总时长，并映射至具体展区（AreaMap）生成漏斗。
- **路过与进店率 (Outside Traffic)**：提取店外视野客群，计算最终的门店进店率。^[[[_living/Whale-SpaceSight/Customer-Flow-Post-Processing|Customer-Flow-Post-Processing]]]

---

**相关概念**:

- [[hidalgo|HIDALGO]]
- [[edge-algo|Edge ALGO]]
- [[reid-pipeline]]
