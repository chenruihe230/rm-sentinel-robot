/**
  ******************************************************************************
  * @file    oled.h
  * @brief   SSD1306 0.96寸 OLED (128x64, I2C) 驱动头文件
  *
  *  特性：
  *    - 基于显存缓冲区绘制，画完后调用 OLED_Refresh() 一次性上屏（无闪烁）
  *    - 支持 6x8 / 8x16 两套 ASCII 字库、数字、十六进制、浮点
  *    - 支持画点/线/矩形/圆、显示图片(BMP)、显示汉字(需字库)
  *
  *  快速上手（main.c 里）：
  *    #include "oled.h"
  *    OLED_Init();                                   // 初始化
  *    OLED_Clear();                                  // 清空缓冲区
  *    OLED_ShowString(0, 0, "Hello", OLED_SIZE_16, OLED_MODE_NORMAL);
  *    OLED_Refresh();                                // 上屏显示
  ******************************************************************************
  */
#ifndef __OLED_H
#define __OLED_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "i2c.h"

/* ===================== 硬件配置（按你的板子改这里） ===================== */
#define OLED_I2C_ADDR    0x78            /* I2C 地址：0x78(SA0=0) / 0x7A(SA0=1) */
#define OLED_I2C_HANDLE  hi2c1           /* 使用的 I2C 句柄 */
#define OLED_WIDTH       128
#define OLED_HEIGHT      64

/* ===================== 字符大小 ===================== */
#define OLED_SIZE_8      8               /* 6x8 小字（8 像素高，宽 6）   */
#define OLED_SIZE_16     16              /* 8x16 大字（16 像素高，宽 8） */

/* ===================== 字符显示模式 ===================== */
#define OLED_MODE_NORMAL  1              /* 正常：透明背景，只画字符   */
#define OLED_MODE_INVERSE 0              /* 反白：填充背景             */

/* ===================== 图形颜色 ===================== */
#define OLED_COLOR_ON     1              /* 点亮像素 */
#define OLED_COLOR_OFF    0              /* 熄灭像素 */

/* ===================== 基础接口 ===================== */
void OLED_Init(void);                     /* 初始化并清屏                 */
void OLED_Clear(void);                    /* 清空缓冲区（全黑）           */
void OLED_Fill(void);                     /* 缓冲区全点亮（全白）         */
void OLED_Refresh(void);                  /* 把缓冲区刷到屏幕（画完调用） */
void OLED_DisplayOn(void);                /* 打开显示                     */
void OLED_DisplayOff(void);               /* 关闭显示                     */

/* ===================== 文字 / 数字 ===================== */
void OLED_ShowChar(uint8_t x, uint8_t y, uint8_t chr, uint8_t size, uint8_t mode);
void OLED_ShowString(uint8_t x, uint8_t y, const char *str, uint8_t size, uint8_t mode);
void OLED_ShowNum(uint8_t x, uint8_t y, uint32_t num, uint8_t len, uint8_t size);
void OLED_ShowSignedNum(uint8_t x, uint8_t y, int32_t num, uint8_t len, uint8_t size);
void OLED_ShowHex(uint8_t x, uint8_t y, uint32_t num, uint8_t len, uint8_t size);
void OLED_ShowFloat(uint8_t x, uint8_t y, float num, uint8_t ilen, uint8_t dlen, uint8_t size);

/* ===================== 图形 ===================== */
void OLED_DrawPoint(uint8_t x, uint8_t y, uint8_t color);
void OLED_DrawLine(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1, uint8_t color);
void OLED_DrawRect(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1, uint8_t color, uint8_t fill);
void OLED_DrawCircle(uint8_t cx, uint8_t cy, uint8_t r, uint8_t color, uint8_t fill);

/* ===================== 图片 / 汉字 ===================== */
/* 图片格式：每字节为一列 8 个像素（bit0 在上），按“页”逐行存放；y 需为 8 的倍数 */
void OLED_ShowBMP(uint8_t x, uint8_t y, uint8_t w, uint8_t h, const uint8_t *bmp);

/* 16x16 汉字：需在 oled.c 的 OLED_Hz16 字库中填入字模（PCtoLCD2002：阴码/逐列式/顺向） */
void OLED_ShowChinese(uint8_t x, uint8_t y, uint8_t index, uint8_t size);

#ifdef __cplusplus
}
#endif

#endif /* __OLED_H */
