#ifndef __CHASSIS_H
#define __CHASSIS_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * 阶段 2（S2-02）差速底盘运动学与接口头文件
 *
 * 1. 单位约定：
 *    - 线速度 vx        ：m/s
 *    - 角速度 omega     ：rad/s
 *    - 轮速             ：RPM
 *    - 位姿位置 (x, y)  ：m
 *    - 航向角 yaw       ：rad
 *
 * 2. 坐标系约定（右手系）：
 *    - +X：车体前进方向
 *    - +Y：车体左侧方向
 *    - +Z：竖直向上，逆时针为正（omega > 0 表示左转）
 *
 * 3. 轮序与侧别映射（四轮差速底盘，禁止实现 vy / 横移 / 麦克纳姆公式）：
 *    - M1（索引 0）：左前（zuoqian）
 *    - M2（索引 1）：右前（youqian）
 *    - M3（索引 2）：左后（zuohou）
 *    - M4（索引 3）：右后（youhou）
 *    - 左侧轮 = M1 / M3，右侧轮 = M2 / M4
 *
 * 4. 速度换算参考（基于实测轮径 WHEEL_DIAMETER_M = 0.066404 m）：
 *    - rpm = v_mps * 60.0f / (3.14159265f * 0.066404f) ≈ v_mps * 287.6f
 *
 * 5. 安全限幅说明：
 *    - 单轮上限 ±250.0f RPM（满速约 330 RPM）；解算后四轮按最大绝对值做等比饱和。
 *    - |vx| <= 0.869f m/s：对应单轮 250 RPM 安全线速度上限。
 *    - |omega| <= 8.5f rad/s：按实测轮距 0.20 m 算得理论极值 2 * 0.869 / 0.20 = 8.69 rad/s，
 *      取 8.5 rad/s 留安全余量；若同时给 vx 与 omega，仍由四轮 ±250 RPM 等比饱和兜底。
 *
 * 6. 本单边界（S2-04）：
 *    - 已实现差速运动学解算与四轮 RPM 下发（Control_SetTargetRpm）；
 *    - 已实现基于四轮累计距离（Control_GetDistanceM）的整车里程计积分（x/y/yaw）及复位接口；
 *    - 已接入 I2C2 维特 IMU（0x50，10 ms 分频读取，DWT 2 ms 硬超时），支持以 IMU 为主的 yaw 融合与纯编码器回退。
 */

#include <stdint.h>
#include "motor.h"
#include "imu.h"

#define CHASSIS_MAX_VX_MPS      0.869f
#define CHASSIS_MAX_OMEGA_RADS  8.5f
#define CHASSIS_MAX_WHEEL_RPM   250.0f

/* 全局状态与标定参数（Watch 可见；motorGain 与 wheelScale 保持独立） */
/* 轮距（m）：0.20 m 为几何粗测值，保持可写；S2-05 将用 track=(右累计距离-左累计距离)/π 标定等效轮距后覆盖 */
extern float chassisTrackWidthM;
extern float motorGain[MOTOR_COUNT];         /* 电机/驱动增益补偿，默认全 1.0f（仅用于运动学） */
extern float wheelScale[MOTOR_COUNT];        /* 轮径/里程比例补偿，默认全 1.0f（仅用于里程计） */
extern float chassisX;                       /* 里程计 X（m），默认 0.0f */
extern float chassisY;                       /* 里程计 Y（m），默认 0.0f */
extern float chassisYaw;                     /* 航向角 yaw（rad），归一化到 (-pi, pi]，默认 0.0f */
extern float chassisOdomVx;                  /* 里程计观测线速度（m/s，仅调试观察，不进 PID） */
extern float chassisOdomOmega;               /* 里程计观测角速度（rad/s，仅调试观察，不进 PID） */
extern float chassisOdomDistLeft;            /* 左侧累计标定距离（m，只读观测量，不进控制） */
extern float chassisOdomDistRight;           /* 右侧累计标定距离（m，只读观测量，不进控制） */
extern float chassisTargetVx;                /* 锁存的目标线速度（m/s），默认 0.0f */
extern float chassisTargetOmega;             /* 锁存的目标角速度（rad/s），默认 0.0f */
extern uint8_t chassisCmdRejected;           /* 最近一次 SetVelocity 是否被拒绝（1=拒绝，0=接受） */
extern uint8_t chassisYawFusionMode;         /* 0 = 纯编码器积分，1 = IMU 为主融合（默认 1，IMU 不可用自动回 0） */
extern uint8_t imuAvailable;                 /* IMU 可用标志（1=在线，0=不可用） */
extern uint8_t chassisHeadingMode;           /* 0 = 纯速度原行为（默认），1 = 航向保持，2 = 定点转向 */
extern float chassisHeadingTargetRad;        /* 定点转向目标角（rad，[-pi, pi]） */
extern float chassisHeadingErrRad;           /* 航向环误差（rad，只读观测） */
extern float chassisHeadingKp;               /* 航向环比例增益（默认 1.0f，可写） */
extern float chassisHeadingMinOmega;         /* 定点转向低速段最小角速度保底（rad/s，默认 0.06f，可写） */
extern float chassisHeadingMaxOmega;         /* 航向环角速度上限（rad/s，默认 1.0f，可写） */
extern uint32_t chassisHeadingTimeoutMs;     /* 定点转向最大超时（ms，默认 8000U，可写） */
extern uint8_t chassisHeadingReached;        /* 定点转向到达标志（1=已到达并停车，只读） */
extern uint8_t chassisHeadingTimedOut;       /* 定点转向是否因超时停车（1=超时停，0=正常到达，只读） */

/* 底盘与 IMU 接口（签名冻结） */
void Chassis_Init(void);
void Chassis_SetVelocity(float vx, float omega);       /* m/s, rad/s */
void Chassis_ForceStop(void);                          /* 统一安全强停（清目标/退航向环/置到达/四路归零） */
void Chassis_SetHeadingTarget(float target_rad);       /* 进入 mode 2 定点转向，目标绝对相对零点角（rad） */
void Chassis_EnableHeadingHold(uint8_t enable);        /* 1=锁存当前 IMU 航向进入 mode 1，0=退回 mode 0 */
void Chassis_Update(float dt);                         /* 由 Control_Update 每 1 ms 调 */
void Chassis_GetPose(float *x, float *y, float *yaw);  /* 指针出参 m/m/rad */
void Chassis_ResetOdometry(void);                      /* 清零整车位姿并对齐当前编码器累计距离 */
uint8_t IMU_IsAvailable(void);                         /* 本阶段返回 0 */
float IMU_GetYaw(void);                                /* 返回 0 */
float IMU_GetYawRate(void);                            /* 返回 0 */

#ifdef __cplusplus
}
#endif

#endif /* __CHASSIS_H */
