# 单块 MAX7219 8×8 点阵：依次显示 1～9

本测试按 MAX7219 模块实现，每次静态显示一个数字，每隔 1 秒切换，按 1～9 循环，上电立即显示 1。

| 模块输入端 | ESP32-S3 |
| --- | --- |
| DIN | GPIO6 |
| CS / LOAD | GPIO5 |
| CLK | GPIO4 |
| GND | GND，共地 |
| VCC | 5V |

信号接模块的 DIN 输入端，不接 DOUT 输出端。GPIO5 本次作为输出，原电位器滑动端如仍接 GPIO5，须先断开。
MAX7219 在 5V 供电时要求逻辑高电平至少 3.5V；ESP32-S3 的 3.3V 直连不保证可靠。
建议 DIN、CS、CLK 经 5V 供电的 74AHCT125 电平转换，输出使能接低电平。
参考：[MAX7219 数据手册](https://www.analog.com/media/en/technical-documentation/data-sheets/max7219-max7221.pdf)。

在仓库根目录运行：

```powershell
pio run -d firmware -e s3_matrix_scroll
pio run -d firmware -e s3_matrix_scroll -t upload --upload-port COM4
pio device monitor -p COM4 -b 115200
```

源码为 `src/matrix_scroll.cpp`，不需要额外点阵库。
`DIGIT_INTERVAL_MS` 设置数字切换间隔，当前为 1000 ms；`BRIGHTNESS` 为 0～15。文件名和编译环境名沿用初版命名。
模块装配方向各异，如果数字旋转，调整 `ROTATION`（0～3）；左右镜像时调整 `MIRROR_X`。

2026-10-21更新：默认 `s3_uart` 已整合点阵与GPIO3采样，显示牵引数字、制动数字加右下角LED、N与E，见[验证步骤](../docs/点阵与GPIO3验证.md)。本独立循环测试环境继续保留。
原OLED源码归档为 `src/main_oled.cpp`，环境为 `s3_oled_legacy`，恢复前须恢复旧接线。
