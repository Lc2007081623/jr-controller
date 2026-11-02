import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import output_profiles as profiles
from controller_app import App

class ProfileTests(unittest.TestCase):
    def test_setting_roundtrip_and_invalid_fallback(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(profiles,'settings_path',return_value=Path(folder)/'settings.json'):
            self.assertEqual(profiles.load_mode(),profiles.XBOX)
            profiles.save_mode(profiles.ZUIKI)
            self.assertEqual(profiles.load_mode(),profiles.ZUIKI)
            profiles.settings_path().write_text('{broken',encoding='utf-8')
            self.assertEqual(profiles.load_mode(),profiles.XBOX)
            with self.assertRaises(ValueError):profiles.save_mode('unknown')

    def test_only_selected_device_is_created(self):
        with patch.object(profiles,'Backend') as xbox,patch.object(profiles,'ZuikiBackend') as zuiki:
            self.assertIs(profiles.create_backend(profiles.ZUIKI),zuiki.return_value)
            xbox.assert_not_called()
            self.assertIs(profiles.create_backend(profiles.XBOX),xbox.return_value)

    def test_zuiki_retains_buttons_between_notches_and_releases_on_close(self):
        with patch.object(profiles,'ZuikiVirtual') as device:
            pad=profiles.ZuikiBackend();pad.connect()
            pad.set_buttons(15);pad.set('P5');pad.set_reverser('F')
            device.return_value.set.assert_called_with('P5',15,'N')
            pad.set_buttons(0);pad.set('N');pad.close()
            device.return_value.set.assert_called_with('N',0,'N')
            device.return_value.close.assert_called_once()
            pad.close()

    def test_switch_releases_old_device_before_new_profile(self):
        app=Mock();app.output_mode=profiles.XBOX;app.mode.get.return_value=profiles.ZUIKI
        actions=[]
        app.release.side_effect=lambda:actions.append('release')
        app.drop_pad.side_effect=lambda:actions.append('close')
        with patch('controller_app.save_mode') as save:
            App.change_mode(app)
            save.assert_called_once_with(profiles.ZUIKI)
        self.assertEqual(actions,['release','close'])
        self.assertEqual(app.output_mode,profiles.ZUIKI)
        self.assertEqual(app.pad_retry_at,0)

if __name__=='__main__':unittest.main()
