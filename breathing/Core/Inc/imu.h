#ifndef __IMU_H
#define __IMU_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/*
 * 维特 10 轴 IMU（I2C2，PB10=SCL / PB11=SDA，400 kHz，7 位地址 0x50）驱动头文件
 *
 * 寄存器定义（已核对 wit_c_sdk/REG.h）：
 *   - KEY   = 0x69，写入 KEY_UNLOCK = 0xB588 解锁配置
 *   - AXIS6 = 0x24，写入 0x0001 切换 6 轴算法模式（屏蔽磁力计干扰）
 *   - RRATE = 0x03，写入 0x0009 设置 100 Hz 输出速率
 *   - RSW   = 0x02，写入 0x000C (RSW_ANGLE 0x08 | RSW_GYRO 0x04)
 *   - GZ    = 0x39，Z 轴角速度原始值（±2000 deg/s -> raw / 32768 * 2000 * pi / 180 rad/s）
 *   - Yaw   = 0x3f，航向角原始值（±180 deg -> raw / 32768 * pi rad）
 *   注：WIT_ANGLE (0x53) 为串口协议帧头，并非 I2C 寄存器（I2C 0x53 为四元数 q2），严禁写入。
 *
 * 死锁防护（SysTick 安全）：
 *   - 运行时 10 ms 轮询读取采用 DWT->CYCCNT（配循环计数兜底）做 2 ms 硬超时，
 *     完全不依赖 HAL_GetTick()，确保未接 IMU 或总线 NACK 时绝不死锁 SysTick。
 */

#define IMU_I2C_ADDR_7BIT       0x50U
#define IMU_I2C_ADDR_WRITE      (IMU_I2C_ADDR_7BIT << 1)
#define IMU_I2C_ADDR_READ       ((IMU_I2C_ADDR_7BIT << 1) | 0x01U)

#define IMU_REG_RSW             0x02U
#define IMU_REG_RRATE           0x03U
#define IMU_REG_AXIS6           0x24U
#define IMU_REG_GZ              0x39U
#define IMU_REG_YAW             0x3FU
#define IMU_REG_KEY             0x69U

#define IMU_KEY_UNLOCK          0xB588U
#define IMU_AXIS6_6DOF          0x0001U
#define IMU_RRATE_100HZ         0x0009U
#define IMU_RSW_GYRO_ANGLE      0x000CU  /* RSW_GYRO(0x04) | RSW_ANGLE(0x08) */

#define IMU_I2C_TIMEOUT_MS      2U

/* Watch 可见标定与状态变量 */
extern uint8_t imuAvailable;             /* 1 = IMU 在线可用，0 = 未接/超时/离线 */
extern float   imuYaw0;                  /* 上电或复位时采集的零点原始角（rad） */
extern float   imuYawSign;               /* 安装方向符号（+1.0f 或 -1.0f，默认 +1.0f，Watch 可写） */
extern float   imuYawOffsetRad;          /* 额外安装零偏（rad，默认 0.0f，Watch 可写） */
extern float   imuRawYawRad;             /* 最近一次读取的原始 yaw（rad） */
extern float   imuYawRad;                /* 标定与相对归零后的 yaw（rad，(-pi, pi]） */
extern float   imuYawRateRads;           /* Z 轴角速度（rad/s，由 GZ 0x39 换算） */

void IMU_Init(void);
void IMU_Update10ms(void);
void IMU_ResetYawZero(void);
uint8_t IMU_IsAvailable(void);
float IMU_GetYaw(void);
float IMU_GetYawRate(void);

#ifdef __cplusplus
}
#endif

#endif /* __IMU_H */
