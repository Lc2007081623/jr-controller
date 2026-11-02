"""Experimental ZUIKI identity on a ViGEm DS4 HID; descriptor is still DS4."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import queue
import time
from xinput_notch_test import load_vgamepad
from serial_protocol import AutoDriveGate
from serial_notch_bridge import Reader

NOTCH_BYTES={'EB':0x00,'B8':0x05,'B7':0x13,'B6':0x20,'B5':0x2e,'B4':0x3c,
             'B3':0x49,'B2':0x57,'B1':0x65,'N':0x80,'P1':0x9f,'P2':0xb7,
             'P3':0xce,'P4':0xe6,'P5':0xff}

def report_values(notch,buttons=0,reverser='N'):
    if notch not in NOTCH_BYTES:raise ValueError('Unknown notch')
    if type(buttons) is not int or not 0<=buttons<=15:raise ValueError('Invalid buttons')
    if reverser not in ('N','F','R'):raise ValueError('Invalid reverser')
    # DS4 HID button usages 1..4 are square/cross/circle/triangle.
    bits={'N':8,'F':0,'R':4}[reverser]
    for i,flag in enumerate((0x40,0x20,0x80,0x10)):
        if buttons & (1<<i):bits |= flag
    if notch=='EB':bits |= 0x400  # ZUIKI also holds HID button 7 in EB.
    return NOTCH_BYTES[notch],bits

class ReverserPulses:
    """Saturate to a known direction, then select N with one Up if requested."""
    def __init__(self):
        self.target=None;self.steps=();self.index=0;self.next_at=0

    def update(self,target,now,enabled):
        if target not in ('F','N','R'):raise ValueError('Invalid reverser')
        if not enabled:
            self.target=None;self.steps=();return 'N'
        if target!=self.target:
            self.target=target
            self.steps=('F','N','F','N') if target=='F' else ('R','N','R','N')
            if target=='N':self.steps+=('F','N')
            self.index=0;self.next_at=now+.12
        elif self.index<len(self.steps) and now>=self.next_at:
            self.index+=1;self.next_at=now+.12
        return self.steps[self.index] if self.index<len(self.steps) else 'N'

def raw_hid_paths():
    class RawDevice(C.Structure):
        _fields_=[('handle',W.HANDLE),('type',W.DWORD)]
    user=C.WinDLL('user32',use_last_error=True)
    user.GetRawInputDeviceList.argtypes=[C.POINTER(RawDevice),C.POINTER(W.UINT),W.UINT]
    user.GetRawInputDeviceList.restype=W.UINT
    user.GetRawInputDeviceInfoW.argtypes=[W.HANDLE,W.UINT,C.c_void_p,C.POINTER(W.UINT)]
    user.GetRawInputDeviceInfoW.restype=W.UINT
    count=W.UINT()
    if user.GetRawInputDeviceList(None,C.byref(count),C.sizeof(RawDevice))==0xffffffff:raise C.WinError(C.get_last_error())
    entries=(RawDevice*count.value)()
    result=user.GetRawInputDeviceList(entries,C.byref(count),C.sizeof(RawDevice))
    if result==0xffffffff:raise C.WinError(C.get_last_error())
    paths=[]
    for entry in entries[:result]:
        if entry.type!=2:continue
        size=W.UINT()
        user.GetRawInputDeviceInfoW(entry.handle,0x20000007,None,C.byref(size))
        buffer=C.create_unicode_buffer(size.value+1)
        if user.GetRawInputDeviceInfoW(entry.handle,0x20000007,buffer,C.byref(size))!=0xffffffff:paths.append(buffer.value)
    return paths

class ZuikiVirtual:
    def __init__(self,vid=0x0f0d,pid=0x00c1):
        load_vgamepad()
        import vgamepad.win.vigem_client as client
        from vgamepad.win.vigem_commons import DS4_REPORT,DS4_REPORT_INIT
        self.api=client;self.client=client.vigem_alloc();self.target=None;self.attached=False
        self.report=DS4_REPORT();DS4_REPORT_INIT(self.report)
        try:
            self.check(client.vigem_connect(self.client))
            self.target=client.vigem_target_ds4_alloc()
            if not self.target:raise RuntimeError('Cannot allocate HID target')
            client.vigem_target_set_vid(self.target,vid);client.vigem_target_set_pid(self.target,pid)
            self.check(client.vigem_target_add(self.client,self.target));self.attached=True
            self.set('N')
        except Exception:
            self.close();raise

    @staticmethod
    def check(result):
        if result!=0x20000000:raise RuntimeError('ViGEm error '+hex(result))

    def set(self,notch,buttons=0,reverser='N'):
        self.report.bThumbLY,self.report.wButtons=report_values(notch,buttons,reverser)
        self.check(self.api.vigem_target_ds4_update(self.client,self.target,self.report))

    def close(self):
        if self.target:
            if self.attached:self.api.vigem_target_remove(self.client,self.target)
            self.api.vigem_target_free(self.target);self.target=None
        if self.client:
            self.api.vigem_disconnect(self.client);self.api.vigem_free(self.client);self.client=None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds',type=float,default=120)
    p.add_argument('--vid',type=lambda s:int(s,0),default=0x0f0d)
    p.add_argument('--pid',type=lambda s:int(s,0),default=0x00c1)
    p.add_argument('--notch',choices=NOTCH_BYTES,default='N')
    p.add_argument('--serial',help='Read calibrated C3 controller, e.g. COM7')
    args=p.parse_args()
    device=ZuikiVirtual(args.vid,args.pid)
    reader=None;events=queue.Queue();gate=AutoDriveGate();last=None;reverser=ReverserPulses()
    try:
        device.set(args.notch);time.sleep(.5)
        matching=[x for x in raw_hid_paths() if f'vid_{args.vid:04x}&pid_{args.pid:04x}' in x.lower()]
        print(json.dumps({'descriptor':'DS4 (experimental, not exact ZUIKI)','requested_vid':args.vid,'requested_pid':args.pid,'host_paths':matching,'notch':args.notch},ensure_ascii=False),flush=True)
        if not matching:raise RuntimeError('Requested HID identity was not enumerated by Windows')
        if args.serial:
            reader=Reader(args.serial,events);reader.start()
            print('Live serial input; return handle and reverser to N, release buttons. Reverser changes apply at handle N.',flush=True)
        end=time.monotonic()+args.seconds
        while time.monotonic()<end:
            if reader:
                for _ in range(160):
                    try:_,kind,value,arrival=events.get_nowait()
                    except queue.Empty:break
                    if kind=='sample':gate.receive(value,arrival)
                    elif kind in ('error','closed'):
                        device.set('N');raise RuntimeError('Serial disconnected: '+str(value))
                notch=gate.update(time.monotonic())
                buttons=gate.sample.buttons if gate.armed else 0
                target=gate.sample.reverser if gate.sample and gate.sample.reverser in ('F','N','R') else 'N'
                hat=reverser.update(target,time.monotonic(),gate.armed and notch=='N')
                device.set(notch,buttons,hat)
                current=(notch,buttons,gate.armed,target,hat)
                if current!=last:
                    print(json.dumps({'notch':notch,'axis2':NOTCH_BYTES[notch],'buttons':buttons,'armed':gate.armed,'reverser':target,'hat':hat,'status':'ZUIKI active' if gate.armed else gate.reason},ensure_ascii=False),flush=True);last=current
            else:device.set(args.notch)
            time.sleep(.02)
    finally:
        if reader:reader.stop_event.set();reader.join(timeout=1)
        device.close()

if __name__=='__main__':main()
