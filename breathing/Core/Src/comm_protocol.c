#include "comm_protocol.h"
#include <stddef.h>

static void Comm_WriteU16LE(uint8_t *dst, uint16_t val)
{
    dst[0] = (uint8_t)(val & 0xFFU);
    dst[1] = (uint8_t)((val >> 8) & 0xFFU);
}

static uint16_t Comm_ReadU16LE(const uint8_t *src)
{
    return (uint16_t)((uint16_t)src[0] | ((uint16_t)src[1] << 8));
}

int32_t Comm_GetExpectedDataLen(uint8_t type)
{
    switch (type)
    {
        case COMM_TYPE_CMD_POLL:
            return (int32_t)COMM_LEN_CMD_POLL;
        case COMM_TYPE_CMD_VEL:
            return (int32_t)COMM_LEN_CMD_VEL;
        case COMM_TYPE_CMD_STOP:
            return (int32_t)COMM_LEN_CMD_STOP;
        case COMM_TYPE_CMD_MODE:
            return (int32_t)COMM_LEN_CMD_MODE;
        case COMM_TYPE_CMD_ACTION:
            return (int32_t)COMM_LEN_CMD_ACTION;
        case COMM_TYPE_TELEMETRY:
            return (int32_t)COMM_LEN_TELEMETRY;
        default:
            return -1;
    }
}

uint8_t Comm_Crc8(const uint8_t *data, uint32_t len)
{
    uint8_t crc = COMM_CRC8_INIT;

    if (data == NULL)
    {
        return (uint8_t)(crc ^ COMM_CRC8_XOROUT);
    }

    for (uint32_t i = 0U; i < len; i++)
    {
        crc ^= data[i];
        for (uint8_t bit = 0U; bit < 8U; bit++)
        {
            if ((crc & 0x80U) != 0U)
            {
                crc = (uint8_t)((uint8_t)(crc << 1U) ^ COMM_CRC8_POLY);
            }
            else
            {
                crc = (uint8_t)(crc << 1U);
            }
        }
    }

    return (uint8_t)(crc ^ COMM_CRC8_XOROUT);
}

uint32_t Comm_BuildFrame(uint8_t *out, uint8_t type, uint8_t seq, const uint8_t *data, uint32_t len)
{
    int32_t expected_len;

    if (out == NULL)
    {
        return 0U;
    }

    if ((len > COMM_FRAME_MAX_DATA_LEN) || ((len > 0U) && (data == NULL)))
    {
        return 0U;
    }

    expected_len = Comm_GetExpectedDataLen(type);
    if ((expected_len < 0) || ((uint32_t)expected_len != len))
    {
        return 0U;
    }

    out[0] = COMM_FRAME_HEADER_0;
    out[1] = COMM_FRAME_HEADER_1;
    out[2] = type;
    out[3] = seq;

    for (uint32_t i = 0U; i < len; i++)
    {
        out[4U + i] = data[i];
    }

    /* CRC8 覆盖 TYPE + SEQ + DATA（共 2 + len 字节），不含帧头/帧尾/CRC 自身 */
    out[4U + len] = Comm_Crc8(&out[2], 2U + len);
    out[5U + len] = COMM_FRAME_TAIL_0;
    out[6U + len] = COMM_FRAME_TAIL_1;

    return COMM_FRAME_OVERHEAD_BYTES + len;
}

int8_t Comm_ParseFrame(const uint8_t *buf, uint32_t len, Comm_Frame_t *frame)
{
    uint32_t data_len;
    int32_t expected_len;
    uint8_t crc_rx;
    uint8_t crc_calc;

    if ((buf == NULL) || (frame == NULL) || (len < COMM_FRAME_MIN_LEN))
    {
        return COMM_PARSE_ERR_LEN;
    }

    if ((buf[0] != COMM_FRAME_HEADER_0) || (buf[1] != COMM_FRAME_HEADER_1))
    {
        return COMM_PARSE_ERR_HEADER;
    }

    if ((buf[len - 2U] != COMM_FRAME_TAIL_0) || (buf[len - 1U] != COMM_FRAME_TAIL_1))
    {
        return COMM_PARSE_ERR_TAIL;
    }

    data_len = len - COMM_FRAME_OVERHEAD_BYTES;
    expected_len = Comm_GetExpectedDataLen(buf[2]);
    if ((expected_len < 0) || (data_len != (uint32_t)expected_len))
    {
        return COMM_PARSE_ERR_LEN;
    }

    crc_rx = buf[4U + data_len];
    crc_calc = Comm_Crc8(&buf[2], 2U + data_len);
    if (crc_rx != crc_calc)
    {
        return COMM_PARSE_ERR_CRC;
    }

    frame->type = buf[2];
    frame->seq = buf[3];
    frame->data_len = data_len;
    frame->crc8 = crc_rx;

    for (uint32_t i = 0U; i < data_len; i++)
    {
        frame->data[i] = buf[4U + i];
    }

    return COMM_PARSE_OK;
}

uint32_t Comm_PackCmdVel(uint8_t *out_data, const Comm_CmdVel_t *cmd)
{
    if ((out_data == NULL) || (cmd == NULL))
    {
        return 0U;
    }

    Comm_WriteU16LE(&out_data[0], (uint16_t)cmd->vx_mmps);
    Comm_WriteU16LE(&out_data[2], (uint16_t)cmd->omega_mradps);
    return COMM_LEN_CMD_VEL;
}

uint8_t Comm_UnpackCmdVel(const uint8_t *data, uint32_t len, Comm_CmdVel_t *cmd)
{
    if ((data == NULL) || (cmd == NULL) || (len != COMM_LEN_CMD_VEL))
    {
        return 0U;
    }

    cmd->vx_mmps = (int16_t)Comm_ReadU16LE(&data[0]);
    cmd->omega_mradps = (int16_t)Comm_ReadU16LE(&data[2]);
    return 1U;
}

uint32_t Comm_PackCmdMode(uint8_t *out_data, const Comm_CmdMode_t *cmd)
{
    if ((out_data == NULL) || (cmd == NULL))
    {
        return 0U;
    }

    out_data[0] = cmd->fusion_mode;
    return COMM_LEN_CMD_MODE;
}

uint8_t Comm_UnpackCmdMode(const uint8_t *data, uint32_t len, Comm_CmdMode_t *cmd)
{
    if ((data == NULL) || (cmd == NULL) || (len != COMM_LEN_CMD_MODE))
    {
        return 0U;
    }

    cmd->fusion_mode = data[0];
    return 1U;
}

uint32_t Comm_PackCmdAction(uint8_t *out_data, const Comm_CmdAction_t *cmd)
{
    if ((out_data == NULL) || (cmd == NULL))
    {
        return 0U;
    }

    out_data[0] = cmd->action_id;
    Comm_WriteU16LE(&out_data[1], (uint16_t)cmd->param);
    return COMM_LEN_CMD_ACTION;
}

uint8_t Comm_UnpackCmdAction(const uint8_t *data, uint32_t len, Comm_CmdAction_t *cmd)
{
    if ((data == NULL) || (cmd == NULL) || (len != COMM_LEN_CMD_ACTION))
    {
        return 0U;
    }

    cmd->action_id = data[0];
    cmd->param = (int16_t)Comm_ReadU16LE(&data[1]);
    return 1U;
}

uint32_t Comm_PackTelemetry(uint8_t *out_data, const Comm_Telemetry_t *tlm)
{
    if ((out_data == NULL) || (tlm == NULL))
    {
        return 0U;
    }

    /*
     * 26 字节遥测载荷小端布局：
     *   [0..7]   rpm[4]          (int16 * 4)
     *   [8..11]  pwm[4]          (int8  * 4)
     *   [12..13] x_mm            (int16)
     *   [14..15] y_mm            (int16)
     *   [16..17] odom_yaw_001deg (int16)
     *   [18..19] imu_yaw_001deg  (int16)
     *   [20]     status          (uint8)
     *   [21]     fusion_mode     (uint8)
     *   [22..23] drop_count      (uint16)
     *   [24..25] timeout_count   (uint16)
     */
    for (uint32_t i = 0U; i < 4U; i++)
    {
        Comm_WriteU16LE(&out_data[i * 2U], (uint16_t)tlm->rpm[i]);
        out_data[8U + i] = (uint8_t)tlm->pwm[i];
    }

    Comm_WriteU16LE(&out_data[12], (uint16_t)tlm->x_mm);
    Comm_WriteU16LE(&out_data[14], (uint16_t)tlm->y_mm);
    Comm_WriteU16LE(&out_data[16], (uint16_t)tlm->odom_yaw_001deg);
    Comm_WriteU16LE(&out_data[18], (uint16_t)tlm->imu_yaw_001deg);
    out_data[20] = tlm->status;
    out_data[21] = tlm->fusion_mode;
    Comm_WriteU16LE(&out_data[22], tlm->drop_count);
    Comm_WriteU16LE(&out_data[24], tlm->timeout_count);

    return COMM_LEN_TELEMETRY;
}

uint8_t Comm_UnpackTelemetry(const uint8_t *data, uint32_t len, Comm_Telemetry_t *tlm)
{
    if ((data == NULL) || (tlm == NULL) || (len != COMM_LEN_TELEMETRY))
    {
        return 0U;
    }

    for (uint32_t i = 0U; i < 4U; i++)
    {
        tlm->rpm[i] = (int16_t)Comm_ReadU16LE(&data[i * 2U]);
        tlm->pwm[i] = (int8_t)data[8U + i];
    }

    tlm->x_mm = (int16_t)Comm_ReadU16LE(&data[12]);
    tlm->y_mm = (int16_t)Comm_ReadU16LE(&data[14]);
    tlm->odom_yaw_001deg = (int16_t)Comm_ReadU16LE(&data[16]);
    tlm->imu_yaw_001deg = (int16_t)Comm_ReadU16LE(&data[18]);
    tlm->status = data[20];
    tlm->fusion_mode = data[21];
    tlm->drop_count = Comm_ReadU16LE(&data[22]);
    tlm->timeout_count = Comm_ReadU16LE(&data[24]);

    return 1U;
}
