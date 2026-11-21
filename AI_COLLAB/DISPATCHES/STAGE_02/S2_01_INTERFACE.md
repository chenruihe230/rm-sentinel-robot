# 派单 S2-01 — 阶段 2 接口与数据结构（v2 修订版）

> 致 Argon4：本任务只建立阶段 2 的接口骨架和数据结构，**不实现运动学算法、不实现里程计积分、不接 IMU 硬件**。
> 派单人：WorkBuddy ｜ 初版：2026-11-20 17:04 ｜ **修订：2026-11-20 19:41（审单 2 阻塞项 + 3 建议全采纳）**
> 依据：`AI_COLLAB/PLAN_STAGE_02.md` S2-01 与 §七细则
> 前置：阶段 1 已正式交付（安全基线：目标 0、开环关、PID 1 ms、KP=0.4/KI=2.5/KD=0）

> **v2 修订要点**（相对初版）：
> 1. `Core/Src/control.c` 加入允许清单，严格限定只改两个调用点（否则 `CONTROL_PID_DT` 与 1 ms 周期无处可调）；
> 2. `Chassis_SetVelocity()` 语义定死：仅限幅校验 + 锁存目标，不换算 RPM、不下发电机；新增可观测状态变量与拒绝标志；
> 3. IMU 不可用标记定死为 `imuAvailable` + `IMU_IsAvailable()`；
> 4. omega 上限依据写清，并注明 S2-02 仍需按实测轮距做饱和/等比缩放；
> 5. 验收改为「静态核对 + 上电不跑」为主，运行时指令测试留 S2-02（人类不用 Watch）。

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

下文 `Core/...` 以 Keil 工程目录为基准。实际文件名是 `pid.h/.c`、`control.h/.c`、`encoder.h/.c`，**不是**旧任务单里的 `motor_pid.*`。

## 2. 任务目标

建立阶段 2 的接口与数据结构，为 S2-02（运动学）、S2-03（里程计）、S2-04（IMU）打骨架。**本单只定接口、不写算法**。

⚠️ 用户裁定：实现细则由 WorkBuddy 定，Codex 只做规划；IMU 选型与引脚到 S2-04 前再单独立项，本单不许接 IMU 硬件、不许改 CubeMX。

## 3. 当前代码状态

| 项 | 当前值 |
|---|---|
| 控制 | `SysTick` 1 ms → `Control_Update()` → 读编码器 → LPF 0.20 + 20 ms 零保护 → PID → 输出 |
| PID 参数 | KP=0.4 / KI=2.5 / KD=0，输出 ±100，1 ms（`CONTROL_PID_DT` 定义在 `control.c`） |
| 目标接口 | `Control_SetTargetRpm(i, rpm)` / `Control_GetTargetRpm(i)` / `motorTargetRpm[0..3]` |
| 里程计接口 | `Encoder_GetDistanceM(i)` / `Encoder_ResetOdometry(i)` / `Control_GetDistanceM(i)` |
| 轮径 | `WHEEL_DIAMETER_M = 0.066404f`（共用） |
| 编码器 | 1320 计数/圈，`direction` 全 +1；`total_count` 与 `distance_m` 已有 |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`、`DUTY=0`、`controlCalibrationMode=0` |
| 构建 | 11-20 16:30 hex，0 Error / 0 Warning |
| 轮序 | M1 左前、M2 右前、M3 左后、M4 右后（见 `main.h` 的 zuoqian/youqian/zuohou/youhou）。**左 = M1/M3，右 = M2/M4** |

## 4. 允许修改（仅限）

```text
Core/Inc/chassis.h       ← 新建
Core/Src/chassis.c       ← 新建
Core/Inc/control.h       ← 仅追加 extern 声明（如需）
Core/Src/control.c       ← 严格限定只改 2 处调用点，见下方 W1
MDK-ARM/breathing.uvprojx ← 新增 chassis.c 时需在 Keil 里 Add
```

**`control.c` 的允许范围（硬限定）**：

1. 在 `Control_Init()` **末尾、`controlInitialized = 1U;` 之前**调用 `Chassis_Init();`；
2. 在 `Control_Update()` 中调用 `Chassis_Update(CONTROL_PID_DT);`（1 ms 周期，DT 用现成宏）；
3. **禁止**改 `control.c` 里任何 PID 参数、`CONTROL_*` 安全宏、滤波系数、零计数保护、诊断窗口、编码器读取逻辑、电机输出逻辑。

> 说明：`CONTROL_PID_DT` 只定义在 `control.c` 内，且 1 ms 控制环也在那里；不放行 `control.c` 就没有合法位置调用 `Chassis_Update()`，同时又不许改 `stm32f4xx_it.c` —— 故本单放行且仅限上述两点。`main.c` 可**完全不动**。

## 5. 禁止修改（硬边界）

```text
breathing.ioc / Core/Src/tim.c / motor.c / gpio.c / stm32f4xx_it.c
Core/Inc/main.h / Core/Src/main.c（本单完全不动）
Core/Inc/encoder.h / Core/Src/encoder.c   ← 轮径与 speed_rpm 公式，一律不许动
Core/Inc/pid.h / Core/Src/pid.c
Core/Src/oled.c / i2c.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 `encoder.c` 的 `speed_rpm` 公式；引入 `0.001f` 分母变体；改 CubeMX 引脚/定时器；接 IMU 硬件；改 `control.c` 里除 W1 两处调用以外的任何内容。

## 6. 具体工作项

### W1 — 接口骨架与调用点（必做，签名定死）

在 `chassis.h` 中定义（**签名不许变**）：

```c
void Chassis_Init(void);
void Chassis_SetVelocity(float vx, float omega);          /* m/s, rad/s */
void Chassis_Update(float dt);                            /* 由 Control_Update 每 1 ms 调用 */
void Chassis_GetPose(float *x, float *y, float *yaw);     /* 指针出参，m / m / rad */
uint8_t IMU_IsAvailable(void);                            /* 本阶段返回 0 */
float IMU_GetYaw(void);                                   /* rad，本阶段返回 0 */
float IMU_GetYawRate(void);                               /* rad/s，本阶段返回 0 */
```

调用点（**仅这两处**）：

- `Control_Init()` 末尾、`controlInitialized = 1U;` **之前**：`Chassis_Init();`
- `Control_Update()` 中：`Chassis_Update(CONTROL_PID_DT);` —— 1 ms 周期，DT 用现成宏，不新定义。

本单内部实现：

- `Chassis_Update(dt)` 只留空实现或状态自检；**不写积分、不写运动学解算**（S2-02/S2-03 的事）。
- `Chassis_GetPose()` 返回全 0，但接口要实现、指针检查要有（NULL 时写 0 返回）。
- `IMU_IsAvailable()` 返回 0；`IMU_GetYaw/GetYawRate()` 返回 0。不接 IMU 硬件。

### W1-b — SetVelocity 行为语义（必做，本单最关键的定义）

**`Chassis_SetVelocity(vx, omega)` 在本单的行为定死为：仅做输入校验 + 锁存目标状态，不换算 RPM、不下发电机。**

```text
1. 校验 |vx| ≤ 0.869f m/s、|omega| ≤ 6.0f rad/s；
2. 若 chassisTrackWidthM ≤ 0（未标定）且 omega ≠ 0 → 拒绝，不更新锁存值，置拒绝标志；
3. 校验通过 → 锁存到 chassisTargetVx / chassisTargetOmega（全局可写）；
4. 不做任何差速分解、不换算 RPM、不调用 Control_SetTargetRpm()、不改电机输出。
   → 本单执行完，车依然不动（TARGET_RPM 仍为 0）。
   真正的换算与下发留到 S2-02。
```

**可观测状态变量（必须定义并 extern 导出供静态核对）**：

```c
extern float chassisTargetVx;        /* 锁存的 vx，默认 0 */
extern float chassisTargetOmega;     /* 锁存的 omega，默认 0 */
extern uint8_t chassisCmdRejected;   /* 最近一次 SetVelocity 是否被拒：1=拒绝，0=接受，默认 0 */
extern uint8_t imuAvailable;         /* IMU 可用性：默认 0（不可用） */
```

- 拒绝时 `chassisCmdRejected = 1` 且**不更新** `chassisTargetVx/Omega`；接受时置 0 并更新锁存值。
- 这几个变量让外部/审查能区分「拒绝 vs 接受」，而不依赖 Watch 运行观测。

### W2 — 数据结构与可调参数（必做）

```c
extern float chassisTrackWidthM;              /* 轮距 m，默认 0.0f —— 未标定 */
extern float motorGain[MOTOR_COUNT];          /* 控制层前馈补偿，默认全 1.0f */
extern float wheelScale[MOTOR_COUNT];         /* 里程计距离修正，默认全 1.0f */
extern float chassisX, chassisY, chassisYaw;  /* 位姿 m / m / rad，默认 0 */
```

- 四路数组统一用 `MOTOR_COUNT`（=4）。
- `motorGain` 与 `wheelScale` **必须分开**，不许合并、不许改 `WHEEL_DIAMETER_M` 掩盖差异。
- `chassisTrackWidthM=0` 表示未标定：拒绝带 omega≠0 的指令（置 `chassisCmdRejected=1`），只接受 omega=0 的直行指令。防的是用错误轮距跑出错误姿态。
- **|vx| ≤ 0.869f m/s** 正确（=250 RPM / 287.6）。**|omega| ≤ 6.0f rad/s** 是按轮距约 0.29 m 估算的上限（250 RPM ≈ 26.2 rad/s 轮速，差速两侧分量差约 0.29 m → 约 6 rad/s 车体角速度）；**S2-02 实际运动学解算时仍需按实测轮距对四轮做 ±250 RPM 饱和 / 等比缩放**，本单的 omega 校验只是粗范围检查，不是最终限幅。

### W3 — 单位与轮序注释（必做）

在 `chassis.h` 顶部写明：

```text
单位：vx = m/s, omega = rad/s, 目标 RPM, 距离 m, 角度 rad
坐标系：+X 前进，+Y 向左，+Z 逆时针（omega>0 = 左转）
轮序：M1 左前 / M2 右前 / M3 左后 / M4 右后；左 = M1,M3；右 = M2,M4
线速度→RPM：rpm = v_mps * 60 / (π * 0.066404f) ≈ v_mps * 287.6
禁止实现 vy / 横移 / 麦克纳姆公式
```

回传中说明 omega 上限取值的依据（见 W2）。

### W4 — 不动的东西（必做）

- 不改任何 PID 参数与安全宏；上电仍默认停车（`TARGET=0`）。
- 不改 OLED 显示（当前 RPM + 占空比保持）；`main.c` 完全不动。
- 不改 `encoder.c` 的瞬时速度公式与轮径。
- 不新增定时器中断 —— `Chassis_Update()` 由 `Control_Update()` 在现有 1 ms SysTick 中驱动。

## 7. 安全要求

```text
上电默认停车，chassisX/Y/Yaw 与锁存目标初值全 0
chassisTrackWidthM 未标定（=0）时拒绝 omega≠0，置 chassisCmdRejected
|vx| > 0.869 m/s 截断；|omega| > 6.0 rad/s 拒绝
本单不换算 RPM、不下发电机，车必须保持不动
motorGain / wheelScale 默认 1.0f
PID 循环禁止 HAL_Delay
CubeMX / 引脚 / 定时器不动
```

## 8. 验收标准（静态核对 + 上电为主，运行时测试留 S2-02）

> 人类现场不用 Watch 改变量，故运行时指令测试不在本单验收，留到 S2-02 联调看屏验证。

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
2. 上电行为与阶段 1 完全一致：车不动，OLED 四行 `0000.0 RPM  000%`。
3. **静态代码核对**（回传中给出文件+行号或片段）：
   - `Chassis_Init()` 在 `Control_Init()` 末尾、`controlInitialized=1U` 之前；
   - `Chassis_Update(CONTROL_PID_DT)` 在 `Control_Update()` 内；
   - `control.c` 除这两处外无其他改动（PID/安全宏/滤波原样）；
   - `chassisTrackWidthM`/`motorGain`/`wheelScale`/`chassisX/Y/Yaw`/`chassisTargetVx/Omega`/`chassisCmdRejected`/`imuAvailable` 均已定义且默认值正确；
   - `Chassis_SetVelocity()` 内无 `Control_SetTargetRpm()`、无 `Motor_SetOutput()`、无 RPM 换算（**本单不下发电机**）。
4. `IMU_IsAvailable()` 返回 0；`IMU_GetYaw()/GetYawRate()` 返回 0。
5. 未触碰任何禁止文件；`encoder.c` 公式未改；无新增中断；`main.c` 未改。

## 9. 测试方法（人类执行）

```text
1. Keil Build，记录 0 Error / 0 Warning 与 hex 时间
2. 烧录，上电确认车不动、OLED 显示与阶段 1 一致（0000.0 RPM 000%）
3. 按 §8 第 3 条做静态代码核对（看源码片段，不看运行时）
4. 运行时 SetVelocity 测试留到 S2-02（届时看 OLED 验证）
```

## 10. 回传要求

```text
1. 修改文件清单（含新建 chassis.h/.c、Keil Add 情况）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 静态核对证据：两个调用点的位置 + control.c 无其他改动的说明
4. 接口签名与全局变量清单（名称、类型、默认值、含义），含拒绝标志与锁存目标
5. omega 上限取值依据
6. 遗留问题与风险
7. 是否建议进入 S2-02（差速运动学）
```

---

**下一位提示**：本单只建骨架、只锁存目标、不下发电机。S2-02 才实现 `left = vx − omega·track/2`、`right = vx + omega·track/2`、RPM 换算、`Control_SetTargetRpm()` 下发与 ±250 等比饱和；S2-03 才做里程计积分；S2-04 才接 IMU 硬件。若发现接口签名需要调整，**先回报 WorkBuddy，不要自行改**。
