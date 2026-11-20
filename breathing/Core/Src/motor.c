#include "motor.h"

Motor_HandleTypeDef motors[MOTOR_COUNT] =
{
    {
        &htim1, TIM_CHANNEL_1,
        M1_IN1_GPIO_Port, M1_IN1_Pin,
        M1_IN2_GPIO_Port, M1_IN2_Pin,
        8399U, 0, 0
    },
    {
        &htim1, TIM_CHANNEL_2,
        M2_IN1_GPIO_Port, M2_IN1_Pin,
        M2_IN2_GPIO_Port, M2_IN2_Pin,
        8399U, 0, 0
    },
    {
        &htim1, TIM_CHANNEL_3,
        M3_IN2_GPIO_Port, M3_IN2_Pin,
        M3_IN1_GPIO_Port, M3_IN1_Pin,
        8399U, 0, 0
    },
    {
        &htim1, TIM_CHANNEL_4,
        M4_IN2_GPIO_Port, M4_IN2_Pin,
        M4_IN1_GPIO_Port, M4_IN1_Pin,
        8399U, 0, 0
    }
};

static int16_t Motor_ClampPercent(int16_t percent)
{
    if (percent > 100)
    {
        return 100;
    }
    if (percent < -100)
    {
        return -100;
    }
    return percent;
}

static void Motor_SetInputs(Motor_HandleTypeDef *motor,
                            GPIO_PinState in1_state,
                            GPIO_PinState in2_state)
{
    HAL_GPIO_WritePin(motor->in1_port, motor->in1_pin, in1_state);
    HAL_GPIO_WritePin(motor->in2_port, motor->in2_pin, in2_state);
}

void Motor_Init(Motor_HandleTypeDef *motor)
{
    motor->output_percent = 0;
    motor->direction = 0;

    Motor_SetInputs(motor, GPIO_PIN_RESET, GPIO_PIN_RESET);
    __HAL_TIM_SET_COMPARE(motor->htim, motor->channel, 0U);
    HAL_TIM_PWM_Start(motor->htim, motor->channel);
}

void Motor_Disable(Motor_HandleTypeDef *motor)
{
    __HAL_TIM_SET_COMPARE(motor->htim, motor->channel, 0U);
    motor->output_percent = 0;
    motor->direction = 0;
    Motor_SetInputs(motor, GPIO_PIN_RESET, GPIO_PIN_RESET);
}

void Motor_SetOutput(Motor_HandleTypeDef *motor, int16_t percent)
{
    percent = Motor_ClampPercent(percent);
    motor->output_percent = percent;

    if (percent == 0)
    {
        motor->direction = 0;
        Motor_SetInputs(motor, GPIO_PIN_RESET, GPIO_PIN_RESET);
        __HAL_TIM_SET_COMPARE(motor->htim, motor->channel, 0U);
        return;
    }

    if (percent > 0)
    {
        motor->direction = 1;
        Motor_SetInputs(motor, GPIO_PIN_SET, GPIO_PIN_RESET);
    }
    else
    {
        motor->direction = -1;
        Motor_SetInputs(motor, GPIO_PIN_RESET, GPIO_PIN_SET);
    }

    uint16_t magnitude = (percent > 0) ? (uint16_t)percent : (uint16_t)(-percent);
    uint32_t compare = ((uint32_t)magnitude * ((uint32_t)motor->period + 1U)) / 100U;

    if (compare > ((uint32_t)motor->period + 1U))
    {
        compare = (uint32_t)motor->period + 1U;
    }

    __HAL_TIM_SET_COMPARE(motor->htim, motor->channel, compare);
}

void Motor_Stop(Motor_HandleTypeDef *motor)
{
    Motor_SetOutput(motor, 0);
}
