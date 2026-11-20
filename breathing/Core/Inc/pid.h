#ifndef __PID_H
#define __PID_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Positional PID controller, intended for speed control.
 *   input  : measured speed (RPM)
 *   output : duty percent (-100 .. +100), fed straight to Motor_SetOutput()
 *
 * Loop rate and gains are chosen by the caller (see main.c).
 */
typedef struct
{
    float kp;
    float ki;
    float kd;

    float setpoint;          /* target speed, RPM */
    float integral;          /* accumulated error * dt */
    float prev_measurement;  /* last measurement, for the D term */
    float out_min;           /* output clamp, percent */
    float out_max;

    float output;            /* last computed output, percent */
} PID_HandleTypeDef;

void PID_Init(PID_HandleTypeDef *pid, float kp, float ki, float kd,
              float out_min, float out_max);
void PID_SetTarget(PID_HandleTypeDef *pid, float setpoint);
void PID_Reset(PID_HandleTypeDef *pid);

/*
 * Compute one PID step.
 *   measurement : measured speed (RPM)
 *   dt          : control period in seconds (e.g. 0.01f for 10 ms)
 * Returns the clamped output in percent.
 */
float PID_Compute(PID_HandleTypeDef *pid, float measurement, float dt);

#ifdef __cplusplus
}
#endif

#endif /* __PID_H */
