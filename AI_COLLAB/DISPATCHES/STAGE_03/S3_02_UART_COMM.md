# 派单 S3-02 — USART1 收发、序号会话与超时强制停车

> 致 Argon4：本任务实现 STM32 侧 HC-12 通信（USART1）、半双工主从会话、序号/丢帧追踪，**以及统一的强制停车 `Chassis_ForceStop()`（安全核心）**。
> 派单人：WorkBuddy ｜ 时间：2026-11-21 21:07 ｜ 依据：Codex 阶段 3 规划定稿 + V2 审单闭环
> 前置：S3-01 协议层 ✅（`comm_protocol.h/c`）；**W0 架构变更（CubeMX）必须先完成**

---

## 0. ⚠️ 开工前置：USART1 架构变更（你指导人类操作，不自己改 .ioc）

**本单第一步是文字教学**，指导人类用户在 CubeMX 里启用 USART1：

```text
1. 打开 breathing\breathing.ioc
2. 启用 USART1：PA9 = USART1_TX、PA10 = USART1_RX
3. 参数：9600 bps、8N1（Word Length 8 / Parity None / Stop 1）、无流控
4. 检查引脚冲突（PA9/PA10 空闲；M1zuoqian 是 PE9 不冲突）
5. Generate Code
6. ★ 重生成会重写 uvprojx，手动 Add 的 .c 会被冲掉 —— 逐个检查并重新 Add：
   pid.c / control.c / encoder.c / motor.c / oled.c / chassis.c / imu.c / comm_protocol.c
   （共 8 个 —— 比阶段 2 多一个 comm_protocol.c，S3-01 刚加的，勿漏！）
7. 编译验证 0 Error / 0 Warning 后再进入代码实现
```

**边界**：你只出教学步骤，**任何模型不得直接改 `.ioc`**；人类确认生成完成、8 个 .c 都在、编译通过，才继续。

## 1. 目录约定

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

## 2. 当前状态（核对 2026-11-21 21:00）

| 项 | 当前值 |
|---|---|
| 协议层 | `comm_protocol.h/c` 已就绪：`Comm_Crc8`/`BuildFrame`/`ParseFrame` + Pack/Unpack，CRC 向量 0x38/0x3D 已验 |
| USART | `.ioc` 当前**无任何 USART**（W0 后才有 USART1） |
| 位姿/控制 | `chassisX/Y/Yaw`、航向闭环、`Chassis_SetVelocity()` 全部就绪 |
| `Chassis_ForceStop()` | **尚不存在** —— 本单新建（见 W4） |
| 安全基线 | 上电 `TARGET=0`、mode 0、车不动；20:57 hex 0 Error / 0 Warning |
| HC-12 模块 | S3-01B 由人类配置（同频道/9600），与本单并行 |

## 3. 允许修改（仅限）

```text
Core/Inc/comm_session.h      ← 新建：会话层接口/状态（可选，也可并入 comm_uart.h）
Core/Src/comm_uart.c         ← 新建：USART1 中断收发 + 会话 + 超时（命名回传说明）
Core/Inc/comm_uart.h         ← 新建
Core/Src/chassis.c           ← 仅新增 Chassis_ForceStop() 实现
Core/Inc/chassis.h           ← 仅追加 Chassis_ForceStop() 声明
Core/Inc/stm32f4xx_it.h/.c   ← 仅 USART1 中断服务里挂接收发回调（CubeMX 生成后再加）
MDK-ARM/.../uvprojx          ← Keil Add 新 .c
```

## 4. 禁止修改（硬边界）

```text
breathing.ioc（W0 由用户改，你不得动）
tim.c / motor.c / gpio.c / main.c / main.h
control.h / control.c（PID/安全宏/1ms 调用点全不动）
encoder.h/.c / pid.h/.c / imu.h/.c / i2c.c / oled.c
comm_protocol.h/.c（S3-01 已验证，本单只读复用，不修改）
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：改 PID 参数；改轮径；把超时判断写成等待循环；只清 vx/omega 就当停车（见 W4 致命点）。

## 5. 具体工作项

### W1 — USART1 中断收发（必做）

- 用 HAL UART 中断方式：`HAL_UART_Receive_IT(&huart1, ...)` 收单字节进环形缓冲；发送用 `HAL_UART_Transmit_IT()` 或轮询短发（9600 下 33 字节约 27 ms，注意别阻塞 SysTick）。
- **不在 1 ms 中断（SysTick/Control_Update）里做 UART 收发的阻塞调用**。USART1 中断与 SysTick 是不同中断源，注意优先级：USART1 优先级不要高于 SysTick 太多以免饿死控制环（回传说明配置）。
- 收到完整一帧（凑齐 `AA 55 ... 0D 0A`，长度按 TYPE 定长）后调用 `Comm_ParseFrame()`，解析成功置「待处理命令」标志，由 `Control_Update()` 每周期取出执行 —— **解析在中断、执行在控制环**，避免在中断里改底盘状态。

### W2 — 半双工主从会话（必做）

```text
电脑 = 主机；STM32 = 从机；STM32 不主动发
周期 50 ms：收到主机一帧 → 处理 → 回一帧 TELEMETRY → 等下一帧
```

- 用 `huart1` 发送 TELEMETRY（20 Hz 由主机轮询驱动，STM32 不自触发）。
- 一帧处理完到回帧之间，确认链路空闲（半双工，不能同时收发）。
- 主机发的帧 SEQ，响应必须复制（S3-01 规则）。

### W3 — 序号/丢帧/重复帧会话层（必做）

- 维护 `lastSeq`：新帧 SEQ 若非 `lastSeq+1`（含 255→0 回绕）→ `drop_count += 缺失数`；重复 SEQ → 视为重发。
- 重复帧处理：`CMD_STOP` **仍执行**；其他命令**不重复改状态**，但照常回缓存 TELEMETRY。
- `drop_count`、`timeout_count` 经 TELEMETRY 回传（S3-01 的 26B 布局已留字段）。

### W4 — 【安全核心】统一强制停车 `Chassis_ForceStop()`（必做，别做错）

**致命点**：阶段 2 的航向闭环（`chassisHeadingMode=1/2`）每帧会用 `Chassis_ComputeHeadingOmega()` 把 omega **重新算出来覆盖**。若通信超时只清 `chassisTargetVx/Omega`，**车根本停不下来**。

在 `chassis.c` 新建统一函数，`Chassis_Init()` 里的清零段可抽出来复用：

```c
void Chassis_ForceStop(void)
{
    chassisTargetVx = 0.0f;
    chassisTargetOmega = 0.0f;
    chassisCmdRejected = 0U;
    chassisHeadingMode = 0U;        /* ★ 关键：退出航向环，否则 omega 被算回 */
    chassisHeadingReached = 1U;     /* ★ 防止 mode 2 再输出 omega */
    for (i...) Control_SetTargetRpm(i, 0.0f);  /* ★ 四路写 0 双保险 */
}
```

**优先级写死**：强制停车 > CMD_MODE > 一切航向模式指令。禁止只清 vx/omega 目标就认为停好了。

### W5 — 超时停车（必做）

```text
最后有效帧时间戳：USART1 接收中断里收到"有效帧"(CRC/长度通过)时更新（用 HAL_GetTick() 读值）
超时判断：在 Control_Update()（SysTick 内）里做 HAL_GetTick() - lastFrameTick > 200 → 调 Chassis_ForceStop()
⚠️ HAL_GetTick() 只做数值比较，禁止任何等待循环（S2-04 死锁教训）
```

- `timeout_count` 每次触发 +1（经 TELEMETRY 回传）。
- IMU 掉线保护（`chassis.c` 第 481 行 `imuAvailable==0` 停车）**不得改动**。

### W6 — 命令执行与 CMD_MODE 作用域（必做）

在 `Control_Update()` 里执行待处理命令：

```text
CMD_VEL  : 定点数还原 → Chassis_SetVelocity(vx_mps, omega_rads)
           vx_mps = vx_mmps/1000, omega_rads = omega_mradps/1000
CMD_STOP : Chassis_ForceStop()（重复也执行）
CMD_MODE : 只写 chassisYawFusionMode(0/1)
           ★ 绝对不碰 chassisHeadingMode（0/1/2 航向模式）—— 本阶段不开放遥控航向
CMD_POLL : 仅触发 TELEMETRY 回帧
```

**命令与超时的优先级**：若同一周期既收到 CMD_STOP 又超时 → 都调 ForceStop（幂等，无妨）。

## 6. 安全要求

```text
上电默认停车（TARGET=0、mode 0）
200 ms 超时 → Chassis_ForceStop()，HAL_GetTick 只比较不等待
CMD_STOP 重复也执行、优先级最高
强制停车必须置 chassisHeadingMode=0 + reached=1 + 四路 RPM 写0
CMD_MODE 只改 chassisYawFusionMode，不碰 chassisHeadingMode
IMU 掉线保护不动；PID 参数/安全宏/轮径不动
1 ms 控制环内无 UART 阻塞等待
```

## 7. 验收标准

1. **W0 完成**：人类确认 CubeMX 已启用 USART1（PA9/PA10，9600 8N1）、生成后**8 个 .c 全在**（含 comm_protocol.c）、编译 0 Error。
2. Keil Build **0 Error / 0 Warning**，生成新 hex。
3. 上电安全：车不动，OLED `0000.0 RPM  000%`。
4. **静态核对**：`Chassis_ForceStop()` 五件事齐全且被超时/CMD_STOP 共用；超时用 HAL_GetTick 数值比较无等待；CMD_MODE 只写 yawFusionMode；IMU 掉线保护未动；解析在中断、执行在控制环。
5. **实车（需 S3-01B 的 HC-12 配好）**：电脑发 CMD_VEL 车动、发 CMD_STOP 立即停；断开电脑/HC-12 超过 200 ms 自动停车（`timeout_count` 增加）；重复 CMD_STOP 仍停；20 Hz 遥测回传字段正确。
   > 若 HC-12 未到/未配，至少完成 1~4 静态核对 + 上电不跑，运行时留 S3-TEST。
6. 未触碰禁止文件；`comm_protocol.c` 未改；PID 参数未改。

## 8. 回传要求

```text
1. W0 教学是否完成 + 8 个 .c 逐项核对结果
2. 修改文件清单（含新 .c 与 Keil Add）
3. Keil 编译结果（Error/Warning 数、hex 时间）
4. USART1 中断方案（收/发、优先级）与解析/执行分工
5. ★ Chassis_ForceStop() 代码 + 超时判断代码（证明不卡 SysTick）
6. 序号/丢帧/重复帧处理实现
7. 实车通信测试结果（CMD_VEL/STOP/超时/drop_count）或注明留 S3-TEST
8. 遗留问题与风险
9. 是否建议进入 S3-03（Python 工具）
```

---

**下一位提示**：本单是阶段 3 的安全核心 —— **强制停车务必按 W4 做全五件事**，否则航向环会把它吃掉。S3-03 才做 Python + pyserial 电脑端工具；S3-04/05 补测。若发现协议字段不够，**先回报 WorkBuddy，不要自行改 `comm_protocol.c`**。
