# 派单 03 — 开环标定 + KP/KI 整定 + 四轮阶跃验收

> 致 Argon4：本任务完成阶段 1 的最后一块 —— 标定、整定、验收。**只改列出的文件。**
> 派单人：WorkBuddy ｜ 时间：2026-11-19 20:35 ｜ 依据：`AI_COLLAB/AI_SYNC.md` §5 待办 2e
> 前置：派单 01（编码器 + 里程计 + 轮径 66.404 mm）✅、派单 02（1 ms 闭环 PID + 目标归零）✅

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB（AI_SYNC.md / AI_WORKLOG_WORKBUDDY.md / CHANGELOG.md / DISPATCHES\ / ACCEPTANCE\）
```

下文相对 **Keil 工程目录**。实际文件名是 `pid.h/.c`、`control.h/.c`，**不是**任务单里的 `motor_pid.h/.c`。

## 2. 当前状态（WorkBuddy 核对，2026-11-19 20:35）

| 项 | 当前值 |
|---|---|
| 控制周期 | 1 ms（`SysTick` → `Control_Update()`，方案 A） |
| 测速 | `delta` → 一阶低通 `ALPHA=0.20` + 连续 20 ms 零计数保护 → `motorSpeedFiltered[]` |
| 闭环 | `CONTROL_OPEN_LOOP=0`；`CONTROL_TARGET_RPM=0.0f`（上电不跑，已实车确认） |
| **开环占空比宏** | **`CONTROL_OPEN_LOOP_DUTY=20`**（派单 02 由 0 改为 20，闭环下不生效） |
| PID 参数 | KP=0.1 / KI=0 / KD=0，输出 ±100 限幅，**未整定基线** |
| 目标接口 | `Control_SetTargetRpm(i, rpm)` / `Control_GetTargetRpm(i)` / 全局 `motorTargetRpm[0..3]`（Watch 可写） |
| 诊断 | 100 ms 窗口 `debugNet[]` / `debugAbs[]` |
| OLED | 四行显示 M1~M4 的 RPM（1 位小数带符号）+ 占空比（%） |
| 实车基线 | 手推前进：RPM 正且平滑、输出占空比为负（负反馈阻力正确）；未给非零目标 |
| 编译 | 20:33:07 hex，0 Error / 0 Warning，Code=10272 |

⚠️ **两个已知坑**：
1. `dt` 已从 0.1 变成 0.001，**同样 KP/KI 数值的物理意义变了 100 倍**（P 项不变，I/D 项按 dt 累加/计算）。当前 KI=KD=0 不受影响，但整定时必须按 1 ms 重新定，不能照搬任何 100 ms 时代的参数。
2. 开环占空比起点是 **20% 不是 0%**。开环测试前必须确认目标归零、从低占空比逐步加，防止突然冲速。

## 3. 任务目标

1. 提供**可现场扫占空比**的开环标定能力（不改宏、不重编译就能改占空比）。
2. 用标定数据支撑 KP/KI 初值选择。
3. 完成四轮阶跃测试与一致性验收，产出阶段 1 验收记录所需数据。

**本派单不做**：PID 算法本体改动、`.ioc`/定时器/GPIO/编码器/电机底层改动、OLED 布局改动。

## 4. 允许修改（仅限）

```text
Core/Inc/control.h
Core/Src/control.c
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc
Core/Src/tim.c / motor.c / gpio.c / stm32f4xx_it.c
Core/Inc/main.h
Core/Inc/encoder.h / Core/Src/encoder.c    ← 含正确 speed_rpm 公式与实测轮径，一律不许动
Core/Inc/pid.h / Core/Src/pid.c            ← PID 算法本体不动
Core/Src/main.c / oled.c / i2c.c           ← OLED 显示本次不改
docs/*、AI_COLLAB/CHANGELOG.md、AI_COLLAB/AI_SYNC.md、AI_COLLAB/AI_WORKLOG_WORKBUDDY.md、DISPATCH_*.md
```

**绝对禁止**：改 `encoder.c` 的 `speed_rpm` 公式或引入 `0.001f` 分母变体。

## 6. 具体工作项

### W1 — 可写的开环占空比与标定模式（必做）

- 在 `control.c` 暴露一个可写变量 `motorOpenLoopDuty[MOTOR_COUNT]`（`int16_t`，范围 -100～+100），并在 `control.h` 中 `extern` 导出供 Watch 写入。
- `CONTROL_OPEN_LOOP=1` 时，用 `motorOpenLoopDuty[i]` 代替固定的 `CONTROL_OPEN_LOOP_DUTY` 输出到电机；`CONTROL_OPEN_LOOP=0` 时该变量不影响闭环。
- **默认值必须为 0**（不是 20）：`static int16_t motorOpenLoopDuty[MOTOR_COUNT] = {0,0,0,0};`。这样即使误切开环也不会突然冲速。
- 增加一个**可由 Watch 写入的全局变量** `controlCalibrationMode`（`uint8_t`，默认 **0**），在 `control.h` 中 `extern` 导出。**不要用 `#define` 宏** —— 宏是编译期的，现场改不了。
  - 为 1 时：强制开环输出 `motorOpenLoopDuty[i]`，且**不走 PID**；
  - 为 0 时：按正常闭环逻辑运行（派单 02 的行为）；
  - 两种模式都必须先经过目标归零检查。
- 回传里说明：人类如何用 Watch 切标定模式 / 写占空比，以及退出标定的步骤。

### W2 — 可写的 PID 参数（必做）

- 把 KP/KI/KD 从纯宏改为**可由 Watch 写入的全局变量**（如 `motorKp` / `motorKi` / `motorKd`，`float`），并在 `control.h` 中 `extern` 导出。
- 默认值保持 `0.1f / 0.0f / 0.0f`。
- 每 1 ms 闭环计算前把当前变量值同步到 `motorPid[i]`（或提供 `Control_SetGains()` 并在写变量时调用），保证 Watch 改参数后立即生效，不需要重新编译。
- 输出限幅 ±100 与积分限幅保持不动。

### W3 — 整定过程的安全约束（必做）

```text
1. 开环标定：CONTROL_CALIBRATION_MODE=1，motorOpenLoopDuty 从 0 开始，
   按 10% 步进逐级加到 60%，每级记录四路稳态 RPM。
2. 任何时刻目标 motorTargetRpm[] 必须为 0（开环阶段 PID 不参与）。
3. 标定结束：占空比先回 0，再退出标定模式（CONTROL_CALIBRATION_MODE=0）。
4. 切闭环前再次确认 motorTargetRpm[]=0，然后将 KP/KI 写入变量，
   由人类现场用小目标（20~30 RPM）观察，随时准备断电急停。
5. PID 循环禁止 HAL_Delay；输出与积分限幅不允许取消。
```

### W4 — 保留现有能力（必做）

- 1 ms 周期、一阶低通 + 零计数保护、目标写入接口、100 ms 诊断窗口、里程计接口、OLED 显示 —— 全部保持不变。
- `Control_GetSpeedRpm()` 继续返回滤波后速度，保证屏上与 PID 一致。

## 7. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
2. 上电安全：静止车不动，OLED `0000.0 RPM 000%`。
3. Watch 可写 `motorOpenLoopDuty[0..3]`、`motorKp/Ki/Kd`、`motorTargetRpm[0..3]`，写入后立即生效、不需重编译。
4. 标定模式可正常切换；退出后闭环行为与派单 02 一致（手推负反馈、松手回零）。
5. 未触碰任何禁止文件；`encoder.c` 公式未改。
6. 回传：Watch 变量清单与写入步骤、标定/整定的操作顺序。

## 8. 测试方法（人类执行，WorkBuddy 整理记录）

```text
A. 开环标定
   1. Watch 设 controlCalibrationMode=1，motorOpenLoopDuty 四路都为 0
   2. 逐级写 10/20/30/40/50/60%，每级等转速稳定后记录 M1~M4 的 RPM
   3. 占空比回 0 → controlCalibrationMode 设回 0 退出标定
B. 参数整定
   4. Ki=0，按标定曲线估 KP 初值写入，观察小目标阶跃响应
   5. 逐步加大 Kp 至出现轻微超调后回退；再加 Ki 消稳态误差
   6. 记录最终 KP/KI 与对应的稳态误差、超调、稳定时间
C. 验收
   7. 四轮分别做 0→200、0→400、400→0、正反转
   8. 四轮统一 400 RPM 直行一致性测试
   9. 目标 0 时确认可靠停车
```

## 9. 回传要求

```text
1. 修改文件清单
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. Watch 变量清单（名称、类型、默认值、含义）与写入步骤
4. 标定模式 / 退出标定的操作顺序
5. KP/KI 初值估算依据（基于哪组占空比→RPM 数据）
6. 遗留问题与风险
7. 是否建议进入阶段 1 验收评审
```

---

**下一位接手者提示**：本派单完成后，人类按 §8 实测并把数据交给 WorkBuddy 整理成阶段 1 验收记录；随后阶段 1 收尾，交 Codex 接 MiMo 做总览与版本规划。若 1 ms 闭环实测无法收敛，回报人类重新裁决，**实现模型不得自行改周期或绕过整定**。
