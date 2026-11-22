#include "comm_actions.h"
#include "comm_protocol.h"
#include "chassis.h"
#include "imu.h"
#include <math.h>

/* Watch 可观测/可调动作状态变量 */
uint8_t  commActionState = COMM_ACT_STATE_IDLE;
uint8_t  commActionCurrentId = 0U;
int16_t  commActionTargetParam = 0;
uint32_t commActionElapsedMs = 0U;
float    commActionProgress = 0.0f;
uint32_t commActionRampUpMs = COMM_ACTION_RAMP_UP_MS;
float    commActionSlowDownMm = COMM_ACTION_SLOW_DOWN_MM;
float    commActionCrawlMps = COMM_ACTION_CRAWL_MPS;

static float s_start_x = 0.0f;
static float s_start_y = 0.0f;
static float s_start_yaw = 0.0f;
static float s_target_dist_m = 0.0f;

static float Comm_Action_WrapToPi(float angle)
{
    if ((angle - angle) != 0.0f)
    {
        return 0.0f;
    }

    angle = fmodf(angle + COMM_PI, 2.0f * COMM_PI);
    if (angle <= 0.0f)
    {
        angle += 2.0f * COMM_PI;
    }

    return angle - COMM_PI;
}

/*
 * 直行动作梯形速度给定计算（单位 m/s，正值）：
 *   1. 常规距离（target_mm >= 400 mm）：
 *      - 起步阶段：前 commActionRampUpMs (250 ms) 从 0.08 -> 0.25 m/s 线性爬升；
 *      - 巡航阶段：0.25 m/s；
 *      - 末端减速：剩余距离 rem_mm <= commActionSlowDownMm (150 mm) 时，按剩余距离线性降至 commActionCrawlMps (0.07 m/s)；
 *   2. 短距离（target_mm < 400 mm）：
 *      - 防止“还没爬完就该减速”：将峰值速度压低至 0.14 m/s、爬升时间缩短为 100 ms，
 *        减速区间取 min(150 mm, 0.5 * target_mm)，末端同样线性降至 0.07 m/s 蠕行；
 *   3. 最终速度取 min(v_ramp, v_decel)，保证全程速度连续单调、无突变冲击。
 */
static float Comm_Action_ComputeMoveSpeedMps(uint32_t elapsed_ms, float target_mm, float traveled_mm)
{
    float crawl_v = (commActionCrawlMps > 0.03f) ? commActionCrawlMps : COMM_ACTION_CRAWL_MPS;
    float peak_v = COMM_ACTION_MOVE_SPEED_MPS;
    float start_v = COMM_ACTION_START_MPS;
    uint32_t ramp_ms = (commActionRampUpMs > 0U) ? commActionRampUpMs : COMM_ACTION_RAMP_UP_MS;
    float slow_mm = (commActionSlowDownMm > 10.0f) ? commActionSlowDownMm : COMM_ACTION_SLOW_DOWN_MM;

    if (target_mm < COMM_ACTION_SHORT_DIST_MM)
    {
        peak_v = COMM_ACTION_SHORT_PEAK_MPS;
        if (ramp_ms > COMM_ACTION_SHORT_RAMP_MS)
        {
            ramp_ms = COMM_ACTION_SHORT_RAMP_MS;
        }
        if (slow_mm > 0.5f * target_mm)
        {
            slow_mm = 0.5f * target_mm;
        }
        if (slow_mm < 20.0f)
        {
            slow_mm = 20.0f;
        }
    }

    if (start_v > peak_v)
    {
        start_v = peak_v;
    }
    if (crawl_v > peak_v)
    {
        crawl_v = peak_v;
    }

    /* 1. 起步线性爬升上限 v_ramp */
    float v_ramp = peak_v;
    if (elapsed_ms < ramp_ms)
    {
        float ratio = (float)elapsed_ms / (float)ramp_ms;
        v_ramp = start_v + (peak_v - start_v) * ratio;
    }

    /* 2. 末端线性减速上限 v_decel */
    float rem_mm = target_mm - traveled_mm;
    if (rem_mm < 0.0f)
    {
        rem_mm = 0.0f;
    }

    float v_decel = peak_v;
    if (rem_mm <= slow_mm)
    {
        float ratio = rem_mm / slow_mm;
        v_decel = crawl_v + (peak_v - crawl_v) * ratio;
    }

    float v_cmd = (v_ramp < v_decel) ? v_ramp : v_decel;
    if (v_cmd < crawl_v)
    {
        v_cmd = crawl_v;
    }
    return v_cmd;
}

void Comm_Action_Init(void)
{
    commActionState = COMM_ACT_STATE_IDLE;
    commActionCurrentId = 0U;
    commActionTargetParam = 0;
    commActionElapsedMs = 0U;
    commActionProgress = 0.0f;
    commActionRampUpMs = COMM_ACTION_RAMP_UP_MS;
    commActionSlowDownMm = COMM_ACTION_SLOW_DOWN_MM;
    commActionCrawlMps = COMM_ACTION_CRAWL_MPS;
    s_start_x = 0.0f;
    s_start_y = 0.0f;
    s_start_yaw = 0.0f;
    s_target_dist_m = 0.0f;
}

void Comm_Action_Abort(void)
{
    if (commActionState == COMM_ACT_STATE_RUNNING)
    {
        /* 释放动作占用的 mode 1 / mode 2 与速度目标，确保新司机（如 CMD_VEL）立刻接管 */
        Chassis_EnableHeadingHold(0U);
        Chassis_SetVelocity(0.0f, 0.0f);
        commActionState = COMM_ACT_STATE_ABORTED;
    }
    else if (commActionState != COMM_ACT_STATE_ABORTED)
    {
        commActionState = COMM_ACT_STATE_IDLE;
    }
    commActionCurrentId = 0U;
}

void Comm_Action_Start(uint8_t action_id, int16_t param)
{
    /* 启动新动作前先确保旧动作已清理 */
    Comm_Action_Abort();

    switch (action_id)
    {
        case COMM_ACTION_STOP:
        {
            Chassis_ForceStop();
            commActionCurrentId = COMM_ACTION_STOP;
            commActionTargetParam = 0;
            commActionElapsedMs = 0U;
            commActionProgress = 0.0f;
            commActionState = COMM_ACT_STATE_DONE;
            break;
        }

        case COMM_ACTION_RESET_ODOM:
        {
            /* W2：0x06 远程里程计归零（Abort -> ForceStop -> ResetOdometry -> DONE） */
            Chassis_ForceStop();
            Chassis_ResetOdometry();
            s_start_x = 0.0f;
            s_start_y = 0.0f;
            s_start_yaw = 0.0f;
            s_target_dist_m = 0.0f;
            commActionCurrentId = COMM_ACTION_RESET_ODOM;
            commActionTargetParam = 0;
            commActionElapsedMs = 0U;
            commActionProgress = 0.0f;
            commActionState = COMM_ACT_STATE_DONE;
            break;
        }

        case COMM_ACTION_MOVE_MM:
        {
            if (param == 0)
            {
                Chassis_ForceStop();
                commActionCurrentId = COMM_ACTION_MOVE_MM;
                commActionTargetParam = 0;
                commActionElapsedMs = 0U;
                commActionProgress = 0.0f;
                commActionState = COMM_ACT_STATE_DONE;
                return;
            }

            s_start_x = chassisX;
            s_start_y = chassisY;
            s_start_yaw = chassisYaw;
            float target_mm = (param > 0) ? (float)param : -(float)param;
            s_target_dist_m = target_mm / 1000.0f;

            float v0 = Comm_Action_ComputeMoveSpeedMps(0U, target_mm, 0.0f);
            float vx = (param > 0) ? v0 : -v0;
            Chassis_EnableHeadingHold(1U);
            Chassis_SetVelocity(vx, 0.0f);

            commActionCurrentId = COMM_ACTION_MOVE_MM;
            commActionTargetParam = param;
            commActionElapsedMs = 0U;
            commActionProgress = 0.0f;
            commActionState = COMM_ACT_STATE_RUNNING;
            break;
        }

        case COMM_ACTION_TURN_01D:
        case COMM_ACTION_UTURN_180:
        {
            int16_t eff_param = (action_id == COMM_ACTION_UTURN_180) ? (int16_t)1800 : param;
            if (eff_param == 0)
            {
                Chassis_ForceStop();
                commActionCurrentId = action_id;
                commActionTargetParam = 0;
                commActionElapsedMs = 0U;
                commActionProgress = 0.0f;
                commActionState = COMM_ACT_STATE_DONE;
                return;
            }

            if (IMU_IsAvailable() == 0U)
            {
                /* mode 2 定点转向依赖 IMU，掉线时拒绝盲转并安全停车 */
                Chassis_ForceStop();
                commActionState = COMM_ACT_STATE_ABORTED;
                return;
            }

            s_start_yaw = IMU_GetYaw();
            /* 180° 掉头取 +179.91° (3.140 rad) 避免 ±pi 边界随机方向翻转，落在 0.46° 容差带中心 */
            float delta_rad = (action_id == COMM_ACTION_UTURN_180)
                                  ? 3.140f
                                  : ((float)eff_param * 0.1f * COMM_DEG_TO_RAD);
            if (delta_rad > 3.140f)
            {
                delta_rad = 3.140f;
            }
            else if (delta_rad < -3.140f)
            {
                delta_rad = -3.140f;
            }

            float target_yaw = Comm_Action_WrapToPi(s_start_yaw + delta_rad);
            Chassis_SetHeadingTarget(target_yaw);

            commActionCurrentId = action_id;
            commActionTargetParam = eff_param;
            commActionElapsedMs = 0U;
            commActionProgress = 0.0f;
            commActionState = COMM_ACT_STATE_RUNNING;
            break;
        }

        /* 0x05 回起点（RETURN_ORIGIN）第一版不做，保持预留位 */
        default:
        {
            Chassis_ForceStop();
            commActionState = COMM_ACT_STATE_ABORTED;
            break;
        }
    }
}

void Comm_Action_Update1ms(void)
{
    if (commActionState != COMM_ACT_STATE_RUNNING)
    {
        return;
    }

    commActionElapsedMs++;

    /* 1. 动作自身 10 s 硬超时保护 */
    if (commActionElapsedMs >= COMM_ACTION_TIMEOUT_MS)
    {
        Chassis_ForceStop();
        commActionState = COMM_ACT_STATE_TIMEOUT;
        return;
    }

    /* 2. 分动作到位检查与梯形速度实时给定 */
    if (commActionCurrentId == COMM_ACTION_MOVE_MM)
    {
        /* 0° 朝向时等价于 |chassisX - s_start_x| >= target/1000，任意朝向下按二维欧氏位移判断 */
        float dx = chassisX - s_start_x;
        float dy = chassisY - s_start_y;
        float dist_m = sqrtf(dx * dx + dy * dy);
        float traveled_mm = dist_m * 1000.0f;
        float target_mm = s_target_dist_m * 1000.0f;
        commActionProgress = traveled_mm;

        if (dist_m >= s_target_dist_m)
        {
            Chassis_ForceStop();
            commActionState = COMM_ACT_STATE_DONE;
        }
        else
        {
            float v_mag = Comm_Action_ComputeMoveSpeedMps(commActionElapsedMs, target_mm, traveled_mm);
            float vx = (commActionTargetParam > 0) ? v_mag : -v_mag;
            Chassis_SetVelocity(vx, 0.0f);
        }
    }
    else if ((commActionCurrentId == COMM_ACTION_TURN_01D) ||
             (commActionCurrentId == COMM_ACTION_UTURN_180))
    {
        float cur_yaw = (IMU_IsAvailable() != 0U) ? IMU_GetYaw() : chassisYaw;
        commActionProgress = Comm_Action_WrapToPi(cur_yaw - s_start_yaw) * (180.0f / COMM_PI);

        if (chassisHeadingReached != 0U)
        {
            uint8_t timed_out = chassisHeadingTimedOut;
            Chassis_ForceStop();
            commActionState = (timed_out != 0U) ? COMM_ACT_STATE_TIMEOUT : COMM_ACT_STATE_DONE;
        }
    }
    else
    {
        Chassis_ForceStop();
        commActionState = COMM_ACT_STATE_ABORTED;
    }
}
