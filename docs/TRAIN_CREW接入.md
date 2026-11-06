# TRAIN CREW 接入

本机游戏：`E:\steam\steamapps\common\TRAIN_CREW_Prologue\TrainCrew.exe`。

选择 JR Controller 的「TRAIN CREW（官方接口）」模式；游戏输入设备设置启用「外部输入/输出」。菜单仍用鼠标或键盘。接口输出只面向驾驶画面，不提供菜单按键导航。

启动顺序：先退出游戏，在JR Controller选择本模式并就绪，再从Steam启动游戏。本机游戏先开启外部接口时，官方SDK的MemoryMappedFile.CreateOrOpen报告访问被拒绝；SDK先启动可以完成初始化。

使用 [Acty官方开发接口](https://acty-soft.com/traincrew/controller/)，2025-11-16 SDK，未修改 `TrainCrewInput.dll`。DLL按作者许可随自行开发的软件打包，未将整个开发包放入安装器。官方DLL SHA256：`ab0c63b8ca309bdfb51c1a4046e33dcfca780841c5729fbdcc5917a73f261bea`。

Python桌面程序复用串口与校准，向独立.NET桥接进程发送绝对状态，由其调用SDK。桥接不依赖游戏安装位置，不修改游戏程序；使用Windows自带.NET Framework 4.x。每20ms传递心跳；超过1秒无新数据、校准暂停、数据失效或退出时发送紧急制动并释放方向与按钮。

| 实体 | 游戏 |
| --- | --- |
| P1～P5、N | 对应牵引、空挡 |
| B1～B6 | B1～B6 |
| B7、B8 | B6，最大常用 |
| EB | 紧急制动 |
| F/N/R | 前进/空挡/后退 |
| A/B | 气笛/电笛 |
| X/Y | EB装置警报确认/联络蜂鸣 |

SDK的一参数SetNotch中：N=0，P1～P5=1～5，B1～B6=-2～-7，EB=-8。保留独立EB，不将实体B7/B8误作紧急制动。游戏侧换向联锁由游戏处理。双手柄车型和电磁直通制动车辆需另行验证。

构建：`python train_crew/build.py`；正式打包由 `python installer/build.py` 自动构建桥接并加入载荷。测试覆盖制动范围、绝对状态、方向与按钮保持、失联紧急输出、关闭释放、游戏模式选择与持续心跳。

## 本机验证（2026-11-06）

- 游戏版本1.0.20261018.23，1261次列车，已在游戏设置启用「外部设备输入/输出」。进入驾驶室后官方SDK初始化及状态回读正常。
- 0.6.0正式安装器在23:00:43完成安装，无需重启；安装日志记录四个模式自检全部通过。安装后的JRController.exe与release/app中的程序SHA256一致。
- 正式安装目录程序已选择TRAIN CREW模式，自动连接COM7，界面显示P4/F；独立只读SDK监测同时读到游戏P4、前进和速度变化，随后记录到P1～P5及N的变化。
- 用户进一步确认N、B1、B5、B7/B8、EB、F/N/R及A气笛、B电笛、X警报确认、Y联络蜂鸣全部正常。
- 84项Python测试及BVE双架构测试通过。未验证其他TRAIN CREW车型、双手柄与电磁直通制动分支，也未在另一台全新电脑上验证安装。

本机只读采样记录位于 `D:\TRAIN-CREW-Adapter\physical-test.log`；仅调用SDK的状态读取，不发送控制输入。验证完成后结束监测，保留正式控制器程序和游戏运行。
