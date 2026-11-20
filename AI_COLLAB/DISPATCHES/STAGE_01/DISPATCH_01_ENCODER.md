# 派单 01 — 编码器测速夯实 + 里程计基础

> 致 Argon4：以下是本次完整任务提示词。请严格按「允许修改」范围执行，不要顺手改其他文件。
> 派单人：WorkBuddy ｜ 建立：2026-11-18 14:57 ｜ **修订：2026-11-18 15:15（W1 公式判断纠错，见 §12）**
> 授权：人类用户 2026-11-18 14:57 裁定（见 `AI_COLLAB/AI_SYNC.md` §6 广播）
> 派单格式：标准任务单（`PROJECT_OVERVIEW.md` §9）。「Gemini 反重力代码提示词」如有固定模板，请用户给出后以模板覆盖本格式。

---

## 1. 目录约定

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB（AI_SYNC.md / AI_WORKLOG_WORKBUDDY.md / CHANGELOG.md / DISPATCHES\ / ACCEPTANCE\）
```

下文所有 `Core/...`、`MDK-ARM/...` 相对路径均以 **Keil 工程目录**为基准。

## 2. 任务目标

接入 PID 之前，把编码器链路的输入质量打牢，同时建立里程计基础接口：

1. **保留** `encoder.c` 现有的 `speed_rpm` 公式（它是正确的），只补充注释说明其含义与噪声特性。
2. 建立可实车读取的测速验证手段：OLED 驱动模式改显 **RPM + 输出占空比**。
3. 把「1 ms 采样 / 100 ms 窗口」的时序契约写进代码注释，**不改任何宏数值**（周期本身另有方案待裁决，见 §12）。
4. 提供四路累计距离（米）接口，为阶段 2 运动学预留；轮径用占位宏，待人类实测填入。

**本任务不接入 PID 闭环，不改变电机输出行为。**

## 3. 当前代码状态（WorkBuddy 已核对，2026-11-18 15:15）

| 项 | 当前值 / 事实 |
|---|---|
| 编码器分辨率 | `ENCODER_COUNTS_PER_REV = 1320U`，四路共用（`Core/Src/encoder.c`） |
| 方向 | 四路 `direction = +1`；M3/M4 在 `motor.c` 中 IN1/IN2 对调，**不要动** |
| 抗干扰 | 编码器脚内部上拉；TIM2~5 `ClockDivision=DIV4`、`IC1/IC2Filter=15`；`.ioc` 已同步，**不要动** |
| 采样链路 | `SysTick_Handler` → `Control_Update()` 每 1 ms 调 `Encoder_Update()` 累加；每 100 ms 算 RPM 和占空比输出到电机 |
| 瞬时速度字段（encoder.c 第 73-74 行） | `encoder->speed_rpm = delta * 60000.0f / counts_per_rev` —— **公式正确，保留不变**。推导：1 ms 内 delta 个计数 → 每分钟 `delta × 60000` 个计数 → `RPM = delta × 60000 / counts_per_rev`。验算：1320 计数/圈、60 RPM = 1.32 计数/ms，代入得 60 RPM |
| 测速公式（control.c） | `motorSpeedRpm = speedCountAccum * 60000 / (1320 * 100)` —— 100 ms 窗口版本，**正确，不要改** |
| OLED 现状 | 驱动模式显示最近 100 ms 的 N / A 诊断计数；`OLED_ShowFloat()` 已在 `oled.h` 可用 |
| 当前配置 | `TEST_MODE=0`、`OPEN_LOOP=1`、`OPEN_LOOP_DUTY=0`、`TARGET_RPM=60`、KP=0.1/KI=0/KD=0 |
| 构建 | 11-17 22:09:39 的 `breathing.hex`，0 Error / 0 Warning；之后源码无改动 |
| 累计计数 | `encoders[i].total_count` 为 `int32_t`，每 1 ms 累加 delta，目前只写不读（除 Watch 外） |

## 4. 允许修改（本次授权范围）

```text
Core/Inc/encoder.h
Core/Src/encoder.c
Core/Inc/control.h
Core/Src/control.c
Core/Src/main.c
```

> 说明：阶段 1 原任务单禁止改 `encoder.c`，本范围由人类用户 2026-11-18 14:57 明确授权，仅限本次任务。改动完成后须在 `AI_COLLAB/CHANGELOG.md` 注明授权来源。

## 5. 禁止修改（硬边界）

```text
breathing.ioc
Core/Src/tim.c
Core/Src/motor.c
Core/Src/gpio.c
Core/Inc/main.h
Core/Inc/pid.h / Core/Src/pid.c
MDK-ARM/breathing.uvprojx（本次不新增 .c 文件，无需 Add）
docs/ 下所有文档
AI_COLLAB/CHANGELOG.md / AI_COLLAB/AI_SYNC.md / AI_COLLAB/AI_WORKLOG_WORKBUDDY.md / AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md（由 WorkBuddy 维护）
```

> **文件名约定**：工程实际文件是 `pid.h/.c` 与 `control.h/.c`。任务单里写的 `motor_pid.h/.c` **不存在**，本派单一律使用实际文件名，不要去找 `motor_pid.*`。

## 6. 具体工作项

### W1 — 保留 speed_rpm 公式，只补注释（必做）

- **不要修改** `Encoder_Update()` 中 `speed_rpm` 的计算公式。当前写法是正确的：
  ```c
  encoder->speed_rpm = ((float)delta * 60000.0f) / ((float)encoder->counts_per_rev * 1.0f);
  ```
- **严禁**改成 `delta * 60000.0f / (counts_per_rev * 0.001f)` 或任何带 `0.001f` 分母的变体 —— 系数 60000 已经包含 60 秒 × 1000 ms，再除 0.001 会**额外放大 1000 倍**。
- 在公式上方补充注释，说明：
  - 这是 **1 ms 瞬时 RPM**，噪声较大；
  - PID 使用的是 `control.c` 中 **100 ms 窗口**计算出的 `Control_GetSpeedRpm()`，不是这个瞬时值。
- 保留 `Encoder_GetSpeedRpm()` 接口（Watch 可能用到）。
- **不要**改 `delta` 的计算、方向处理、`total_count` 累加逻辑。

### W2 — OLED 驱动模式改显 RPM + 占空比（必做）

- 只改 `main.c` 中 `Control_IsTestMode()` 为假的显示分支；测试模式分支（手推累计计数）保持原样。
- 每行格式建议：`M1` + `Control_GetSpeedRpm(i)`（保留 1 位小数，带符号）+ `Control_GetOutputPercent(i)`（整数 %）。
- 用已有的 `OLED_ShowFloat()` / `OLED_ShowSignedNum()` / `OLED_ShowString()`；注意 128px 宽度，8 号字约 6px/字符，四行分别 y=0/16/32/48。
- 不再显示 N / A 原始计数（需要时看 Watch 变量 `debugNet` / `debugAbs`）。

### W3 — 时序契约写进注释（必做）

- 在 `control.c` 顶部调参区加注释，明确写出：
  - `SysTick` 每 1 ms 调 `Control_Update()`
  - 每 1 ms 读编码器并累加，每 `CONTROL_PID_PERIOD_MS = 100` ms 计算一次 RPM
  - 这是当初为抑制低速读数跳变从 1 ms → 10 ms → 100 ms 定的，不是笔误
  - 周期口径冲突已列为**正式待裁决项**（见 §12 与 `AI_COLLAB/AI_SYNC.md` §7 第 1 条），本次不改数值
- **禁止**改 `CONTROL_PID_PERIOD_MS`、`CONTROL_PID_DT`、KP/KI/KD 的数值。

### W4 — 里程计基础接口（必做，轮径占位）

- 在 `encoder.h` 增加轮径宏，**占位值 0.0f**，并写明 `TODO: 待人类实测轮径后填入（单位：米）`：
  ```c
  #define WHEEL_DIAMETER_M  0.0f
  ```
- 在 `encoder.c` 增加：
  ```c
  float Encoder_GetDistanceM(const Encoder_HandleTypeDef *encoder);  /* 累计距离，米；有符号 */
  void  Encoder_ResetOdometry(Encoder_HandleTypeDef *encoder);       /* 累计计数清零 */
  ```
  换算：`total_count / counts_per_rev * (3.14159265f * WHEEL_DIAMETER_M)`。
- 轮径为 0 时直接返回 0.0f，避免误导（**不要**填猜测的轮径）。
- 在 `control.h/.c` 增加转发接口 `float Control_GetDistanceM(uint32_t index);`，便于 Watch 观察四路累计距离。
- **不要**改 `total_count` 的累加方式和类型（int32_t 在 32 位 MCU 上原子读，够用）。

## 7. 硬件约束

```text
M1: PE9/PE0/PE1/TIM3/PA6/PA7    M2: PE11/PE2/PE3/TIM4/PD12/PD13
M3: PE13/PE4/PE5/TIM5/PA0/PA1   M4: PE14/PE6/PE7/TIM2/PA5/PB3
编码器 1320 计数/圈，四倍频，direction 全 +1
TIM1 PWM 周期 8399（约 20 kHz）
PB6/PB7 = I2C1 OLED（128x64）
```

## 8. 控制周期与安全要求

```text
1 ms 采样 / 100 ms RPM+PID 窗口 —— 本次不改，周期方案待裁决（见 §12）
保持 CONTROL_OPEN_LOOP = 1、CONTROL_OPEN_LOOP_DUTY = 0
CONTROL_TARGET_RPM 本派单保持 60（因为还在开环、DUTY=0，车不会动）
绝不切闭环、不改 PID 参数、不改电机输出行为
切闭环前必须先把 CONTROL_TARGET_RPM 改为 0，或由人类现场写入目标速度 —— 见 §12 方案
上电默认停车；PWM 和输出限幅保持现状
PID 循环禁止 HAL_Delay()
不动 GPIO / 定时器 / 方向逻辑 / CubeMX
```

## 9. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新的 `breathing.hex`。
2. OLED 驱动模式四行分别显示 M1~M4 的 RPM + 占空比，数值稳定可读，不再显示 N/A。
3. 手推轮子时 RPM 正负号与前进方向一致；静止时归零。
4. **W1 回归检查**：`encoder.c` 的 `speed_rpm` 公式与修改前逐字一致，只多出注释；没有出现 `0.001f` 或任何放大 1000 倍的改动。
5. Watch 可读到四路 `total_count`、`speed_rpm`（数值未变）、`distance_m`（轮径为 0 时应为 0）。
6. 电机行为不变：上电后车不动，`Motor_SetOutput()` 仍输出 0。
7. 未触碰任何「禁止修改」文件。

## 10. 测试方法（人类执行，WorkBuddy 整理记录）

```text
1. Keil Build，把 0 Error / 0 Warning 结果和 hex 时间戳发回
2. 下载固件，上电确认车不动、OLED 四行正常显示
3. 手推 M1 前进，观察 OLED RPM 符号 + Watch 中 total_count 增量
4. 依次测 M2/M3/M4，四路符号应一致
5. 提供实测轮径后，手推整圈，distance_m 应约等于轮周长
```

## 11. 回传要求

```text
1. 修改文件清单（逐文件说明改了什么）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 新增 / 变动的 Watch 变量名与含义
4. W1 确认：speed_rpm 公式未改动，只加注释
5. 遗留问题（尤其：轮径仍需人类实测填入；PID 周期待裁决）
6. 是否建议进入「PID 接入」下一步
```

---

## 12. 正式待裁决项（实现模型不得自行决定）

### 12.1 PID 周期口径冲突

```text
TASK_STAGE_01_PID.md：PID 周期 1 ms
control.c：1 ms 采样，100 ms 计算 RPM / PID
```

三个候选方案，**本派单不改任何周期数值**，等人类 / Codex 拍板：

| 方案 | 内容 | 说明 |
|---|---|---|
| A | 改成 1 ms PID | 每 1 ms 用瞬时 speed_rpm 做 PID；需重新评估低速噪声与控制稳定性 |
| B | 明确当前阶段是 100 ms PID | 承认现状，修订任务单口径；优点是有实车依据（低速读数稳定），缺点是控制延迟 100 ms |
| C | 1 ms 采样，10～20 ms 计算速度和 PID | 折中：窗口缩短降低延迟，同时比 1 ms 抗噪；需重新验证低速读数 |

裁决后由 WorkBuddy 更新 `AI_COLLAB/AI_SYNC.md` §7 第 1 条并出后续派单；**Argon4 不得自行选一个实现**。

### 12.2 闭环切换前目标必须归零

当前 `CONTROL_TARGET_RPM = 60`。虽然开环 `DUTY=0` 时车不动，但一旦切 `CONTROL_OPEN_LOOP=0` 会立即尝试跑到 60 RPM。

闭环派单（派单 02）中必须满足其一：

```text
(1) 先把 CONTROL_TARGET_RPM 改为 0，再切闭环；或
(2) 明确要求人类在现场写入目标速度后才允许闭环运行
```

**下一位接手者提示**：本派单只做编码器基础，不含 PID 整定。PID 接入是下一张派单，等本单验收 + 轮径回填 + 周期方案裁决后才能出。
