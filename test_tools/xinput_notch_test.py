"""Manual, Steam-independent XInput axis test. Does not modify the game."""
import ctypes as C
from ctypes import wintypes as W
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'python_deps'))
NOTCHES = {'EB':.96,'B8':.87,'B7':.76,'B6':.655,'B5':.545,'B4':.43,
           'B3':.32,'B2':.205,'B1':.105,'N':0,'P1':-.20,'P2':-.40,
           'P3':-.60,'P4':-.81,'P5':-.96}

class Gamepad(C.Structure):
    _fields_=[('buttons',W.WORD),('lt',C.c_ubyte),('rt',C.c_ubyte),
              ('lx',C.c_short),('ly',C.c_short),('rx',C.c_short),('ry',C.c_short)]
class State(C.Structure):
    _fields_=[('packet',W.DWORD),('gamepad',Gamepad)]

def slots():
    dll=C.WinDLL('XInput1_4.dll')
    dll.XInputGetState.argtypes=[W.DWORD,C.POINTER(State)]
    dll.XInputGetState.restype=W.DWORD
    result=[]
    for i in range(4):
        s=State()
        if dll.XInputGetState(i,C.byref(s))==0:
            result.append({'slot':i,'packet':s.packet,'lx':s.gamepad.lx,
                           'ly':s.gamepad.ly,'buttons':s.gamepad.buttons})
    return result

class Backend:
    def __init__(self):
        self.pad=None
        self.notch='N';self.reverser='N'
    def connect(self):
        if self.pad is not None:return
        # Python's platform.system() can block on a stalled Windows WMI service.
        # The executable/platform and pointer width are already known locally.
        import platform
        old_system,old_arch=platform.system,platform.architecture
        platform.system=lambda:'Windows' if sys.platform=='win32' else old_system()
        platform.architecture=lambda *a,**k:(str(C.sizeof(C.c_void_p)*8)+'bit','WindowsPE')
        try:
            import vgamepad
        finally:
            platform.system,platform.architecture=old_system,old_arch
        self.pad=vgamepad.VX360Gamepad()
        self.notch='N';self.reverser='N'
        self.pad.reset();self.pad.update()
    def set(self,name):
        if self.pad is None:raise RuntimeError('Virtual controller is not connected')
        self.notch=name
        return self._report()
    def set_reverser(self,name):
        if self.pad is None:raise RuntimeError('Virtual controller is not connected')
        if name not in ('N','F'):raise ValueError('Unsupported reverser position')
        self.reverser=name
        self._report()
    def _report(self):
        name=self.notch
        y=round(NOTCHES[name]*32767)
        self.pad.left_joystick(x_value=32767 if self.reverser=='F' else 0,y_value=y)
        self.pad.update()
        return y
    def close(self):
        if self.pad:
            self.pad.reset();self.pad.update();self.pad=None

def log_event(event):
    event={'time':time.strftime('%Y-%m-%d %H:%M:%S'),**event}
    with (HERE/'test_events.jsonl').open('a',encoding='utf-8') as f:
        f.write(json.dumps(event,ensure_ascii=False)+'\n')

def probe():
    result={'before':slots()};b=Backend()
    try:
        b.connect();time.sleep(1)
        result['connected']=slots()
        # Windows API verification only: brief N/P1/N; game should be paused.
        result['sent_y']=b.set('P1');time.sleep(.2)
        result['p1_readback']=slots()
        b.set('N');time.sleep(.1);result['neutral']=slots()
    except Exception as e:result['error']=str(e)
    finally:b.close()
    log_event({'probe':result});print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if 'error' in result else 0

def gui():
    import tkinter as tk
    from tkinter import ttk
    root=tk.Tk();root.title('JR 绝对档位 XInput 测试');root.geometry('820x590')
    b=Backend();pending=None
    status=tk.StringVar(value='未连接虚拟手柄')
    chosen=tk.StringVar(value='N');delay=tk.IntVar(value=3)
    ttk.Label(root,text='中央线 E233 0 番台 · 左摇杆 Y 绝对档位测试',font=('Microsoft YaHei',14)).pack(pady=12)
    ttk.Label(root,text='先连接虚拟手柄；选择档位后切回游戏。此程序不更改游戏文件或设置。').pack()
    ttk.Label(root,textvariable=status,wraplength=770).pack(pady=10)
    controls=ttk.Frame(root);controls.pack()
    box=tk.Text(root,height=15,width=102);box.pack(side='bottom',padx=12,pady=12)
    def log(msg):
        box.insert('end',time.strftime('%H:%M:%S')+' '+msg+'\n');box.see('end')
    def connect():
        try:
            before=slots();b.connect();status.set('已连接；等待设备枚举');
            log('连接前 '+json.dumps(before));root.after(1200,refresh)
        except Exception as e:status.set('连接失败：'+str(e));log(str(e))
    def refresh():
        state=slots();log('XInput '+json.dumps(state))
        if state:
            status.set('已连接。游戏使用首个有效 XInput 槽；若真实 Xbox 手柄占用低号槽，请先断开该手柄。')
        else:status.set('尚无 XInput 槽，请检查驱动连接')
    def cancel():
        nonlocal pending
        if pending is not None:root.after_cancel(pending);pending=None
    def send(name):
        nonlocal pending
        pending=None
        try:
            y=b.set(name);chosen.set(name)
            event={'notch':name,'y':y,'slots':slots()};log_event(event)
            log(f'发送 {name}，Y={y}；读回 '+json.dumps(event['slots']))
            status.set(f'正在输出 {name} / Y={y}。请以游戏 HUD 判定实际档位。')
        except Exception as e:status.set(str(e));log(str(e))
    def schedule(name):
        nonlocal pending
        cancel();seconds=max(0,min(15,delay.get()))
        status.set(f'{seconds} 秒后输出 {name}，现在切回游戏。')
        pending=root.after(seconds*1000,lambda:send(name))
    ttk.Button(controls,text='连接虚拟手柄',command=connect).grid(row=0,column=0,padx=6)
    ttk.Button(controls,text='查看 XInput 槽',command=refresh).grid(row=0,column=1,padx=6)
    ttk.Label(controls,text='发送延迟（秒）').grid(row=0,column=2)
    ttk.Spinbox(controls,from_=0,to=15,textvariable=delay,width=4).grid(row=0,column=3)
    grid=ttk.Frame(root);grid.pack(pady=15)
    for i,(name,value) in enumerate(NOTCHES.items()):
        ttk.Button(grid,text=f'{name}\nY={value:+.3f}',width=12,
                   command=lambda n=name:schedule(n)).grid(row=i//5,column=i%5,padx=5,pady=6)
    ttk.Button(root,text='取消排队并立即输出 N',command=lambda:(cancel(),send('N'))).pack(pady=3)
    ttk.Label(root,text='分别记录 P1/P3/B1/B5 是否直接命中。首次验证前保持游戏静止或暂停；EB 单独手动测试。').pack(pady=8)
    def close():
        cancel();b.close();root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    log('初始 XInput 槽 '+json.dumps(slots()))
    root.after(200,connect)
    root.mainloop()

if __name__=='__main__':
    if '--self-test' in sys.argv:
        assert C.sizeof(State)==16
        assert all(-32768<=round(x*32767)<=32767 for x in NOTCHES.values())
        assert len(set(round(x*32767) for x in NOTCHES.values()))==15
        print('PASS: XInput structure and 15 distinct notch outputs')
    elif '--probe' in sys.argv:sys.exit(probe())
    elif '--slots' in sys.argv:print(json.dumps(slots(),indent=2))
    else:gui()
