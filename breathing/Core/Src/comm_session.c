#include "comm_session.h"
#include "comm_actions.h"
#include "comm_uart.h"
#include "comm_protocol.h"
#include "chassis.h"
#include "control.h"
#include "imu.h"
#include "main.h"

/* Watch 可观测通信状态变量 */
uint16_t commDropCount = 0U;
uint16_t commTimeoutCount = 0U;
uint8_t  commLastSeq = 0U;
uint8_t  commLinkActive = 0U;
uint8_t  commTimedOutFlag = 0U;

static uint8_t  s_has_seq = 0U;
static uint8_t  s_cached_tlm_payload[COMM_LEN_TELEMETRY];
static uint8_t  s_has_cached_tlm = 0U;

static int16_t Comm_RoundClampI16(float val)
{
    if ((val - val) != 0.0f)
    {
        return 0;
    }

    if (val >= 32767.0f)
    {
        return 32767;
    }
    if (val <= -32768.0f)
    {
        return -32768;
    }

    return (val >= 0.0f) ? (int16_t)(val + 0.5f) : (int16_t)(val - 0.5f);
}

static int8_t Comm_ClampPwmI8(int16_t pwm_pct)
{
    if (pwm_pct > 100)
    {
        return 100;
    }
    if (pwm_pct < -100)
    {
        return -100;
    }
    return (int8_t)pwm_pct;
}

static void Comm_BuildLiveTelemetryPayload(uint8_t *out_payload)
{
    Comm_Telemetry_t tlm;
    float odom_deg = chassisYaw * (180.0f / COMM_PI);
    float imu_deg  = (IMU_IsAvailable() != 0U) ? (IMU_GetYaw() * (180.0f / COMM_PI)) : 0.0f;

    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        tlm.rpm[i] = Comm_RoundClampI16(Control_GetSpeedRpm(i));
        tlm.pwm[i] = Comm_ClampPwmI8(Control_GetOutputPercent(i));
    }

    tlm.x_mm            = Comm_RoundClampI16(chassisX * COMM_POS_MM_PER_M);
    tlm.y_mm            = Comm_RoundClampI16(chassisY * COMM_POS_MM_PER_M);
    tlm.odom_yaw_001deg = Comm_RoundClampI16(odom_deg * 100.0f);
    tlm.imu_yaw_001deg  = Comm_RoundClampI16(imu_deg * 100.0f);

    tlm.status = (uint8_t)(((IMU_IsAvailable() != 0U) ? 0x01U : 0x00U) |
                           ((commTimedOutFlag != 0U) ? 0x02U : 0x00U) |
                           ((chassisHeadingMode != 0U) ? 0x04U : 0x00U) |
                           ((chassisCmdRejected != 0U) ? 0x08U : 0x00U) |
                           ((commActionState == COMM_ACT_STATE_RUNNING) ? 0x10U : 0x00U) |
                           ((commActionState == COMM_ACT_STATE_DONE) ? 0x20U : 0x00U) |
                           ((commActionState == COMM_ACT_STATE_TIMEOUT) ? 0x40U : 0x00U));
    tlm.fusion_mode   = chassisYawFusionMode;
    tlm.drop_count    = commDropCount;
    tlm.timeout_count = commTimeoutCount;

    (void)Comm_PackTelemetry(out_payload, &tlm);
}

static void Comm_ExecuteCommand(const Comm_Frame_t *rx, uint8_t is_dup)
{
    if (rx->type == COMM_TYPE_CMD_STOP)
    {
        /* 重复序号下 CMD_STOP 仍必须执行，安全优先（ForceStop 内含 Comm_Action_Abort） */
        Comm_Action_Abort();
        Chassis_ForceStop();
        return;
    }

    if (is_dup != 0U)
    {
        /* 非 CMD_STOP 的重复帧不重复改写控制状态 */
        return;
    }

    /* ★ 单一司机规则：除纯查询 CMD_POLL 外，任何新指令到达先在入口统一 Abort 当前动作 */
    if (rx->type != COMM_TYPE_CMD_POLL)
    {
        Comm_Action_Abort();
    }

    switch (rx->type)
    {
        case COMM_TYPE_CMD_POLL:
            break;

        case COMM_TYPE_CMD_VEL:
        {
            Comm_CmdVel_t cmd_vel;
            if (Comm_UnpackCmdVel(rx->data, rx->data_len, &cmd_vel) != 0U)
            {
                float vx_mps = (float)cmd_vel.vx_mmps / COMM_VEL_MMPS_PER_MPS;
                float omega_rads = (float)cmd_vel.omega_mradps / COMM_OMEGA_MRADPS_PER_RADS;
                Chassis_SetVelocity(vx_mps, omega_rads);
            }
            break;
        }

        case COMM_TYPE_CMD_MODE:
        {
            Comm_CmdMode_t cmd_mode;
            if (Comm_UnpackCmdMode(rx->data, rx->data_len, &cmd_mode) != 0U)
            {
                /* S3-02 约定：CMD_MODE 只写 chassisYawFusionMode(0/1)，绝不碰 chassisHeadingMode */
                chassisYawFusionMode = (cmd_mode.fusion_mode != 0U) ? 1U : 0U;
            }
            break;
        }

        case COMM_TYPE_CMD_ACTION:
        {
            Comm_CmdAction_t cmd_act;
            if (Comm_UnpackCmdAction(rx->data, rx->data_len, &cmd_act) != 0U)
            {
                Comm_Action_Start(cmd_act.action_id, cmd_act.param);
            }
            break;
        }

        default:
            break;
    }
}

void Comm_Session_Init(void)
{
    commDropCount = 0U;
    commTimeoutCount = 0U;
    commLastSeq = 0U;
    commLinkActive = 0U;
    commTimedOutFlag = 0U;
    s_has_seq = 0U;
    s_has_cached_tlm = 0U;

    Comm_Action_Init();
    Comm_Uart_Init();
}

void Comm_Session_Update1ms(void)
{
    Comm_Frame_t rx;
    uint32_t frame_tick = 0U;
    uint32_t now_tick = 0U;
    uint32_t last_tick = 0U;

    Comm_Uart_EnsureRxArmed();

    /* 1. 取走中断里已校验通过的待处理帧并执行 */
    if (Comm_Uart_PopFrame(&rx, &frame_tick) != 0U)
    {
        uint8_t is_dup = 0U;

        commLinkActive = 1U;
        commTimedOutFlag = 0U;

        if (s_has_seq == 0U)
        {
            s_has_seq = 1U;
            commLastSeq = rx.seq;
        }
        else
        {
            uint8_t delta = (uint8_t)(rx.seq - commLastSeq);
            if (delta == 0U)
            {
                is_dup = 1U;
            }
            else
            {
                if (delta > 1U)
                {
                    uint16_t missed = (uint16_t)(delta - 1U);
                    if ((uint32_t)commDropCount + (uint32_t)missed > 65535U)
                    {
                        commDropCount = 65535U;
                    }
                    else
                    {
                        commDropCount = (uint16_t)(commDropCount + missed);
                    }
                }
                commLastSeq = rx.seq;
            }
        }

        Comm_ExecuteCommand(&rx, is_dup);

        /*
         * 半双工主从应答：收到一帧有效命令后回一帧 TELEMETRY（原样复制请求 SEQ）；
         * 重复非 STOP 帧优先返回上次缓存的 26B 遥测载荷。
         */
        if ((is_dup == 0U) || (rx.type == COMM_TYPE_CMD_STOP) || (s_has_cached_tlm == 0U))
        {
            Comm_BuildLiveTelemetryPayload(s_cached_tlm_payload);
            s_has_cached_tlm = 1U;
        }

        uint8_t tx_frame[COMM_FRAME_MAX_LEN];
        uint32_t tx_len = Comm_BuildFrame(tx_frame,
                                          COMM_TYPE_TELEMETRY,
                                          rx.seq,
                                          s_cached_tlm_payload,
                                          COMM_LEN_TELEMETRY);
        if (tx_len > 0U)
        {
            (void)Comm_Uart_SendFrame(tx_frame, tx_len);
        }
    }

    /*
     * 2. 400 ms 超时强制停车检查（仅对 HAL_GetTick 做关中断原子快照与数值比较，绝不忙等）
     */
    if (commLinkActive != 0U)
    {
        uint32_t primask = __get_PRIMASK();
        __disable_irq();
        now_tick = HAL_GetTick();
        last_tick = Comm_Uart_GetLastFrameTick();
        if (primask == 0U)
        {
            __enable_irq();
        }

        if ((uint32_t)(now_tick - last_tick) > COMM_SESSION_TIMEOUT_MS)
        {
            if (commTimedOutFlag == 0U)
            {
                commTimedOutFlag = 1U;
                if (commTimeoutCount < 65535U)
                {
                    commTimeoutCount++;
                }
                Chassis_ForceStop();
            }
        }
    }
}
