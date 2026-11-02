import itertools
import queue
import sys
import unittest
import json
import time
import tkinter as tk
from unittest.mock import patch,Mock
from types import SimpleNamespace
from serial_protocol import button_assignments,parse_sample
from serial_notch_bridge import Reader,App

class ButtonCalibrationTests(unittest.TestCase):
    def test_all_permutations_and_strict_validation(self):
        for values in itertools.permutations((1,2,4,8)):
            result=button_assignments(list(values))
            self.assertEqual(set(result),set('ABXY'))
            self.assertEqual(set(result.values()),{0,10,20,21})
        for bad in (None,{},[1,2,4],[1,1,4,8],[True,2,4,8],[1,2,4,16],[[],2,4,8]):
            with self.assertRaises(ValueError):button_assignments(bad)
    def test_calibration_disconnect_cancels_pending_learning(self):
        events=queue.Queue();reader=Reader('COM7',events,exit_commands=('CANCEL','RCANCEL','KCANCEL'))
        class Connection:
            in_waiting=0
            def __init__(self):self.writes=[];self.flushed=False;self.closed=False
            def __enter__(self):return self
            def __exit__(self,*args):self.closed=True
            def read(self,size):reader.stop_event.set();return b''
            def write(self,data):self.writes.append(data)
            def flush(self):self.flushed=True
        connection=Connection()
        with patch.dict(sys.modules,{'serial':SimpleNamespace(Serial=lambda:connection)}):reader.run()
        self.assertEqual(connection.writes,[b'CANCEL\n',b'RCANCEL\n',b'KCANCEL\n'])
        self.assertTrue(connection.flushed);self.assertTrue(connection.closed)
    def test_ui_capture_advances_then_save_displays_board_mapping(self):
        root=tk.Tk();root.withdraw();app=App(root,calibration_only=True)
        reader=Mock();reader.commands=queue.Queue();app.reader=reader;app.connected=True
        sample=parse_sample(json.dumps(dict(v=1,type='state',boot=1,seq=1,ms=20,raw=1000,adc=1000,
            calibrated=True,notch='N',board='C3',reverser='N')))
        app.gate.receive(sample,time.monotonic())
        try:
            app.button_command('KBEGIN')
            self.assertEqual(reader.commands.get_nowait(),'KBEGIN')
            self.assertTrue(app.buttons_calibrating)
            app.events.put((reader,'info',dict(type='button_capture',button='A',contact=8),time.monotonic()))
            app.tick()
            self.assertEqual(app.btn_target.get(),'B')
            self.assertEqual(app.button_table.item('A')['values'][1],'GPIO21')
            app.events.put((reader,'info',dict(type='button_config',map=[8,4,2,1],collecting=False),time.monotonic()))
            app.tick()
            self.assertFalse(app.buttons_calibrating)
            self.assertEqual(app.button_table.item('Y')['values'][1],'GPIO0')
        finally:app.close()

if __name__=='__main__':unittest.main()
