# 修改记录 (CHANGELOG)

项目：呼吸机 / 四轮电机控制（STM32F407VET6，Keil MDK-ARM，工程 breathing）

> 说明：以后每次改动都追加一条到这里（日期 + 改了什么 + 涉及文件 + 是否需要动 CubeMX）。
> 注意：从 CubeMX 重新生成代码会重写 `MDK-ARM/breathing.uvprojx`，手动加进工程的 .c 文件（pid.c、control.c 等）会被冲掉，需在 Keil 里重新 Add。

## 2026-11-22 20:15 [派单 S3-DEMO v3 — 精度与娱乐性增强 收官]

### 阶段 3 展示层彻底完成（v3 增量，三处纠正全落地）

- **改动范围（WorkBuddy 核对）**：车端仅 `comm_actions.h/c`（19:54），上位机仅 `TOOL\hmi\` 内文件。禁止文件时间戳**全部未变**：`comm_protocol.h/c`（18:09）、`comm_session.h/c`（16:47/18:10）、`chassis.h/c`（15:36/18:10）、`protocol.py`（15:50）、`comm_tool.py`（16:47）、`main.c`（17:34）、`.ioc`（11-21 22:04）。
- **三处纠正核对通过**：
  1. **编号**：`COMM_ACTION_RESET_ODOM=0x06`（在 TYPE 0x05 DATA 内）；`COMM_ACTION_HOME_RSVD=0x05` 保持预留；**无新增 TYPE**（仍 01~05,10）。
  2. **演示级标注**：界面与 `actions.py` 明确"演示级导航（预期落点误差 ~5cm 量级）"。
  3. **两层打断**：上位机 `_abort_script_queue()` + `tracker.abort()`（WASD/按钮/急停/断开均触发），车端靠已有单一司机 Abort。
- **W1 梯形减速**：`Comm_Action_ComputeMoveSpeedMps()`（起步 0.08→0.25 m/s/250ms、末端 150mm 降到 0.07 m/s 蠕行）；短距离 <400mm 处理（峰值 0.14、爬升 100ms、减速区 `min(150mm,0.5×target)`、三角形包络）。**⚠️ 回传的停止误差 +0.1mm(1000mm) / +0.6mm(200mm) 均为 `MockStm32Simulator` 仿真数据，非实车** —— 记录标「仿真通过、实车待验证」，不写成精度达标。
- **W2 归零**：0x06 帧 `AA 55 05 01 06 00 00 86 0D 0A`，Abort→ForceStop→ResetOdometry→DONE；仿真下一帧 X/Y=0、Yaw=0（实车待验证）。
- **W3/W4/W5**：WASD 八向（W/S/A/D + 组合弧线）+ 三档（0.15/0.30/0.60）+ 松手停 + 空格急停 + QTimer(50ms)；轨迹图金色车头射线 + 双击解算「转 Δyaw → 直行 L」串行（实测双击 (1,1)m 解出 +45°/1414mm）；三预设剧本（正方形 8 步 / 折返 4 步 / 摇摆 4 步）+ DONE 后 0.3s 下发；GUI 无头自检/截图通过。
- **编译**：11-22 **20:04:37** hex 67797 bytes（Code=21296 / RO=2664 / RW=516 / ZI=3756），0 Error / 0 Warning。
- **遗留**：**实车物理验证待做**（梯形停止误差、0x06 归零、WASD/双击/剧本实车演练）—— 烧 20:04 hex 跑一轮即可收齐；仿真数据不作为实车结论。
- **结论**：**阶段 3 展示层（S3-DEMO v1→v2→v3）全部交付完成**；阶段 3 主体验收记录 `ACCEPTANCE/STAGE_03.md` 已于 17:40 通过，本展示层为其收尾补充。
- CubeMX：否。

## 2026-11-22 19:46 [派单 S3-DEMO v2 收口 + v3 增强派单]

### v2 交付核对通过（参数化动作 API + 可视化上位机）

- **核对**：`comm_protocol.h/c` 仅追加 TYPE 0x05（`LEN=3B`），已有 TYPE 01/02/03/04/10 与 CRC8 向量（0x38/0x3D）未动；新建 `comm_actions.h/c`（5 动作 + 10s 超时 + status bit4..6 回传 RUNNING/DONE/TIMEOUT）；**单一司机规则在 `Comm_ExecuteCommand()` 入口统一收敛**（第 100-104 行，POLL 除外）；`chassis.c` 仅两行（ForceStop 加 Abort 318 行、1ms 环加 Update 446 行）。`protocol.py`/`comm_tool.py`/`.ioc`/control/encoder/imu 时间戳未变。HMI 九文件（PySide6 + pyqtgraph + 原始帧工具 + QThread + Mock 自检）。
- **编译**：11-22 **18:11:59** hex 66635 bytes（Code=20892），0 Error / 0 Warning。
- **状态**：v2 交付合格，作为阶段 3 展示层已成型。

### v3 增强派单（用户要更高停止精度 + 操控娱乐性）

- 产出 `AI_COLLAB/DISPATCHES/STAGE_03/S3_DEMO_V3_ENHANCE.md`。WorkBuddy 评估反重力提案后**三处纠正**：
  1. **编号冲突**：提案的「启用 0x05 做里程计归零」错误 —— TYPE 0x05 已占用、action 0x05 是回起点预留；归零必须用 **action 0x06**（不加新 TYPE）。
  2. **点地图精度打折**：串联误差累积，定位演示级（~5cm 量级），不承诺精准到达。
  3. **剧本打断两层做**：上位机清队列 + 车端 Abort，缺一不可。
- 保留的好想法：梯形减速（起步 250ms 爬升 + 末端 150mm 降到 0.07m/s 蠕行）、里程计归零、WASD 八向 + 三档变速、车头图标 + 双击地图串行导航、三种预设剧本。
- 硬边界：不动 TYPE/PID/里程计/400ms/已有动作语义；仅 `comm_actions.*` + `TOOL\hmi\`。用 **Argon**。
- CubeMX：否。

## 2026-11-22 17:36 [派单 S3-04/05 — 阶段 2 遗留五项补测 收口]

### 五项补测全部闭环（零生产代码改动）

- **改动范围**：**零生产代码改动**（`chassis.c` 15:36、`comm_session` 16:47、`comm_protocol` 20:57 等全部原样；`main.c` 临时测试后还原，7049→7095 bytes 与 S3-03 后基线一致、无 `MODE/ODOM ERR` 等测试残留）。`chassis.c:442` 过时注释按可选约定未动（纯注释，见 §7 第 30 条）。
- **编译**：11-22 Keil Build **0 Error / 0 Warning**（Code=19780 / RO=2664 / RW=476 / ZI=3756）；hex 文件系统时间 **17:36:07**（回传写 17:34:26，同类小偏差按文件系统记），63501 bytes，上电静止。
- **T1 弧线（v0.2/ω0.8，HC-12 无线）**：内侧 M1=20/M3=14 RPM、外侧 M2=97/M4=99 RPM；**WorkBuddy 验算理论 14.9/100.1 与实测一致**（内侧偏差因打滑）；轨迹左弧 X=+0.114/Y=+0.338/Yaw=+114.80°。**顺带坐实 S3-03B**：6.5~7.1 Hz / RTT 122ms 连续轮询 TX112→191 全程 drop=0/timeout=0，**400ms 超时无误停车**。
- **T3 原地 360°（分模式）**：**IMU 融合模式**物理转一圈读 `+360.18°`，偏差仅 **+0.18°**（硬指标 ≤10°、目标 ≤5°，实测 ≤1°，大胜）；**纯编码器模式**读 +367.03°（相对 IMU 偏 +6.85°），**只记录不设硬线**（得益于 0.3703 m 标定，精度已大幅提升）。
- **T4 回起点（全自动 1m×1m 正方形：mode1 直行 4s ×4 + mode2 定点转 90°）**：卷尺实测回起点右偏仅 **3 cm**；OLED `X=+0.003 / Y=-0.013 / YAW=-0.3° / ODOM ERR=0.013 m`。**达到 ≤5 cm 争取线**（亦远优于 ≤10 cm 通过线）。
- **T2 单轮 1m（0.25m/s 直行 4s，实走 1.040m）**：M1=1.0191m（**2.01%**）、M2=1.0272（1.23%）、M3=1.0191（**2.01%**）、M4=1.0262（1.33%）、整车 chassisX=1.024m（**1.54%**）。**WorkBuddy 独立验算与回传一致**。**如实标注：M1/M3 严格说 2.01% > 硬指标 2%，属压线**（实现方解释为卷尺 cm 级估读 + wheelScale=1.015 四舍五入边界，合理）；整车 1.54% 通过。
- **T5 模式切换（m1→m0→m1）**：切换无跳变、两模式 yaw 连续平滑、切回 fusion=1 稳定、timeout=0。
- **遗留**：T2 M1/M3 压线 2.01%（非功能缺陷）；`chassis.c:442` 过时注释（纯注释）。
- **下一步**：**S3-TEST 阶段 3 统一验收收官**。
- CubeMX：否。

## 2026-11-22 16:50 [派单 S3-03B — 无线超时 200→400 ms 收口]

### 安全阈值调整完成（Argon 执行）

- **核对通过**：`comm_session.h:27` 宏 `200U→400U`、第 9/20/22 行注释同步；`comm_session.c:213` 注释同步，**判断逻辑（226 行引用宏 + 228-236 flag/count + HAL_GetTick 原子快照/无等待循环）原样未动**；`comm_tool.py` 第 33/213/217 行（`0.5→0.8s`、提示文字 400ms）、`README.md:48/53` 同步；`--timeout-ms` 默认 260 保持。
- **残留搜索**：四个目标文件无旧阈值残留（仅 `comm_session.c:36` 的 `val+0.5f` 四舍五入表达式，无关）。
- **编译**：11-22 Keil Build **0 Error / 0 Warning**（Code=19780 / RO=2664 / RW=476 / ZI=3756）；hex 文件系统时间 **16:50:07**（回传写 16:47:42，同类小偏差按文件系统记），63501 bytes，上电静止。
- **CRC 自检复核**：`protocol.py` 两向量 0x38/0x3D + STOP 帧全过。
- **⚠️ 已知文档瑕疵（不阻塞）**：`chassis.c:442` 注释仍写「半双工主从应答 + **200 ms** 超时 Chassis_ForceStop」—— 这是描述通信超时、非航向稳定窗口，阈值改 400 后该注释过时。因 `chassis.c` 在本单禁止清单内未动。**下个涉及 chassis.c 的派单带上这处注释修正**。
- **遗留**：无线 30 s 连续心跳无误停车 / 故意断连 >0.8s 停车 / CMD_STOP 即时性 —— 待人类烧录 16:50 版 hex 实测，或并入 S3-04/05、S3-TEST。
- **下一步**：S3-04/05 补测 → S3-TEST 阶段 3 收官（高速测试预留 ≥0.5 m）。
- CubeMX：否。

## 2026-11-22 16:33 [派单 S3-03 — Python 上位机 收口（含 ⚠️ 超时线告警）]

### 阶段 3 电脑端工具完成（有线全项通过 / 无线发现时序隐患）

- **改动范围**：仅新建 `breath\TOOL\` 下 `protocol.py`、`comm_tool.py`、`README.md`、`run_comm.bat`。CRC 自检**独立复跑通过**（0x38 / 0x3D / STOP 帧 `AA 55 03 01 38 0D 0A`）。
- **实测（WorkBuddy 核对）**：
  - **有线 USB-TTL 直连 COM6**：POLL 847/847、静止 RPM 全 0；`CMD_VEL(0.2,0)` 四轮 63/58/52/60 RPM、X 推进至 +1.5m；`CMD_STOP` 立即停；`t` 断连 0.5s → timeout 4→5 且停车；`q` 自动 STOP 退出。**19.9 Hz / RTT 44 ms / 丢包 0**。
  - **HC-12 CH002 无线**：CMD_VEL 车动、遥测 x/y/yaw 更新；seq 03→06 计 drop=2；重复 seq=06 回缓存不累加；间隔 >200ms timeout 5→7→8 且停车。**全功能正确**。
- **⚠️ 关键时序隐患（必须决策，未解决）**：无线在 9600/FU3 下**实测 RTT 170~180 ms**（半双工实际 ~5.6~5.8 Hz）。上位机是「发一帧等回帧再发下一帧」的严格半双工心跳 → 心跳间隔 ≈175 ms，**距 STM32 `COMM_SESSION_TIMEOUT_MS=200U` 仅余 25 ms**；空口抖动 +30 ms 就会**误触发停车**。这不是 bug 是设计余量不足，**不能带到 S3-TEST 碰运气**。
  - 方案 A（WorkBuddy 推荐）：**超时放宽到 400 ms** —— 余量 225 ms，代价是真断连停车延迟 0.4 s（0.2 m/s 下多走 ~8 cm），安全可控；
  - 方案 B：HC-12 提 19200/38400 —— 但手册对应空中 236 kbps、灵敏度 −100 dBm、距离缩短，与"远距离"初衷相悖；
  - 方案 C：加上位机心跳补偿（收帧即发下一帧，减少等待） —— 受 RTT 物理限制，改善有限。
  - **待人类拍板后再动 `comm_session.h` 的超时宏**（改宏属安全逻辑变更，按用户偏好建议用 Argon 跑）。
- **一处如实标注的出入**：回传称 `main.c` 已 SHA256 字节级还原，实测 `main.c` = **7095 bytes / 16:23:25**（此前基线 7049 bytes），hex = 16:31:35 / 63501 bytes。内容核对**无遥控/测试代码残留**，仅 `MX_USART1_UART_Init()`（S3-02 W0 正常生成）+ 中文注释编码差异；但**不能写"字节级还原"**，记录按实标注。
- **遗留**：超时线决策（上）；无线端到端的完整连续遥控压力测试留 S3-TEST。
- **下一步**：人类拍板超时方案 → S3-04/05 补测 → S3-TEST。
- CubeMX：否（仅 TOOL 目录新增文件）。

## 2026-11-22 15:38 [派单 S3-01B + S3-02 — HC-12 配对 + USART1 通信 收口]

### 阶段 3 硬件与通信链路打通（HC-12 CH002 配对、USART1 半双工、强制停车）

**S3-01B（HC-12 配对，人类实测）**：
- 最终两块一致：**9600 / CH002 / FU3 / P8(+20dBm)**。人工把信道从默认 CH001 改 **CH002 避开干扰**；出厂两块信道原本不同（RC001 vs RC021）。
- 异常排查：右侧模块**天线断裂**、USB-TTL **3.3V 供电不足**导致发射瞬间掉电吐 `0xFF` → 换天线 + 改 5V 测试供电 + 统一 C002 + SET 悬空退出 AT、断电重启。
- 实测：`COM6↔COM3` 连续互发 `AAA`/`BBB` **4/4 双向稳定**，往返 ~90~100 ms。
- 小车接线：HC-12 B TXD→PA10、RXD→PA9、GND 共地、VCC **独立 3.3V 稳压（严禁从 STM32 取电）**、SET 悬空；HC-12 A 留电脑 USB-TTL。

**S3-02（USART1 通信，WorkBuddy 核对）**：
- W0 架构变更完成：CubeMX 启用 USART1（PA9/PA10，9600 8N1，无流控），**8 个手动 .c 全在**（含 comm_protocol.c），编译 0E/0W。
- 改动：新建 `comm_uart.h/c`（中断单字节环形缓冲、CRC 校验在 ISR、`HAL_UART_Transmit_IT` 非阻塞回包、ORE 自恢复）+ `comm_session.h/c`（半双工主从会话、序号/丢帧/重发、200ms 超时、26B 遥测）；`chassis.h/c` 新增 `Chassis_ForceStop()` 并在 Init 复用，Init 末尾调 `Comm_Session_Init()`、`Chassis_Update()` 内调 `Comm_Session_Update1ms()`；uvprojx 加两个新 .c。禁止文件时间戳未变（control/encoder/comm_protocol/imu/i2c 均原样）。
- **`Chassis_ForceStop()` 五件事齐全且三处共用**（Init 289 / CMD_STOP 85 / 超时 235）：清 vx/omega、`chassisHeadingMode=0`+`prevHeadingMode=0`、`chassisHeadingReached=1` 等航向状态归位、四路 `Control_SetTargetRpm(i,0)` 双保险。**航向环覆盖停车的 bug 已根治**。
- 超时判断：`HAL_GetTick()` 关中断原子快照 + 数值比较、无等待循环（避开 S2-04 死锁坑）；序号 `delta=rx.seq-lastSeq`，`delta==0` 重复（STOP 仍执行）、`delta>1` 计丢包、255→0 回绕正常；CMD_MODE 只写 `chassisYawFusionMode`、不碰 `chassisHeadingMode`；命令**在控制环执行、中断只解析**。
- **⚠️ 优先级表述纠错（WorkBuddy）**：回传称「USART1 优先级 5、SysTick 15，绝不会饿死 SysTick」—— **推理错误**。Cortex-M 数值越小优先级越高，5 < 15 恰说明 USART1 **高于** SysTick（`TICK_INT_PRIORITY=15U` 已核对），USART1 可抢占 SysTick。实际无碍是因回调仅数微秒，**结论对、理由错**，记录纠正，禁止据此推理去配更高优先级中断。
- **编译**：11-22 **15:37:05** Keil Build，**0 Error / 0 Warning**（Code=19772 / RO=2664 / RW=472 / ZI=3752），hex 63485 bytes，上电 TARGET=0 静止。
- **实车**：HC-12 无线链路已通（4/4 互发）；USART1 收发的 20 Hz 遥测/运动/CMD_STOP/200ms 断连停车**待 S3-03 Python 工具联调 + S3-TEST 验收**（当前仅静态核对 + 编译通过）。
- **下一步**：S3-03（Python + pyserial 上位机）→ S3-04/05 补测 → S3-TEST。
- CubeMX：是（W0 已由人类操作，完成）。

## 2026-11-21 21:00 [派单 S3-01 — HC-12 协议与纯软件接口 收口]

> 回传单写作「S3-01A」，本工程派单名为 S3-01（同一单，别名标注）

### 阶段 3 第一单完成（协议层，未碰串口/硬件）

- **改动范围**：新建 `Core/Inc/comm_protocol.h`、`Core/Src/comm_protocol.c`，`uvprojx` 加入 comm_protocol.c。禁止文件时间戳全未变（`main.c` 16:20 版、chassis.c 16:19 版、control/encoder/imu/i2c、`.ioc`）；**未调用任何 HAL USART API**。
- **协议实现**：帧 `AA 55 | TYPE | SEQ | DATA | CRC8 | 0D 0A`；TYPE 表（POLL01/VEL02/STOP03/MODE04/TELEMETRY10）与 DATA 定长（0/4/0/1/26 B）；CRC8 poly0x07/init0/no-reflect/xorout0 覆盖 TYPE+SEQ+DATA；小端定点数；序号回绕/丢帧/重发规则注释齐全；显式小端逐字节编解码（无结构体对齐隐患）。
- **接口**：`Comm_Crc8` / `Comm_BuildFrame` / `Comm_ParseFrame`（四类错码 -1头/-2尾/-3CRC/-4长度）+ `Comm_GetExpectedDataLen`、Pack/Unpack 系列纯函数。无状态机、无多帧缓冲（留 S3-02）。
- **验证（WorkBuddy 独立复核，不依赖实现方自测）**：`gcc -Wall -Wextra` 直接编译 `comm_protocol.c` 跑向量 —— CRC `{03 01}=0x38`、`{02 01 64 00 00 00}=0x3D`、`CMD_STOP(seq=1)` 组帧 `AA 55 03 01 38 0D 0A`（7B）、解析返回 0 —— **全部与规划一致**。
- **编译**：11-21 **20:57:57** Keil Build，**0 Error / 0 Warning**（Code=15752 / RO=2664 / RW=444 / ZI=3460），`breathing.hex` 52182 bytes，行为与 S2-06B 基线一致（上电静止、OLED `0000.0 RPM 000%`）。
- **遗留**：无（序号跳变/重发状态追踪按约定留 S3-02 会话层）。
- **下一步**：S3-01B（HC-12 配置：先配后接线）+ S3-02（USART1 架构变更 + 收发 + 统一强制停车 `Chassis_ForceStop()`）。
- CubeMX：否。

## 2026-11-21 16:25 [阶段 2 正式收官 — S2-TEST 验收记录]

- **产出** `AI_COLLAB/ACCEPTANCE/STAGE_02.md`：对照 `PLAN_STAGE_02.md` §五逐项验收，结论 **阶段 2 通过、同意收官**。
- **达标项**：运动学（直行同向/旋转反向/停车归零）、里程计（直行 2 m 纵向 0.1%、横偏 ≤5 cm、90°/180° 定点误差 −0.7°）、IMU（静止 YAW 稳定、CCW 为正、旋转真值一致）、安全（掉线 SAFE STOP、±250 饱和、1 ms 无阻塞）。
- **4 项非阻塞未测如实记录**：弧线旋转内外侧速度差、单轮 1 m 独立误差、360°/闭环回起点、编码器/融合模式切换对比 —— 均有代证或非核心，建议阶段 3 补测。
- **5 条工程结论沉淀**：等效轮距 0.3703（几何 0.20 的 1.85 倍）、闭环下 motorGain 保持 1.0、wheelScale 只修里程不修轨迹、定点转向需低速保底+过冲刹车、I2C 看总线时序不只看地址。
- **移交 Codex**：更新总览、定通信归属（原 S2-06 已移出阶段 2、归属未定）、阶段 3 规划。
- README 加验收记录入口；AI_SYNC §2 转阶段 2 收官、§5 S2-TEST 完成。
- CubeMX：否（文档）。

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

## 2026-11-21 15:04 [派单 S2-04 v2 — IMU 接入与 yaw 融合 收口]

### 阶段 2 第四单完成（IMU 硬件接入 + 防死锁驱动 + IMU 为主融合）

- **改动范围**：新建 `Core/Inc/imu.h`、`Core/Src/imu.c`；追加 `Core/Inc/chassis.h`（`#include "imu.h"` + `chassisYawFusionMode`）；修改 `Core/Src/chassis.c`（桩函数改真实 + 10 ms 分频读 + IMU 为主融合 + 复位零点）；`uvprojx` 加入 `imu.c`。禁止文件时间戳全未变（`main.c/.h`、`control.c/.h`、`encoder.c/.h`、`pid.c/.h`、`i2c.c`、`oled.c`、`.ioc`）。
- **防死锁实现（WorkBuddy 逐项核对）**：`imu.c` **无任何 `HAL_I2C_*` 调用**，全部 `I2C2->SR1/SR2/CR1/DR` 裸寄存器轮询；**DWT->CYCCNT 2 ms 硬超时**（`IMU_GetTimeoutCycles` 按 `SystemCoreClock` 算，168 MHz 下 336000 cycles）+ `IMU_MAX_POLL_LOOPS=350000` 双层兜底；NACK/ARLO/BERR 立即清标志发 STOP；`IMU_BusRecover()` 软复位 + `MX_I2C2_Init()` 重配 + `imuAvailable=0`。SysTick 不会被卡死。
- **10 ms 分频**：在 `chassis.c` 的 `Chassis_Update()` 内（`imuPollDivider >= CHASSIS_IMU_POLL_DIV`），**control.c 未改**。
- **配置序列**：`IMU_Init()`（由 `Chassis_Init()` 调用）→ DWT 使能 → KEY(0x69)=0xB588 解锁 → AXIS6(0x24)=1 → RRATE(0x03)=0x09 → RSW(0x02)=0x0C；**无 0x53 写**；IMU 后上线自动补配。
- **14 字节连读**：从 GZ(0x39) 连读 14 字节，`raw_gz=buf[1]<<8|buf[0]`、`raw_yaw=buf[13]<<8|buf[12]`（低字节在前）；`IMU_GetYawRate()` 换算 `raw/32768*2000*pi/180`，含 `imuYawSign`；yaw 相对角 `wrap(sign*wrap(raw−yaw0)+offset)`。
- **融合策略**：IMU 可用 → `chassisYaw=IMU_GetYaw()`，位置用 IMU 中点角投影；不可用 → 自动回退 S2-03 纯编码器；IMU 恢复时重新对齐基准角。IMU yaw/yaw_rate **未喂速度 PID**。
- **编译**：11-21 **14:56:15** Keil Build（ARMCC V5.06u7），**0 Error / 0 Warning**（Code=14960 / RO=2664 / RW=388 / ZI=3460），`breathing.hex` 49903 bytes。
- **实车状态**：① **未接 IMU 上电防死锁实测 —— 待人类烧录 14:56 版 hex 确认**（派单必测项，代码层已防护但实测未回传）；② 接 IMU 旋转 90°/180° 对比留 S2-TEST（模块待到货/接线）。
- **遗留**：未接 IMU 防死锁实测未回传；IMU 实车旋转对比未做；等效轮距与左右差异待 S2-05。
- **下一步**：S2-05 等效轮距（S2-03 实测约 0.40 m）与左右轮增益标定；S2-06 UART 通信。
- CubeMX：否（W0 已于 14:39 完成）。

## 2026-11-21 16:21 [派单 S2-06B — 定点转向精度微调 收口]

### 定点转向误差从 ~2° 压到 ~0.7°（优于 ≤1° 目标）

- **改动范围**：仅 `Core/Inc/chassis.h`、`Core/Src/chassis.c`。禁止文件时间戳全未变；`main.c` 临时测试后字节级还原（7049 bytes、无 `O:1/T:0` 残留）。
- **最终参数**（全局可写，非 const）：`CHASSIS_HEADING_TOL_RAD` 0.05→**0.008f**（约 0.46°）、`SETTLE_MS` 200→**150U**、`CHASSIS_HEADING_LOW_BAND_RAD=0.10f`、`CHASSIS_HEADING_OVERSHOOT_RAD=0.05f`、`chassisHeadingMinOmega=0.06f`（可写）、`chassisHeadingTimeoutMs=8000U`（可写）、`chassisHeadingTimedOut`（只读）。
- **控制率（WorkBuddy 核对）**：`Chassis_ComputeHeadingOmega(yaw_ref, is_point_turn, err_out)` 加模式隔离 —— **mode 1 传 `is_point_turn=0U` 仍纯比例**（第 471 行，避免直行画龙）；**mode 2** 四级：容差带内 `w=0` 刹车等待 150ms → 过冲符号翻转且 `|err|<0.05` 用 minOmega 主动反向 → 低速段 `max(Kp*|err|, minOmega)` 克服静摩擦 → 高速段纯比例，均限幅 ±max_w；`min_w>max_w` 有钳位保护。
- **保护未动**：mode 2 掉线 `IMU_IsAvailable()==0U` 立即停车（第 481 行）原样；超时 8000ms 置 `chassisHeadingReached=1`/`chassisHeadingTimedOut=1` 并停车回报余差（第 524-527 行）。
- **编译**：11-21 **16:20:31** Keil Build，**0 Error / 0 Warning**（Code=15752 / RO=2664 / RW=444 / ZI=3460），`breathing.hex` 52182 bytes，上电 mode 0 + `TARGET=0`。
- **实车（人类）**：
  - `TOL=0.017f` 时：+90°→**89.3°**、+180°→**179.3°**（误差均 −0.7°，`O:1 T:0`，无超调无振荡）；
  - 人类要求进一步提高 → `TOL=0.008f` 复测，平稳停准（最终取值）；
  - **定点误差约 0.7°，优于派单目标 ≤1°**。
- **回归**：mode 1 纯比例支路与 mode 2 掉线保护代码未改（S2-06 已实测直行横偏 <5cm、断 IMU SAFE STOP）；完整联动回归留 S2-TEST。
- **遗留**：无。**阶段 2 全部实现完成，下一步 S2-TEST 统一验收 → 阶段 2 收官。**
- CubeMX：否。

## 2026-11-21 16:08 [派单 S2-06 — 航向闭环纠偏 收口]

> 编号说明：本 S2-06 = 航向闭环（11-21 新增），与原 S2-06 基础通信（15:41 移出阶段 2）无关。

### 阶段 2 最后一个实现单完成（IMU 航向闭环，直行保持 + 定点转向）

- **改动范围**：仅 `Core/Inc/chassis.h`、`Core/Src/chassis.c`。禁止文件时间戳全未变（`control.c/.h`、`encoder.c/.h`、`pid.c/.h`、`imu.c/.h`、`i2c.c`、`.ioc`）；`main.c` 临时测试后字节级还原（7049 bytes 与基线一致，无 `MODE/SAFE STOP` 残留）。
- **W0 固化（保持 Watch 可写，非 const）**：`chassisTrackWidthM` 0.20→**0.3703f**（`CHASSIS_DEFAULT_TRACK_M`）、`wheelScale[]` 1.0→**1.015f**（`CHASSIS_DEFAULT_WHEEL_SCALE`）、`motorGain[]` 保持全 **1.0f**（不写开环 1.076）。
- **航向环实现（WorkBuddy 核对）**：`Chassis_ComputeHeadingOmega()` 在**差速解算之前**覆盖 omega（第 385-442 行 vs 452 行）；`err=wrap(yaw_ref−IMU_GetYaw())`、`omega=clamp(Kp*err, ±maxOmega)`，Kp 默认 1.0、maxOmega 1.0 rad/s；mode 0 原行为、mode 1 锁存基准保持、mode 2 定点转向。**速度 PID 反馈仍只读 `motorSpeedFiltered[]`，IMU yaw 未喂 PID**。1 ms 中断无阻塞。
- **安全**：mode 2 下 `imuAvailable==0` 立即清零 vx/omega/target 停车、绝不盲转（398-406 行）；到达判据 `|err|≤0.05 rad(2.86°)` 持续 200 ms → 锁死停车、`chassisHeadingReached=1`。
- **编译**：11-21 **16:07:32** Keil Build，**0 Error / 0 Warning**（Code=15444 / RO=2664 / RW=424 / ZI=3456），`breathing.hex` 51290 bytes，上电 mode 0 + `TARGET=0`。
- **实车全项（人类确认）**：
  - **测试 A 航向保持直行 2 m**：横偏由 S2-05 右偏 ~10 cm 收敛到**左偏 ≤5 cm**（满足判据）；里程计 X=2.002 m vs 实走 2.00 m（**0.1%**），Y=−0.012 m、YAW=−0.3°。
  - **测试 B 定点转向**：+90° 实停 **88.0°**（−2.0°）、+180° 实停 **177.7°**（−2.3°），均 ≤5°、零超调（停在目标前约 2° 系 2.86° 容差触发 200 ms 锁死，符合预期）。
  - **测试 C IMU 掉线**：mode 2 下发 +90° 时断开 IMU → OLED `IMU:NO`/`MODE:2`/`SAFE STOP!`、四轮 0.0 RPM、车静止，不死锁不盲转。
- **遗留**：mode 2 到达容差 0.05 rad 会稳定停在目标前约 2°；若 S2-TEST 要求压到 1° 内再微调容差/Kp（非功能缺陷）。
- **结论**：S2-06 设计目标与实车判据一次性全通过。**阶段 2 最后一个实现单完成，下一步 S2-TEST 统一验收。**
- CubeMX：否。

## 2026-11-21 15:46 [派单 S2-05 — 实车标定 收口]

### 阶段 2 第五单完成（等效轮距 / motorGain / wheelScale 实测标定）

- **改动范围**：仅 `chassis.h` 追加只读观测 `chassisOdomDistLeft/Right` 声明，`chassis.c` 在 `Chassis_UpdateOdometry()` 累加、`Chassis_ResetOdometry()` 清零；`Chassis_Init()` 默认值仍 `0.20f` / gain、scale 全 `1.0f`（**未写死标定值**），`WHEEL_DIAMETER_M` 只读。禁止文件时间戳全未变；`main.c` 临时 OLED 测试后字节级还原（7049 bytes 与 S2-04 版一致、无残留）。
- **编译**：11-21 **15:39:54** Keil Build，**0 Error / 0 Warning**（Code=15000 / RO=2664 / RW=396 / ZI=3460），`breathing.hex` 50022 bytes，上电 `TARGET=0`。
- **等效轮距（3 次原地旋转，IMU 真值 + 累计距离差）**：T1=0.364 / T2=0.376 / T3=0.370 m，**均值 0.3703 m，极差 3.24%**（≤5% 判据）。与 S2-03「0.20 m 发 90° 实转 ~48°」自洽（0.20/0.3703×90≈48.6°）。**建议值 0.3703f**（未固化，待人类决定）。
- **motorGain（20/40/60/80% 开环 + 闭环 100 RPM 验证）**：四轮开环增益 M1=3.234 / M2=3.167 / M3=3.216 / M4=2.910 RPM/%（M4 偏慢约 8%）；**闭环在 `motorGain=1.0` 下四轮稳态 99.5~100.2 RPM（±0.5%），远优于 ±4%**。
  - **⚠️ 重要工程结论**：**闭环模式下 `motorGain[]` 维持全 1.0f**。若把开环比值 0.968/1.076 写入，会强迫 M4 闭环比 M1 快 11% 导致左偏 —— 速度 PI 已闭环拉齐，开环前馈不可用。除非日后改为前馈加到 PWM 占空比，否则不启用开环补偿值。
- **wheelScale（2 m 地砖直行）**：里程计 X=1.971 m / Y=−0.008 m；实走 2.00 m，纵向误差 **1.45%**（≤3%）；左右累计差仅 2 mm。建议 `wheelScale[]={1.015}×4`（未固化，不改写轮径）。
- **遗留**：无航向闭环下 2 m 自由直行右偏约 10 cm（~2.86°），源自起点 2~3° 初角误差 / 微打滑 / 轮径公差；`wheelScale` 只修里程读数不改轨迹，人类确认**不靠静态硬调差速掩盖**。→ 需航向闭环根治（新需求，见下）。
- **编号纠偏（WorkBuddy）**：实现方回传中反复写「进入 S2-06（IMU 航向闭环纠偏）」，但 **S2-06（基础通信）已于 15:41 移出阶段 2**，且「IMU 航向闭环」从未定为 S2-06。本记录不沿用该错误编号，记为**遗留待规划项**。
- **下一步**：S2-TEST 统一验收；待固化的 `chassisTrackWidthM=0.3703f`、`wheelScale=1.015f` 由人类决定；航向闭环（直行纠偏 / 定点精确转向）为新增需求，留待阶段末规划，不自增派单。
- CubeMX：否。

## 2026-11-21 15:41 [文档调整 — 基础通信移出阶段 2]

- **人类裁定**：基础电脑通信（原 S2-06）**肯定不是阶段 2 任务**，但暂不指定归属阶段（「先不想放哪个阶段」）。
- **改动**：从 `PLAN_STAGE_02.md`（阶段目标、任务拆分表、S2-06 章节、验收标准、细则 5、阶段 3 预留、最终交付清单）、`AI_SYNC.md`（§5 待办、§7 第 13 条并新增第 20 条、广播）、三张已出派单的「下一位提示」、`BRIEF_FOR_CODEX.md` 中移除 S2-06；规划里以删除线 + 说明形式存档原内容，参考口径保留。
- **阶段 2 现为**：S2-01 接口 → S2-02 运动学 → S2-03 里程计 → S2-04 IMU → S2-05 标定 → **S2-TEST 统一验收**（前五单全部完成或已出派单）。
- **通信归属留空**：待阶段末由 Codex 规划，不预设是阶段 3；基础/完整通信与 200 ms 超时的参考口径存档在 `PLAN_STAGE_02.md` §七细则 5。
- 未改任何源码/`.ioc`/hex。

## 2026-11-21 15:17 [派单 S2-04 最终版确认 — 上电收敛 + 实车通过]

> 相对 15:04 收口版的增量（同一单，非新单）

- **新增 1000 ms 启动零点收敛**：模块手册启动时间 1000 ms，`imu.c` 加 `imuWarmupCount=100`，上电前 100 次 10 ms 采样持续跟随 `imuYaw0`，滤波收敛后锁存（第 390-394 行）。解决上电初期 yaw 跳变。
- **临时测试还原**：人类现场临时改 `main.c` 用 OLED 观测 `IMU:OK/Gz/YAW`，测后已**完整还原** —— WorkBuddy 核对 `main.c` 大小 7049 bytes 与 14:39 CubeMX 生成版一致，全文无 IMU 测试残留。
- **编译**：11-21 最终 hex **文件系统时间 15:17:01**（实现方报告 15:15:01，同类小偏差按文件系统记），**0 Error / 0 Warning**（Code=14968 / RO=2664 / RW=388 / ZI=3460），49932 bytes。
- **实车验证（人类确认，接 IMU）**：
  - 接线：3V3→3.3V、GND→GND、SCL→PB10、SDA→PB11（与 OLED I2C1 PB6/PB7 隔离）；
  - 通信正常 OLED 显示 `IMU:OK`；静止 `Gz≈0`；加 1000 ms 收敛后上电 1 秒 `YAW` 稳定 0.0° 附近；
  - **方向标定验证：原地逆时针（左转）90° → YAW 读数 +90°，确认 `imuYawSign=+1.0f`（CCW 为正）正确** —— 与坐标系约定一致，且对比 S2-03 纯编码器同动作仅 45°，坐实编码器打滑误差；
  - 融合默认 `chassisYawFusionMode=1`（IMU 为主），`imuAvailable=0` 或手动置 0 时无感回退纯编码器。
- **S2-04 结论**：代码层 + 实车双双通过，**正式完成**。遗留「未接 IMU 上电防死锁实测」仍待人类单独确认（接 IMU 实车正常已间接验证驱动无死锁，但异常场景未单测），列 §5 待办 2-S2-04b，不阻塞 S2-05。
- **下一步**：S2-05 等效轮距（S2-03 实测约 0.40 m）与左右轮增益/里程 scale 标定 —— 现在有 IMU 真值航向角可用作标定基准。

## 2026-11-21 14:21 [派单 S2-03 — 整车里程计积分 收口]

### 阶段 2 第三单完成（纯编码器里程计 + 发现 skid-steer 打滑）

- **改动范围**：仅 `Core/Inc/chassis.h`、`Core/Src/chassis.c`（源码时间戳 11-20 21:17/21:18）。`main.c` / `control.c` 为临时实测后**已彻底还原**：`main.c` 6738→大小 7030 bytes 与 11-18 基线一致、显示逻辑原样（M1~M4 的 RPM + 占空比）；`control.c` 8638 bytes 与 S2-02 版一致。禁止文件时间戳全未变。
- **实现要点**：
  1. `chassis.c` 新增 `prevDistance[4]`、`Chassis_UpdateOdometry(dt, track)`：仅用 `Control_GetDistanceM(i)` 累计距离差分 × `wheelScale[i]`，**禁用 `speed_rpm` 积分位姿**；`d_left=(d0+d2)/2`（M1/M3）、`d_right=(d1+d3)/2`（M2/M4）、`ds=(dL+dR)/2`、`dtheta=(dR−dL)/track`；区间中点角度积分 + `Chassis_WrapToPi()` 归一化；轮距 ≤0 跳过 dtheta。
  2. 观测速度 `chassisOdomVx/Omega`：LPF alpha=0.15、连续 20 ms 无位移归零；**仅供 Watch，不喂 PID**。
  3. `Chassis_ResetOdometry()`：关中断保护下对齐 `prevDistance`、清 x/y/yaw/odom。`Chassis_Init()` 内调用一次。
- **编译**：11-21 **14:20:55** Keil Build，**0 Error / 0 Warning**（Code=13252 / RO=2664 / RW=360 / ZI=3376），`breathing.hex` 45080 bytes。临时测试代码已移除并重编安全基线（目标 0、上电不跑）。
- **实车验证（人类，临时 OLED + 闭环 0.25 m/s 直行 + 1.5 rad/s 旋转）**：
  - **定点直行 1.00 m**：实测行驶 1.03 m（误差约 **+3%**，含制动滑行），方向略向右微偏 —— 纯编码器直行距离精度良好，与轮径 0.066404 m 一致。
  - **原地左转 90°**（按几何轮距 0.20 m 积分到 +90° 停）：车体实际仅逆时针转约 **45°** → **等效滑移轮距约 0.40 m，约为几何轮距 2 倍**。
- **重要发现（影响 S2-04/S2-05）**：普通四轮 skid-steer 原地旋转横向打滑约 2 倍，单靠几何轮距积分 yaw 误差大。直行距离已较准。→ S2-04 接 IMU 解决打滑下的航向精度；S2-05 标定等效轮距与左右轮差异。
- **下一步**：S2-04 IMU 标定与 yaw 融合；S2-05 等效轮距标定。
- CubeMX：否（I2C2 推迟到 S2-04 前）。

## 2026-11-20 21:11 [派单 S2-02 — 差速底盘运动学 收口]

### 阶段 2 第二单完成（vx/omega → 四轮 RPM 下发，已恢复停车基线）

- **改动范围**：仅 `Core/Inc/chassis.h`、`Core/Src/chassis.c`。禁止文件时间戳全未变（`control.h/.c`、`encoder.h/.c`、`pid.h/.c`、`main.c`、`tim.c`、`motor.c`、`breathing.ioc`）。
- **实现要点**：
  1. `chassis.h`：`CHASSIS_MAX_OMEGA_RADS` 6.0→**8.5f**，新增 `CHASSIS_MAX_WHEEL_RPM=250.0f`，更新 `chassisTrackWidthM` 注释（默认 0.20f 可写、S2-05 精修）。
  2. `chassis.c`：引入 `control.h` / `encoder.h`（只读 `WHEEL_DIAMETER_M`）；`chassisTrackWidthM` 默认与 `Chassis_Init()` 设为 **0.20f**；`Chassis_Update(dt)` 实现 `left=vx−ω·track/2` / `right=vx+ω·track/2` → `rpm=v·60/(π·0.066404)` → 乘 `motorGain[i]` → 四轮 ±250 RPM 等比饱和（`scale=250/max|rpm|`，保 vx:omega 比例）→ `Control_SetTargetRpm(i, rpm)` 下发。
- **WorkBuddy 核对**：差速公式、RPM 换算、gain 相乘、等比饱和、下发调用齐全；**无 `Motor_SetOutput()` 直驱、无 vy/麦克纳姆公式**；最终源码目标锁存 `chassisTargetVx/Omega=0`，临时测试语句已移除，未遗留。
- **omega 上限依据**：单轮 250 RPM → 0.869 m/s；轮距 0.20 m 下理论自转正极值 `2×0.869/0.20=8.69 rad/s`，取 **8.5** 留余量；组合工况由四轮 ±250 等比饱和兜底。
- **编译**：11-20 **21:11:08** Keil Build，**0 Error / 0 Warning**（Code=11004 / RO=2632 / RW=348 / ZI=3356），`breathing.hex` 38661 bytes。
- **实车（人类确认，架空单测）**：`Chassis_SetVelocity(0.0f, 2.0f)`（理论左 −57.5 / 右 +57.5 RPM）→ 实测四轮符号正确（M1/M3 后退、M2/M4 前进，逆时针左转），OLED 四路约 60 RPM 上下稳定浮动。测后移除临时语句、重编回 `vx=0/omega=0` 上电停车基线。
- **遗留**：0.20 m 为几何粗测，等效轮距待 S2-05 原地旋转标定精修；完整落地直行/旋转/停车联合测试留 S2-TEST。
- **下一步**：S2-03 整车里程计积分。
- CubeMX：否。

## 2026-11-20 20:54 [派单 S2-01 v2 — 底盘与里程计接口骨架 收口]

### 阶段 2 第一单完成（接口骨架，车行为与阶段 1 一致）

- **改动范围**：新建 `Core/Inc/chassis.h`、`Core/Src/chassis.c`；`MDK-ARM/breathing.uvprojx` 添加 `..\Core\Src\chassis.c`；`Core/Src/control.c` 严格只改 2 处调用点 + 1 处 include（第 3 行引入 `chassis.h`、第 119 行 `Chassis_Init()` 在 `controlInitialized=1U` 之前、第 222 行 `Chassis_Update(CONTROL_PID_DT)`）。`control.h`、`main.c` 及全部禁止文件未动（时间戳复核）。
- **接口冻结**：`Chassis_Init()` / `Chassis_SetVelocity(vx, omega)` / `Chassis_Update(dt)` / `Chassis_GetPose(x,y,yaw)`（NULL 检查）/ `IMU_IsAvailable()` / `IMU_GetYaw()` / `IMU_GetYawRate()`（均返回 0）。
- **SetVelocity 语义（v2 关键点）**：仅 NaN 拒收、轮距未标定且 omega≠0 拒收（置 `chassisCmdRejected=1` 不更新锁存）、`|vx|≤0.869` / `|omega|≤6.0` 截断后锁存 `chassisTargetVx/Omega`；**不换算 RPM、不调 `Control_SetTargetRpm()`、不驱动电机** —— WorkBuddy 核对源码确认无相关调用。
- **全局默认值**：`chassisTrackWidthM=0`（未标定）、`motorGain[]=wheelScale[]={1,1,1,1}`（相互独立）、`chassisX/Y/Yaw=0`、`chassisTargetVx/Omega=0`、`chassisCmdRejected=0`、`imuAvailable=0`。
- **omega 上限依据**：单轮 250 RPM → 0.869 m/s；轮距约 0.29 m 粗估 `2×0.869/0.29≈6.0 rad/s`。S2-02 仍需按实测轮距做四轮 ±250 RPM 饱和 / 等比缩放。
- **编译**：11-20 **20:50:21** Keil Build，**0 Error / 0 Warning**（Code=10628 / RO=2632 / RW=348 / ZI=3356），`breathing.hex` 37602 bytes。
- **实车（人类确认）**：烧录 20:50 版 hex，上电车静止、OLED 四行 `0000.0 RPM  000%`；此前重插线导致的 M1/M2 编码器插错已排查修复。
- **遗留**：S2-02 实现运动学与里程计前，需实测左右轮中心距（m）填入 `chassisTrackWidthM`。
- **下一步**：S2-02 差速运动学。CubeMX/I2C2 按用户裁定推迟到 S2-04 前。
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
