# 多 AI 协作信息同步板 (AI_SYNC)

> 本文件是**所有 AI 共用的当前状态入口**。任何人接手这个工程，先读这里，再按「上手顺序」读其他文档。
>
> ```text
> 项目根目录：D:\stm32\stm32f4\breath
> Keil 工程目录：D:\stm32\stm32f4\breath\breathing
> 协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
>   ├─ AI_SYNC.md（本文件）/ AI_WORKLOG_WORKBUDDY.md / CHANGELOG.md / README.md
>   ├─ DISPATCHES\STAGE_01\（派单 01~03）
>   └─ ACCEPTANCE\STAGE_01.md（阶段 1 验收记录）
> ```
>
> 工程：STM32F407VET6 / Keil MDK-ARM / CubeMX
> 建立：2026-11-18 14:31 by WorkBuddy ｜ 流程规则更新：14:42 ｜ 公式纠错与裁决项更新：15:15 ｜ 派单 01 收口：22:04 ｜ 轮径回填补充收口：22:14 ｜ PID 周期裁决：11-19 20:20（方案 A）｜ 阶段 1 收口：11-19 21:14 ｜ 目录规范化：11-20 16:25（迁入 AI_COLLAB）｜ **阶段 1 正式交付：11-20 16:31（200 RPM 核定）**

---

## 0. 怎么用这个文件（重要）

| 区块 | 谁能改 | 规则 |
|---|---|---|
| §2 当前状态快照 | **仅 WorkBuddy** | 其他 AI 不要直接改；有变化就在 §6 广播，由 WorkBuddy 更新 |
| §3 协作流程与分工 | **仅人类用户裁定** | WorkBuddy 负责把裁定原文写进来，其他 AI 遵守，不自行改流程 |
| §4 文件占用登记 | 所有 AI | **动手改任何文件前先登记一行**，完成后把状态改成「已完成」 |
| §5 待办与认领 | 所有 AI | 认领时写 AI 名；不要静默开工 |
| §6 广播 / 交接流水 | 所有 AI | **只追加，不修改、不删除历史行** |
| §7 存疑与待裁决 | 所有 AI | 提出疑问；日常由 WorkBuddy 分析 + 人类拍板，架构级争议留到阶段末交 Codex/MiMo |

广播行格式（固定，方便别人一眼扫）：

```text
- YYYY-MM-DD HH:MM | AI名 | 一句话事实或结论 | 涉及文件 | 需谁跟进
```

**单一真相源约定**：

- 代码最终状态 → 以 `Core/Src/*.c` + `breathing.ioc` 为准（文档与代码冲突时，**以代码为准**）。
- 代码改动历史 → `AI_COLLAB/CHANGELOG.md`（每次改动必须追加：日期 + 改了什么 + 涉及文件 + 是否需动 CubeMX）。
- 此刻的协作状态 → 本文件 §2。
- **协作流程与分工 → 本文件 §3（用户 2026-11-18 裁定，优先级最高）**。
- 架构 / 阶段计划 / 安全底线 / 标准任务单 → `breathing/docs/PROJECT_OVERVIEW.md`（由 **Codex 接 MiMo** 维护总览）。
  ⚠️ 该文件 §6 的旧 AI 分工表**已过时**（把 WorkBuddy 写成纯助理、把 Codex 写成日常总工），以 §3 为准；待 Codex/MiMo 阶段末做版本规划时同步更新。
- 阶段 1 功能要求与验收 → `breathing/docs/TASK_STAGE_01_PID.md`。
- WorkBuddy 自己的工作流水 → `AI_COLLAB/AI_WORKLOG_WORKBUDDY.md`（不放公共状态）。

---

## 1. 新加入的 AI：60 秒上手顺序

```text
0. AI_COLLAB/README.md（目录索引与文件职责）
1. AI_COLLAB/AI_SYNC.md（本文件）§3 协作流程 → §2 当前状态快照 → §4 文件锁 → §6 最近广播 → §7 待裁决
2. AI_COLLAB/CHANGELOG.md（只看最后 2～3 个日期段，了解最近改了什么）
3. breathing/docs/PROJECT_OVERVIEW.md（架构、阶段计划、安全底线；§6 旧分工表以本文件 §3 为准）
4. breathing/docs/TASK_STAGE_01_PID.md（当前阶段任务单：允许/禁止修改的文件）
5. 若领派单：AI_COLLAB/DISPATCHES\STAGE_xx\ 下对应派单全文
6. 再打开实际源码：Core/Src/control.c → encoder.c → motor.c → pid.c → main.c
```

**所有任务和报错从 WorkBuddy 起手**（§3）。别的 AI 不要绕过起点直接开工；接到派单后按派单里限定的文件范围干活。

开工前确认三件事：**当前有没有人在改同一个文件**（§4）、**这个文件在不在任务单的禁止列表里**、**改动是否需要动 CubeMX**。

**文件名约定**：工程实际是 `pid.h/.c` 与 `control.h/.c`；任务单里的 `motor_pid.h/.c` 不存在，派单一律用实际文件名。

---

## 2. 当前状态快照

> 由 WorkBuddy 维护。核对时间：**2026-11-19 21:14**（派单 03 已落地，源码为 11-19 21:12 安全基线版）。
> **派单 01 已验收完成**：编码器测速夯实 + 里程计基础，22:01 编译、人类实车确认通过；详见 `AI_COLLAB/CHANGELOG.md` 2026-11-18 节与 §6 广播。
> **15:15 纠错**：WorkBuddy 曾误判 `encoder.c` 的 `speed_rpm` 公式「差 1000 倍」，实际公式正确；收口核对确认公式**逐字未改**，只补了注释。见 §7 第 8 条。

### 进度

| 项 | 状态 |
|---|---|
| 当前阶段 | ✅ **阶段 1 正式交付完成**（11-20 16:31），待移交 Codex 做总览与阶段 2 规划 |
| 已完成 | 四路 PWM + 方向控制、编码器与轮径标定、PWM 串扰治理、1 ms 闭环 PID、开环标定、KP/KI 整定、阶跃验证 |
| 未开始 | 阶段 2 底盘运动学、阶段 3 通信与安全、云台 / 视觉 / 发射 / 导航 |
| 阶段 1 遗留 | 落地 200 RPM 长时间直行对比、上位机指令测试（并入阶段 2）；400 RPM 测试点裁决（§7 第 10 条） |

### 关键事实（已与代码逐项核对）

| 项 | 值 | 出处 |
|---|---|---|
| 编码器分辨率 | `1320` 计数/圈，四路共用（11 线 × 4 倍频 × 30:1） | `Core/Src/encoder.c` |
| **底盘轮型** | **普通轮子**（非麦克纳姆、非全向轮），四轮独立驱动 → 差速底盘（skid-steer）；无独立侧移（vy=0），斜行只能靠转向+前进组合近似 | 人类 11-20 确认 |
| 编码器方向 | 四路 `direction = +1`；M3/M4 在 `motor.c` 中 IN1/IN2 对调 | `encoder.c` / `motor.c` |
| 抗干扰 | 8 个编码器脚内部上拉；TIM2~5 `ClockDivision=DIV4`、`IC1/IC2Filter=15`；`.ioc` 已同步 | `Core/Src/tim.c` / `breathing.ioc` |
| **瞬时速度公式** | `speed_rpm = delta * 60000.0f / counts_per_rev` —— **正确，不得改动**。推导：`delta` 为 1 ms 计数，每分钟计数 = `delta × 60000`，RPM = 该值 / 1320。验算：60 RPM → 1.32 计数/ms → 代入得 60 | `Core/Src/encoder.c` 第 73-74 行 |
| 控制时序 | **派单 02（11-19）**：`SysTick_Handler` → `Control_Update()` 每 1 ms 完成「读编码器 → 一阶低通滤波 + 零计数保护 → PID → 输出」；100 ms 诊断窗口独立保留 | `stm32f4xx_it.c` / `control.c` |
| 当前运行配置 | **【21:12 安全基线】** `TEST_MODE=0`、`OPEN_LOOP=0`（闭环）、`OPEN_LOOP_DUTY=0`、`TARGET_RPM=0`、PID 周期 **1 ms**、**KP=0.4 / KI=2.5 / KD=0**（实测整定）、LPF alpha=0.20、零计数保护 20 ms、`controlCalibrationMode=0` | `Core/Src/control.c` 顶部调参区 |
| 目标写入接口 | `Control_SetTargetRpm()` / `Control_GetTargetRpm()` / 全局 `motorTargetRpm[0..3]`；滤波速度 `motorSpeedFiltered[0..3]`；标定 `controlCalibrationMode` + `motorOpenLoopDuty[0..3]`；增益 `motorKp/Ki/Kd`；setter：`Control_SetCalibrationMode/SetOpenLoopDuty/SetGains` | `control.h/c` |
| 速度环实测 | 100 RPM 目标 → 四路稳态 96~104（误差 ≤±4%，无超调）；200 RPM 稳住；反转与 60 RPM 低速稳；开环增益约 3.25 RPM/%；**100% 占空比极速实测四路均约 330 RPM** | `AI_COLLAB/ACCEPTANCE/STAGE_01.md`；人类实测 |
| 验收口径 | **正式核定 200 RPM**（人类 11-20 拍板），400 RPM 测试点因硬件上限豁免；阶段 2 目标建议 ≤250 RPM（留 20~25% 余量） | `AI_COLLAB/ACCEPTANCE/STAGE_01.md` §0 |
| OLED 驱动模式 | **已改为**显示四行 M1~M4 的 RPM（1 位小数、带符号）+ 输出占空比（%）；测试模式分支保留 | `Core/Src/main.c` |
| 构建 | **11-19 21:12:48** 生成 `breathing.hex`（37655 bytes），重编 `control.c`，**0 Error / 0 Warning**（Code=10448 / RO=2632 / RW=288 / ZI=3360） | `MDK-ARM/breathing/breathing.build_log.htm` |
| 是否已下载到车 | **是，21:12 安全基线版已烧录并完成实车整定**：开环 20/40/60% 标定、闭环 100/200 RPM 阶跃、反转与 60 RPM 低速均验证通过；最终目标已归零、参数固化为 0.4/2.5/0 | 人类 21:14 确认 |
| 里程计 | 已加 `Encoder_GetDistanceM()` / `Encoder_ResetOdometry()` / `Control_GetDistanceM()`；`WHEEL_DIAMETER_M=0.066404f` 已由 1 m 实推标定填入（均值 6327.5 脉冲/米 → 轮径 66.404 mm，WorkBuddy 验算一致），距离读数现有效 | `encoder.h/c`、`control.h/c`；`AI_COLLAB/CHANGELOG.md` 22:14 节 |
| PID 实现 | 位置式，`PID_Compute()` 输出 ±100 限幅、微分先行、条件积分抗饱和 | `Core/Src/pid.c` |

**上电安全性**：当前是开环且 `DUTY=0`，车不会动。目标值虽为 60 RPM，但未生效；**一旦切 `CONTROL_OPEN_LOOP=0`，会立即尝试跑到 60 RPM**。切闭环前必须把 `TARGET_RPM` 归零，或由人类现场写入目标速度 —— 见 §7 第 2 条与派单 01 §12.2。

### 硬件映射（速查，完整版见 PROJECT_OVERVIEW §3，冲突以 `.ioc` 为准）

| 电机 | PWM | IN1 | IN2 | 编码器 |
|---|---|---|---|---|
| M1 | PE9 / TIM1_CH1 | PE0 | PE1 | TIM3 / PA6 / PA7 |
| M2 | PE11 / TIM1_CH2 | PE2 | PE3 | TIM4 / PD12 / PD13 |
| M3 | PE13 / TIM1_CH3 | PE4 | PE5 | TIM5 / PA0 / PA1 |
| M4 | PE14 / TIM1_CH4 | PE6 | **PE7** | TIM2 / PA5 / PB3 |

其他：PB6/PB7 = I2C1 OLED；PA13/PA14 = SWD；PH0/PH1 = HSE。TIM1 PWM 周期 8399（约 20 kHz）。

---

## 3. 协作流程与分工（2026-11-18 14:42 用户裁定，覆盖 PROJECT_OVERVIEW §6）

> 这是当前**唯一有效的流程定义**。旧分工表把 WorkBuddy 定为纯项目助理、把 Codex 定为日常总工，已被本裁定取代。

### 3.1 任务流转链

```text
人类提出任务 / 报错 / 异常现象
        ↓
① WorkBuddy（起点，必须从这里开始）
   · 读 AI_SYNC 状态 + CHANGELOG + 相关源码，核对当前事实
   · 分析错误、定位原因、拆解任务、评估影响文件
   · 登记 §4 文件锁、更新 §5 待办
   · 产出派单：Gemini 反重力代码提示词（含任务目标、允许/禁止文件、验收标准、安全要求）
        ↓
② Argon4（主力，代码实现）
   · 按派单提示词编写 / 修改代码，不越出限定文件范围
   · 结果回传 WorkBuddy
        ↓
③ WorkBuddy（收口）
   · 核对改动、更新 §2 快照 + §6 广播、追加 CHANGELOG 记录、整理测试记录
        ↓
④ 人类（编译 / 下载 / 实车验证 / 最终放行）
        ↓
⑤ 一个阶段做完后 → Codex 接 MiMo 做总览与版本规划
```

**无特殊情况，① WorkBuddy + ② Argon4 就是主力**，日常编码不拉其他模型进来。

### 3.2 角色表

| 角色 | 定位 | 什么时候用 |
|---|---|---|
| **WorkBuddy** | **任务起点 + 错误分析 + 派单 + 记录收口；主力之一** | 每个任务、每次报错，一律从这里起手；维护 `AI_COLLAB/AI_SYNC.md` §2/§5/§6/§7 |
| **Argon4** | **代码实现主力** | 接到 WorkBuddy 的「Gemini 反重力代码提示词」派单后写码 |
| Gemini 反重力代码提示词 | **派单载体**（不是独立角色） | 由 WorkBuddy 产出、直接交由 Argon4（反重力）执行的写代码提示词；固定模板格式待用户提供 |
| Chat 网页模型 | 资料搜集 + 部分代码 / 算法解读分析 | 分析阶段按需辅助，不进入主力链路 |
| **Codex 接 MiMo** | **总览 / 版本规划**（`PROJECT_OVERVIEW.md` 归他） | **一般做完一个阶段才介入**，做版本规划与整体规划；不参与日常排错和实现 |
| Claude 接 DeepSeek | token 不足时的接力 | **仅当 token 不足**，由用户决定是否启用；不是默认链路 |
| 人类用户 | 硬件负责人 + 流程裁定者 | 接线、实车测试、现象确认、最终放行；也是 token 不足时切换接力的开关 |

### 3.3 触发条件速查

| 情况 | 谁上手 |
|---|---|
| 新任务 / 编译报错 / 实车异常 | **WorkBuddy 先分析** → 派单给 Argon4 |
| 日常写代码、改 `.c/.h` | Argon4（WorkBuddy 收口记录） |
| 查资料、读数据手册、解读算法 | Chat 网页模型（WorkBuddy 按需调用） |
| 架构 / 引脚 / 定时器 / CubeMX 级争议 | 先由 WorkBuddy 记录进 §7，**阶段末**交 Codex 接 MiMo 裁决 |
| 阶段完成、版本规划、总览更新 | Codex 接 MiMo |
| token 不足 | 用户切 Claude 接 DeepSeek |
| 实车验证、放行 | 人类 |

### 3.4 派单最低要求（沿用 PROJECT_OVERVIEW §9 标准任务单）

```text
目录约定（项目根 / Keil 工程 / 协作文档）
任务目标 / 允许修改文件 / 禁止修改文件 /
硬件约束 / 控制周期 / 当前代码状态（引用 AI_SYNC §2） /
安全要求 / 验收标准 / 测试方法 / 回传要求 / 待裁决项
```

派单里必须显式带上：阶段 1 任务单的允许 / 禁止文件清单（**用实际文件名** `pid.h/.c`、`control.h/.c`，不是任务单里的 `motor_pid.h/.c`）、上电默认停车、输出与积分限幅、不得在 PID 循环用 `HAL_Delay`。

---

## 4. 文件占用登记（动手前先登记）

> 规则来自 PROJECT_OVERVIEW §7：**同一个文件同一时间只能有一个模型修改**。
> 登记格式：`时间 | AI | 文件 | 目的 | 状态(进行中/已完成)`。

| 时间 | AI | 文件 | 目的 | 状态 |
|---|---|---|---|---|
| 2026-11-18 14:57 | Argon4 | `Core/Inc/encoder.h`、`Core/Src/encoder.c`、`Core/Inc/control.h`、`Core/Src/control.c`、`Core/Src/main.c` | 派单 01：补速度字段注释、OLED 显 RPM+占空比、时序注释、里程计接口；22:12 回填实测轮径 | ✅ **已完成并关闭**（派单 01 全部验收通过） |
| 2026-11-19 20:20 | Argon4 | `Core/Inc/control.h`、`Core/Src/control.c` | 派单 02：1 ms PID（方案 A）+ LPF/零计数保护 + 目标归零后切闭环 + Watch 目标接口 | ✅ **已完成**（20:33 编译 0E/0W，人类实车初步验证通过；20:35 WorkBuddy 收口） |
| 2026-11-19 20:38 | Argon4 | `Core/Inc/control.h`、`Core/Src/control.c` | 派单 03：Watch 可写标定开关/占空比/增益 + 实车整定 KP=0.4/KI=2.5 + 安全基线固化 | ✅ **已完成**（21:12 编译 0E/0W，实车验证通过；21:14 WorkBuddy 收口） |
| 2026-11-18 14:57 | WorkBuddy | `AI_COLLAB/AI_SYNC.md`、`AI_COLLAB/AI_WORKLOG_WORKBUDDY.md`、`AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md` | 起点分析 + 出派单；15:15 纠错修订；22:04 收口记录 | 已完成 |

> **授权例外**：阶段 1 任务单原禁止改 `encoder.c`；本次由人类用户 2026-11-18 14:57 明确授权，仅限派单 01 范围，改完须在 `AI_COLLAB/CHANGELOG.md` 注明授权来源。Argon4 动手前请在本表确认无其他占用。

阶段 1 任务单的文件范围（**跨阶段前一直有效**）：

```text
任务单原文允许：Core/Inc/motor_pid.h、Core/Src/motor_pid.c、Core/Src/main.c、MDK-ARM/breathing.uvprojx
任务单原文禁止：breathing.ioc、Core/Src/tim.c、Core/Src/motor.c、Core/Src/encoder.c、
                Core/Src/gpio.c、Core/Inc/main.h

实际工程文件名：Core/Inc/pid.h、Core/Src/pid.c、Core/Inc/control.h、Core/Src/control.c
```

⚠️ 任务单里的 `motor_pid.h/.c` 在工程里**不存在**；派单中一律使用实际文件名，避免 Argon4 找不到文件。见 §7 第 4 条。

---

## 5. 待办与认领

| # | 事项 | 归属 | 认领 | 状态 |
|---|---|---|---|---|
| 1 | 更正 CHANGELOG「当前源码尚未编译」的过时记录（追加更正，不改历史原文） | WorkBuddy | WorkBuddy | 待办 |
| 2 | **派单 01**：编码器测速夯实 + 里程计基础（W1 仅补注释、OLED 显 RPM+占空比、时序注释、里程计接口） | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（22:01 编译 0E/0W，人类实车确认；详见 `AI_COLLAB/CHANGELOG.md`） |
| 2a | 提供**实测轮径（米）**：1 m 直推标定完成，均值 6327.5 脉冲/米 → 轮径 66.404 mm，已填入 `WHEEL_DIAMETER_M=0.066404f`（WorkBuddy 验算一致） | 人类 | 人类 | ✅ **已完成**（22:12） |
| 2a-1 | **22:12 最终版 hex 上电确认**：含实测轮径 + RPM/% 画面，看一眼 OLED 正常即可 | 人类 | 未认领 | 待办 |
| 2b | 派单 01 验收：Build 结果、OLED 四行显示、四路 RPM 符号一致性、**W1 公式未被改动**、Watch 变量 | 人类实车 + WorkBuddy 记录 | 人类/WorkBuddy | ✅ **已通过**（22:04；W1 逐字未改、符号一致、禁止文件未动） |
| 2c | **裁决 PID 周期方案**（A/B/C，见 §7 第 1 条）：不许实现模型自定 | 人类 / Codex | 人类 | ✅ **已裁决：选 A（1 ms PID）**，11-19 20:20 |
| 2a-2 | 22:12 版上电看 OLED | 人类 | 人类 | ✅ **已勾掉**（11-19：画面与已确认的 22:01 版一致，轮径不影响 OLED，1 m 直推时已烧录验证） |
| 2d | **派单 02**：按方案 A 实现 1 ms PID + **闭环前 `TARGET_RPM` 归零** + 1 ms 窗口测速抗噪声保护 | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（20:35 收口；实车初步验证通过） |
| 2e | **派单 03**：开环占空比→RPM 标定 + KP/KI 整定 + 四轮阶跃测试验收 | WorkBuddy 出派单 / Argon4 实现 + 人类实车 | Argon4 / 人类 | ✅ **已完成**（21:12 安全基线，实车验证通过；21:14 收口） |
| 3 | 开环标定：`OPEN_LOOP_DUTY=20/40/60`，记录四路稳态 RPM，得到占空比→转速曲线（并入派单 03） | 人类实车 + WorkBuddy 记录 | 未认领 | 并入 2e |
| 4 | 定 KP/KI（先 Ki=0 加 Kp，再加 Ki 消稳态误差）；注意 dt 已从 0.1→0.001，参数需重新整定（并入派单 03） | WorkBuddy 分析数据 + Argon4 改 | 未认领 | 并入 2e |
| 5 | 按任务单做四轮阶跃测试（0→200/400 RPM、400→0、正反转、四轮一致性）并出验收记录（并入派单 03） | 人类实车 + WorkBuddy 记录 | 未认领 | 并入 2e |
| 6 | 裁决 400 RPM 超限：100% 实测极速约 330 RPM，**正式按 200 RPM 核定验收** | 人类 | 人类 | ✅ **已裁决**（11-20 16:31）；任务单修订交 Codex 阶段末 |
| 7 | **移交 Codex 接 MiMo**：总览更新（§6 分工表同步）+ 任务单 400→200 RPM 修订 + 阶段 2 规划 | Codex 接 MiMo | 阶段末 | **下一步**（移交单已备好，见 `AI_COLLAB/HANDOFF_TO_CODEX_STAGE_02.md`） |
| 8 | 落地 200 RPM 长时间直行对比测试（架空已验，落地未做） | 人类实车 | 未认领 | 遗留（可并入阶段 2 联调） |
| 9 | 外部上位机下发指令测试 | 人类 + Argon4 | 未认领 | 遗留（阶段 2 联调） |

> 每次 Keil Build + 下载的结果、每组实车数据，请**同时**在 §6 广播一行，并把详细数据交给 WorkBuddy 整理成测试记录。

---

## 6. 广播 / 交接流水（只追加）

```text
- 2026-11-17 22:09 | Keil/人类 | 重新构建：重编 encoder.c + control.c，0 Error / 0 Warning，breathing.hex 已更新 | MDK-ARM/breathing/ | WorkBuddy 更正 CHANGELOG
- 2026-11-18 10:31 | WorkBuddy | 通读工程（只读，未改任何文件），建立状态理解；发现 3 处文档/任务单与代码不一致 | 无 | 见 §7
- 2026-11-18 14:31 | WorkBuddy | 新建 AI_COLLAB/AI_SYNC.md 与 AI_COLLAB/AI_WORKLOG_WORKBUDDY.md，确立协作同步机制 | AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 全体 AI 按 §0 使用
- 2026-11-18 14:42 | 人类用户 | 裁定新协作流程：任务与报错一律从 WorkBuddy 起手 → 派单给 Argon4 写码；两者为主力；Codex 接 MiMo 只做阶段末总览与版本规划；Chat 网页模型做资料与算法解读；token 不足时才由用户切 Claude 接 DeepSeek | AI_COLLAB/AI_SYNC.md §3、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 全体 AI 遵守 §3
- 2026-11-18 14:57 | 人类用户 | 裁定下一阶段先做「测速夯实 + 里程计基础」再接 PID；授权本次改 encoder.c（任务单例外，仅限派单 01） | AI_COLLAB/AI_SYNC.md §4/§5 | WorkBuddy 出派单
- 2026-11-18 14:57 | WorkBuddy | 起点分析完成，产出派单 01（当时对 speed_rpm 公式的判断有误，见 15:15 更正） | AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md | 已被 15:15 修订覆盖
- 2026-11-18 15:06 | 人类用户 | 澄清「Gemini 反重力代码提示词」= WorkBuddy 产出、直接粘进反重力执行的写代码提示词；WorkBuddy 给出可直接复制的提示词全文 | 会话内 | 固定模板格式仍待提供
- 2026-11-18 15:15 | 人类用户/Codex | **纠错**：WorkBuddy 误判 `encoder.c` 的 `speed_rpm` 公式差 1000 倍；实际公式正确（60000 已含 60×1000）。要求 W1 改为「保留公式 + 补注释」，并把 PID 周期冲突列为正式待裁决（A/B/C 三方案）、统一实际文件名、闭环前目标归零、区分根目录与 Keil 目录 | AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | WorkBuddy 已修订派单 01 与同步板
- 2026-11-18 15:15 | WorkBuddy | 修订派单 01：W1 改为保留公式仅补注释 + 新增 W1 回归检查；§12 加入 PID 周期三方案与闭环前目标归零；统一目录约定与实际文件名 | AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md | Argon4 必须按 15:15 修订版执行
- 2026-11-18 21:51~22:01 | Argon4/反重力 | 按修订版派单 01 改完 5 个文件：W1 仅补注释（公式逐字未改、无 0.001f）、OLED 改显 RPM+占空比、control.c 补时序注释、里程计接口 + 轮径占位宏 | encoder.h/c、control.h/c、main.c | Keil 22:01 Build 0 Error / 0 Warning，新 hex
- 2026-11-18 22:04 | 人类用户 | 实车确认派单 01 通过：上电静止车不动、OLED 四行 `0000.0 RPM  000%`；手推前进四路正 RPM、后拉负 RPM、停稳回零 | 烧录 22:01 的 breathing.hex | 允许 WorkBuddy 收口
- 2026-11-18 22:04 | WorkBuddy | 收口：逐项核对源码（W1 公式未改、所有宏数值未变、禁止文件时间戳未动）+ 追加 CHANGELOG + 更新本文件 §2/§4/§5 | AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 阶段 1 待裁决项仍挂起
- 2026-11-18 22:12 | Argon4/反重力 | 1 m 实推标定完成（M1=6283/M2=6338/M3=6310/M4=6379，均值 6327.5 → 轮径 66.404 mm）；回填 WHEEL_DIAMETER_M=0.066404f，重编 control.c + encoder.c | Core/Inc/encoder.h、Core/Src/control.c | 22:12:13 新 hex，0 Error / 0 Warning
- 2026-11-18 22:14 | WorkBuddy | 补充收口：独立验算轮径（6327.5/1320→208.613 mm 周长→66.404 mm，与填入值一致）；复核 W1 公式未动、安全宏未变、禁止文件未动；追加 CHANGELOG 22:14 节并更新本文件 §2/§4/§5/§7/§9 | AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 22:12 版 hex 仍待人类上电确认
- 2026-11-19 20:20 | 人类用户 | 裁决 PID 周期口径：选 **A（改成 1 ms PID）**，否决 B（明确 100 ms）与 C（20 ms 折中）；WorkBuddy 已提示 1 ms 量化噪声风险，人类仍拍板 A | AI_COLLAB/AI_SYNC.md §5 待办 2c / §7 第 1 条 | WorkBuddy 出派单 02，须含抗噪声保护
- 2026-11-19 20:20 | 人类用户 | 勾掉「22:12 版上电看 OLED」（画面与已确认的 22:01 版一致，轮径不影响 OLED，1 m 直推时已烧录验证） | AI_COLLAB/AI_SYNC.md §5 待办 2a-2 | 派单 01 全部关闭
- 2026-11-19 20:20 | WorkBuddy | 核对今日无新改动（源码/hex 仍停在 11-18 22:12）；更新 §2 核对时间、§5 待办 2c/2a-2 完成、2d 转下一步、§7 第 1 条改为已裁决 A 并写明抗噪声强制要求 | AI_COLLAB/AI_SYNC.md | 下一步：出派单 02
- 2026-11-19 20:22 | 人类用户 | 问「要不要开中断（周期）」；WorkBuddy 判定：沿用现有 SysTick（已 1 ms 调 `Control_Update()`），**不开新定时器中断** —— 新开 TIM6 等需改 `.ioc`/`tim.c`，属任务单禁止文件，且现有 SysTick 已足够 | AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_02_PID_1MS.md W1、AI_COLLAB/AI_SYNC.md §7 第 1 条 | 派单 02 已写死周期来源
- 2026-11-19 20:33 | Argon4/反重力 | 派单 02 落地：control.h/c 实现 1 ms PID + LPF(0.20) + 零计数保护(20 ms) + 目标归零后切闭环 + Watch 目标接口 | Core/Inc/control.h、Core/Src/control.c | 20:33:07 hex，0 Error / 0 Warning
- 2026-11-19 20:35 | 人类用户 | 实车初步确认：上电静止车不动、OLED `0000.0 RPM 000%`；手推前进有明显负反馈阻力、RPM 正且平滑、输出占空比为负，松手回零；未给非零目标 | 烧录 20:33 版 hex | 建议收口并直接进派单 03（开环标定 + 整定）
- 2026-11-19 20:35 | WorkBuddy | 收口：核对源码/编译/禁止文件时间戳；发现 2 处偏差（DUTY 0→20 未报、hex 时间报告不符），均记入 CHANGELOG 与 §7 第 9 条；§2 快照更新为闭环 1 ms 状态、§4 文件锁标完成、§5 派单 02 完成 + 新增 2e、§7 第 2 条标已解决 | AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 下一步：出派单 03
- 2026-11-19 20:38~21:12 | Argon4/反重力 | 派单 03 落地：Watch 可写标定开关/占空比/增益 + 进标定自动归零复位 + 实车整定 KP=0.4/KI=2.5；最终固化安全基线（目标 0、DUTY 0、标定模式 0） | Core/Inc/control.h、Core/Src/control.c | 21:12:48 hex，0 Error / 0 Warning
- 2026-11-19 21:14 | 人类用户 | 实车验收数据：开环 20/40/60% 平稳（增益 3.25 RPM/%、极速 300~340 RPM）；闭环 100 RPM 稳态 96~104（≤±4%、无超调）、200 RPM 稳住、反转与 60 RPM 低速稳；建议进入阶段 1 验收评审并移交阶段 2 | 烧录 21:12 版 hex | 阶段 1 速度环核心完成
- 2026-11-19 21:14 | WorkBuddy | 收口：核对源码仅动 control.h/c、安全基线参数与禁止文件时间戳；追加 CHANGELOG 21:14 节；更新 §2 快照为整定后状态、§4 文件锁、§5 阶段 1 核心完成 + 新增待裁决 6/下一步 7/遗留 8-9、§7 第 9 条闭环 + 新增第 10 条 400 RPM 超限 + 第 11 条遗留 | AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md | 下一步：400 RPM 裁决 + 阶段 1 验收评审 + 交 Codex/MiMo
- 2026-11-20 16:25 | WorkBuddy | 目录规范化：协作文档从项目根迁入 `AI_COLLAB\`，派单按阶段分入 `DISPATCHES\STAGE_01\`，验收记录入 `ACCEPTANCE\STAGE_01.md`，新建 README.md 索引；批量更新全部文档的路径引用 | AI_COLLAB\ 下全部 md | 后续阶段派单放 STAGE_02\，未改任何源码
- 2026-11-20 16:31 | 人类用户 | 补测 100% 占空比：四路最大稳态均约 **330 RPM**，确认 400 RPM 超出硬件上限；**拍板阶段 1 验收上限正式核定 200 RPM**，阶段 2 目标 ≤250 RPM（留 20~25% 余量）；已恢复安全基线 | 烧录 11-20 16:30 hex | 阶段 1 正式交付
- 2026-11-20 16:31 | WorkBuddy | 阶段 1 正式交付：核对安全基线与编译（16:30:21 / 0E/0W）；验收记录改正式版（§0 裁决、100% 极速、400 RPM 豁免、移交）；更新 §2 验收口径、§5 待裁决 6 与下一步 7、§7 第 10 条闭环；产出移交单给 Codex/MiMo | `AI_COLLAB/ACCEPTANCE/STAGE_01.md`、`AI_COLLAB/HANDOFF_TO_CODEX_STAGE_02.md`、CHANGELOG、本文件 | 移交总览与阶段 2 规划
- 2026-11-20 16:43 | 人类用户 | 确认底盘轮型为**普通轮子**（非麦克纳姆/全向）；并要求阶段 2 四个架构问题（里程计精度/IMU、左右轮 10% 标定、通信分级、派单粒度）先与 Codex 对齐颗粒度，不预设结论 | AI_SYNC §2/§7、移交单 §3.3/§3.4 | WorkBuddy 出对齐提示词，Codex 定后出阶段 2 派单
```

---

## 7. 存疑与待裁决（日常由 WorkBuddy 分析 + 人类拍板，架构级留阶段末交 Codex/MiMo）

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | **【已裁决：方案 A】PID 周期口径冲突** —— 人类 2026-11-19 20:20 拍板 **改成 1 ms PID**（任务单口径），否决 B（100 ms）与 C（20 ms 折中） | 1 ms 窗口下 60 RPM 仅 1.32 计数，量化误差 ±76%、低速易读 0；WorkBuddy 已充分提示风险，人类仍选 A | **按 A 实现**，但派单 02 必须强制加抗噪声设计：① 1 ms 原始 delta 做滑动平均/低通后再喂 PID ② 低速零计数保护 ③ 实车重点验低速抖动。若实测无法收敛，回报人类再议，**不得由实现模型自行退回 B/C**。**周期来源：沿用现有 SysTick（已每 1 ms 调 `Control_Update()`），不开新定时器中断、不动 `.ioc`/`tim.c`/`stm32f4xx_it.c`** |
| 2 | **【已解决】闭环切换前目标归零**：派单 02 已把 `TARGET_RPM` 从 60 改为 **0.0f** 后才切 `OPEN_LOOP=0`；实车确认上电静止不跑 | 原违反「上电默认停车」红线，现已满足 | 已闭环。现场通过 `Control_SetTargetRpm()` 或 Watch 写 `motorTargetRpm[]` 给目标 |
| 3 | CHANGELOG 11-17 写「当前源码尚未编译」，但 22:09 有完整构建日志 | 会误导接手者重复编译 / 误判固件 | 追加一条更正，不改历史原文 |
| 4 | 任务单「允许修改 `motor_pid.h/.c`」，工程实际是 `pid.h/.c` + `control.h/.c` | 其他 AI 按任务单会找不到文件、误改或越界 | 派单统一用实际文件名；任务单由 Codex/MiMo 阶段末修订 |
| 5 | 22:09 的 hex 是否已下载到车、实车当前表现 | 所有「已验证」结论的前提 | 人类确认后补一行广播 |
| 6 | `PROJECT_OVERVIEW.md` §6 旧分工表与新流程冲突 | 其他 AI 读旧文档会按旧规则行事 | 以本文件 §3 为准；阶段末由 Codex 接 MiMo 更新总览 |
| 7 | **【已闭环】** 里程计轮径：1 m 实推标定均值 6327.5 脉冲/米 → 轮径 66.404 mm，已填入 `WHEEL_DIAMETER_M=0.066404f`，WorkBuddy 验算一致 | 距离读数已有效；四路一致性 1.52%（极差 96 脉冲）可接受 | 已解决；22:12 版 hex 待上电确认画面 |
| 8 | **【已闭环】** WorkBuddy 曾误判 `encoder.c` 的 `speed_rpm` 公式差 1000 倍 | 错误指令会让 Argon4 把正确公式改成 1000 倍错误值 | 15:15 修订派单 01 W1；22:04 收口核对确认公式逐字未改、只增加注释（第 73-79 行），全文无 `0.001f`。**公式正确，不得改动** |
| 9 | **【已闭环】** 派单 02 收口发现：`CONTROL_OPEN_LOOP_DUTY` 曾由 0 改为 20 | 曾影响开环标定起点 | 派单 03 已将 `OPEN_LOOP_DUTY` 改回 **0**，`motorOpenLoopDuty[]` 默认全 0，起点安全。已解决 |
| 10 | **【已裁决闭环】400 RPM 测试点超出硬件上限**：**100% 占空比实测四路最大稳态约 330 RPM**（11-20 补测，车架空） | `TASK_STAGE_01_PID.md` 的 0→400、400→0、四轮 400 RPM 一致性测试物理上无法通过 | **人类 11-20 拍板：阶段 1 验收上限正式核定 200 RPM**，400 RPM 测试点豁免；阶段 2 目标 ≤250 RPM（留 20~25% 余量）。任务单由 Codex 接 MiMo 阶段末修订 |
| 11 | **阶段 1 遗留测试**：落地 200 RPM 长时间直行对比、外部上位机下发指令 | 架空单轮/四轮已验，真实地面与外部指令未验 | 并入阶段 2 运动学联调；不影响阶段 1 速度环核心验收 |
| 12 | **【已确认】底盘轮型**：人类 11-20 确认为**普通轮子**，四轮独立驱动差速底盘（skid-steer），无独立侧移 | 阶段 2 运动学必须按 vx + omega 两自由度做，不能按麦克纳姆全向模型；斜行只能转向+前进近似 | 已写入 `AI_COLLAB/HANDOFF_TO_CODEX_STAGE_02.md`，Codex 按此规划 |
| 13 | **【待 Codex 对齐颗粒度】** 阶段 2 四个架构问题：① 里程计精度验收标准与是否引入 IMU ② 左右轮 10% 差异标定方案 ③ 基础/完整通信边界 ④ 阶段 2 派单粒度 | 用户 11-20 要求先与 Codex 对齐，不预设结论 | WorkBuddy 已给参考口径写进移交单 §3.4；以 Codex 结论为准，不写成既定标准 |
| 14 | **【省 token 约定】** Codex 阶段末只读 `AI_COLLAB/BRIEF_FOR_CODEX.md`（~60 行速览卡），细节按指针跳读；**不要默认全文通读** CHANGELOG(229)/AI_SYNC(322)/移交单(121) | 用户 11-20 提出全读太耗 token | 已建速览卡并在 README、移交单 §2 写明分层阅读规则 |

---

## 8. 红线（摘自 PROJECT_OVERVIEW §7 / §11，违反即停）

```text
同一文件同一时间只能有一个模型修改
每个开发任务必须限定修改文件范围
CubeMX / 定时器 / 引脚 / 方向逻辑不得由实现模型随意修改
每个阶段完成后必须编译、测试、记录，再进入下一阶段
实车测试结果由人类确认，不以模型推测替代硬件结果
硬件急停优先级最高 / 上电默认停车 / PWM 和积分必须限幅 / PID 循环禁止 HAL_Delay
从 CubeMX 重新生成会重写 uvprojx，手动加进工程的 pid.c、control.c、encoder.c、motor.c、oled.c 需在 Keil 重新 Add
PID 周期等架构口径必须由人类 / Codex 裁决，实现模型不得自行决定
```

---

## 9. 本文件维护记录

| 日期 | 变更 |
|---|---|
| 2026-11-18 14:31 | 建立文件；写入状态快照、文件锁、广播流水、存疑清单（WorkBuddy） |
| 2026-11-18 14:42 | 按用户裁定重写 §3 协作流程与分工；§0/§1/§5/§6/§7 同步更新；旧分工表标记为过时（WorkBuddy） |
| 2026-11-18 14:57 | 起点分析 + 出派单 01：§2 标注进行中任务；§4 登记文件锁与 encoder.c 授权例外；§5 待办重排；§6 广播两条；§7 新增轮径与速度字段两条 |
| 2026-11-18 15:15 | 纠错修订：顶部统一目录约定；§2 标注瞬时速度公式正确 + 纠正记录；§3.4 派单要求加待裁决项与实际文件名；§4 文件名约定；§5 新增 2c 周期裁决 / 2d 派单 02 前置条件；§6 广播两条；§7 第 1 条升级为正式三方案裁决、第 2 条明确闭环归零、第 8 条标注已纠正；§8 新增裁决红线（WorkBuddy） |
| 2026-11-18 22:04 | 派单 01 收口：核对源码与禁止文件时间戳、确认 W1 公式未改；§2 更新 OLED/构建/下载/里程计四项、§4 文件锁转已完成、§5 待办 2 与 2b 标完成、§6 广播三条、§7 第 8 条标已闭环（WorkBuddy） |
| 2026-11-18 22:14 | 轮径回填补充收口：独立验算轮径、复核 W1 与安全宏未变；§2 更新构建/下载/里程计、§4 文件锁补 22:12 回填、§5 待办 2a 完成 + 新增 2a-1 上电确认 + 2d 前置条件更新、§6 广播两条、§7 第 7 条标已闭环（WorkBuddy） |
| 2026-11-19 20:20 | PID 周期裁决落地：§2 核对时间；§5 待办 2c 标已裁决 A、新增 2a-2 勾掉上电确认、2d 转下一步；§6 广播三条；§7 第 1 条改为已裁决 A + 抗噪声强制要求（WorkBuddy） |
| 2026-11-19 20:35 | 派单 02 收口：§2 更新闭环 1 ms 状态/编译/实车/目标接口；§4 文件锁标完成；§5 派单 02 完成 + 新增 2e、待办 3/4/5 并入 2e；§6 广播三条；§7 第 2 条标已解决、新增第 9 条两处偏差（WorkBuddy） |
| 2026-11-19 21:14 | 派单 03 收口 + 阶段 1 核心完成：§2 更新整定参数/编译/实车/进度；§4 文件锁；§5 全面更新（阶段 1 完成、新增待裁决 6/下一步 7/遗留 8-9）；§6 广播三条；§7 第 9 条闭环 + 第 10 条 400 RPM 超限 + 第 11 条遗留（WorkBuddy） |
| 2026-11-20 16:25 | 目录规范化：全部文档迁入 AI_COLLAB\；派单分阶段放 DISPATCHES\STAGE_xx\，验收放 ACCEPTANCE\；新建 README.md；批量更新路径引用；§1 上手顺序加 README 与派单入口（WorkBuddy） |
| 2026-11-20 16:31 | 阶段 1 正式交付：§2 加验收口径、进度转正式交付；§5 待裁决 6 与下一步 7 更新；§6 广播两条；§7 第 10 条标已裁决（200 RPM / 实测 330）；产出移交单（WorkBuddy） |
