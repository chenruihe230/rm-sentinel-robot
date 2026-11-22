# 派单 S3-DEMO v3 — 精度提升 + 操控娱乐化（展示层增量）

> 致 Argon4：v2 已交付并通过核对（18:11 hex，0E/0W）。本单是 v2 的**微创增量**：车端梯形减速 + 里程计归零动作，上位机 WASD 赛车模式 + 双击地图 + 动作剧本。
> 派单人：WorkBuddy ｜ 时间：2026-11-22 19:46 ｜ 依据：反重力优化提案 + WorkBuddy 评估（三处纠正见 §0）
> 前置：S3-DEMO v2 ✅（TYPE 0x05 / comm_actions.h/c / HMI 五区 + 原始帧工具已就绪）

---

## 0. WorkBuddy 评估结论与三处纠正（先读）

**整体可做，价值高、风险低**（车端只改 `comm_actions.c`，上位机只改 `TOOL\hmi\`）。但提案有三处必须纠正：

### 纠正 1 — 编号冲突（关键）

提案说「新增 `0x06` 或启用 `0x05` 做远程里程计归零」—— **错误**：

```text
TYPE 0x05 = CMD_ACTION（已占用，不可改）
action 0x05 = 回起点预留（RETURN_ORIGIN，第一版不做，保持预留）
★ 里程计归零必须用新的 action_id = 0x06（放在 TYPE 0x05 的 DATA 里）
   即帧：AA 55 05 SEQ 06 00 00 CRC8 0D 0A
```

不是新 TYPE，不是动 0x05 预留位，不加新命令类型。

### 纠正 2 — "点地图指哪打哪"精度预期打折

串联动作误差会累积（转向 ±0.7° + 直行 ~1.5% → 落点偏移）。**定位为演示级落点（预期误差 ~5 cm 量级，远距离更大）**，界面提示写"演示级导航"，不承诺精准到达。逻辑（转 Δyaw → 走 L 串行）本身正确，保留。

### 纠正 3 — 剧本打断要两层都做

提案说"任何 WASD/按钮/急停清空队列"—— 对，但要写清：

```text
上位机侧：清空动作队列 + 停止下发下一步
车端侧：靠已有单一司机规则 Abort 当前动作（不用新机制）
两层都要做，否则队列清了但车还在执行旧动作
```

## 1. 车端精度优化（仅改 `comm_actions.h/c`）

### W1 — 直行梯形速度曲线

现状：`COMM_ACTION_MOVE_SPEED_MPS = 0.25f` 阶跃，起步微打滑、终点急刹前冲 1~2 cm。

改为（**只改速度给定，不碰 PID/里程计/航向环**）：

```text
起步：前 250 ms 从 0.08 → 0.25 m/s 线性爬升
巡航：0.25 m/s
末端：剩余距离 ≤ 150 mm 时，按剩余距离线性降速至 0.07 m/s 慢速爬行
到位：|Δx| ≥ |target| → 立即 Chassis_ForceStop()
```

- 宏化参数（Watch 可写更好）：`COMM_ACTION_RAMP_UP_MS=250`、`COMM_ACTION_SLOW_DOWN_MM=150`、`COMM_ACTION_CRAWL_MPS=0.07`。
- 625 mm 以下短距离要防止"还没爬完就该减速"—— 做简单判断：距离 < 400 mm 时缩短爬升时间或直接用低速全程。回传说明处理方式。
- **保持单一司机规则与 10 s 超时不变**；减速逻辑只在 `0x01` 动作内，不影响手动 CMD_VEL。

### W2 — 新增 action_id 0x06 远程里程计归零

```text
action_id 0x06（COMM_ACTION_RESET_ODOM）：
  先 Comm_Action_Abort() → Chassis_ForceStop() → Chassis_ResetOdometry()
  状态置 DONE
★ 不动 0x05 预留位；不加新 TYPE
```

`Chassis_ResetOdometry()` 已存在（chassis.c 第 177 行），直接调用。**不改 chassis.c**。

## 2. 上位机操控升级（仅改 `TOOL\hmi\`）

### W3 — WASD 键盘赛车模式

```text
开关：「键盘驾驶」按钮/勾选
按住 W/S：前进/后退（CMD_VEL，走单一司机规则）
按住 A/D：原地左/右转（CMD_VEL(0,±ω)）
W+A / W+D：边走边拐画弧线（vx + omega 同时给）
松手：自动 CMD_VEL(0,0) 停稳
三档变速：慢 0.15 / 常 0.30 / 快 0.60 m/s（界面切换）
空格：全局急停（CMD_STOP）—— v2 已有，保持
```

- 键盘事件不能阻塞 GUI 线程；用 Qt 的 keyPressEvent/keyReleaseEvent 维护按键集合，定时器周期发_cmd（如 50 ms）。
- 进入键盘驾驶时先清动作队列 + Abort 车端动作（纠正 3）。

### W4 — X-Y 轨迹图车头图标 + 双击导航

```text
1. 轨迹图实时画小车图标（三角/箭头）+ 车头朝向射线（用 ImuYaw）
2. 鼠标双击图上任意点 (X*, Y*)：
   Δyaw = atan2(Y*−y_now, X*−x_now) − yaw_now   （归一化到 ±π）
   L = hypot(X*−x_now, Y*−y_now)
   串行下发：CMD_ACTION(0x02, Δyaw*10) → 等 DONE（status bit5）→ CMD_ACTION(0x01, L*1000)
   界面提示「演示级导航，落点误差约 5 cm 量级」
```

- 双击导航执行中，任何手动输入/急停 → 上位机清队列 + 车端 Abort（纠正 3）。

### W5 — 动作剧本编排器（一键花式）

```text
界面：动作队列列表（可增删）+ 预设剧本按钮：
  [正方形巡逻]  前进1m → 转90° → 前进1m → 转90° ×4
  [折返跑]      前进2m → 掉头 → 前进2m → 掉头
  [摇摆舞]      左转30° → 右转60° → 左转60° → 右转30°（循环）
执行：收到 status bit5 (ACTION_DONE) 后停 0.3 s 下发下一步
中断：任何 WASD / 手动按钮 / 空格急停 → 清队列 + 车端 Abort（纠正 3）
```

## 3. 边界（硬）

```text
允许：comm_actions.h/c、TOOL\hmi\ 下文件
禁止：comm_protocol.h/.c（TYPE 与 CRC 不动）、comm_session.c/.h、chassis.c/.h、
      control/encoder/pid/imu/i2c/oled/main/.ioc、TOOL/protocol.py、TOOL/comm_tool.py、
      AI_COLLAB\、docs\
不改 400ms 超时宏、不改 PID/安全宏、不动已有 action 0x01~0x04 语义、0x05 保持预留
单一司机规则与 CMD_STOP 最高优先级不变；上电默认无动作
```

## 4. 验收标准

1. Keil 0 Error / 0 Warning，新 hex；上位机 `python main.py` 独立运行。
2. 编号核对：里程计归零是 **action 0x06**、TYPE 仍 0x05、0x05 动作位仍预留 —— 无冲突。
3. 梯形减速：`CMD_ACTION(0x01,1000)` 停止误差优于 v2（v2 约 1~2 cm 前冲 → 期望毫米级，或给出实测值）；短距离（<400mm）不失控。
4. 里程计归零：`0x06` 后 `chassisX/Y/Yaw ≈ 0`，车停稳。
5. WASD：八向（含弧线）可动、三档变速有效、松手即停、空格急停。
6. 双击地图：能算出 Δyaw/L 并串行下发两步，落点误差记录（预期 ~5 cm 量级）；执行中可打断。
7. 剧本：三种预设能跑完；执行中 WASD/急停能清队列 + 打断车端动作。
8. **回归**：已有基本动作、POLL/VEL/MODE、原始帧工具、单一司机规则、400ms 超时全部不变；禁止文件时间戳未变。

> 无车/无 HC-12 时可用 HMI 的 Mock 仿真验证 3/5/6/7 的逻辑，实车误差留现场演示。

## 5. 回传要求

```text
1. 修改文件清单（车端 / 上位机分开）
2. Keil 编译结果与 hex 时间
3. 梯形减速实现与实测停止误差（含短距离处理）
4. action 0x06 实现与归零实测
5. 上位机新功能说明（WASD/双击/剧本）与截图或 mock 验证
6. 编号核对（0x06 非新 TYPE、0x05 仍预留）
7. 回归核对（禁止文件未动、单一司机/400ms/急停不变）
8. 遗留问题与后续改进点
```

---

**下一位提示**：v3 是纯增量，硬边界是「**不动 TYPE / PID / 里程计 / 400ms / 已有动作语义**」。三处纠正（编号 0x06、演示级精度、两层打断）已在 §0，务必先读。做完阶段 3 展示层彻底收官。
