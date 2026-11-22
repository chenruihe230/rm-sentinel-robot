#ifndef __COMM_PROTOCOL_H
#define __COMM_PROTOCOL_H

#ifdef __cplusplus
extern "C" {
#endif

/*
 * 阶段 3（S3-01A）HC-12 无线串口通信协议头文件（纯软件协议与打包/解包接口）
 *
 * 1. 链路与调度约定（由 S3-02 UART 层实现，本文件不含任何硬件/HAL 调用）：
 *    - 模块与链路：HC-12 半双工无线串口，电脑主机 <-> STM32 从机；
 *    - 应答规则：STM32 仅在收到一帧有效请求后回传一帧 TELEMETRY，周期 50 ms（20 Hz）；
 *    - 序号规则（uint8，255 -> 0 回绕为正常递增）：
 *      * 主机每帧递增 SEQ，STM32 响应帧原样复制请求帧 SEQ；
 *      * 非 +1（含非 255->0 回绕）的序号跳变计入 drop_count；
 *      * 收到重复序号视为重发：CMD_STOP 仍必须执行，其余命令不重复修改控制状态，仅返回缓存遥测。
 *
 * 2. 帧格式（多字节字段一律小端 Little-Endian，禁止浮点字符串）：
 *    [0..1]   AA 55       帧头（COMM_FRAME_HEADER_0 / 1）
 *    [2]      TYPE        命令/遥测类型
 *    [3]      SEQ         帧序号（0~255）
 *    [4..4+N-1] DATA      载荷数据（N 字节，随 TYPE 固定）
 *    [4+N]    CRC8        校验字节（覆盖 TYPE + SEQ + DATA 共 2+N 字节）
 *    [5+N..6+N] 0D 0A     帧尾（COMM_FRAME_TAIL_0 / 1）
 *
 * 3. CRC8 参数（非查表位运算标准实现）：
 *    - Poly = 0x07（x^8 + x^2 + x + 1）、Init = 0x00、RefIn = false、RefOut = false、XorOut = 0x00。
 *    - 标准验证向量：
 *      * {03 01}             -> 0x38（CMD_STOP SEQ=1 完整帧：AA 55 03 01 38 0D 0A）
 *      * {02 01 64 00 00 00} -> 0x3D（CMD_VEL  SEQ=1, vx=100 mm/s, omega=0）
 *
 * 4. 定点整数换算约定：
 *    - vx_mps     = (float)vx_mmps / 1000.0f              （mm/s -> m/s）
 *    - omega_rads = (float)omega_mradps / 1000.0f         （mrad/s -> rad/s）
 *    - yaw_rad    = (float)yaw_001deg * 0.01f * PI / 180.0f（0.01° -> rad）
 *    - x_m / y_m  = (float)x_mm / 1000.0f                 （mm -> m）
 *    - rpm[4]     = int16 整数 RPM（1 RPM/LSB）
 *    - pwm[4]     = int8  有符号占空比百分比（-100 ~ +100 %）
 */

#include <stdint.h>

/* 帧定界与长度常量 */
#define COMM_FRAME_HEADER_0        0xAAU
#define COMM_FRAME_HEADER_1        0x55U
#define COMM_FRAME_TAIL_0          0x0DU
#define COMM_FRAME_TAIL_1          0x0AU
#define COMM_FRAME_OVERHEAD_BYTES  7U
#define COMM_FRAME_MIN_LEN         COMM_FRAME_OVERHEAD_BYTES
#define COMM_FRAME_MAX_DATA_LEN    26U
#define COMM_FRAME_MAX_LEN         (COMM_FRAME_OVERHEAD_BYTES + COMM_FRAME_MAX_DATA_LEN)

/* CRC8 与通信周期参数 */
#define COMM_CRC8_POLY             0x07U
#define COMM_CRC8_INIT             0x00U
#define COMM_CRC8_XOROUT           0x00U
#define COMM_PERIOD_MS             50U

/* 定点换算比例常量 */
#define COMM_PI                    3.14159265f
#define COMM_VEL_MMPS_PER_MPS      1000.0f
#define COMM_OMEGA_MRADPS_PER_RADS 1000.0f
#define COMM_POS_MM_PER_M          1000.0f
#define COMM_YAW_001DEG_SCALE      0.01f
#define COMM_DEG_TO_RAD            (COMM_PI / 180.0f)

/* 帧类型 TYPE 定义 */
#define COMM_TYPE_CMD_POLL         0x01U
#define COMM_TYPE_CMD_VEL          0x02U
#define COMM_TYPE_CMD_STOP         0x03U
#define COMM_TYPE_CMD_MODE         0x04U
#define COMM_TYPE_CMD_ACTION       0x05U
#define COMM_TYPE_TELEMETRY        0x10U

/* 各 TYPE 固定载荷长度（字节） */
#define COMM_LEN_CMD_POLL          0U
#define COMM_LEN_CMD_VEL           4U
#define COMM_LEN_CMD_STOP          0U
#define COMM_LEN_CMD_MODE          1U
#define COMM_LEN_CMD_ACTION        3U
#define COMM_LEN_TELEMETRY         26U

/* Comm_ParseFrame 返回错码 */
#define COMM_PARSE_OK              ((int8_t)0)
#define COMM_PARSE_ERR_HEADER      ((int8_t)-1)
#define COMM_PARSE_ERR_TAIL        ((int8_t)-2)
#define COMM_PARSE_ERR_CRC         ((int8_t)-3)
#define COMM_PARSE_ERR_LEN         ((int8_t)-4)

/* CMD_VEL (0x02, 4B) 解析结构 */
typedef struct
{
    int16_t vx_mmps;        /* 线速度，mm/s（vx_mps = vx_mmps / 1000.0f） */
    int16_t omega_mradps;   /* 角速度，mrad/s（omega_rads = omega_mradps / 1000.0f） */
} Comm_CmdVel_t;

/* CMD_MODE (0x04, 1B) 解析结构 */
typedef struct
{
    uint8_t fusion_mode;    /* 对应 chassisYawFusionMode（0=纯编码器，1=IMU 为主） */
} Comm_CmdMode_t;

/* CMD_ACTION (0x05, 3B) 解析结构 */
typedef struct
{
    uint8_t action_id;      /* 0x01=直行(mm), 0x02=转向(0.1°), 0x03=停车, 0x04=掉头180° */
    int16_t param;          /* 小端有符号参数（mm 或 0.1°） */
} Comm_CmdAction_t;

/* TELEMETRY (0x10, 26B) 载荷结构（小端逐字节编解码） */
typedef struct
{
    int16_t  rpm[4];          /* 4 路轮速（1 RPM/LSB），8B */
    int8_t   pwm[4];          /* 4 路占空比（-100~+100 %），4B */
    int16_t  x_mm;            /* 里程计 X（mm），2B */
    int16_t  y_mm;            /* 里程计 Y（mm），2B */
    int16_t  odom_yaw_001deg; /* 里程计航向角（0.01°），2B */
    int16_t  imu_yaw_001deg;  /* IMU 航向角（0.01°），2B */
    uint8_t  status;          /* 状态位掩码，1B */
    uint8_t  fusion_mode;     /* 当前航向融合模式，1B */
    uint16_t drop_count;      /* 序号跳变丢包计数，2B */
    uint16_t timeout_count;   /* 通信超时停车计数，2B */
} Comm_Telemetry_t;

/* 通用解析帧结构 */
typedef struct
{
    uint8_t  type;
    uint8_t  seq;
    uint32_t data_len;
    uint8_t  data[COMM_FRAME_MAX_DATA_LEN];
    uint8_t  crc8;
} Comm_Frame_t;

/* 纯软件协议接口 */
uint8_t  Comm_Crc8(const uint8_t *data, uint32_t len);
uint32_t Comm_BuildFrame(uint8_t *out, uint8_t type, uint8_t seq, const uint8_t *data, uint32_t len);
int8_t   Comm_ParseFrame(const uint8_t *buf, uint32_t len, Comm_Frame_t *frame);

/* 载荷小端编解码辅助接口（纯函数，无状态） */
int32_t  Comm_GetExpectedDataLen(uint8_t type);
uint32_t Comm_PackCmdVel(uint8_t *out_data, const Comm_CmdVel_t *cmd);
uint8_t  Comm_UnpackCmdVel(const uint8_t *data, uint32_t len, Comm_CmdVel_t *cmd);
uint32_t Comm_PackCmdMode(uint8_t *out_data, const Comm_CmdMode_t *cmd);
uint8_t  Comm_UnpackCmdMode(const uint8_t *data, uint32_t len, Comm_CmdMode_t *cmd);
uint32_t Comm_PackCmdAction(uint8_t *out_data, const Comm_CmdAction_t *cmd);
uint8_t  Comm_UnpackCmdAction(const uint8_t *data, uint32_t len, Comm_CmdAction_t *cmd);
uint32_t Comm_PackTelemetry(uint8_t *out_data, const Comm_Telemetry_t *tlm);
uint8_t  Comm_UnpackTelemetry(const uint8_t *data, uint32_t len, Comm_Telemetry_t *tlm);

#ifdef __cplusplus
}
#endif

#endif /* __COMM_PROTOCOL_H */
