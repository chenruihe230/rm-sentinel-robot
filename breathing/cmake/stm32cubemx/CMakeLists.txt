cmake_minimum_required(VERSION 3.22)

project(stm32cubemx)
add_library(stm32cubemx INTERFACE)

# Enable CMake support for ASM and C languages
enable_language(C ASM)

target_compile_definitions(stm32cubemx INTERFACE 
	USE_HAL_DRIVER 
	STM32F407xx
    $<$<CONFIG:Debug>:DEBUG>
)

target_include_directories(stm32cubemx INTERFACE
    ../../Core/Inc
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Inc
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Inc/Legacy
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/CMSIS/Device/ST/STM32F4xx/Include
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/CMSIS/Include
)

target_sources(stm32cubemx INTERFACE
    ../../Core/Src/main.c
    ../../Core/Src/gpio.c
    ../../Core/Src/i2c.c
    ../../Core/Src/tim.c
    ../../Core/Src/stm32f4xx_it.c
    ../../Core/Src/stm32f4xx_hal_msp.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_i2c.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_i2c_ex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_rcc_ex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash_ex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_flash_ramfunc.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_dma_ex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_dma.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_pwr_ex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_cortex.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_exti.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim.c
    D:/stm32/Repository/STM32Cube_FW_F4_V1.28.3/Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim_ex.c
    ../../Core/Src/system_stm32f4xx.c
    ../../Core/Src/sysmem.c
    ../../Core/Src/syscalls.c
    ../../startup_stm32f407xx.s
)

target_link_directories(stm32cubemx INTERFACE
)

target_link_libraries(stm32cubemx INTERFACE
)

# Validate that STM32CubeMX code is compatible with C standard
if(CMAKE_C_STANDARD LESS 11)
    message(ERROR "Generated code requires C11 or higher")
endif()


