"""Settings and the 8 × 8 pattern editor."""
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from serial_protocol import NOTCH_ORDER
from update_check import VERSION, RELEASES, check_update

THEMES = {
    '经典浅色': ('#F3F6FC', '#FFFFFF', '#14243B', '#53647C', '#2563EB', '#EDF2FA', '#16846A', '#B37412', '#D34C5E'),
    '绿色': ('#EAF5EE', '#FFFFFF', '#123527', '#496858', '#147352', '#DBEEE2', '#147352', '#88560F', '#B5334B'),
    '深色': ('#101722', '#1B2635', '#F1F5FC', '#B0BDD0', '#3463C3', '#2B394C', '#65D5A5', '#F4C06A', '#FF8797'),
}
DEFAULT_LED = dict(enabled=True, brightness=2, rotation=3, patterns={})
DEFAULT_PORT = 8765

def led_settings(value):
    if not isinstance(value, dict):
        value = {}
    result = DEFAULT_LED | value
    if (type(result['enabled']) is not bool
            or type(result['brightness']) is not int or not 0 <= result['brightness'] <= 15
            or type(result['rotation']) is not int or not 0 <= result['rotation'] <= 3
            or not isinstance(result['patterns'], dict)):
        return DEFAULT_LED.copy()
    patterns = {key: frame for key, frame in result['patterns'].items()
                if key in NOTCH_ORDER and isinstance(frame, str) and re.fullmatch('[0-9a-f]{16}', frame)}
    return dict(enabled=result['enabled'], brightness=result['brightness'],
                rotation=result['rotation'], patterns=patterns)

def led_command(settings):
    patterns = settings['patterns']
    mask = sum(1 << i for i, notch in enumerate(NOTCH_ORDER) if notch in patterns)
    frames = ''.join(patterns.get(notch, '0' * 16) for notch in NOTCH_ORDER)
    return f"LED {int(settings['enabled'])}{settings['rotation']}{settings['brightness']:x}{mask:04x}{frames}"

class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title('软件设置')
        self.window.geometry('620x610')
        self.window.transient(app.root)
        self.window.configure(bg=THEMES[app.theme][0])
        tabs = ttk.Notebook(self.window)
        tabs.pack(fill='both', expand=True, padx=14, pady=14)
        general = ttk.Frame(tabs, padding=18)
        matrix = ttk.Frame(tabs, padding=18)
        tabs.add(general, text='常规与更新')
        tabs.add(matrix, text='LED 点阵')
        hardware = ttk.Frame(tabs, padding=18)
        tabs.add(hardware, text='硬件与固件')
        app.updater.add_controls(hardware)
        self.general(general)
        self.matrix(matrix)

    def general(self, parent):
        ttk.Label(parent, text='外观', style='Section.TLabel').pack(anchor='w')
        theme = ttk.Combobox(parent, values=tuple(THEMES), state='readonly')
        theme.set(self.app.theme)
        theme.pack(anchor='w', pady=(6, 18))

        def change_theme(event):
            if self.app.save_preferences(theme=theme.get()):
                self.app.set_theme(theme.get())
                self.window.configure(bg=THEMES[self.app.theme][0])
            else:
                theme.set(self.app.theme)

        theme.bind('<<ComboboxSelected>>', change_theme)
        ttk.Label(parent, text='本机 HTTP 接口', style='Section.TLabel').pack(anchor='w')
        enabled = tk.BooleanVar(value=self.app.api_enabled)
        port = tk.StringVar(value=str(self.app.api_port))
        ttk.Checkbutton(parent, text='允许本机软件读取控制器状态', variable=enabled).pack(anchor='w', pady=5)
        row = ttk.Frame(parent)
        row.pack(anchor='w')
        ttk.Label(row, text='端口').pack(side='left')
        ttk.Entry(row, textvariable=port, width=8).pack(side='left', padx=8)
        endpoint = ttk.Label(parent, wraplength=540)
        api_feedback = ttk.Label(parent, wraplength=540)

        def apply_api():
            try:
                value = int(port.get())
                if not 1024 <= value <= 65535:
                    raise ValueError
            except ValueError:
                api_feedback.configure(text='端口请输入 1024 到 65535 之间的整数。')
                return
            api_feedback.configure(text=self.app.configure_api(enabled.get(), value))
            refresh_endpoint()

        def refresh_endpoint():
            endpoint.configure(text=f'http://127.0.0.1:{self.app.api_port}/v1/state'
                               if self.app.state_api else '接口当前关闭')

        def copy_endpoint():
            if self.app.state_api:
                self.window.clipboard_clear()
                self.window.clipboard_append(endpoint.cget('text'))

        ttk.Button(row, text='应用', command=apply_api).pack(side='left')
        ttk.Button(row, text='复制地址', command=copy_endpoint).pack(side='left', padx=5)
        refresh_endpoint()
        endpoint.pack(anchor='w', pady=(6, 0))
        api_feedback.pack(anchor='w')
        ttk.Label(parent, text='只接受本机读取。返回档位、F/N/R、按键位掩码及数据有效性。',
                  wraplength=540, style='Muted.TLabel').pack(anchor='w', pady=(2, 18))
        ttk.Separator(parent).pack(fill='x', pady=(0, 14))
        ttk.Label(parent, text=f'软件更新 · 当前版本 {VERSION}', style='Section.TLabel').pack(anchor='w')
        self.update_status = ttk.Label(parent, wraplength=540, style='Muted.TLabel')
        self.update_status.pack(anchor='w', pady=8)
        row = ttk.Frame(parent)
        row.pack(anchor='w')
        self.update_button = ttk.Button(row, text='查询更新', command=self.start_check)
        self.update_button.pack(side='left')
        ttk.Button(row, text='打开 GitHub 发布页', command=lambda: webbrowser.open(RELEASES)).pack(side='left', padx=8)

    def start_check(self):
        self.update_button.state(['disabled'])
        self.update_status.configure(text='正在查询 GitHub…')
        result = queue.Queue(maxsize=1)

        def worker():
            try:
                tag, newer = check_update()
                if newer:
                    message = f'发现新版本 {tag}。打开发布页下载新版安装包。'
                else:
                    message = f'GitHub 最新版本为 {tag}，当前无需更新。'
            except Exception:
                message = '查询失败。请检查网络连接，或直接打开 GitHub 发布页。'
            result.put(message)

        def poll():
            try:
                message = result.get_nowait()
            except queue.Empty:
                self.window.after(100, poll)
                return
            self.update_status.configure(text=message)
            self.update_button.state(['!disabled'])

        threading.Thread(target=worker, daemon=True).start()
        self.window.after(100, poll)

    def matrix(self, parent):
        config = self.app.led_settings
        self.patterns = config['patterns'].copy()
        enabled = tk.BooleanVar(value=config['enabled'])
        brightness = tk.StringVar(value=str(config['brightness']))
        angles = ('0°', '顺时针 90°', '180°', '逆时针 90°')
        row = ttk.Frame(parent)
        rotation = ttk.Combobox(row, values=angles, state='readonly', width=13)
        rotation.current(config['rotation'])
        row.pack(fill='x', pady=(0, 10))
        ttk.Checkbutton(row, text='显示点阵', variable=enabled).pack(side='left')
        ttk.Label(row, text='亮度 0–15').pack(side='left', padx=(14, 4))
        ttk.Spinbox(row, from_=0, to=15, width=4, textvariable=brightness).pack(side='left')
        rotation.pack(side='left', padx=12)
        ttk.Label(parent, text='选择档位，点击格子切换亮灭。图案按旋转前的方向编辑。',
                  wraplength=540).pack(anchor='w')
        notch = ttk.Combobox(parent, values=NOTCH_ORDER, state='readonly', width=7)
        notch.set('N')
        notch.pack(anchor='w', pady=6)
        grid = ttk.Frame(parent)
        grid.pack(anchor='w')
        pixels = []
        pattern_status = ttk.Label(parent, style='Muted.TLabel')

        def redraw():
            frame = bytes.fromhex(self.patterns.get(notch.get(), '0' * 16))
            for i, button in enumerate(pixels):
                lit = frame[i // 8] & (0x80 >> (i % 8))
                button.configure(bg='#16846A' if lit else '#26374D')
            pattern_status.configure(text='正在编辑自定义图案' if notch.get() in self.patterns else
                                     '此档使用固件默认图案。首次点击从空白开始绘制。')

        def toggle(i):
            key = notch.get()
            frame = bytearray.fromhex(self.patterns.get(key, '0' * 16))
            frame[i // 8] ^= 0x80 >> (i % 8)
            self.patterns[key] = frame.hex()
            redraw()

        for i in range(64):
            button = tk.Button(grid, width=2, height=1, relief='flat',
                               activebackground='#35A889', command=lambda i=i: toggle(i))
            button.grid(row=i // 8, column=i % 8, padx=1, pady=1)
            pixels.append(button)
        notch.bind('<<ComboboxSelected>>', lambda event: redraw())
        pattern_status.pack(anchor='w', pady=5)
        redraw()
        row = ttk.Frame(parent)
        row.pack(anchor='w', pady=5)

        def reset_pattern():
            self.patterns.pop(notch.get(), None)
            redraw()

        def reset_all():
            enabled.set(True)
            brightness.set('2')
            rotation.current(3)
            self.patterns.clear()
            redraw()

        def save():
            try:
                level = int(brightness.get())
                if not 0 <= level <= 15:
                    raise ValueError
            except ValueError:
                feedback.configure(text='请输入 0 到 15 之间的亮度。')
                return
            settings = dict(enabled=enabled.get(), brightness=level, rotation=rotation.current(),
                            patterns=self.patterns.copy())
            if self.app.save_preferences(led=settings):
                self.app.led_settings = settings
                self.app.led_sent = None
                feedback.configure(text='已保存到此电脑。设备应用状态见下方。')
            else:
                feedback.configure(text='保存失败，请检查设置目录的写入权限。')

        ttk.Button(row, text='保存并应用', style='Accent.TButton', command=save).pack(side='left')
        ttk.Button(row, text='恢复本档图案', command=reset_pattern).pack(side='left', padx=6)
        ttk.Button(row, text='恢复全部默认', command=reset_all).pack(side='left')
        feedback = ttk.Label(parent, style='Muted.TLabel')
        feedback.pack(anchor='w')
        ttk.Label(parent, textvariable=self.app.led_status, wraplength=540).pack(anchor='w', pady=4)
        ttk.Label(parent, text='需要支持点阵设置的固件。自定义图案保存在本机，每次连接后自动应用。',
                  wraplength=540, style='Muted.TLabel').pack(anchor='w')
