
#include "control.h"
#include "chassis.h"
#include "motor.h"
#include "encoder.h"
#include "pid.h"
#include <stdint.h>

/* ============================ 调参区 ============================ */
/*
 * 时序契约说明（派单 02，方案 A）：
 *   - SysTick_Handler() 每 1 ms 调用一次 Control_Update()；
 *   - 每次 1 ms 完成：读编码器（1 ms 瞬时速度）→ W2 一阶低通滤波 + 零计数保护
 *     → 1 ms 闭环 PID（dt = CONTROL_PID_DT = 0.001 s）→ 输出占空比；
 *   - debugNet / debugAbs 保留独立的 100 ms 诊断累加窗口（CONTROL_DIAG_PERIOD_MS）。
 */

/* 安全红线：切闭环前默认目标转速必须为 0，保证上电不自行跑车 */
#define CONTROL_TARGET_RPM        0.0f

/* 速度PID运行周期：1 ms */
#define CONTROL_PID_PERIOD_MS     1U
#define CONTROL_PID_DT            ((float)CONTROL_PID_PERIOD_MS / 1000.0f)

/* 1 ms 测速抗噪声保护（W2） */
#define CONTROL_SPEED_LPF_ALPHA   0.20f  /* 一阶低通系数 (0~1)，平滑 1 ms 量化跳变 */
#define CONTROL_ZERO_GUARD_MS     20U    /* 连续 20 ms 无脉冲 (<2.3 RPM) 则速度归零，避免静止残留且不伤低速跟踪 */

/* 100 ms 诊断窗口周期（保留 debugNet/debugAbs Watch 统计） */
#define CONTROL_DIAG_PERIOD_MS    100U

/* PID参数（派单 03 实测整定值，1 ms 速度闭环） */
#define CONTROL_PID_KP            0.4f
#define CONTROL_PID_KI            2.5f
#define CONTROL_PID_KD            0.0f

/* 1 = 固定PWM开环；0 = PID闭环（运行期也可由 controlCalibrationMode=1 切入标定开环） */
#define CONTROL_OPEN_LOOP         0
#define CONTROL_OPEN_LOOP_DUTY    0

/* 1 = 手动编码器测试；0 = 电机驱动模式 */
#define CONTROL_TEST_MODE         0

/* ================================================================ */

static volatile uint8_t controlInitialized = 0U;
static PID_HandleTypeDef motorPid[MOTOR_COUNT];

float motorTargetRpm[MOTOR_COUNT] = {
    CONTROL_TARGET_RPM,
    CONTROL_TARGET_RPM,
    CONTROL_TARGET_RPM,
    CONTROL_TARGET_RPM
};

float motorSpeedFiltered[MOTOR_COUNT] = {0.0f};

/* W1：开环标定控制量（默认全 0，确保误切开环也不冲速） */
int16_t motorOpenLoopDuty[MOTOR_COUNT] = {0, 0, 0, 0};
uint8_t controlCalibrationMode = 0U;

/* W2：运行时可调 PID 参数（默认值 0.4 / 2.5 / 0） */
float motorKp = CONTROL_PID_KP;
float motorKi = CONTROL_PID_KI;
float motorKd = CONTROL_PID_KD;

/* 编码器诊断数据（100 ms 窗口） */
static volatile int32_t debugNet[MOTOR_COUNT] = {0};
static volatile int32_t debugAbs[MOTOR_COUNT] = {0};

#if !CONTROL_TEST_MODE
static uint8_t prevCalibrationMode = 0U;
static uint32_t zeroCountStreak[MOTOR_COUNT] = {0};
static int32_t diagNetAccum[MOTOR_COUNT] = {0};
static int32_t diagAbsAccum[MOTOR_COUNT] = {0};
static uint32_t diagWindowCount = 0U;
#endif

void Control_Init(void)
{
    motorKp = CONTROL_PID_KP;
    motorKi = CONTROL_PID_KI;
    motorKd = CONTROL_PID_KD;
	controlCalibrationMode = 0U;    //1为开环模式，0为闭环模式

    for (uint32_t i = 0; i < MOTOR_COUNT; i++)
    {
        Motor_Init(&motors[i]);
        Encoder_Init(&encoders[i]);

        motorTargetRpm[i] = CONTROL_TARGET_RPM;
        motorOpenLoopDuty[i] = 0;

        PID_Init(&motorPid[i],
                 motorKp,
                 motorKi,
                 motorKd,
                 -100.0f,
                 100.0f);

        PID_SetTarget(&motorPid[i], motorTargetRpm[i]);

        motorSpeedFiltered[i] = 0.0f;
        debugNet[i] = 0;
        debugAbs[i] = 0;

#if !CONTROL_TEST_MODE
        zeroCountStreak[i] = 0U;
        diagNetAccum[i] = 0;
        diagAbsAccum[i] = 0;
#endif
    }

#if !CONTROL_TEST_MODE
    prevCalibrationMode = controlCalibrationMode;
    diagWindowCount = 0U;
#endif

    Chassis_Init();

    controlInitialized = 1U;
}

void Control_Update(void)
{
    if (!controlInitialized)
    {
        return;
    }

#if CONTROL_TEST_MODE

    /* 手动测试模式：只更新编码器累计计数 */
    for (uint32_t i = 0; i < MOTOR_COUNT; i++)
    {
        Encoder_Update(&encoders[i]);
    }

#else

    /* 模式切换安全保护：进/出标定模式均先将目标转速归零并复位 PID 状态 */
    uint8_t calib = (controlCalibrationMode != 0U) ? 1U : 0U;
    if (calib != prevCalibrationMode)
    {
        for (uint32_t i = 0; i < MOTOR_COUNT; i++)
        {
            motorTargetRpm[i] = 0.0f;
            PID_Reset(&motorPid[i]);
            PID_SetTarget(&motorPid[i], 0.0f);
        }
        prevCalibrationMode = calib;
    }

    /* 每 1 ms 读取编码器、滤波测速并执行控制输出 */
    for (uint32_t i = 0; i < MOTOR_COUNT; i++)
    {
        int32_t delta = Encoder_Update(&encoders[i]);

        /* 100 ms 诊断窗口累加（N：净计数，A：绝对计数总和） */
        diagNetAccum[i] += delta;
        diagAbsAccum[i] += (delta >= 0) ? delta : -delta;

        /* W2：连续零计数保护 + 一阶低通滤波 */
        if (delta == 0)
        {
            if (zeroCountStreak[i] < CONTROL_ZERO_GUARD_MS)
            {
                zeroCountStreak[i]++;
            }
        }
        else
        {
            zeroCountStreak[i] = 0U;
        }

        if (zeroCountStreak[i] >= CONTROL_ZERO_GUARD_MS)
        {
            motorSpeedFiltered[i] = 0.0f;
        }
        else
        {
            float raw_rpm = Encoder_GetSpeedRpm(&encoders[i]);
            motorSpeedFiltered[i] +=
                CONTROL_SPEED_LPF_ALPHA * (raw_rpm - motorSpeedFiltered[i]);
        }

        if ((calib != 0U) || (CONTROL_OPEN_LOOP != 0))
        {
            /* W1：标定模式或开环模式，按 motorOpenLoopDuty[] 输出，不走 PID */
            Motor_SetOutput(&motors[i], motorOpenLoopDuty[i]);
        }
        else
        {
            /* W2/W4：同步运行时增益与目标转速，每 1 ms 执行 PID 闭环控制 */
            motorPid[i].kp = motorKp;
            motorPid[i].ki = motorKi;
            motorPid[i].kd = motorKd;
            PID_SetTarget(&motorPid[i], motorTargetRpm[i]);

            float out = PID_Compute(&motorPid[i],
                                    motorSpeedFiltered[i],
                                    CONTROL_PID_DT);

            Motor_SetOutput(&motors[i], (int16_t)out);
        }
    }

    /* W5：独立 100 ms 诊断窗口刷新 */
    if (++diagWindowCount >= CONTROL_DIAG_PERIOD_MS)
    {
        diagWindowCount = 0U;

        for (uint32_t i = 0; i < MOTOR_COUNT; i++)
        {
            debugNet[i] = diagNetAccum[i];
            debugAbs[i] = diagAbsAccum[i];
            diagNetAccum[i] = 0;
            diagAbsAccum[i] = 0;
        }
    }

    Chassis_Update(CONTROL_PID_DT);

#endif
}

/* ====================== 数据读取与目标接口 ====================== */

float Control_GetSpeedRpm(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0.0f;

    return motorSpeedFiltered[index];
}

void Control_SetTargetRpm(uint32_t index, float target_rpm)
{
    if (index >= MOTOR_COUNT)
        return;

    motorTargetRpm[index] = target_rpm;
    PID_SetTarget(&motorPid[index], target_rpm);
}

float Control_GetTargetRpm(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0.0f;

    return motorTargetRpm[index];
}

void Control_SetCalibrationMode(uint8_t enable)
{
    controlCalibrationMode = (enable != 0U) ? 1U : 0U;
}

void Control_SetOpenLoopDuty(uint32_t index, int16_t duty_percent)
{
    if (index >= MOTOR_COUNT)
        return;

    if (duty_percent > 100)
        duty_percent = 100;
    else if (duty_percent < -100)
        duty_percent = -100;

    motorOpenLoopDuty[index] = duty_percent;
}

void Control_SetGains(float kp, float ki, float kd)
{
    motorKp = kp;
    motorKi = ki;
    motorKd = kd;
}

int16_t Control_GetOutputPercent(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0;

    return motors[index].output_percent;
}

int32_t Control_GetTotalCount(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0;

    return encoders[index].total_count;
}

float Control_GetDistanceM(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0.0f;

    return Encoder_GetDistanceM(&encoders[index]);
}

/* N：最近100ms净计数 */
int32_t Control_GetDebugNet(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0;

    return debugNet[index];
}

/* A：最近100ms绝对计数总和 */
int32_t Control_GetDebugAbs(uint32_t index)
{
    if (index >= MOTOR_COUNT)
        return 0;

    return debugAbs[index];
}

uint8_t Control_IsTestMode(void)
{
    return (CONTROL_TEST_MODE != 0) ? 1U : 0U;
}
