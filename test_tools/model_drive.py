"""Live model driving instrument based on the controller's reported output."""
import math
import tkinter as tk
from tkinter import ttk
from ui_theme import FONT, blend

TRACK_SUPPLY_VOLTS = 12


def model_reading(sample):
    if sample is None:
        return None, '等待连接控制器'
    if sample.model != 'JR-C3-HIDARI-2':
        return None, '模型驾驶适用于 Hidari 2'
    if sample.mode != 'odoriko':
        return None, '等待切换到模型模式（Od）'
    if sample.model_duty is None:
        return None, '显示输出电压需要 Hidari 2 固件 1.2.5 或更新版本'
    return TRACK_SUPPLY_VOLTS * sample.model_duty / 255, '模型模式已开启'


class ModelDashboard(ttk.Frame):
    def __init__(self, parent, palette, open_settings):
        super().__init__(parent, padding=(22, 18))
        _, card, ink, muted, _, _, green, _, _ = palette
        self.last_reading = None

        canvas = self.gauge = tk.Canvas(self, width=410, height=292, bg=card, highlightthickness=0)
        canvas.pack(side='left', fill='y', padx=(0, 14))
        canvas.create_text(18, 17, text='当前输出电压', anchor='nw', fill=muted, font=(FONT, 10))
        bounds = (67, 43, 343, 319)
        canvas.create_arc(*bounds, start=210, extent=-240, style='arc', outline=blend(card, ink, .12), width=5)
        self.arc = canvas.create_arc(*bounds, start=210, extent=0, style='arc', outline=green, width=5)
        for volts in range(TRACK_SUPPLY_VOLTS + 1):
            major = volts % 2 == 0
            canvas.create_line(*self.point(volts, 130), *self.point(volts, 119 if major else 124),
                               fill=muted, width=2 if major else 1)
            if major:
                canvas.create_text(*self.point(volts, 104), text=str(volts), fill=ink,
                                   font=(FONT, 11))
        self.needle = canvas.create_line(*self.point(0, 0), *self.point(0, 90), fill=green, width=2)
        canvas.create_oval(200, 176, 210, 186, fill=green, outline='')
        self.voltage = canvas.create_text(205, 233, fill=ink, font=(FONT, 34, 'bold'))
        canvas.create_text(205, 267, text='V', fill=muted, font=(FONT, 11))

        info = ttk.Frame(self, padding=(13, 16), style='Card.TFrame')
        info.pack(side='left', fill='both', expand=True)
        self.status = ttk.Label(info, style='CardSection.TLabel', wraplength=265, justify='left')
        self.status.pack(anchor='w', pady=(0, 16))
        ttk.Label(info, text='电压按 12 V 标称供电和当前输出估算。', style='CardMuted.TLabel',
                  wraplength=265, justify='left').pack(anchor='w', pady=(0, 14))
        ttk.Label(info, text='两个手柄回 N，长按 A＋Y，选 Od 后按 X。',
                  style='Card.TLabel', wraplength=265, justify='left').pack(anchor='w', pady=(0, 14))
        ttk.Button(info, text='模型驾驶设定', command=open_settings,
                   style='PanelAccent.TButton').pack(anchor='w')
        self.update_reading(None)

    @staticmethod
    def point(volts, radius):
        angle = math.radians(210 - 240 * volts / TRACK_SUPPLY_VOLTS)
        return 205 + radius * math.cos(angle), 181 - radius * math.sin(angle)

    def update_reading(self, sample):
        voltage, status = model_reading(sample)
        reading = voltage, status
        if reading == self.last_reading:
            return
        self.last_reading = reading
        self.status.configure(text=status)
        visible = voltage is not None
        volts = voltage if visible else 0
        self.gauge.itemconfigure(self.voltage, text=f'{volts:.2f}' if visible else '—')
        self.gauge.coords(self.needle, *self.point(volts, 0), *self.point(volts, 90))
        self.gauge.itemconfigure(self.needle, state='normal' if visible else 'hidden')
        self.gauge.itemconfigure(self.arc, extent=-240 * volts / TRACK_SUPPLY_VOLTS)
