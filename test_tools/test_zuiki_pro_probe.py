import unittest
from unittest.mock import Mock,patch
from zuiki_pro_probe import ProProbe,probe_axis,AXES,VID,PID
from zuiki_virtual_test import ZuikiVirtual

class ProProbeTests(unittest.TestCase):
    def test_hypothesis_values_and_inversion(self):
        for axis,field in AXES.items():
            neutral,forward=(0,128) if axis=='rz' else (128,0)
            self.assertEqual(probe_axis(axis,'N'),(field,neutral))
            self.assertEqual(probe_axis(axis,'F'),(field,forward))
            self.assertEqual(probe_axis(axis,'R',True),(field,forward))
            self.assertEqual(probe_axis(axis,'N',True),(field,neutral))
        for args in [('y','N'),('x','X')]:
            with self.assertRaises(ValueError):probe_axis(*args)

    def test_pro_identity_and_axis_released_on_neutral(self):
        with patch.object(ZuikiVirtual,'__init__') as init,patch.object(ZuikiVirtual,'set') as send:
            pad=ProProbe('rz');init.assert_called_once_with(VID,PID)
            pad.report=Mock();pad.set('N',15,'R')
            self.assertEqual(pad.report.bThumbRY,255)
            self.assertEqual(pad.report.bThumbLX,128)
            send.assert_called_with('N',15,'N')
            pad.set('N',0,'N');self.assertEqual(pad.report.bThumbRY,0)

    def test_running_train_rz_forward_and_neutral_swap_preserves_reverse(self):
        self.assertEqual([probe_axis('rz',v)[1] for v in ('F','N','R')],[128,0,255])

    def test_default_probe_sends_no_direction_hypothesis(self):
        with patch.object(ZuikiVirtual,'__init__'),patch.object(ZuikiVirtual,'set'):
            pad=ProProbe();pad.report=Mock();pad.set('N',0,'F')
            for field in AXES.values():self.assertEqual(getattr(pad.report,field),128)

if __name__=='__main__':unittest.main()
