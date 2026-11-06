import unittest
from unittest.mock import patch,Mock
from contextlib import ExitStack
import tempfile
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'installer'))
import setup_app

class InstallerTests(unittest.TestCase):
    def test_bve_plugins_copy_selected_architecture_and_allow_blank(self):
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'app';game=Path(temp)/'game';game.mkdir()
            (game/'BveTs.exe').touch();(game/'Mackoy.IInputDevice.dll').touch()
            source=target/'BVE Plugins/BVE5/JRController.Bve.dll'
            source.parent.mkdir(parents=True);source.write_bytes(b'x86-plugin')
            setup_app.install_bve_plugins(target,[('BVE5',str(game)),('BVE6','')])
            self.assertEqual((game/'Input Devices/JRController.Bve.dll').read_bytes(),b'x86-plugin')
            with self.assertRaisesRegex(RuntimeError,'游戏目录'):
                setup_app.install_bve_plugins(target,[('BVE6',str(target))])
            with patch.object(setup_app.shutil,'copy2',side_effect=PermissionError()):
                with self.assertRaisesRegex(RuntimeError,'退出 BVE'):
                    setup_app.install_bve_plugins(target,[('BVE5',str(game))])

    def installation_case(self,existing,reboot=False,checks=(True,)):
        progress=Mock()
        with tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
            for name,value in [('check_system',None),('is_running',False),('driver_installed',existing),
                               ('run_driver',reboot),('install_directory',Path(temp)),('shortcut',None)]:
                stack.enter_context(patch.object(setup_app,name,return_value=value))
            run=setup_app.run_driver
            verify=stack.enter_context(patch.object(setup_app,'verify_app',side_effect=checks))
            stack.enter_context(patch.object(setup_app.shutil,'copytree'))
            stack.enter_context(patch.object(setup_app.shutil,'copy2'))
            stack.enter_context(patch.object(setup_app.winreg,'CreateKeyEx'))
            stack.enter_context(patch.object(setup_app.winreg,'SetValueEx'))
            result=setup_app.install(Path(temp)/'payload',True,progress)
        return result,run,verify,progress

    def test_clean_install_driver_then_checks_without_hardware(self):
        result,run,verify,progress=self.installation_case(False)
        self.assertFalse(result);run.assert_called_once();verify.assert_called_once()
        self.assertEqual([c.args[0] for c in progress.call_args_list],[1,2,3,4])

    def test_restart_required_does_not_claim_check_passed(self):
        result,run,verify,progress=self.installation_case(False,reboot=True)
        self.assertTrue(result);verify.assert_not_called()
        self.assertIn('重启',progress.call_args.args[1])

    def test_existing_broken_driver_is_repaired_then_checked(self):
        result,run,verify,_=self.installation_case(True,checks=(False,True))
        self.assertFalse(result);self.assertTrue(run.call_args.kwargs['repair'])
        self.assertEqual(verify.call_count,2)

    def test_supported_windows_only(self):
        with patch.object(setup_app.sys,'platform','win32'),patch.object(setup_app.sys,'getwindowsversion',return_value=Mock(major=10)):
            with patch.dict('os.environ',{'PROCESSOR_ARCHITECTURE':'AMD64','PROCESSOR_ARCHITEW6432':''}):setup_app.check_system()
            with patch.dict('os.environ',{'PROCESSOR_ARCHITECTURE':'ARM64','PROCESSOR_ARCHITEW6432':''}):
                with self.assertRaises(RuntimeError):setup_app.check_system()

    def test_install_check_requires_success_report_and_exit_code(self):
        def run(args,**kw):
            Path(args[2]).write_text(json.dumps({'ok':True}),encoding='utf-8')
            return Mock(returncode=0)
        with patch.object(setup_app.subprocess,'run',side_effect=run):
            self.assertTrue(setup_app.verify_app(Path('C:/example')))
        def failed(args,**kw):
            Path(args[2]).write_text(json.dumps({'ok':False}),encoding='utf-8')
            return Mock(returncode=1)
        with patch.object(setup_app.subprocess,'run',side_effect=failed):
            self.assertFalse(setup_app.verify_app(Path('C:/example')))

    def test_failed_check_without_report_is_actionable(self):
        with patch.object(setup_app.subprocess,'run',return_value=Mock(returncode=1)),self.assertLogs(level='ERROR'):
            with self.assertRaisesRegex(RuntimeError,'自检未完成'):setup_app.verify_app(Path('C:/example'))

    def test_repair_uses_offline_bundle_and_never_restarts_automatically(self):
        with patch.object(setup_app.subprocess,'run',return_value=Mock(returncode=3010)) as run:
            self.assertTrue(setup_app.run_driver(Path('C:/payload'),repair=True))
            args=run.call_args.args[0]
            self.assertIn('/exenoui',args);self.assertIn('/fomus',args);self.assertIn('//',args)
            self.assertIn('/qn',args);self.assertIn('/norestart',args)
            self.assertNotIn('/repair',args);self.assertNotIn('/install',args)

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
