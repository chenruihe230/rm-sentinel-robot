#ifndef __COMM_UART_H
#define __COMM_UART_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * 阶段 3（S3-02）USART1 中断收发与帧同步层头文件（HC-12 无线串口）
 *
 * 1. 分工原则：
 *    - 中断内（HAL_UART_RxCpltCallback）：单字节进环形缓冲 + 帧边界对齐 + 调 Comm_ParseFrame() 解析；
 *      若通过 CRC8 与长度校验，锁存为待处理帧并记录 HAL_GetTick() 到 last_frame_tick；
 *    - 控制环内（Comm_Uart_PopFrame）：原子取出待处理帧在 1 ms 控制环中执行；
 *    - 发送（Comm_Uart_SendFrame）：基于 HAL_UART_Transmit_IT 非阻塞发送，绝不阻塞 SysTick。
 *
 * 2. 中断优先级说明：
 *    - USART1_IRQn 在 CubeMX NVIC 中设为 Preemption Priority = 5（SysTick = 15），
 *      单字节中断服务仅做环形缓冲写入与短帧校验（微秒级，无等待循环），绝不会饿死 SysTick。
 */

#include <stdint.h>
#include "comm_protocol.h"

#define COMM_UART_RX_RING_SIZE  128U

void     Comm_Uart_Init(void);
uint8_t  Comm_Uart_PopFrame(Comm_Frame_t *out_frame, uint32_t *out_frame_tick);
uint8_t  Comm_Uart_SendFrame(const uint8_t *buf, uint32_t len);
uint32_t Comm_Uart_GetLastFrameTick(void);
uint32_t Comm_Uart_GetRxErrorCount(void);
uint32_t Comm_Uart_GetRxByteCount(void);
uint8_t  Comm_Uart_GetLastRxByte(void);
void     Comm_Uart_EnsureRxArmed(void);

#ifdef __cplusplus
}
#endif

#endif /* __COMM_UART_H */
