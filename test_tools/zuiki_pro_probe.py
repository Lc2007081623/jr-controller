"""Bounded Mascon Pro identity/axis experiment; this is still a DS4 descriptor."""
import argparse
import json
import queue
import time

from serial_notch_bridge import Reader
from serial_protocol import AutoDriveGate
from zuiki_virtual_test import ZuikiVirtual,NOTCH_BYTES,raw_hid_paths

VID,PID=0x33dd,0x0006
AXES={'x':'bThumbLX','z':'bThumbRX','rz':'bThumbRY'}

def probe_axis(axis,reverser,inverted=False):
    if axis not in AXES:raise ValueError('Unsupported probe axis')
    if reverser not in ('N','F','R'):raise ValueError('Invalid reverser')
    # RUNNING TRAIN feedback: the Rz probe's original F/N values were swapped.
    values={'N':0,'F':128,'R':255} if axis=='rz' else {'N':128,'F':0,'R':255}
    if inverted:values={**values,'F':values['R'],'R':values['F']}
    return AXES[axis],values[reverser]

class ProProbe(ZuikiVirtual):
    def __init__(self,axis=None,inverted=False):
        if axis is not None:probe_axis(axis,'N')
        self.axis=axis;self.inverted=inverted
        super().__init__(VID,PID)

    def set(self,notch,buttons=0,reverser='N'):
        # These axes are hypotheses, not a recovered Pro reverser protocol.
        for field in AXES.values():setattr(self.report,field,128)
        if self.axis:
            field,value=probe_axis(self.axis,reverser,self.inverted)
            setattr(self.report,field,value)
        elif reverser not in ('N','F','R'):raise ValueError('Invalid reverser')
        super().set(notch,buttons,'N')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial',help='Optional physical controller COM port')
    p.add_argument('--seconds',type=float,default=120)
    p.add_argument('--axis',choices=AXES,help='Explicit unverified reverser-axis hypothesis')
    p.add_argument('--invert',action='store_true')
    args=p.parse_args()
    if not 0<args.seconds<=900:p.error('--seconds must be in (0, 900]')
    if args.invert and not args.axis:p.error('--invert needs --axis')
    device=ProProbe(args.axis,args.invert);reader=None
    events=queue.Queue();gate=AutoDriveGate();last=None;direction='N'
    try:
        time.sleep(.5)
        paths=[v for v in raw_hid_paths() if 'vid_33dd&pid_0006' in v.lower()]
        print(json.dumps({'identity':'33DD:0006','descriptor':'DS4, not exact Mascon Pro',
                          'host_paths':paths,'axis_hypothesis':args.axis},ensure_ascii=False),flush=True)
        if not paths:raise RuntimeError('Windows did not enumerate the Pro identity')
        if args.serial:
            reader=Reader(args.serial,events);reader.start()
        end=time.monotonic()+args.seconds
        while time.monotonic()<end:
            for _ in range(160):
                try:owner,kind,value,arrival=events.get_nowait()
                except queue.Empty:break
                if owner is not reader:continue
                if kind=='sample':gate.receive(value,arrival)
                elif kind in ('closed','error'):raise RuntimeError('Serial disconnected: '+str(value))
            notch=gate.update(time.monotonic(),enabled=reader is not None)
            sample=gate.sample
            if not gate.armed:direction='N';buttons=0
            else:
                buttons=sample.buttons
                # The physical switch may change the hypothesis only at handle N.
                if notch=='N':direction=sample.reverser
            device.set(notch,buttons,direction)
            state=(notch,buttons,direction,gate.armed,gate.reason,
                   sample.notch if sample else None,sample.reverser if sample else None)
            if state!=last:
                print(json.dumps({'notch':notch,'buttons':buttons,'reverser':direction,
                                  'armed':gate.armed,'reason':gate.reason,
                                  'input_notch':sample.notch if sample else None,
                                  'input_reverser':sample.reverser if sample else None}),flush=True)
                last=state
            time.sleep(.02)
    finally:
        if reader:reader.stop_event.set();reader.join(timeout=1)
        try:device.set('N',0,'N')
        finally:device.close()

if __name__=='__main__':main()
