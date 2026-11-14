# JR Controller

ESP32-S3 / ESP32-C3 + AS5600 的 JR EAST Train Simulator 单手柄控制器项目，保留第一版电位器方案。

当前桌面版本为 **1.1.6**，详见[版本记录](CHANGELOG.md)。Hidari 2 的 Odoriko 参数和 EB 行为可在「设定 → 模型驾驶」读取和保存。

[下载安装包（v1.1.6）](https://github.com/Lc2007081623/jr-controller/releases/tag/v1.1.6)。[Hidari 2 与 Odoriko 客户说明书](https://github.com/Lc2007081623/jr-controller/releases/download/v1.1.4/Hidari2-Odoriko-User-Manual.pdf)含 LED 点阵速查表。配套的 `SHA256SUMS.txt` 可用于核对发布文件。

在“软件设置”中可以切换主题、查询 GitHub 更新、映射四个实体按键、编辑点阵并开启本机只读 HTTP 接口。游戏模式右侧提供对应的接入步骤。软件显示所连接的板型、传感器与固件版本，并按设备型号匹配内置的 hidari1 或 hidari2 固件。多型号更新流程已通过软件校验，实机刷写尚待验证。

## 安装与使用

1. 从上方发行页面下载 `JRControllerSetup.exe`，退出旧版 JR Controller 和游戏后运行安装包。Windows 10/11 64 位无需另装 Python；安装器会检查并按需安装手柄驱动。
2. 安装时可选择 BVE 5、BVE 6 的游戏目录；不使用 BVE 时可以留空。按提示完成安装，需要时重启电脑。
3. 用数据线连接已烧录、已校准的控制器，打开 JR Controller，进入「模拟驾驶」并选择下表中的游戏模式，然后启动游戏。若未校准，可在程序中打开“设备校准”。
4. 连接或恢复连接后，游戏输入会跟随实体手柄、换向器和按钮的当前位置。开始驾驶前请确认手柄位置及游戏内显示。

| 游戏 | 程序模式 | 游戏设置与操作 |
| --- | --- | --- |
| JR EAST Train Simulator（Steam） | JR EAST（Xbox） | 在 Steam 启用 Steam Input，并应用官方 Tsukasa Mascon 布局。 |
| JR EAST Train Simulator（原生 XInput 直连） | JR EAST（Xbox） | 先运行控制器程序，再按游戏本身的要求启动。不同游戏版本和车型需分别验证。 |
| RUNNING TRAIN | RUNNING TRAIN（ZUIKI） | 在 Steam 中禁用该游戏的 Steam Input。 |
| BVE 5.8 / 6 | BVE 5/6（专用插件） | 在游戏 Preferences → Input device 中勾选 JR Controller；BVE 5 和 6 分别使用对应架构插件。详见 [BVE 接入说明](docs/BVE接入验证.md)。 |
| TRAIN CREW | TRAIN CREW（官方接口） | 游戏输入设备设置启用“外部设备输入/输出”。建议先选择控制器模式，再启动游戏。详见 [TRAIN CREW 接入说明](docs/TRAIN_CREW接入.md)。 |

TRAIN CREW 模式下，A 为气笛，B 为电笛，X 为 EB 警报确认，Y 为联络蜂鸣；实体 B7/B8 对应游戏 B6 常用最大制动，EB 单独保留。BVE 模式下，A 为鸣笛，B 为 ATS 确认，X 为 EB 确认，Y 为 ATS 复位。

本机已验证 TRAIN CREW 的主手柄、F/N/R 和四按钮，以及 BVE 5/6 部分档位和换向；BVE 四按钮的线路效果及其他车型尚未逐一验证。安装包完成四模式自检；详见[安装说明](installer/README.md)和[版本记录](CHANGELOG.md)。

当前 C3 载板的接线、校准和固件资料分别见 [C3 接线与验证](docs/C3接线与验证.md)及 [Arduino 上传说明](firmware/arduino/README.md)。校准保存在控制器中；正常更新固件且不擦除全部 Flash 时保留。

## 第一版技术路线（历史记录）

```mermaid
flowchart LR
    P[电位器与机械卡位] --> S[ESP32-S3 ADC采样与档位校准]
    S -->|USB串口| B[Windows桥接程序]
    B --> X[虚拟Xbox 360 / XInput]
    X --> G[游戏原生绝对档位输入]
```

第一版验证配置：**GPIO3电位器 + MAX7219点阵（DIN6、CS5、CLK4）**，15点校准已保存；GPIO10按钮选择前进，XInput X轴保持换向、Y轴输出主档位。牵引只显示数字，制动显示数字并点亮最右下角LED，N/EB显示N/E。22项自动测试通过，用户已确认游戏链路验证成功。操作详见[点阵与GPIO3验证](docs/点阵与GPIO3验证.md)。

## 第一版验证记录

| 项目 | 状态 |
| --- | --- |
| ESP32-S3 芯片识别，16MB Flash、芯片报告8MB PSRAM | 已读取，未做存储器压力测试 |
| Windows 虚拟 XInput 轴输出与读回 | 已通过 |
| E233 0 番台 P1/P3/B5 直接命中 | 用户观察游戏 HUD 确认 |
| 所有15档、EB、其他车型 | 未逐项实测 |
| S3固件、ADC校准、串口桥接 | 校准已保存，用户确认主档位正常 |
| GPIO10换向前进 | 改为XInput X轴保持后，用户确认验证成功 |
| MAX7219显示 | 已接入第一版；其他按钮待后续实现 |
| 机械回差 | 2026-10-24用户确认已解决 |
| 机械模型、原理图、PCB 设计文件 | 不在公开仓库提供 |

## 第一版 XInput 测试程序

环境：Windows、Python（本机实测为3.12）、Tkinter、用户安装的 ViGEmBus 驱动。ViGEmBus 已结束维护，使用前请阅读[作者说明](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)。本仓库不打包驱动或第三方库。

安装 Python 依赖（PowerShell）：

```powershell
$env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = 'true'
python -m pip install -r test_tools/requirements.txt
```

该变量禁止依赖安装流程自动安装驱动。驱动需单独从[作者官方发行页](https://github.com/nefarius/ViGEmBus/releases)获取，并按本机要求完成安装。

测试顺序：

1. 先启动 `test_tools/启动档位测试.cmd`，或运行 `python test_tools/xinput_notch_test.py`。
2. 确认窗口显示虚拟手柄已连接。真实 Xbox 手柄如果占用较低的 XInput 槽，先正常断开它。
3. 保持测试程序开启，**再启动游戏**。游戏初始化时识别 XInput；运行中才创建虚拟手柄，本次测试没有自动切换输入模式。
4. 进入 E233 0 番台驾驶画面。先选择 N，再测试 P1、P3、B1、B5；点击后默认延迟3秒，切回游戏观察 HUD。
5. 结束前输出 N，再关闭测试窗口。

测试程序没有修改游戏文件或内存。`game_input_probe.py` 仅只读检查本次分析版本的进程状态，地址与版本相关，不能当作跨版本的公共 API。

## 第一版 XInput 档位映射

静态分析发现：游戏存在直接读取 `XInputGetState`、将左摇杆 Y 归一化后转换成牵引/制动目标值的分支。一般档位分支不是“加一档/减一档”，而是写入目标档位。

| 档位 | 左摇杆Y中心值 | 档位 | 左摇杆Y中心值 |
| --- | --- | --- | --- |
| EB | +0.96 | N | 0 |
| B8 | +0.87 | P1 | -0.20 |
| B7 | +0.76 | P2 | -0.40 |
| B6 | +0.655 | P3 | -0.60 |
| B5 | +0.545 | P4 | -0.81 |
| B4 | +0.43 | P5 | -0.96 |
| B3 | +0.32 |  |  |
| B2 | +0.205 |  |  |
| B1 | +0.105 |  |  |

第一版档位测试的 XInput 输出为 `round(Y × 32767)`，当时测试时 X 轴保持0；当前正式程序使用 X 轴输出换向。表中数值来自该版本内置阈值；当前只有P1/P3/B5由用户确认，其他档位、车型特殊分支和外部配置覆盖都需实测。

详见[技术总结](docs/技术总结.md)。

## 硬件

- 当前载板主控：ESP32-C3 4MB，接线见 [C3 接线与验证](docs/C3接线与验证.md)。以下为 S3 第一版及早期参考图设计。
- 电位器：第一版改用低成本 RK097N B10K 三脚单联线性款（2026-10-18 用户确认），单手柄共用牵引与制动。原 ALPS RK09L1120A5F 保留为备选，端子、封装与轴连接件不能直接互换。
- 载板参考图主ADC：GPIO1；按现有图纸经4.7kΩ供电限幅、1kΩ串联和100nF滤波。当前临时实测改用GPIO3，电位器两侧接3V3/GND。
- USB：保留GPIO19/20及板上原生接口。
- 12路按钮：GPIO4–15；换向触点GPIO16/17；独立EB触点GPIO18；校准GPIO21。
- 显示：MAX7219单色8×8，经SN74AHCT125转换3.3V信号到5V。

具体板卡排针、供电路径与机械尺寸仍需实物核对。A0图纸采用主控USB供电、显示独立5V、仅共地的安排。


## 目录

| 路径 | 内容 |
| --- | --- |
| `docs/技术总结.md` | 接口分析结论、验证过程、限制和实现计划 |
| `docs/点阵与GPIO3验证.md` | 当前接线、数字与制动角灯、重新校准步骤 |
| `docs/第一版验证.md` | 历史GPIO5/OLED接线 |
| `firmware/` | ESP32-S3 ADC3 + MAX7219固件，保留独立点阵测试与旧OLED环境 |
| `test_tools/` | 手动XInput档位测试、只读诊断、依赖说明 |

游戏文件、提取数据、本机运行日志、驱动安装包与私人附件不包含在仓库中。TRAIN CREW 官方 SDK 的 DLL 按作者许可随项目提供，详见其附带说明。
