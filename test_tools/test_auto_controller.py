import unittest
from types import SimpleNamespace
from serial_protocol import AutoDriveGate,parse_sample
from test_serial_protocol import frame
from controller_app import controller_ports

class AutomaticTests(unittest.TestCase):
    def sample(self,**kw):
        values=dict(board='C3',reverser='N');values.update(kw)
        return parse_sample(frame(**values))
    def stable(self,g,start=0,seq=1,**kw):
        for i in range(5):
            g.receive(self.sample(seq=seq+i,**kw),start+i*.1);g.update(start+i*.1)
    def test_stable_neutral_arms_then_notches_follow(self):
        g=AutoDriveGate();self.stable(g);self.assertTrue(g.armed)
        g.receive(self.sample(seq=6,notch='P5'),.5)
        self.assertEqual(g.update(.5),'P5')
    def test_non_neutral_or_held_buttons_never_auto_arm(self):
        for values in ({'notch':'P1'},{'reverser':'F'},{'buttons':1},
                       {'calibrated':False,'notch':'--'},{'reverser':'X'}):
            g=AutoDriveGate();self.stable(g,**values);self.assertFalse(g.armed)
    def test_timeout_fault_restart_require_neutral_again(self):
        for change in ({'boot':456},{'sensor_ok':False,'calibrated':False,'notch':'--'},
                       {'reverser':'X'}):
            g=AutoDriveGate();self.stable(g);self.assertTrue(g.armed)
            g.receive(self.sample(seq=6,**change),.5);g.update(.5)
            self.assertFalse(g.armed)
        g=AutoDriveGate();self.stable(g);self.assertEqual(g.update(1),'N')
        g.receive(self.sample(seq=6,notch='P5'),1.1);g.update(1.1)
        self.assertFalse(g.armed)
        self.stable(g,start=1.2,seq=7);self.assertTrue(g.armed)
    def test_stale_backlog_and_disabled_do_not_arm(self):
        g=AutoDriveGate()
        for i in range(5):
            g.receive(self.sample(seq=i+1),i*.1);g.update(10)
        self.assertFalse(g.armed)
        g=AutoDriveGate();self.stable(g);g.update(.4,enabled=False)
        self.assertFalse(g.armed)
    def test_only_native_esp_usb_ports(self):
        ports=[SimpleNamespace(device='COM7',vid=0x303a,pid=0x1001),
               SimpleNamespace(device='COM8',vid=None,pid=None)]
        self.assertEqual(controller_ports(ports),['COM7'])

if __name__=='__main__':unittest.main()
