# 派单 S2-02 — 差速底盘运动学（vx/omega → 四轮 RPM）

> 致 Argon4：本任务实现差速底盘运动学解算，把 `vx/omega` 转成四轮目标 RPM 并下发。**不做里程计积分（S2-03）、不接 IMU（S2-04）。**
> 派单人：WorkBuddy ｜ 时间：2026-11-20 21:00 ｜ 依据：`AI_COLLAB/PLAN_STAGE_02.md` S2-02 与 §七细则
> 前置：S2-01 接口骨架已交付（20:50 hex）；轮距已粗测约 0.20 m

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

下文 `Core/...` 以 Keil 工程目录为基准。实际文件名 `pid.h/.c`、`control.h/.c`、`encoder.h/.c`、`chassis.h/.c`。

## 2. 任务目标

把 S2-01 的「锁存目标」真正变成「四轮 RPM 下发」：

```text
Chassis_SetVelocity(vx, omega) 锁存
        ↓
Chassis_Update(dt) 每 1 ms 解算：
  left_speed  = vx − omega × track/2
  right_speed = vx + omega × track/2
        ↓
线速度 → RPM（乘 motorGain[i]，±250 等比饱和）
        ↓
Control_SetTargetRpm(i, rpm) 下发四路
```

**支持**：直行、原地旋转、弧线旋转、停车。**禁止**：vy、斜行、横移、麦克纳姆公式。

## 3. 当前代码状态（核对时间 2026-11-20 20:55）

| 项 | 当前值 |
|---|---|
| S2-01 骨架 | `chassis.h/c` 已建；`Chassis_SetVelocity()` 只校验 + 锁存 `chassisTargetVx/Omega`，**不换算、不下发** |
| 调用链 | `Control_Init()` 末尾调 `Chassis_Init()`；`Control_Update()` 中调 `Chassis_Update(CONTROL_PID_DT)`（1 ms） |
| 轮距变量 | `chassisTrackWidthM = 0.0f`（默认未标定），Watch 可写 |
| **轮距实测** | **约 0.20 m（人类 20:59 粗测，后期校准）** |
| 增益/比例 | `motorGain[4]={1,1,1,1}`、`wheelScale[4]={1,1,1,1}`（分开独立） |
| 限幅宏 | `CHASSIS_MAX_VX_MPS=0.869f`、`CHASSIS_MAX_OMEGA_RADS=6.0f`（在 chassis.h） |
| PID | 1 ms，KP=0.4/KI=2.5/KD=0，输出 ±100，`CONTROL_TARGET_RPM=0` |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`、`DUTY=0`、`controlCalibrationMode=0`，上电不跑 |
| 构建 | 20:50:21 hex，0 Error / 0 Warning |

**验算提示**：轮距 0.20 m 对应理论 omega 上限 `2×0.869/0.20 = 8.69 rad/s`；当前 `CHASSIS_MAX_OMEGA_RADS=6.0` 是按旧粗估 0.29 m 算的，**偏保守但安全**。本单按实测轮距重算并注明依据（见 W3）。

## 4. 允许修改（仅限）

```text
Core/Inc/chassis.h
Core/Src/chassis.c
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc / Core/Src/tim.c / motor.c / gpio.c / stm32f4xx_it.c / main.c / main.h
Core/Inc/control.h / Core/Src/control.c   ← S2-01 成果，调用点与 PID 全不动
Core/Inc/encoder.h / Core/Src/encoder.c   ← 轮径与 speed_rpm 公式不动
Core/Inc/pid.h / Core/Src/pid.c
Core/Src/oled.c / i2c.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 PID 参数/安全宏；改 `encoder.c` 公式；改 CubeMX/引脚/定时器；接 IMU 硬件；引入 `0.001f` 分母变体。

## 6. 具体工作项

### W1 — 差速解算（必做）

在 `Chassis_Update(dt)` 里实现（**这是本单核心**）：

```c
float track = chassisTrackWidthM;
float vx = chassisTargetVx;
float omega = chassisTargetOmega;

float left_mps  = vx - omega * track * 0.5f;
float right_mps = vx + omega * track * 0.5f;
```

- 线速度 → RPM：`rpm = v_mps * 60.0f / (3.14159265f * 0.066404f)`（≈ `v_mps * 287.6`）。**轮径宏在 encoder.h，只读、不改**。
- 左 = M1/M3（索引 0/2），右 = M2/M4（索引 1/3）。
- `omega>0`（逆时针/左转）→ 左轮慢、右轮快，与公式一致。
- **轮距未标定保护**：`chassisTrackWidthM <= 0` 时不做解算、不下发（`Chassis_SetVelocity()` 已在 S2-01 拒绝 omega≠0，这里是双保险）。
- **`dt` 参数本单不用于积分**（里程计是 S2-03），只保留接口；可做 `(void)dt` 或注释说明。

### W2 — 增益、饱和与下发（必做）

- 每轮 RPM 乘对应 `motorGain[i]`（默认 1.0）：
  `rpm_cmd[i] = base_rpm_left_or_right * motorGain[i]`
- **±250 RPM 等比饱和**：先算四路目标，若任一 `|rpm| > 250`，取 `k = 250 / max(|rpm_i|)`，**四轮同乘 k**，保持 vx:omega 比例（单侧独立截断会破坏差速关系、导致 yaw 漂移）。缩放后再逐轮保险限幅 ±250。
- 下发：调用 `Control_SetTargetRpm(i, rpm_cmd[i])` 写四路目标。**本单不直接调 `Motor_SetOutput()`** —— 速度环仍由 `control.c` 的 PID 每 1 ms 闭环。
- **停车语义**：`vx=0 且 omega=0` 时四路目标 RPM 写 0（车停）。

### W3 — 轮距与 omega 上限（必做）

- `chassisTrackWidthM` 保持**可写变量**，默认填 **0.20f**（人类实测几何值）。**不要写成 const 或宏**：S2-05 会用原地旋转标定精修等效轮距，届时 Watch 直接改、不重编译。
- `CHASSIS_MAX_OMEGA_RADS` 由 6.0f 改为 **8.5f**（按实测轮距 0.20 m 算得 8.69 rad/s，取 8.5 留余量）；`CHASSIS_MAX_VX_MPS=0.869f` 不变。回传说明依据。
- 注释写明：0.20 m 是几何粗测值，S2-05 将用 `track=(右累计距离−左累计距离)/π` 标定等效轮距后覆盖。

### W4 — 保留与隔离（必做）

- S2-01 的接口签名、`SetVelocity()` 的校验/锁存逻辑、`imuAvailable`/IMU 桩函数全部保留。
- `chassisCmdRejected` 仍按 S2-01 语义（拒收时置 1）；本单解算不额外改它。
- `wheelScale[]` 本单不参与（留给 S2-03 里程计）。
- 不改 OLED 显示、不动 PID/安全宏、上电默认停车不变。

## 7. 安全要求

```text
上电默认停车：TARGET_RPM=0，四轮目标 0
轮距 <=0 时拒绝解算与下发
|vx| > 0.869 m/s 截断；|omega| > 8.5 rad/s 截断
四轮目标一律 ±250 RPM 等比饱和，禁止单侧独立截断
PID 输出 ±100 限幅保持；PID 循环禁 HAL_Delay
不改 CubeMX / 引脚 / 定时器；不接 IMU
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
2. 上电安全：车不动，OLED 四行 `0000.0 RPM  000%`（目标仍 0，不会自行跑）。
3. **静态代码核对**：`Chassis_Update()` 内有差速公式、`287.6` 换算、`motorGain` 相乘、四轮 ±250 等比饱和、`Control_SetTargetRpm()` 调用；无 `vy`/麦克纳姆公式；无 `Motor_SetOutput()` 直驱。
4. **直行**（Watch 写 `chassisTargetVx=0.2`、`omega=0` 或人类现场方式）：四轮同向、RPM 正值、数值约 `0.2×287.6≈57.5 RPM`（乘 gain 后）。
5. **原地旋转**（轮距已填 0.20 后，写 `vx=0`、`omega=1.0`）：左右侧反向，左约 `−0.1×287.6≈−28.8`、右约 `+28.8 RPM`。
6. **停车**：`vx=0/omega=0` 时四路目标回 0。
7. 未触碰禁止文件；`encoder.c` 公式与 PID 参数未改。

> **注**：人类现场不用 Watch 改变量。运行时验收可在 S2-02 里通过「改 `chassisTargetVx/Omega` 初值重编看 OLED」完成（远程下发通信已移出阶段 2，归属待定）。**若实车测试不便，至少完成 1~3 静态核对 + 上电不跑，运行时现象留到 S2-TEST 统一验收。**

## 9. 测试方法（人类执行）

```text
1. Keil Build，记录 0 Error / 0 Warning 与 hex 时间
2. 烧录，上电确认车不动、OLED 0000.0 RPM 000%
3. 静态核对 §8 第 3 条（看源码）
4. 若现场可测：写目标/改初值 → 看 OLED 四路 RPM 与方向，记录
5. 回传
```

## 10. 回传要求

```text
1. 修改文件清单
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 差速解算代码片段（左/右速度、RPM 换算、gain、饱和、下发）
4. omega 上限改为 8.5 的依据；轮距默认 0.20f 的确认
5. 实测现象（直行/旋转/停车）或注明「运行时留 S2-TEST」
6. 遗留问题与风险
7. 是否建议进入 S2-03（整车里程计）
```

---

**下一位提示**：本单只做运动学解算与 RPM 下发。S2-03 才用四轮累计距离积分整车 `x/y/yaw`（禁用 1 ms 瞬时 RPM）；S2-04 才接 IMU；S2-05 用原地旋转标定精修轮距与增益。若接口需调整，**先回报 WorkBuddy，不要自行改**。
