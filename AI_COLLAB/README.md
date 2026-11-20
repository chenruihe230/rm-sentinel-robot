# 协作文档索引 (AI_COLLAB)

> 这里是所有**协作过程文档**的统一位置。工程源码与正式文档仍在 Keil 工程目录，不要混放。
> 维护：WorkBuddy ｜ 建立：2026-11-20 ｜ 项目：RM 哨兵机器人四轮底盘

---

## 1. 目录约定

```text
项目根目录：D:\stm32\stm32f4\breath
Keil 工程目录：D:\stm32\stm32f4\breath\breathing
协作文档目录：D:\stm32\stm32f4\breath\AI_COLLAB  ← 本目录
```

## 2. 本目录结构

```text
AI_COLLAB\
├── README.md                          ← 本文件：索引与阅读顺序
├── BRIEF_FOR_CODEX.md                 ← Codex 决策速览卡（阶段末只读这一张）
├── AI_SYNC.md                         ← 所有 AI 共用的状态同步板（第一入口）
├── AI_WORKLOG_WORKBUDDY.md            ← WorkBuddy 自己的工作流水
├── CHANGELOG.md                       ← 代码/文档改动历史（追加式）
├── DISPATCHES\                        ← 派单（按阶段分目录）
│   └── STAGE_01\
│       ├── DISPATCH_01_ENCODER.md     ← 编码器测速夯实 + 里程计
│       ├── DISPATCH_02_PID_1MS.md     ← 1 ms 速度 PID（方案 A）
│       └── DISPATCH_03_TUNE_AND_TEST.md ← 开环标定 + KP/KI 整定 + 阶跃验收
└── ACCEPTANCE\
    └── STAGE_01.md                    ← 阶段 1 验收记录
```

**阶段 2 开始后**：派单放 `DISPATCHES\STAGE_02\`，验收记录放 `ACCEPTANCE\STAGE_02.md`，依此类推。

**不在本目录的正式文档**（归 Codex 接 MiMo 维护）：

```text
breathing\docs\PROJECT_OVERVIEW.md     架构 / 阶段计划 / AI 分工 / 安全底线
breathing\docs\TASK_STAGE_01_PID.md    阶段 1 任务单
```

## 3. 新加入的 AI：从这里开始

```text
1. README.md（本文件）—— 搞清目录约定和分工
2. BRIEF_FOR_CODEX.md —— 若你是阶段末的 Codex，只读这一张即可决策（~60 行）
3. AI_SYNC.md —— 日常主力读 §3 协作流程 → §2 状态快照 → §4 文件锁 → §6 广播 → §7 待裁决
4. CHANGELOG.md —— 只看最后 2～3 个日期段，别读全文
5. breathing\docs\PROJECT_OVERVIEW.md 与当前阶段任务单
6. 若领派单：DISPATCHES\STAGE_xx\ 下对应派单全文
7. 再打开 Keil 工程里的实际源码
```

**省 token 原则**：每个文档末尾都给了「细节指针」，先读摘要/速览，需要时按指针跳到具体章节，**不要默认全文通读**。


## 4. 各文件职责（不重叠）

| 文件 | 写什么 | 谁能写 |
|---|---|---|
| `AI_SYNC.md` | **公共状态**：当前快照、文件锁、待办、广播、存疑 | §2 仅 WorkBuddy；其余按文件内 §0 规则 |
| `AI_WORKLOG_WORKBUDDY.md` | WorkBuddy 个人工作流水、判断、待办、交接 | 仅 WorkBuddy |
| `CHANGELOG.md` | 每次代码/文档改动的追加记录（日期+改了什么+涉及文件+是否动 CubeMX） | 产生改动的人追加 |
| `DISPATCHES\STAGE_xx\*.md` | 单张派单全文：目标、允许/禁止文件、当前状态、安全、验收、回传 | 仅 WorkBuddy 出派单 |
| `ACCEPTANCE\STAGE_xx.md` | 阶段验收记录：任务单对照、实测数据、遗留、移交结论 | WorkBuddy 整理，人类确认数据 |

**红线**：同一文件同一时间只能一个模型改；任务与报错一律从 WorkBuddy 起手；实车结论由人类确认。
