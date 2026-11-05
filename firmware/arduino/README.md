# Arduino IDE 上传 ESP32-C3 成品控制器

打开 `JRController_C3/JRController_C3.ino`，保留同目录的全部 `.cpp` 和 `.h` 文件。此草图由 `firmware/export_arduino.py` 从同一份固件源代码生成；修改正式固件后重新运行导出脚本，避免两个版本不同步。

建议解压到全英文路径，例如 `D:\Arduino\JRController_C3`。本机 ESP32 3.3.10 工具链对中文构建输出路径会在链接时失败，Arduino IDE 默认临时构建目录保持英文即可。

Arduino IDE 开发板管理器安装 **esp32 by Espressif Systems**，选择 **ESP32C3 Dev Module**。此草图使用内置 Arduino、Wire 与 Preferences，不需要额外安装显示库。

工具菜单：

- USB CDC On Boot：Enabled
- CPU Frequency：160MHz
- Flash Size：4MB
- Partition Scheme：Default 4MB（默认）
- Erase All Flash Before Sketch Upload：Disabled（保留已有板上校准；新板仍需校准）
- Port：新板实际出现的 COM 口，不一定是旧板 COM7
- Upload Speed：先用 460800，失败时降到 115200

上传前退出 JR 控制器软件和串口监视器。连接 C3 原生 USB 口并点击上传；若提示无法进入下载模式，按住 BOOT，点按 RESET 后松开 BOOT，再上传。完成后重新插拔 USB，打开桌面软件完成主手柄、换向器和四按钮校准。

接线：AS5600 SDA=GPIO6，SCL=GPIO5；点阵 DIN=GPIO4，CS=GPIO3，CLK=GPIO2；换向触点 GPIO7/GPIO1；按钮 GPIO0/10/20/21。与此前 C3 配套载板一致。

固件不会修复屏幕供电压降；此前旧板屏幕端测得 2.8V 的问题需要单独检查。
