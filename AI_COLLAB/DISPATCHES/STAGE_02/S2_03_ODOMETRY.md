# 派单 S2-03 — 整车里程计积分（四轮编码器 → x/y/yaw）

> 致 Argon4：本任务实现整车里程计，用四轮**累计距离**积分出车体位姿。**不接 IMU（S2-04）、不做 IMU 融合、不改运动学解算（S2-02 已完成）。**
> 派单人：WorkBuddy ｜ 时间：2026-11-20 21:13 ｜ 依据：`AI_COLLAB/PLAN_STAGE_02.md` S2-03 与 §七细则
> 前置：S2-01 骨架 ✅、S2-02 差速运动学 ✅（21:11 hex，已恢复停车基线）

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

下文 `Core/...` 以 Keil 工程目录为基准。实际文件名 `pid.h/.c`、`control.h/.c`、`encoder.h/.c`、`chassis.h/.c`。

## 2. 任务目标

把四轮编码器的**累计距离**融合成整车位姿 `x / y / yaw`（以及 `vx / omega` 观测值），写入 `chassisX/Y/Yaw`，供 `Chassis_GetPose()` 与 S2-04 融合使用。

**核心红线：用累计距离增量积分，禁止用 1 ms 瞬时 RPM（`speed_rpm`）积分位姿** —— 后者噪声大，积分会快速发散。

## 3. 当前代码状态（核对时间 2026-11-20 21:13）

| 项 | 当前值 |
|---|---|
| 位姿变量 | `chassisX/Y/Yaw`（`chassis.c` 全局，默认 0），`Chassis_GetPose()` 已实现指针出参 |
| 里程计源 | `Encoder_GetDistanceM(&encoders[i])`（每轮累计距离，m）；已有 `Control_GetDistanceM(i)` 转发 |
| 原始计数 | `Encoder_GetTotalCount()` / `encoders[i].total_count`（int32）保留 |
| 修正系数 | `wheelScale[4]={1,1,1,1}`（已定义，**本单开始使用**，与 motorGain 独立） |
| 轮距 | `chassisTrackWidthM=0.20f`（可写，几何粗测；S2-05 旋转标定精修） |
| 已实现（S2-02） | `Chassis_Update(dt)` 里做 vx/omega → 四轮 RPM → `Control_SetTargetRpm()` 下发；`(void)dt` 占位 |
| 调用链 | `Control_Update()` 每 1 ms 调 `Chassis_Update(CONTROL_PID_DT)` |
| 瞬时速度 | `encoder->speed_rpm`（1 ms 瞬时，**本单禁止用它积分位姿**） |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`，上电不跑；21:11 hex 0 Error / 0 Warning |

## 4. 允许修改（仅限）

```text
Core/Inc/chassis.h
Core/Src/chassis.c
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / stm32f4xx_it.c / main.c / main.h
Core/Inc/control.h / Core/Src/control.c   ← S2-01/02 调用点与 PID 全不动
Core/Inc/encoder.h / Core/Src/encoder.c   ← 轮径与 speed_rpm 公式、累计计数一律不动
Core/Inc/pid.h / Core/Src/pid.c / oled.c / i2c.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 `encoder.c` 公式或轮径；改 `control.c` 的调用点/PID/安全宏；改 CubeMX/引脚/定时器；接 IMU 硬件；用 `speed_rpm` 积分位姿。

## 6. 具体工作项

### W1 — 累计距离差分（必做）

在 `chassis.c` 内增加**每轮上次累计距离**的静态状态（如 `static float prevDistance[MOTOR_COUNT]`），在 `Chassis_Update(dt)` 里：

```c
float d_i = wheelScale[i] * Control_GetDistanceM(i) - prevDistance[i];
prevDistance[i] = wheelScale[i] * Control_GetDistanceM(i);
```

- **用 `Control_GetDistanceM(i)`（累计距离，m）做差分**，不用 `Encoder_GetSpeedRpm()` / `speed_rpm`。
- `wheelScale[i]` 乘在**距离**上（修正里程），不是乘在 RPM 上（那是 S2-02 的 `motorGain`）。两者独立。
- `Chassis_Init()` 里把 `prevDistance[]` 初始化为当前 `wheelScale[i]*Control_GetDistanceM(i)`，避免上电第一帧把历史累计距离当成位移。
- 提供**里程计复位**能力：`Chassis_ResetOdometry()`（新函数，签名 `void Chassis_ResetOdometry(void)`）把 `chassisX/Y/Yaw`、`prevDistance[]`、`vx/omega` 观测值清零并对齐当前编码器累计距离。在 `Chassis_Init()` 内部调用它一次。

### W2 — 差速里程计积分（必做）

由四轮距离增量算车体位移与转角（**M1/M3 左，M2/M4 右**）：

```c
float dLeft  = 0.5f * (d[0] + d[2]);   /* M1, M3 */
float dRight = 0.5f * (d[1] + d[3]);   /* M2, M4 */
float ds     = 0.5f * (dLeft + dRight);          /* 车体前进量 m */
float dtheta = (dRight - dLeft) / chassisTrackWidthM;  /* 航向增量 rad，逆时针为正 */
```

位置积分（**用区间中点角度**减小误差）：

```c
float yaw_mid = chassisYaw + 0.5f * dtheta;
chassisX   += ds * cosf(yaw_mid);
chassisY   += ds * sinf(yaw_mid);
chassisYaw  = wrap_to_pi(chassisYaw + dtheta);   /* 角度归一化到 (-π, π] */
```

- 坐标系：+X 前进、+Y 左、+Z 逆时针。`dRight > dLeft` → `dtheta > 0` → 左转，与 S2-02 一致。
- `wrap_to_pi()` 自己实现（如 `while (a > π) a -= 2π; while (a < -π) a += 2π;`），避免 yaw 无限增长。
- **轮距保护**：`chassisTrackWidthM <= 0` 时跳过 `dtheta` 积分（只更新 x/y），防止除零/错误航向。

### W3 — vx/omega 观测量（必做）

在 `chassis.c` 增加 `extern float chassisOdomVx, chassisOdomOmega;`，由距离增量与 `dt` 算：

```c
chassisOdomVx    = (dt > 0.0f) ? ds / dt : 0.0f;
chassisOdomOmega = (dt > 0.0f) ? dtheta / dt : 0.0f;
```

- 这是**里程计观测值**（供调试/后续融合用），**不是 PID 反馈** —— PID 反馈仍用 `motorSpeedRpm`（滤波后的编码器速度）。不要把 odom 速度喂给 PID。
- 1 ms 差分噪声大，需做**轻度低通**（如 alpha 0.1~0.2）再输出，或在回传中说明未滤波的理由。
- `dt <= 0` 时置 0，防除零。

### W4 — 与 S2-02 共存、不越界（必做）

- S2-02 的差速解算与 RPM 下发代码**保持原样**（`Chassis_Update()` 里先做里程计积分，再做运动学下发，或反之 —— 只要两者都用同一帧的编码器读数、互不干扰）。
- `motorGain[]` 只用于运动学 RPM；`wheelScale[]` 只用于里程计距离。**不得混用**。
- IMU 三个桩函数（`IMU_IsAvailable/GetYaw/GetYawRate`）保持返回 0，`imuAvailable=0`，本单不接 IMU。
- OLED 显示不改；PID 参数/安全宏不动；上电停车不变。

## 7. 安全要求

```text
上电默认停车（TARGET=0），里程计初值 x/y/yaw=0
禁用 1 ms 瞬时 RPM 积分位姿；只用累计距离差分
轮距 <=0 时跳过航向积分（防除零）
dt <=0 时 vx/omega 观测置 0
不喂 odom 速度给 PID（PID 反馈仍是 motorSpeedRpm）
motorGain 与 wheelScale 各司其职，不得混用
PID 循环禁 HAL_Delay；不改 CubeMX / 引脚 / 定时器
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
2. 上电安全：车不动，OLED 四行 `0000.0 RPM  000%`。
3. **静态代码核对**：里程计用 `Control_GetDistanceM()` 差分、有 `wheelScale` 修正、`dtheta=(dRight−dLeft)/track`、中点角度积分、`wrap_to_pi`、有 `Chassis_ResetOdometry()`；**无 `speed_rpm` 参与位姿积分**；odom 速度未送 PID。
4. **Watch 变量**：新增 `chassisOdomVx` / `chassisOdomOmega` 可读，默认 0；`chassisX/Y/Yaw` 可读。
5. **实车（若方便）**：手推车前进约 1 m，`chassisX` 接近 +1 m、`chassisY` 接近 0、`yaw` 接近 0；原地手推旋转 360°，`yaw` 接近 ±2π（归一化后接近 0）。允许粗测误差，符号方向必须对。
   > 人类现场不用 Watch；若不便观测，至少完成 1~4 静态核对 + 上电不跑，运行时位移精度留 S2-TEST 统一验收。
6. 未触碰禁止文件；`encoder.c` 公式与 PID 参数未改。

## 9. 测试方法（人类执行）

```text
1. Keil Build，记录 0 Error / 0 Warning 与 hex 时间
2. 烧录，上电确认车不动、OLED 0000.0 RPM 000%
3. 静态核对 §8 第 3、4 条
4. 若现场可测：手推前进/旋转，看 chassisX/Y/Yaw 方向与量级（或改初值重编看屏）
5. 回传
```

## 10. 回传要求

```text
1. 修改文件清单
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 里程计代码骨架：差分、wheelScale、dtheta、中点积分、wrap、复位、odom 速度与滤波
4. 新增 Watch 变量清单（chassisOdomVx/Omega、复位接口）
5. 实车位移/旋转观测或注明「运行时留 S2-TEST」
6. 遗留问题与风险（尤其轮距粗测对 yaw 精度的影响）
7. 是否建议进入 S2-04（IMU 标定与 yaw 融合）
```

---

**下一位提示**：本单只做纯编码器里程计。S2-04 才接 IMU 硬件（需先由反重力指导在 CubeMX 启用 I2C2 PB10/PB11），做 yaw 融合；S2-05 用原地旋转标定精修轮距与 wheelScale。若接口需调整，**先回报 WorkBuddy，不要自行改**。
