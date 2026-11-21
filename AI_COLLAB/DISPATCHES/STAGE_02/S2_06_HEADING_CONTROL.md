# 派单 S2-06 — 航向闭环纠偏（直行保持 / 定点精确转向）

> ⚠️ **编号说明**：本单编号 S2-06 指**航向闭环纠偏**（人类 11-21 15:51 采纳反重力建议新增）。原 S2-06「基础电脑通信」已于 15:41 移出阶段 2，两者无关，勿混淆。
> 致 Argon4：用已验证的 IMU 真值 yaw 做航向闭环，根治 S2-05 遗留的「2 m 直行右偏 ~10 cm」与「定点转向精度」。**不改 PID、不改 imu.c、不新增硬件。**
> 派单人：WorkBuddy ｜ 时间：2026-11-21 15:51 ｜ 依据：S2-05 回传建议 + `PLAN_STAGE_02.md` §七
> 前置：S2-01~S2-05 ✅ 全完成；IMU 真值航向可用（15:17 实车 +90° 验证）

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

## 2. 要解决的问题（S2-05 实测遗留）

| 现象 | 实测 | 根因 |
|---|---|---|
| 2 m 直行右偏 | 约 10 cm（~2.86°） | 无航向闭环；起点 2~3° 初角误差 / 微打滑 / 轮径公差积累 |
| 定点转向 | S2-03 用 0.20 m 发 90° 实转 ~48° | 编码器 yaw 打滑 2 倍不可信（IMU 已解决读数，但还没闭环控制） |

**S2-05 人类已确认**：不靠静态硬调差速掩盖跑偏 —— 用航向闭环根治。

## 3. 当前状态（核对 2026-11-21 15:46）

| 项 | 当前值 |
|---|---|
| IMU 真值 | `IMU_GetYaw()` 相对角可用，`imuAvailable=1`；10 ms 分频更新（`Chassis_Update()` 内） |
| 航向融合 | `chassisYaw = IMU_GetYaw()`（IMU 主），位置用 IMU 中点角投影；IMU 不可用自动回退编码器 |
| 速度指令 | `Chassis_SetVelocity(vx, omega)` → `chassisTargetVx/Omega` 锁存 → `Chassis_Update()` 差速解算 → `Control_SetTargetRpm()` |
| **等效轮距** | `chassisTrackWidthM = 0.20f`（默认），**S2-05 标定建议 0.3703f，尚未固化** |
| wheelScale | 全 1.0f（默认），**S2-05 建议 1.015f，尚未固化** |
| motorGain | 全 1.0f（**保持**，闭环 PI 已 ±0.5%，不用开环比值） |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`，上电不跑；15:39 hex 0 Error / 0 Warning |

## 4. 允许修改（仅限）

```text
Core/Inc/chassis.h       ← 追加航向闭环接口/模式/调参变量声明
Core/Src/chassis.c       ← 实现航向环；W0 固化标定默认值
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / stm32f4xx_it.c / main.c / main.h
control.h / control.c（PID 参数/安全宏/1ms 调用点全不动）
encoder.h / encoder.c（轮径 0.066404f 与 speed_rpm 公式不动）
pid.h / pid.c / imu.h / imu.c / i2c.c / oled.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 PID 参数（KP=0.4/KI=2.5/KD=0）；改 `WHEEL_DIAMETER_M`；改 imu.c 驱动；改 CubeMX；把 `motorGain` 改成开环比值（见 S2-05 结论）；新接口写死常量（调参量必须 Watch 可写）。

## 6. 具体工作项

### W0 — 固化 S2-05 标定建议值（前置，应用反重力建议）

按 S2-05 回传建议，把标定值写进 `Chassis_Init()` 默认初值（**仍保留 Watch 可写**）：

```text
chassisTrackWidthM : 0.20f   → 0.3703f   （S2-05 3 次均值，极差 3.24%）
wheelScale[0..3]   : 1.0f    → 1.015f    （S2-05 2m 直行误差 1.45% 修正）
motorGain[0..3]    : 保持全 1.0f          （闭环 PI 已 ±0.5%，不改）
```

- 只改 `Chassis_Init()` 里的默认赋值；全局变量声明处初值同步或由 Init 覆盖均可，回传说明。
- `WHEEL_DIAMETER_M` 不动；`motorGain` 不动。

### W1 — 航向闭环模式与接口（必做）

在 `chassis.h/.c` 定义（新增，不影响现有 `Chassis_SetVelocity()` 签名）：

```c
extern uint8_t  chassisHeadingMode;       /* 0=纯速度(原行为), 1=航向保持, 2=定点转向, 默认 0 */
extern float    chassisHeadingTargetRad;  /* 目标 yaw（相对角, rad），Watch 可写 */
extern float    chassisHeadingErrRad;     /* 只读观测：当前航向误差 */
extern float    chassisHeadingKp;         /* 航向环比例增益，默认 1.0，Watch 可调 */
extern float    chassisHeadingMaxOmega;   /* 航向环输出 omega 上限，默认 1.0 rad/s */
void Chassis_SetHeadingTarget(float yaw_target_rad);  /* 设目标 + 自动切 mode 2 */
void Chassis_EnableHeadingHold(uint8_t enable);       /* 1=锁当前 yaw 为基准并保持(mode1) */
```

- **默认 mode 0**：上电行为与现在完全一致（速度环开环给 omega），不破坏既有验收。
- **mode 1（航向保持直行）**：`Chassis_EnableHeadingHold(1)` 锁存当前 `IMU_GetYaw()` 为 `headingHoldBase`，之后每帧以该基准为目标纠偏。
- **mode 2（定点转向）**：`Chassis_SetHeadingTarget(target)` 设目标相对角，闭环转到目标后保持（或按 §W3 判据停车）。
- 模式切换时重新对齐基准，避免跳变。

### W2 — 航向环解算（必做，核心）

在 `Chassis_Update()` 里、**差速解算之前**，根据模式覆盖 `omega`：

```text
若 (chassisHeadingMode != 0) && (imuAvailable == 1):
    yaw_now  = IMU_GetYaw()
    yaw_ref  = (mode==1) ? headingHoldBase : chassisHeadingTargetRad
    err      = wrap(yaw_ref - yaw_now)              /* rad，+ 表示需逆时针转 */
    omega_cmd = clamp(chassisHeadingKp * err, ±chassisHeadingMaxOmega)
    omega    = omega_cmd                            /* 覆盖 omega，vx 保持 */
否则:
    omega    = chassisTargetOmega                   /* 原行为 */
    IMU 掉线时自动回退 mode 0（不改 chassisHeadingMode 的设定值，仅本帧不覆盖）
```

- **符号**：+Z 逆时针为正，`err>0`（目标在当前左侧）→ omega>0 → 左转。若实车方向反了，人类改 `imuYawSign`（S2-04 已验证 +1 正确，正常不用改）。
- **数据源**：用 `IMU_GetYaw()`（10 ms 更新），航向环每 1 ms 算但 yaw 10 ms 才更新一次 —— 零阶保持即可，**不要为了等新数据在 1 ms 中断里忙等**。
- `chassisHeadingErrRad` 每帧更新供 Watch 观察。
- **`chassisHeadingKp` 默认 1.0、范围 0.3~3.0 Watch 可调**；`chassisHeadingMaxOmega` 默认 1.0 rad/s。回传说明整定依据（2.86° 初角误差应在数秒内收敛，不要过冲振荡）。
- 航向环输出的 omega 仍走原有 `Chassis_Update()` 的 **±250 RPM 四轮等比饱和**，不另设限幅逻辑。

### W3 — 定点转向到达判据与停车（必做）

- mode 2 下，`|err| ≤ 0.05 rad（约 3°）` **持续 200 ms** 视为到达，自动把 `vx/omega` 目标清零停车（写 `chassisTargetVx/Omega=0`），并置一个只读到达标志（如 `chassisHeadingReached`）供 Watch/验收看。
- 到达后若人类再次写目标，`chassisHeadingReached` 清零、重新闭环。
- 未完成到达前，若 IMU 掉线 → 立即停车（`vx/omega` 清零，`imuAvailable=0` 时不允许继续盲转）。

### W4 — 隔离与保留（必做）

- S2-01~S2-05 全部能力保留：运动学下发、里程计、IMU 融合、`motorGain`/`wheelScale`、复位、三个标定值可写。
- **IMU yaw 不喂速度 PID**（PID 反馈仍是 `motorSpeedRpm`）—— 航向环只覆盖 omega 目标，不碰 PID 内部。
- OLED 不改；上电默认停车（mode 0、`TARGET=0`）；PID/安全宏不动。
- 航向环不得引入阻塞等待、`HAL_Delay()`。

## 7. 安全要求

```text
上电默认 mode 0 + TARGET=0，车不动
航向环输出 omega 限幅 ±chassisHeadingMaxOmega(默认1.0 rad/s)，再走 ±250 RPM 等比饱和
IMU 掉线（imuAvailable=0）→ 本帧不覆盖 omega；mode 2 下立即停车
定点转向到达判据 3°/200ms，到达自动停车
PID 参数/安全宏不动；WHEEL_DIAMETER_M 不动；motorGain 保持 1.0
调参量 Watch 可写，不写死；CubeMX/引脚/定时器不动
PID 循环禁 HAL_Delay
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`（安全基线：mode 0、目标 0、上电不跑）。
2. 上电：车不动，OLED `0000.0 RPM  000%`。
3. **静态核对**：W0 三个默认值已改（0.3703/1.015/1.0）、航向环在差速解算前覆盖 omega、符号正确、IMU 掉线回退/停车、到达判据、IMU yaw 未喂 PID、调参量 Watch 可写。
4. **航向保持（mode 1）实车**：2 m 地砖直行，横向跑偏 **≤5 cm**（S2-05 无闭环是 ~10 cm）；记录 `chassisHeadingErrRad` 收敛曲线。
5. **定点转向（mode 2）实车**：目标 90°，IMU 真值核对误差 **≤5°**，到达后自动停车、`chassisHeadingReached=1`；180° 同样测。
6. **异常测试**：IMU 掉线时 mode 2 立即停车、不盲转；mode 0 行为不受影响。
7. 未触碰禁止文件；`encoder.c`/`imu.c` 未改；PID 参数未改；无临时测试残留。

> 人类现场不用 Watch；若不便实时调，允许「改初值重编看 OLED」实测，最终调参量必须留在可写变量里。

## 9. 测试方法（人类执行）

```text
1. Keil Build，记录 0 Error / 0 Warning 与 hex 时间
2. 烧录上电：mode 0、车不动、OLED 0000.0 RPM 000%
3. mode 1：锁当前 yaw，闭环 vx=0.25 m/s 直行 2 m，量横向跑偏
4. mode 2：设目标 90° / 180°，看 IMU 真值误差与到达标志
5. 异常：断开 IMU 看是否安全停车
6. 测完还原临时代码、重编安全基线
```

## 10. 回传要求

```text
1. 修改文件清单
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. W0 默认值固化确认（0.3703 / 1.015 / motorGain 1.0）
4. 航向环代码骨架（模式切换、err 计算、omega 覆盖、限幅、掉线回退、到达判据）
5. chassisHeadingKp 整定依据与 Watch 变量清单
6. 实车：2 m 直行跑偏、90°/180° 转向误差与到达、IMU 掉线测试（或注明留 S2-TEST）
7. 遗留问题与风险
8. 是否建议进入 S2-TEST 统一验收
```

---

**下一位提示**：本单是阶段 2 最后一个实现单，之后 **S2-TEST 统一验收**。航向闭环只覆盖 omega 目标，不动 PID、不动 imu.c、不动硬件。若接口需调整，**先回报 WorkBuddy，不要自行改**。
