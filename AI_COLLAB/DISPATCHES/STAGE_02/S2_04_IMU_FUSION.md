# 派单 S2-04 — IMU 接入与 yaw 融合（v2 修订版）

> 致 Argon4：本任务接入维特 10 轴 IMU（I2C2），实现 `IMU_GetYaw/GetYawRate()` 与**以 IMU 为主**的 yaw 融合。**这是阶段 2 唯一动硬件的一单。**
> 派单人：WorkBuddy ｜ 初版：2026-11-21 14:25 ｜ **修订：2026-11-21 14:47（审单 1 致命死锁 + 3 SDK/边界细节全采纳）**
> 依据：`AI_COLLAB/PLAN_STAGE_02.md` S2-04 ｜ 前置：W0 CubeMX ✅ 已完成（11-21 14:39 核对）

> **v2 修订要点**（相对初版）：
> 1. **【致命】** SysTick 内禁止用 `HAL_I2C_Mem_Read()` 的 `HAL_GetTick` 超时 —— 会死锁；改用 **DWT->CYCCNT 硬超时**；
> 2. 10 ms 分频写在 **`Chassis_Update()`（chassis.c）** 内，不写「在 Control_Update 里做」（control.c 禁止改）；
> 3. `IMU_GetYawRate()` 读 **GZ(0x39)**，`raw/32768*2000*pi/180` rad/s；**从 0x39 连读 14 字节**一次取 GZ 与 Yaw；
> 4. 写配置寄存器前先向 **KEY(0x69)=0xB588 解锁**；**删除「WIT_ANGLE(0x53) 是角度寄存器」的错误描述**（那是串口包类型，不是 I2C 寄存器）。

---

## 0. 前置 W0 已完成（不用你动 CubeMX）

人类用户 11-21 14:39 已在 CubeMX 启用 I2C2（PB10=SCL/PB11=SDA，400 kHz），WorkBuddy 已核对：`.ioc` 配置正确、`i2c.c` 有 `hi2c2`/`MX_I2C2_Init()`、`main.c` 第 99 行调用在、Keil 工程树六个手动 Add 的 `.c` 全在、编译 0 Error。**你不改 `.ioc`/CubeMX/引脚/定时器，也不要给 IMU 开任何中断**（模块无 DRDY 引脚，SDK 是纯轮询读）。

## 1. 目录约定与文件名

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
IMU 资料：D:\stm32\imu(10zhou)（模块简介 PDF + 串口/I2C 例程源码 zip）
```

## 2. 硬件与协议（已查证，不要猜）

| 项 | 值 |
|---|---|
| 模块 | 亚博智能维特 WT 系列 **10 轴**惯导，**裸机版**，3.3V，Z 轴朝上，远离电机 |
| 接口 | **I2C2**：PB10=SCL / PB11=SDA，400 kHz，**从机地址 0x50**（`0x50<<1=0xA0`） |
| 算法模式 | **6 轴模式**（`AXIS6`=0x24 写 1），磁力计不启用 |
| 协议 | 维特 `wit_c_sdk`：模块自带卡尔曼解算直出角度，STM32 只读寄存器，不自己算姿态 |

**寄存器地址（已查 `REG.h` 逐项核对）**：

```text
KEY      = 0x69   ← 写 0xB588 (KEY_UNLOCK) 解锁后才能写配置寄存器
RSW      = 0x02   ← 输出内容：RSW_ANGLE=0x08 | RSW_GYRO=0x04 → 写 0x0C
RRATE    = 0x03   ← 输出速率：RRATE_100HZ=0x09
AXIS6    = 0x24   ← 6 轴算法开关：写 1
GZ       = 0x39   ← 陀螺 Z 轴角速度（raw int16）
Yaw      = 0x3f   ← 航向角（raw int16）
```

**⚠️ 两个 SDK 陷阱（必须避开）**：

1. **写配置前必须解锁**：`WitWriteReg(KEY, KEY_UNLOCK)` 即向 0x69 写 **0xB588**，之后才能写 `AXIS6`/`RRATE`/`RSW`。SDK 里所有写配置的函数（`WitSetUartBaud` 等）都是这个顺序。不解锁写入无效。
2. **`WIT_ANGLE`(0x53) 是串口协议包类型标识，不是 I2C 寄存器** —— I2C 寄存器表里 0x53 是 `q2`（四元数分量）。**不要按 0x53 写任何配置**。本单读角度直接用寄存器 `Yaw`(0x3f)。

**连读优化**：`GZ=0x39` 到 `Yaw=0x3f` 连续 7 个 16-bit 寄存器（0x39 GZ / 0x3a HX / 0x3b HY / 0x3c HZ / 0x3d Roll / 0x3e Pitch / 0x3f Yaw）。**一次读 14 字节**即可同时拿到 GZ（前 2 字节）与 Yaw（最后 2 字节），比读两次省一半总线时间。

**SDK 源码**：`D:\stm32\imu(10zhou)\2.STM32-IIC应用例程\STM32Core_SDK_IIC.zip` 内 `Source/wit_c_sdk/`（`wit_c_sdk.c/.h`、`REG.h`）。参考其寄存器读写时序与解锁流程，**不要整包照搬**（那是 F103 标准库 + 软件 I2C，本项目是 F407 HAL + 硬件 I2C2）。

## 3. 当前状态（核对 2026-11-21 14:21）

| 项 | 当前值 |
|---|---|
| IMU 桩函数 | `IMU_IsAvailable()` / `IMU_GetYaw()` / `IMU_GetYawRate()` 返回 0，`imuAvailable=0` |
| 位姿 | `chassisX/Y/Yaw` 由 S2-03 纯编码器里程计积分；**实车发现原地转 90° 实际只 45°（打滑，等效轮距约 0.40 m）** |
| 里程计 | `Chassis_UpdateOdometry()` 累计距离差分；`Chassis_Update(dt)` 由 `Control_Update()` 每 1 ms 调 |
| 安全基线 | `TARGET=0`、`OPEN_LOOP=0`，上电不跑；14:39 hex 0 Error / 0 Warning |

**⚠️ S2-03 发现决定本单策略**：编码器 yaw 在旋转时误差约 2 倍，**不可靠**；IMU yaw 才可信。融合策略为 **IMU yaw 为主，编码器仅在 IMU 不可用时兜底** —— 不要反过来。

## 4. 允许修改（仅限）

```text
Core/Inc/imu.h             ← 新建（或扩展 chassis.h，二选一，回传说明）
Core/Src/imu.c             ← 新建
Core/Inc/chassis.h         ← 仅追加融合模式相关声明与变量
Core/Src/chassis.c         ← IMU_* 桩函数改真实实现 + 10 ms 分频读 + yaw 融合
MDK-ARM/.../uvprojx        ← 新增 imu.c 时 Keil Add
```

## 5. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / stm32f4xx_it.c / main.c / main.h
Core/Inc/control.h / Core/Src/control.c   ← PID/安全宏/调用点全不动
Core/Inc/encoder.h / Core/Src/encoder.c   ← 轮径与 speed_rpm 公式、累计计数不动
Core/Inc/pid.h / Core/Src/pid.c / oled.c / i2c.c
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 `.ioc`/CubeMX；改 `encoder.c` 公式/轮径；改 PID/安全宏；IMU yaw 喂速度 PID（PID 反馈仍是 `motorSpeedRpm`）；用磁力计绝对航向；按 0x53 写 I2C 配置。

## 6. 具体工作项

### W1 — I2C2 读 IMU（含死锁防护，必做，最关键）

**⚠️ 致命陷阱**：`Control_Update()` / `Chassis_Update()` 运行在 `SysTick_Handler()` 内，`HAL_GetTick()` 在 SysTick 里**不会自增**。`HAL_I2C_Mem_Read(..., timeout=2)` 内部超时依赖 `HAL_GetTick()` —— **IMU 未接或 NACK 时会无限死锁整个系统**。

**硬性要求**：

1. **`IMU_Init()` 只在 `main()` 初始化阶段调用**（用户已在 main.c 调 `MX_I2C2_Init()`；你可要求用户在 `MX_I2C2_Init()` 之后加一行 `IMU_Init()`，由用户操作；或由 `Chassis_Init()` 间接调用，回传说明）。`IMU_Init()` 里可以用 HAL 阻塞写（此时不在中断里）。
2. **运行时 I2C2 读取严禁使用带 HAL 超时的 API**。两种可选方案（回传说明选了哪种）：
   - **推荐 A：DWT->CYCCNT 硬超时轮询** —— 使能 `CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk; DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;`，读操作用有限循环检查 I2C2 状态寄存器（SR1/SR2 的 TXE/RXNE/ADDR/BTF/STOPF 等），以 `DWT->CYCCNT` 差值做 **2 ms 硬超时**（72 MHz 下约 144000 周期），超时立即返回失败并复位 I2C2 状态。**完全不依赖 HAL_GetTick**。
   - 方案 B：用 `HAL_I2C_Mem_Read_IT()` 非阻塞 + 状态机轮询完成标志（但不能用 HAL 超时），复杂度高。
   - **无论哪种，必须保证：无传感器 / NACK / 总线异常时，SysTick 绝不会被卡住超过 2 ms。**
3. **10 ms 分频位置**：在 **`Chassis_Update()`（chassis.c）内部**做计数分频（计到 10 读一次，匹配 IMU 100 Hz 输出率）—— **不要写「在 Control_Update() 里做分频」**（control.c 禁止修改）。不要每 1 ms 都读。
4. **一次连读**：从 `0x39` 读 **14 字节**，前 2 字节是 GZ、最后 2 字节是 Yaw（中间 HX/HY/HZ/Roll/Pitch 忽略）。按维特协议，16-bit 数据为 **低字节在前**（SDK 里 `sReg = (buf[i*2+1]<<8) | buf[i*2]`），注意字节序。
5. 读失败 / 超时 / 数据无更新超过约定时间 → `imuAvailable=0`；正常 → `imuAvailable=1`。

### W2 — 初始化配置与相对角标定（必做）

**初始化序列（`IMU_Init()`，main 阶段，用 HAL 阻塞写）**：

```text
1. 向 KEY(0x69) 写 0xB588 解锁                    ← 必须，否则后续写无效
2. 向 AXIS6(0x24) 写 1                            ← 6 轴模式，磁力计不启用
3. 向 RRATE(0x03) 写 0x09                         ← 100 Hz 输出
4. 向 RSW(0x02) 写 0x0C (RSW_ANGLE|RSW_GYRO)      ← 使能角度+角速度输出
（每次写之间留微小延时，参考 SDK 的解锁后延时）
```

**相对角与标定**：

- 模块 yaw 可能是绝对角（东北天 0°=北），上电记 `imuYaw0`，`IMU_GetYaw()` 返回 `wrap(raw − imuYaw0)` 的相对角（rad）。
- 可写变量 `imuYawSign`（±1）、`imuYawOffsetRad`（默认 0），返回 `wrap(imuYawSign*yaw_rel + imuYawOffsetRad)`。实物装好后由人类 Watch 改符号，不改接线。
- **`IMU_GetYawRate()`**：从连读缓冲区取 GZ raw，`rad/s = raw / 32768.0f * 2000.0f * PI / 180.0f`（等价 `raw * 0.061 * PI/180`，模块量程 ±2000°/s、分辨率 0.061(°/s)/LSB）。**注意这是角速度，不做相对化**（零偏由模块内部处理）。在回传里写清换算依据。

### W3 — yaw 融合策略（必做，核心）

在 `Chassis_Update()` 的 `Chassis_UpdateOdometry()` 之后实现：

```text
若 imuAvailable == 1：
    chassisYaw = IMU_GetYaw();        ← IMU 为主（S2-03 已证明编码器旋转打滑 2 倍）
    位置 x/y 仍用编码器累计距离积分，但用 IMU yaw 作为积分角度
否则：
    chassisYaw 保持 S2-03 的编码器积分（兜底）
```

- **融合开关**（Watch 可写）：`extern uint8_t chassisYawFusionMode;`（0=纯编码器，1=IMU 融合，默认 1 但 IMU 不可用时自动回 0）。两模式可切换可对比。
- **积分一致性**：改用 IMU yaw 后，`Chassis_UpdateOdometry()` 位置积分的 `yaw_mid` 应基于**选中的 yaw 源**，避免位置用编码器角、yaw 用 IMU 角的割裂。若同帧切换难实现，回传说明方案。
- **不做**：完整姿态解算 / 四元数导航 / 复杂 EKF / SLAM —— 模块已自带卡尔曼，STM32 只做 yaw 源选取与相对化。

### W4 — 保留与隔离（必做）

- S2-01/02/03 能力全保留：运动学下发、`wheelScale` 里程计、`Chassis_GetPose()`、`Chassis_ResetOdometry()`。
- `Chassis_ResetOdometry()` 同时重置 `imuYaw0`（重新采当前 IMU yaw 作零点）。
- IMU yaw / yaw_rate **不喂速度 PID**（PID 反馈仍是 `motorSpeedRpm`）；IMU yaw_rate 仅供 Watch/上层。
- OLED 不改；上电停车不变；不改 PID/安全宏。

## 7. 安全要求

```text
上电默认停车（TARGET=0）
★ 运行时 I2C 读绝不用 HAL_GetTick 超时；DWT->CYCCNT 硬超时 2 ms，异常不卡 SysTick
无传感器/NACK/总线异常 → imuAvailable=0 → 自动回纯编码器模式
不开 IMU 中断；1 ms 中断内不做 HAL 阻塞长等待
IMU yaw 不进速度 PID；不做绝对航向/磁力计；不按 0x53 写配置
写配置前 KEY(0x69)=0xB588 解锁
CubeMX 只由用户操作，模型不得直接改 .ioc
PID 循环禁 HAL_Delay；不改引脚/定时器
```

## 8. 验收标准

1. **静态核对（重点）**：
   - **无任何运行时 `HAL_I2C_Mem_Read`/HAL 阻塞 API 依赖 HAL_GetTick 超时**；有 DWT->CYCCNT 硬超时实现，超时分支能安全返回；
   - 10 ms 分频在 `chassis.c` 的 `Chassis_Update()` 内，不在 control.c；
   - `IMU_Init()` 配置序列：KEY=0xB588 解锁 → AXIS6=1 → RRATE=0x09 → RSW=0x0C，**无 0x53 写操作**；
   - `IMU_GetYawRate()` 读 GZ(0x39)、换算含 `2000/32768*pi/180`；从 0x39 连读 14 字节取 GZ 与 Yaw；
   - `IMU_GetYaw()` 返回 `wrap(imuYawSign*(raw−yaw0)+offset)`；IMU 为主融合、不可用回退；`imuAvailable` 正确；IMU yaw 未喂 PID。
2. Keil Build **0 Error / 0 Warning**，生成新 `breathing.hex`。
3. 上电安全：车不动，OLED `0000.0 RPM  000%`。
4. **异常测试（必做）**：**不接 IMU**（或断开）上电，系统必须正常运行不死锁 —— 车不动、OLED 正常刷新、无卡死。这是死锁防护的实测证据。
5. Watch 可读：`imuAvailable`、`IMU_GetYaw()`、`IMU_GetYawRate()`、`chassisYaw`、`chassisYawFusionMode`、`imuYawSign`、`imuYawOffsetRad`。
6. **实车（接上 IMU）**：原地转 90°，`chassisYaw` 应接近 +1.57 rad（对比 S2-03 纯编码器仅约 0.785 rad）；逆时针转 yaw 增加（符号用 `imuYawSign` 修正）；两模式切换能看出差异。不便测则留 S2-TEST。
7. 未触碰禁止文件；`encoder.c` 公式与 PID 参数未改。

## 9. 测试方法（人类执行）

```text
0. W0 已完成（CubeMX I2C2 已启用、Keil 六 .c 全在）
1. 先测「不接 IMU 上电」：确认系统不死锁（车不动、OLED 正常）—— 必做
2. Keil Build，记录 0 Error / 0 Warning 与 hex 时间
3. 接上 IMU 上电，静态核对 §8 第 1 条 + Watch 变量
4. 实车原地转 90°，看 chassisYaw 是否接近 1.57 rad
5. 回传
```

## 10. 回传要求

```text
1. 修改文件清单（含新建 imu.h/c、Keil Add 情况）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. ★ 运行时 I2C 读方案（A: DWT->CYCCNT 轮询 / B: IT 状态机）与硬超时实现代码
4. 「不接 IMU 上电」异常测试结果（证明不死锁）
5. IMU_Init 配置序列代码（含 KEY 解锁）与 I2C 连读/字节序处理
6. IMU_GetYawRate 换算依据；Watch 变量与模式切换方式
7. 实车旋转对比数据或注明「留 S2-TEST」
8. 遗留问题与风险
9. 是否建议进入 S2-05（等效轮距与差异标定）
```

---

**下一位提示**：本单只做 IMU 接入与 yaw 融合（6 轴模式、相对角、IMU 为主、DWT 硬超时）。S2-05 用原地旋转标定**等效轮距（S2-03 实测约 0.40 m）**与左右轮增益；之后是 S2-TEST 统一验收（通信已移出阶段 2）。若接口需调整，**先回报 WorkBuddy，不要自行改**。
