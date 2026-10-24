"""V1 serial calibration/monitor GUI. XInput is opt-in, not enabled at launch."""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from serial_protocol import DriveGate, ForwardPressGate, NOTCH_ORDER, parse_sample

class Reader(threading.Thread):
    def __init__(self,port,events,parser=parse_sample):
        super().__init__(daemon=True)
        self.port,self.events=port,events
        self.parser=parser
        self.commands=queue.Queue(maxsize=32)
        self.stop_event=threading.Event()

    def event(self,kind,data):
        self.events.put((self,kind,data,time.monotonic()))

    def run(self):
        try:
            import serial
            connection=serial.Serial()
            connection.port=self.port; connection.baudrate=115200
            connection.timeout=0.05; connection.write_timeout=0.3
            connection.dtr=False; connection.rts=False
            with connection:
                self.event('open',self.port)
                pending=bytearray(); dropping=False
                while not self.stop_event.is_set():
                    # Limit each batch to keep incoming data serviced.
                    for _ in range(4):
                        try: command=self.commands.get_nowait()
                        except queue.Empty: break
                        connection.write((command+'\n').encode('ascii'))
                    for c in connection.read(min(max(connection.in_waiting,1),512)):
                        if c==10:
                            if pending and not dropping:
                                try:
                                    text=pending.decode('utf-8').strip()
                                    data=json.loads(text)
                                    sample=self.parser(text)
                                    self.event('sample' if sample else 'info',sample or data)
                                except (ValueError,UnicodeError) as exc:
                                    self.event('bad',str(exc))
                            pending.clear(); dropping=False
                        elif not dropping:
                            if len(pending)<512: pending.append(c)
                            else: pending.clear(); dropping=True
        except Exception as exc:
            self.event('error',str(exc))
        finally:
            self.event('closed',self.port)

class App:
    def __init__(self,root):
        self.root=root; self.reader=None; self.pad=None; self.last_output=None
        self.gate=DriveGate(); self.events=queue.Queue(); self.connected=False
        self.forward_gate=ForwardPressGate()
        self.forward_status=tk.StringVar(value='GPIO10 → GND：物理N且输出启用时选择前进；XInput X轴保持F')
        self.current_capture={}; self.bad_lines=0; self.centers={}
        root.title('JR 控制器 · 电位器 / AS5600 · 串口校准'); root.geometry('1020x800')
        self.status=tk.StringVar(value='默认仅监看，不输出游戏输入')
        self.live=tk.StringVar(value='等待串口数据')
        self.port=tk.StringVar(); self.target=tk.StringVar(value='EB')
        self.caltext=tk.StringVar(value='先开始校准，再逐个采集15个卡位')
        self.drive_status=tk.StringVar(value='虚拟手柄尚未创建')
        self.heading=tk.StringVar(value='JR 控制器 / MAX7219 DIN6 CS5 CLK4')
        ttk.Label(root,textvariable=self.heading,font=('Microsoft YaHei',15)).pack(pady=12)
        top=ttk.Frame(root);top.pack(fill='x',padx=16)
        ttk.Label(top,text='串口').pack(side='left')
        self.portbox=ttk.Combobox(top,textvariable=self.port,width=12,state='readonly');self.portbox.pack(side='left',padx=6)
        ttk.Button(top,text='刷新',command=self.refresh_ports).pack(side='left')
        ttk.Button(top,text='连接',command=self.connect).pack(side='left',padx=6)
        ttk.Button(top,text='断开',command=self.disconnect).pack(side='left')
        ttk.Button(top,text='显示配置',command=lambda:self.command('SCAN')).pack(side='left',padx=6)
        ttk.Label(root,textvariable=self.status,wraplength=980).pack(pady=8)
        ttk.Label(root,textvariable=self.live,font=('Consolas',17)).pack(pady=8)
        box=ttk.LabelFrame(root,text='机械卡位校准（EB → B8…B1 → N → P1…P5；支持两个方向）')
        box.pack(fill='x',padx=16,pady=8)
        row=ttk.Frame(box);row.pack(pady=8)
        ttk.Button(row,text='1 开始校准',command=self.begin).pack(side='left',padx=5)
        ttk.Combobox(row,textvariable=self.target,values=NOTCH_ORDER,width=6,state='readonly').pack(side='left',padx=5)
        ttk.Button(row,text='2 采集当前卡位',command=self.capture).pack(side='left',padx=5)
        ttk.Button(row,text='3 校验并保存',command=lambda:self.command('SAVE')).pack(side='left',padx=5)
        ttk.Button(row,text='取消（恢复旧校准）',command=lambda:self.command('CANCEL')).pack(side='left',padx=5)
        ttk.Button(row,text='读取校准表',command=lambda:self.command('DUMP')).pack(side='left',padx=5)
        ttk.Label(box,textvariable=self.caltext,wraplength=950).pack(pady=7)
        self.table=ttk.Treeview(box,columns=('notch','adc','captured'),show='headings',height=8)
        for col,name in [('notch','档位'),('adc','位置中心值'),('captured','本次采集')]:
            self.table.heading(col,text=name);self.table.column(col,width=250,anchor='center')
        for name in NOTCH_ORDER:self.table.insert('','end',iid=name,values=(name,'—','—'))
        self.table.pack(fill='x',padx=10,pady=5)
        drive=ttk.LabelFrame(root,text='游戏输出（默认关闭；创建虚拟手柄后再启动游戏）');drive.pack(fill='x',padx=16,pady=8)
        row=ttk.Frame(drive);row.pack(pady=8)
        ttk.Button(row,text='创建虚拟手柄（输出N）',command=self.create_pad).pack(side='left',padx=6)
        ttk.Button(row,text='手柄置N后启用输出',command=self.arm).pack(side='left',padx=6)
        ttk.Button(row,text='停止输出并置N',command=self.neutral).pack(side='left',padx=6)
        ttk.Label(drive,textvariable=self.drive_status,wraplength=950).pack(pady=6)
        ttk.Label(drive,textvariable=self.forward_status,wraplength=950).pack(pady=4)
        self.logbox=tk.Text(root,height=7,font=('Consolas',10));self.logbox.pack(fill='both',expand=True,padx=16,pady=8)
        ttk.Label(root,text='串口超时500ms、设备重启或校准失效：置N并停止输出，必须手动重新启用。此N策略需在游戏静止时验证。',wraplength=980).pack(pady=5)
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_ports();root.after(20,self.tick)

    def log(self,message):
        self.logbox.insert('end',time.strftime('%H:%M:%S')+' '+message+'\n')
        self.logbox.see('end')
        if int(self.logbox.index('end-1c').split('.')[0])>350:self.logbox.delete('1.0','100.0')

    def refresh_ports(self):
        try:
            from serial.tools import list_ports
            ports=[p.device for p in list_ports.comports()]
            self.portbox['values']=ports
            if self.port.get() not in ports:self.port.set(ports[0] if ports else '')
        except ImportError:self.status.set('缺少pyserial：python -m pip install -r test_tools/requirements.txt')

    def connect(self):
        self.disconnect()
        if not self.port.get():self.status.set('未选择串口');return
        self.gate=DriveGate();self.forward_gate=ForwardPressGate()
        self.reader=Reader(self.port.get(),self.events);self.reader.start()
        self.status.set('正在连接 '+self.port.get())

    def disconnect(self):
        self.neutral()
        if self.reader:self.reader.stop_event.set()
        self.reader=None;self.connected=False
        self.gate=DriveGate();self.live.set('串口未连接')
        self.status.set('串口未连接；请连接后将手柄置N并启用输出')

    def command(self,value):
        if not self.reader or not self.connected:self.status.set('请先连接串口');return
        try:self.reader.commands.put_nowait(value)
        except queue.Full:self.status.set('命令队列已满，请等待设备响应');return
        self.log('TX '+value)

    def begin(self):
        if not self.connected:self.status.set('请先连接串口');return
        self.neutral();self.current_capture={};self.target.set('EB');self.command('BEGIN')
        for name in NOTCH_ORDER:self.table.item(name,values=(name,self.centers.get(name,'—'),'—'))

    def capture(self):
        self.neutral();self.command('CAP '+self.target.get())

    def create_pad(self):
        if self.pad is not None:return
        try:
            from xinput_notch_test import Backend
            pad=Backend();pad.connect();self.pad=pad;self.last_output=None
            self.write_output('N');self.log('虚拟手柄已创建，输出N；现在可启动游戏')
        except Exception as exc:
            self.log('虚拟手柄创建失败 '+str(exc));self.status.set('虚拟手柄失败；串口监看仍可继续')

    def write_output(self,name):
        if self.pad is None:return
        if self.last_output!=name:
            try:
                self.pad.set(name);self.last_output=name;self.log('XInput '+name)
            except Exception as exc:
                self.gate.disarm('XInput failure');self.log('XInput异常 '+str(exc))
                pad,self.pad=self.pad,None
                try:pad.close()
                except Exception:pass

    def neutral(self):
        self.gate.disarm();self.write_output('N')
        self.reset_reverser()

    def reset_reverser(self):
        if self.pad and self.pad.reverser!='N':
            try:
                self.pad.set_reverser('N');self.forward_status.set('换向请求N；再次启用后在物理N按GPIO10选择F')
            except Exception as exc:self.log('换向复位失败 '+str(exc))

    def arm(self):
        if self.pad is None:self.status.set('请先创建虚拟手柄');return
        try:self.gate.arm(time.monotonic())
        except ValueError as exc:self.status.set(str(exc));return
        self.log('已手动启用输出，当前N')

    def tick(self):
        for _ in range(160):
            try:owner,kind,value,received_at=self.events.get_nowait()
            except queue.Empty:break
            if owner is not self.reader:continue
            if kind=='sample':
                if self.gate.receive(value,received_at):
                    now=time.monotonic();self.gate.output(now)
                    if value.sensor=='AS5600':
                        self.heading.set('AS5600 SDA7 SCL15 / MAX7219 DIN6 CS5 CLK4')
                        angle=f'{value.raw*360/4096:.2f}°' if value.sensor_ok else '磁铁/通信异常'
                        self.live.set(f'{angle}  POS {value.adc}  档位 {value.notch}  CAL {int(value.calibrated)}  按钮10 {int(value.forward_pressed)}')
                    else:
                        self.heading.set('电位器 ADC3 / MAX7219 DIN6 CS5 CLK4')
                        self.live.set(f'RAW {value.raw:4d}  ADC {value.adc:4d}  档位 {value.notch}  CAL {int(value.calibrated)}  按钮10 {int(value.forward_pressed)}')
                    if self.forward_gate.receive(value,received_at,now,self.gate.armed):
                        try:
                            self.pad.set_reverser('F')
                            self.forward_status.set('XInput换向请求 F / LX=32767（实际位置看游戏HUD）')
                            self.log('GPIO10 → XInput LX=32767，保持前进F')
                        except Exception as exc:
                            self.forward_status.set('换向失败 '+str(exc));self.neutral()
            elif kind=='open':
                self.connected=True;self.status.set('串口已连接；默认仅监看，需手动启用游戏输出')
                self.command('SCAN');self.command('DUMP')
            elif kind in ('closed','error'):
                self.connected=False;self.neutral();self.status.set(kind+': '+str(value));self.log(kind+': '+str(value))
            elif kind=='bad':
                self.bad_lines+=1
                if self.bad_lines<=3:self.log('忽略无效行：'+str(value))
            elif kind=='info':
                if not isinstance(value,dict):continue
                self.log('RX '+json.dumps(value,ensure_ascii=False))
                if value.get('type')=='ack' and value.get('message')=='calibration_saved':
                    self.command('DUMP')
                if value.get('type') in ('center','capture') and value.get('notch') in NOTCH_ORDER:
                    name=value['notch'];adc=value.get('adc');self.centers[name]=adc
                    if value['type']=='capture':
                        self.current_capture[name]=adc
                        i=NOTCH_ORDER.index(name)
                        if i+1<len(NOTCH_ORDER):self.target.set(NOTCH_ORDER[i+1])
                    self.table.item(name,values=(name,adc,'已采集' if name in self.current_capture else '—'))
                    self.table.see(name)
                    self.caltext.set(f'本次已采集 {len(self.current_capture)}/15；保存前确认每个卡位已静止、两端无长段饱和')
        output=self.gate.output(time.monotonic());self.write_output(output)
        if not self.gate.armed:self.reset_reverser()
        self.drive_status.set(('XInput '+str(self.last_output)+' / ' if self.pad else '未创建虚拟手柄 / ')+self.gate.reason)
        self.root.after(20,self.tick)

    def close(self):
        self.disconnect()
        if self.pad:
            try:self.pad.close()
            except Exception:pass
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
