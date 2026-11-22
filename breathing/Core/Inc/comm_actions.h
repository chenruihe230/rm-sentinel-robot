#ifndef __COMM_ACTIONS_H
#define __COMM_ACTIONS_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * 阶段 3（S3-DEMO v2 / v3）车端闭环参数化动作状态机头文件
 *
 * 1. 动作列表（TYPE 0x05 CMD_ACTION，DATA = action_id(1B) + param(int16 LE)）：
 *    - 0x01 COMM_ACTION_MOVE_MM    ：直线前进/后退（param 单位 mm，正=前进，负=后退）
 *                                    复用 mode 1（Chassis_EnableHeadingHold(1)）保持直线航向，
 *                                    v3 升级为梯形速度曲线（250ms 爬升 0.08->0.25 m/s，末端 150mm 降至 0.07 m/s 蠕行）；
 *    - 0x02 COMM_ACTION_TURN_01D   ：原地左转/右转（param 单位 0.1°，正=逆时针左转，负=顺时针右转）
 *                                    复用 mode 2（Chassis_SetHeadingTarget）定点闭环转向；
 *    - 0x03 COMM_ACTION_STOP       ：立即停车（中止当前动作并调用 Chassis_ForceStop()）；
 *    - 0x04 COMM_ACTION_UTURN_180  ：原地掉头 180°（复用 mode 2 转 +180°）；
 *    - 0x05 COMM_ACTION_HOME_RSVD  ：回起点第一版不做，保持预留位不动；
 *    - 0x06 COMM_ACTION_RESET_ODOM ：远程里程计归零（Abort -> ForceStop -> Chassis_ResetOdometry -> DONE）。
 *
 * 2. 单一司机规则（防状态竞争）：
 *    - 除 CMD_POLL 外，任何新指令（CMD_STOP / CMD_VEL / CMD_MODE / CMD_ACTION）到达时，
 *      以及 400 ms 通信超时或 Chassis_ForceStop() 触发时，统一先调用 Comm_Action_Abort() 清空当前动作；
 *    - 每个动作自身带 10 s（10000 ms）硬超时保护，超时自动调用 Chassis_ForceStop() 停车并置 TIMEOUT 状态。
 */

#include <stdint.h>

/* 动作 ID 定义（均封装在 TYPE 0x05 CMD_ACTION 的 DATA[0] 中，不新增 TYPE） */
#define COMM_ACTION_MOVE_MM          0x01U
#define COMM_ACTION_TURN_01D         0x02U
#define COMM_ACTION_STOP             0x03U
#define COMM_ACTION_UTURN_180        0x04U
/* 0x05 回起点（RETURN_ORIGIN）第一版不做，保持预留位 */
#define COMM_ACTION_RESET_ODOM       0x06U

/* 动作控制与梯形速度规划参数（仅作用于 0x01 直行动作，不影响手动 CMD_VEL） */
#define COMM_ACTION_START_MPS        0.08f
#define COMM_ACTION_MOVE_SPEED_MPS   0.25f
#define COMM_ACTION_CRAWL_MPS        0.07f
#define COMM_ACTION_RAMP_UP_MS       250U
#define COMM_ACTION_SLOW_DOWN_MM     150.0f
#define COMM_ACTION_SHORT_DIST_MM    400.0f
#define COMM_ACTION_SHORT_PEAK_MPS   0.14f
#define COMM_ACTION_SHORT_RAMP_MS    100U
#define COMM_ACTION_TIMEOUT_MS       10000U

/* 动作状态枚举 */
#define COMM_ACT_STATE_IDLE          0U
#define COMM_ACT_STATE_RUNNING       1U
#define COMM_ACT_STATE_DONE          2U
#define COMM_ACT_STATE_TIMEOUT       3U
#define COMM_ACT_STATE_ABORTED       4U

/* Watch 可观测/可调动作状态变量 */
extern uint8_t  commActionState;
extern uint8_t  commActionCurrentId;
extern int16_t  commActionTargetParam;
extern uint32_t commActionElapsedMs;
extern float    commActionProgress;
extern uint32_t commActionRampUpMs;
extern float    commActionSlowDownMm;
extern float    commActionCrawlMps;

void Comm_Action_Init(void);
void Comm_Action_Start(uint8_t action_id, int16_t param);
void Comm_Action_Abort(void);
void Comm_Action_Update1ms(void);

#ifdef __cplusplus
}
#endif

#endif /* __COMM_ACTIONS_H */
