# RM 哨兵机器人

基于 **STM32F407VET6 + Raspberry Pi 5** 的 RM 哨兵机器人工程，包含四轮底盘、二维云台、视觉追踪、发射机构、激光雷达和自主导航。

## 当前进度

```text
阶段 0：总体设计冻结              ✅
阶段 1：四轮独立速度 PID          ✅
阶段 2：运动学、里程计与 IMU       ✅
阶段 3：底盘补测与基础通信         进行中
阶段 4：二维云台                  未开始
阶段 5：视觉目标追踪              未开始
阶段 6：发射机构与完整通信安全     未开始
阶段 7：激光雷达与自主导航         未开始
阶段 8：整机任务整合              未开始
```

## 系统架构

```text
摄像头 / 激光雷达 / GPS（远期）
              ↓
Raspberry Pi 5
  视觉检测、追踪、SLAM、导航、任务决策
              ↓
UART / USB / CAN
              ↓
STM32F407
  四轮 PID、运动学、IMU、云台、发射、安全
              ↓
电机 / 编码器 / IMU / 发射机构
```

## 工程目录

```text
breathing/          STM32 CubeMX、HAL、Keil 工程
AI_COLLAB/          多 AI 协作、派单、规划和验收记录
```

## 重要文档

- [总工程总览](breathing/docs/PROJECT_OVERVIEW.md)
- [完整阶段规划](breathing/docs/PROJECT_STAGES.md)
- [阶段 1 任务单](breathing/docs/TASK_STAGE_01_PID.md)
- [协作文档索引](AI_COLLAB/README.md)
- [多 AI 当前状态](AI_COLLAB/AI_SYNC.md)
- [阶段 2 规划](AI_COLLAB/PLAN_STAGE_02.md)
- [阶段 1 验收](AI_COLLAB/ACCEPTANCE/STAGE_01.md)
- [阶段 2 验收](AI_COLLAB/ACCEPTANCE/STAGE_02.md)

## 当前底盘基线

```text
MCU：STM32F407VET6
工程：Keil MDK-ARM + STM32CubeMX
底盘：四轮独立驱动 skid-steer
轮径：0.066404 m
等效轮距：0.3703 m
编码器：1320 计数/圈
PID：1 ms，KP=0.4 / KI=2.5 / KD=0
目标轮速：±250 RPM
硬件极速：约 330 RPM
IMU：维特 10 轴模块，I2C2
```

## Git 标签

```text
stage-01：四轮独立速度 PID
stage-02：运动学、里程计、IMU 与航向闭环
```

## 安全原则

```text
硬件急停优先级最高
上电默认停车
通信超时必须停车
PID 输出和积分必须限幅
发射必须有独立互锁
目标丢失必须禁止发射
```
