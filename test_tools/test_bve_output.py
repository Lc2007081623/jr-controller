import ctypes
import mmap
import unittest
from unittest.mock import patch

import bve_output as bve


class BveTests(unittest.TestCase):
    def test_all_notches_and_publication_release(self):
        with patch.object(bve, 'MAP_NAME', r'Local\JRController.BVE.test'):
            pad = bve.BveBackend()
            pad.connect()
            reader = mmap.mmap(-1, 32, tagname=bve.MAP_NAME)
            try:
                for index, notch in enumerate(bve.NOTCH_ORDER):
                    pad.set(notch); pad.set_reverser('F'); pad.set_buttons(5)
                    pad.refresh(True)
                    seq, magic, tick, value, rev, buttons, enabled, end = bve.PACKET.unpack(reader[:])
                    self.assertEqual((magic, value, rev, buttons, enabled), (bve.MAGIC, index-9, 1, 5, 1))
                    self.assertEqual(seq, end); self.assertEqual(seq % 2, 0)
                    now = ctypes.windll.kernel32.GetTickCount() & 0xffffffff
                    self.assertLess((now-tick) & 0xffffffff, 500)
                pad.close()
                self.assertEqual(bve.PACKET.unpack(reader[:])[6], 0)
                pad.close()
            finally:
                reader.close(); pad.close()

    def test_invalid_values(self):
        pad = bve.BveBackend()
        for method, value in ((pad.set, 'P6'), (pad.set_reverser, 'X'), (pad.set_buttons, 16), (pad.set_buttons, True)):
            with self.assertRaises(ValueError): method(value)


if __name__ == '__main__': unittest.main()
