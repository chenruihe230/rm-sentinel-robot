#include "chassis.h"
#include "control.h"
#include "encoder.h"
#include <math.h>
#include <stddef.h>

#define CHASSIS_PI               3.14159265f
#define CHASSIS_TWO_PI           (2.0f * CHASSIS_PI)
#define CHASSIS_ODOM_LPF_ALPHA      0.15f  /* 观测速度轻度低通系数（0.1~0.2），仅用于 Watch 观察 */
#define CHASSIS_ODOM_ZERO_MS        20U    /* 连续 20 ms 无位移则将观测速度归零，避免残留拖尾 */
#define CHASSIS_IMU_POLL_DIV        10U    /* 1 ms 控制环内 10 ms 分频读一次 IMU（100 Hz） */
#define CHASSIS_DEFAULT_TRACK_M     0.3703f /* S2-05 实测 3 次均值等效轮距（m） */
#define CHASSIS_DEFAULT_WHEEL_SCALE 1.015f  /* S2-05 实测 2 m 里程比例补偿 */
#define CHASSIS_HEADING_TOL_RAD          0.008f  /* 定点转向到达容差（约 0.46°） */
#define CHASSIS_HEADING_SETTLE_MS        150U    /* 连续满足容差 150 ms 判定到达 */
#define CHASSIS_HEADING_LOW_BAND_RAD     0.10f   /* 低速分段阈值（约 5.7°） */
#define CHASSIS_HEADING_OVERSHOOT_RAD    0.05f   /* 过冲主动反向阈值（约 2.86°） */
#define CHASSIS_HEADING_DEFAULT_KP       1.0f    /* 航向环默认 Kp */
#define CHASSIS_HEADING_DEFAULT_MIN_W    0.06f   /* 定点转向低速段默认保底角速度（rad/s） */
#define CHASSIS_HEADING_DEFAULT_MAX_W    1.0f    /* 航向环默认角速度限幅（rad/s） */
#define CHASSIS_HEADING_DEFAULT_TIMEOUT  8000U   /* 定点转向默认最大超时（ms） */

/* 全局状态与标定参数 */
float chassisTrackWidthM = CHASSIS_DEFAULT_TRACK_M;
float motorGain[MOTOR_COUNT] = { 1.0f, 1.0f, 1.0f, 1.0f };
float wheelScale[MOTOR_COUNT] = { CHASSIS_DEFAULT_WHEEL_SCALE, CHASSIS_DEFAULT_WHEEL_SCALE,
                                  CHASSIS_DEFAULT_WHEEL_SCALE, CHASSIS_DEFAULT_WHEEL_SCALE };
float chassisX = 0.0f;
float chassisY = 0.0f;
float chassisYaw = 0.0f;
float chassisOdomVx = 0.0f;
float chassisOdomOmega = 0.0f;
float chassisOdomDistLeft = 0.0f;
float chassisOdomDistRight = 0.0f;
float chassisTargetVx = 0.0f;
float chassisTargetOmega = 0.0f;
uint8_t chassisCmdRejected = 0U;
uint8_t chassisYawFusionMode = 1U;
uint8_t chassisHeadingMode = 0U;
float chassisHeadingTargetRad = 0.0f;
float chassisHeadingErrRad = 0.0f;
float chassisHeadingKp = CHASSIS_HEADING_DEFAULT_KP;
float chassisHeadingMinOmega = CHASSIS_HEADING_DEFAULT_MIN_W;
float chassisHeadingMaxOmega = CHASSIS_HEADING_DEFAULT_MAX_W;
uint32_t chassisHeadingTimeoutMs = CHASSIS_HEADING_DEFAULT_TIMEOUT;
uint8_t chassisHeadingReached = 0U;
uint8_t chassisHeadingTimedOut = 0U;

static float prevDistance[MOTOR_COUNT] = { 0.0f, 0.0f, 0.0f, 0.0f };
static uint32_t odomZeroStreak = 0U;
static uint8_t imuPollDivider = 0U;
static uint8_t prevImuAvailable = 0U;
static float headingHoldBase = 0.0f;
static uint8_t prevHeadingMode = 0U;
static uint32_t headingSettleMs = 0U;
static uint32_t headingTurnElapsedMs = 0U;
static float prevHeadingErrRad = 0.0f;
static uint8_t prevHeadingErrValid = 0U;

static float Chassis_WrapToPi(float angle)
{
    /* NaN / Inf 防护，避免 1 ms 中断异常 */
    if ((angle - angle) != 0.0f)
    {
        return 0.0f;
    }

    angle = fmodf(angle + CHASSIS_PI, CHASSIS_TWO_PI);
    if (angle <= 0.0f)
    {
        angle += CHASSIS_TWO_PI;
    }

    return angle - CHASSIS_PI;
}

static void Chassis_UpdateOdometry(float dt, float track)
{
    float d[MOTOR_COUNT];

    /* 1. 仅用四轮累计距离差分并乘各自 wheelScale[]（禁止使用 speed_rpm 积分） */
    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        float cur_dist = Control_GetDistanceM(i);
        d[i] = wheelScale[i] * (cur_dist - prevDistance[i]);
        prevDistance[i] = cur_dist;
    }

    /* 2. 左右侧均值位移（M1/M3 左、M2/M4 右）与整车线位移、角位移 */
    float d_left   = 0.5f * (d[0] + d[2]);
    float d_right  = 0.5f * (d[1] + d[3]);
    float ds       = 0.5f * (d_left + d_right);
    chassisOdomDistLeft  += d_left;
    chassisOdomDistRight += d_right;
    float dtheta   = 0.0f;
    float prev_yaw = chassisYaw;

    /*
     * 3. 航向与位置积分（S2-04 核心融合）：
     *    - IMU 在线恢复时自动开启融合模式（1）；IMU 不可用时自动回退到 0（纯编码器）；
     *    - 融合模式（1）且 IMU 可用：chassisYaw 直接取 IMU 相对角，位置 (x, y) 用编码器 ds
     *      搭配 IMU 中点航向角积分，避免编码器打滑造成航向与轨迹割裂；
     *    - 纯编码器模式（0）或 IMU 不可用：回退 S2-03 纯编码器差速积分。
     */
    if (IMU_IsAvailable() != 0U)
    {
        if (prevImuAvailable == 0U)
        {
            chassisYawFusionMode = 1U;
        }
        prevImuAvailable = 1U;
    }
    else
    {
        chassisYawFusionMode = 0U;
        prevImuAvailable = 0U;
    }

    if ((chassisYawFusionMode != 0U) && (IMU_IsAvailable() != 0U))
    {
        float imu_yaw = IMU_GetYaw();
        dtheta = Chassis_WrapToPi(imu_yaw - prev_yaw);
        float yaw_mid = Chassis_WrapToPi(prev_yaw + 0.5f * dtheta);
        chassisX += ds * cosf(yaw_mid);
        chassisY += ds * sinf(yaw_mid);
        chassisYaw = imu_yaw;
    }
    else
    {
        if (track > 0.0f)
        {
            dtheta = (d_right - d_left) / track;
        }
        float yaw_mid = prev_yaw + 0.5f * dtheta;
        chassisX += ds * cosf(yaw_mid);
        chassisY += ds * sinf(yaw_mid);
        chassisYaw = Chassis_WrapToPi(prev_yaw + dtheta);
    }

    /* 4. 观测速度仅作 Watch/调试观察（做轻度低通，绝不喂给 PID） */
    if (dt <= 0.0f)
    {
        chassisOdomVx = 0.0f;
        chassisOdomOmega = 0.0f;
        odomZeroStreak = 0U;
        return;
    }

    if ((ds == 0.0f) && (dtheta == 0.0f))
    {
        if (odomZeroStreak < CHASSIS_ODOM_ZERO_MS)
        {
            odomZeroStreak++;
        }
    }
    else
    {
        odomZeroStreak = 0U;
    }

    if (odomZeroStreak >= CHASSIS_ODOM_ZERO_MS)
    {
        chassisOdomVx = 0.0f;
        chassisOdomOmega = 0.0f;
    }
    else
    {
        float raw_vx = ds / dt;
        float raw_omega = dtheta / dt;
        chassisOdomVx += CHASSIS_ODOM_LPF_ALPHA * (raw_vx - chassisOdomVx);
        chassisOdomOmega += CHASSIS_ODOM_LPF_ALPHA * (raw_omega - chassisOdomOmega);
    }
}

void Chassis_ResetOdometry(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();

    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        prevDistance[i] = Control_GetDistanceM(i);
    }

    chassisX = 0.0f;
    chassisY = 0.0f;
    chassisYaw = 0.0f;
    chassisOdomVx = 0.0f;
    chassisOdomOmega = 0.0f;
    chassisOdomDistLeft = 0.0f;
    chassisOdomDistRight = 0.0f;
    odomZeroStreak = 0U;
    headingHoldBase = 0.0f;
    headingSettleMs = 0U;
    headingTurnElapsedMs = 0U;
    prevHeadingErrRad = 0.0f;
    prevHeadingErrValid = 0U;
    chassisHeadingErrRad = 0.0f;
    chassisHeadingReached = 0U;
    chassisHeadingTimedOut = 0U;
    IMU_ResetYawZero();

    if (primask == 0U)
    {
        __enable_irq();
    }
}

static float Chassis_ComputeHeadingOmega(float yaw_ref, uint8_t is_point_turn, float *err_out)
{
    float err = Chassis_WrapToPi(yaw_ref - IMU_GetYaw());
    if (err_out != NULL)
    {
        *err_out = err;
    }

    float kp = (chassisHeadingKp > 0.0f) ? chassisHeadingKp : 0.0f;
    float max_w = (chassisHeadingMaxOmega > 0.0f) ? chassisHeadingMaxOmega : 0.0f;
    float w_cmd = kp * err;

    if (is_point_turn != 0U)
    {
        float abs_err = (err < 0.0f) ? -err : err;
        float min_w = (chassisHeadingMinOmega > 0.0f) ? chassisHeadingMinOmega : 0.0f;
        uint8_t sign_flipped = 0U;

        if (min_w > max_w)
        {
            min_w = max_w;
        }

        if (prevHeadingErrValid != 0U)
        {
            if (((err > 0.0f) && (prevHeadingErrRad < 0.0f)) ||
                ((err < 0.0f) && (prevHeadingErrRad > 0.0f)))
            {
                sign_flipped = 1U;
            }
        }

        if (abs_err <= CHASSIS_HEADING_TOL_RAD)
        {
            /* 已进入目标容差带：停止驱动等待 150 ms 稳定，避免在 ±1° 边界来回拉扯 */
            w_cmd = 0.0f;
        }
        else if ((sign_flipped != 0U) && (abs_err < CHASSIS_HEADING_OVERSHOOT_RAD))
        {
            /* 过冲且误差 < 0.05 rad：用 minOmega 主动反向拉回，不靠滑行 */
            w_cmd = (err > 0.0f) ? min_w : -min_w;
        }
        else if (abs_err < CHASSIS_HEADING_LOW_BAND_RAD)
        {
            /* mode 2 低速段保底（|err| < 0.10 rad）：克服静摩擦 */
            float w_mag = kp * abs_err;
            if (w_mag < min_w)
            {
                w_mag = min_w;
            }
            w_cmd = (err > 0.0f) ? w_mag : -w_mag;
        }

        prevHeadingErrRad = err;
        prevHeadingErrValid = 1U;
    }

    if (w_cmd > max_w)
    {
        w_cmd = max_w;
    }
    else if (w_cmd < -max_w)
    {
        w_cmd = -max_w;
    }

    return w_cmd;
}

void Chassis_Init(void)
{
    chassisTrackWidthM = CHASSIS_DEFAULT_TRACK_M;

    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        motorGain[i] = 1.0f;
        wheelScale[i] = CHASSIS_DEFAULT_WHEEL_SCALE;
    }

    chassisTargetVx = 0.0f;
    chassisTargetOmega = 0.0f;
    chassisCmdRejected = 0U;
    chassisYawFusionMode = 1U;
    chassisHeadingMode = 0U;
    chassisHeadingTargetRad = 0.0f;
    chassisHeadingErrRad = 0.0f;
    chassisHeadingKp = CHASSIS_HEADING_DEFAULT_KP;
    chassisHeadingMinOmega = CHASSIS_HEADING_DEFAULT_MIN_W;
    chassisHeadingMaxOmega = CHASSIS_HEADING_DEFAULT_MAX_W;
    chassisHeadingTimeoutMs = CHASSIS_HEADING_DEFAULT_TIMEOUT;
    chassisHeadingReached = 0U;
    chassisHeadingTimedOut = 0U;
    imuPollDivider = 0U;
    prevImuAvailable = 0U;
    headingHoldBase = 0.0f;
    prevHeadingMode = 0U;
    headingSettleMs = 0U;
    headingTurnElapsedMs = 0U;
    prevHeadingErrRad = 0.0f;
    prevHeadingErrValid = 0U;

    IMU_Init();
    if (IMU_IsAvailable() == 0U)
    {
        chassisYawFusionMode = 0U;
    }
    else
    {
        prevImuAvailable = 1U;
    }

    Chassis_ResetOdometry();
}

void Chassis_SetVelocity(float vx, float omega)
{
    /* 安全校验与目标锁存；解算与 RPM 下发由 Chassis_Update() 每 1 ms 执行 */
    if ((vx != vx) || (omega != omega))
    {
        chassisCmdRejected = 1U;
        return;
    }

    /* 轮距未标定时禁止任何转向指令，防止用错误轮距解算出错误姿态 */
    if ((chassisTrackWidthM <= 0.0f) && (omega != 0.0f))
    {
        chassisCmdRejected = 1U;
        return;
    }

    /* 安全限幅截断：|vx| <= 0.869 m/s（250 RPM），|omega| <= 8.5 rad/s */
    if (vx > CHASSIS_MAX_VX_MPS)
    {
        vx = CHASSIS_MAX_VX_MPS;
    }
    else if (vx < -CHASSIS_MAX_VX_MPS)
    {
        vx = -CHASSIS_MAX_VX_MPS;
    }

    if (omega > CHASSIS_MAX_OMEGA_RADS)
    {
        omega = CHASSIS_MAX_OMEGA_RADS;
    }
    else if (omega < -CHASSIS_MAX_OMEGA_RADS)
    {
        omega = -CHASSIS_MAX_OMEGA_RADS;
    }

    chassisTargetVx = vx;
    chassisTargetOmega = omega;
    chassisCmdRejected = 0U;
}

void Chassis_SetHeadingTarget(float target_rad)
{
    if ((target_rad - target_rad) != 0.0f)
    {
        chassisCmdRejected = 1U;
        return;
    }

    chassisHeadingTargetRad = Chassis_WrapToPi(target_rad);
    chassisTargetVx = 0.0f;
    chassisTargetOmega = 0.0f;
    chassisHeadingReached = 0U;
    chassisHeadingTimedOut = 0U;
    headingSettleMs = 0U;
    headingTurnElapsedMs = 0U;
    prevHeadingErrRad = 0.0f;
    prevHeadingErrValid = 0U;
    chassisHeadingMode = 2U;
    prevHeadingMode = 2U;
    chassisCmdRejected = 0U;
}

void Chassis_EnableHeadingHold(uint8_t enable)
{
    if (enable != 0U)
    {
        headingHoldBase = (IMU_IsAvailable() != 0U) ? IMU_GetYaw() : chassisYaw;
        chassisHeadingTargetRad = headingHoldBase;
        chassisHeadingReached = 0U;
        chassisHeadingTimedOut = 0U;
        headingSettleMs = 0U;
        headingTurnElapsedMs = 0U;
        prevHeadingErrValid = 0U;
        chassisHeadingMode = 1U;
        prevHeadingMode = 1U;
    }
    else
    {
        chassisHeadingMode = 0U;
        prevHeadingMode = 0U;
        chassisHeadingErrRad = 0.0f;
        chassisHeadingReached = 0U;
        chassisHeadingTimedOut = 0U;
        headingSettleMs = 0U;
        headingTurnElapsedMs = 0U;
        prevHeadingErrValid = 0U;
    }
}

void Chassis_Update(float dt)
{
    float track = chassisTrackWidthM;
    float wheel_diam = WHEEL_DIAMETER_M;
    float vx = chassisTargetVx;
    float omega = chassisTargetOmega;
    float rpm_cmd[MOTOR_COUNT];
    float max_abs_rpm = 0.0f;

    /* 10 ms 分频读取一次 IMU（100 Hz，内部使用 DWT 2 ms 硬超时，绝不阻塞死锁 SysTick） */
    if (++imuPollDivider >= CHASSIS_IMU_POLL_DIV)
    {
        imuPollDivider = 0U;
        IMU_Update10ms();
    }

    /* 先更新整车里程计（含 IMU 为主 yaw 融合与不可用自动回退） */
    Chassis_UpdateOdometry(dt, track);

    /* 轮距未标定或轮径无效时，不做运动学解算与下发 */
    if ((track <= 0.0f) || (wheel_diam <= 0.0f))
    {
        return;
    }

    /* NaN 安全防护 */
    if ((vx != vx) || (omega != omega))
    {
        return;
    }

    /* 0. 航向闭环纠偏（在差速解算之前覆盖 omega；IMU 航向不喂速度 PID） */
    if (chassisHeadingMode != prevHeadingMode)
    {
        if (chassisHeadingMode == 1U)
        {
            headingHoldBase = (IMU_IsAvailable() != 0U) ? IMU_GetYaw() : chassisYaw;
        }
        headingSettleMs = 0U;
        headingTurnElapsedMs = 0U;
        prevHeadingErrValid = 0U;
        if (chassisHeadingMode != 2U)
        {
            chassisHeadingReached = 0U;
            chassisHeadingTimedOut = 0U;
        }
        else
        {
            chassisHeadingReached = 0U;
            chassisHeadingTimedOut = 0U;
        }
        prevHeadingMode = chassisHeadingMode;
    }

    if (chassisHeadingMode == 1U)
    {
        /* mode 1：航向保持（仍为纯比例，避免直行画龙），IMU 不可用时退回原 chassisTargetOmega */
        if (IMU_IsAvailable() != 0U)
        {
            omega = Chassis_ComputeHeadingOmega(headingHoldBase, 0U, &chassisHeadingErrRad);
        }
        else
        {
            chassisHeadingErrRad = 0.0f;
        }
    }
    else if (chassisHeadingMode == 2U)
    {
        /* mode 2：定点精确转向；IMU 掉线立即停车，绝不盲转 */
        if (IMU_IsAvailable() == 0U)
        {
            vx = 0.0f;
            omega = 0.0f;
            chassisTargetVx = 0.0f;
            chassisTargetOmega = 0.0f;
            chassisHeadingErrRad = 0.0f;
            headingSettleMs = 0U;
        }
        else if (chassisHeadingReached != 0U)
        {
            vx = 0.0f;
            omega = 0.0f;
            chassisHeadingErrRad = Chassis_WrapToPi(chassisHeadingTargetRad - IMU_GetYaw());
        }
        else
        {
            float w_cmd = Chassis_ComputeHeadingOmega(chassisHeadingTargetRad, 1U, &chassisHeadingErrRad);
            float abs_err = (chassisHeadingErrRad < 0.0f) ? -chassisHeadingErrRad : chassisHeadingErrRad;
            uint32_t dt_ms = (dt > 0.0f) ? (uint32_t)(dt * 1000.0f + 0.5f) : 1U;
            if (dt_ms == 0U)
            {
                dt_ms = 1U;
            }

            headingTurnElapsedMs += dt_ms;

            if (abs_err <= CHASSIS_HEADING_TOL_RAD)
            {
                headingSettleMs += dt_ms;
                if (headingSettleMs >= CHASSIS_HEADING_SETTLE_MS)
                {
                    chassisHeadingReached = 1U;
                    chassisHeadingTimedOut = 0U;
                    chassisTargetVx = 0.0f;
                    chassisTargetOmega = 0.0f;
                    vx = 0.0f;
                    w_cmd = 0.0f;
                }
            }
            else
            {
                headingSettleMs = 0U;
                if ((chassisHeadingTimeoutMs > 0U) && (headingTurnElapsedMs >= chassisHeadingTimeoutMs))
                {
                    chassisHeadingReached = 1U;
                    chassisHeadingTimedOut = 1U;
                    chassisTargetVx = 0.0f;
                    chassisTargetOmega = 0.0f;
                    vx = 0.0f;
                    w_cmd = 0.0f;
                }
            }

            vx = 0.0f;
            omega = w_cmd;
        }
    }
    else
    {
        chassisHeadingErrRad = 0.0f;
        chassisHeadingReached = 0U;
        chassisHeadingTimedOut = 0U;
        headingSettleMs = 0U;
        headingTurnElapsedMs = 0U;
        prevHeadingErrValid = 0U;
    }

    /* 1. 差速底盘逆运动学（+Z 逆时针为正：omega > 0 左转 → 左轮慢、右轮快） */
    float left_mps  = vx - omega * track * 0.5f;
    float right_mps = vx + omega * track * 0.5f;

    /* 2. 线速度转目标 RPM，并乘各自 motorGain[]（wheelScale[] 留待 S2-03） */
    float mps_to_rpm = 60.0f / (3.14159265f * wheel_diam);
    float left_rpm   = left_mps * mps_to_rpm;
    float right_rpm  = right_mps * mps_to_rpm;

    rpm_cmd[0] = left_rpm  * motorGain[0];  /* M1：左前 */
    rpm_cmd[1] = right_rpm * motorGain[1];  /* M2：右前 */
    rpm_cmd[2] = left_rpm  * motorGain[2];  /* M3：左后 */
    rpm_cmd[3] = right_rpm * motorGain[3];  /* M4：右后 */

    /* 3. 四轮 ±250 RPM 等比饱和：保持 vx 与 omega 比例不失真 */
    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        float abs_rpm = (rpm_cmd[i] < 0.0f) ? -rpm_cmd[i] : rpm_cmd[i];
        if (abs_rpm > max_abs_rpm)
        {
            max_abs_rpm = abs_rpm;
        }
    }

    if (max_abs_rpm > CHASSIS_MAX_WHEEL_RPM)
    {
        float scale = CHASSIS_MAX_WHEEL_RPM / max_abs_rpm;
        for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
        {
            rpm_cmd[i] *= scale;
        }
    }

    /* 4. 缩放后再逐轮保险限幅 ±250 RPM，并调用 Control_SetTargetRpm() 下发四路 */
    for (uint32_t i = 0U; i < MOTOR_COUNT; i++)
    {
        if (rpm_cmd[i] > CHASSIS_MAX_WHEEL_RPM)
        {
            rpm_cmd[i] = CHASSIS_MAX_WHEEL_RPM;
        }
        else if (rpm_cmd[i] < -CHASSIS_MAX_WHEEL_RPM)
        {
            rpm_cmd[i] = -CHASSIS_MAX_WHEEL_RPM;
        }

        Control_SetTargetRpm(i, rpm_cmd[i]);
    }
}

void Chassis_GetPose(float *x, float *y, float *yaw)
{
    if (x != NULL)
    {
        *x = chassisX;
    }

    if (y != NULL)
    {
        *y = chassisY;
    }

    if (yaw != NULL)
    {
        *yaw = chassisYaw;
    }
}
