#include "encoder.h"

/*
 * 编码器分辨率：输出轴每转一圈的计数（A/B 两相 4 倍频），四路电机同型号共用。
 *
 * 2026-11-17 多圈标定（5 圈/路）：
 *   M1~M4 总计数均为 6590（极差 ≤5），折算 1318 计数/圈。
 *   1318 不是 4 的倍数，而 4 倍频计数必须是 4 的倍数；这 0.15% 的偏差
 *   正好等于手推起止点未精确对齐的误差（5 圈共约 10 个计数）。
 *   按电机规格 11 线 × 4 倍频 × 30:1 减速比，取理论精确值 1320。
 *   1320 与实测仅差 0.15%，对测速和 PID 无影响。
 */
#define ENCODER_COUNTS_PER_REV  1320U

/*
 * 每路编码器方向：让"前进"方向计数为正（+1 / -1）。
 * M3/M4 的电机 IN1/IN2 已在 motor.c 对调，因此四路方向均为 +1。
 *
 * 电机映射：
 *   M1 -> TIM3 -> PA6/PA7
 *   M2 -> TIM4 -> PD12/PD13
 *   M3 -> TIM5 -> PA0/PA1
 *   M4 -> TIM2 -> PA5/PB3
 */
static const int8_t encoderDirection[ENCODER_COUNT] =
{
     1,   /* M1 */
     1,   /* M2 */
     1,   /* M3 */
     1    /* M4 */
};

Encoder_HandleTypeDef encoders[ENCODER_COUNT] =
{
    { &htim3, 0, 0, 0, 0, 0, 0.0f, 0.0f },
    { &htim4, 0, 0, 0, 0, 0, 0.0f, 0.0f },
    { &htim5, 0, 0, 0, 0, 0, 0.0f, 0.0f },
    { &htim2, 0, 0, 0, 0, 0, 0.0f, 0.0f }
};

void Encoder_Init(Encoder_HandleTypeDef *encoder)
{
    uint32_t idx = (uint32_t)(encoder - encoders);

    encoder->direction      = encoderDirection[idx];
    encoder->counts_per_rev = ENCODER_COUNTS_PER_REV;

    encoder->last_raw    = (uint16_t)__HAL_TIM_GET_COUNTER(encoder->htim);
    encoder->total_count = 0;
    encoder->last_delta  = 0;
    encoder->speed_rpm   = 0.0f;
    encoder->distance_m  = 0.0f;

    HAL_TIM_Encoder_Start(encoder->htim, TIM_CHANNEL_ALL);
}

int32_t Encoder_Update(Encoder_HandleTypeDef *encoder)
{
    uint16_t raw = (uint16_t)__HAL_TIM_GET_COUNTER(encoder->htim);
    int32_t delta = (int32_t)(uint16_t)(raw - encoder->last_raw);

    if (delta > 32767)
    {
        delta -= 65536;
    }

    delta *= encoder->direction;

    encoder->last_raw    = raw;
    encoder->last_delta  = delta;
    encoder->total_count += delta;

    /*
     * 这是 1 ms 瞬时 RPM，噪声较大；PID 使用 control.c 中 100 ms 窗口的
     * Control_GetSpeedRpm()，不是这个瞬时值。
     * （60000 系数已包含 60 s/min × 1000 ms/s，公式保持不变）
     */
    encoder->speed_rpm =
        ((float)delta * 60000.0f) / ((float)encoder->counts_per_rev * 1.0f);
    encoder->distance_m = Encoder_GetDistanceM(encoder);

    return delta;
}

int32_t Encoder_GetTotalCount(const Encoder_HandleTypeDef *encoder)
{
    return encoder->total_count;
}

float Encoder_GetSpeedRpm(const Encoder_HandleTypeDef *encoder)
{
    return encoder->speed_rpm;
}

float Encoder_GetDistanceM(const Encoder_HandleTypeDef *encoder)
{
    float wheel_diameter_m = WHEEL_DIAMETER_M;

    if ((encoder == NULL) || (encoder->counts_per_rev == 0U) || (wheel_diameter_m <= 0.0f))
    {
        return 0.0f;
    }

    return ((float)encoder->total_count / (float)encoder->counts_per_rev) *
           (3.14159265f * wheel_diameter_m);
}

void Encoder_ResetOdometry(Encoder_HandleTypeDef *encoder)
{
    if (encoder == NULL)
    {
        return;
    }

    encoder->total_count = 0;
    encoder->distance_m  = 0.0f;
}
