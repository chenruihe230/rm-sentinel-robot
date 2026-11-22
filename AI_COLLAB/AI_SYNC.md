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
| 当前阶段 | ✅ **阶段 1/2/3 全部收官**；**阶段 4 二维云台已批准启动（11-22 21:37）**，进行中第一单 S4-01（硬件现场确认 + USART6 架构变更，人类主导）。执行用 Argon |
| 阶段 4 决策 | USART6(PC6/PC7) 独立链路 + 带编码器版云台；协议 UART 128000bps/7B XOR 帧；F407 只发目标帧不搞 PID；TYPE 0x20 透传；重生成后重新 Add **11 个** .c；编码器协议未现场确认前禁止写解析代码 |
| 阶段 3 验收 | 15 项对照：13 完全通过 + 2 如实标注（无线遥测 5.6~7.1Hz 物理限制、单轮 1m M1/M3 2.01% 压线），均非阻塞。T3 IMU 360° 偏差 +0.18°、回起点 3cm、400ms 超时 0 误触发 |
| 补测关键结果 | IMU 模式 360° 偏差 **+0.18°**（≤10° 硬指标大胜）；回起点卷尺偏 **3 cm**（≤5cm 争取线达成）；400ms 超时连续轮询 drop=0/timeout=0；T2 单轮 M1/M3 **2.01% 压线**、整车 1.54% 过 |
| 阶段 3 通信状态 | HC-12 CH002 无线全功能验证通过；**超时已 200→400ms**（RTT 175ms 留 2.28× 余量），16:50 hex 0E/0W。待实测 30s 心跳无误停车。已知瑕疵：`chassis.c:442` 注释仍写 200ms（纯注释，下个改 chassis.c 的派单带上） |
| 阶段 2 验收 | 核心指标全达标（直行 0.1%、横偏 ≤5cm、定点 −0.7°、IMU 方向正确）；4 项非阻塞未测如实记录；通信归属未定待 Codex 规划 |
| 航向闭环已验证 | mode 1 直行 2m 横偏 10cm→≤5cm、里程 0.1%；mode 2 转 90°→89.3°/180°→179.3°（**误差 −0.7°**，S2-06B 微调后）；IMU 掉线 SAFE STOP 不盲转 |
| 标定建议值（待固化） | `chassisTrackWidthM` **0.3703f**（3 次极差 3.24%）、`motorGain[]` **保持全 1.0**（闭环 PI 已 ±0.5%，开环补偿不可用）、`wheelScale[]` **1.015×4**（直行 2m 误差 1.45%）。均未写死，由人类决定是否固化默认值 |
| 阶段 2 基线 | 阶段 1 安全基线 + `chassis.h/c` + `imu.h/c`：1 ms 差速解算 + 四轮里程计 + IMU 为主 yaw 融合（DWT 2ms 硬超时防死锁）、gain/scale 与轮距 0.20f 可写、±250 等比饱和；`TARGET=0` 上电不跑（11-21 14:56 hex） |
| IMU 状态 | I2C2（PB10/PB11，400 kHz，0x50）已接；6 轴模式、相对角、**IMU yaw 为主**（编码器打滑 2 倍不可信）；未接时自动回退纯编码器。1000 ms 上电零点收敛；实车逆时针 90°→YAW +90°，`imuYawSign=+1` 方向正确 |
| **里程计实车关键发现** | 直行 1 m 实测 1.03 m（+3%，良好）；**原地转 90° 实际仅 45° → 等效滑移轮距约 0.40 m ≈ 几何 0.20 m 的 2 倍** —— skid-steer 打滑，单靠几何轮距 yaw 误差大，S2-04 用 IMU、S2-05 标定等效轮距 |
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
| 7 | **移交 Codex 接 MiMo**：总览更新（§6 分工表同步）+ 任务单 400→200 RPM 修订 | Codex 接 MiMo | 阶段末 | **待办**（阶段 2 规划已完成存档，不重复做） |
| 2-S2-01 | **阶段 2 第一单**：接口与数据结构骨架（`Chassis_*` / `IMU_*` / gain/scale / 轮距变量） | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（v2 修订版；20:50 编译 0E/0W，人类实车确认车不动/OLED 0000.0；20:54 收口） |
| 2-S2-02 | **阶段 2 第二单**：差速运动学（vx/omega → 四轮 RPM + 下发 + ±250 饱和） | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（21:11 编译 0E/0W，架空单测旋转符号正确，已恢复停车基线；21:11 收口） |
| 2-S2-03 | **阶段 2 第三单**：整车里程计积分（四轮累计距离 → x/y/yaw/vx/omega，禁用瞬时 RPM） | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（11-21 14:20 编译 0E/0W，实车直行 +3% / 旋转发现 2 倍打滑，已还原安全基线；14:21 收口） |
| 2-S2-04 | **阶段 2 第四单**：IMU 标定与 yaw 融合 | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（15:17 最终 hex 0E/0W；加 1000ms 零点收敛；**实车 IMU:OK、静止 Gz≈0、逆时针转 90°→YAW +90° 方向正确**；15:17 最终确认） |
| 2-S2-04b | **不接 IMU 上电**确认不死锁（异常场景单测） | 人类实车 | 人类 | **可选补测**（接 IMU 实车正常已间接验证驱动无死锁；异常场景未单测，不阻塞 S2-05） |
| 2-S2-05 | **阶段 2 第五单**：等效轮距（S2-03 实测约 0.40 m）与左右轮增益/里程 scale 标定 | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（15:46 收口：轮距 0.3703m、gain 保持 1.0、scale 1.015；15:39 hex 0E/0W） |
| 2-S2-06 | **航向闭环纠偏**（直行保持 / 定点精确转向） | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（16:07 hex 0E/0W；直行横偏 ≤5cm、90°→88°/180°→177.7°、掉线 SAFE STOP；16:08 收口） |
| 2-S2-06B | **定点转向精度微调**（2°→≤1°，低速保底+过冲刹车） | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（16:20 hex 0E/0W；90°→89.3°、180°→179.3°，误差 −0.7° 优于 ≤1°；16:21 收口） |
| 2-S2-TEST | **阶段 2 统一验收** | WorkBuddy 整理 / 人类实测 | WorkBuddy | ✅ **已完成**（11-21 16:25 出验收记录 `ACCEPTANCE/STAGE_02.md`，结论通过、阶段 2 收官） |
| 3-移交 | 阶段末移交 Codex：更新总览 + 定通信归属 + 阶段 3 规划 | Codex 接 MiMo | 未认领 | **下一步**（移交材料见验收记录 §6 + 速览卡） |
| 3-审单 | Codex 阶段 3 规划两轮审单 | WorkBuddy 审 / Codex 改 | ✅ **闭环** | V1 七条 + V2 五条**全部采纳**；CRC8 两向量经 WorkBuddy 验算通过（0x38/0x3D）、TELEMETRY 26B 自洽；规划定稿 |
| 3-S3-01 | **阶段 3 第一单**：HC-12 协议与帧格式（纯软件，不碰串口/CubeMX） | WorkBuddy 出派单 / Argon4 实现 | Argon4 | ✅ **已完成**（20:57 hex 0E/0W；CRC 两向量+STOP 帧经 WorkBuddy 独立编译复核通过；21:00 收口。回传别名 S3-01A） |
| 3-S3-01B | **HC-12 模块配置** | WorkBuddy 出派单 / 人类操作 | 人类 | ✅ **已完成**（CH002/9600/FU3/P8 两块一致，4/4 互发稳定，排障天线+5V供电；15:38 收口） |
| 3-S3-02 | **USART1 架构变更 + STM32 收发 + 超时停车** | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（8 .c 全在、ForceStop 三处共用、15:37 hex 0E/0W；15:38 收口。运行时待 S3-03 联调） |
| 3-S3-03 | **Python + pyserial 上位机** | WorkBuddy 出派单 / Argon4 | Argon4 | ✅ **已完成**（16:33 收口：有线全项通过、无线功能正确；CRC 自检独立复核通过） |
| 3-S3-03B | **无线超时 200→400ms**（含上位机 t 测试 0.5→0.8s 与注释同步） | WorkBuddy 出派单 / Argon4 | Argon4 | ✅ **已完成**（16:50 收口：宏与四处同步全对、逻辑未动、0E/0W；待实测 30s 心跳） |
| 3-S3-04/05 | **补测**：弧线/360°分模式/回起点分级 + 单轮1m/模式切换 | WorkBuddy 出派单 / Argon4 + 人类 | Argon4 / 人类 | ✅ **已完成**（17:36 收口，零生产代码改动；五项全闭环，T2 M1/M3 2.01% 压线如实标注） |
| 3-S3-TEST | **阶段 3 统一验收** | WorkBuddy 整理 / 人类实测 | WorkBuddy | ✅ **已完成**（11-21/22 17:40 出 `ACCEPTANCE/STAGE_03.md`，结论通过、阶段 3 收官） |
| 3-S3-DEMO | **参数化动作 API + 交互式上位机（展示层）** | WorkBuddy 出派单 / Argon 全包 | Argon | ✅ **v2 完成**（18:11 hex 0E/0W；TYPE 0x05、5 动作、单一司机入口收敛、HMI 九文件；19:46 收口核对通过） |
| 3-S3-DEMO-v3 | **增强**：梯形减速 + 归零 0x06 + WASD 赛车 + 双击地图 + 剧本 | WorkBuddy 出派单 / Argon | Argon | ✅ **已完成**（20:15 收口：三处纠正全落地、20:04 hex 0E/0W；⚠️ 停止误差为 Mock 仿真，实车待验证） |
| 3-实车补验 | 烧 20:04 hex 实车跑：梯形停止误差 / 0x06 归零 / WASD / 双击地图 / 三剧本 | 人类实车 | 人类 | **可选**（展示层，不阻塞阶段 3；仿真已过） |
| 4-移交 | Codex 总览与阶段 4 规划 | Codex 接 MiMo | Codex | ✅ **已回执**：总览更新质量高、三项遗留处置认同；WorkBuddy 审单 `REVIEW_STAGE_04_PLAN.md`（状态越权已直接修正 + 2 处技术空白待 Codex 补） |
| 4-规划补 | 阶段 4 两处空白 | Codex 补 / 人类选 | ✅ **已查证+已拍板** | 硬件事实 `GIMBAL_HARDWARE_FACTS.md`：WHEELTEC 步进云台自带 STM32F103+D36A，UART 7B 角度帧（0x7B...XOR...0x7D，128000bps），不是裸步进。**人类 21:26 拍板：USART6(PC6/PC7) 独立链路 + 带编码器版**。PC6/PC7 已核对空闲；重生成后需重新 Add **11 个**手动 .c；编码器角度读取协议待现场确认（不许猜） |
| 4-启动 | 阶段 4 二维云台启动 | 人类批准 | 人类 | ✅ **人类 11-22 21:37 批准启动**；规划 V2 审单通过 |
| 4-S4-01 | **S4-01 硬件现场确认 + USART6 架构变更**（人类主导，Argon 出指南/核对） | WorkBuddy 出派单 / 人类 + Argon | 未认领 | ✅ **已出派单+已按 Argon 查证修订**（`S4_01_HW_CONFIRM.md`）：原编码器 10 问已查明"无串口协议"→改为**编码器 6 芯线接线确认 + 两轴定时器/引脚盘点**；含安全归零角/供电/CubeMX/11个.c；待发 |
| 4-执行模型 | 阶段 4 实现（安全关键 + 多文件架构变更） | Argon 跑 / 人类操作 CubeMX | — | USART6 CubeMX 由人类亲手操作，模型不得改 .ioc；重生成后重新 Add 11 个 .c |
| 3-决策-超时 | 无线超时线方案 | 反重力评估 → WorkBuddy 核对 → 人类裁定 | 人类 ✅ | **裁定 400 ms**（11-22 16:42）：采纳反重力评估——上位机已零等待收发、RTT 是物理下限（C 无效），B 牺牲距离；400ms 留 2.28× 余量，未来切有线只改一个宏。WorkBuddy 原倾向 350ms，核算后与 400ms 制动仅差 4~5cm，故采纳 400。**待出改单（Argon 跑）** |
| 2-遗留-通信 | 基础/完整通信（原 S2-06）归属未定 | 待阶段末 Codex 规划 | 未认领 | 肯定不是阶段 2；不预设阶段 3 |
| 2-S2-05 | **阶段 2 第五单**：等效轮距与左右轮差异标定（已证实等效轮距约 0.40 m） | WorkBuddy 出派单 / Argon4 + 人类 | 未认领 | 待办 |
| 2-S2-00 | 实测左右轮中心距（m）填入 `chassisTrackWidthM` | 人类实测 + WorkBuddy 记录 | 人类 | ✅ **已粗测：约 0.20 m**（11-20 20:59，用户称后期再校准）；已记入 PLAN_STAGE_02.md §七细则 1；S2-05 用原地旋转标定精修等效轮距 |
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
- 2026-11-20 17:04 | 人类用户 | 转交 Codex 的阶段 2 完整规划（7 单 S2-01~S2-06+S2-TEST），裁定：**实现细则由 WorkBuddy 定，Codex 只做规划；IMU 选型/引脚到 S2-04 前再立项** | `AI_COLLAB/PLAN_STAGE_02.md` | WorkBuddy 存档 + 拍板细则
- 2026-11-20 17:04 | WorkBuddy | 阶段 2 规划定稿：Codex 规划存为 PLAN_STAGE_02.md；拍板 6 条细则（轮距两级标定、IMU 延后立项、gain/scale 预留、接口形式与轮序、通信超时 200 ms、±250 等比缩放）；速览卡与 §7 第 13 条改已闭环
- 2026-11-20 20:54 | WorkBuddy | S2-01 收口：核对两个调用点与 SetVelocity 无下发、安全宏原样、禁止文件未动；追加 CHANGELOG 20:54 节；§2 进度转阶段 2、§5 S2-01 完成 + 新增 S2-02 与轮距阻塞项、§6 广播三条、§7 第 19 条标已闭环（WorkBuddy）
- 2026-11-20 20:59 | 人类用户 | 实测左右轮中心距约 **0.20 m（20 cm，粗测，后期校准）**；WorkBuddy 验算：理论 omega 上限 8.69 rad/s，当前代码 6.0 rad/s 偏保守但安全，S2-02 按实测轮距重算 | PLAN_STAGE_02.md §七细则 1、AI_SYNC §5 待办 2-S2-00 | 轮距阻塞解除，可出 S2-02 派单
- 2026-11-20 21:11 | Argon4/反重力 | S2-02 落地：chassis.h/c 实现差速逆解算 + gain + 四轮 ±250 等比饱和 + Control_SetTargetRpm 下发；omega 上限 8.5f、轮距默认 0.20f | Core/Inc/chassis.h、Core/Src/chassis.c | 21:11:08 hex，0 Error / 0 Warning
- 2026-11-20 21:11 | 人类用户 | 架空单测：SetVelocity(0, 2.0) 理论左 −57.5/右 +57.5 RPM，实测符号正确（M1/M3 退、M2/M4 进，逆时针左转），OLED 约 60 RPM 稳定；测后恢复 vx=0/omega=0 停车基线 | 烧录 21:11 版 hex | S2-02 验收通过
- 2026-11-20 21:11 | WorkBuddy | 收口：核对差速公式/RPM 换算/gain/等比饱和/下发齐全、无 Motor_SetOutput 直驱与 vy、禁止文件未动、无临时测试遗留；追加 CHANGELOG 21:11 节，§2 基线更新、§5 S2-02 完成 + 新增 S2-03 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | 下一步：出 S2-03 派单
- 2026-11-21 14:21 | Argon4/反重力 | S2-03 落地：chassis.h/c 实现累计距离差分里程计（wheelScale 修正、中点积分、wrap、odom LPF、复位），临时 OLED 测试后彻底还原 main.c/control.c | Core/Inc/chassis.h、Core/Src/chassis.c | 14:20:55 hex，0 Error / 0 Warning
- 2026-11-21 14:21 | 人类用户 | 实车验证：直行 1 m 实测 1.03 m（+3% 良好）；**原地转 90° 实际仅 45° → 等效滑移轮距约 0.40 m（几何 0.20 m 的 2 倍）**；临时代码已还原、重编安全基线 | 烧录 14:20 版 hex | S2-03 验收通过；关键发现入规划
- 2026-11-21 14:21 | WorkBuddy | 收口：核对里程计用累计距离差分、无 speed_rpm 积分、odom 不喂 PID、main.c/control.c 已还原（字节数与基线一致）、禁止文件未动；追加 CHANGELOG 14:21 节；§2 加关键发现、§5 S2-03 完成 + 新增 S2-04/S2-05、PLAN §七记录 2 倍打滑 | CHANGELOG.md、AI_SYNC.md、PLAN_STAGE_02.md | 下一步：S2-04（先 CubeMX 配 I2C2）
- 2026-11-21 14:39 | 人类用户 | 按反重力指导在 CubeMX 启用 I2C2（PB10/PB11，400 kHz）并生成代码；Keil 中六个手动 Add 的 .c 全部保留；编译 0 Error / 0 Warning（Code=13388） | breathing.ioc、i2c.c、main.c、uvprojx | S2-04 W0 架构变更完成
- 2026-11-21 14:39 | WorkBuddy | 核对 W0：.ioc I2C2 配置正确、i2c.c hi2c2/MX_I2C2_Init/400000/AF4 齐全、main.c 第 99 行调用在、六 .c 全在、I2C1 未动；§5 待办 2-S2-04 与 §7 第 18 条标 W0 完成 | AI_SYNC.md | 发 S2-04 W1~W4 代码提示词
- 2026-11-21 14:47 | 人类用户 | S2-04 审单：发现 1 致命死锁（SysTick 内 HAL_GetTick 超时）+ 3 SDK/边界细节；WorkBuddy 查证 REG.h/wit_c_sdk.c 后全部采纳，派单重写为 v2 | S2_04_IMU_FUSION.md v2、AI_SYNC §7 第 19b 条 | 发 v2 代码提示词
- 2026-11-21 14:56 | Argon4/反重力 | S2-04 v2 落地：新建 imu.h/c（裸寄存器 I2C2 + DWT 2ms 硬超时 + 总线恢复 + 14 字节连读 + 解锁配置），chassis.h/c 加 10ms 分频与 IMU 为主融合，Keil Add imu.c | Core/Inc/imu.h、Core/Src/imu.c、chassis.h/c、uvprojx | 14:56:15 hex，0 Error / 0 Warning
- 2026-11-21 15:04 | WorkBuddy | 收口：核对 imu.c 无 HAL_I2C 调用、DWT 双层兜底、分频在 chassis.c 249-254 行、配置序列 KEY 解锁无 0x53、GZ 连读字节序与换算、IMU 为主且回退逻辑、IMU yaw 未喂 PID；禁止文件未动；追加 CHANGELOG 15:04 节、§2 加 IMU 状态、§5 S2-04 完成 + 新增 2-S2-04b 实测待办与 S2-05、§7 第 19b 闭环 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | 下一步：S2-05；未接 IMU 防死锁实测待人类
- 2026-11-21 15:17 | 人类用户 | S2-04 最终版实车：接线 3V3/GND/PB10/PB11 与 OLED 隔离；临时 OLED 显示 `IMU:OK`、静止 Gz≈0、1000ms 收敛后 YAW 稳定 0.0°；**逆时针转 90°→YAW +90°，`imuYawSign=+1` 方向正确**；临时测试 main.c 已完整还原 | 烧录最终 hex | S2-04 实车闭环通过
- 2026-11-21 15:17 | WorkBuddy | 最终版确认：核对 1000ms 收敛代码（imuWarmupCount=100，390-394 行）、main.c 7049 bytes 无 IMU 测试残留、编译 0E/0W（Code=14968）；记录 hex 时间偏差（报 15:15:01 / 实际 15:17:01）；追加 CHANGELOG 15:17 节、§2 IMU 状态、§5 S2-04 完成与 2-S2-04b 降为可选 | CHANGELOG.md、AI_SYNC.md | 下一步：出 S2-05 派单
- 2026-11-21 15:41 | 人类用户 | 裁定**基础电脑通信（原 S2-06）肯定不是阶段 2 任务**，暂不指定归属阶段 | PLAN_STAGE_02.md、AI_SYNC §7 第 20 条 | WorkBuddy 从规划/待办/派单/速览卡移除 S2-06，归属留空待阶段末 Codex 规划
- 2026-11-21 15:46 | Argon4/人类 | S2-05 实车标定完成：3 次原地转得等效轮距 0.3703m（极差 3.24%）；四轮开环 20/40/60/80% 测 RPM；2m 地砖直行纵向误差 1.45%；临时 main.c 还原、15:39:54 hex 0E/0W | chassis.h/c（只读观测量）、main.c（还原） | S2-05 验收通过
- 2026-11-21 15:46 | WorkBuddy | 收口：核对只加只读观测量、默认值未写死、轮径未改、main.c 无残留、禁止文件未动；采纳「闭环下 motorGain 保持 1.0」结论并从回传中纠正错误 S2-06 编号；追加 CHANGELOG 15:46 节、§2 标定建议值、§5 S2-05 完成 + S2-TEST/航向闭环遗留、§7 第 21 条 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | 下一步：S2-TEST 统一验收
- 2026-11-21 15:51 | 人类用户 | 采纳反重力建议：**先做航向闭环纠偏单，再进 S2-TEST**；沿用 S2-06 编号（原通信单已移出） | `AI_COLLAB/DISPATCHES/STAGE_02/S2_06_HEADING_CONTROL.md` | WorkBuddy 出派单并标注编号复用
- 2026-11-21 15:51 | WorkBuddy | 新增 S2-06 航向闭环派单（W0 固化 0.3703/1.015 + W1 模式接口 + W2 航向环覆盖 omega + W3 到达判据 + W4 隔离）；更新 PLAN/README/§5 待办/§7 第 22 条区分编号 | PLAN_STAGE_02.md、README.md、AI_SYNC.md、S2_06_HEADING_CONTROL.md | 发反重力
- 2026-11-21 16:08 | Argon4/人类 | S2-06 航向闭环完成：固化 0.3703/1.015/gain1.0；mode1 直行 2m 横偏 10cm→≤5cm、里程 0.1%；mode2 转 90°→88°/180°→177.7°（≤5°）；IMU 掉线 SAFE STOP 不盲转；main.c 还原、16:07:32 hex 0E/0W | chassis.h/c、main.c（还原） | S2-06 验收通过
- 2026-11-21 16:08 | WorkBuddy | 收口：核对航向环在差速解算前覆盖 omega、速度 PID 未碰、mode2 掉线清零停车、到达判据、固化值 Watch 可写、禁止文件未动、main.c 无残留；追加 CHANGELOG 16:08 节、§2 航向闭环已验证、§5 S2-06 完成与 S2-TEST 下一步、§7 第 22 条闭环 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | 阶段 2 实现单全完成 → S2-TEST
- 2026-11-21 16:21 | Argon4/人类 | S2-06B 完成：TOL 0.05→0.017→0.008f、SETTLE 150ms、低速保底 minOmega 0.06、过冲反向、超时 8s；实车 90°→89.3°/180°→179.3°（−0.7° 优于 ≤1°）；main.c 还原、16:20:31 hex 0E/0W | chassis.h/c、main.c（还原） | S2-06B 验收通过
- 2026-11-21 16:21 | WorkBuddy | 收口：核对 mode1 传 is_point_turn=0 仍纯比例、mode2 四级分段与钳位、掉线保护未动、超时在、参数可写、禁止文件未动、main.c 无残留；追加 CHANGELOG 16:21 节、§2 更新 89.3°/179.3°、§5 S2-06B 完成、§7 第 23 条闭环 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | **阶段 2 实现全完成 → S2-TEST 收官**
- 2026-11-21 16:25 | WorkBuddy | **S2-TEST 收官**：对照 PLAN §五逐项验收，出 `ACCEPTANCE/STAGE_02.md`（结论通过）；核心指标全达标、4 项非阻塞未测如实记录、5 条工程结论沉淀、移交 Codex（更新总览 + 定通信归属 + 阶段 3 规划）。README 加验收记录入口、§2 转阶段 2 收官、§5 S2-TEST 完成 + 3-移交 | ACCEPTANCE/STAGE_02.md、README.md、AI_SYNC.md | **阶段 2 正式收官，待 Codex**
- 2026-11-22 17:40 | WorkBuddy | **S3-TEST 收官**：对照 Codex §八 15 项验收，出 `ACCEPTANCE/STAGE_03.md`（结论通过）；13 通过 + 2 如实标注（无线频率物理限制、单轮 M1/M3 2.01% 压线）；5 条工程结论沉淀、移交 Codex（总览 + 后续阶段规划）。README 加验收入口、§2/§5 转阶段 3 收官、§6 广播 | ACCEPTANCE/STAGE_03.md、README.md、AI_SYNC.md、BRIEF_FOR_CODEX | **阶段 1/2/3 全部交付，待 Codex** |
- 2026-11-21 20:30 | 人类用户 | 转交 Codex 阶段 3 规划（HC-12 + 补测），WorkBuddy 审查：查证 HC-12 手册 + 核对工程 .ioc | REVIEW_STAGE_03_PLAN.md、AI_SYNC §7 第 24 条 | 出审单意见，待 Codex 修订
- 2026-11-21 20:30 | WorkBuddy | 阶段 3 审单：3 必改（半双工时序/波特率方向/USART1 架构变更）+ 4 建议；核对 PA9/PA10 空闲、M1 是 PE9 不冲突；README 加入口、§5 加 3-审单、§7 第 24 条 | REVIEW_STAGE_03_PLAN.md、README.md、AI_SYNC.md | 发 Codex 审单提示词
- 2026-11-21 20:46 | WorkBuddy | 阶段 3 规划定稿：V1/V2 全部采纳，CRC8 两向量验算通过；出 S3-01 派单（纯协议层） | DISPATCHES/STAGE_03/S3_01_PROTOCOL.md、README、AI_SYNC | 发反重力
- 2026-11-21 21:00 | Argon4/反重力 | S3-01（回传称 S3-01A）完成：新建 comm_protocol.h/c、Keil Add；CRC8/组帧/解析纯函数、四类错码；gcc 单测全过；20:57:57 hex 0E/0W | comm_protocol.h/c、uvprojx | S3-01 验收通过
- 2026-11-21 21:00 | WorkBuddy | 收口：gcc 独立编译复核 CRC 0x38/0x3D、STOP 帧 `AA 55 03 01 38 0D 0A`、解析返回0 全对；禁止文件未动、无 USART API；追加 CHANGELOG 21:00、§5 S3-01 完成 + S3-01B/S3-02 待办 | CHANGELOG.md、AI_SYNC.md | 下一步：S3-01B + S3-02 |
- 2026-11-20 17:24 | 人类用户 | 提供 IMU 模块淘宝链接（亚博智能 GPS/北斗+IMU 惯导，MF168）；WorkBuddy 查证官方规格登记到 PLAN_STAGE_02.md S2-04：自带卡尔曼解算直出 yaw（简化实现），但九轴 yaw 为绝对角（东北天）与车体相对 yaw 冲突，已定用 `wrap(raw−yaw0)` 转相对角 | PLAN_STAGE_02.md S2-04、AI_SYNC §7 第 15 条 | 待确认版本(6/9/10轴)、裸机/外壳、供电、UART/I2C、引脚、安装方向；S2-04 派单前必须确认
- 2026-11-20 20:54 | Argon4/反重力 | S2-01 v2 落地：新建 chassis.h/c、Keil Add chassis.c、control.c 严格两处调用（119 行 Chassis_Init、222 行 Chassis_Update(CONTROL_PID_DT)）+ 3 行 include；SetVelocity 仅校验锁存不下发电机 | Core/Inc/chassis.h、Core/Src/chassis.c、Core/Src/control.c、uvprojx | 20:50:21 hex，0 Error / 0 Warning
- 2026-11-20 20:54 | 人类用户 | 实车确认 S2-01：烧录 20:50 版 hex，车静止、OLED 四行 `0000.0 RPM 000%`；此前重插线导致的 M1/M2 编码器插错已修复 | 烧录 20:50 版 hex | S2-01 验收通过
- 2026-11-20 20:54 | WorkBuddy | 收口：核对两个调用点精确位置、安全宏原样、SetVelocity 无 RPM 换算/电机调用、禁止文件时间戳未动；追加 CHANGELOG 20:54 节；§2 进度转阶段 2、§5 S2-01 完成 + 新增 S2-02/轮距阻塞项 | CHANGELOG.md、AI_SYNC.md、AI_WORKLOG_WORKBUDDY.md | 下一步：出 S2-02 派单；轮距实测待人类 | | PLAN_STAGE_02.md、BRIEF_FOR_CODEX.md、AI_SYNC.md | 出 S2-01 派单
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
| 13 | **【已闭环】** 阶段 2 四题颗粒度：Codex 已完成规划，用户裁定实现细则由 WorkBuddy 定 | 存档 `AI_COLLAB/PLAN_STAGE_02.md` | 结论：IMU 到 S2-04 前立项；motor_gain/wheel_scale 分开且 S2-01 预留；轮距不猜数值用可写变量 + 两级标定。**通信已移出阶段 2（见第 20 条）** |
| 20 | **【通信归属调整 11-21 15:41】** 用户裁定基础电脑通信（原 S2-06）**肯定不是阶段 2 的任务**，但暂不指定放哪个阶段 | 阶段 2 现为 S2-01~S2-05 + S2-TEST | 规划/同步板/派单/速览卡已全部移除 S2-06；归属留空待阶段末 Codex 规划，不预设阶段 3；参考口径存档 PLAN §七细则 5 |
| 21 | **【闭环下 motorGain 不可用开环值 — 11-21 15:46 实测结论】** S2-05 实测：开环 M4 偏慢 8%、前馈比 1.076，但闭环 PI（KP=0.4/KI=2.5）在 `motorGain=1.0` 下已把四轮拉到 99.5~100.2 RPM（±0.5%） | 若写入开环比值会强迫 M4 快 11% 导致左偏 | **闭环下 motorGain[] 保持全 1.0**；开环补偿值仅存档参考，除非改为前馈到 PWM 占空比。已写入 CHANGELOG 15:46 |
| 22 | **【S2-06 编号复用 11-21 15:51，已闭环 16:08】** 人类采纳反重力建议，新增**航向闭环纠偏单**并沿用 S2-06 编号（原 S2-06 基础通信 15:41 已移出阶段 2） | 两单内容无关：新 S2-06=航向闭环（直行保持/定点转向）；原 S2-06=UART 通信（归属未定） | 16:08 实车全项通过；阶段 2 六张实现单全部完成 |
| 23 | **【定点精度微调 11-21 16:10，已闭环 16:21】** 用户要求进 TEST 前把 mode 2 误差从 ~2° 压到 ≤1° | S2-06 容差 0.05rad(2.86°) 导致停前 2° | 未单纯改容差（1° 时 0.9 RPM 静摩擦卡死），用低速保底+过冲反向+超时；**实测误差 −0.7° 优于目标**，TOL 最终 0.008f、minOmega 0.06f；mode1 仍纯比例未回归 |
| 24 | **【阶段 3 规划审单 11-21 20:30】** Codex 阶段 3 规划（HC-12 + 补测），WorkBuddy 审查 | HC-12 官方手册 v2.3B 查证 + 本工程 .ioc 核对 | V1：3 必改 + 4 建议，**Codex V2 全部采纳**（9600、主从轮询、架构变更、分模式验收、Python、CRC8） |
| 25 | **【阶段 3 V2 审单 11-21 20:40，已闭环 20:46】** 修订版真 bug | 核对 `chassis.c` 466-500 行：航向环每帧覆盖 omega | Codex 全采纳：统一 `Chassis_ForceStop()`（清 vx/omega+置 `chassisHeadingMode=0`+reached 置位+四路 RPM 写0，优先级>一切模式）；CMD_MODE 只切 `chassisYawFusionMode`；补 DATA 字节数表（TELEMETRY 26B）、CRC8 向量**经 WorkBuddy 验算 0x38/0x3D 均正确**；配置先于接线；丢帧计数 STM32 统计。**阶段 3 规划定稿** |
| 26 | **【重生成清单更新 11-21 21:07，已验证 11-22】** S3-02 CubeMX 变更的重新 Add 清单由 7 → **8 个 .c** | S3-01 新增 `comm_protocol.c`，原 7 个清单（阶段 2 定）没算它 | 11-22 核对：pid/control/encoder/motor/oled/chassis/imu/**comm_protocol** + 新增 comm_uart/comm_session **全部在 Keil 工程树**，编译通过 |
| 27 | **【中断优先级表述纠错 11-22 15:38】** 实现方回传称「USART1=5、SysTick=15，不会饿死 SysTick」 | Cortex-M 数值越小优先级越高；`TICK_INT_PRIORITY=15U`、`USART1_IRQn=5` 已核对 | **5 < 15 恰说明 USART1 高于 SysTick、可抢占**。实际无碍是因回调仅数微秒 —— 结论对、理由错；禁止据此推理配更高优先级中断。已写入 CHANGELOG 15:38 |
| 28 | **【无线超时线告警 11-22 16:33 → 闭环 16:42】** S3-03 实测 RTT 170~180ms vs 200ms 超时线，余量仅 25ms | 反重力评估（仅评估未改代码）+ WorkBuddy 核对 | **采纳 400ms**：上位机已零等待收发（方案C无效）、B 牺牲距离；400ms 留 2.28× 余量、未来切有线只改一个宏。满速制动 41cm（高速测试预留 ≥0.5m）、常速 9.5cm。需同步改 comm_session.h:27+注释、comm_session.c:213 注释、comm_tool.py:212-217 的 t 测试 0.5→0.8s、README.md:48/53 |
| 29 | **【如实标注 11-22 16:33】** S3-03 回传称 main.c 已 SHA256 字节级还原，实测 7095 bytes / 16:23:25（基线 7049）、hex 16:31:35 / 63501 | 内容核对**无遥控/测试残留**，仅 `MX_USART1_UART_Init()`（S3-02 正常生成）+ 中文注释编码差异 | 不算安全事故，但**不得写"字节级还原"**；CHANGELOG 16:33 按实标注 |
| 30 | **【注释瑕疵 11-22 16:50】** S3-03B 把超时改 400ms 后，`chassis.c:442` 注释仍写「+ 200 ms 超时 Chassis_ForceStop」 | 该注释描述的是**通信超时**（非航向稳定窗口），确实过时；S3-04/05 补测为零代码改动，实现方选择不动 | 纯注释不影响功能、不阻塞；**已在 S3-04/05 收口说明中保留记录**，阶段 3 收官后如再做 chassis.c 相关改动时顺手修 |
| 31 | **【S3-DEMO v2 决策 11-22 17:55】** 用户拍板：STM32 端加参数化动作指令（像调 API，自由改距离/角度），回起点第一版不做，Argon 全包 | v1 上位机闭环精度差（±15cm、7Hz 轮询、提前量拍脑袋） | 改 v2：车端闭环复用已有 mode1/mode2、新增 TYPE 0x05（action_id+param int16）、上位机加原始帧工具替代串口助手；已有 TYPE/PID/安全零回归为硬边界。派单 v2 已出 |
| 32 | **【隔离性确认 11-22 18:01】** 用户问「确定不影响后期工程？」 | 核对插入点：TYPE 0x05 空位、帧 10B<33B、switch 加 case、1ms 环加一行、ForceStop 加一行、新逻辑独立文件；CubeMX/PID/里程计/航向环/400ms 宏不动 | **结构上可卸载**（删 comm_actions.* + 两行调用即还原）；发现**运行时状态竞争**缝：手动 CMD_VEL 可能与自动动作抢 mode1/mode2 全局状态 → 派单补「单一司机规则」：任何运动指令（VEL/MODE/ACTION/STOP）到达先 Abort 再执行，POLL 除外；验收加对应测试项。**v2 已核对落实（comm_session.c 100-104 行入口统一收敛）** |
| 33 | **【v3 审单三处纠正 11-22 19:46】** 反重力提案（精度+娱乐性），WorkBuddy 评估 | 核对现有编号：TYPE 0x05=CMD_ACTION、action 0x05=回起点预留 | ① 里程计归零必须用 **action 0x06**（提案的"启用 0x05"冲突，不可加新 TYPE）② 双击地图串联误差→演示级精度（~5cm）③ 剧本打断两层：上位机清队列+车端 Abort。派单 `S3_DEMO_V3_ENHANCE.md` |
| 34 | **【云台硬件事实查证 11-22 21:18，21:26 拍板，21:54 重大修正】** 用户提供 `D:\stm32\步进电机资料`，WorkBuddy+Argon 深挖全部资料 | `serial_control.py` + 全部 STM32/绘图例程 + 手册 §4.3/§1.1 + 更新记录 + 随货卡片图像 | **WHEELTEC 步进云台自带 STM32F103+D36A，UART 7B 角度帧（128000bps、0.1°、A=Yaw/B=Pitch）**。人类拍板 USART6(PC6/PC7)+编码器版。**⚠️ 21:54 修正**：编码器**不通过串口回传**（Argon 查遍资料确认"无串口查询/回传协议"）——MS42CG/MT6816 增量 A/B 相 4000计数/圈，须自己接 F407 定时器编码器口读 CNT。**WorkBuddy 核实硬冲突**：官方绘图例程的 TIM2(PB3/PA15)/TIM5(PA1/PA0) 与底盘编码器 TIM2~5 全撞；候选 TIM9(PE5/PE6)/TIM12，待查数据手册。**S4-04 增强级在定时器方案定前不可开工**。事实文件 §6.5 + S4-01 派单已修订 |
| 14 | **【省 token 约定】** Codex 阶段末只读 `AI_COLLAB/BRIEF_FOR_CODEX.md`（~60 行速览卡），细节按指针跳读；**不要默认全文通读** CHANGELOG(229)/AI_SYNC(322)/移交单(121) | 用户 11-20 提出全读太耗 token | 已建速览卡并在 README、移交单 §2 写明分层阅读规则 |
| 15 | **【IMU 已选型，待确认版本】** 用户 11-20 提供淘宝链接：亚博智能 GPS/北斗 + IMU 惯导模块（MF168）。自带 32 位 MCU + 卡尔曼姿态解算，直接输出 yaw 角（UART 或 I2C，5V/3.3V）。**九轴 yaw 是绝对角（东北天、0°=北、不能归零），与车体相对 yaw 冲突** → 已定方案：`IMU_GetYaw()` 返回相对角 `wrap(raw − yaw0)` | 若确认是外壳版只能 USB，不适合 STM32；GPS 室内无效阶段 2 不用 | 详见 `PLAN_STAGE_02.md` S2-04；版本（6/9/10轴）、裸机/外壳、供电、UART/I2C、引脚、安装方向**待用户确认**，确认前不得接线或改 `.ioc` |
| 16 | **【IMU 适用性评估 11-20 18:59】** 模块适合本项目（自带解算直出 yaw、精度远超验收线），但用法保守：① **波特率必须改 115200**（默认 9600 不够 100~200 Hz 输出，会丢帧）② **优先 6 轴模式**（仅陀螺仪 + 编码器，先不启用磁力计，避开 66 mm 小车的电机磁场干扰）③ 远离电机安装、Z 轴朝上 | 用默认 9600 或一上来开 9 轴会导致丢帧 / yaw 跳变 | 已写入 `PLAN_STAGE_02.md` S2-04「适用性评估」；S2-04 派单按此约束出 |
| 17 | **【IMU 资料查证 + 接口定案 11-20 19:17，前置全齐 19:25，接口 19:31 纠正】** 用户提供 `D:\stm32\imu(10zhou)`（简介 PDF + 串口/I2C 例程源码）。确认：**10 轴**维特 WT 系列（wit_c_sdk），SDK 直供 `Yaw` 寄存器 0x3f 无需自算姿态；供电 3.3V；按 6 轴模式用。人类 19:25 确认**裸机版、Z 轴朝上、XY 轴实物装好后软件标定** | 原「与 OLED 共用 I2C1」方案错误已废弃：`OLED_Refresh()` 阻塞 90 ms 会让 100 Hz 的 IMU 丢数据 | **最终接口：独立 I2C2（PB10/PB11，400 kHz，地址 0x50）**，已核对 `.ioc` 中 PB10/PB11 空闲；OLED 保持 I2C1 不变。备选 UART 115200 |
| 18 | **【✅ 已完成 11-21 14:39】S2-04 架构变更**：启用 I2C2（PB10=SCL/PB11=SDA，400 kHz），由反重力指导、人类在 CubeMX 亲手操作 | WorkBuddy 核对：`.ioc` I2C2 Fast mode、PB10/PB11 信号正确；`i2c.c` 有 `hi2c2`/`MX_I2C2_Init()`/400000/AF4；`main.c` 第 99 行调用在；Keil 六 .c 全在；14:39 hex 0E/0W | I2C1（OLED）未动，两总线物理隔离；W0 完成 |
| 19b | **【已闭环 11-21 15:04】S2-04 派单 v2 审单**：① **致命** SysTick 内 `HAL_I2C_Mem_Read` 的 `HAL_GetTick` 超时会死锁（IMU 未接/NACK）→ 改 **DWT->CYCCNT 硬超时 2 ms**，`IMU_Init` 仅在 main 阶段用 HAL ② 10ms 分频写在 `Chassis_Update()`（chassis.c），非 control.c ③ `IMU_GetYawRate` 读 GZ(0x39)，`raw/32768*2000*pi/180`，从 0x39 连读 14 字节取 GZ+Yaw ④ 写 AXIS6/RRATE/RSW 前先 KEY(0x69)=0xB588 解锁；**WIT_ANGLE(0x53) 是串口包类型非 I2C 寄存器**，删除该错误 | WorkBuddy 已逐项查 REG.h/wit_c_sdk.c 核对无误 | **15:04 收口核对：imu.c 无 HAL_I2C 调用、DWT 双层兜底、分频在 chassis.c、配置序列含解锁无 0x53、IMU 为主且可回退、IMU yaw 未喂 PID —— 代码层全通过**；实测待人类 |
| 19 | **【已闭环 11-20 20:54】S2-01 审单**：2 阻塞项 —— ① `control.c` 未放行却要调 `Chassis_Update(CONTROL_PID_DT)`（宏只在 control.c）→ 放行 control.c 且仅限 `Control_Init()` 末尾调 `Chassis_Init()`、`Control_Update()` 调 `Chassis_Update()` 两点，`main.c` 完全不动 ② `SetVelocity()` 语义不明 → 定死「仅校验+锁存目标，不换算 RPM/不下发电机」，新增 `chassisTargetVx/Omega`/`chassisCmdRejected`/`imuAvailable` 可观测 | 3 建议也全采纳：IMU 标记定名、omega 依据与 S2-02 饱和说明、验收改静态核对+上电为主 | **20:54 收口核对：两个调用点精确（119/222 行）、SetVelocity 无 RPM 换算/电机调用、安全宏原样；S2-01 已完成** |

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
