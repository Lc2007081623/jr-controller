"""Pure protocol/arming logic. Importing this module never creates a controller."""
import json
from dataclasses import dataclass

NOTCH_ORDER = ('EB','B8','B7','B6','B5','B4','B3','B2','B1','N','P1','P2','P3','P4','P5')

def button_assignments(values):
    if (not isinstance(values,list) or len(values)!=4 or
            not all(type(x) is int and x in (1,2,4,8) for x in values) or len(set(values))!=4):
        raise ValueError('invalid button mapping')
    pins={1:0,2:10,4:20,8:21}
    return dict(zip('ABXY',(pins[x] for x in values)))

@dataclass(frozen=True)
class Sample:
    boot: int
    seq: int
    ms: int
    raw: int
    adc: int
    calibrated: bool
    notch: str
    forward_pressed: bool = False
    forward_count: int = 0
    sensor: str = 'ADC'
    sensor_ok: bool = True
    board: str = 'S3'
    reverser: str | None = None
    buttons: int = 0

def parse_sample(line):
    if len(line) > 512:
        raise ValueError('line too long')
    try:
        data = json.loads(line)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('invalid JSON') from exc
    if not isinstance(data,dict) or data.get('v') != 1 or type(data.get('v')) is not int:
        raise ValueError('unsupported protocol')
    if data.get('type') != 'state':
        return None
    for key, high in [('boot',0xffffffff),('seq',0xffffffff),('ms',0xffffffff),('raw',4095),('adc',4095)]:
        if type(data.get(key)) is not int or not 0 <= data[key] <= high:
            raise ValueError('invalid '+key)
    if type(data.get('calibrated')) is not bool:
        raise ValueError('invalid calibration flag')
    notch = data.get('notch')
    if data['calibrated']:
        if notch not in NOTCH_ORDER: raise ValueError('invalid notch')
    elif notch != '--':
        raise ValueError('uncalibrated sample must not claim a notch')
    data.setdefault('forward_pressed',False)
    data.setdefault('forward_count',0)
    if type(data['forward_pressed']) is not bool:
        raise ValueError('invalid forward button')
    if type(data['forward_count']) is not int or not 0 <= data['forward_count'] <= 0xffffffff:
        raise ValueError('invalid forward count')
    data.setdefault('sensor','ADC');data.setdefault('sensor_ok',True)
    if data['sensor'] not in ('ADC','AS5600') or type(data['sensor_ok']) is not bool:
        raise ValueError('invalid sensor status')
    if not data['sensor_ok'] and data['calibrated']:
        raise ValueError('invalid sensor cannot report a calibrated notch')
    data.setdefault('board','S3');data.setdefault('reverser',None);data.setdefault('buttons',0)
    if data['board'] not in ('S3','C3') or data['reverser'] not in (None,'F','N','R','X'):
        raise ValueError('invalid board/reverser')
    if data['board']=='C3' and data['reverser'] is None:
        raise ValueError('C3 requires reverser contacts')
    if type(data['buttons']) is not int or not 0 <= data['buttons'] <= 15:
        raise ValueError('invalid buttons')
    return Sample(**{key:data[key] for key in Sample.__dataclass_fields__})

class ReverserSwitchGate:
    """Consume changes outside handle N, while disarmed, or from old frames."""
    def __init__(self):
        self.previous=None

    def receive(self,sample,arrival,now,armed):
        previous,self.previous=self.previous,sample
        if previous is None or sample.boot != previous.boot:
            return None
        if (sample.reverser in ('F','N','R') and sample.reverser != previous.reverser
                and armed and sample.calibrated and sample.sensor_ok and sample.notch=='N'
                and 0 <= now-arrival <= .15):
            return sample.reverser
        return None

class ForwardPressGate:
    """Consume every counter change; never replay a press on arm/reconnect/reset."""
    def __init__(self):
        self.previous=None

    def receive(self,sample,arrival,now,armed):
        previous,self.previous=self.previous,sample
        if previous is None or sample.boot != previous.boot:
            return False
        delta=(sample.forward_count-previous.forward_count)&0xffffffff
        return (delta==1 and sample.forward_pressed and armed and sample.calibrated
                and sample.notch=='N' and 0 <= now-arrival <= .15)

class DriveGate:
    """Manual arm, neutral on timeout/invalid calibration/reset, no auto-rearm."""
    def __init__(self, timeout=0.5):
        self.timeout=timeout
        self.sample=None
        self.received=None
        self.armed=False
        self.reason='monitor only'

    def receive(self,sample,now):
        if self.received is not None and now-self.received > self.timeout:
            self.disarm('serial gap; re-arm manually')
        if self.sample is not None and sample.boot==self.sample.boot:
            delta=(sample.seq-self.sample.seq)&0xffffffff
            if not 0 < delta < 0x80000000:
                return False
        if self.sample is not None and sample.boot!=self.sample.boot:
            self.disarm('device restarted; re-arm manually')
        self.sample=sample
        self.received=now
        if sample.reverser == 'X':
            self.disarm('invalid reverser contacts; re-arm manually')
        elif not sample.sensor_ok:
            self.disarm('sensor invalid; re-arm manually')
        elif not sample.calibrated:
            self.disarm('calibration required/in progress')
        return True

    def arm(self,now):
        if self.received is None or now-self.received > self.timeout or not self.sample.calibrated:
            raise ValueError('need fresh calibrated data')
        if self.sample.notch != 'N':
            raise ValueError('move handle to N before enabling XInput')
        if self.sample.reverser not in (None,'N'):
            raise ValueError('move reverser switch to N before enabling XInput')
        self.armed=True
        self.reason='XInput enabled'

    def disarm(self,reason='monitor only'):
        self.armed=False
        self.reason=reason

    def output(self,now):
        if self.received is not None and now-self.received > self.timeout:
            self.disarm('serial timeout; N sent; re-arm manually')
        return self.sample.notch if self.armed else 'N'

class AutoDriveGate(DriveGate):
    """Follow any fresh calibrated position immediately; faults release output."""
    def update(self,now,enabled=True):
        self.output(now)
        fresh=self.received is not None and 0 <= now-self.received <= .15
        if not enabled or not fresh or not self.sample.calibrated or not self.sample.sensor_ok or self.sample.reverser=='X':
            self.disarm('等待控制器或完成校准')
        else:
            self.armed=True;self.reason='已连接，实时输出'
        return self.sample.notch if self.armed else 'N'
