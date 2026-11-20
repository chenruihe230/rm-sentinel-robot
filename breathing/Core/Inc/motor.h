#ifndef __MOTOR_H
#define __MOTOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"
#include "tim.h"

#define MOTOR_COUNT  4U

/*
 * Four motor driver channels:
 *   TIM1_CH1 / PE9  -> M1 PWM
 *   TIM1_CH2 / PE11 -> M2 PWM
 *   TIM1_CH3 / PE13 -> M3 PWM
 *   TIM1_CH4 / PE14 -> M4 PWM
 *
 * Each motor uses two direction inputs:
 *   IN1=1, IN2=0 -> forward
 *   IN1=0, IN2=1 -> reverse
 *   IN1=0, IN2=0 -> coast/stop
 */
typedef struct
{
    TIM_HandleTypeDef *htim;
    uint32_t channel;

    GPIO_TypeDef *in1_port;
    uint16_t in1_pin;

    GPIO_TypeDef *in2_port;
    uint16_t in2_pin;

    uint16_t period;
    int16_t output_percent;
    int8_t direction;
} Motor_HandleTypeDef;

extern Motor_HandleTypeDef motors[MOTOR_COUNT];

void Motor_Init(Motor_HandleTypeDef *motor);
void Motor_Disable(Motor_HandleTypeDef *motor);
void Motor_SetOutput(Motor_HandleTypeDef *motor, int16_t percent);
void Motor_Stop(Motor_HandleTypeDef *motor);

#ifdef __cplusplus
}
#endif

#endif /* __MOTOR_H */
