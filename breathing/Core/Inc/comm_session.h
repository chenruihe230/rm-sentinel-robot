#ifndef __COMM_SESSION_H
#define __COMM_SESSION_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * 阶段 3（S3-02 / S3-03B）半双工主从通信会话与 400 ms 超时强制停车头文件
 *
 * 1. 半双工主从约定：
 *    - 电脑主机（50 ms / 20 Hz）发起请求，STM32 从机不主动发送，仅在收到有效帧后回一帧 TELEMETRY；
 *    - 响应帧原样复制请求帧 SEQ。
 *
 * 2. 序号 / 丢帧 / 重发规则（uint8，255 -> 0 为正常回绕）：
 *    - delta = (uint8_t)(rx.seq - lastSeq) == 1：正常递增；
 *    - delta == 0：重复序号（重发）—— CMD_STOP 仍必须执行，其余命令不重复改控制状态，仅回缓存遥测；
 *    - delta > 1：发生跳变，commDropCount += (delta - 1)。
 *
 * 3. 超时保护（400 ms）：
 *    - 在 1 ms 控制环中读取 HAL_GetTick() 与 last_frame_tick 做数值比较（禁止任何等待循环）；
 *    - 若曾建立通信且 (now - last_frame_tick) > 400 ms：调用 Chassis_ForceStop() 并累加 commTimeoutCount。
 */

#include <stdint.h>

#define COMM_SESSION_TIMEOUT_MS  400U

/* Watch 可观测通信状态变量 */
extern uint16_t commDropCount;
extern uint16_t commTimeoutCount;
extern uint8_t  commLastSeq;
extern uint8_t  commLinkActive;
extern uint8_t  commTimedOutFlag;

void Comm_Session_Init(void);
void Comm_Session_Update1ms(void);

#ifdef __cplusplus
}
#endif

#endif /* __COMM_SESSION_H */
