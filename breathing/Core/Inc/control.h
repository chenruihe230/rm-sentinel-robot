#ifndef __CONTROL_H
#define __CONTROL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include "motor.h"

/* One-time setup: init motors, encoders and the PID controllers. */
void Control_Init(void);

/* 1 ms control tick. Call from SysTick_Handler. */
void Control_Update(void);

/* Accessors & runtime tuning interfaces (values are updated/applied in Control_Update). */
float Control_GetSpeedRpm(uint32_t index);
void Control_SetTargetRpm(uint32_t index, float target_rpm);
float Control_GetTargetRpm(uint32_t index);
void Control_SetCalibrationMode(uint8_t enable);
void Control_SetOpenLoopDuty(uint32_t index, int16_t duty_percent);
void Control_SetGains(float kp, float ki, float kd);
int16_t Control_GetOutputPercent(uint32_t index);
int32_t Control_GetTotalCount(uint32_t index);
float Control_GetDistanceM(uint32_t index);
uint8_t Control_IsTestMode(void);
int32_t Control_GetDebugNet(uint32_t index);
int32_t Control_GetDebugAbs(uint32_t index);

/* Watch-accessible variables (updated/read in 1 ms control loop). */
extern float motorTargetRpm[MOTOR_COUNT];
extern float motorSpeedFiltered[MOTOR_COUNT];
extern int16_t motorOpenLoopDuty[MOTOR_COUNT];
extern uint8_t controlCalibrationMode;
extern float motorKp;
extern float motorKi;
extern float motorKd;
#ifdef __cplusplus
}
#endif

#endif /* __CONTROL_H */
