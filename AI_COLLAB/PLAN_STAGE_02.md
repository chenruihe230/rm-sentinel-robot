# 阶段 2 正式规划：差速底盘运动学与整车里程计

> 来源：Codex 接 MiMo 规划（人类 2026-11-20 17:03 转交）｜ 存档 + 实现细则补充：WorkBuddy
> 状态：**规划已定，实现细则已拍板**；派单由 WorkBuddy 按本文件出具
> 依据：`AI_COLLAB/BRIEF_FOR_CODEX.md`、`AI_COLLAB/ACCEPTANCE/STAGE_01.md`

---

## 一、阶段目标

```text
差速底盘运动学
四轮编码器整车里程计
IMU yaw 标定与融合
左右轮差异标定
基础电脑通信
底盘运动精度验收
```

最终链路：

```text
vx / omega
    ↓
四轮目标 RPM
    ↓
四轮 PID
    ↓
编码器 + IMU
    ↓
整车 x / y / yaw
```

## 二、硬约束

```text
底盘：普通轮子四轮独立驱动，skid-steer
自由度：只有 vx + omega；禁止 vy / 横移 / 麦克纳姆公式
轮径：WHEEL_DIAMETER_M = 0.066404f
编码器：1320 计数/圈
PID：1 ms，KP=0.4 / KI=2.5 / KD=0，输出 -100～+100
硬件极速：约 330 RPM；阶段目标速度 ≤250 RPM
上电默认停车
坐标系：+X 前进、+Y 向左、+Z 逆时针
```

## 三、任务拆分（7 张）

| 单号 | 内容 |
|---|---|
| S2-01 | 接口和架构（接口/数据结构/单位约定） |
| S2-02 | 差速底盘运动学 |
| S2-03 | 整车里程计 |
| S2-04 | IMU 标定与 yaw 融合 |
| S2-05 | 左右轮差异标定 |
| S2-06 | 基础电脑通信 |
| S2-TEST | 实车统一验收 |

每张派单必须含：项目路径、允许/禁止文件、硬件约束、接口、安全要求、验收标准、测试方法、回传内容。

## 四、各单要点（按 Codex 规划原文整理）

### S2-01 接口和架构

```text
Chassis_SetVelocity(vx, omega)
Chassis_Update(dt)
Chassis_GetPose(x, y, yaw)
Encoder_GetDistanceM(index)       ← 已存在
Control_SetTargetRpm(index, rpm)  ← 已存在
IMU_GetYaw()                      ← 先留空位，S2-04 再实现
IMU_GetYawRate()                  ← 先留空位
```

单位：m/s、rad/s、RPM、m、rad。不得由上位机直接写 PWM。目标轮速限 ±250 RPM。

### S2-02 差速底盘运动学

```text
left_speed  = vx - omega × track_width / 2
right_speed = vx + omega × track_width / 2
```

左右轮线速度 → 目标 RPM。支持直行 / 原地旋转 / 弧线旋转 / 停车。禁止 vy、斜行、横移、麦克纳姆公式。

### S2-03 整车里程计

四轮编码器累计距离积分出 `x / y / yaw / vx / omega`。**禁止用 1 ms 瞬时 RPM 积分位姿**。保留四路 `total_count` 与 `distance_m`。允许分别设置 `wheel_scale[i]`。

### S2-04 IMU 标定与 yaw 融合

先确认并登记：IMU 型号 / 通信接口 / 供电 / 引脚 / 坐标轴方向 / 安装方向。**型号和引脚未确认前不得猜测接线或直接改 CubeMX。**

实现：静止陀螺零漂标定、安装方向标定、`IMU_GetYaw/GetYawRate()`、纯编码器模式、编码器+IMU yaw 融合模式，两模式可切换可对比。

阶段 2 只做 yaw 融合，**不做**完整姿态解算 / 四元数导航 / 复杂 EKF / SLAM。

### S2-05 左右轮差异标定

四轮分别测 20/40/60/80% PWM，记录稳态 RPM，得到：

```text
motor_gain[i]：控制层 RPM/% 前馈补偿
wheel_scale[i]：里程计距离修正
```

**控制补偿与里程计修正分开；不得通过修改轮径掩盖电机差异；左右 10% 差异只作初始参考，以实测为准。**

### S2-06 基础电脑通信

基础双向 UART：

```text
CMD_VEL      : vx / omega
CMD_STOP     : 停车
TELEMETRY    : 四轮 RPM、PID 输出、x/y/yaw、IMU yaw
```

定长帧、序号、校验、通信超时停车、上电默认停车。暂不做变长帧 / CRC16 完整协议 / 复杂心跳 / 重连机制 / 发射互锁（留阶段 3）。

### S2-TEST 实车统一验收

按 §六 验收标准逐项测，出阶段 2 验收记录。

## 五、验收标准

**运动学**：直行四轮同向；原地旋转左右侧反向；弧线旋转内外侧速度不同；停止时四轮目标 RPM 为 0。

**里程计**：单轮 1 m ≤2%；直行 2 m 纵向 ≤3%、横向跑偏 ≤5 cm；原地 360° 目标 ≤5°、门槛 ≤10°；受控地面闭环回起点 ≤5 cm。

**IMU**：静止 yaw 漂移受控；yaw 正负方向与坐标系一致；旋转 360° 与实际一致；编码器模式与融合模式均可观察。

**通信**：可发 vx/omega；可远程停车；可回传 RPM、PWM、x/y/yaw；超时自动停车。

## 六、安全要求

```text
硬件急停优先级最高
目标速度超过 ±250 RPM 时截断
PID 输出限制 ±100
目标为 0 时立即停车
通信超时未更新时停车
PID 循环禁止 HAL_Delay
不得修改 CubeMX 引脚和定时器，除非先报架构变更
```

## 七、WorkBuddy 拍板的实现细则（6 条）

> 用户 2026-11-20 17:04 裁定：这些细则由 WorkBuddy 定；Codex 只做规划；IMU 选型/引脚等到 S2-04 前再单独立项。

### 细则 1 — track_width 不猜数值，用可写变量 + 两级标定

- S2-01 定义 `float chassisTrackWidthM = 0.0f;`（Watch 可写，单位 m）。**未标定时为 0**。
- 安全逻辑：`chassisTrackWidthM <= 0` 时 `Chassis_SetVelocity()` 只接受 omega=0 的直行指令，带 omega 的指令拒绝执行并回报错误 —— 防止用错误轮距跑出错误姿态。
- **几何轮距**：人类实测左右轮中心距，填入为初值。
- **等效轮距**：skid-steer 转弯有侧滑，几何轮距与运动学等效轮距不同。S2-05 原地旋转 360°，用四轮累计距离反推：`track = (右轮累计距离 − 左轮累计距离) / π`，取 M1/M3 为左侧、M2/M4 为右侧，左右各求平均后填入 `chassisTrackWidthM`。
- 派单里**不许直接写死一个猜的轮距数值**。

### 细则 2 — IMU 硬件到 S2-04 前单独立项

- S2-01~S2-03 **不接 IMU 硬件**：`IMU_GetYaw()` / `IMU_GetYawRate()` 只留函数空位，返回 0 或明确标记不可用，上位机/里程计不得依赖其有效值。
- S2-04 开工前置：人类确认型号 / 接口 / 供电 / 引脚 / 轴向 / 安装方向 → 报架构变更 → Codex 改 `.ioc` → 才允许接线。实现模型不得自行改 CubeMX。
- 用户已明确：IMU 选型引脚到需要时再规划。

### 细则 3 — motor_gain / wheel_scale 在 S2-01 就预留

- S2-01 定义 `float motorGain[MOTOR_COUNT]` 和 `float wheelScale[MOTOR_COUNT]`，**默认均 1.0f**，Watch 可写。
- S2-02 输出目标 RPM 前乘 `motorGain[i]`，补偿后再限幅 ±250 RPM。
- S2-03 里程计用 `Encoder_GetDistanceM(i) * wheelScale[i]`。
- 两者独立，不合并；**不许改 `WHEEL_DIAMETER_M` 掩盖电机差异**。S2-05 只标定这两个数组。

### 细则 4 — 接口形式定死

```c
void Chassis_SetVelocity(float vx, float omega);              /* m/s, rad/s */
void Chassis_Update(float dt);                                /* 挂 1 ms SysTick，dt = CONTROL_PID_DT */
void Chassis_GetPose(float *x, float *y, float *yaw);         /* 指针出参，不用返回值 */
float IMU_GetYaw(void);                                       /* rad，S2-04 前返回 0 */
float IMU_GetYawRate(void);                                   /* rad/s，S2-04 前返回 0 */
```

- 轮序：M1 左前、M2 右前、M3 左后、M4 右后（`main.h` 引脚命名 zuoqian/youqian/zuohou/youhou）。**左 = M1/M3，右 = M2/M4**。
- omega 正向（+Z 逆时针）→ 左轮减速、右轮加速，与规划公式一致。
- 线速度 → RPM：`rpm = v_mps * 60.0f / (3.14159265f * 0.066404f)` ≈ `v_mps * 287.6`。派单必须写明，不许实现模型自己推。

### 细则 5 — 通信阶段边界与超时

- 阶段 2 只做 S2-06 的基础通信（定长帧 + 序号 + 校验 + 两模式指令 + 遥测 + 超时停车）。
- 变长帧 / CRC16 / 复杂心跳 / 重连 / 发射互锁明确留阶段 3；Codex 更新总览时同步阶段边界。
- **通信超时时间定为 200 ms**：超过 200 ms 未收到有效帧 → 四轮目标归零停车。派单里不许写「约定时间」这种模糊表述。

### 细则 6 — ±250 RPM 饱和用等比缩放

- 先算左右轮目标速度，若任一超过 ±250 RPM，取 `k = 250 / max(|left|, |right|)`，**左右同乘 k** 整体等比缩放，保持 vx:omega 比例 —— 单侧独立截断会破坏差速关系、导致 yaw 漂移。
- 缩放后再乘 `motorGain[i]`，再限幅一次 ±250 RPM。
- vx 自身上限：`250 / 287.6 ≈ 0.869 m/s`，作为 `Chassis_SetVelocity()` 输入校验。

## 八、阶段 3 预留（不进阶段 2）

```text
完整通信协议：变长帧 / CRC16 / 心跳 / 重连 / 发射互锁
云台、视觉、发射机构、激光雷达导航
```

## 九、最终交付（阶段 2 收尾）

```text
1. 修改文件清单
2. Keil 编译结果
3. 运动学接口说明
4. 里程计和 IMU Watch 变量
5. 四轮 motor_gain / wheel_scale 标定值 + 等效轮距
6. 直行、旋转、闭环测试数据
7. 通信测试结果
8. 遗留问题
9. 是否允许进入阶段 3
```
