#include "imu.h"
#include "i2c.h"
#include <math.h>

#define IMU_PI                  3.14159265f
#define IMU_TWO_PI              (2.0f * IMU_PI)
#define IMU_DEG2RAD             (IMU_PI / 180.0f)

/* 0x39(GZ) 到 0x3f(Yaw) 共 7 个 16-bit 寄存器 = 14 字节 */
#define IMU_BURST_START_REG     IMU_REG_GZ
#define IMU_BURST_READ_LEN      14U

/* 保险循环计数上限（防止调试器关闭 DWT 时卡住，168 MHz 下约数毫秒） */
#define IMU_MAX_POLL_LOOPS      350000U

uint8_t imuAvailable = 0U;
float   imuYaw0 = 0.0f;
float   imuYawSign = 1.0f;
float   imuYawOffsetRad = 0.0f;
float   imuRawYawRad = 0.0f;
float   imuYawRad = 0.0f;
float   imuYawRateRads = 0.0f;

static uint8_t imuZeroCaptured = 0U;
static uint8_t imuConfigured = 0U;
static uint8_t imuWarmupCount = 0U;

static float IMU_WrapToPi(float angle)
{
    if ((angle - angle) != 0.0f)
    {
        return 0.0f;
    }

    angle = fmodf(angle + IMU_PI, IMU_TWO_PI);
    if (angle <= 0.0f)
    {
        angle += IMU_TWO_PI;
    }

    return angle - IMU_PI;
}

static void IMU_DwtInit(void)
{
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
}

static uint32_t IMU_GetTimeoutCycles(uint32_t timeout_ms)
{
    uint32_t sys_hz = SystemCoreClock;
    if (sys_hz == 0U)
    {
        sys_hz = 168000000U;
    }
    return (sys_hz / 1000U) * timeout_ms;
}

static void IMU_DwtDelayUs(uint32_t delay_us)
{
    uint32_t start = DWT->CYCCNT;
    uint32_t ticks = (SystemCoreClock / 1000000U) * delay_us;
    uint32_t loops = 0U;

    while (((DWT->CYCCNT - start) < ticks) && (loops < IMU_MAX_POLL_LOOPS))
    {
        loops++;
    }
}

/* I2C2 异常恢复：仅操作寄存器，不调用任何依赖 HAL_GetTick 的函数 */
static void IMU_BusRecover(void)
{
    I2C_TypeDef *i2c = hi2c2.Instance;
    if (i2c == NULL)
    {
        return;
    }

    i2c->CR1 |= I2C_CR1_STOP;
    i2c->CR1 |= I2C_CR1_SWRST;
    IMU_DwtDelayUs(2U);
    i2c->CR1 &= ~I2C_CR1_SWRST;

    hi2c2.State = HAL_I2C_STATE_RESET;
    MX_I2C2_Init();
}

/*
 * 等待 SR1 指定标志位，带 DWT->CYCCNT 2 ms 硬超时与 NACK/错误立即退出。
 * 返回 1 = 成功，0 = 超时或总线错误（绝不依赖 HAL_GetTick）。
 */
static uint8_t IMU_WaitSr1Flag(I2C_TypeDef *i2c,
                               uint32_t flag,
                               uint32_t start_cyc,
                               uint32_t timeout_cyc)
{
    uint32_t loops = 0U;

    while ((i2c->SR1 & flag) == 0U)
    {
        uint32_t sr1 = i2c->SR1;

        /* NACK / 仲裁丢失 / 总线错误：立即清标志并发 STOP 退出 */
        if ((sr1 & (I2C_SR1_AF | I2C_SR1_ARLO | I2C_SR1_BERR)) != 0U)
        {
            i2c->SR1 &= ~(I2C_SR1_AF | I2C_SR1_ARLO | I2C_SR1_BERR);
            i2c->CR1 |= I2C_CR1_STOP;
            return 0U;
        }

        if (((DWT->CYCCNT - start_cyc) > timeout_cyc) || (++loops > IMU_MAX_POLL_LOOPS))
        {
            IMU_BusRecover();
            return 0U;
        }
    }

    return 1U;
}

static uint8_t IMU_WaitNotBusy(I2C_TypeDef *i2c,
                               uint32_t start_cyc,
                               uint32_t timeout_cyc)
{
    uint32_t loops = 0U;

    if ((i2c->CR1 & I2C_CR1_PE) == 0U)
    {
        i2c->CR1 |= I2C_CR1_PE;
    }

    while ((i2c->SR2 & I2C_SR2_BUSY) != 0U)
    {
        if (((DWT->CYCCNT - start_cyc) > timeout_cyc) || (++loops > IMU_MAX_POLL_LOOPS))
        {
            IMU_BusRecover();
            return 0U;
        }
    }

    return 1U;
}

/*
 * 向维特 IMU 写 16-bit 寄存器（低字节在前，2 ms DWT 硬超时）。
 */
static uint8_t IMU_WriteRegDwt(uint8_t reg, uint16_t val)
{
    I2C_TypeDef *i2c = hi2c2.Instance;
    uint32_t start_cyc = DWT->CYCCNT;
    uint32_t timeout_cyc = IMU_GetTimeoutCycles(IMU_I2C_TIMEOUT_MS);

    if (i2c == NULL)
    {
        return 0U;
    }

    if (!IMU_WaitNotBusy(i2c, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->CR1 &= ~I2C_CR1_POS;
    i2c->CR1 |= I2C_CR1_START;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_SB, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->DR = IMU_I2C_ADDR_WRITE;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_ADDR, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    (void)i2c->SR1;
    (void)i2c->SR2;

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_TXE, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->DR = reg;

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_TXE, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->DR = (uint8_t)(val & 0xFFU);

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_TXE, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->DR = (uint8_t)((val >> 8) & 0xFFU);

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_BTF, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->CR1 |= I2C_CR1_STOP;
    return 1U;
}

/*
 * 从维特 IMU 连续读取 len 字节（len >= 3，此处固定 14 字节，2 ms DWT 硬超时）。
 */
static uint8_t IMU_ReadBurst14Dwt(uint8_t start_reg, uint8_t *buf)
{
    I2C_TypeDef *i2c = hi2c2.Instance;
    uint32_t start_cyc = DWT->CYCCNT;
    uint32_t timeout_cyc = IMU_GetTimeoutCycles(IMU_I2C_TIMEOUT_MS);

    if ((i2c == NULL) || (buf == NULL))
    {
        return 0U;
    }

    if (!IMU_WaitNotBusy(i2c, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->CR1 &= ~I2C_CR1_POS;
    i2c->CR1 |= I2C_CR1_ACK;

    /* 1. 发送 START + 写地址 + 寄存器首地址 */
    i2c->CR1 |= I2C_CR1_START;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_SB, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->DR = IMU_I2C_ADDR_WRITE;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_ADDR, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    (void)i2c->SR1;
    (void)i2c->SR2;

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_TXE, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->DR = start_reg;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_TXE, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    /* 2. 发送 Repeated START + 读地址 */
    i2c->CR1 |= I2C_CR1_START;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_SB, start_cyc, timeout_cyc))
    {
        return 0U;
    }

    i2c->DR = IMU_I2C_ADDR_READ;
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_ADDR, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    (void)i2c->SR1;
    (void)i2c->SR2;

    /* 3. 读取前 11 字节（0 .. 10） */
    for (uint32_t i = 0U; i < (IMU_BURST_READ_LEN - 3U); i++)
    {
        if (!IMU_WaitSr1Flag(i2c, I2C_SR1_RXNE, start_cyc, timeout_cyc))
        {
            return 0U;
        }
        buf[i] = (uint8_t)i2c->DR;
    }

    /* 4. RM0090 标准最后 3 字节关闭 ACK 与发送 STOP 时序 */
    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_BTF, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->CR1 &= ~I2C_CR1_ACK;
    buf[IMU_BURST_READ_LEN - 3U] = (uint8_t)i2c->DR;

    if (!IMU_WaitSr1Flag(i2c, I2C_SR1_BTF, start_cyc, timeout_cyc))
    {
        return 0U;
    }
    i2c->CR1 |= I2C_CR1_STOP;
    buf[IMU_BURST_READ_LEN - 2U] = (uint8_t)i2c->DR;
    buf[IMU_BURST_READ_LEN - 1U] = (uint8_t)i2c->DR;

    return 1U;
}

static uint8_t IMU_ConfigureRegisters(void)
{
    /* 1. 写配置前必须先写 KEY=0x69 (0xB588) 解锁 */
    if (!IMU_WriteRegDwt(IMU_REG_KEY, IMU_KEY_UNLOCK))
    {
        return 0U;
    }
    IMU_DwtDelayUs(200U);

    /* 2. AXIS6=0x24 写 1（6 轴模式，不使用磁力计） */
    if (!IMU_WriteRegDwt(IMU_REG_AXIS6, IMU_AXIS6_6DOF))
    {
        return 0U;
    }
    IMU_DwtDelayUs(200U);

    /* 3. RRATE=0x03 写 0x09（100 Hz 输出速率） */
    if (!IMU_WriteRegDwt(IMU_REG_RRATE, IMU_RRATE_100HZ))
    {
        return 0U;
    }
    IMU_DwtDelayUs(200U);

    /* 4. RSW=0x02 写 0x0C（RSW_ANGLE 0x08 | RSW_GYRO 0x04；不写 0x53） */
    if (!IMU_WriteRegDwt(IMU_REG_RSW, IMU_RSW_GYRO_ANGLE))
    {
        return 0U;
    }
    IMU_DwtDelayUs(200U);

    return 1U;
}

void IMU_Init(void)
{
    IMU_DwtInit();

    imuAvailable = 0U;
    imuYaw0 = 0.0f;
    imuRawYawRad = 0.0f;
    imuYawRad = 0.0f;
    imuYawRateRads = 0.0f;
    imuZeroCaptured = 0U;
    imuConfigured = 0U;
    imuWarmupCount = 100U; /* 等待 IMU 上电启动收敛（手册启动时间 1000 ms） */

    if (IMU_ConfigureRegisters())
    {
        imuConfigured = 1U;
    }
}

void IMU_Update10ms(void)
{
    uint8_t buf[IMU_BURST_READ_LEN];

    /* 若上电瞬间 IMU 尚未就绪，后续在线时自动补发一次 6 轴/100Hz 配置 */
    if (imuConfigured == 0U)
    {
        if (IMU_ConfigureRegisters())
        {
            imuConfigured = 1U;
        }
    }

    if (!IMU_ReadBurst14Dwt(IMU_BURST_START_REG, buf))
    {
        imuAvailable = 0U;
        imuYawRateRads = 0.0f;
        return;
    }

    /*
     * 14 字节连读解析（低字节在前）：
     *   buf[0..1]   -> 0x39 GZ
     *   buf[12..13] -> 0x3f Yaw
     */
    int16_t raw_gz  = (int16_t)(((uint16_t)buf[1] << 8) | (uint16_t)buf[0]);
    int16_t raw_yaw = (int16_t)(((uint16_t)buf[13] << 8) | (uint16_t)buf[12]);

    /*
     * 换算依据（wit_c_sdk Main.c）：
     *   GZ (deg/s) = raw_gz / 32768.0f * 2000.0f -> 乘 (pi / 180) 得 rad/s
     *   Yaw (deg)  = raw_yaw / 32768.0f * 180.0f -> 乘 (pi / 180) 得 raw_yaw / 32768.0f * pi (rad)
     */
    float sign = (imuYawSign < 0.0f) ? -1.0f : 1.0f;
    float yaw_raw_rad = ((float)raw_yaw / 32768.0f) * IMU_PI;
    float gz_rads     = ((float)raw_gz / 32768.0f) * 2000.0f * IMU_DEG2RAD * sign;

    imuRawYawRad = yaw_raw_rad;
    imuYawRateRads = gz_rads;

    /* 上电前 1000 ms（100 次 10 ms 采样）持续跟随零点，待模块内部滤波收敛后锁存 imuYaw0 */
    if ((imuZeroCaptured == 0U) || (imuWarmupCount > 0U))
    {
        imuYaw0 = yaw_raw_rad;
        imuZeroCaptured = 1U;
        if (imuWarmupCount > 0U)
        {
            imuWarmupCount--;
        }
    }

    float yaw_rel = IMU_WrapToPi(imuRawYawRad - imuYaw0);
    imuYawRad = IMU_WrapToPi(sign * yaw_rel + imuYawOffsetRad);
    imuAvailable = 1U;
}

void IMU_ResetYawZero(void)
{
    imuYaw0 = imuRawYawRad;
    imuYawRad = IMU_WrapToPi(imuYawOffsetRad);
}

uint8_t IMU_IsAvailable(void)
{
    return imuAvailable;
}

float IMU_GetYaw(void)
{
    if (imuAvailable == 0U)
    {
        return 0.0f;
    }

    float sign = (imuYawSign < 0.0f) ? -1.0f : 1.0f;
    float yaw_rel = IMU_WrapToPi(imuRawYawRad - imuYaw0);
    imuYawRad = IMU_WrapToPi(sign * yaw_rel + imuYawOffsetRad);
    return imuYawRad;
}

float IMU_GetYawRate(void)
{
    if (imuAvailable == 0U)
    {
        return 0.0f;
    }

    return imuYawRateRads;
}
