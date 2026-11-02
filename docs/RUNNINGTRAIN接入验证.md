# RUNNING TRAIN：虚拟 ZUIKI 试验

2026-11-01，游戏本地版本 0.9.5c EA，Steam AppID 4630570，安装 buildid 25925974。

## 公开资料

- [Train Controller Database：ZKNS-001](https://traincontrollerdb.marcriera.cat/hardware/zkns001/) 提供 VID/PID、HID 描述符与 15 档轴值：原版为 0F0D:00C1，4 轴、14 按钮、1 POV，主手柄为第二轴，N=128。
- [HID 描述符](https://traincontrollerdb.marcriera.cat/hardware/zkns001/hid-report-descriptor.txt)：没有 Report ID，按钮在前，接着 POV、X/Y/Z/Rz 和填充，输入报告共 8 字节。
- [开发者说明](https://steamcommunity.com/app/4630570/discussions/0/838377489360272256/)：专用控制器需要关闭该游戏的 Steam Input，避免被转成普通手柄。
- [ViGEmClient](https://github.com/nefarius/ViGEmClient/blob/master/include/ViGEm/Client.h) 提供 VID/PID 覆盖，但仅支持 Xbox 360、DS4 两种固定设备描述符，不是任意 HID 仿真框架。
- [HIDMaestro](https://github.com/hifihedgehog/HIDMaestro) 可自定义描述符，但首次运行涉及安装本机信任的自签证书和 UMDF 驱动；本次未运行此安装流程。

## 已做试验

复用本机已有 ViGEmBus，创建 DS4 HID 设备、在加入总线前设置 VID/PID=0F0D:00C1，按公开表把 15 个档位写入 Y 轴。四个物理按钮映射为 ZUIKI 的 A/B/X/Y 对应 HID 按钮，EB 附带 ZL。当前未映射实体换向器。

Windows Raw Input 实际枚举到了 `HID#VID_0F0D&PID_00C1&REV_0100`；游戏设置页与用户均确认出现 `ZUIKI Master Controller`。已接入 COM7 的真实校准状态，日志记录牵引、制动、EB 和按键变化。43 项软件测试通过。

第一轮驾驶反馈：**只有识别，档位没有响应**。因此目前只能确认设备识别成功，不能确认原生驾驶接入成功。DS4 描述符与真实 ZUIKI 描述符仍不同，不能把 VID/PID 相同等同于完整仿真。正在排查设备重建后的重新枚举与报告布局。

后续验证：保持虚拟设备运行并重启游戏后，用户确认“手柄和按键可以，换向器没用”。因此主手柄与按钮已有用户实机确认。换向脉冲逻辑已写入独立试验脚本，但用户随后反馈仍不可用，现按用户要求保留为待解决问题，暂停修复；未合入正式安装包。

## 复现

### 正式软件（0.3.2 起）

主窗口选择“RUNNING TRAIN（ZUIKI）”，等待虚拟设备建立，再启动或重启游戏；关闭该游戏的 Steam Input。选择会保存在本机，下次启动恢复。主手柄和换向器置 N、松开按钮后自动启用。主手柄与四按钮沿用已验证的映射；换向器尚未解决，正式模式仅显示其实体状态，不发送方向操作。校准、断线与传感器异常仍会释放输入。切回 JR EAST（Xbox）会移除 ZUIKI 设备并创建 Xbox 设备，不同时创建两个。

### 独立试验脚本（保留用于排查）

```powershell
python test_tools/zuiki_virtual_test.py --serial COM7 --seconds 900
```

先启动虚拟设备，再启动游戏；主手柄和换向器都置 N、松开按钮后自动输出。运行时长默认受限，结束会移除虚拟设备；串口异常或传感器失效时输出 N，不改写固件或校准。脚本仍保留；主手柄和按钮现已通过适配器集成到正式软件。

REA MCP 未连接，CLI 需要的 Node 版本高于本机；本记录来自普通本地文件检查、Windows API、用户反馈及游戏界面，不是 REA Evidence。
