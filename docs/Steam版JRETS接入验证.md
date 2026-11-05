# Steam 版 JR EAST Train Simulator

2026-11-05：目标为 Steam 体验版（App ID 3214350），目录 `E:\steam\steamapps\common\JRETSDemo`，游戏显示版本 1.0.1.551。

## 设置

1. JR Controller 选择 **JR EAST（Xbox）**，先保持软件运行，再启动游戏。
2. Steam 库选择游戏，点击开始按钮右侧的控制器图标。
3. 保持 **使用 Steam 输入** 开启。点击“当前按键布局”，选择官方 **Tsukasa Mascon**，点击“应用布局”。
4. 返回后确认当前布局标题已变为 Tsukasa Mascon。进入驾驶画面逐档核对 HUD。

这是 Steam 中的设置，游戏内的显示／音效设置没有该选项。此设置只针对 JR EAST；RUNNING TRAIN 仍使用原来的 ZUIKI 模式并关闭 Steam Input。

## 依据与当前验证范围

游戏自带 `controller_config/controller_xbox360.vdf` 的默认 Xbox360 Basic 布局将左摇杆映射为换向增减，十字键映射为主手柄增减，不能据此认定绝对档位已接通。

`controller_TsukasaMascon.vdf` 的 DrivingControls 激活 group 33，使用 `joystick_move`、`deadzone_enable_type=0`、游戏动作 `Mascon2`。Steam 布局预览显示左摇杆为 Master Controller (Tsukasa Spec)。

本次已实际应用 Tsukasa Mascon，恢复驾驶后观察到游戏 HUD 从 B6 变为 B8，说明模拟轴路径开始生效。随后用户按 N、P1、P5、B1、EB 与 F/N/R 的验证要求实测，回复“全部正常”。主手柄与换向器按本次用户验证记为通过；四个按钮具体游戏功能及全部中间档位尚未逐项记录。

本次复用现有 Xbox 后端，没有修改固件、游戏程序或输出轴值。Steam 布局需要在其他电脑上分别选择。
