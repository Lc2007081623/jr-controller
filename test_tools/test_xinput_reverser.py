import unittest
from xinput_notch_test import Backend,NOTCHES

class FakePad:
    def __init__(self):self.axes=None;self.updates=0;self.buttons=0;self.lt=0;self.rt=0
    def left_joystick(self,**kw):self.axes=kw
    def update(self):self.updates+=1
    def reset(self):self.axes=dict(x_value=0,y_value=0);self.buttons=0
    def press_button(self,button):self.buttons |= button
    def release_button(self,button):self.buttons &= ~button
    def left_trigger(self,value):self.lt=value
    def right_trigger(self,value):self.rt=value

class AxisTests(unittest.TestCase):
    def backend(self):
        b=Backend();b.pad=FakePad();return b
    def test_forward_latches_across_every_notch(self):
        b=self.backend();b.set_reverser('F')
        for notch,value in NOTCHES.items():
            b.set(notch)
            self.assertEqual(b.pad.axes,dict(x_value=32767,y_value=round(value*32767)))
    def test_reverser_change_preserves_notch(self):
        b=self.backend();b.set('B5');b.set_reverser('F')
        self.assertEqual(b.pad.axes['y_value'],round(NOTCHES['B5']*32767))
        b.set_reverser('N')
        self.assertEqual(b.pad.axes,dict(x_value=0,y_value=round(NOTCHES['B5']*32767)))
    def test_stop_neutralizes_both_axes(self):
        b=self.backend();b.set_reverser('F');b.set('P3')
        b.set('N');b.set_reverser('N')
        self.assertEqual(b.pad.axes,dict(x_value=0,y_value=0))
    def test_close_resets_and_removes_pad(self):
        b=self.backend();pad=b.pad;b.set_reverser('F');b.close()
        self.assertEqual(pad.axes,dict(x_value=0,y_value=0));self.assertIsNone(b.pad)
    def test_invalid_reverser_is_rejected(self):
        b=self.backend()
        with self.assertRaises(ValueError):b.set_reverser('P1')
    def test_reverse_latches_and_preserves_every_notch(self):
        b=self.backend();b.set_reverser('R')
        for notch,value in NOTCHES.items():
            b.set(notch)
            self.assertEqual(b.pad.axes,dict(x_value=-32767,y_value=round(value*32767)))
        b.set_reverser('N')
        self.assertEqual(b.pad.axes['x_value'],0)
    def test_abxy_combinations_release_and_preserve_axes(self):
        b=self.backend();b.set('B5');b.set_reverser('R');axes=b.pad.axes.copy()
        for mask in range(16):
            b.set_buttons(mask)
            self.assertEqual(b.pad.buttons,mask<<12)
            self.assertEqual(b.pad.axes,axes)
        updates=b.pad.updates;b.set_buttons(15)
        self.assertEqual(b.pad.updates,updates)
        b.set_buttons(0);self.assertEqual(b.pad.buttons,0)
        for mask in (True,-1,16,'1'):
            with self.assertRaises(ValueError):b.set_buttons(mask)
    def test_app_stop_releases_buttons_and_both_axes(self):
        from serial_notch_bridge import App
        from serial_protocol import DriveGate
        from unittest.mock import Mock
        app=App.__new__(App);app.pad=self.backend();app.gate=DriveGate()
        app.last_output='P3';app.log=Mock();app.forward_status=Mock()
        app.pad.set('P3');app.pad.set_reverser('F');app.pad.set_buttons(15)
        app.neutral()
        self.assertFalse(app.gate.armed)
        self.assertEqual(app.pad.pad.buttons,0)
        self.assertEqual(app.pad.pad.axes,dict(x_value=0,y_value=0))

    def test_custom_xbox_buttons_and_triggers_reset_with_existing_stop_path(self):
        b=self.backend();b.set('P3');axes=b.pad.axes.copy()
        b.set_xbox_buttons(0x0108, 3)
        self.assertEqual((b.pad.buttons,b.pad.lt,b.pad.rt), (0x0108,255,255))
        b.set_buttons(0)
        self.assertEqual((b.pad.buttons,b.pad.lt,b.pad.rt), (0,0,0))
        self.assertEqual(b.pad.axes,axes)
    def test_close_releases_held_buttons(self):
        b=self.backend();pad=b.pad;b.set_buttons(15);b.close()
        self.assertEqual(pad.buttons,0);self.assertEqual(b.buttons,0)

if __name__=='__main__':unittest.main()
