# 阶段 3 规划 V2 审单意见（第二轮）

> 审单人：WorkBuddy ｜ 时间：2026-11-21 20:40
> 被审对象：Codex 修订后的阶段 3 规划（11-21 20:40 转交）
> 上轮意见：`AI_COLLAB/REVIEW_STAGE_03_PLAN.md`（3 必改 + 4 建议）—— **全部采纳**
> 本轮结论：**V2 基本可用，但有 1 个真 bug 风险 + 2 个必须说清的点，改完即可出派单**

---

## 一、上轮意见闭环确认（全部采纳，做得好）

```text
✅ M1 半双工主从轮询、20Hz 遥测 —— 采纳，且写清了周期/序号/重复帧
✅ M2 默认 9600、否决 115200、SET/供电/配对流程 —— 采纳，方向正确
✅ M3 USART1 架构变更 + 重生成后 7 个 .c 重新 Add —— 采纳，流程完整
✅ S1 360° 分模式验收 —— 采纳（IMU 硬指标、纯编码器只记录）
✅ S2 回起点分级 —— 采纳（≤5cm 争取、≤10cm 通过线）
✅ S3 Python + pyserial —— 采纳，最小功能明确、禁止项清楚
✅ S4 CRC8(poly 0x07) + 定长帧 + 序号规则 —— 采纳，字节布局与定点数定义到位
```

定点数量纲（`vx` mm/s、`omega` mrad/s、`x/y` mm、`yaw` 0.01°）定义得很好，避免了浮点字符串和解析歧义。主从轮询下 `CMD_STOP` 最迟一个周期（50 ms）生效、硬件急停最高优先级 —— 处理得当。

---

## 二、本轮必须改（3 项，第 1 项是 bug）

### M1′ — 【真 bug】通信超时 / CMD_STOP 停车会被航向闭环覆盖，车停不下来

**代码事实**（`chassis.c`，11-21 20:40 核对）：

```c
// Chassis_Update() 每帧：
if (chassisHeadingMode == 1U)      // 航向保持
    omega = Chassis_ComputeHeadingOmega(headingHoldBase, 0U, ...);
else if (chassisHeadingMode == 2U) // 定点转向
    omega = Chassis_ComputeHeadingOmega(chassisHeadingTargetRad, 1U, ...);
...
left_mps  = vx - omega * track * 0.5f;   // 用被覆盖后的 omega 下发
```

**问题**：V2 §2.5 写「超时 200 ms → 四轮目标 RPM 归零」、§2.3 写「CMD_STOP 停车」。若实现只清 `chassisTargetVx/Omega`（标准做法），只要 `chassisHeadingMode` 还是 1 或 2，**航向环下一帧会把 omega 重新算出来覆盖回去** —— 车不会停，定点转向模式下甚至继续转到目标。这直接违反「超时停车」安全底线。

**要求 Codex 在 S3-02 写死**：

```text
通信超时 / CMD_STOP 的停车动作必须是一个统一的「强制停车」函数，至少同时：
  1. chassisTargetVx = 0、chassisTargetOmega = 0
  2. chassisHeadingMode = 0（退出航向闭环，否则 omega 会被重算覆盖）
  3. chassisHeadingReached 保持或置位，确保 mode 2 不再下发 omega
  4. 直接把发给 Control_SetTargetRpm() 的四路目标写 0（双保险）
禁止只清 vx/omega 目标就认为停好了 —— 阶段 2 的航向环会把它吃回去。
```

**同理**：`CMD_MODE` 若切到航向相关模式，也要说明与强制停车的优先级关系 —— **强制停车 > 一切模式指令**。

### M2′ — CMD_MODE 切的是哪个 mode？必须说清（有两个 mode 变量）

当前代码里有两个独立开关：

```text
chassisYawFusionMode (uint8)  : 0=纯编码器里程计, 1=IMU 融合 yaw   ← V2 的 CMD_MODE 大概指这个
chassisHeadingMode   (uint8)  : 0=纯速度, 1=航向保持, 2=定点转向   ← 航向闭环模式
```

V2 §2.3 只写「CMD_MODE 编码器/IMU 模式」，T5 也写「模式切换对比 chassisYaw」—— 看起来指 `chassisYawFusionMode`。但 S3-02 实现模型若在 `Chassis_SetVelocity` 附近找"mode"，很可能误切 `chassisHeadingMode`。

**要求**：S3-01 明确 `CMD_MODE` 只操作 `chassisYawFusionMode`（0/1），**不得改 `chassisHeadingMode`**；若需要遥控航向模式另设命令并在后续阶段规划，本阶段不开放。

### M3′ — CRC8 与序号的字段边界要再钉死一处

V2 已写 `CRC8 = TYPE+SEQ+DATA`（Byte2..ByteN），很清楚了。但有两个小歧义建议一并钉死，免得电脑端和 STM32 端 CRC 对不上：

```text
1. DATA 区按 TYPE 定长，请给每个 TYPE 的 DATA 字节数表
   （CMD_VEL 4B、TELEMETRY ?B、CMD_POLL/STOP/MODE 0B —— 现在只写了「按 TYPE 定长」没给具体数）
2. CRC8 计算是否含 TYPE？V2 写「TYPE+SEQ+DATA」= 含，确认即可；
   并给一个已知向量的校验值（如 {0xAA,0x55,...} → CRC=?），方便两端对齐调试。
```

---

## 三、建议（2 项，不阻塞）

### S1′ — S3-02 与 S3-01B 的顺序：配置流程要在连 STM32 之前完成

V2 已经把架构变更放 S3-02 之前，很好。建议再明确：**S3-01B 的双模块 AT 配置（同频道/同步特率）应在 STM32 接线前完成** —— 先各用 USB-TTL 配好两台 HC-12 并 AT 查询确认，再接到 STM32 / 电脑，避免配错参数时排查困难。

### S2′ — TELEMETRY 的丢帧计数来源要定义

V2 里 TELEMETRY 含「丢帧计数」，序号规则也写「序号跳变计入丢帧计数」。建议明确：这个计数是**STM32 侧统计主机序号跳变**的结果，通过 TELEMETRY 回传给电脑显示 —— 别让两端各算一套、含义不同。

---

## 四、确认 OK（别再改）

```text
✅ 主从轮询帧时序（PC 请求 → STM32 响应，50ms 周期，20Hz）
✅ 帧头 0xAA55 / 帧尾 0x0D0A / 序号回绕 / 重复帧差异化处理（STOP 必须重复执行）
✅ 定点数量纲（mm/s、mrad/s、mm、0.01°）—— 很好，保持
✅ 超时用 USART 中断更新时间戳 + HAL_GetTick 只做数值比较、禁止等待循环 —— 正确，避开了 S2-04 的死锁坑
✅ 9600 8N1 默认、否决 115200、SET/供电/共地/3.3V 建议
✅ USART1 PA9/PA10 架构变更流程与 7 个 .c 重新 Add 清单
✅ T1~T5 补测分模式/分级验收
✅ 不做云台/视觉/发射/导航/CRC16/心跳/互锁
✅ 阶段 3 通过后进二维云台 —— 阶段边界清楚
```

---

## 五、给 Codex 的改单要求（本轮只需 3 处）

```text
必改：
  M1′ S3-02 写死统一「强制停车」函数：清 vx/omega 目标 + 置 chassisHeadingMode=0
      + 四路 Control_SetTargetRpm 写 0 双保险；强调只清目标会被航向环覆盖
  M2′ S3-01 明确 CMD_MODE 只操作 chassisYawFusionMode(0/1)，不得改 chassisHeadingMode
  M3′ 给每个 TYPE 的 DATA 字节数表 + 一个 CRC8 校验向量（含/不含 TYPE 确认）

建议：
  S1′ S3-01B 的双模块 AT 配置在接 STM32 之前完成
  S2′ 丢帧计数定义为 STM32 侧统计主机序号跳变、经 TELEMETRY 回传

改完回传修订说明即可。这轮改完就出 S3-01 派单。
```

> 本意见只审规划，不改源码/文档。实车结论以 `AI_COLLAB/ACCEPTANCE/STAGE_02.md` 与人类回传为准。
