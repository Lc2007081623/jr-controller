import unittest
from unittest.mock import Mock,patch
from zuiki_pro import ZuikiProVirtual,VID,PID
from zuiki_virtual_test import ZuikiVirtual

class ProTests(unittest.TestCase):
    def test_verified_rz_mapping_and_button_preservation(self):
        with patch.object(ZuikiVirtual,'__init__') as init,patch.object(ZuikiVirtual,'set') as send:
            pad=ZuikiProVirtual();pad.report=Mock()
            init.assert_called_once_with(VID,PID)
            for direction,value in [('F',128),('N',0),('R',255)]:
                pad.set('P5',15,direction)
                self.assertEqual(pad.report.bThumbRY,value)
                send.assert_called_with('P5',15,'N')
            with self.assertRaises(ValueError):pad.set('N',0,'X')

if __name__=='__main__':unittest.main()
