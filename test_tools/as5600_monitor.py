"""Live display for the independent AS5600 test firmware; no game outputs."""
import json
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk
from serial_notch_bridge import Reader

def parse_reading(line):
    d=json.loads(line)
    if not isinstance(d,dict) or d.get('type')!='as5600':return None
    for key in ('i2c_ok','valid'):
        if type(d.get(key)) is not bool:raise ValueError('Invalid '+key)
    if not d['i2c_ok']:
        if d['valid']:raise ValueError('Disconnected sensor cannot be valid')
        return d
    if type(d.get('raw')) is not int or not 0<=d['raw']<=4095:raise ValueError('Invalid angle')
    for key in ('magnet_detected','weak','strong'):
        if type(d.get(key)) is not bool:raise ValueError('Invalid '+key)
    if d['valid']!=(d['magnet_detected'] and not d['weak'] and not d['strong']):
        raise ValueError('Inconsistent magnet state')
    return d

class Monitor:
    def __init__(self,root):
        self.root=root;self.last=None;self.events=queue.Queue()
        root.title('AS5600 实时角度 · COM4 · SDA7 / SCL15');root.geometry('600x340')
        ttk.Label(root,text='AS5600 · ESP32-S3 · SDA7 / SCL15',font=('Microsoft YaHei',16)).pack(pady=16)
        self.angle=tk.StringVar(value='等待数据');self.raw=tk.StringVar(value='RAW —')
        self.status=tk.StringVar(value='正在连接 COM4 / 115200')
        ttk.Label(root,textvariable=self.angle,font=('Consolas',44)).pack(pady=4)
        ttk.Label(root,textvariable=self.raw,font=('Consolas',17)).pack(pady=7)
        self.status_label=tk.Label(root,textvariable=self.status,font=('Microsoft YaHei',13),wraplength=560)
        self.status_label.pack(pady=8)
        ttk.Label(root,text='转动磁铁或手柄观察角度；359° → 0° 是正常跨圈。\n关闭窗口会释放串口；本窗口不控制游戏。').pack(pady=8)
        self.reader=Reader('COM4',self.events,parse_reading);self.reader.start()
        root.protocol('WM_DELETE_WINDOW',self.close);root.after(50,self.tick)

    def tick(self):
        for _ in range(100):
            try:_,kind,data,arrival=self.events.get_nowait()
            except queue.Empty:break
            if kind=='sample':
                self.last=arrival
                valid=data['valid']
                self.angle.set(f"{data['raw']*360/4096:.2f}°" if valid else '—')
                self.raw.set(f"RAW {data['raw']} / 4095" if data['i2c_ok'] else 'RAW —')
                message=('通信失败：检查供电和 SDA7 / SCL15' if not data['i2c_ok'] else
                         '未检测到磁铁' if not data['magnet_detected'] else
                         '磁场过弱：检查磁铁位置和距离' if data['weak'] else
                         '磁场过强：适当增加距离' if data['strong'] else '通信正常 · 磁铁状态有效')
                self.status.set(message);self.status_label.config(fg='green' if valid else 'red')
            elif kind=='error':
                self.status.set('串口错误：'+str(data));self.status_label.config(fg='red')
        if self.last is not None and time.monotonic()-self.last>1:
            self.angle.set('—');self.status.set('数据超时：检查USB连接');self.status_label.config(fg='red')
        self.root.after(50,self.tick)

    def close(self):
        self.reader.stop_event.set();self.reader.join(timeout=1);self.root.destroy()

if __name__=='__main__':
    if '--self-test' in sys.argv:
        good=dict(type='as5600',i2c_ok=True,valid=True,raw=3638,magnet_detected=True,weak=False,strong=False)
        assert parse_reading(json.dumps(good))['raw']==3638
        assert parse_reading('{"type":"as5600","i2c_ok":false,"valid":false}')['valid'] is False
        for change in ({'raw':4096},{'valid':False},{'weak':True},{'i2c_ok':False}):
            try:parse_reading(json.dumps(good|change))
            except ValueError:pass
            else:raise AssertionError(change)
        print('AS5600 monitor self-test passed')
    else:
        root=tk.Tk();Monitor(root);root.mainloop()
