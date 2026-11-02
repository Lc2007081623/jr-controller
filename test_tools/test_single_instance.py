import ctypes
import unittest
from unittest.mock import Mock,patch
import controller_app

class InstanceTests(unittest.TestCase):
    def run_main(self,handle,error,window=123):
        kernel,user=Mock(),Mock()
        def create(*args):
            ctypes.set_last_error(error);return handle
        kernel.CreateMutexExW.side_effect=create;user.FindWindowW.return_value=window
        with patch.object(controller_app.ctypes,'WinDLL',side_effect=lambda name,**kw:kernel if name=='kernel32' else user),patch.object(controller_app.tk,'Tk') as root,patch.object(controller_app,'App') as app:
            controller_app.main()
        return kernel,user,root,app
    def test_existing_instance_requests_only_synchronize_and_restores_window(self):
        k,u,root,app=self.run_main(17,183)
        k.CreateMutexExW.assert_called_once_with(None,'Local\\JRController',0,0x100000)
        u.ShowWindow.assert_called_once_with(123,9);k.CloseHandle.assert_called_once_with(17)
        root.assert_not_called();app.assert_not_called()
    def test_denied_instance_does_not_crash_or_start_second_gamepad(self):
        k,u,root,app=self.run_main(None,5)
        u.ShowWindow.assert_called_once_with(123,9)
        k.CloseHandle.assert_not_called();root.assert_not_called();app.assert_not_called()
    def test_denied_without_window_shows_recovery_message(self):
        _,u,root,_=self.run_main(None,5,window=0)
        u.MessageBoxW.assert_called_once();root.assert_not_called()
    def test_first_instance_runs_and_releases_handle(self):
        k,_,root,app=self.run_main(17,0)
        app.assert_called_once_with(root.return_value)
        root.return_value.mainloop.assert_called_once();k.CloseHandle.assert_called_once_with(17)

if __name__=='__main__':unittest.main()
