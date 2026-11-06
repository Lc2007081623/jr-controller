import unittest
from unittest.mock import Mock

from train_crew_output import NOTCHES, TrainCrewBackend
import output_profiles as profiles


class TrainCrewTests(unittest.TestCase):
    def test_game_notches_and_service_brake_limit(self):
        self.assertEqual([NOTCHES[f'P{i}'] for i in range(1, 6)], [1, 2, 3, 4, 5])
        self.assertEqual([NOTCHES[f'B{i}'] for i in range(1, 9)], [-2, -3, -4, -5, -6, -7, -7, -7])
        self.assertEqual(NOTCHES['EB'], -8)
        self.assertEqual(NOTCHES['N'], 0)

    def test_refresh_preserves_absolute_inputs_and_disarmed_report_is_emergency(self):
        b = TrainCrewBackend(); b.process = Mock(); b.process.poll.return_value = None
        b.set('P3'); b.set_reverser('R'); b.set_buttons(5)
        b.refresh(True)
        b.process.stdin.write.assert_called_with('3 -1 5\n')
        b.refresh(False)
        b.process.stdin.write.assert_called_with('-8 0 0\n')
        b.refresh(True)
        b.process.stdin.write.assert_called_with('3 -1 5\n')

    def test_invalid_inputs_and_dead_helper(self):
        b = TrainCrewBackend()
        for fn, value in ((b.set, 'P6'), (b.set_reverser, 'X'), (b.set_buttons, 16), (b.set_buttons, True)):
            with self.assertRaises(ValueError): fn(value)
        with self.assertRaises(RuntimeError): b.refresh(True)
        b.process = Mock(); b.process.poll.return_value = 1
        with self.assertRaises(RuntimeError): b.refresh(True)

    def test_close_releases_buttons_and_direction_and_is_idempotent(self):
        b = TrainCrewBackend(); b.process = p = Mock(); p.poll.return_value = None
        b.close(); b.close()
        p.stdin.write.assert_called_once_with('-8 0 0\nQUIT\n')
        p.wait.assert_called_once_with(timeout=3)
        p.stdin.close.assert_called_once(); p.stdout.close.assert_called_once()

    def test_profile_selects_official_sdk(self):
        self.assertIsInstance(profiles.create_backend(profiles.TRAIN_CREW), TrainCrewBackend)


if __name__ == '__main__': unittest.main()
