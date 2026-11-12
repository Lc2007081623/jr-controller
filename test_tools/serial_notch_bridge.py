"""V1 serial calibration/monitor GUI. XInput is opt-in, not enabled at launch."""
import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from ui_theme import FONT, apply_theme, button_strip, update_buttons
from serial_protocol import DriveGate, ForwardPressGate, ReverserSwitchGate, NOTCH_ORDER, parse_sample,button_assignments

class Reader(threading.Thread):
    def __init__(self,port,events,parser=parse_sample,exit_commands=()):
        super().__init__(daemon=True)
        self.port,self.events=port,events
        self.parser=parser
        self.exit_commands=exit_commands
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
                for command in self.exit_commands:
                    connection.write((command+'\n').encode('ascii'))
                if self.exit_commands:connection.flush()
        except Exception as exc:
            self.event('error',str(exc))
        finally:
            self.event('closed',self.port)

class App:
    def __init__(self,root,calibration_only=False):
        self.root=root; self.reader=None; self.pad=None; self.last_output=None
        self.calibration_only=calibration_only
        self.gate=DriveGate();self.events=queue.Queue();self.connected=False
        self.forward_gate=ForwardPressGate();self.reverser_gate=ReverserSwitchGate()
        self.current_capture={};self.bad_lines=0;self.centers={}
        self.reverser_calibrating=False;self.buttons_calibrating=False
        self.reverser_config_requested=False;self.button_captures={}
        apply_theme(root);root.title('JR 控制器 · 校准中心');root.geometry('900x750')
        self.status=tk.StringVar(value='连接控制器后开始校准')
        self.live=tk.StringVar(value='等待控制器数据')
        self.port=tk.StringVar();self.target=tk.StringVar(value='EB')
        self.caltext=tk.StringVar(value='依次停稳在 15 个机械卡位，采集后保存。')
        self.drive_status=tk.StringVar(value='游戏输出已暂停')
        self.forward_status=tk.StringVar(value='主手柄回 N 时切换方向')
        self.rev_target=tk.StringVar(value='F');self.rev_text=tk.StringVar(value='依次学习前进 F、空挡 N、后退 R。')
        self.btn_target=tk.StringVar(value='A');self.btn_text=tk.StringVar(value='按住一个实体按钮，将它指定为 A、B、X 或 Y。')
        self.heading=tk.StringVar(value='校准中心')
        body=ttk.Frame(root,padding=24);body.pack(fill='both',expand=True)
        ttk.Label(body,textvariable=self.heading,style='Title.TLabel').pack(anchor='w')
        ttk.Label(body,text='保存到控制器 · 断电保留 · 校准期间暂停游戏输入',style='Muted.TLabel').pack(anchor='w',pady=(2,16))
        top=ttk.Frame(body);top.pack(fill='x',pady=(0,10))
        self.portbox=ttk.Combobox(top,textvariable=self.port,width=10,state='readonly');self.portbox.pack(side='left',padx=(0,8))
        ttk.Button(top,text='连接',style='Accent.TButton',command=self.connect).pack(side='left',padx=4)
        ttk.Button(top,text='刷新',command=self.refresh_ports).pack(side='left',padx=4)
        ttk.Button(top,text='断开',command=self.disconnect).pack(side='left',padx=4)
        ttk.Label(body,textvariable=self.status,style='Muted.TLabel',wraplength=880).pack(anchor='w')
        ttk.Label(body,textvariable=self.live,font=(FONT,11)).pack(anchor='w',pady=(8,14))
        tabs=ttk.Notebook(body);tabs.pack(fill='both',expand=True)
        handle=ttk.Frame(tabs,padding=20,style='Card.TFrame');tabs.add(handle,text='主手柄')
        direction=ttk.Frame(tabs,padding=20,style='Card.TFrame');tabs.add(direction,text='换向器')
        keys=ttk.Frame(tabs,padding=20,style='Card.TFrame');tabs.add(keys,text='按钮')
        logs=ttk.Frame(tabs,padding=16,style='Card.TFrame');tabs.add(logs,text='诊断日志')
        ttk.Label(handle,text='01  采集机械卡位',style='CardSection.TLabel').pack(anchor='w')
        ttk.Label(handle,text='EB → B8…B1 → N → P1…P5',style='Card.TLabel').pack(anchor='w',pady=(5,14))
        row=ttk.Frame(handle,style='Card.TFrame');row.pack(fill='x',pady=5)
        ttk.Button(row,text='开始',command=self.begin).pack(side='left',padx=(0,8))
        ttk.Combobox(row,textvariable=self.target,values=NOTCH_ORDER,width=6,state='readonly').pack(side='left',padx=4)
        ttk.Button(row,text='采集卡位',style='Accent.TButton',command=self.capture).pack(side='left',padx=8)
        ttk.Button(row,text='保存',command=lambda:self.command('SAVE')).pack(side='left',padx=4)
        ttk.Button(row,text='取消',command=lambda:self.command('CANCEL')).pack(side='left',padx=4)
        ttk.Label(handle,textvariable=self.caltext,style='Card.TLabel',wraplength=820).pack(anchor='w',pady=10)
        self.table=ttk.Treeview(handle,columns=('notch','adc','captured'),show='headings',height=7)
        for col,name in [('notch','档位'),('adc','中心值'),('captured','采集状态')]:
            self.table.heading(col,text=name);self.table.column(col,width=220,anchor='center')
        for name in NOTCH_ORDER:self.table.insert('','end',iid=name,values=(name,'—','—'))
        self.table.pack(fill='both',expand=True)
        ttk.Label(direction,text='02  学习三档换向开关',style='CardSection.TLabel').pack(anchor='w')
        ttk.Label(direction,text='拨到目标方向，停稳后点击采集；中间位置应断开。',style='Card.TLabel').pack(anchor='w',pady=(8,22))
        row=ttk.Frame(direction,style='Card.TFrame');row.pack(fill='x')
        ttk.Button(row,text='开始',command=lambda:self.reverser_command('RBEGIN')).pack(side='left',padx=(0,8))
        ttk.Combobox(row,textvariable=self.rev_target,values=('F','N','R'),width=5,state='readonly').pack(side='left',padx=4)
        ttk.Button(row,text='采集方向',style='Accent.TButton',command=lambda:self.reverser_command('RCAP '+self.rev_target.get())).pack(side='left',padx=8)
        ttk.Button(row,text='保存',command=lambda:self.reverser_command('RSAVE')).pack(side='left',padx=4)
        ttk.Button(row,text='取消',command=lambda:self.reverser_command('RCANCEL')).pack(side='left',padx=4)
        ttk.Label(direction,textvariable=self.rev_text,style='Card.TLabel',wraplength=820).pack(anchor='w',pady=20)
        ttk.Label(keys,text='03  指定四个实体按钮',style='CardSection.TLabel').pack(anchor='w')
        ttk.Label(keys,text='按住想用作目标按键的按钮，再点击采集。每个按钮只能分配一次。',style='Card.TLabel',wraplength=820).pack(anchor='w',pady=(8,16))
        strip,self.key_labels=button_strip(keys);strip.pack(anchor='w',pady=(0,16))
        row=ttk.Frame(keys,style='Card.TFrame');row.pack(fill='x')
        ttk.Button(row,text='开始',command=lambda:self.button_command('KBEGIN')).pack(side='left',padx=(0,8))
        ttk.Combobox(row,textvariable=self.btn_target,values=tuple('ABXY'),width=5,state='readonly').pack(side='left',padx=4)
        ttk.Button(row,text='采集按钮',style='Accent.TButton',command=lambda:self.button_command('KCAP '+self.btn_target.get())).pack(side='left',padx=8)
        ttk.Button(row,text='保存',command=lambda:self.button_command('KSAVE')).pack(side='left',padx=4)
        ttk.Button(row,text='取消',command=lambda:self.button_command('KCANCEL')).pack(side='left',padx=4)
        ttk.Label(keys,textvariable=self.btn_text,style='Card.TLabel',wraplength=820).pack(anchor='w',pady=16)
        self.button_table=ttk.Treeview(keys,columns=('key','pin','state'),show='headings',height=4)
        for col,name in [('key','手柄按键'),('pin','实体输入'),('state','本次学习')]:
            self.button_table.heading(col,text=name);self.button_table.column(col,width=220,anchor='center')
        for name in 'ABXY':self.button_table.insert('','end',iid=name,values=(name,'—','—'))
        self.button_table.pack(fill='x')
        ttk.Button(logs,text='读取设备配置',command=lambda:self.command('SCAN')).pack(anchor='w',pady=(0,10))
        style = ttk.Style(root)
        self.logbox=tk.Text(logs,height=10,font=('Consolas',10),bg=style.lookup('TLabel','background'),
                            fg=style.lookup('TLabel','foreground'),relief='flat',padx=12,pady=12)
        self.logbox.pack(fill='both',expand=True)
        if not calibration_only:
            drive=ttk.Frame(tabs,padding=20,style='Card.TFrame');tabs.add(drive,text='手动输出')
            ttk.Button(drive,text='创建手柄',command=self.create_pad).pack(anchor='w',pady=8)
            ttk.Button(drive,text='回 N 后启用',command=self.arm).pack(anchor='w',pady=8)
            ttk.Button(drive,text='停止并释放',command=self.neutral).pack(anchor='w',pady=8)
            ttk.Label(drive,textvariable=self.drive_status,style='Card.TLabel').pack(anchor='w',pady=12)
            ttk.Label(drive,textvariable=self.forward_status,style='Card.TLabel',wraplength=800).pack(anchor='w')
        footer='关闭窗口后自动连接。' if calibration_only else '当前仅校准监看；手动输出需先回 N。'
        ttk.Label(body,text=footer,style='Muted.TLabel').pack(anchor='w',pady=(12,0))
        root.protocol('WM_DELETE_WINDOW',self.close);self.refresh_ports();root.after(20,self.tick)

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
        self.gate=DriveGate();self.forward_gate=ForwardPressGate();self.reverser_gate=ReverserSwitchGate()
        self.reverser_config_requested=False;self.reverser_calibrating=False;self.buttons_calibrating=False
        self.reader=Reader(self.port.get(),self.events,exit_commands=('CANCEL','RCANCEL','KCANCEL'));self.reader.start()
        self.status.set('正在连接 '+self.port.get())

    def disconnect(self):
        self.neutral()
        reader,self.reader=self.reader,None
        if reader:reader.stop_event.set();reader.join(timeout=1)
        self.connected=False
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
        self.reverser_calibrating=False;self.buttons_calibrating=False
        for name in NOTCH_ORDER:self.table.item(name,values=(name,self.centers.get(name,'—'),'—'))

    def capture(self):
        self.neutral();self.command('CAP '+self.target.get())

    def reverser_command(self,command):
        if not self.connected or not self.gate.sample or self.gate.sample.board!='C3':
            self.status.set('请先连接 C3 控制器');return
        self.neutral()
        if command=='RBEGIN':
            self.buttons_calibrating=False
            self.reverser_calibrating=True;self.rev_target.set('F')
            self.rev_text.set('拨到物理前进 F，停稳后采集；接着采集 N、R，再保存')
        self.command(command)

    def button_command(self,command):
        if not self.connected or not self.gate.sample or self.gate.sample.board!='C3':
            self.status.set('请先连接 C3 控制器');return
        self.neutral()
        if command=='KBEGIN':
            self.buttons_calibrating=True;self.reverser_calibrating=False
            self.button_captures={};self.btn_target.set('A')
            self.btn_text.set('按住希望用作 A 的实体按钮，再点击“采集按钮”。')
        self.command(command)

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
        self.write_buttons(0)
        self.reset_reverser()

    def write_buttons(self,mask):
        if self.pad is None:return
        try:self.pad.set_buttons(mask)
        except Exception as exc:
            self.gate.disarm('XInput buttons failure');self.log('按钮输出失败 '+str(exc))
            pad,self.pad=self.pad,None
            try:pad.close()
            except Exception:pass

    def reset_reverser(self):
        if self.pad and self.pad.reverser!='N':
            try:
                self.pad.set_reverser('N');self.forward_status.set('换向请求N；手柄和三档开关置N后重新启用输出')
            except Exception as exc:self.log('换向复位失败 '+str(exc))

    def arm(self):
        if self.pad is None:self.status.set('请先创建虚拟手柄');return
        if self.reverser_calibrating or self.buttons_calibrating:self.status.set('请先保存或取消校准');return
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
                    update_buttons(self.key_labels,value.buttons)
                    if value.sensor=='AS5600':
                        self.heading.set('校准中心 · '+('ESP32-C3' if value.board=='C3' else 'ESP32-S3'))
                        angle=f'{value.raw*360/4096:.2f}°' if value.sensor_ok else '磁铁/通信异常'
                        inputs=(f'换向 {value.reverser}  A/B/X/Y '+ '/'.join(str((value.buttons>>i)&1) for i in range(4))) if value.board=='C3' else f'按钮10 {int(value.forward_pressed)}'
                        self.live.set(f'{angle}  POS {value.adc}  档位 {value.notch}  CAL {int(value.calibrated)}\n{inputs}')
                    else:
                        self.heading.set('电位器 ADC3 / MAX7219 DIN6 CS5 CLK4')
                        self.live.set(f'RAW {value.raw:4d}  ADC {value.adc:4d}  档位 {value.notch}  CAL {int(value.calibrated)}  按钮10 {int(value.forward_pressed)}')
                    switch_request=self.reverser_gate.receive(value,received_at,now,self.gate.armed)
                    forward_request=self.forward_gate.receive(value,received_at,now,self.gate.armed)
                    request=switch_request or ('F' if forward_request and value.reverser is None else None)
                    if value.board=='C3':
                        if not self.reverser_config_requested:
                            self.command('RDUMP');self.command('KDUMP');self.reverser_config_requested=True
                        self.forward_status.set(f'物理换向 {value.reverser}；手柄N时切换；游戏请求 {self.pad.reverser if self.pad else "N"}；GPIO0/10/20/21 → A/B/X/Y')
                    if request:
                        try:
                            self.pad.set_reverser(request)
                            self.forward_status.set('XInput换向请求 '+request+'（实际位置看游戏HUD）')
                            self.log('换向 → XInput '+request)
                        except Exception as exc:
                            self.forward_status.set('换向失败 '+str(exc));self.neutral()
            elif kind=='open':
                self.connected=True;self.status.set('已连接 · 校准期间游戏输入已暂停' if self.calibration_only else '已连接 · 默认仅监看，需手动启用游戏输出')
                self.command('SCAN');self.command('DUMP')
            elif kind in ('closed','error'):
                self.connected=False;self.neutral();self.status.set(kind+': '+str(value));self.log(kind+': '+str(value))
            elif kind=='bad':
                self.bad_lines+=1
                if self.bad_lines<=3:self.log('忽略无效行：'+str(value))
            elif kind=='info':
                if not isinstance(value,dict):continue
                self.log('RX '+json.dumps(value,ensure_ascii=False))
                if value.get('type')=='ack':
                    message=value.get('message','')
                    if str(message).startswith('error_button'):
                        self.btn_text.set({'error_button_hold_one':'请仅按住一个按钮，停稳后重新采集。',
                            'error_button_duplicate':'这个实体按钮已经分配，请换一个按钮。',
                            'error_button_capture_all_four':'请先采集 A、B、X、Y 四个不同的按钮。',
                            'error_button_begin_first':'请先点击“开始”。'}.get(message,str(message)))
                    elif message=='button_calibration_saved':self.status.set('按钮校准已保存到控制器')
                if value.get('type')=='button_config':
                    try:assignments=button_assignments(value.get('map'))
                    except ValueError:self.log('忽略无效按钮映射');continue
                    if type(value.get('collecting')) is not bool:continue
                    self.buttons_calibrating=value['collecting']
                    if not self.buttons_calibrating:
                        self.btn_text.set('当前映射：'+'  ·  '.join(f'{key} → GPIO{pin}' for key,pin in assignments.items()))
                        for key,pin in assignments.items():self.button_table.item(key,values=(key,f'GPIO{pin}','—'))
                if value.get('type')=='button_capture' and value.get('button') in ('A','B','X','Y'):
                    key=value['button'];contact=value.get('contact')
                    if type(contact) is not int or contact not in (1,2,4,8):continue
                    pin={1:0,2:10,4:20,8:21}[contact];self.button_captures[key]=pin
                    self.button_table.item(key,values=(key,f'GPIO{pin}','已采集'))
                    i='ABXY'.index(key)
                    self.btn_text.set(f'已采集 {key}，共 {len(self.button_captures)}/4。'+('松开后，按住下一个按钮继续采集。' if i<3 else '点击“保存”完成。'))
                    if i<3:self.btn_target.set('ABXY'[i+1])
                if value.get('type')=='ack' and str(value.get('message','')).startswith('error_reverser'):
                    self.rev_text.set({'error_reverser_hold_still':'请停稳开关后重新采集',
                        'error_reverser_need_distinct_F_N_R_center_off':'保存失败：需采集 F、N、R 三个不同位置，N 必须中间断开',
                        'error_reverser_begin_first':'请先开始换向校准'}.get(value['message'],value['message']))
                if value.get('type')=='reverser_config':
                    self.reverser_calibrating=value.get('collecting',False)
                    if not self.reverser_calibrating:
                        self.rev_text.set(f'板上换向映射 F={value.get("F")}、N={value.get("N")}、R={value.get("R")}；已退出校准')
                if value.get('type')=='reverser_capture' and value.get('position') in ('F','N','R'):
                    pos=value['position'];i=('F','N','R').index(pos)
                    self.rev_text.set(f'已采集 {pos}：触点={value.get("contacts")}；'+('拨到 '+('F','N','R')[i+1]+' 后采集' if i<2 else '点击保存换向校准'))
                    if i<2:self.rev_target.set(('F','N','R')[i+1])
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
        self.write_buttons(self.gate.sample.buttons if self.gate.armed and self.gate.sample else 0)
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
