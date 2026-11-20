#include "pid.h"

void PID_Init(PID_HandleTypeDef *pid, float kp, float ki, float kd,
              float out_min, float out_max)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->setpoint = 0.0f;
    pid->integral = 0.0f;
    pid->prev_measurement = 0.0f;
    pid->out_min = out_min;
    pid->out_max = out_max;
    pid->output = 0.0f;
}

void PID_SetTarget(PID_HandleTypeDef *pid, float setpoint)
{
    pid->setpoint = setpoint;
}

void PID_Reset(PID_HandleTypeDef *pid)
{
    pid->integral = 0.0f;
    pid->prev_measurement = 0.0f;
    pid->output = 0.0f;
}

float PID_Compute(PID_HandleTypeDef *pid, float measurement, float dt)
{
    if (dt <= 0.0f)
    {
        dt = 0.001f; /* guard against division by zero */
    }

    float error = pid->setpoint - measurement;

    /* Proportional term. */
    float p = pid->kp * error;

    /* Derivative on measurement (not on error) to avoid derivative kick
       when the setpoint changes. */
    float d = -pid->kd * (measurement - pid->prev_measurement) / dt;
    pid->prev_measurement = measurement;

    float out = p + pid->ki * pid->integral + d;

    /* Conditional-integration anti-windup: only accumulate while the output
       is not already saturated in the direction the error is pushing it. */
    if (!((out >= pid->out_max && error > 0.0f) ||
          (out <= pid->out_min && error < 0.0f)))
    {
        pid->integral += error * dt;
    }

    out = p + pid->ki * pid->integral + d;

    /* Output clamp. */
    if (out > pid->out_max)
    {
        out = pid->out_max;
    }
    else if (out < pid->out_min)
    {
        out = pid->out_min;
    }

    pid->output = out;
    return out;
}
