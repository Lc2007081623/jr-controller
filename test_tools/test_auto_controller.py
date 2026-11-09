import unittest
import queue
import time
from unittest.mock import Mock, patch
from types import SimpleNamespace
from serial_protocol import AutoDriveGate,parse_sample
from test_serial_protocol import frame
from controller_app import controller_ports,App
from output_profiles import BVE,TRAIN_CREW,XBOX,ZUIKI

class AutomaticTests(unittest.TestCase):
    def test_jr_launcher_switches_mode_waits_and_starts_once(self):
        entry = r'C:\Games\JR EAST\JREAST_TrainSimulator.exe'
        app = Mock()
        app.jr_pending = None
        app.output_mode = ZUIKI
        app.change_mode.side_effect = lambda: App.change_mode(app)
        app.cancel_jr_launch.side_effect = lambda: App.cancel_jr_launch(app)
        app.mode.get.return_value = XBOX
        app.gate.armed = False
        with patch('controller_app.load_settings', return_value={'jr_launch_entry': entry}), \
             patch('controller_app.Path.is_file', return_value=True), \
             patch('controller_app.save_mode'), patch('controller_app.os.startfile') as start:
            App.request_jr_launch(app)
            self.assertEqual(app.output_mode, XBOX)
            app.drop_pad.assert_called_once()
            App.launch_jr_if_ready(app)
            start.assert_not_called()
            app.gate.armed = True
            App.launch_jr_if_ready(app)
            App.launch_jr_if_ready(app)
            start.assert_called_once_with(entry, cwd=r'C:\Games\JR EAST')

    def test_jr_launcher_warns_if_game_starts_while_waiting(self):
        app = Mock()
        app.jr_pending = 'steam://rungameid/2111630'
        app.output_mode = XBOX
        app.gate.armed = True
        app.jr_can_start.side_effect = lambda entry: App.jr_can_start(app, entry)
        with patch('controller_app.jr_game_running', return_value=True), \
             patch('controller_app.messagebox.showwarning') as warn, \
             patch('controller_app.os.startfile') as start:
            App.launch_jr_if_ready(app)
            app.cancel_jr_launch.assert_called_once()
            warn.assert_called_once()
            start.assert_not_called()

    def test_bve_heartbeat_even_with_unchanged_notch_and_release_on_pause(self):
        for mode in (BVE,TRAIN_CREW):
            app=Mock();app.output_mode=mode;app.closing=False;app.calibration=None
            app.events=queue.Queue();app.last_sample_at=time.monotonic()
            app.gate.sample=self.sample(notch='P3',reverser='F');app.gate.armed=True
            app.gate.update.return_value='P3';app.pad.notch='P3';app.pad.reverser='F'
            App.tick(app)
            app.pad.set.assert_not_called();app.pad.refresh.assert_called_once_with(True)
            App.release(app)
            app.pad.refresh.assert_called_with(False)

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
    def test_any_valid_position_and_held_buttons_arm_immediately(self):
        for values in ({'notch':'P5','reverser':'F','buttons':15},
                       {'notch':'EB','reverser':'R'},{'notch':'B1'}):
            g=AutoDriveGate();g.receive(self.sample(**values),0)
            self.assertEqual(g.update(0),values['notch']);self.assertTrue(g.armed)
    def test_invalid_sensor_calibration_and_contacts_do_not_arm(self):
        for values in ({'calibrated':False,'notch':'--'},{'reverser':'X'},
                       {'sensor_ok':False,'calibrated':False,'notch':'--'}):
            g=AutoDriveGate();self.stable(g,**values);self.assertFalse(g.armed)
    def test_timeout_and_fault_release_then_resume_at_current_position(self):
        for change in ({'sensor_ok':False,'calibrated':False,'notch':'--'},
                       {'reverser':'X'}):
            g=AutoDriveGate();self.stable(g);self.assertTrue(g.armed)
            g.receive(self.sample(seq=6,**change),.5);g.update(.5)
            self.assertFalse(g.armed)
        g=AutoDriveGate();self.stable(g);self.assertEqual(g.update(1),'N')
        g.receive(self.sample(seq=6,notch='P5'),1.1);g.update(1.1)
        self.assertTrue(g.armed);self.assertEqual(g.update(1.1),'P5')
        g.receive(self.sample(boot=456,seq=1,notch='EB',reverser='R'),1.2)
        self.assertEqual(g.update(1.2),'EB');self.assertTrue(g.armed)
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

    def test_main_app_sends_reverser_while_handle_is_in_power(self):
        app=Mock();app.closing=False;app.calibration=None;app.events=queue.Queue()
        app.last_sample_at=time.monotonic();app.gate.armed=True
        app.gate.sample=self.sample(notch='P5',reverser='R',buttons=3)
        app.gate.update.return_value='P5'
        app.pad.notch='P5';app.pad.reverser='F'
        App.tick(app)
        app.pad.set_reverser.assert_called_once_with('R')
        app.pad.set_buttons.assert_called_once_with(3)

if __name__=='__main__':unittest.main()
