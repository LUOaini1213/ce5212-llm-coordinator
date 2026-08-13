# 面试卡 · NAVSIM / Bench2Drive 指标（3 分钟）

来源：官方 docs，不是二手总结。  
- NAVSIM v1 PDMS：https://github.com/autonomousvision/navsim/blob/v1.1/docs/metrics.md  
- NAVSIM v2 EPDMS：https://github.com/autonomousvision/navsim/blob/master/docs/metrics.md  
- Bench2Drive：https://github.com/Thinklab-SJTU/Bench2Drive  

和你的课设差一层：**这些是自车 4 秒轨迹评测**。你的 CE5203/5212 是路网/出行对照。面试用同一套「开环会骗分、对照才算数」的话，不要说你跑过 NAVSIM。

---

## 一句话

开环 L2（轨迹离专家多远）几乎不能说明车能不能开。NAVSIM 用 **乘子罚碰撞/驶出可行驶区**，再加权进度、碰撞时距、舒适。Bench2Drive 改成 **CARLA 闭环**，看 Driving Score、成功率、分能力，后来又加了效率和平顺。

---

## NAVSIM v1 · PDMS

4 秒非反应仿真：背景车走录好的未来轨迹，自车用 LQR 跟踪规划。

| 符号 | 中文 | 角色 | 取值 |
|------|------|------|------|
| NC | 无主责碰撞 | **乘子** | 0 / 0.5 / 1 |
| DAC | 可行驶区合规 | **乘子** | 0 / 1 |
| TTC | 碰撞时距在界内 | 权重 5 | 0 / 1 |
| EP | 自车进度 | 权重 5 | [0, 1] |
| C | 舒适 | 权重 2 | 0 / 1 |
| DDC | 行驶方向合规 | v1 **权重 0，不算分** | 0 / 0.5 / 1 |

官方公式：

`PDMS = NC × DAC × (5·TTC + 5·EP + 2·C) / 12`

背这个就够：撞了或开出路面，后面分再高也接近 0。

---

## NAVSIM v2 · EPDMS

多了乘子 DDC、TLC（红绿灯）；加权多了 LK（车道保持）、HC（相对历史舒适）、EC（相邻帧动力学一致）。

`EPDMS = (NC·DAC·DDC·TLC 经 human filter) × 加权(TTC, EP, HC, LK, EC)`

**human filter：** 人类专家在同一场景也违规，则该项不罚智能体。避免「必须借对向超静止障碍」被冤枉。

v2 还有两段伪闭环：第一段 4 秒打分；第二段在若干预滚出的后续场景上再打分，按终点靠近程度加权，再和第一段相乘。比真闭环便宜，比纯开环狠。

---

## Bench2Drive · 闭环

CARLA 0.9.15，220 条路线。官方点名：**不要再拿 nuScenes 开环规划当证据**（2025-02-05 README）。

主指标：Driving Score、Success Rate。能力维：汇入、超车、红绿灯等（以当前 `ability_benchmark.py` 为准）。v0.0.2 起加 Driving Efficiency、Driving Smoothness；Drive Score 去掉最低车速罚，TickRunTime 2000→4000。

坑（面试加分）：UniAD/VAD 评测 agent 后相机外参曾写错；能力维公式有过 typo。所以「论文表」和「你自己跑」可能对不上。

---

## 对照你的实验（诚实）

| 他们 | 你 |
|------|----|
| 自车轨迹 4s / CARLA 闭环 | SUMO 路网控制或出行方式 |
| NC×DAC 一票否决 | 5212：规则 vs LLM 同一执行层 |
| 开环 L2 不信 | 5203：路段内 VSL 单独用往往更差 |
| human filter | 你还没有「专家也违规则不罚」 |

可说：我认同评测要有硬否决和对照执行层。不能说：我的 PDMS 是多少。
