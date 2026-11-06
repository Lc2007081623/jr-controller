import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import install_check

class InstallCheckTests(unittest.TestCase):
    def test_both_modes_neutral_and_closed_without_serial_hardware(self):
        pads=[Mock() for _ in install_check.MODES]
        with patch.object(install_check,'create_backend',side_effect=pads),patch.object(install_check.time,'sleep'),patch.object(install_check,'raw_hid_paths',return_value=['HID#VID_33DD&PID_0006']):
            result=install_check.check_installation()
        self.assertTrue(result['ok']);self.assertEqual(len(result['checks']),len(install_check.MODES))
        for pad in pads:
            pad.set.assert_called_once_with('N');pad.set_reverser.assert_called_once_with('N')
            pad.set_buttons.assert_called_once_with(0);pad.close.assert_called_once()

    def test_driver_failure_reported_and_all_devices_closed(self):
        pads=[Mock() for _ in install_check.MODES];pads[0].connect.side_effect=RuntimeError('missing bus')
        with patch.object(install_check,'create_backend',side_effect=pads),patch.object(install_check.time,'sleep'),patch.object(install_check,'raw_hid_paths',return_value=['HID#VID_33DD&PID_0006']):
            result=install_check.check_installation()
        self.assertFalse(result['ok']);self.assertIn('missing bus',result['checks'][0]['error'])
        for pad in pads:pad.close.assert_called_once()

    def test_missing_pro_enumeration_fails_check(self):
        with patch.object(install_check,'create_backend',side_effect=[Mock() for _ in install_check.MODES]),patch.object(install_check.time,'sleep'),patch.object(install_check,'raw_hid_paths',return_value=[]):
            self.assertFalse(install_check.check_installation()['ok'])

    def test_cli_result_file_and_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(install_check,'check_installation',return_value={'ok':False,'checks':[]}):
            target=Path(temp)/'result.json';self.assertEqual(install_check.write_check(target),1)
            self.assertFalse(json.loads(target.read_text(encoding='utf-8'))['ok'])

if __name__=='__main__':unittest.main()
