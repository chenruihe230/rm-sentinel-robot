# 派单 S2-06B — 定点转向精度微调（目标前 2° → ≤1°）

> 致 Argon4：S2-06 实车 +90° 停在 88.0°、+180° 停在 177.7°（误差 −2°），原因是到达容差 0.05 rad（2.86°）触发锁死。**本单把定点误差压到 ≤1°，但不能用「单纯改小容差」的做法**（会卡住，见 §2）。
> 派单人：WorkBuddy ｜ 时间：2026-11-21 16:10 ｜ 依据：S2-06 回传遗留 + 人类「精度微调一下先」
> 前置：S2-06 ✅ 已完成（16:07 hex）；本单是小改，**不改架构、不改硬件、不加新文件**

---

## 1. 为什么不能只改容差（必读，这是本单核心）

当前控制率是纯比例：

```c
w_cmd = chassisHeadingKp * err;   /* Kp 默认 1.0 */
到达判据：|err| <= 0.05 rad (2.86°) 持续 200 ms → 锁死停车
```

**如果把容差直接改到 0.017 rad（1°）**：

- `err=1°` 时 `w_cmd = 1.0 × 0.017 = 0.017 rad/s`
- 对应轮速 `0.017 × 0.3703/2 ≈ 0.0031 m/s` → 约 **0.9 RPM**
- **这个转速下静摩擦/齿槽转矩会让轮子根本转不动** → 车永远卡在 1° 外，到达判据永不满足，要么超时要么原地抖

所以必须配「低速段保底驱动 + 过冲反向刹车」，不能只动一个数。

## 2. 当前实现（核对 2026-11-21 16:10）

| 项 | 当前值 | 位置 |
|---|---|---|
| 到达容差 | `CHASSIS_HEADING_TOL_RAD = 0.05f`（2.86°） | `chassis.c` 第 14 行 |
| 保持时间 | `CHASSIS_HEADING_SETTLE_MS = 200U` | 第 15 行 |
| 控制率 | `w_cmd = Kp * err`（Kp 默认 1.0，max_w 1.0） | `Chassis_ComputeHeadingOmega()` 第 195 行 |
| 到达动作 | 置 `chassisHeadingReached=1`、清零 vx/omega/target、锁死 | 第 423-433 行 |
| 掉线保护 | mode 2 下 `imuAvailable==0` 立即停车 | 第 398-406 行（**本单不许动**） |

## 3. 允许修改（仅限）

```text
Core/Src/chassis.c        ← 改容差宏 + 控制率分段 + 过冲处理（严格限定 §4 范围）
Core/Inc/chassis.h        ← 仅当新增 Watch 调参变量时追加声明
```

## 4. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / main.c / main.h
control.h / control.c（PID 参数/安全宏/1ms 调用点全不动）
encoder.h/.c（轮径、speed_rpm 公式不动）
pid.h/.c / imu.h/.c / i2c.c / oled.c / docs/* / AI_COLLAB/*
```

**绝对禁止**：改 S2-06 已验证的 mode 0 / mode 1 行为；改掉线保护（第 398-406 行）；改 `WHEEL_DIAMETER_M`；改 PID 参数；把新参数写死成不可调常量。

## 5. 具体工作项

### W1 — 容差与保持时间收紧

```c
CHASSIS_HEADING_TOL_RAD   0.05f  → 0.017f   /* 约 1° */
CHASSIS_HEADING_SETTLE_MS 200U   → 150U     /* 略缩短，减少到位后惯性漂移 */
```

两个都保留宏定义（不是写死在函数里的魔数）。

### W2 — 低速段保底驱动（解决 0.9 RPM 转不动）

在 `Chassis_ComputeHeadingOmega()` 里加**分段**，仅对 `|err|` 小的区域生效：

```text
若 |err| >= 高速阈值（建议 0.10 rad ≈ 5.7°）：
    w_cmd = Kp * err                      /* 原行为，全速接近 */
否则（低速段）：
    w_mag = max(Kp * |err|, 最小角速度)    /* 保底，如 0.06 rad/s ≈ 3.4°/s */
    w_cmd = sign(err) * w_mag
    再限幅到 ±max_w
```

- **最小角速度建议 0.06 rad/s**（对应轮速约 1.7 RPM，仍偏低 —— 若实车仍转不动，允许人类 Watch 上调到 0.10~0.15 rad/s）。
- 必须做成**可写变量** `chassisHeadingMinOmega`（默认 0.06），不许写死 —— 静摩擦因车而异，人类现场调。
- 作用范围**只在 mode 2 定点转向**；mode 1 航向保持直行保持原纯比例（避免直行时引入保底速度造成画龙）。可在函数加参数或分支区分，回传说明实现方式。

### W3 — 过冲反向刹车（防止来回抖）

低速段加过冲检测：

```text
记录上一帧 err（prev_err）
若本帧 err 与 prev_err 符号相反 且 |err| < 过冲阈值（建议 0.05 rad ≈ 2.9°）：
    w_cmd = -sign(err) * 更小的修正速度（如 minOmega）   /* 反向微调 */
    或直接检测到越过目标就反向，直到 |err| <= 新容差维持 150ms
```

- 目的是：越过目标时不要靠"慢慢滑回来"（那会永远到不了 1°），而是**主动反向修正**。
- 加一个**最大转向超时**（建议 8 s for 180°，可写变量 `chassisHeadingTimeoutMs`），超时置 `chassisHeadingReached=1` 并停车、回报实际误差 —— 防止极端情况下死循环。

### W4 — 保留与隔离（必做）

- S2-06 的 mode 0 / mode 1 行为、IMU 融合、掉线保护（`imuAvailable==0` 立即停车）、里程计、标定值全部**原样保留**。
- IMU yaw 不喂速度 PID；1 ms 中断无阻塞/`HAL_Delay`。
- 上电默认 mode 0、车不动、OLED 不变。
- 新增调参变量全部 Watch 可写：`chassisHeadingMinOmega`、`chassisHeadingTimeoutMs`（如需 `chassisHeadingOvershootThr` 也做成可写）。

## 6. 安全要求

```text
上电默认 mode 0 + TARGET=0，车不动
mode 2 下 IMU 掉线立即停车（原保护不许动）
保底角速度 <= chassisHeadingMaxOmega，不能因保底造成高速过冲
最大转向超时必须生效，超时停车回报
PID 参数/安全宏/轮径/CubeMX 不动
调参量 Watch 可写，不写死
```

## 7. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`（默认 mode 0、目标 0、上电不跑）。
2. 上电：车不动，OLED `0000.0 RPM  000%`。
3. **静态核对**：容差 0.017f、保持 150ms；低速保底分段只对 mode 2 生效、mode 1 仍纯比例；过冲反向逻辑在；超时保护在；IMU 掉线保护未动；调参量可写。
4. **实车 mode 2**：+90° 目标，IMU 真值误差 **≤1°**（原 −2°）；+180° 同样 ≤1°；**无来回振荡**（转到目标后 3 s 内 yaw 稳定）。
5. **回归**：mode 1 直行 2 m 横偏仍 ≤5 cm（不能因低速分段变差）；mode 2 IMU 掉线仍 SAFE STOP 不盲转。
6. 未触碰禁止文件；无临时测试残留。

> 若实车发现 1° 过严（静摩擦导致反复修正不停），由人类 Watch 上调 `chassisHeadingMinOmega` 或把容差放宽到 0.025 rad（1.4°），**以不振荡为先**，回传说明最终取值 —— 不追求纸面指标牺牲稳定性。

## 8. 回传要求

```text
1. 修改文件清单
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 控制率改动代码骨架（分段、保底、过冲反向、超时）
4. 新增 Watch 变量清单与默认值
5. 实车 +90°/+180° 误差与稳定性（或注明留 S2-TEST）
6. mode 1 回归与掉线测试结果
7. 遗留问题与风险
8. 是否建议进入 S2-TEST 统一验收
```

---

**下一位提示**：本单是精度微调，不动架构、不动硬件、不动 S2-06 已验证的掉线保护。完成后 **S2-TEST 统一验收、阶段 2 收官**。若发现 1° 目标不可达，优先保稳定、由人类裁决放宽，不要自行反复调参。
