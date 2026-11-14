"""Small automatic bridge. Calibration remains in the existing dedicated window."""
import csv
import ctypes
import os
import queue
import subprocess
import sys
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from serial_protocol import AutoDriveGate, NOTCH_ORDER
from button_mapping import KeyboardOutput, button_mapping, mapped_outputs
from serial_notch_bridge import Reader, App as CalibrationApp
from output_profiles import MODES,XBOX,ZUIKI,BVE,TRAIN_CREW,load_mode,save_mode,create_backend,load_settings,save_settings
from ui_theme import FONT, SlidingReadout, apply_theme, blend, button_strip, style_window, update_buttons
from settings_ui import THEMES, DEFAULT_THEME, DEFAULT_PORT, SettingsWindow, led_settings, led_command
from local_state_api import LocalStateAPI, OFFLINE
from hardware_update import HardwareUpdater, hardware_name, hardware_details
from game_guides import GUIDES
from model_drive import ModelDashboard
from mascon_view import HandleTravel, MasconView

TITLE='JR 控制器'
JR_STEAM_URI = 'steam://rungameid/2111630'
JR_GAME_EXE = 'JREAST_TrainSimulator.exe'
NOTCH_RANK = {notch: index for index, notch in enumerate(NOTCH_ORDER)}
REVERSER_RANK = {'R': 0, 'N': 1, 'F': 2}

def controller_ports(ports):
    return [p.device for p in ports if (p.vid,p.pid)==(0x303a,0x1001)]

def jr_game_running(entry):
    names = {JR_GAME_EXE.casefold(), Path(entry).name.casefold()}
    result = subprocess.run(['tasklist.exe', '/fo', 'csv', '/nh'], check=True,
                            capture_output=True, encoding='oem', errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
    return any(row and row[0].casefold() in names for row in csv.reader(result.stdout.splitlines()))


class App:
    def __init__(self,root):
        self.root=root;self.reader=None;self.pad=None;self.events=queue.Queue()
        self.gate=AutoDriveGate();self.retry_at=0;self.pad_retry_at=0
        self.opened_at=0;self.last_sample_at=0;self.calibration=None;self.closing=False
        self.output_mode=load_mode()
        prefs = load_settings()
        self.button_mapping = button_mapping(prefs.get('button_mapping'))
        self.keyboard = KeyboardOutput()
        self.mapping_held = 0
        theme = prefs.get('theme')
        self.theme = theme if isinstance(theme, str) and theme in THEMES else DEFAULT_THEME
        self.details_visible = False
        self.handle_travel = HandleTravel()
        self.settings_window = None
        self.state_api = None
        self.api_enabled = prefs.get('api_enabled') is True
        port = prefs.get('api_port')
        self.api_port = port if type(port) is int and 1024 <= port <= 65535 else DEFAULT_PORT
        self.led_settings = led_settings(prefs.get('led'))
        self.led_sent = None
        self.led_status = tk.StringVar(value='等待控制器连接')
        self.hardware_name = tk.StringVar(value='未识别硬件')
        self.hardware_text = tk.StringVar()
        self.updater = HardwareUpdater(self)
        self.status=tk.StringVar(value='正在连接控制器…')
        self.live=tk.StringVar(value='插入 USB 后自动连接')
        self.mode=tk.StringVar(value=self.output_mode)
        self.mode_hint=tk.StringVar()
        self.jr_pending = None
        self.jr_button_text = tk.StringVar(value='启动 JR EAST')
        root.title(TITLE);root.geometry('790x408');root.minsize(760,408)
        self.page = '首页'
        self.shell = ttk.Frame(root)
        self.shell.pack(fill='both',expand=True)
        self.set_theme(self.theme)
        if self.api_enabled:
            try:
                self.state_api = LocalStateAPI(self.api_port)
            except OSError:
                self.status.set('本机接口端口被占用，请在软件设置中更换端口')
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(20,self.tick)

    def set_theme(self, theme):
        self.theme = theme
        apply_theme(self.root, THEMES[theme])
        for child in self.shell.winfo_children():
            child.destroy()
        palette = THEMES[theme]
        bg, card, ink, _, _, _, _, _, _ = palette
        header = tk.Frame(self.shell, bg=bg, padx=22, pady=9)
        header.pack(fill='x')
        self.back_button = ttk.Button(header, text='返回首页', style='Panel.TButton',
                                      command=lambda: self.show_page('首页'))
        self.page_title = tk.Label(header, bg=bg, fg=ink, pady=4, font=(FONT, 15, 'bold'))
        self.page_title.pack(side='left')
        self.output_badge = tk.Label(header, bg=bg, padx=0, font=(FONT, 10))
        self.usb_badge = tk.Label(header, bg=bg, padx=0, font=(FONT, 10))
        self.usb_badge.pack(side='right')
        tk.Frame(self.shell, bg=blend(card, ink, .10), height=1).pack(fill='x', padx=22)
        self.model_dashboard = ModelDashboard(self.shell, palette, lambda: self.open_settings('模型驾驶'))
        self.pages = {
            '首页': self.build_home(),
            '模拟驾驶': self.build_dashboard(),
            '模型驾驶': self.model_dashboard,
            '使用说明': self.build_usage(),
        }
        self.show_page(self.page)

    def show_page(self, name):
        self.pages[self.page].pack_forget()
        self.page = name
        self.page_title.configure(text=TITLE if name == '首页' else name)
        if name == '首页':
            self.back_button.pack_forget()
        else:
            self.back_button.pack(side='left', before=self.page_title, padx=(0, 12))
        if name == '模拟驾驶':
            self.output_badge.pack(side='right', before=self.usb_badge, padx=(16, 0))
        else:
            self.output_badge.pack_forget()
        self.pages[name].pack(fill='both', expand=True)
        self.render()

    def build_home(self):
        home = ttk.Frame(self.shell, padding=(16, 0, 16, 12))
        home.columnconfigure((0, 1, 2, 3), weight=1, uniform='home')
        home.rowconfigure(0, weight=1)
        home.rowconfigure(3, weight=1)
        for column, (title, hint, command) in enumerate((
            ('模拟驾驶', '连接电脑游戏', lambda: self.show_page('模拟驾驶')),
            ('模型驾驶', '查看当前输出电压', lambda: self.show_page('模型驾驶')),
            ('设定', '调整软件和控制器', self.open_settings),
            ('使用说明', '第一次使用', lambda: self.show_page('使用说明')),
        )):
            ttk.Button(home, text=title, command=command, style='Home.TButton').grid(
                row=1, column=column, sticky='ew', padx=6)
            ttk.Label(home, text=hint, style='Muted.TLabel', anchor='center').grid(
                row=2, column=column, sticky='ew', pady=(10, 0))
        return home

    def build_usage(self):
        body = ttk.Frame(self.shell, padding=(20, 16))
        body.columnconfigure((0, 1), weight=1, uniform='help')
        sections = (
            ('用控制器玩电脑游戏', (
                '连接控制器，进入「模拟驾驶」，选你要玩的游戏。',
                '等右上角显示「游戏输入就绪」，再启动游戏。第一次玩，先看游戏旁边的「接入说明」。',
                '停车时拨动手柄，看看软件和游戏里的档位是否跟着变。游戏没反应时，保持软件开启，再重开游戏。',
            )),
            ('驾驶模型列车', (
                '进入「模型驾驶」。把主手柄和换向器都放到 N，同时按住 A 和 Y 约一秒。',
                '松开后按 A 或 B 选到 Od，再按 X 确认。把换向器拨到 F 或 R，用 P 档加速、N 档滑行、B 档减速。',
                'EB 按设定归零或降至最低电压，换向器回 N 时归零。等小车停稳再换方向。回电脑游戏时，两柄回 N，再选 PC。',
            )),
        )
        for column, (title, steps) in enumerate(sections):
            section = ttk.Frame(body, padding=(12, 12), style='Card.TFrame')
            section.grid(row=0, column=column, sticky='nsew', padx=4)
            ttk.Label(section, text=title, style='CardSection.TLabel').grid(
                row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
            for number, step in enumerate(steps, 1):
                ttk.Label(section, text=f'{number}.', style='Card.TLabel').grid(
                    row=number, column=0, sticky='nw', padx=(0, 6), pady=(0, 8))
                ttk.Label(section, text=step, wraplength=302, justify='left', style='Card.TLabel').grid(
                    row=number, column=1, sticky='nw', pady=(0, 8))
        ttk.Label(body, text='小车低速时不动？打开「设定 → 模型驾驶」，先读取，再稍微调高最低输出电压。',
                  style='Muted.TLabel', wraplength=680, justify='left').grid(
                      row=1, column=0, columnspan=2, sticky='w', padx=12, pady=(8, 0))
        return body

    def build_dashboard(self):
        BG,CARD,INK,MUTED,_,TILE,_,_,_ = THEMES[self.theme]
        body=ttk.Frame(self.shell,padding=(22,18))
        games=ttk.Frame(body);games.pack(fill='x',pady=(0,10))
        ttk.Label(games,text='游戏模式',style='Section.TLabel').pack(side='left',padx=(0,12))
        self.mode_box=ttk.Combobox(games,textvariable=self.mode,values=MODES,state='readonly',width=28)
        self.mode_box.pack(side='left',fill='both',expand=True);self.mode_box.bind('<<ComboboxSelected>>',self.change_mode)
        self.jr_controls = ttk.Frame(games)
        ttk.Button(self.jr_controls,textvariable=self.jr_button_text,command=self.request_jr_launch,
                   style='PanelAccent.TButton').pack(side='left',padx=(8,0))
        ttk.Button(self.jr_controls,text='启动设置',command=self.choose_jr_entry,
                   style='Panel.TButton').pack(side='left',padx=(8,0))
        guide = ttk.Button(games,text='接入说明',command=self.open_mode_guide,style='Panel.TButton')
        guide.pack(side='right',padx=(8,0))
        self.update_mode_hint()
        self.status_label = tk.Label(body, textvariable=self.status, bg=BG, fg=MUTED, wraplength=700,
                                     anchor='w', justify='left', font=(FONT, 10))
        self.status_label.pack(fill='x',pady=(0,14))

        divider = blend(CARD, INK, .10)
        metrics=tk.Frame(body,bg=CARD,highlightbackground=divider,highlightthickness=1)
        metrics.pack(fill='x')
        metrics.columnconfigure((0,2,4),weight=1)
        for column in (1,3):
            tk.Frame(metrics,bg=divider,width=1).grid(row=0,column=column,sticky='ns',pady=14)
        main=tk.Frame(metrics,bg=CARD,padx=20,pady=14)
        main.grid(row=0,column=0,sticky='nsew')
        tk.Label(main,text='主手柄档位',bg=CARD,fg=MUTED,font=(FONT,10)).pack(anchor='w')
        handle = tk.Frame(main, bg=TILE)
        handle.pack(fill='x', pady=(9, 0))
        self.mascon = MasconView(handle, TILE)
        self.mascon.pack(side='left')
        self.notch_readout = SlidingReadout(handle, TILE, (FONT, 42, 'bold'), '000')
        self.notch_readout.pack(side='left', fill='x', expand=True)
        direction=tk.Frame(metrics,bg=CARD,padx=20,pady=14)
        direction.grid(row=0,column=2,sticky='nsew')
        tk.Label(direction,text='换向器',bg=CARD,fg=MUTED,font=(FONT,10)).pack(anchor='w')
        selector=tk.Frame(direction,bg=CARD);selector.pack(anchor='w',pady=(9,4));self.direction_labels={}
        for value in ('F','N','R'):
            label=tk.Label(selector,text=value,bg=TILE,fg=MUTED,font=(FONT,14,'bold'),width=3,pady=7)
            label.pack(side='left',padx=(0,5));self.direction_labels[value]=label
        self.reverser_readout = SlidingReadout(direction, CARD, (FONT, 12, 'bold'), '前进')
        self.reverser_readout.pack(anchor='w')
        buttons=tk.Frame(metrics,bg=CARD,padx=20,pady=14)
        buttons.grid(row=0,column=4,sticky='nsew')
        tk.Label(buttons,text='实体按键',bg=CARD,fg=MUTED,font=(FONT,10)).pack(anchor='w')
        strip,self.key_labels=button_strip(buttons,width=3);strip.pack(anchor='w',pady=(9,0))

        row=ttk.Frame(body);row.pack(fill='x',pady=(14,0))
        ttk.Label(row,textvariable=self.hardware_name,style='Muted.TLabel').pack(side='left')
        self.details_button = ttk.Button(row,command=self.toggle_details,style='Panel.TButton')
        self.details_button.pack(side='left',padx=8)
        for label, command in (('退出', self.close), ('软件设置', self.open_settings),
                               ('设备校准', self.calibrate)):
            ttk.Button(row,text=label,command=command,style='Panel.TButton').pack(side='right',padx=(8,0))
        self.details = ttk.Frame(body)
        for variable in (self.live, self.hardware_text):
            ttk.Label(self.details,textvariable=variable,style='Muted.TLabel').pack(anchor='w')
        self.show_details()
        return body

    def toggle_details(self):
        self.details_visible = not self.details_visible
        self.show_details()

    def show_details(self):
        self.details_button.configure(text='收起详情' if self.details_visible else '设备详情')
        if self.details_visible:
            self.details.pack(fill='x',pady=(8,0))
        else:
            self.details.pack_forget()

    def open_settings(self, section=None):
        if self.settings_window and self.settings_window.window.winfo_exists():
            self.settings_window.window.lift()
        else:
            self.settings_window = SettingsWindow(self)
        if section:
            self.settings_window.select(section)

    def save_preferences(self, **changes):
        try:
            save_settings(**changes)
            return True
        except OSError as error:
            messagebox.showerror('软件设置', f'无法保存设置。\n{error}', parent=self.root)
            return False

    def configure_api(self, enabled, port):
        previous = self.state_api
        replacement = previous if enabled and previous and self.api_port == port else None
        if enabled and replacement is None:
            try:
                replacement = LocalStateAPI(port)
            except OSError:
                return '无法开启接口，请更换一个未被占用的端口。'
        if not self.save_preferences(api_enabled=enabled, api_port=port):
            if replacement and replacement is not previous:
                replacement.close()
            return '原来的接口设置仍在使用。'
        self.api_enabled, self.api_port, self.state_api = enabled, port, replacement
        if previous and previous is not replacement:
            previous.close()
        return '接口已开启。' if enabled else '接口已关闭。'

    def open_mode_guide(self):
        window = tk.Toplevel(self.root)
        window.title(self.output_mode + ' · 接入说明')
        window.geometry('670x500')
        style_window(window, THEMES[self.theme][0])
        body = ttk.Frame(window,padding=24)
        body.pack(fill='both',expand=True)
        ttk.Label(body,text=self.output_mode,style='Title.TLabel').pack(anchor='w',pady=(0,16))
        ttk.Label(body,text=self.mode_hint.get(),style='Muted.TLabel',wraplength=600,
                  justify='left').pack(anchor='w',pady=(0,12))
        for index, step in enumerate(GUIDES[self.output_mode], 1):
            ttk.Label(body,text=f'{index:02}  {step}',wraplength=600,
                      justify='left').pack(anchor='w',pady=(0,10))
        mode = self.output_mode
        ttk.Button(body,text='打开完整说明',command=lambda: self.open_guide(mode)).pack(anchor='w',pady=8)

    def open_guide(self, mode=None):
        mode = mode or self.output_mode
        filename='train_crew_guide.html' if mode==TRAIN_CREW else 'bve_guide.html' if mode==BVE else 'first_steps.html'
        path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'installer'))/filename
        try:os.startfile(path)
        except OSError:self.status.set('使用说明无法打开，请查看安装目录中的 '+filename)

    def update_mode_hint(self):
        if self.output_mode == XBOX:
            self.jr_controls.pack(side='left')
        else:
            self.jr_controls.pack_forget()
        if self.output_mode==TRAIN_CREW:
            self.mode_hint.set('TRAIN CREW · 先选本模式，再启动游戏并启用“外部设备输入输出”；A气笛 / B电笛 / X警报确认 / Y联络蜂鸣。B7/B8均为常用最大制动。')
            return
        if self.output_mode==BVE:
            self.mode_hint.set('BVE 5/6 · 游戏中启用 JR Controller 输入插件；主手柄、换向器及四按键直接输入。')
            return
        self.mode_hint.set('ZUIKI PRO · 主手柄 / 换向器 / 四按键。先打开本程序，再启动游戏；关闭 Steam Input。'
                           if self.output_mode==ZUIKI else 'Xbox · Steam 版使用 Tsukasa Mascon 布局。直连版本的操作见接入说明。')

    def change_mode(self,event=None):
        mode=self.mode.get()
        if mode not in MODES or mode==self.output_mode:return
        if mode != XBOX and self.jr_pending:
            self.cancel_jr_launch()
        self.release();self.drop_pad();self.output_mode=mode;self.pad_retry_at=0
        self.update_mode_hint();self.status.set('正在切换游戏模式…')
        try:save_mode(mode)
        except OSError:self.status.set('模式已切换，但未能保存设置；下次启动需重新选择')

    def choose_jr_entry(self):
        self.cancel_jr_launch()
        steam = messagebox.askyesnocancel('JR EAST 启动设置',
            '选择“是”通过 Steam 启动，选择“否”指定游戏 EXE。', parent=self.root)
        if steam is None:
            return None
        entry = JR_STEAM_URI if steam else filedialog.askopenfilename(
            parent=self.root, title='选择 JR EAST 游戏 EXE', filetypes=[('游戏程序', '*.exe')])
        if not entry:
            return None
        try:
            save_settings(jr_launch_entry=entry)
        except OSError as exc:
            messagebox.showerror('JR EAST 启动设置', f'无法保存启动入口：{exc}', parent=self.root)
        return entry

    def request_jr_launch(self):
        if self.output_mode != XBOX:
            return
        if self.jr_pending:
            self.cancel_jr_launch()
            return
        entry = load_settings().get('jr_launch_entry')
        if entry != JR_STEAM_URI and (not isinstance(entry, str) or not Path(entry).is_file()):
            entry = self.choose_jr_entry()
        if not entry or not self.jr_can_start(entry):
            return
        self.jr_pending = entry
        self.jr_button_text.set('取消启动')

    def cancel_jr_launch(self):
        self.jr_pending = None
        self.jr_button_text.set('启动 JR EAST')

    def jr_can_start(self, entry):
        try:
            if not jr_game_running(entry):
                return True
            detail = 'JR EAST 已在运行。请退出游戏，再点击“启动 JR EAST”。'
        except (OSError, subprocess.SubprocessError) as exc:
            detail = f'无法检查 JR EAST 是否在运行：{exc}'
        messagebox.showwarning('启动 JR EAST', detail, parent=self.root)
        return False

    def launch_jr_if_ready(self):
        entry = self.jr_pending
        if not (entry and self.output_mode == XBOX and self.pad and self.gate.armed):
            return
        self.cancel_jr_launch()
        if not self.jr_can_start(entry):
            return
        try:
            if entry == JR_STEAM_URI:
                os.startfile(entry)
            else:
                os.startfile(entry, cwd=str(Path(entry).parent))
        except OSError as exc:
            messagebox.showerror('启动 JR EAST', f'启动失败，请检查启动设置：{exc}', parent=self.root)

    def render(self):
        _,_,INK,MUTED,ACCENT,TILE,GREEN,AMBER,RED = THEMES[self.theme]
        sample=self.gate.sample
        notch = sample.notch if sample else '—'
        rev=sample.reverser if sample and sample.mode not in ('menu', 'odoriko') else None
        animate = self.page == '模拟驾驶'
        self.reverser_readout.show({'F':'前进','N':'空挡','R':'后退','X':'异常'}.get(rev,'—'),
                                   INK, REVERSER_RANK.get(rev), animate)
        for value,label in self.direction_labels.items():
            label.configure(bg=ACCENT if value==rev else TILE,fg='#F4FAF7' if value==rev else MUTED)
        color = INK
        if notch == 'EB':
            color = RED
        elif notch.startswith('B'):
            color = AMBER
        elif notch.startswith('P'):
            color = GREEN
        self.notch_readout.show(notch, color, NOTCH_RANK.get(notch), animate)
        if animate:
            now = time.monotonic()
            fresh = self.gate.received is not None and 0 <= now - self.gate.received <= .15
            self.mascon.show(self.handle_travel.angle(self.reader, sample if fresh else None, now))
        update_buttons(self.key_labels,sample.buttons if sample else 0)
        usb_state = 'USB 已连接' if sample else 'USB 正在连接' if self.reader else 'USB 未连接'
        self.usb_badge.configure(text='●  ' + usb_state,fg=GREEN if sample else MUTED)
        if self.calibration:
            output, indicator = '校准中', AMBER
        elif self.gate.armed:
            output, indicator = '游戏输入就绪', GREEN
        elif sample:
            output, indicator = '游戏输入暂停', AMBER
        else:
            output, indicator = '游戏输入待命', MUTED
        self.output_badge.configure(text='●  ' + output,fg=indicator)
        if self.page == '模型驾驶':
            fresh = self.gate.received is not None and 0 <= time.monotonic() - self.gate.received <= .15
            self.model_dashboard.update_reading(sample if fresh else None)

    def apply_button_mapping(self, mapping):
        if not self.save_preferences(button_mapping=mapping):
            return False
        self.mapping_held = self.gate.sample.buttons if self.gate.sample else 0
        self.release()
        self.button_mapping = mapping
        return True

    def update_keyboard(self, keys):
        try:
            self.keyboard.update(keys)
        except OSError:
            self.status.set('键盘输出失败，请检查目标程序是否以管理员身份运行')

    def release(self):
        self.gate.disarm()
        self.update_keyboard(set())
        if self.pad:
            try:
                self.pad.set_buttons(0);self.pad.set('N');self.pad.set_reverser('N')
                if self.output_mode in (BVE,TRAIN_CREW):self.pad.refresh(False)
            except Exception:
                self.drop_pad()

    def drop_pad(self):
        pad,self.pad=self.pad,None
        if pad:
            try:pad.close()
            except Exception:pass

    def disconnect(self):
        if self.settings_window and self.settings_window.window.winfo_exists():
            self.settings_window.disconnect_odoriko()
        self.release()
        reader,self.reader=self.reader,None
        if reader:
            reader.stop_event.set();reader.join(timeout=1)
        self.gate=AutoDriveGate();self.retry_at=time.monotonic()+1
        self.mapping_held = 0
        self.led_sent = None
        self.led_status.set('等待控制器连接')
        self.hardware_name.set('未识别硬件')
        self.hardware_text.set('')
        if self.state_api:
            self.state_api.snapshot = OFFLINE
        self.live.set('插入 USB 后自动连接')

    def calibrate(self):
        if self.updater.busy:
            return
        if self.calibration:
            self.calibration.root.lift();return
        port=self.reader.port if self.reader else None
        self.disconnect();self.status.set('校准中，游戏输入已暂停')
        window=tk.Toplevel(self.root)
        self.calibration=CalibrationApp(window,calibration_only=True)
        if port:
            self.calibration.port.set(port);self.calibration.connect()
        window.protocol('WM_DELETE_WINDOW',self.finish_calibration)

    def finish_calibration(self):
        if not self.calibration:return
        self.calibration.command('CANCEL')
        if self.calibration.gate.sample and self.calibration.gate.sample.board=='C3':
            self.calibration.command('RCANCEL');self.calibration.command('KCANCEL')
        self.root.after(200,self.resume)

    def resume(self):
        if not self.calibration:return
        app,self.calibration=self.calibration,None
        reader=app.reader;app.close()
        if reader:reader.join(timeout=1)
        self.retry_at=0;self.status.set('校准结束，正在重新连接…')

    def tick(self):
        if self.closing:return
        if self.updater.busy is True:
            self.root.after(20,self.tick)
            return
        now=time.monotonic()
        if not self.pad and now>=self.pad_retry_at:
            self.pad_retry_at=now+5
            try:
                pad=create_backend(self.output_mode);pad.connect();self.pad=pad
            except Exception:
                self.status.set('TRAIN CREW 接口未就绪，请退出游戏，待本程序就绪后再启动游戏' if self.output_mode==TRAIN_CREW else '游戏接口初始化失败，正在重试' if self.output_mode==BVE else '手柄驱动未就绪，请完成安装或重启电脑')
        if not self.calibration and not self.reader and now>=self.retry_at:
            self.retry_at=now+1
            try:
                from serial.tools import list_ports
                ports=controller_ports(list_ports.comports())
                if len(ports)==1:
                    self.reader=Reader(ports[0],self.events);self.reader.start()
                    self.opened_at=now;self.last_sample_at=now
                    self.status.set('正在连接 '+ports[0])
                else:self.status.set('等待插入控制器' if not ports else '发现多个开发板，请只连接控制器')
            except Exception as exc:self.status.set('连接失败：'+str(exc))
        for _ in range(160):
            try:owner,kind,value,arrival=self.events.get_nowait()
            except queue.Empty:break
            if owner is not self.reader:continue
            if kind=='sample':
                if self.gate.receive(value,arrival):self.last_sample_at=arrival
            elif kind == 'info' and isinstance(value, dict):
                if value.get('type') == 'center':
                    self.handle_travel.read_center(owner, value)
                if self.settings_window and self.settings_window.window.winfo_exists():
                    self.settings_window.odoriko_response(value)
                if value.get('type') == 'ack':
                    if value.get('message') == 'led_config_applied':
                        self.led_status.set('固件已接收并应用点阵设置')
                    elif value.get('message') == 'error_led_config':
                        self.led_status.set('设备拒绝点阵设置，请检查固件版本')
            elif kind in ('closed','error'):
                self.disconnect();self.status.set('控制器已断开，等待重新连接')
        if self.reader and now-self.last_sample_at>3:
            self.disconnect();self.status.set('未收到控制器数据，正在重连')
        if not self.calibration:
            now=time.monotonic()
            notch=self.gate.update(now,enabled=self.pad is not None)
            sample=self.gate.sample
            keys = set()
            if self.pad:
                try:
                    if self.pad.notch!=notch:self.pad.set(notch)
                    if not self.gate.armed:
                        self.pad.set_buttons(0)
                        if self.pad.reverser!='N':self.pad.set_reverser('N')
                    elif sample:
                        if sample.reverser in ('F','N','R') and self.pad.reverser!=sample.reverser:
                            self.pad.set_reverser(sample.reverser)
                        self.mapping_held &= sample.buttons
                        native, xbox, triggers, keys = mapped_outputs(
                            sample.buttons & ~self.mapping_held, self.button_mapping, self.output_mode == XBOX)
                        if self.output_mode == XBOX:self.pad.set_xbox_buttons(xbox, triggers)
                        else:self.pad.set_buttons(native)
                    if self.output_mode in (BVE,TRAIN_CREW):self.pad.refresh(self.gate.armed)
                except Exception:
                    keys = set()
                    self.release();self.drop_pad();self.status.set('手柄连接异常，正在重试')
            if sample:
                self.live.set(f'{self.reader.port if self.reader else "USB"}  ·  {sample.sensor}  ·  {sample.raw*360/4096:.1f}°' if sample.sensor=='AS5600' else f'位置采样 {sample.adc}')
                if not sample.sensor_ok:self.status.set('传感器连接异常，请检查磁铁与接线')
                elif sample.mode == 'odoriko':self.status.set('N 比例模块模式 · 游戏输入已暂停')
                elif sample.mode == 'menu':self.status.set('控制器正在选择模式 · 游戏输入已暂停')
                elif not sample.calibrated:self.status.set('请先点击“校准”完成主手柄校准')
                elif self.pad:self.status.set(self.mode_hint.get() if self.gate.armed else self.gate.reason)
            self.update_keyboard(keys)
            self.launch_jr_if_ready()
        self.publish_state(now)
        self.render();self.root.after(20,self.tick)

    def publish_state(self, now):
        sample = self.gate.sample
        fresh = bool(sample and not self.calibration and self.reader and 0 <= now-self.last_sample_at <= .15)
        self.updater.observe(sample if fresh else None, now)
        if fresh:
            self.hardware_name.set(hardware_name(sample))
            self.hardware_text.set(hardware_details(sample))
            if not sample.led_config:
                self.led_status.set('此固件不支持点阵设置，请先更新固件')
            elif self.led_sent != sample.boot:
                try:
                    self.reader.commands.put_nowait(led_command(self.led_settings))
                    self.led_sent = sample.boot
                    self.led_status.set('已发送，等待固件确认…')
                except queue.Full:
                    pass
        if self.state_api:
            valid = bool(fresh and sample.calibrated and sample.sensor_ok and sample.reverser != 'X'
                         and sample.mode not in ('menu', 'odoriko'))
            self.state_api.snapshot = dict(OFFLINE, connected=fresh, valid=valid,
                                           notch=sample.notch if valid else None,
                                           reverser=sample.reverser if valid else None,
                                           buttons=sample.buttons if valid else 0,
                                           hardware=sample.model if fresh else None)


    def close(self):
        if self.updater.busy:
            return
        self.closing=True
        if self.state_api:
            self.state_api.close()
        if self.calibration:self.calibration.close()
        self.disconnect();self.drop_pad();self.root.destroy()

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--self-check':
        from install_check import write_check
        return write_check(sys.argv[2])
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexExW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong]
    kernel.CreateMutexExW.restype=ctypes.c_void_p
    ctypes.set_last_error(0)
    # Duplicate detection needs SYNCHRONIZE, not MUTEX_ALL_ACCESS across integrity levels.
    mutex=kernel.CreateMutexExW(None,'Local\\JRController',0,0x100000)
    error=ctypes.get_last_error()
    if error==183 or (not mutex and error==5):
        user=ctypes.WinDLL('user32')
        user.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p];user.FindWindowW.restype=ctypes.c_void_p
        window=user.FindWindowW(None,TITLE)
        if window:
            user.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int];user.ShowWindow(window,9)
            user.SetForegroundWindow.argtypes=[ctypes.c_void_p];user.SetForegroundWindow(window)
        else:
            user.MessageBoxW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint]
            user.MessageBoxW(None,'另一个控制器程序正在运行或被其他权限的进程占用。请关闭旧窗口后重试。',TITLE,0x40)
        if mutex:
            kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)
        return
    if not mutex:raise ctypes.WinError(error)
    try:
        root=tk.Tk()
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'installer')) / 'hikari.ico'
        if sys.platform == 'win32' and icon.is_file():
            root.iconbitmap(default=str(icon))
        App(root)
        if '--background' in sys.argv:root.iconify()
        root.mainloop()
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)

if __name__=='__main__':sys.exit(main())
