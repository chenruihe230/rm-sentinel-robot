# 派单 S3-01 — HC-12 通信协议与接口定义

> 致 Argon4：本任务**只定义协议与接口**（头文件、常量、数据结构、解析/组帧函数骨架），**不实现 USART 驱动、不改 `.ioc`、不接硬件**。S3-02 才做 UART 收发与超时停车。
> 派单人：WorkBuddy ｜ 时间：2026-11-21 20:46 ｜ 依据：Codex 阶段 3 规划定稿（V1+V2 审单全闭环）
> 前置：阶段 2 ✅ 收官；USART1 硬件变更属 S3-02 前置，**本单不涉及**

---

## 1. 目录约定

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档：D:\stm32\stm32f4\breath\AI_COLLAB
```

下文 `Core/...` 以 Keil 工程目录为基准。

## 2. 任务目标

建立 HC-12 通信的协议层骨架，供 S3-02（STM32 收发）和 S3-03（Python 工具）共同遵循。**本单只写协议定义与纯软件函数（CRC8、组帧、解析），不碰串口外设、不动 CubeMX。**

## 3. 允许修改（仅限）

```text
Core/Inc/comm_protocol.h    ← 新建：帧格式、TYPE 常量、数据结构、接口声明
Core/Src/comm_protocol.c    ← 新建：CRC8、组帧、解析（纯软件，无 HAL 串口调用）
MDK-ARM/.../uvprojx         ← Keil 里 Add comm_protocol.c
```

## 4. 禁止修改（硬边界）

```text
breathing.ioc / tim.c / motor.c / gpio.c / main.c / main.h
control.h / control.c / encoder.h/.c / pid.h/.c / imu.h/.c / i2c.c / oled.c
chassis.h / chassis.c        ← 本单不碰（ForceStop 等是 S3-02 的事）
usart.c / uart 相关          ← 本单不碰串口
docs/*、AI_COLLAB/* 下所有文档
```

**绝对禁止**：本单调用任何 HAL USART API；改 `.ioc`；改 PID/安全宏；把协议参数写死在函数里而不做成 `comm_protocol.h` 的宏/常量。

## 5. 协议定义（Codex 规划定稿，逐条写死）

### 5.1 链路模型

```text
HC-12 半双工：空中任意时刻只允许一端发送
电脑 = 主机，STM32 = 从机
STM32 不主动发送，只在收到一帧后回一帧
通信周期 50 ms（遥测 20 Hz）：PC 请求 → STM32 响应 → 下一周期
```

### 5.2 帧格式（定长，按 TYPE 定长 DATA）

```text
Byte 0    0xAA    帧头1
Byte 1    0x55    帧头2
Byte 2    TYPE    消息类型
Byte 3    SEQ     uint8 序号
Byte 4..N DATA    按 TYPE 定长（见下表）
Byte N+1  CRC8    覆盖 TYPE+SEQ+DATA
Byte N+2  0x0D    帧尾1
Byte N+3  0x0A    帧尾2
```

**多字节字段一律小端。禁止浮点字符串。**

### 5.3 TYPE 与 DATA 长度表（写死）

| TYPE | 消息 | DATA 长度 | DATA 内容 |
|---:|---|---:|---|
| `0x01` | `CMD_POLL` | 0 B | 无 |
| `0x02` | `CMD_VEL` | 4 B | `vx int16`(mm/s)、`omega int16`(mrad/s) |
| `0x03` | `CMD_STOP` | 0 B | 无 |
| `0x04` | `CMD_MODE` | 1 B | `chassisYawFusionMode uint8`（0=纯编码器, 1=IMU 融合） |
| `0x10` | `TELEMETRY` | 26 B | 见下 |

**TELEMETRY 26 B 明细**：

```text
rpm[4]          8 B   int16  ×4
pwm[4]          4 B   int8   ×4
x               2 B   int16  mm
y               2 B   int16  mm
odom_yaw        2 B   int16  0.01°
imu_yaw         2 B   int16  0.01°
status          1 B   uint8
fusion_mode     1 B   uint8
drop_count      2 B   uint16
timeout_count   2 B   uint16
─────────────────────────
合计           26 B
```

### 5.4 CRC8（写死，已验算）

```text
覆盖范围：TYPE + SEQ + DATA（不含帧头/帧尾/CRC 自身）
多项式：0x07
初值：0x00
不反转
XOROUT：0x00
```

**已知校验向量（WorkBuddy 已用脚本验算通过，实现必须能复现）**：

```text
向量1：TYPE=0x03, SEQ=0x01, DATA=空
  输入 03 01 → CRC8 = 0x38
  完整帧：AA 55 03 01 38 0D 0A

向量2：TYPE=0x02, SEQ=0x01, vx=100mm/s(64 00), omega=0(00 00)
  输入 02 01 64 00 00 00 → CRC8 = 0x3D
```

### 5.5 序号规则

```text
序号 uint8，255 后回绕到 0（正常）
主机每发一帧递增一次
STM32 响应必须复制请求序号
序号跳变（非 +1 且非 255→0）计入 drop_count
重复序号 = 重发：
  CMD_STOP → 仍执行
  其他命令 → 不重复执行状态改变，返回缓存遥测
```

### 5.6 命令语义（协议层只定义，执行在 S3-02）

```text
CMD_VEL   : 设 vx/omega（定点数还原为 m/s、rad/s 后交 Chassis_SetVelocity）
CMD_STOP  : 强制停车（S3-02 调 Chassis_ForceStop()）—— 最高优先级
CMD_MODE  : 只改 chassisYawFusionMode(0/1)，禁止改 chassisHeadingMode
CMD_POLL  : 请求遥测
TELEMETRY : STM32 回传，20 Hz 由主机轮询驱动
```

**CMD_STOP 优先级最高的协议层体现**：即使序号重复也执行；且在 S3-02 中强制停车优先级 > CMD_MODE > 一切航向模式。

## 6. 具体工作项

### W1 — comm_protocol.h（必做）

定义并注释：

```c
/* 帧常量 */
#define COMM_FRAME_HEAD1  0xAAU
#define COMM_FRAME_HEAD2  0x55U
#define COMM_FRAME_TAIL1  0x0DU
#define COMM_FRAME_TAIL2  0x0AU

/* TYPE */
#define COMM_TYPE_POLL      0x01U
#define COMM_TYPE_VEL       0x02U
#define COMM_TYPE_STOP      0x03U
#define COMM_TYPE_MODE      0x04U
#define COMM_TYPE_TELEMETRY 0x10U

/* DATA 长度 */
#define COMM_DATA_LEN_VEL       4U
#define COMM_DATA_LEN_MODE      1U
#define COMM_DATA_LEN_TELEMETRY 26U
/* POLL/STOP 为 0 */

/* 最大帧长 = 4(head+type+seq... 实为 head2+type+seq+data+crc+tail2) */
#define COMM_MAX_FRAME_LEN  (4U + COMM_DATA_LEN_TELEMETRY + 4U)  /* = 34，回传确认 */
```

定义数据结构：

```c
typedef struct {
    uint8_t  type;
    uint8_t  seq;
    uint8_t  data[COMM_DATA_LEN_TELEMETRY];  /* 最大 DATA 缓冲 */
    uint8_t  data_len;
} Comm_Frame_t;

typedef struct { int16_t vx_mmps, omega_mradps; } Comm_CmdVel_t;
typedef struct {
    int16_t rpm[4];      /* 0..250 或负 */
    int8_t  pwm[4];      /* -100..100 */
    int16_t x_mm, y_mm, odom_yaw_001deg, imu_yaw_001deg;
    uint8_t status, fusion_mode;
    uint16_t drop_count, timeout_count;
} Comm_Telemetry_t;
```

**定点换算约定写进注释**：`vx_mps = vx_mmps / 1000.0f`、`omega_rads = omega_mradps / 1000.0f`、`yaw_rad = yaw_001deg * 0.01f * PI/180`。

### W2 — CRC8 与组帧/解析（必做，纯软件）

在 `comm_protocol.c` 实现：

```c
uint8_t  Comm_Crc8(const uint8_t *buf, uint32_t len);        /* poly 0x07/init0/no reflect/xorout0 */
uint32_t Comm_BuildFrame(uint8_t *out, uint8_t type, uint8_t seq,
                         const uint8_t *data, uint32_t data_len);  /* 返回帧长 */
int8_t   Comm_ParseFrame(const uint8_t *buf, uint32_t len, Comm_Frame_t *frame);
                                                             /* 0=OK, -1=头错, -2=尾错, -3=CRC错, -4=长度错 */
```

- `Comm_ParseFrame()` 必须校验：帧头 0xAA55、帧尾 0x0D0A、CRC8、DATA 长度与该 TYPE 的定长一致。
- **不实现状态机、不缓冲多帧** —— 那是 S3-02 的事。本单只做单帧纯函数。
- 用 **查表法或位运算法**均可，但必须能复现 §5.4 两个向量；回传里贴出你对两个向量的实测输出。

### W3 — 编译自检（必做）

写一个**临时**自检（不留在工程里，或用 `#ifdef COMM_SELF_TEST` 包裹）：上电/PC 端调用 CRC8 对 `{0x03,0x01}` 和 `{0x02,0x01,0x64,0x00,0x00,0x00}` 求值，确认 `0x38` / `0x3D`。回传说明验证方式（可不烧录，PC 上用 C 编译或在线工具复现均可，但代码里的 CRC 实现必须与之同源）。

## 7. 安全要求

```text
本单不碰串口/硬件/CubeMX，不改 PID/安全宏
上电行为完全不变（车不动、OLED 原样）
协议参数全部做成 comm_protocol.h 宏/常量，不写死在函数里
CRC8 必须复现两个已知向量，否则不许进入 S3-02
CMD_MODE 作用域在注释和接口里明确：只 yaw fusion，不碰 heading mode
```

## 8. 验收标准

1. Keil Build **0 Error / 0 Warning**，生成新 hex（行为与阶段 2 基线一致：车不动、OLED `0000.0 RPM 000%`）。
2. 静态核对：帧格式/TYPE/DATA 长度/CRC8 参数/序号规则/定点换算注释齐全；无 HAL USART 调用；未碰禁止文件。
3. **CRC8 两向量复现**：`{03 01}→0x38`、`{02 01 64 00 00 00}→0x3D`（回传贴实测输出）。
4. `Comm_BuildFrame()` 组出的 `CMD_STOP` 帧与 §5.4 向量1 的字节序列一致：`AA 55 03 01 38 0D 0A`。
5. `Comm_ParseFrame()` 对头/尾/CRC/长度四类错误能返回不同错误码。
6. 新增 `comm_protocol.c` 已在 Keil 工程树中（若本单就 Add）。

> 本单偏接口定义，若不方便实车验证，按静态核对 + CRC 向量复现为准 —— 运行时通信测试在 S3-02/S3-03。

## 9. 回传要求

```text
1. 修改文件清单（含 Keil Add 情况）
2. Keil 编译结果（Error/Warning 数、hex 时间）
3. comm_protocol.h 宏/结构清单（TYPE、DATA 长度、换算约定）
4. ★ CRC8 两向量实测输出（0x38 / 0x3D）与 CMD_STOP 完整帧字节
5. Comm_ParseFrame 四类错误码定义
6. 遗留问题与风险
7. 是否建议进入 S3-01B（HC-12 配置）与 S3-02（USART1 架构变更 + 收发）
```

---

**下一位提示**：本单是纯协议层（软件函数），不碰串口、不碰 CubeMX。S3-01B 指导你配 HC-12（先配置后接线），S3-02 才做 USART1 架构变更 + 收发 + **统一强制停车 `Chassis_ForceStop()`**（清 vx/omega + 置 `chassisHeadingMode=0` + reached 置位 + 四路 RPM 写 0，优先级高于 CMD_MODE 和一切航向模式）。若协议字段需调整，**先回报 WorkBuddy，不要自行改**。
