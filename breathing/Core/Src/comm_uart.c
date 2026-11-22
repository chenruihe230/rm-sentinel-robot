#include "comm_uart.h"
#include "usart.h"
#include <stddef.h>

static uint8_t s_rx_byte = 0U;
static uint8_t s_rx_ring[COMM_UART_RX_RING_SIZE];
static volatile uint16_t s_ring_head = 0U;
static volatile uint16_t s_ring_tail = 0U;

static Comm_Frame_t s_pending_frame;
static volatile uint8_t  s_pending_valid = 0U;
static volatile uint32_t s_last_frame_tick = 0U;
static volatile uint32_t s_rx_error_count = 0U;
static volatile uint32_t s_rx_byte_count = 0U;
static volatile uint8_t  s_last_rx_byte = 0U;

static uint8_t s_tx_buf[COMM_FRAME_MAX_LEN];

static uint16_t Comm_RingCount(void)
{
    uint16_t head = s_ring_head;
    uint16_t tail = s_ring_tail;

    if (head >= tail)
    {
        return (uint16_t)(head - tail);
    }

    return (uint16_t)(COMM_UART_RX_RING_SIZE - tail + head);
}

static uint8_t Comm_RingPeek(uint16_t offset)
{
    uint16_t idx = (uint16_t)((s_ring_tail + offset) % COMM_UART_RX_RING_SIZE);
    return s_rx_ring[idx];
}

static void Comm_RingDrop(uint16_t count)
{
    uint16_t avail = Comm_RingCount();
    if (count > avail)
    {
        count = avail;
    }

    s_ring_tail = (uint16_t)((s_ring_tail + count) % COMM_UART_RX_RING_SIZE);
}

static void Comm_RingPush(uint8_t byte)
{
    uint16_t next_head = (uint16_t)((s_ring_head + 1U) % COMM_UART_RX_RING_SIZE);
    if (next_head == s_ring_tail)
    {
        /* 缓冲满时丢弃最旧字节，保证实时新数据不断写入 */
        s_ring_tail = (uint16_t)((s_ring_tail + 1U) % COMM_UART_RX_RING_SIZE);
    }

    s_rx_ring[s_ring_head] = byte;
    s_ring_head = next_head;
}

static void Comm_TryParseFromRingISR(void)
{
    uint8_t frame_buf[COMM_FRAME_MAX_LEN];
    Comm_Frame_t parsed;

    while (Comm_RingCount() >= COMM_FRAME_MIN_LEN)
    {
        if (Comm_RingPeek(0U) != COMM_FRAME_HEADER_0)
        {
            Comm_RingDrop(1U);
            continue;
        }

        if (Comm_RingPeek(1U) != COMM_FRAME_HEADER_1)
        {
            Comm_RingDrop(1U);
            continue;
        }

        int32_t expected_data_len = Comm_GetExpectedDataLen(Comm_RingPeek(2U));
        if (expected_data_len < 0)
        {
            /* 未知 TYPE，丢掉当前假帧头 0xAA 继续向后重同步 */
            Comm_RingDrop(1U);
            continue;
        }

        uint16_t frame_len = (uint16_t)(COMM_FRAME_OVERHEAD_BYTES + (uint32_t)expected_data_len);
        if (Comm_RingCount() < frame_len)
        {
            /* 帧尚未收齐，等待后续字节 */
            break;
        }

        for (uint16_t i = 0U; i < frame_len; i++)
        {
            frame_buf[i] = Comm_RingPeek(i);
        }

        /* 在中断中完成完整协议校验（头/尾/长度/CRC8） */
        if (Comm_ParseFrame(frame_buf, (uint32_t)frame_len, &parsed) == COMM_PARSE_OK)
        {
            Comm_RingDrop(frame_len);
            s_pending_frame = parsed;
            s_pending_valid = 1U;
            s_last_frame_tick = HAL_GetTick();
        }
        else
        {
            /* CRC 或帧尾失败，推进 1 字节继续寻找真帧头 */
            Comm_RingDrop(1U);
        }
    }
}

void Comm_Uart_Init(void)
{
    s_ring_head = 0U;
    s_ring_tail = 0U;
    s_pending_valid = 0U;
    s_last_frame_tick = HAL_GetTick();
    s_rx_error_count = 0U;

    (void)HAL_UART_Receive_IT(&huart1, &s_rx_byte, 1U);
}

void Comm_Uart_EnsureRxArmed(void)
{
    if (huart1.RxState == HAL_UART_STATE_READY)
    {
        (void)HAL_UART_Receive_IT(&huart1, &s_rx_byte, 1U);
    }
}

uint8_t Comm_Uart_PopFrame(Comm_Frame_t *out_frame, uint32_t *out_frame_tick)
{
    uint32_t primask = __get_PRIMASK();
    uint8_t has_frame = 0U;

    __disable_irq();
    if (s_pending_valid != 0U)
    {
        if (out_frame != NULL)
        {
            *out_frame = s_pending_frame;
        }
        if (out_frame_tick != NULL)
        {
            *out_frame_tick = s_last_frame_tick;
        }
        s_pending_valid = 0U;
        has_frame = 1U;
    }
    if (primask == 0U)
    {
        __enable_irq();
    }

    return has_frame;
}

uint8_t Comm_Uart_SendFrame(const uint8_t *buf, uint32_t len)
{
    if ((buf == NULL) || (len == 0U) || (len > COMM_FRAME_MAX_LEN))
    {
        return 0U;
    }

    if (huart1.gState != HAL_UART_STATE_READY)
    {
        return 0U;
    }

    for (uint32_t i = 0U; i < len; i++)
    {
        s_tx_buf[i] = buf[i];
    }

    return (HAL_UART_Transmit_IT(&huart1, s_tx_buf, (uint16_t)len) == HAL_OK) ? 1U : 0U;
}

uint32_t Comm_Uart_GetLastFrameTick(void)
{
    return s_last_frame_tick;
}

uint32_t Comm_Uart_GetRxErrorCount(void)
{
    return s_rx_error_count;
}

uint32_t Comm_Uart_GetRxByteCount(void)
{
    return s_rx_byte_count;
}

uint8_t Comm_Uart_GetLastRxByte(void)
{
    return s_last_rx_byte;
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        uint8_t rx = s_rx_byte;
        s_rx_byte_count++;
        s_last_rx_byte = rx;
        /* 优先重新开启单字节接收，避免高波特或连续帧漏字节 */
        (void)HAL_UART_Receive_IT(&huart1, &s_rx_byte, 1U);

        Comm_RingPush(rx);
        Comm_TryParseFromRingISR();
    }
}

void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1)
    {
        s_rx_error_count++;
        __HAL_UART_CLEAR_OREFLAG(huart);
        (void)HAL_UART_Receive_IT(&huart1, &s_rx_byte, 1U);
    }
}
