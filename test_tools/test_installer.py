import unittest
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import setup_app

class InstallerTests(unittest.TestCase):
    def test_driver_exit_codes(self):
        self.assertFalse(setup_app.driver_result(0))
        self.assertTrue(setup_app.driver_result(3010))
        self.assertTrue(setup_app.driver_result(1641))
        for code in (1,1603,1618,-1):
            with self.assertRaises(RuntimeError):setup_app.driver_result(code)
    def test_install_and_shortcuts_have_fixed_locations(self):
        with patch.dict('os.environ',{'ProgramW6432':r'C:\Program Files','PUBLIC':r'C:\Users\Public','ProgramData':r'C:\ProgramData'}):
            self.assertEqual(setup_app.install_directory(),Path(r'C:\Program Files')/'JR Controller')
            self.assertTrue(all(p.name=='JR Controller.lnk' for p in setup_app.shortcut_paths()))
    def test_uninstall_refuses_execution_outside_install_root(self):
        with patch.object(setup_app,'is_running',return_value=False),patch.object(setup_app.sys,'executable',r'C:\Elsewhere\Uninstall.exe'):
            with self.assertRaisesRegex(RuntimeError,'位置不正确'):setup_app.uninstall()

if __name__=='__main__':unittest.main()
