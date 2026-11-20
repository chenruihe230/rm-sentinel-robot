# 修改记录 (CHANGELOG)

项目：呼吸机 / 四轮电机控制（STM32F407VET6，Keil MDK-ARM，工程 breathing）

> 说明：以后每次改动都追加一条到这里（日期 + 改了什么 + 涉及文件 + 是否需要动 CubeMX）。
> 注意：从 CubeMX 重新生成代码会重写 `MDK-ARM/breathing.uvprojx`，手动加进工程的 .c 文件（pid.c、control.c 等）会被冲掉，需在 Keil 里重新 Add。

## 2026-11-08

### 修复 M4 后退不转
- 现象：后退时 M4 的 IN2 拉不高，正转正常。
- 过程：M4_IN2 从 PE7 改到 PE8（PE7 测为低电平，拉不高）；最终确认是 **IN2 信号线问题**（软件挪了引脚但板子跳线没跟着挪 / 接触不良），不是驱动、电机、软件问题。
- CubeMX：`.ioc` 里 PE8 设为 M4_IN2（GPIO_Output）并重新生成。
- 涉及文件：`breathing.ioc`、`Core/Inc/main.h`、`Core/Src/gpio.c`。

### 新增速度环 PID
- 新增 `Core/Inc/pid.h`、`Core/Src/pid.c`（位置式 PID，积分抗饱和 + 输出限幅 ±100）。
- `Core/Src/main.c` 集成：目标转速 + 编码器测速 + PID 输出占空比。
- 测速窗口：1ms → 10ms → 100ms（解决低速下速度读数正负乱跳）。

### 电机控制搬入 SysTick 中断
- 新增 `Core/Inc/control.h`、`Core/Src/control.c`（控制逻辑集中，含开环/闭环开关）。
- `Core/Src/main.c` 只保留 OLED 显示，控制逻辑移除。
- `Core/Src/stm32f4xx_it.c` 的 `SysTick_Handler` 加 `Control_Update()`（每 1ms 精确执行，不受 OLED 阻塞 I2C 影响）。
- Keil 工程加入 pid.c、control.c。
- 原因：OLED `OLED_Refresh()` 阻塞 I2C 约 90ms，和电机控制挤在同一主循环导致车卡顿、OLED 不刷新。

### 编码器参数改成每电机独立 + 加测试模式
- `encoder.h/c`：把全局 `ENCODER_DIRECTION` / `ENCODER_COUNTS_PER_REV` 改成每电机的 `direction` / `counts_per_rev`（在 `encoder.c` 的 `encoderParams[]` 里配置）。
- `control.c`：加 `CONTROL_TEST_MODE`（测试模式不驱动电机，OLED 显示每路累计计数）；速度计算改用每电机的 `counts_per_rev`。
- `main.c`：OLED 在测试模式下显示累计计数。
- 目的：逐电机测编码器方向/分辨率，把四个参数对齐，方便后续统一 PID 参数。

### 当前状态 / 待办
- `control.c` 顶部：`CONTROL_TEST_MODE = 1`（编码器测试模式）。
- 编码器实测：正转一圈计数 M1=1329、M2=1327、M3=1312、M4=1332（约 1320）→ 已填入 `encoderParams[]`（`counts_per_rev` 由 2000 改成实测值）。
- 驱动模式下发现 M3/M4 给正占空比时转速显示负（电机正转方向与编码器/手推方向相反）→ 把 M3/M4 的 `direction` 改成 -1，保证"正指令 → 正转速"，否则 PID 会正反馈狂转。
- 待办：关测试模式（`CONTROL_TEST_MODE = 0`）→ 开环标定 → 定 KP/KI → 切 `CONTROL_OPEN_LOOP = 0` 闭环。

## 2026-11-09

### 编码器引脚开内部上拉（修 M3/M4 转速虚高、堵转读数反向升高）
- 现象：开环 20% 占空比下 M1≈62 RPM 正常；M3/M4 显示 800~1200，手动堵转读数反而更高；M2 时好时坏（同一次会话里 1200 → 正常）。
- 定位：集成四路驱动板，GND 共用，排除地线/接线问题。`tim.c` 里 8 个编码器引脚是 `GPIO_NOPULL`；编码器为开漏输出时 A/B 线浮空，电机 PWM 一开就串噪声 → 堵转电流最大、噪声最大、读数越高，与现象完全吻合（手转测试模式电机不转时读数干净 ~1320 也佐证）。
- 修改：CubeMX 里 8 个编码器引脚 GPIO Pull 从 No pull 改 Pull-up，重新生成。
  - M1：PA6/PA7（TIM3），M2：PD12/PD13（TIM4），M3：PA0/PA1（TIM5），M4：PA5/PB3（TIM2）
- 涉及文件：`breathing.ioc`、`Core/Src/tim.c`（重新生成后 `GPIO_NOPULL` → `GPIO_PULLUP`）。
- CubeMX：是。重新生成后需在 Keil 重新 Add 手动 .c：pid.c、control.c、encoder.c、motor.c、oled.c。

### 修正 M3/M4 电机极性（IN1/IN2 接反）
- 现象：测试模式手转轮子「前进」时 M3/M4 计数为负，驱动模式给正占空比却显示正 → 说明 M3/M4 的电机 +占空比 把轮子往「后退」方向转，IN1/IN2（或电机两根线）接反了。
- 修改：`motor.c` 里 M3/M4 的 IN1/IN2 引脚对调（交换 `M3_IN1`↔`M3_IN2`、`M4_IN1`↔`M4_IN2`），使「+占空比 → 轮子朝手转的"前进"方向」。
- 关键：测试模式不经过电机，所以只换电机线不影响测试模式符号；测试模式符号只由 `direction` 决定。
- 最终：`encoder.c` 里 M3/M4 的 `direction` 取 **-1**（编码器 AB 相序与前进方向相反），配合上面的电机对调，使「+占空比 → 前进 → 编码器正计数」三处一致。
- 结果：测试模式（手转前进）和驱动模式（+20%）下 M3/M4 均为正，符号不再互相矛盾。
- 涉及文件：`Core/Src/motor.c`、`Core/Src/encoder.c`。
- CubeMX：否。

## 2026-11-16 [Gemini 修改]

### 编码器定时器加硬件输入数字滤波 + SysTick 启动保护（由 Gemini 修改）
- 现象：PWM=0 手推前进 4 路正常（约 1300/圈）；开启 PWM 驱动后 M2 飙升至 +1200~1300、M3/M4 计数达到 1400~2200/100ms（换算约 -1300 RPM，实际轮速仅 48~60 RPM），与 20 kHz PWM 开关周期串扰一致。
- 修改：
  1. `Core/Src/tim.c`：`MX_TIM2_Init` ~ `MX_TIM5_Init` 将 `ClockDivision` 由 `TIM_CLOCKDIVISION_DIV1` 改为 `TIM_CLOCKDIVISION_DIV4`，`IC1Filter` / `IC2Filter` 由 `0` 改为 `15`（对应约 `12.2 µs` 硬件滤波窗口）。
  2. `Core/Src/control.c`：增加 `controlInitialized` 标志，防止 `Control_Init()` 完成前 `SysTick_Handler` 提前调用 `Control_Update()` 访问未就绪外设。
- 涉及文件：`Core/Src/tim.c`、`Core/Src/control.c`。
- CubeMX：否（注意若后续用 CubeMX 重新生成，需在 CubeMX TIM2~TIM5 参数中同步 `Clock Division = DIV4` 与 `Input Filter = 15`，或重新应用本次 `tim.c` 修改）。

## 2026-11-17 [Claude 记录]

> 本节由 Claude 整理记录（经用户确认后写入）。

### 确认当前工程状态正确：编码器/电机方向全部对齐
- 结论：**当前工程代码即为正确状态**，本次只更新记录，不改代码。
- 验证结果：
  - 编码器引脚内部上拉 + TIM2~TIM5 硬件输入数字滤波（`ClockDivision = DIV4`、`IC1Filter/IC2Filter = 15`）后，**开 PWM 驱动时四路编码器读数均正常**，不再出现 M2/M3/M4 虚高、堵转读数反向升高等现象。
  - 测试模式（手推）与驱动模式（PWM 驱动）下，四路计数符号一致。
  - M1~M4 的电机转向、编码器计数方向、"前进"方向三者已对齐。
- 与历史记录不一致之处（**以当前代码为准**）：
  - M3/M4 在 `Core/Src/encoder.c` 的 `direction` 当前为 **+1**；11-09 条目里的 **-1 是当时的调试中间状态，已不再适用**。配合 `Core/Src/motor.c` 中 M3/M4 的 IN1/IN2 对调，保持"+占空比 → 前进 → 编码器正计数"三处一致。
  - M4_IN2 当前引脚为 **PE7**（`.ioc`、`Core/Inc/main.h`、`Core/Src/gpio.c` 三处一致）；11-08 条目中的 PE8 是当时的临时试验，现已不使用。
- 当前运行配置（`Core/Src/control.c` 顶部）：
  - `CONTROL_TEST_MODE = 0`
  - `CONTROL_OPEN_LOOP = 1`，`CONTROL_OPEN_LOOP_DUTY = 0`
  - `CONTROL_TARGET_RPM = 60`，PID 周期 100 ms，KP=0.1 / KI=0 / KD=0
- 构建：Keil MDK 0 Error / 0 Warning（2026-11-17 21:48 重新构建，`breathing.hex` 已更新）。
- CubeMX：`.ioc` 中 TIM2~TIM5 已同步 `ClockDivision = DIV4`、`IC1Filter/IC2Filter = 15`，后续重新生成不会再冲掉硬件滤波设置。
- 涉及文件：`AI_COLLAB/CHANGELOG.md`（本节无代码逻辑改动）。

### 注释与文件编码整理（Claude）
- `Core/Src/main.c`：文件本身是 **UTF-8**（不是 GBK），但有 9 个汉字字节被写坏成了 `?`（0x3F），导致编辑器判定为非法编码、中文注释乱码。已按上下文修复为「到、留、由、近、总」及 4 处句号「。」。
  - 校验：修复前后文件长度一致，仅这 9 个字节不同，其余字节逐一比对完全相同；**不影响编译和运行**。
- `Core/Src/encoder.c`：M3/M4 参数注释里的"取 -1"已过时，改为说明当前 `direction = +1`，方向由 `Core/Src/motor.c` 中 M3/M4 的 IN1/IN2 对调对齐。
- `Core/Src/control.c`：`/* 固定20% PWM */` 改为"固定占空比开环（数值见 CONTROL_OPEN_LOOP_DUTY）"，与当前 `CONTROL_OPEN_LOOP_DUTY = 0` 一致。
- 涉及文件：`Core/Src/main.c`、`Core/Src/encoder.c`、`Core/Src/control.c`、`AI_COLLAB/CHANGELOG.md`。
- CubeMX：否。
- 注意：`main.c` 因编码修复时间戳变化，Keil 会重新编译它；以上均为注释/编码改动，不改变逻辑。

### 编码器多圈标定 + 分辨率定死（Claude）
- 方法：临时把 `CONTROL_TEST_MODE` 置 1，上电清零，手推每路轮子沿前进方向**整 5 圈**，读取累计计数。
- 实测：四路总计数均为 **6590**（极差 ≤5），折算 **1318 计数/圈**。
- 取值依据：
  - 1318 不是 4 的倍数，而 A/B 四倍频计数必然是 4 的倍数 → 说明手推起止点有偏差。
  - 按电机规格 11 线 × 4 倍频 × 30:1 = **1320**；5 圈少 10 个计数，正好是 0.15% 的对标记误差。
  - 因此定死 **1320**（与实测仅差 0.15%，对测速和 PID 无影响）。
- 代码：
  - `Core/Src/encoder.c`：删除每电机独立的 `encoderParams[]`，改为全局常量 `ENCODER_COUNTS_PER_REV = 1320U`，四路共用；`direction` 仍单独配置（当前四路均为 +1）。
  - `Core/Inc/encoder.h`：同步更新说明。
  - `Core/Src/control.c`：标定完成后 `CONTROL_TEST_MODE` 改回 0（开环、占空比 0 的配置不变）。
- 涉及文件：`Core/Src/encoder.c`、`Core/Inc/encoder.h`、`Core/Src/control.c`、`AI_COLLAB/CHANGELOG.md`。
- CubeMX：否。
- 下一步：接入速度环 PID（先做开环占空比→RPM 标定，再定 KP/KI）。

### 当前状态 / 明天待办（2026-11-17 收工记录）
- **编码器已定死**：`Core/Src/encoder.c` 中 `ENCODER_COUNTS_PER_REV = 1320U`，四路共用。标定：每路手推 5 圈总计数 6590（极差 ≤5），折算 1318；因 1318 非 4 的倍数、且与 11 线 × 4 × 30:1 = 1320 仅差 0.15%，取理论值 1320。
- **`Core/Src/control.c` 当前配置**：`CONTROL_TEST_MODE = 0`、`CONTROL_OPEN_LOOP = 1`、`CONTROL_OPEN_LOOP_DUTY = 0`、目标 60 RPM、PID 周期 100 ms、KP=0.1 / KI=0 / KD=0。
- **构建状态**：最后一次 Keil 构建为 22:03（当时 `TEST_MODE=1`、还是旧的 `encoderParams[]`）；之后 `encoder.c`、`encoder.h`、`control.c` 在 22:08 又改过，**当前源码尚未编译**。明天第一件事：Keil Build + 下载。
- 已验证：`encoder.c`、`control.c`、`main.c` 单独用 armcc 编译，均 0 error / 0 warning。
- **明天计划**：
  1. OLED 驱动模式显示改为 **RPM + 输出占空比**（当前显示的是 N/A 原始计数）。
  2. 开环 `CONTROL_OPEN_LOOP_DUTY = 20`，记录四路稳态 RPM；再测 40%、60%，得到"占空比 → 转速"曲线。
  3. 定 KP/KI，切 `CONTROL_OPEN_LOOP = 0` 闭环。
- CubeMX：否。

## 2026-11-18 [派单 01 — Argon4 实现 / WorkBuddy 收口]

### 编码器测速夯实 + 里程计基础（已编译、实车确认）

- 背景：接 PID 前先夯实测速输入；人类用户裁定「测速 + 里程计一起做」，并授权本次改 `encoder.c`（阶段 1 任务单原禁止，仅限本次）。
- 改动明细：
  1. `Core/Src/encoder.c`：`speed_rpm` 公式**保持不变**（WorkBuddy 曾误判「差 1000 倍」，15:15 由用户/Codex 纠正；系数 60000 已含 60 s × 1000 ms），仅补注释说明「1 ms 瞬时 RPM、噪声大，PID 用 100 ms 窗口值」。新增 `distance_m` 字段与 `Encoder_GetDistanceM()` / `Encoder_ResetOdometry()`；轮径 ≤0 或空指针时距离返回 0。
  2. `Core/Inc/encoder.h`：新增 `WHEEL_DIAMETER_M = 0.0f` 占位宏（TODO：待人类实测轮径后填入，米）、`distance_m` 字段及两个里程计接口声明。
  3. `Core/Src/control.c`：顶部补「1 ms 采样 / 100 ms 窗口」时序契约注释；新增 `Control_GetDistanceM()` 转发接口。**所有宏数值未变**（`TARGET_RPM=60`、`PID_PERIOD=100`、KP=0.1/KI=0/KD=0、`OPEN_LOOP=1`、`DUTY=0`）。
  4. `Core/Inc/control.h`：新增 `Control_GetDistanceM()` 声明。
  5. `Core/Src/main.c`：驱动模式 OLED 从 N/A 原始计数改为四行显示 M1~M4 的 RPM（1 位小数、带符号）+ 输出占空比（%）；测试模式分支保留原样。
- 验证结果：
  - **编译**：11-18 22:01 Keil Build，0 Error / 0 Warning，生成新 `breathing.hex`（Code=9988、RO=2632、RW=284、ZI=3324）。
  - **W1 回归检查**：`speed_rpm` 公式与修改前逐字一致，只多注释；全文无 `0.001f` 或任何 1000 倍放大改动。✓
  - **实车（人类确认）**：上电静止车不动，OLED 四行显示 `0000.0 RPM  000%`；手推前进四路均显示正 RPM，后拉均显示负 RPM，停稳后回 `0000.0`。✓
  - **禁止文件未触碰**：`.ioc`、`tim.c`、`motor.c`、`gpio.c`、`main.h`、`pid.c` 时间戳均未变。✓
- 涉及文件：`Core/Inc/encoder.h`、`Core/Src/encoder.c`、`Core/Inc/control.h`、`Core/Src/control.c`、`Core/Src/main.c`；协作文档 `AI_COLLAB/DISPATCHES/STAGE_01/DISPATCH_01_ENCODER.md`、`AI_COLLAB/AI_SYNC.md`、`AI_COLLAB/AI_WORKLOG_WORKBUDDY.md`。
- CubeMX：否。
- 遗留：`WHEEL_DIAMETER_M` 仍为 0，距离读数暂无效，待人类实测轮径填入；PID 周期口径（方案 A/B/C）待人类 / Codex 裁决；切闭环前必须先将 `CONTROL_TARGET_RPM` 归零或由人类现场写入目标速度。
- 下一步：派单 02（PID 接入）需等轮径回填 + 周期方案裁决后才能出。

## 2026-11-18 22:14 [补充收口 — 轮径标定回填]

### 1 m 实推轮径标定完成 + 最终 hex 更新

- **授权来源**：`encoder.c` 的修改依据为**人类用户 2026-11-18 14:57 明确授权**（阶段 1 任务单原禁止改 `encoder.c`，仅限派单 01 本次任务）；本次轮径回填在同一授权范围内。
- **范围核对**：仅改动允许的 5 个文件；禁止文件（`.ioc`、`tim.c`、`motor.c`、`gpio.c`、`main.h`、`pid.h/.c`、`breathing.uvprojx`、`docs/*`、`AI_COLLAB/CHANGELOG.md`、`AI_*.md`）时间戳复核均未变。
- **轮径标定（1.00 m 地上直线实推）**：
  - 四路计数：M1=6283、M2=6338、M3=6310、M4=6379，均值 **6327.5 脉冲/米**（极差 96，约 1.52%）。
  - 反推：6327.5 / 1320 = 4.7936 圈/米 → 周长 208.613 mm → **轮径 66.404 mm**。
  - 已填入 `Core/Inc/encoder.h`：`#define WHEEL_DIAMETER_M 0.066404f`，替换原 0.0f 占位，注释保留标定数据与来源。
  - WorkBuddy 独立验算：与填入值一致 ✓。
- **逐文件改动（在 22:04 记录基础上新增/复核）**：
  1. `Core/Inc/encoder.h`：轮径宏由 0.0f 占位改为 **0.066404f 实测值**；`distance_m` 成员、`Encoder_GetDistanceM()` / `Encoder_ResetOdometry()` 声明不变。
  2. `Core/Src/encoder.c`：**W1 公式逐字未动**，仅保留补充注释；里程计实现与 `distance_m` 维护不变；全文未引入 `0.001f`（`pid.c` 中的 `dt=0.001f` 是原有除零保护，与 W1 无关）。
  3. `Core/Inc/control.h`：`Control_GetDistanceM()` 声明不变。
  4. `Core/Src/control.c`：22:12 重编，复核时序契约注释与安全状态未变（`TEST_MODE=0`、`OPEN_LOOP=1`、`DUTY=0`、`TARGET_RPM=60`、`PID_PERIOD=100`、KP=0.1/KI=0/KD=0）；`Control_GetDistanceM()` 不变。
  5. `Core/Src/main.c`：OLED 四行 RPM + 占空比显示不变（22:01 版已实车确认）。
- **编译**：11-18 **22:12:13** 生成新 `breathing.hex`（36366 bytes），重编 `control.c` + `encoder.c`，**0 Error / 0 Warning**（Code=9996、RO=2632、RW=284、ZI=3324）。
- **实测状态（分版本记录，不混为一谈）**：
  - 22:01 版 hex：人类已实车确认（上电不动、OLED `0000.0 RPM 000%`、手推前进正 / 后拉负 / 停稳回零）。
  - 1 m 直推标定：已完成，四路计数 6283~6379、前进符号一致。
  - **22:12 最终版 hex（含 0.066404f 轮径 + RPM/% 画面）：待上电看一眼 OLED 确认，尚未确认。**
- CubeMX：否。
- 遗留：① 最终版 hex 上电确认；② PID 周期口径（方案 A/B/C）待人类 / Codex 裁决；③ 切 `CONTROL_OPEN_LOOP=0` 前须先将 `CONTROL_TARGET_RPM` 归零或由现场写入安全目标转速。

## 2026-11-19 20:35 [派单 02 — 1 ms 速度 PID（方案 A）收口]

### 1 ms 闭环 PID 接入（已编译、实车初步验证）

- **裁决依据**：人类用户 2026-11-19 20:20 拍板 PID 周期采用**方案 A（1 ms PID）**，否决 B（100 ms）/ C（20 ms 折中）。
- **改动范围**：仅 `Core/Inc/control.h`、`Core/Src/control.c`。禁止文件时间戳复核未变：`encoder.h/c`、`pid.h/c`、`main.c`、`tim.c`、`motor.c`、`gpio.c`、`breathing.ioc`、`docs/*`。
- **实现要点**：
  1. **W1 周期**：`CONTROL_PID_PERIOD_MS=1U`、`CONTROL_PID_DT=0.001f`；沿用现有 SysTick（每 1 ms 调 `Control_Update()`），**未开新定时器中断**；每 1 ms 完成「读编码器 → 滤波 → PID → 输出」。
  2. **W2 抗噪声**：新增 `CONTROL_SPEED_LPF_ALPHA=0.20f`（一阶低通）与 `CONTROL_ZERO_GUARD_MS=20U`（连续 20 ms 无脉冲则速度归零，约 <2.3 RPM）；`motorSpeedFiltered[4]` 为滤波后速度，`Control_GetSpeedRpm()` 返回该值，保证 OLED / Watch / PID 三处一致。
  3. **W3 安全切换**：`CONTROL_TARGET_RPM=0.0f`（先归零）、`CONTROL_OPEN_LOOP=0`（后切闭环）；新增 `Control_SetTargetRpm(index, rpm)` / `Control_GetTargetRpm(index)`，全局 `motorTargetRpm[0..3]` 可由 Watch 写入。
  4. **W4 参数保持**：KP=0.1 / KI=0 / KD=0、输出 ±100 限幅未改；循环内无 `HAL_Delay()`。
  5. **W5 诊断保留**：独立 `CONTROL_DIAG_PERIOD_MS=100U` 窗口刷新 `debugNet[]` / `debugAbs[]`。
- **新增 / 导出 Watch 变量**：`motorSpeedFiltered[0..3]`（滤波后 1 ms RPM）、`motorTargetRpm[0..3]`（目标 RPM，默认 0，可写）、`debugNet[]` / `debugAbs[]`（100 ms 诊断计数，保留）。
- **编译**：11-19 Keil Build，**0 Error / 0 Warning**（Code=10272、RO=2632、RW=268、ZI=3356），生成 `breathing.hex`（37107 bytes）。
- **实车（人类现场确认）**：上电静止车不动，OLED 显示 `0000.0 RPM  000%`；手推前进有明显**负反馈阻力**，OLED 左列 RPM 为正且平滑变化、右列输出占空比为负（-%），松手回零。暂未给非零目标（KP=0.1/KI=0 为未整定基线）。
- **WorkBuddy 收口核对发现（2 处偏差，不影响当前安全，需后续留意）**：
  1. **hex 时间戳**：文件系统实际为 **11-19 20:33:07**，实现方报告 20:25:45；文件大小一致（37107 bytes），编译日志参数一致。以文件系统时间为准。
  2. **`CONTROL_OPEN_LOOP_DUTY` 由 0 改为 20**：实现摘要未提此项。当前 `OPEN_LOOP=0`，该宏不生效、不影响安全；但**下一张开环标定派单的起点占空比是 20%**，必须显式写明，避免误判为 0。
- CubeMX：否。
- 遗留：① 开环占空比 → 稳态 RPM 标定曲线未测；② KP/KI 未整定（当前为基线值）；③ 四轮阶跃测试与阶段 1 验收未做。
- 下一步：派单 03（开环标定 + KP/KI 整定 + 阶跃验收）。

## 2026-11-19 21:14 [派单 03 — 开环标定 + KP/KI 整定 + 阶跃验证 收口]

### 阶段 1 速度环核心完成（已编译、实车验证、安全基线固化）

- **改动范围**：仅 `Core/Inc/control.h`、`Core/Src/control.c`。禁止文件时间戳复核未变：`encoder.h/c`（含正确 `speed_rpm` 公式与轮径 0.066404f）、`pid.h/c`、`main.c`、`tim.c`、`motor.c`、`gpio.c`、`breathing.ioc`、`docs/*`。
- **实现要点**：
  1. `control.h`：引入 `motor.h`，导出 `motorOpenLoopDuty[4]` / `controlCalibrationMode` / `motorKp/Ki/Kd`，新增 `Control_SetCalibrationMode()` / `Control_SetOpenLoopDuty()` / `Control_SetGains()`。
  2. **W1 标定**：`controlCalibrationMode`（`uint8_t`，默认 0）与 `motorOpenLoopDuty[4]`（`int16_t`，默认全 0）；**进/出标定模式自动把目标转速归零并 `PID_Reset()`**，防止切换瞬间冲车。为 1 时按占空比开环输出、不走 PID。
  3. **W2 运行时参数**：KP/KI/KD 改为全局 `float motorKp/motorKi/motorKd`，每 1 ms 闭环前同步进 `motorPid[]`，Watch 改参立即生效；`Control_SetGains()` 带参数范围保护。
  4. **W3/W4 保持**：1 ms 周期、LPF alpha=0.20 + 20 ms 零计数保护、±100 限幅、100 ms 诊断窗口、里程计接口、OLED 显示全部不变。
  5. **安全基线固化**：整定完成后 `CONTROL_TARGET_RPM` 恢复 **0.0f**、`CONTROL_OPEN_LOOP_DUTY` 由 20 改回 **0**、标定模式默认 0；最终参数写入 `CONTROL_PID_KP=0.4f / KI=2.5f / KD=0.0f`。
- **编译**：11-19 **21:12:48** 生成 `breathing.hex`（37655 bytes），重编 `control.c`，**0 Error / 0 Warning**（Code=10448 / RO=2632 / RW=288 / ZI=3360）。
- **Watch 变量与操作顺序**：
  - `controlCalibrationMode`（默认 0）、`motorOpenLoopDuty[0..3]`（默认全 0）、`motorKp/Ki/Kd`（默认 0.4/2.5/0）、`motorTargetRpm[0..3]`（默认 0）、`motorSpeedFiltered[0..3]`、`debugNet/debugAbs[0..3]`。
  - 标定流程：`controlCalibrationMode=1` → 逐级写占空比 0→60% → 占空比回 0 → `controlCalibrationMode=0`（自动清目标、复位 PID）。
  - **本次人类现场采用「不连 Watch、改初值重编看 OLED」方式完成全部实测**。
- **实车数据（人类确认）**：
  - 开环标定（车架空）：20% ≈ 60 RPM 四路平稳；40% M1/M3≈130、M2/M4≈120 RPM；60% M1/M3≈200、M2/M4≈180 RPM，均平稳无异常抖动。
  - 增益模型：左轮约 3.5 RPM/%、右轮约 3.0 RPM/%，均值 3.25 RPM/%；左右固有差约 10%；外推满占空比极速约 **300~340 RPM**。
  - 闭环（KP=0.4/KI=2.5/KD=0，1 ms）：100 RPM 目标时四路稳态 96~104 RPM（误差 ≤±4%，满足 ≤5%），占空比 32~35%，无超调；200 RPM 四路均能稳住；负转速反转与 60 RPM 低速均稳、无明显震荡。
- **重要发现（需裁决）**：本款电机满占空比极速约 **300~340 RPM**，`TASK_STAGE_01_PID.md` 的 **400 RPM 测试点超出硬件上限**。建议阶段 1 验收上限按 **200 RPM** 核定；任务单修订由 Codex 接 MiMo 在阶段末处理，本收口不改任务单。
- **遗留**：① 尚未做落地 200 RPM 长时间直行对比；② 外部上位机下发指令测试留待阶段 2 联调；③ 400 RPM 测试点裁决。
- **下一步**：阶段 1 验收评审 → 移交阶段 2（底盘运动学与整车里程计）。总览与版本规划交 Codex 接 MiMo。
- CubeMX：否。

## 2026-11-20 16:31 [阶段 1 正式交付]

### 100% 占空比极速补测 + 验收口径核定

- **补测（车架空）**：`controlCalibrationMode=1`、`motorOpenLoopDuty[]=100`，四路 M1~M4 最大稳态转速均约 **330 RPM**。此前 300~340 RPM 为外推，现由 100% 实测确认。
- **正式裁决（人类拍板）**：
  - 阶段 1 验收上限**正式核定为 200 RPM**；`TASK_STAGE_01_PID.md` 的 400 RPM 测试点因硬件上限豁免，任务单修订交 Codex 接 MiMo 阶段末处理。
  - 阶段 2 目标转速建议 **≤250 RPM**（留 20~25% 余量）。
- **安全基线恢复复核**（WorkBuddy 逐项核对）：`controlCalibrationMode=0U`、`motorOpenLoopDuty[]={0,0,0,0}`、`CONTROL_TARGET_RPM=0.0f`、`CONTROL_OPEN_LOOP=0`、`KP/KI/KD=0.4/2.5/0.0`、1 ms 闭环（LPF 0.20 + 20 ms 零保护）；禁止文件时间戳全未变。
- **编译**：11-20 **16:30:21** Keil Build，**0 Error / 0 Warning**，生成 `breathing.hex`（37655 bytes）。
- **交付**：阶段 1 正式完成，验收记录定稿于 `AI_COLLAB/ACCEPTANCE/STAGE_01.md`；移交单 `AI_COLLAB/HANDOFF_TO_CODEX_STAGE_02.md` 已编制，交 Codex 接 MiMo 做总览更新（§6 分工表同步）、任务单 400→200 RPM 修订与阶段 2 版本规划。
- CubeMX：否。
