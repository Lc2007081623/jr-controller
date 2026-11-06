# BVE 5.8 / 6 接入（0.5.0）

2026-11-06：用户确认 BVE 6 内房线 N/P1/P3/B5/EB 正常；BVE 5 京成线相同档位及 F/N/R 正常。BVE 6 初次接入时观察到实体 COM7 的 F/B8 与游戏 HUD F B8 一致。

## 使用

- 预览版程序：`D:\JRController-BVE\JRControllerBVE.exe`，桌面“JR 控制器 - BVE 预览版”。选择“BVE 5/6（专用插件）”。
- BVE 5：`D:\bve\Input Devices\JRController.Bve.dll`（CLR 2.0 / x86）。
- BVE 6：`D:\BVE6\Input Devices\JRController.Bve.dll`（CLR 4.0 / x64）。
- 游戏右键 → Preferences → Input device → Additional input device → 勾选 JR Controller → OK；两个版本均已配置。
- A：电笛；B：ATS 确认；X：EB 确认；Y：ATS 复位。按压与松开分别触发事件，持续按住不重复触发。
- 预览版的“使用说明”打开 BVE 专用操作页。校准继续使用现有校准窗口。

## 实现边界

沿用现有串口协议、Reader、AutoDriveGate 和校准。Python 桌面程序独占串口，通过会话内命名共享内存 `Local\JRController.BVE.v1` 发布状态，游戏只读该映射，不另开串口，也不模拟键盘。插件使用 BVE 的 `Mackoy.Bvets.IInputDevice` / `LeverMoved` / `KeyDown` / `KeyUp` 接口。

32 字节小端数据：sequence(u32)、magic(u32, 0x4A524256)、GetTickCount毫秒(u32)、notch(i32, -9=EB/-8…-1=B8…B1/0=N/1…5=P1…P5)、reverser(i32,-1/0/1)、buttons(i32,0…15)、enabled(i32,0/1)、sequence副本(u32)。先写奇数序号，完成负载后发布相同偶数序号。读端检查双序号及再次读取首序号，拒绝撕裂帧、非法值、超过500ms的心跳。

车型档位范围来自 SetAxisRanges：双手柄走轴1/2，单手柄走轴3，换向走轴0。P1–P5按最大动力档缩放，B1–B8按最大常用制动档缩放；最大制动档留给EB。京成线制动 HUD 显示角度，不要求显示 B 字样。

仅在收到有效且 enabled 的状态后接管。失去桥接心跳、校准/传感器故障、切换模式或退出后，撤销动力、换向回N、释放按钮并输出EB一次。随后不持续覆盖键盘；重连后按项目现有行为立即跟随实体当前位置。切换到其他游戏前先退出 BVE。游戏暂停或卡死期间不能保证实时处理保护事件。

## 构建与检查

```powershell
.\bve_plugin\build.ps1 -Test
python -m unittest discover -s test_tools -p 'test_*.py'
```

插件依赖 BVE 安装目录中的官方接口 DLL，不在源码仓库复制其二进制。默认路径为 D:\bve 和 D:\BVE6，可用 build.ps1 的 -Bve5/-Bve6 参数指定其他路径。DLL 输出到 build/bve/BVE5 和 BVE6。自动测试使用独立映射，不接触实机输入。

独立预览版打包：

```powershell
$guide = Join-Path (Get-Location) 'installer\first_steps.html'
$bveGuide = Join-Path (Get-Location) 'installer\bve_guide.html'
python -m PyInstaller --noconfirm --onedir --windowed --name JRControllerBVE --collect-all vgamepad --distpath release/bve --workpath build/bve-app --specpath build --add-data "$guide;." --add-data "$bveGuide;." test_tools/controller_app.py
```

2026-11-06：正式 0.5.0 完整离线安装包已集成 BVE 插件。安装时可选择游戏目录，留空时插件随正式用户程序放在 BVE Plugins 文件夹，之后可手动复制。正式用户版入口为桌面 JR Controller；上文独立预览版路径与打包命令仅保留作开发记录。

验证：79项Python测试通过；两个CLR/架构的插件事件测试覆盖15档、双/单手柄、车型档位缩放、按钮按下/松开、撕裂帧、过期帧、超时EB、禁用释放与重连。尚未逐项人工确认四按钮的线路效果、全部中间档、其他车型或其他电脑。

接口研究参考作者源码：[BveNumerousControllerInterface](https://github.com/kusaanko/BveNumerousControllerInterface)，本次参考提交 5512ff514f2c1f7cef0d6b487ead56851153f219；本插件独立实现，没有复制第三方代码或引入其依赖。
