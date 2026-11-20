# 派单 02 — 接入 1 ms 速度 PID（方案 A）

> 致 Argon4：本任务按人类用户 2026-11-19 20:20 裁决的**方案 A（1 ms PID）**执行。**只改列出的文件。**
> 派单人：WorkBuddy ｜ 时间：2026-11-19 20:20 ｜ 依据：`AI_COLLAB/AI_SYNC.md` §5 待办 2c / §7 第 1 条
> 前置状态：派单 01 全部完成（编码器测速 + 里程计 + 轮径 66.404 mm 已实车验证）

---

## 1. 目录约定

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB（AI_SYNC.md / AI_WORKLOG_WORKBUDDY.md / CHANGELOG.md / DISPATCHES\ / ACCEPTANCE\）
```

下文 `Core/...`、`MDK-ARM/...` 相对 **Keil 工程目录**。

**文件名**：实际是 `pid.h/.c` 与 `control.h/.c`。任务单里的 `motor_pid.h/.c` 不存在，不要找、不要新建。

## 2. 任务目标

把四轮速度环从「1 ms 采样 + 100 ms 计算 + 开环输出」切换为**每 1 ms 计算一次 PID 并输出**，同时保证切换瞬间车不会自己跑。

⚠️ **方案 A 是人类在明确知悉量化噪声风险后拍板的**，WorkBuddy 已提示：60 RPM 时 1 ms 窗口仅 1.32 个计数，量化误差 ±76%、低速易读 0。因此**本派单的抗噪声保护是强制项，不是可选优化**；若实现后实测无法收敛，如实回传，**不得自行退回 100 ms 或 20 ms**。

## 3. 当前代码状态（核对时间 2026-11-19 20:20）

| 项 | 当前值 |
|---|---|
| 控制时序 | `SysTick_Handler` → `Control_Update()` 每 1 ms 采样 `Encoder_Update()` 累加；每 `CONTROL_PID_PERIOD_MS=100` 才算 RPM 并输出 |
| 当前宏 | `CONTROL_TARGET_RPM=60.0f`、`PID_PERIOD_MS=100U`、`PID_DT=0.1f`、KP=0.1/KI=0/KD=0、`OPEN_LOOP=1`、`OPEN_LOOP_DUTY=0`、`TEST_MODE=0` |
| 测速来源 | `motorSpeedRpm[i] = speedCountAccum[i] * 60000 / (1320 * 100)`（100 ms 窗口） |
| 瞬时 RPM | `encoder->speed_rpm = delta * 60000 / counts_per_rev`（1 ms 瞬时值，**公式正确不得改动**） |
| 编码器 | 1320 计数/圈，四路 direction=+1；轮径 `WHEEL_DIAMETER_M=0.066404f` |
| PID 实现 | `pid.c` 位置式，输出 ±100 限幅、微分先行、条件积分抗饱和；`PID_Compute(pid, measurement, dt)` |
| 构建 | 11-18 22:12:13 hex，0 Error / 0 Warning，Code=9996 |
| OLED | 驱动模式四行显示 M1~M4 的 RPM（1 位小数、带符号）+ 占空比（%） |

## 4. 允许修改（仅限）

```text
Core/Inc/control.h
Core/Src/control.c
MDK-ARM/breathing.uvprojx（仅当确需新增 .c 时；尽量不新增）
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc
Core/Src/tim.c / motor.c / gpio.c / stm32f4xx_it.c
Core/Inc/main.h
Core/Inc/encoder.h / Core/Src/encoder.c   ← 派单 01 成果，含正确公式与实测轮径，一律不许动
Core/Inc/pid.h / Core/Src/pid.c            ← PID 算法本体不动，只从 control.c 调用
Core/Src/main.c / oled.c / i2c.c           ← OLED 显示逻辑本次不改
docs/*、AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md、DISPATCH_*.md
```

**绝对禁止**：改 `encoder.c` 第 78-79 行的 `speed_rpm` 公式，或引入 `0.001f` 分母变体。

## 6. 具体工作项

### W1 — 周期改为 1 ms（必做）

**周期来源已确定：继续用现有 SysTick，不开新定时器中断。**

- `SysTick_Handler` 已经每 1 ms 调用 `Control_Update()`（`HAL_IncTick()` 之后），1 ms 周期天然存在。**不要新建 TIM6/TIM7 等定时器中断，不要改 `.ioc` / `tim.c` / `stm32f4xx_it.c`** —— 这些是任务单禁止文件，且现有 SysTick 已足够。
- 方案 A 的实现动作就是：**去掉「每 100 ms 才算一次」的分频判断**，让 `Control_Update()` 每次被 SysTick 调用都完成「读编码器 → 算 RPM → 滤波 → 算 PID → 输出占空比」。
- 原来的 `pidWindowCount` 若还要给 Watch 提供 100 ms 诊断快照（`debugNet` / `debugAbs`），可改名为 `diagWindowCount` 单独保留，**但它绝不能参与 PID 触发判断**。
- `CONTROL_PID_DT` 改由新周期派生：`((float)CONTROL_PID_PERIOD_MS / 1000.0f)`，其中 `CONTROL_PID_PERIOD_MS = 1U`（即 0.001f）。
- `encoder.c` 的 `speed_rpm` 是 1 ms 瞬时值，可作为 PID 测量输入的候选；但**必须先经 W2 滤波**，不得直接喂给 PID。
- 保留 `Control_GetSpeedRpm()` 的语义：OLED 和 Watch 应看到**送给 PID 的同一个滤波后速度值**，避免屏上看一套、PID 吃另一套。
- `encoder.c` 的 `speed_rpm` 是 1 ms 瞬时值，可作为 PID 测量输入的候选；但**必须先经 W2 滤波**，不得直接喂给 PID。
- 保留 `Control_GetSpeedRpm()` 的语义：OLED 和 Watch 应看到**送给 PID 的同一个滤波后速度值**，避免屏上看一套、PID 吃另一套。

### W2 — 1 ms 测速抗噪声保护（**强制项**）

1 ms 窗口量化严重（静止时 delta 常为 0，动起来常为 1~2 计数），必须做平滑。要求：

- 在主控侧（`control.c`）为每路维护一个滤波后的速度变量，例如 `motorSpeedFiltered[MOTOR_COUNT]`。
- 采用**一阶低通**或**N 点滑动平均**（建议 8~16 点，或 alpha 约 0.2~0.3 的一阶滤波），把 1 ms 原始 RPM 平滑后再送 PID。
- 滤波只作用于**测量值**，不改变 `PID_Compute()` 内部、不改变 `encoder.c` 的原始计数与 `speed_rpm`。
- 滤波系数/点数用宏定义放在调参区并注释说明，方便后续调。
- 加**低速零计数保护**：连续多个 1 ms 窗口 delta=0 时速度按 0 处理，避免抖动放大；但 Don't dead-zone 到影响正常低速跟踪（阈值要小，且注释说明）。

### W3 — 闭环切换前目标归零（**安全红线**）

- 把 `CONTROL_TARGET_RPM` 从 `60.0f` 改为 **`0.0f`**。
- `CONTROL_OPEN_LOOP` 从 `1` 改为 `0`（切闭环）。
- 顺序要求：**目标归零后才允许闭环生效**。上电默认 `TARGET=0` → PID 目标 0 → 输出 0 → 车不动。现场需要跑车时，由人类通过 Watch 写入目标速度。
- 保留 PID 目标可写接口（如 `Control_SetTargetRpm(index, rpm)` 或暴露 `motorTargetRpm` 给 Watch），便于人类现场写目标；接口形式在回传中说明。

### W4 — PID 参数与限幅（保持）

- KP=0.1 / KI=0 / KD=0 保持不动（本派单只改周期与目标，不做整定）。
- 输出限幅 ±100、积分限幅、`PID_Compute()` 内部逻辑一律不动。
- 每 1 ms 调用 `PID_Compute()` 时 `dt` 传 `CONTROL_PID_DT`（=0.001f）。
- 积分项注意：`KI=0` 时积分不生效，但 `PID_Compute()` 内部的积分累加仍按 `dt=0.001f` 进行 —— 周期从 0.1 改成 0.001 后，同样的 KP/KI 数值物理意义变了 100 倍；本次 KI=0 所以暂不影响，但要在回传中明确提醒「后续加 KI 时必须重新整定」。

### W5 — 保留诊断

- `debugNet` / `debugAbs` 的 100 ms 诊断窗口如依赖原 100 ms 分支，需保留一个独立的诊断计数器，不要因改周期而丢失 Watch 变量。
- 不得在 PID 循环中使用 `HAL_Delay()` 或任何阻塞调用。

## 7. 硬件约束与安全

```text
编码器 1320 计数/圈，四路 direction=+1，轮径 0.066404f
TIM1 PWM 周期 8399（约 20 kHz）；SysTick 1 ms 调用 Control_Update()
上电默认停车：TARGET=0 → 输出 0 → 车不动
输出 ±100 限幅、积分限幅保留；PID 循环禁止 HAL_Delay
不改 GPIO / 定时器 / 方向逻辑 / CubeMX / OLED
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
2. **上电安全**：烧录后车不动；OLED 四行显示 `0000.0 RPM  000%`（目标 0）。
3. **1 ms 生效**：PID 每 1 ms 计算一次；Watch 中滤波后速度随手推连续平滑变化，不是 0/45/90 这样跳变的离散值。
4. **符号一致**：手推前进四路速度为正、后拉为负，停稳回 0（滤波衰减后归零）。
5. **无异常抖动**：静止时输出占空比稳定 0，无明显抖动或异响；低速手推时速度读数可用。
6. `encoder.c` 的 `speed_rpm` 公式逐字未改；未触碰任何禁止文件。
7. 回传中给出：滤波方案与系数、目标写入接口形式、Watch 变量名与含义。

## 9. 测试方法（人类执行）

```text
1. Keil Build → 记录 0 Error / 0 Warning 与 hex 时间
2. 烧录，上电：确认车不动、OLED 显示 0000.0 RPM / 000%
3. 手推 M1 前进/后拉，观察 OLED 与 Watch 速度是否平滑、符号是否正确
4. 静止观察 10 s：占空比是否稳定 0、有无抖动异响
5. 人类现场写入一个小目标转速（如 20~30 RPM）短时观察，随时准备断电急停
6. 记录数据回传 WorkBuddy 整理
```

## 10. 回传要求

```text
1. 修改文件清单（逐文件说明改了什么）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. W2 滤波方案（一阶/滑动平均、系数/点数、低速保护阈值）
4. W3 目标写入接口形式（Watch 变量名或函数名）
5. 新增/变动的 Watch 变量名与含义
6. 遗留问题与风险（尤其 1 ms 低速表现）
7. 是否建议进入 PID 参数整定
```

---

**下级提示**：本派单只做「周期切换 + 安全归零 + 抗噪声」，**不做 KP/KI 整定**。整定要等本单实测稳定后进行，另出派单 03。若 1 ms 实测确实无法稳定（持续抖动/读数离散），如实回传，由人类重新裁决，实现模型不得自行换方案。
