"""Settings and the 8 × 8 pattern editor."""
from decimal import Decimal, InvalidOperation
import queue
import re
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

from button_mapping import BUTTONS, TARGET_LABELS
from serial_protocol import NOTCH_ORDER
from ui_theme import FONT, style_window
from update_check import VERSION, RELEASES, check_update

DEFAULT_THEME = '列车终端'
THEMES = {
    DEFAULT_THEME: ('#1B1D1E', '#242728', '#E9EDEA', '#ADB6B2', '#23684D', '#191C1D', '#81CFAB', '#DAB477', '#F08D91'),
    '经典浅色': ('#F3F5F4', '#FFFFFF', '#202825', '#55645D', '#23684D', '#E9EEEB', '#216649', '#83550F', '#AC3544'),
    '绿色': ('#1A211D', '#242D27', '#E9F0EB', '#ACBDB2', '#276B4D', '#181F1A', '#8AD3AC', '#DAB477', '#F08D91'),
    '深色': ('#151617', '#1E2021', '#ECEFEE', '#AAB4B0', '#245F4A', '#141617', '#81CFAB', '#DAB477', '#F08D91'),
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
        self.window.geometry('740x560')
        self.window.minsize(720, 550)
        self.window.transient(app.root)
        style_window(self.window, THEMES[app.theme][0])
        menu = ttk.Frame(self.window, padding=(16, 18, 12, 18))
        menu.pack(side='left', fill='y')
        ttk.Frame(self.window, width=1, style='Divider.TFrame').pack(side='left', fill='y', pady=18)
        content = ttk.Frame(self.window, padding=(18, 18, 20, 18))
        content.pack(side='left', fill='both', expand=True)
        self.sections = {}
        for name, build in (('常规与更新', self.general), ('LED 点阵', self.matrix),
                            ('按键映射', self.buttons), ('模型驾驶', self.odoriko),
                            ('硬件与固件', app.updater.add_controls)):
            button = ttk.Button(menu, text=name, width=13,
                                command=lambda name=name: self.select(name))
            button.pack(fill='x', pady=(0, 6))
            page = ttk.Frame(content)
            build(page)
            self.sections[name] = (button, page)
        self.select('常规与更新')

    def select(self, name):
        for label, (button, page) in self.sections.items():
            if label == name:
                button.configure(style='PanelAccent.TButton')
                page.pack(fill='both', expand=True)
            else:
                button.configure(style='Panel.TButton')
                page.pack_forget()

    def odoriko(self, parent):
        ttk.Label(parent, text='模型驾驶', style='Section.TLabel').pack(anchor='w')
        ttk.Label(parent, text='加速、滑行和制动的数值越大，速度变化越快。修改前先读取当前设定，保存时把两个手柄都放回 N。',
                  wraplength=510, justify='left').pack(anchor='w', pady=(6, 14))
        self.odoriko_fields = {}
        for key, label in (('accel', 'P 档加速'), ('coast', 'N 档滑行掉速'), ('brake', 'B 档减速')):
            row = ttk.Frame(parent)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=label, width=18).pack(side='left')
            field = self.odoriko_fields[key] = tk.StringVar()
            ttk.Entry(row, textvariable=field, width=8).pack(side='left')
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text='最低输出电压', width=18).pack(side='left')
        self.minimum_voltage = tk.StringVar()
        self.minimum_entry = ttk.Entry(row, textvariable=self.minimum_voltage, width=8, state='disabled')
        self.minimum_entry.pack(side='left')
        ttk.Label(row, text='V').pack(side='left', padx=6)
        ttk.Label(parent, text='设为 0 时从零起步。如果小车低速时不动，可以略微调高。停车时输出仍会归零。',
                  style='Muted.TLabel', wraplength=495, justify='left').pack(anchor='w', pady=(6, 0))
        self.odoriko_status = tk.StringVar(value='连接 Hidari 2 后，先点击「读取」。')
        self.odoriko_pending = None
        actions = ttk.Frame(parent)
        actions.pack(anchor='w', pady=(16, 8))
        ttk.Button(actions, text='读取', command=lambda: self.send_odoriko('ODGET')).pack(side='left')
        ttk.Button(actions, text='保存到控制器', style='Accent.TButton',
                   command=self.save_odoriko).pack(side='left', padx=8)
        ttk.Label(parent, textvariable=self.odoriko_status, wraplength=510).pack(anchor='w')

    def save_odoriko(self):
        try:
            values = [int(field.get()) for field in self.odoriko_fields.values()]
            if any(not 1 <= value <= 255 for value in values):
                raise ValueError
        except ValueError:
            self.odoriko_status.set('三项参数都须为 1–255 的整数。')
            return
        sample = self.app.gate.sample
        if sample and sample.model_duty is not None:
            try:
                volts = Decimal(self.minimum_voltage.get().strip())
                if not volts.is_finite() or not 0 <= volts <= 12:
                    raise ValueError
                centivolts = volts * 100
                if centivolts != int(centivolts):
                    raise ValueError
            except (InvalidOperation, ValueError):
                self.odoriko_status.set('最低电压请输入 0–12 V，最多两位小数。')
                return
            values.append(int(centivolts))
        self.send_odoriko('ODSET ' + ' '.join(map(str, values)))

    def send_odoriko(self, command):
        sample = self.app.gate.sample
        if self.odoriko_pending is not None:
            return
        if not self.app.reader or not sample or sample.model != 'JR-C3-HIDARI-2':
            self.odoriko_status.set('请先连接 Hidari 2。')
            return
        try:
            self.app.reader.commands.put_nowait(command)
        except queue.Full:
            self.odoriko_status.set('串口忙，请重试。')
            return
        self.odoriko_status.set('等待控制器回复…')
        self.odoriko_pending = self.window.after(
            2000, lambda: self.finish_odoriko('控制器未应答，请检查连接及固件版本。'))

    def finish_odoriko(self, status):
        if self.odoriko_pending is not None:
            self.window.after_cancel(self.odoriko_pending)
            self.odoriko_pending = None
            self.odoriko_status.set(status)

    def disconnect_odoriko(self):
        self.finish_odoriko('控制器已断开。')
        self.minimum_voltage.set('')
        self.minimum_entry.configure(state='disabled')
        self.odoriko_status.set('重新连接后，点击「读取」。')

    def odoriko_response(self, response):
        if self.odoriko_pending is None:
            return
        if response.get('type') == 'odoriko_config':
            values = [response.get(key) for key in self.odoriko_fields]
            if all(type(value) is int and 1 <= value <= 255 for value in values):
                for field, value in zip(self.odoriko_fields.values(), values):
                    field.set(str(value))
                minimum = response.get('minimum_cv')
                supported = type(minimum) is int and 0 <= minimum <= 1200
                self.minimum_voltage.set(f'{minimum / 100:.2f}' if supported else '')
                self.minimum_entry.configure(state='normal' if supported else 'disabled')
                message = '已保存到控制器。' if response.get('saved') is True else '已读取当前设定。'
                if not supported:
                    message += ' 设置最低电压需要 Hidari 2 固件 1.2.5 或更新版本。'
                self.finish_odoriko(message)
        elif response.get('type') == 'ack':
            errors = {'error_odoriko_neutral': '请将主手柄和换向器都置 N，再保存。',
                      'error_odoriko_rates': '控制器拒绝了参数，请检查数值范围。',
                      'error_odoriko_voltage': '控制器拒绝了最低电压，请输入 0–12 V。',
                      'error_odoriko_save': '控制器保存失败，请重试。'}
            error = errors.get(response.get('message'))
            if error:
                self.finish_odoriko(error)

    def buttons(self, parent):
        ttk.Label(parent, text='四个实体按键', style='Section.TLabel').pack(anchor='w')
        ttk.Label(parent, text='键盘键发送给当前前台窗口。Xbox 360 映射仅在 JR EAST（Xbox）模式生效，其他模式使用该键的游戏默认功能。',
                  wraplength=510, justify='left').pack(anchor='w', pady=(6, 14))
        targets = {label: target for target, label in TARGET_LABELS.items()}
        choices = {}
        for button in BUTTONS:
            row = ttk.Frame(parent)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=f'实体 {button}', width=10).pack(side='left')
            combo = ttk.Combobox(row, values=tuple(targets), state='readonly', width=30, height=18)
            combo.set(TARGET_LABELS[self.app.button_mapping.get(button, 'default')])
            combo.pack(side='left')
            choices[button] = combo

        status = tk.StringVar(value='按键名称以设备校准中的 A / B / X / Y 为准。')

        def save():
            mapping = {button: targets[combo.get()] for button, combo in choices.items()
                       if combo.get() != TARGET_LABELS['default']}
            if self.app.apply_button_mapping(mapping):
                status.set('已保存。若实体键仍按着，松开后再按即可测试。')
            else:
                status.set('保存失败，请检查设置文件权限。')

        def reset():
            for combo in choices.values():
                combo.set(TARGET_LABELS['default'])
            status.set('已选择游戏默认，点击「保存并应用」生效。')

        actions = ttk.Frame(parent)
        actions.pack(anchor='w', pady=(16, 8))
        ttk.Button(actions, text='保存并应用', style='Accent.TButton', command=save).pack(side='left')
        ttk.Button(actions, text='恢复默认', command=reset).pack(side='left', padx=8)
        ttk.Label(parent, textvariable=status, wraplength=510).pack(anchor='w')

    def general(self, parent):
        ttk.Label(parent, text='外观', style='Section.TLabel').pack(anchor='w')
        theme = ttk.Combobox(parent, values=tuple(THEMES), state='readonly')
        theme.set(self.app.theme)
        theme.pack(anchor='w', pady=(6, 18))

        def change_theme(event):
            if self.app.save_preferences(theme=theme.get()):
                self.app.set_theme(theme.get())
                style_window(self.window, THEMES[self.app.theme][0])
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
        ttk.Frame(parent, height=1, style='Divider.TFrame').pack(fill='x', pady=(0, 14))
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
                button.configure(bg='#468C6C' if lit else '#303735')
            pattern_status.configure(text='正在编辑自定义图案' if notch.get() in self.patterns else
                                     '此档使用固件默认图案。首次点击从空白开始绘制。')

        def toggle(i):
            key = notch.get()
            frame = bytearray.fromhex(self.patterns.get(key, '0' * 16))
            frame[i // 8] ^= 0x80 >> (i % 8)
            self.patterns[key] = frame.hex()
            redraw()

        for i in range(64):
            button = tk.Button(grid, width=2, height=1, relief='flat', borderwidth=0,
                               pady=0, font=(FONT, 10), activebackground='#588E75',
                               command=lambda i=i: toggle(i))
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
