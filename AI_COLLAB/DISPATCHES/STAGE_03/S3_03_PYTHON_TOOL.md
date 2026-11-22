# 派单 S3-03 — Python + pyserial 上位机工具

> 致 Argon4：本任务写**电脑端 Python 工具**，通过 HC-12 A（USB-TTL）与 STM32 通信：发指令、收遥测、显示状态。STM32 侧代码已完成（S3-02），**本单不碰任何 STM32 工程文件**。
> 派单人：WorkBuddy ｜ 时间：2026-11-22 15:44 ｜ 依据：Codex 阶段 3 规划定稿 §5 + S3-01/02 协议实现
> 前置：HC-12 已配 CH002（S3-01B ✅）、STM32 USART1 通信已就绪（S3-02 ✅）

---

## 1. 文件位置（本单独立目录）

```text
项目根：D:\stm32\stm32f4\breath
新目录：D:\stm32\stm32f4\breath\TOOL\
  ├── comm_tool.py        ← 主程序（可单文件）
  ├── protocol.py         ← 协议编解码（CRC8/帧/TYPE）—— 与 C 端 comm_protocol.c 逐位对齐
  └── README.md           ← 使用方法（中文）
```

**允许新建/修改**：仅 `breath\TOOL\` 下文件。
**禁止**：`breathing\` 下任何文件（源码/`.ioc`/hex/Keil 工程）、`AI_COLLAB\` 下任何文档、`docs\`。**不改 STM32 侧任何东西**。

## 2. 协议（必须与 S3-01 C 端逐位一致）

### 2.1 帧格式

```text
AA 55 | TYPE | SEQ | DATA(定长) | CRC8 | 0D 0A
```

### 2.2 CRC8（已验算，必须复现）

```text
覆盖 TYPE+SEQ+DATA（不含帧头/尾/CRC 自身）
poly=0x07, init=0x00, no reflect, xorout=0x00
向量1：{03 01}            → 0x38
向量2：{02 01 64 00 00 00} → 0x3D
STOP 完整帧：AA 55 03 01 38 0D 0A
```

### 2.3 TYPE 与 DATA

| TYPE | 消息 | DATA | 内容 |
|---:|---|---:|---|
| `0x01` | `CMD_POLL` | 0B | — |
| `0x02` | `CMD_VEL` | 4B | `vx int16`(mm/s)、`omega int16`(mrad/s)，**小端** |
| `0x03` | `CMD_STOP` | 0B | — |
| `0x04` | `CMD_MODE` | 1B | `fusion_mode uint8`：0=纯编码器，1=IMU 融合 |
| `0x10` | `TELEMETRY` | 26B | 见下 |

**TELEMETRY 26B 布局（小端）**：

```text
[0..7]   rpm[4]  int16×4
[8..11]  pwm[4]  int8×4
[12..13] x_mm    int16
[14..15] y_mm    int16
[16..17] odom_yaw_001deg  int16
[18..19] imu_yaw_001deg   int16
[20]     status  uint8   (bit0 IMU OK / bit1 超时 / bit2 heading模式 / bit3 指令拒绝)
[21]     fusion_mode uint8
[22..23] drop_count  uint16
[24..25] timeout_count uint16
```

### 2.4 主从时序（半双工，20 Hz）

```text
电脑每 50 ms 发一帧（CMD_POLL 或当前指令）
STM32 回一帧 TELEMETRY（SEQ 复制请求）
电脑收到回帧后才进入下一周期 —— 禁止不等回复连续猛发（半双工会撞）
序号：uint8 逐帧递增、255→0 回绕
```

## 3. 串口参数

```text
端口：默认 COM3 可用命令行参数指定（如 python comm_tool.py --port COM6）
波特率：9600
8N1，无流控
超时：读 100 ms（50ms 周期 + HC-12 往返 90~100ms，要留够；回传实测往返 ~90-100ms）
```

> 注意：HC-12 实测往返 ~90~100 ms，50 ms 周期下可能出现在途重叠。工具要能处理「上一帧未回就到下一个周期」—— 建议**等到回帧或读超时后再发下一帧**，实际频率可能略低于 20 Hz，以不撞车为先（符合半双工原则）。回传里说明实测频率。

## 4. 具体工作项

### W1 — protocol.py（协议层，必做）

- `crc8(data: bytes) -> int`：poly 0x07 位运算实现，**自检两个向量**（0x38/0x3D），不对就报错退出。
- `build_frame(type, seq, data=b'') -> bytes`：按定长检查 DATA 长度，组帧。
- `parse_frame(buf) -> (type, seq, data) | None`：校验头/尾/CRC/长度，失败返回 None（不抛异常崩掉主循环）。
- `pack_cmd_vel(vx_mps, omega_rads) -> bytes`：`int(round(vx*1000))`、`int(round(omega*1000))` 小端 int16。
- `pack_cmd_mode(fusion: int) -> bytes`、`unpack_telemetry(data) -> dict`：字段全解成可读单位（RPM 原值、PWM %、`x/y` m、yaw °）。
- 全部纯函数、可独立 import 测试。

### W2 — comm_tool.py（主循环，必做）

```text
启动：
  1. 自检 CRC 向量（不过就报错退出）
  2. 打开串口（9600 8N1），打印 "connected: COMx"
  3. 序号 seq=0

主循环（每周期）：
  1. 取当前要发的命令（默认 CMD_POLL；用户按键/命令改为 VEL/STOP/MODE）
  2. build_frame(type, seq, data) → 串口发送；seq=(seq+1)&0xFF
  3. 等待回帧（带超时，见 §3 注意）
  4. parse_frame 成功 → unpack_telemetry → 打印/刷新显示
  5. 统计：发帧数、收回数、超时数、本地丢帧率
```

**交互方式**（选一种实现，回传说明）：

- **方式 A（推荐，简单）**：命令行交互 —— 用户输入 `v 0.2 0` 发速度、`s` 停车、`m 1` 切 IMU 融合、`p` 轮询、`q` 退出；遥测刷新打印在终端；
- 方式 B：curses 实时面板（可选，非必需）。

**遥测显示至少包含**：

```text
四轮 RPM、四路 PWM(%)、x/y(m)、odom_yaw(°)、imu_yaw(°)
IMU 状态(OK/NO)、超时标志、heading 模式、指令拒绝
drop_count(STM32 回传)、timeout_count(STM32 回传)、本地超时次数/丢帧率
```

### W3 — README.md（必做，中文）

```text
1. 环境：Python 3.x + pyserial（pip install pyserial）
2. 接线：HC-12 A 插 USB-TTL 接电脑，端口查设备管理器（COMx）
3. HC-12 参数：CH002 / 9600 / FU3 / P8（两块一致，已配好）
4. 运行：python comm_tool.py --port COM6
5. 命令示例：v 0.2 0（前进 0.2m/s）、s（停车）、m 1（IMU 融合）、q（退出）
6. 安全提示：通信断开 STM32 200ms 自动停车；CMD_STOP 优先
```

## 5. 禁止事项

```text
禁止大型 GUI / 数据库 / ROS / 图像显示
禁止浮点字符串协议（必须二进制定点数）
禁止不等回帧连续猛发（半双工撞车）
禁止改 STM32 侧 comm_protocol.h/c（本单只在 Python 端复刻协议）
禁止在工具里绕过 200ms 停车逻辑（如发完 VEL 就退出不轮询 —— 会触发 STM32 停车，属预期，不算 bug）
```

## 6. 验收标准

1. `python -c "from protocol import crc8; assert crc8(bytes.fromhex('0301'))==0x38; assert crc8(bytes.fromhex('020164000000'))==0x3D"` 通过。
2. `build_frame(0x03, 1)` 输出 `AA 55 03 01 38 0D 0A`（与 C 端一致）。
3. 工具能连 HC-12 A（COM 口），打印连接成功。
4. 发 `CMD_POLL` 能收到 33B TELEMETRY，解出四轮 RPM/PWM/x/y/yaw/状态字段，数值合理（静止时 RPM≈0）。
5. 发 `CMD_VEL 0.2 0` 小车动（需人在场看车）、`s` 立即停；断开发送 >200ms 车自动停。
6. `drop_count`/`timeout_count` 正确显示（STM32 回传值）。
7. 未改 STM32 工程任何文件。

> 联调需人在场看车、注意安全（架空或空旷地面）。若 HC-12 不通，先按 S3-01B 排障表查（频道/供电/天线/SET）。

## 7. 回传要求

```text
1. 新增文件清单（TOOL\ 下）
2. CRC 向量自检与 STOP 帧实测输出
3. 串口参数与实测往返延迟/实际轮询频率
4. 交互方式说明（A/B）与命令示例
5. 联调结果：POLL/VEL/STOP/超时 四项现象（或注明待 S3-TEST）
6. 遗留问题与风险
7. 是否建议进入 S3-04/S3-05 补测与 S3-TEST
```

---

**下一位提示**：本单是纯电脑端工具，不碰 STM32 工程。联调时**人在场、架空或空旷地面**，先 `s` 确认停车再发速度。之后 S3-04（弧线/360°/回起点补测）、S3-05（单轮 1m/模式切换）、S3-TEST 统一验收。若协议对不上，**先回报 WorkBuddy，不要改 STM32 侧**。
