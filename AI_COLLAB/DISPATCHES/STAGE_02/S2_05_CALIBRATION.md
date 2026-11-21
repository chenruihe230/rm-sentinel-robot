# 派单 S2-05 — 等效轮距与左右轮差异标定

> 致 Argon4：本任务把 S2-03/S2-04 实测暴露的误差**标定掉**：等效轮距（0.20→约 0.40 m）、`motorGain[]`（控制前馈）、`wheelScale[]`（里程修正）。**不新增控制算法、不接新硬件、不改 PID。**
> 派单人：WorkBuddy ｜ 时间：2026-11-21 15:19 ｜ 依据：`AI_COLLAB/PLAN_STAGE_02.md` S2-05、S2-03 实车发现、S2-04 IMU 真值
> 前置：S2-01~04 ✅ 全完成；IMU 真值航向可用（15:17 实车验证）

---

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

下文 `Core/...` 以 Keil 工程目录为基准。

## 2. 背景：这单要解决的三个实测误差

| 实测来源 | 现象 | 根因 | 本单怎么修 |
|---|---|---|---|
| S2-03 直行 1 m | 实走 1.03 m（+3%，略右偏） | 轮径/里程比例小偏差 | `wheelScale[i]` 距离修正 |
| S2-03 原地转 90° | 实际只转 ~45° | skid-steer 侧滑，**等效轮距约 0.40 m**（几何 0.20 m 的 2 倍） | 重标 `chassisTrackWidthM` |
| S2-03 开环 | 左轮 3.5 / 右轮 3.0 RPM/%（差约 10%） | 电机/驱动固有差异 | `motorGain[i]` 控制前馈补偿 |

**关键原则（用户/Codex 定，不许违反）**：

```text
motorGain（控制层 RPM/% 前馈）与 wheelScale（里程计距离修正）分开标定，不得混用
不得通过修改 WHEEL_DIAMETER_M（0.066404f）掩盖电机差异 —— 轮径只读不改
左右 10% 差异只作初始参考，最终以实测为准
```

## 3. 当前状态（核对 2026-11-21 15:17）

| 项 | 当前值 |
|---|---|
| `chassisTrackWidthM` | 0.20f（几何粗测，可写）→ 本单要重标为实测等效值 |
| `motorGain[4]` | 全 1.0f（可写，S2-02 已用于 RPM 补偿） |
| `wheelScale[4]` | 全 1.0f（可写，S2-03 已用于里程修正） |
| `WHEEL_DIAMETER_M` | 0.066404f（**只读，不改**） |
| IMU | `IMU_GetYaw()` 可用真值航向（15:17 实车 +90° 验证），**本单用它当旋转标定基准** |
| 标定模式 | `controlCalibrationMode`（阶段 1 遗留，默认 0）+ `motorOpenLoopDuty[4]`（默认 0，量程 ±100） |
| Watch 已有 | `motorSpeedFiltered[]`、`chassisX/Y/Yaw`、`imuYawRad`、`chassisTrackWidthM`、`motorGain[]`、`wheelScale[]` 均可读/写 |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`、上电不跑；15:17 hex 0 Error / 0 Warning |

## 4. 允许修改（仅限）

```text
Core/Inc/chassis.h       ← 仅追加标定辅助接口声明（如需）
Core/Src/chassis.c       ← 仅追加标定辅助函数（如需），不改现有运动学/里程计/融合逻辑
```

**⚠️ 本单以「Watch 可写变量 + 人类实测」为主，尽量不写代码**。只有确实需要辅助接口（如一键复位标定值、旋转标定触发器）才改上面两个文件，且必须说明必要性。

## 5. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / stm32f4xx_it.c / main.c / main.h
control.h / control.c（PID/安全宏/标定模式逻辑全不动）
encoder.h / encoder.c（轮径 0.066404f 与 speed_rpm 公式一律不动）
pid.h / pid.c / imu.h / imu.c / i2c.c / oled.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 `WHEEL_DIAMETER_M`；把 `motorGain` 和 `wheelScale` 混用；改 PID 参数/安全宏；改 CubeMX；把临时测试数据写死成常量（标定值必须是 Watch 可写全局变量，人类可随时调）。

## 6. 标定方法（三件事，按顺序）

### W1 — 等效轮距标定（核心，用 IMU 真值）

S2-03 已发现几何 0.20 m 在旋转时只有一半效果。用 IMU 真值精标：

```text
方法 A（推荐，无需改代码）：
  1. chassisTrackWidthM 先设 0.20f，闭环给 omega（如 1.0 rad/s）原地左转
  2. 用 IMU 真值读实际转过的角度 Δyaw_imu（如转够 90° 停）
  3. 同时读四轮在该时段的累计距离差：dRight − dLeft（M1/M3 左、M2/M4 右）
  4. 等效轮距 = (dRight − dLeft) / Δyaw_imu(rad)
  5. 把结果写入 chassisTrackWidthM（Watch 可写，不重编译）
  预期约 0.40 m（S2-03 粗测），以实测为准

方法 B（若 Watch 不便读累计距离差）：
  固定 omega 指令转固定时间，用 IMU 实测 Δyaw，与「按 0.20 算的理论 Δyaw」比较，
  按比例缩放 chassisTrackWidthM = 0.20 × (理论Δyaw / 实测Δyaw)
```

- **收敛判据**：标定后原地转 90°，`chassisYaw`（IMU 主）与 IMU 真值一致（本来就一致），且**位置积分不再因轮距错误而偏移**；重复 3 次等效轮距读数差 ≤5%。
- 若需要辅助读「四轮累计距离差」，允许在 `chassis.c` 加一个只读 Watch 变量（如 `chassisOdomDistLeft/Right`），**仅用于标定观测，不参与控制**。

### W2 — motorGain 前馈标定（控制层，四轮分别测）

沿用阶段 1 开环标定方法，但用运行时变量：

```text
1. controlCalibrationMode=1（开环），motorOpenLoopDuty[] 四路分别设 20/40/60/80%
2. 每级记录稳态 motorSpeedFiltered[i]（RPM）—— 得到每轮增益 gain_i ≈ RPM/% 
3. 以四轮平均增益为基准：motorGain[i] = 平均增益 / gain_i
   （增益低的轮子 motorGain > 1，补偿更强）
4. 退出：占空比回 0 → controlCalibrationMode=0（自动清目标复位 PID）
5. 闭环验证：四轮统一目标 100 RPM，看稳态是否都落在 96~104（误差 ≤±4%）
```

- 依据：S2-03 实测左约 3.5、右约 3.0 RPM/%（差 10%），`motorGain` 预期左约 0.93 / 右约 1.08 —— **只作参考，以实测为准**。
- `motorGain` 范围建议 0.5~2.0，超出说明标定异常，回传报告不要强写。

### W3 — wheelScale 里程标定（里程计层，直行距离修正）

```text
1. wheelScale[] 全 1.0，wheelScale 不改轮径
2. 场地量一段 2 m 直线（起点/终点标记）
3. 闭环 0.25 m/s 直行从起点到终点，读 chassisX/Y
4. wheelScale[i] = 实际距离 / 里程计读数（纵向）
   若整体偏大 3%（S2-03：1 m 读成 1.03），则 wheelScale 约 0.97
5. 右偏修正：若 chassisY 漂移明显（如走 2 m 偏 >5 cm），
   分别微调左右轮 wheelScale 使两侧里程一致
6. 复测：再走 2 m，纵向误差 ≤3%、横向跑偏 ≤5 cm
```

- **与 motorGain 的区别**：`motorGain` 让轮子**转得一样快**（控制），`wheelScale` 让里程计**算得一样远**（观测）。改一个不影响另一个。
- 左右轮固有差约 10%，`wheelScale` 修正的是「里程读数」而非「实际转速」—— 不要用它掩盖电机差异。

### W4 — 标定值固化与恢复（必做）

- 三个标定结果（`chassisTrackWidthM`、`motorGain[]`、`wheelScale[]`）都是 **Watch 可写全局变量**，本单**不写死成宏/常量**。
- `Chassis_Init()` 的默认值保持当前值（轮距 0.20、gain/scale 全 1.0）—— 标定值是运行时写入，掉电不保存（除非人类要求存 Flash，那是后续需求）。
- 回传里给出**最终建议标定值表**，由人类决定是否后续固化。

## 7. 安全要求

```text
上电默认停车（TARGET=0），标定过程由人类现场控制
开环标定占空比从 0 逐步加，退出先回 0 再切闭环
WHEEL_DIAMETER_M 不动；PID 参数/安全宏不动
motorGain 与 wheelScale 不混用
临时测试代码测完必须还原，最终 hex 是安全基线（目标 0）
不接硬件改动、不改 CubeMX
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`（安全基线：目标 0、上电不跑）。
2. 上电：车不动，OLED `0000.0 RPM  000%`。
3. **等效轮距**：标定后原地转 90°，用 IMU 真值核对，重复 3 次等效轮距差 ≤5%；给出最终 `chassisTrackWidthM` 建议值。
4. **motorGain**：四轮统一 100 RPM 目标，稳态 96~104（≤±4%）；给出四路 `motorGain` 建议值。
5. **wheelScale**：直行 2 m，纵向误差 ≤3%、横向跑偏 ≤5 cm；给出四路 `wheelScale` 建议值。
6. 未触碰禁止文件；`encoder.c` 轮径与公式未改；PID/安全宏未改；无临时测试残留。
7. 未把标定值写死成宏/常量。

> 人类现场不用 Watch；若不便改变量实时标定，**允许用「改初值重编看 OLED」方式完成实测，但最终标定值必须留在可写全局变量里**（不写死），并在回传里给出建议值表。

## 9. 测试方法（人类执行）

```text
1. 等效轮距：闭环给 omega 原地转，用 IMU 读实际角度 + 读累计距离差 → 算等效轮距
2. motorGain：开环 20/40/60/80% 四轮测 RPM → 算补偿系数 → 闭环 100 RPM 验证
3. wheelScale：量 2 m 直线，直行看 x/y 误差 → 算比例 → 复测
4. 每次标定后记录建议值
5. 测完还原临时代码、重编安全基线
```

## 10. 回传要求

```text
1. 修改文件清单（若只 Watch 标定无代码改动，明确说明）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. 等效轮距标定过程与最终建议值（含 3 次重复性）
4. motorGain 四路标定数据表（20/40/60/80% RPM → 系数）与闭环验证结果
5. wheelScale 四路标定依据（直行 2 m 误差）与复测结果
6. 最终标定值汇总表（三个量的建议值）
7. 遗留问题与风险
8. 是否建议进入 S2-TEST 统一验收（通信已移出阶段 2，归属待阶段末规划）
```

---

**下一位提示**：本单是**标定单**，以人类实测 + Watch 写入为主，不新增控制算法、不改硬件。**下一单是 S2-TEST 统一验收**（基础通信已移出阶段 2，归属待阶段末规划）。标定值不写死，掉电不保存 —— 如需固化 flash 另行立项。若发现接口不够用，**先回报 WorkBuddy，不要自行改**。
