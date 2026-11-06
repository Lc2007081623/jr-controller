"""Small automatic bridge. Calibration remains in the existing dedicated window."""
import ctypes
import queue
import sys
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk

from serial_protocol import AutoDriveGate
from serial_notch_bridge import Reader, App as CalibrationApp
from output_profiles import MODES,ZUIKI,BVE,TRAIN_CREW,load_mode,save_mode,create_backend
from ui_theme import apply_theme,button_strip,update_buttons,BG,CARD,INK,MUTED,BLUE,GREEN,RED,AMBER

TITLE='JR 控制器'

def controller_ports(ports):
    return [p.device for p in ports if (p.vid,p.pid)==(0x303a,0x1001)]

class App:
    def __init__(self,root):
        self.root=root;self.reader=None;self.pad=None;self.events=queue.Queue()
        self.gate=AutoDriveGate();self.retry_at=0;self.pad_retry_at=0
        self.opened_at=0;self.last_sample_at=0;self.calibration=None;self.closing=False
        self.output_mode=load_mode()
        apply_theme(root);root.title(TITLE);root.geometry('760x740');root.resizable(False,False)
        self.status=tk.StringVar(value='正在连接控制器…')
        self.live=tk.StringVar(value='插入 USB 后自动连接')
        self.notch_text=tk.StringVar(value='—');self.reverser_text=tk.StringVar(value='—')
        header=tk.Frame(root,bg=INK,padx=28,pady=20);header.pack(fill='x')
        tk.Label(header,text='JR / CONTROLLER',bg=INK,fg='white',font=('Segoe UI',23,'bold')).pack(side='left')
        tk.Label(header,text='CONTROL DESK  /  1.0.0',bg=INK,fg='#9DB1CD',font=('Segoe UI',9)).pack(side='right',anchor='s',pady=7)
        tk.Frame(root,bg=GREEN,height=3).pack(fill='x')
        body=ttk.Frame(root,padding=(26,20));body.pack(fill='both',expand=True)
        games=ttk.Frame(body);games.pack(fill='x',pady=(0,14))
        ttk.Label(games,text='游戏模式').pack(side='left',padx=(0,12))
        self.mode=tk.StringVar(value=self.output_mode)
        self.mode_box=ttk.Combobox(games,textvariable=self.mode,values=MODES,state='readonly',width=32)
        self.mode_box.pack(side='left',fill='x',expand=True);self.mode_box.bind('<<ComboboxSelected>>',self.change_mode)
        self.mode_hint=tk.StringVar();self.update_mode_hint()
        ttk.Label(body,textvariable=self.mode_hint,style='Muted.TLabel',wraplength=700).pack(anchor='w',pady=(0,14))
        status_card=tk.Frame(body,bg=CARD,padx=18,pady=15);status_card.pack(fill='x',pady=(0,14))
        self.badge=tk.Label(status_card,text='● 等待连接',bg='#EDF2FA',fg=MUTED,font=('Microsoft YaHei UI',10,'bold'),padx=10,pady=5)
        self.badge.pack(side='right',anchor='n')
        tk.Label(status_card,textvariable=self.status,bg=CARD,fg=INK,font=('Microsoft YaHei UI',12,'bold'),wraplength=470,anchor='w',justify='left').pack(anchor='w',pady=(0,7))
        tk.Label(status_card,textvariable=self.live,bg=CARD,fg=MUTED,font=('Segoe UI',10),anchor='w').pack(anchor='w')
        metrics=tk.Frame(body,bg=BG);metrics.pack(fill='x',pady=(0,14))
        metrics.columnconfigure((0,1),weight=1,uniform='metric')
        main=tk.Frame(metrics,bg=CARD,padx=22,pady=16);main.grid(row=0,column=0,sticky='nsew',padx=(0,7))
        tk.Label(main,text='01  /  主手柄',bg=CARD,fg=MUTED,font=('Microsoft YaHei UI',10)).pack(anchor='w')
        self.notch_label=tk.Label(main,textvariable=self.notch_text,bg=CARD,fg=BLUE,font=('Segoe UI',57,'bold'));self.notch_label.pack(anchor='w')
        tk.Label(main,text='牵引  /  空挡  /  制动',bg=CARD,fg=MUTED,font=('Microsoft YaHei UI',9)).pack(anchor='w')
        direction=tk.Frame(metrics,bg=CARD,padx=22,pady=16);direction.grid(row=0,column=1,sticky='nsew',padx=(7,0))
        tk.Label(direction,text='02  /  换向器',bg=CARD,fg=MUTED,font=('Microsoft YaHei UI',10)).pack(anchor='w')
        tk.Label(direction,textvariable=self.reverser_text,bg=CARD,fg=INK,font=('Microsoft YaHei UI',23,'bold'),pady=14).pack(anchor='w')
        selector=tk.Frame(direction,bg=CARD);selector.pack(anchor='w',pady=(0,6));self.direction_labels={}
        for value in ('F','N','R'):
            label=tk.Label(selector,text=value,bg='#EDF2FA',fg=MUTED,font=('Segoe UI',11,'bold'),width=4,pady=5)
            label.pack(side='left',padx=(0,6));self.direction_labels[value]=label
        buttons=tk.Frame(body,bg=CARD,padx=14,pady=12);buttons.pack(fill='x',pady=(0,18))
        tk.Label(buttons,text='03  /  实体按键',bg=CARD,fg=MUTED,font=('Microsoft YaHei UI',10)).pack(anchor='w',padx=6,pady=(0,8))
        strip,self.key_labels=button_strip(buttons);strip.pack(anchor='w')
        row=ttk.Frame(body);row.pack(fill='x')
        ttk.Button(row,text='校准与设置',style='Accent.TButton',command=self.calibrate).pack(side='left')
        ttk.Button(row,text='最小化',command=root.iconify).pack(side='left',padx=10)
        ttk.Button(row,text='使用说明',command=self.open_guide).pack(side='left')
        ttk.Button(row,text='退出',command=self.close).pack(side='right')
        ttk.Label(body,text='校准保存在控制器中  ·  USB 自动连接  ·  实时跟随当前位置',style='Muted.TLabel',wraplength=700).pack(anchor='w',pady=(16,0))
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(20,self.tick)

    def open_guide(self):
        import os
        filename='train_crew_guide.html' if self.output_mode==TRAIN_CREW else 'bve_guide.html' if self.output_mode==BVE else 'first_steps.html'
        path=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'installer'))/filename
        try:os.startfile(path)
        except OSError:self.status.set('使用说明无法打开，请查看安装目录中的 '+filename)

    def update_mode_hint(self):
        if self.output_mode==TRAIN_CREW:
            self.mode_hint.set('TRAIN CREW · 先选本模式，再启动游戏并启用“外部设备输入输出”；A气笛 / B电笛 / X警报确认 / Y联络蜂鸣。B7/B8均为常用最大制动。')
            return
        if self.output_mode==BVE:
            self.mode_hint.set('BVE 5/6 · 游戏中启用 JR Controller 输入插件；主手柄、换向器及四按键直接输入。')
            return
        self.mode_hint.set('ZUIKI PRO · 主手柄 / 换向器 / 四按键。先打开本程序，再启动游戏；关闭 Steam Input。'
                           if self.output_mode==ZUIKI else 'Xbox · 主手柄 / 换向器 / 四按键。连接后立即跟随当前档位。')

    def change_mode(self,event=None):
        mode=self.mode.get()
        if mode not in MODES or mode==self.output_mode:return
        self.release();self.drop_pad();self.output_mode=mode;self.pad_retry_at=0
        self.update_mode_hint();self.status.set('正在切换游戏模式…')
        try:save_mode(mode)
        except OSError:self.status.set('模式已切换，但未能保存设置；下次启动需重新选择')

    def render(self):
        sample=self.gate.sample
        self.notch_text.set(sample.notch if sample else '—')
        rev=sample.reverser if sample else None
        self.reverser_text.set({'F':'前进 F','N':'空挡 N','R':'后退 R','X':'异常'}.get(rev,'—'))
        for value,label in self.direction_labels.items():
            label.configure(bg=BLUE if value==rev else '#EDF2FA',fg='white' if value==rev else MUTED)
        color=RED if sample and sample.notch.startswith(('B','E')) else GREEN if sample and sample.notch.startswith('P') else BLUE
        self.notch_label.configure(fg=color)
        update_buttons(self.key_labels,sample.buttons if sample else 0)
        if self.calibration:text,fg,bg='● 校准中',BLUE,'#EAF0FF'
        elif self.gate.armed:text,fg,bg='● 已就绪',GREEN,'#E5F5EE'
        elif not self.pad:text,fg,bg='● 等待驱动',RED,'#FCEEF0'
        elif self.reader:text,fg,bg='● 待就绪',AMBER,'#FFF4DE'
        else:text,fg,bg='● 等待连接',MUTED,'#EDF2FA'
        self.badge.configure(text=text,fg=fg,bg=bg)

    def release(self):
        self.gate.disarm()
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
        self.release()
        reader,self.reader=self.reader,None
        if reader:
            reader.stop_event.set();reader.join(timeout=1)
        self.gate=AutoDriveGate();self.retry_at=time.monotonic()+1
        self.live.set('插入 USB 后自动连接')

    def calibrate(self):
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
            elif kind in ('closed','error'):
                self.disconnect();self.status.set('控制器已断开，等待重新连接')
        if self.reader and now-self.last_sample_at>3:
            self.disconnect();self.status.set('未收到控制器数据，正在重连')
        if not self.calibration:
            now=time.monotonic()
            notch=self.gate.update(now,enabled=self.pad is not None)
            sample=self.gate.sample
            if self.pad:
                try:
                    if self.pad.notch!=notch:self.pad.set(notch)
                    if not self.gate.armed:
                        self.pad.set_buttons(0)
                        if self.pad.reverser!='N':self.pad.set_reverser('N')
                    elif sample:
                        if sample.reverser in ('F','N','R') and self.pad.reverser!=sample.reverser:
                            self.pad.set_reverser(sample.reverser)
                        self.pad.set_buttons(sample.buttons)
                    if self.output_mode in (BVE,TRAIN_CREW):self.pad.refresh(self.gate.armed)
                except Exception:
                    self.release();self.drop_pad();self.status.set('手柄连接异常，正在重试')
            if sample:
                self.live.set(f'{self.reader.port if self.reader else "USB"}  ·  {sample.sensor}  ·  {sample.raw*360/4096:.1f}°' if sample.sensor=='AS5600' else f'位置采样 {sample.adc}')
                if not sample.sensor_ok:self.status.set('传感器连接异常，请检查磁铁与接线')
                elif not sample.calibrated:self.status.set('请先点击“校准”完成主手柄校准')
                elif self.pad:self.status.set('已连接，可以开始游戏' if self.gate.armed else self.gate.reason)
        self.render();self.root.after(20,self.tick)

    def close(self):
        self.closing=True
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
        root=tk.Tk();App(root)
        if '--background' in sys.argv:root.iconify()
        root.mainloop()
    finally:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(mutex)

if __name__=='__main__':sys.exit(main())
