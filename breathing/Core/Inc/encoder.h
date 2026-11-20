#ifndef __ENCODER_H
#define __ENCODER_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include "tim.h"

#define ENCODER_COUNT  4U

/* 2026-11-18 1m 实推标定等效轮径（M1=6283, M2=6338, M3=6310, M4=6379，均值 6327.5 -> 66.40 mm） */
#define WHEEL_DIAMETER_M  0.066404f

/*
 * 编码器分辨率统一在 encoder.c 的 ENCODER_COUNTS_PER_REV 中定义，四路共用（1320）。
 *   direction      ：+1 或 -1。让"正转/前进"方向时计数为正，在 encoder.c 中配置。
 *   counts_per_rev ：输出轴转一圈的计数（4 倍频后），四路一致。
 */
typedef struct
{
    TIM_HandleTypeDef *htim;
    int8_t   direction;
    uint32_t counts_per_rev;
    uint16_t last_raw;
    int32_t  total_count;
    int32_t  last_delta;
    float    speed_rpm;
    float    distance_m;
} Encoder_HandleTypeDef;

extern Encoder_HandleTypeDef encoders[ENCODER_COUNT];

void Encoder_Init(Encoder_HandleTypeDef *encoder);
int32_t Encoder_Update(Encoder_HandleTypeDef *encoder);
int32_t Encoder_GetTotalCount(const Encoder_HandleTypeDef *encoder);
float Encoder_GetSpeedRpm(const Encoder_HandleTypeDef *encoder);
float Encoder_GetDistanceM(const Encoder_HandleTypeDef *encoder);
void Encoder_ResetOdometry(Encoder_HandleTypeDef *encoder);

#ifdef __cplusplus
}
#endif

#endif /* __ENCODER_H */
