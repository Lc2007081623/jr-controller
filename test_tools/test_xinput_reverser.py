import unittest
from xinput_notch_test import Backend,NOTCHES

class FakePad:
    def __init__(self):self.axes=None;self.updates=0
    def left_joystick(self,**kw):self.axes=kw
    def update(self):self.updates+=1
    def reset(self):self.axes=dict(x_value=0,y_value=0)

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

if __name__=='__main__':unittest.main()
