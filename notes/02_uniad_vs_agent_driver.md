# UniAD 总图 × Agent-Driver × CE5212

日期：2026-08-13  
目的：能画三张流水线，说清你在哪一层。不是复现 UniAD。

---

## 1. UniAD（端到端大模型岗在考的）

论文：Planning-oriented Autonomous Driving（CVPR 2023 Best Paper）  
仓：https://github.com/opendrivelab/uniad

一条网络，按规划倒推任务：

```text
多相机
  → BEV 表征
    → 在线建图 / 检测 / 跟踪
      → 运动预测
        → 占用栅格
          → 规划器出轨迹
```

面试要能说：它不是「先感知再另写规划」，而是 **规划当目标、中间任务当辅助**。评测常挂 nuScenes 开环；Bench2Drive 把它放进 CARLA 闭环后，开环好看的模型可能翻车。训练量级是多卡 A100，不是课设周末。

你没有：BEV、nuScenes、占用、自车轨迹头。

---

## 2. Agent-Driver（离你最近的「别人的仓」）

介绍：https://psi-lab.ai/Agent-Driver/  
LLM 当驾驶 agent，不是一条视觉大网。

```text
感知结果（已做好的检测/预测）
  → 工具库（function call 查地图、预测、占用）
  → 认知记忆（常识 + 经验）
  → 推理引擎（CoT：任务规划 / 运动规划 / 自反思）
    → 轨迹
```

和 packing-agent 同构的是 **工具约束 + 推理**。和 5212 同构的是 **模型不直接碰执行 ID**。

差别：他们在 nuScenes 上出 **自车轨迹**；你在 SUMO 上出 **语义意图**（方向 + 秒数），代码再接地到边/信号灯。

---

## 3. CE5212（你真实做的）

```text
SUMO 边状态（占用、速度、停车数）
  → 边 ID 先译成方向标签（east_to_cbd / exit_ramp …）
    → Coordinator：LLM 或规则，同一 JSON 意图
      → apply / ground：方向 → 边 ID → 延绿 / 调度占位
        → 对照：B（LLM）vs B_RULE（规则）vs A（不干预）
```

失败再改（可讲 30 秒）：4B 模型直接吐 TraCI ID 会抄 schema 里的 `"str"`，调用变空操作。改成语义意图后，幻觉被挡在接地层。

强规则若阈值太低：AV 喂给调度爆炸，公交被挤掉（856 次调度、到达 −32%）。抬触发 + 冷却后，到达从 2232 回到 3066（对照 A=3291）。这是 **评测/控制门禁**，不是规划器。

---

## 4. 一张有/无表

| 能力 | UniAD | Agent-Driver | CE5212 | packing-agent |
|------|-------|--------------|--------|---------------|
| 多相机 BEV | 有 | 通常吃现成感知 | 无 | 无 |
| 自车轨迹 | 有 | 有 | 无 | 无 |
| 工具 / function call | 弱（端到端） | 有 | 弱（固定意图槽） | 有（白名单 tools） |
| 记忆 | 隐式 | 有 | 规则冷却 / persona 短记忆 | 会话 + HITL |
| 执行接地 | 网络直接出规划 | 工具+规划头 | **有（方向→边 ID）** | **有（LLM 不写几何）** |
| 对照基线 | 论文表 | 论文表 | **A / 规则 / LLM 同执行层** | 影子 KPI |
| 闭环 | 开环为主；B2D 才闭环 | 开环场景为主 | SUMO 微观，非车端 | 装箱域 |

---

## 5. 开口句（按岗位换）

**智驾评测 / 工具链：**  
「我认同 NAVSIM 那种乘子否决。我在走廊仿真里做的是同一执行层上比规则和 LLM，并记录 proposed vs applied。」

**智驾产品 / Agent：**  
「Agent-Driver 用工具库；我这边是意图槽 + 代码接地。packing-agent 把同一原则做到可演示产品。」

**端到端 / VLA / 世界模型：**  
「我读过 UniAD 任务图和 NAVSIM 指标，代码仓是协调器不是 BEV 规划。预期这岗偏冷。」
