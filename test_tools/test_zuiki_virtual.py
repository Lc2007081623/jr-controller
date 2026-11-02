import unittest
from zuiki_virtual_test import report_values,NOTCH_BYTES,ReverserPulses

class ZuikiTests(unittest.TestCase):
    def test_all_15_positions_and_emergency_button(self):
        self.assertEqual(len(NOTCH_BYTES),15)
        for name,value in NOTCH_BYTES.items():
            axis,buttons=report_values(name)
            self.assertEqual(axis,value)
            self.assertEqual(buttons,0x408 if name=='EB' else 8)
        self.assertEqual(report_values('N')[0],128)
        self.assertEqual(report_values('P5')[0],255)
    def test_face_buttons_and_hat_are_independent(self):
        for mask in range(16):
            _,buttons=report_values('N',mask,'F')
            self.assertEqual(buttons&15,0)
            self.assertEqual((buttons>>4)&15,((mask&1)<<2)|(mask&2)|((mask&4)<<1)|((mask&8)>>3))
        self.assertEqual(report_values('N',0,'R')[1],4)
    def test_reject_invalid_input(self):
        for args in [('P6',),('N',16),('N',True),('N',0,'X')]:
            with self.assertRaises(ValueError):report_values(*args)
    def test_reverser_saturates_and_releases(self):
        for target,expected in [('F',['F','N','F','N','N']),('R',['R','N','R','N','N']),
                                ('N',['R','N','R','N','F','N','N'])]:
            gate=ReverserPulses()
            actual=[gate.update(target,i*.13,True) for i in range(len(expected))]
            self.assertEqual(actual,expected)
            self.assertEqual(gate.update(target,5,True),'N')
    def test_reverser_interrupt_and_resume_rehomes(self):
        g=ReverserPulses();self.assertEqual(g.update('F',0,True),'F')
        self.assertEqual(g.update('F',.1,False),'N')
        self.assertEqual(g.update('F',.2,True),'F')
        self.assertEqual(g.update('R',.21,True),'R')

if __name__=='__main__':unittest.main()
