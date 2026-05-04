# BW指数: 人类七情六欲量化建模与分析系统

![Field](https://img.shields.io/badge/BFFLS-blue) ![Version](https://img.shields.io/badge/version-0.0.1-green) ![Last Commit](https://img.shields.io/github/last-commit/WYC999999/BFFLS-OSR) ![Repo Size](https://img.shields.io/github/repo-size/WYC999999/BFFLS-OSR) ![Stars](https://img.shields.io/github/stars/WYC999999/BFFLS-OSR?style=social) ![Forks](https://img.shields.io/github/forks/WYC999999/BFFLS-OSR?style=social)

## 1. 简介 (Introduction)

**BW指数 (Biological & Will Index)** 是一种用于衡量人类“心理-生理”综合驱动力的数字化指标。它通过捕获个体在特定时间内“七情”与“六欲”的波动强度，利用加权整合算法生成一个反映生命活跃度与意志张力的综合指数。

本系统不仅支持宏观的**全天综合指数**，也支持**微观瞬时指数**，并允许通过调整参数来提取单一情感或欲望对整体状态的影响力（含参子指数）。

---

## 2. 理论框架 (Theoretical Framework)

BW指数将人的内在驱动力分为两个核心维度，并对每一项进行 $[0, 10]$ 的强度赋值：

### 2.1 七情分量 (The Seven Emotions Vector, $E$)
反映个体的心理情感状态：
* $e_1$ (喜 - Joy): 正向激励强度
* $e_2$ (怒 - Anger): 防御与攻击能量
* $e_3$ (哀 - Sorrow): 能量回收与沉溺度
* $e_4$ (惧 - Fear): 风险规避敏感度
* $e_5$ (爱 - Love): 链接与共鸣强度
* $e_6$ (恶 - Loathing): 排斥与厌恶度
* $e_7$ (欲 - Desire): 获取目标的心理冲动

### 2.2 六欲分量 (The Six Desires Vector, $D$)
反映个体的生理感知与外界反馈：
* $d_1$ (眼 - Vision): 视觉审美与观测欲
* $d_2$ (耳 - Hearing): 听觉刺激需求
* $d_3$ (鼻 - Smell): 嗅觉环境反馈
* $d_4$ (舌 - Taste): 味觉摄取欲望
* $d_5$ (身 - Touch): 触觉、舒适度与躯体欲望
* $d_6$ (意 - Thought): 意识层面的纯粹思维欲



---

## 3. 数学建模 (Mathematical Modeling)

### 3.1 瞬时 BW 指数 ($BW_t$)
瞬时指数反映 $t$ 时刻的爆发状态，公式如下：

$$BW(t) = \sigma \left( \sum_{i=1}^{7} w_i e_i(t) + \sum_{j=1}^{6} v_j d_j(t) \right) \times 10$$

其中：
* $w_i, v_j$ 是权重系数，默认配置下 $\sum w = 6, \sum v = 4$（侧重心理影响）。
* $\sigma$ 是归一化算子，确保结果处于 $[0, 100]$。

### 3.2 全周期（日均）BW 指数 ($BW_{day}$)
反映一整天的能量分布均衡度。采用积分均值法：

$$BW_{day} = \frac{1}{T_{24}} \int_{0}^{T_{24}} BW(t) \cdot \lambda(t) \, dt$$

* $\lambda(t)$ 为**时间权重函数**，例如深夜时段（睡眠）的权值较低，而工作/活跃时段权值较高。

### 3.3 含参子指数 ($BW_P$)
用于观察某一特定因子（如“愤怒”）在系统中的占比，称为 **$\theta$-感官指数**。
设目标因子为 $x$，其对 BW 的贡献系数为 $P$：

$$BW_P(x) = \frac{\partial BW}{\partial x} \cdot \frac{x}{BW}$$

---

## 4. 值域与分级标准 (Standard Ratings)

BW指数标准值域为 **0 - 100**，根据数值大小划分为五个层级：

| 指数区间 | 等级名称 | 状态特征 | 建议策略 |
| :--- | :--- | :--- | :--- |
| **0 - 20** | **寂灭期 (Quiescence)** | 极低波动，情感剥离，生理机能处于休眠或极度抑制状态。 | 需补充能量，警惕抑郁倾向。 |
| **21 - 45** | **恒常期 (Stasis)** | 情绪平稳，欲望较低。典型的工作或深度思考状态。 | 适合处理逻辑性强的事务。 |
| **46 - 65** | **活跃期 (Vibrance)** | 情感丰富，感知敏锐。生活气息浓厚。 | 适合社交、创作与艺术体验。 |
| **66 - 85** | **激荡期 (Turbulence)** | 欲望强烈或情绪剧烈波动，决策可能受到感性主导。 | 宜采取行动，但需注意风险把控。 |
| **86 - 100** | **超限期 (Surge)** | 极度亢奋、狂热或极度痛苦。处于意志力的临界点。 | 需通过静心或物理手段强制冷却。 |

---

## 5. 简单 BW 指数 (Simplified BW, SBW)

为了实现快速自我评估，我们简化了复杂的积分公式，采用“三维加权法”。用户只需对以下三个维度进行打分（1-10分）：

1.  **情感张力 ($E_{score}$):** 此时此刻你的情绪波动是大还是小？
2.  **生理冲动 ($D_{score}$):** 此时此刻你对进食、感官刺激或肉体舒适的渴望程度？
3.  **意志专注度 ($W_{score}$):** 你在多大程度上受这些情感/欲望的支配？

### 快速计算公式：
$$SBW = (E_{score} \times 4) + (D_{score} \times 3) + (W_{score} \times 3)$$

**示例：**
* 小明感到很愤怒 (E=8)，很想吃东西 (D=9)，但理性告诉他要忍住，意志力高度集中 (W=9)。
* $SBW = (8 \times 4) + (9 \times 3) + (9 \times 3) = 32 + 27 + 27 = 86$
* **评级：** 超限期。

---

> **Warning**
> BW 指数属于社会科学与行为数学模型，仅供自我了解与科研参考，不作为医学诊断依据。
