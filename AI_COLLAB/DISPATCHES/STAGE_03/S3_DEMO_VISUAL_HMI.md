# 派单 S3-DEMO v2 — 动作指令 API + 交互式可视化上位机

> 致 Argon4（反重力）：本任务做**参数化动作指令（STM32 端）+ 交互式可视化上位机（Python 端）**，作为阶段 3 收尾的展示内容。**用 Argon 全包**（安全关键逻辑 + 项目上下文连续性）。
> 派单人：WorkBuddy ｜ 初版 17:48 ｜ **修订 2026-11-22 17:55（v2：用户拍板加 STM32 动作指令，回起点第一版不做）**
> 前置：阶段 1/2/3 全部完成；`TOOL/protocol.py`、`comm_tool.py` 可复用

> **v2 相对 v1 的关键变化**：v1 是「上位机闭环、STM32 零改动」；v2 改为 **STM32 加参数化动作指令 API**（动作在车上闭环，精度高、链路空闲）+ 上位机做 GUI/工具化。用户明确可以在 32 端加东西，只要**不影响后面工程文件**。

---

## 0. 定位与边界

```text
展示层 + 多功能工具：
  ✅ 参数化动作指令：上位机发「前进 1300mm」「左转 90°」，像调 API，参数自由改
  ✅ 动作在 STM32 端闭环执行（复用已有 mode1 直行 / mode2 定点转向），不依赖通信频率
  ✅ 上位机：科技感 GUI + 实时曲线 + 原始帧/遥测工具（替代串口助手）
  ✅ 独立可演进：新代码放独立文件，已有协议 TYPE 01~04/10 与所有控制逻辑不动
  ❌ 回起点动作（action 0x05）第一版不做（skid-steer 开环回环精度不稳，S3-04 的 3cm 是理想条件）
```

## 1. STM32 侧 — 参数化动作指令（安全关键，Argon 做）

### 1.1 协议扩展（新增，不动已有）

在 `comm_protocol.h/.c` **追加**：

```c
#define COMM_TYPE_CMD_ACTION   0x05U   /* 新增 TYPE */
#define COMM_LEN_CMD_ACTION    3U      /* action_id(1B) + param(2B) */

/* 参数化动作：param 单位由 action_id 决定，见下 */
```

```text
帧：AA 55 05 SEQ [action_id][param_lo][param_hi] CRC8 0D 0A   （共 10B）
已有 TYPE 01 POLL / 02 VEL / 03 STOP / 04 MODE / 10 TELEMETRY 一律不动
CRC8 覆盖规则不变（TYPE+SEQ+DATA）；parameter 为 int16 小端（负值=反向）
```

**这就是"活的 API"**：上位机填 1300 就是 1300 mm，填 2500 就是 2500 mm，**固件不写死任何距离/角度**。

### 1.2 动作清单（第一版）

| action_id | 动作 | param | 实现（复用已有能力） |
|---:|---|---|---|
| `0x01` | 前进/后退指定距离 | mm，int16（负=后退） | 锁存起点 `chassisX`，`Chassis_EnableHeadingHold(1)` 保持航向，`Chassis_SetVelocity(0.25,0)`，每帧检查 `|chassisX−start| ≥ |param|` → `Chassis_ForceStop()` |
| `0x02` | 左转/右转指定角度 | 0.1°，int16（正=CCW 左转，负=右转） | `Chassis_SetHeadingTarget(wrap(current_yaw + param*0.1°))` → 已有 mode2 到位自动停（`chassisHeadingReached`） |
| `0x03` | 立即停车 | 忽略 | `Chassis_ForceStop()` |
| `0x04` | 原地掉头 180° | 忽略 | 等价于 0x02 param=1800 |
| `0x05` 回起点 | **第一版不做**（派单里注释说明留后续） |

### 1.3 动作状态机（新文件 `comm_actions.h/c`）

```c
extern uint8_t  commActionActive;      /* 1=动作执行中 */
extern uint8_t  commActionId;          /* 当前动作 */
extern int16_t  commActionTarget;      /* 目标参数 */
extern float    commActionStart;       /* 起始 x 或 yaw */
extern uint32_t commActionElapsedMs;   /* 执行计时 */
void Comm_Action_Start(uint8_t id, int16_t param);
void Comm_Action_Update1ms(void);      /* 每 1 ms 在控制环检查到位/超时 */
void Comm_Action_Abort(void);          /* 清动作状态（ForceStop 时调用） */
```

**到位/超时**：

```text
前进：|chassisX − start| ≥ |target| mm/1000 → ForceStop + 清 active
旋转：chassisHeadingReached==1（mode2 已到位）→ 清 active（Spin 由 S2-06B 的判据保证 ±0.7°）
动作超时：统一 10 s（宏 COMM_ACTION_TIMEOUT_MS）→ ForceStop + 清 active + 回报超时
动作中收到 CMD_STOP 或通信超时 400ms → ForceStop 必须同时清 action 状态（防动作"复活"）
```

**★ 单一司机规则（必做，防状态竞争）**：

动作执行复用全局状态（`chassisHeadingMode` / `chassisTargetVx/Omega` / `chassisHeadingReached`），**不能和新指令抢方向盘**。硬性要求：

```text
任何新的运动类指令到达时，先 Comm_Action_Abort() 清当前动作，再执行新指令：
  CMD_STOP    → Abort + ForceStop（已有）
  CMD_VEL     → Abort + 正常设速度        ★ 补这条（原来只写了 STOP）
  CMD_MODE    → Abort + 切 fusion 模式    ★ 补这条
  CMD_ACTION  → Abort + 启新动作          ★ 补这条（动作切动作）
  CMD_POLL    → 不动动作（纯查询，允许动作中继续回遥测）
 通信超时 400ms → Abort + ForceStop（已有）
```

实现建议：在 `Comm_ExecuteCommand()` 入口按 `rx->type` 统一做 Abort（POLL 除外），一处收敛、别散在各个 case 里。这样任何时刻**只有一个"司机"**，手动遥控与自动动作不会互相覆盖。

### 1.4 允许/禁止修改（STM32）

```text
允许：comm_protocol.h/.c（仅追加 TYPE 0x05 与宏）、comm_session.h/.c（仅加一个 case 调 Comm_Action_Start）、
      新建 comm_actions.h/c、chassis.c（仅两处小改：① ForceStop 内加 Comm_Action_Abort() 一行；
      ② Chassis_Update 内加 Comm_Action_Update1ms() 一行）、uvprojx（Add 新 .c）
禁止：PID 参数、运动学公式、里程计算法、航向闭环逻辑、超时 400ms 宏、
      TYPE 01~04/10 语义、已有 CRC8/序号规则、main.c/.h、tim/motor/gpio/i2c/oled、.ioc
```

**安全**：已有能力零回归；CMD_STOP 最高优先级且能打断动作；通信超时仍能停车并清动作；上电默认无动作。

## 2. 上位机侧 — 科技感 GUI + 多功能工具（Python）

### 2.1 位置与复用

```text
新建：TOOL\hmi\ 下全部文件（main.py / hmi_widget.py / link.py / actions.py / plots.py /
      raw_tool.py / requirements.txt / README.md）
只读复用：TOOL/protocol.py —— 本单需给它追加 TYPE_CMD_ACTION 与 pack_cmd_action()，
      ★ 但 protocol.py 是"只读复用"边界 —— 改为：hmi\protocol_ext.py 里定义 ACTION TYPE 与打包函数，
      用 protocol.build_frame() 组帧（不修改 protocol.py 本身）
禁止改：protocol.py、comm_tool.py、TOOL/README.md、breathing\ 下除 §1.4 允许的文件外的一切、AI_COLLAB\、docs\
```

### 2.2 技术栈

```text
Python 3 + PyQt6（或 PySide6）+ pyqtgraph + pyserial
requirements.txt：pyqt6 pyqtgraph pyserial
```

### 2.3 界面分区（暗色科技风：深蓝/黑底 + 青/橙高亮）

```text
┌──────────────────────────────────────────────────────────────┐
│ 顶栏：标题 + 连接状态(COM口/CH002/9600) + 红色急停按钮        │
├───────────────┬──────────────────────────────────────────────┤
│ 动作按钮区    │ 实时数据区                                    │
│ [前进 __ mm]  │ 四轮 RPM 数字/仪表 | 四路 PWM 条               │
│ [后退 __ mm]  │ X/Y 位置 | OdomYaw / ImuYaw                    │
│ [左转 __ °]   │ 状态位(IMU/超时/heading/拒绝/动作中)           │
│ [右转 __ °]   │ drop/timeout | 本地丢帧率/RTT                  │
│ [掉头180°]    ├──────────────────────────────────────────────┤
│ [停车]        │ 实时曲线：X-Y 轨迹 / yaw 双曲线 / 四轮 RPM 曲线│
│ 手动 vx/ω     ├──────────────────────────────────────────────┤
│ [发送]        │ 日志：指令/回帧/动作进度/完成/超时/急停        │
├───────────────┴──────────────────────────────────────────────┤
│ 标签页：[遥测面板] [原始帧工具] [动作说明]                     │
└──────────────────────────────────────────────────────────────┘
```

**「原始帧工具」标签页（替代串口助手，用户明确要的多功能）**：

```text
- 手动填 TYPE / SEQ / DATA（十六进制）→ 发帧 → 显示原始回包 hex + 解析结果
- 常用帧快捷按钮：CMD_POLL / CMD_MODE 0 / CMD_MODE 1 / CMD_STOP
- 显示最近 N 帧收发历史（时间、方向、hex、CRC 结果）
- 可切换「ASCII 显示」方便看文本
```

### 2.4 最小功能（必须）

```text
1. 串口连接/断开（默认 COM6，可选端口）；顶栏显示 CH002/9600 状态
2. 参数化动作按钮：前进/后退(mm 可填)、左转/右转(° 可填)、掉头180°、停车
3. 手动 vx/ω 发送（保留直接遥控）
4. 急停按钮（始终可点，发 CMD_STOP）
5. 实时遥测全字段显示 + 三类曲线（轨迹/yaw 双曲线/RPM）
6. 动作进度与结果日志（"前进中 620/1300mm"、完成/超时/被急停）
7. 原始帧工具标签页（替代串口助手）
8. 动作中若链路异常/超时 → 显著告警
```

**进阶（有余力）**：主题切换、CSV 导出、截图、动作队列、参数记忆。

### 2.5 架构

```text
TOOL\hmi\
  ├── main.py            入口 + 窗口
  ├── hmi_widget.py      布局 + QSS 科技感样式
  ├── link.py            串口 QThread：复用 protocol.py 组帧/解析 + 序号/统计
  ├── protocol_ext.py    ACTION TYPE 常量 + pack_cmd_action()（不改 protocol.py）
  ├── actions.py         动作按钮 → CMD_ACTION 打包/发送/进度解析
  ├── plots.py           pyqtgraph 曲线与轨迹
  ├── raw_tool.py        原始帧工具标签页
  ├── requirements.txt
  └── README.md          运行/依赖/按钮/安全
```

**线程**：串口收发在 QThread，GUI 主线程只更新显示；禁止 GUI 线程阻塞读串口。

## 3. 安全要求（重点）

```text
CMD_STOP 最高优先级，能打断任何动作（STM32 ForceStop + 清 action 状态）
★ 单一司机：CMD_VEL / CMD_MODE / CMD_ACTION / CMD_STOP 到达时先 Abort 清动作再执行（POLL 除外）
通信超时 400ms 仍停车且清动作状态（不能"动作复活"）
动作自身 10s 超时 → 停车 + 告警
上电/启动默认无动作、不发速度
回起点 action 0x05 第一版不做（代码里注释说明）
PID/安全宏/轮径/已有协议语义不动；.ioc 不动
实测人在场、架空或空旷、高速前方 ≥0.5m
```

## 4. 验收标准

**STM32 侧**：

1. Keil 0 Error / 0 Warning，新 hex；上电车不动、OLED `0000.0 RPM  000%`。
2. 静态核对：TYPE 0x05 仅追加、已有 TYPE 不动；ForceStop 加了 Abort 一行、Chassis_Update 加了 Update 一行，**其他逻辑原样**；PID/超时宏/CubeMX 未动。
3. 实车：`CMD_ACTION(0x01, 1300)` 走约 1.3m 自动停；`(0x02, 900)` 左转约 90° 自动停；`(0x02, -900)` 右转；`(0x04)` 掉头；`(0x03)` 停车。
4. 动作中发 `CMD_STOP` 立即打断且动作状态清零；**动作中发 `CMD_VEL` / `CMD_MODE` / 新 `CMD_ACTION` 也能先 Abort 再执行（手动遥控与自动动作不抢方向盘）**；通信断开 >400ms 动作中止不复活；动作 >10s 超时停车。
5. 回归：已有 CMD_POLL/VEL/MODE/TELEMETRY 功能不变。

**上位机侧**：

6. `pip install -r requirements.txt` 后 `python main.py` 独立运行；暗色科技风、分区齐全。
7. 连 COM6/CH002，收 33B 遥测全字段显示；三类曲线实时更新。
8. 参数化动作按钮可用（填距离/角度发出去、进度显示、到位/超时日志）。
9. 急停按钮即时有效；原始帧工具能手动发帧并显示 hex 回包。
10. `protocol.py`、`comm_tool.py` 时间戳未变（只读复用证据）。

> 无车/无 HC-12 时可用 mock 数据验证 GUI 与动作打包逻辑，实车部分留现场演示。

## 5. 回传要求

```text
1. 修改/新建文件清单（STM32 侧 + TOOL\hmi\ 侧分开列）
2. Keil 编译结果（Error/Warning、hex 时间）
3. 动作指令协议说明（TYPE 0x05 DATA 布局、action_id 表、参数单位）
4. 动作状态机代码骨架（到位/超时/Abort 与 ForceStop/400ms 的联动）
5. 上位机界面截图或布局说明 + 原始帧工具使用方法
6. 实车动作测试（距离/角度误差、急停打断、超时）或 mock 说明
7. 回归核对：已有 TYPE 与 PID/安全逻辑未动、protocol.py 未改
8. 遗留问题与后续可改进点（回起点等）
9. 是否可作为阶段 3 展示内容交付
```

---

**下一位提示**：v2 的核心是**参数化动作 API**——固件不写死距离/角度，上位机像调 API 一样自由传参。**回起点第一版不做**。安全红线是"CMD_STOP 与 400ms 超时都能打断动作并清状态"。做完这单，阶段 3 连展示层一起彻底收官。
