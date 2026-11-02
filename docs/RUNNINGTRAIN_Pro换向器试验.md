# RUNNING TRAIN：Mascon Pro 换向器研究

日期：2026-11-02。分支：`codex/running-train-reverser`。正式软件基线提交：`50afa5f`。

## 已确认与尚未确认

- 瑞起为 SDL 提交的驱动与 USB ID 定义确认 Mascon Pro 为 `33DD:0006`。
- 该提交读取 8 字节输入：按钮位于 data[0:2]、方向帽 data[2]、四轴 data[3:7]。它只做通用输入解析，**没有注明哪个轴或按钮对应实体换向器**，不能从这个文件确认 F/N/R 编码。
- 原版普通 ZUIKI 的上下键脉冲试验此前已获用户反馈不可用；正式软件 0.3.2 不发送换向操作。
- Pro 拥有实体换向器和机械联锁，不能据此断言游戏已支持其电气输入。开发者只宣布 Pro 部分支持。
- 本地 Windows 已枚举试验设备 `HID#VID_33DD&PID_0006&REV_0100`。这是设备身份枚举成功，**不是游戏换向功能成功**。

## 试验实现

`test_tools/zuiki_pro_probe.py` 创建独立的 Pro 身份虚拟设备，默认只输出 N。使用现有 ViGEmBus，实际 HID 描述符仍为 DS4；未安装新驱动，未刷写固件，未修改游戏文件或校准。

```powershell
# 只检查 Pro 身份枚举，120 秒后自动移除
python test_tools/zuiki_pro_probe.py --seconds 120

# 实体输入 + Rz 轴假设，最多 15 分钟
python test_tools/zuiki_pro_probe.py --serial COM7 --axis rz --seconds 900
```

`--axis x|z|rz` 是三个明确标记的候选轴；暂用 F=0 / N=128 / R=255，`--invert` 反转两端。**这些是排查假设，不是真实 Pro 协议。** 试验保留已验证的主手柄 Y 轴与四按键映射；方向帽始终释放，避免与旧的上下键猜测混淆。

运行前关闭正式控制器软件以释放 COM7 与旧虚拟设备，再启动试验，最后启动游戏。主手柄与换向器回 N、松开按钮后才启用，方向候选值只在主手柄 N 时更新。串口断开、采样异常、超时或退出会释放按钮并恢复 N；主进程正常退出时移除设备。不要在一次试验中同时开启多个探测进程。

2026-11-02 首轮：Windows 枚举成功，COM7 校准有效并通过回 N 启用条件；已在设备存在后启动游戏 0.9.5c EA，等待驾驶画面验证。59 项软件测试通过，但不能用单元测试代替游戏实测。

## 游戏文件检查范围

本地包 `RunningTrain-Windows.pak` 的索引未加密，SHA256：`8a17711f82be4bb9bfb36a82cfbda6fdf48c32da21fbfefc48acd5c2fcb50aaf`。文件清单含 `DefaultInput.ini`、`DefaultEngine.ini` 与 `IMC_Zuiki` 资源。配置内容使用 Oodle 压缩，本轮未解压，**文件名只能说明存在资源，不能证明实际换向映射**。REA 工具未连接；以上不是 REA Evidence。

## 来源

- [瑞起提交的 SDL 驱动（固定提交）](https://github.com/libsdl-org/SDL/blob/fc648e55468cd565e99f1d39735b3383556051db/src/joystick/hidapi/SDL_hidapi_zuiki.c)
- [同提交 USB ID 定义](https://github.com/libsdl-org/SDL/blob/fc648e55468cd565e99f1d39735b3383556051db/src/joystick/usb_ids.h)
- [瑞起 Pro 产品机械结构说明](https://www.zuiki.co.jp/product_examples_own/zuiki-mascon-pro/)
- [开发者关于原生控制器与 Pro 部分支持的发布说明](https://store.steampowered.com/news/posts/?enddate=1779627778&feed=steam_community_announcements)
- [开发者要求关闭 Steam Input](https://steamcommunity.com/app/4630570/discussions/0/838377489360272256/)
