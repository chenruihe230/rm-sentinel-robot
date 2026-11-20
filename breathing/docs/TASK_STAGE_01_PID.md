# 阶段 1 任务单：四轮独立速度 PID

> 状态：阶段 1 已于 2026-11-20 正式交付。
> 正式验收上限：200 RPM。
> 豁免说明：100% PWM 实测硬件极速约 330 RPM，400 RPM 物理上无法完成；人类于 2026-11-20 核定阶段 1 验收上限为 200 RPM。

## 目标

在当前四轮底盘工程上实现四个轮子独立速度 PID，为后续底盘运动学打基础。

## 项目路径

`D:\stm32\stm32f4\breath\breathing`

## 允许修改

```text
Core/Inc/pid.h
Core/Src/pid.c
Core/Inc/control.h
Core/Src/control.c
Core/Src/main.c
MDK-ARM/breathing.uvprojx
```

## 禁止修改

```text
breathing.ioc
Core/Src/tim.c
Core/Src/motor.c
Core/Src/encoder.c
Core/Src/gpio.c
Core/Inc/main.h
```

如需修改 CubeMX、引脚、定时器或方向逻辑，必须先提交架构变更，不得直接修改。

## 硬件约束

```text
M1：PE9 / PE0 / PE1 / TIM3 / PA6 / PA7
M2：PE11 / PE2 / PE3 / TIM4 / PD12 / PD13
M3：PE13 / PE4 / PE5 / TIM5 / PA0 / PA1
M4：PE14 / PE6 / PE7 / TIM2 / PA5 / PB3
```

M4_IN2 当前为 PE7。

## 功能要求

1. 四个 PID 状态完全独立。
2. 控制周期为 1 ms。
3. 每个 PID 使用自己的：
   - `target_rpm`
   - `measured_rpm`
   - `error`
   - `last_error`
   - `integral`
   - `output`
4. PID 输出限制为 `-100～+100`。
5. 积分值必须限幅。
6. 目标速度为 0 时，输出必须为 0。
7. PID 循环中禁止 `HAL_Delay()`。
8. OLED 刷新保持 100 ms，不进入 PID 循环。
9. 保留 Watch 变量：
   - 四个 `target_rpm`
   - 四个 `measured_rpm`
   - 四个 `output`
10. 默认目标速度必须为 0，不能让程序下载后自动高速转动。

实现基线：

```text
KP = 0.4
KI = 2.5
KD = 0
输出范围 = -100～+100
速度低通 = LPF 0.20
零计数保护 = 20 ms
```

## 调试模式

允许保留一个明确的测试变量，例如：

```c
motorTargets[MOTOR_COUNT]
```

但必须方便切换：

```text
全部停车
单独测试 M1
单独测试 M2
单独测试 M3
单独测试 M4
统一阶跃测试
```

## PID 调试方法

先使用 PI 控制：

```text
Ki=0, Kd=0
逐步增加 Kp
加入 Ki 消除稳态误差
只有必要时才加入 Kd
```

## 验收测试

每个轮子分别测试：

```text
0 → 200 RPM
200 → 0
正转
反转
```

直行一致性测试：

```text
M1 = 200 RPM
M2 = 200 RPM
M3 = 200 RPM
M4 = 200 RPM
```

正式验收建议：

```text
稳态误差 ≤ 5%
超调 ≤ 10%～15%
稳定时间 < 300～500 ms
无持续振荡
四个轮子速度差异 < 5%
目标为 0 时可靠停车
```

## 交付内容

```text
1. 修改文件清单
2. Keil 编译结果
3. Watch 变量说明
4. PID 参数初始值
5. 四轮阶跃测试记录
6. 遗留问题
7. 是否允许进入阶段 2
```
