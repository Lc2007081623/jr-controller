"""Plain-language first-run guides for each existing output mode."""
from output_profiles import XBOX, ZUIKI, BVE, TRAIN_CREW

GUIDES = {
    XBOX: (
        '先连接控制器，打开本程序并选中 JR EAST（Xbox）。确认主手柄和换向器在软件里能跟随。',
        'Steam 版：在库中点游戏页面的控制器图标，开启 Steam Input。在当前布局里选择官方 Tsukasa Mascon，点应用布局。',
        '支持原生 XInput 的版本：保持本程序开启后启动游戏，直接测试输入。游戏是否需要 Steam 启动由游戏本身决定。',
        '进入单手柄车型，停车检查 N、P1、B1、EB 和 F/N/R。没反应时，保持本程序开启并重启游戏。',
    ),
    ZUIKI: (
        '连接控制器并选择 RUNNING TRAIN（ZUIKI）。',
        '在 Steam 库右键游戏，打开属性 → 控制器，把该游戏的 Steam Input 设为禁用。',
        '本程序显示控制器已就绪后再启动游戏。游戏已经运行时请退出并重开。',
        '进入驾驶画面，停车检查档位、F/N/R 和按钮。游戏内的车辆联锁仍生效。',
    ),
    BVE: (
        '连接控制器并选择 BVE 5/6（专用插件）。',
        '将安装目录 BVE Plugins 里的对应 DLL 复制到游戏的 Input Devices。BVE5 选 32 位，BVE6 选 64 位。',
        '启动 BVE，右键驾驶画面 → Preferences → Input device，勾选 JR Controller 并点 OK。',
        '停车确认主手柄和换向器。车型档位较少时，部分实体档位会映射到同一游戏档。',
    ),
    TRAIN_CREW: (
        '连接控制器，先打开本程序并选择 TRAIN CREW（官方接口）。',
        '随后启动游戏，在设置 → 操作设置里启用外部设备输入输出。游戏菜单仍用鼠标或键盘。',
        'A 气笛，B 电笛，X 警报确认，Y 联络蜂鸣。B7 和 B8 对应游戏的最大常用制动。',
        '如果提示接口未就绪，请先退出游戏，等本程序就绪后重新启动游戏。',
    ),
}
