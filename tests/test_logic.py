import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from logic import Monitor

A = {'box': (0.05, 0.1, 0.4, 0.95), 'facing': True}
B = {'box': (0.65, 0.1, 0.85, 0.7), 'facing': False}


class MonitorTests(unittest.TestCase):
    def setup_owner(self):
        m = Monitor()
        m.update([A], 0)
        self.assertTrue(m.calibrate(1))
        return m

    def feed(self, m, observations, start, end):
        events = []
        for tick in range(start, end):
            tracks, new = m.update(observations, tick/10)
            events.extend(new)
        return events

    def test_single_owner_never_alerts(self):
        m = self.setup_owner()
        self.assertEqual(self.feed(m, [A], 1, 80), [])

    def test_needs_explicit_owner(self):
        m = Monitor()
        self.assertEqual(self.feed(m, [A, B], 0, 80), [])
        self.assertFalse(m.calibrate(999))

    def test_presence_confirmation_and_cooldown(self):
        m = self.setup_owner()
        self.assertEqual(self.feed(m, [A, B], 1, 8), [])
        events = self.feed(m, [A, B], 8, 35)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['message'], '检测到其他人员')

    def test_passing_person_without_face(self):
        m = self.setup_owner()
        events = []
        for tick in range(1, 20):
            x = .50 + tick*.008
            _, new = m.update([A, {'box': (x,.1,x+.15,.7), 'facing': False}], tick/10)
            events.extend(new)
        self.assertEqual(events[0]['message'], '身后有人活动')

    def test_dwell_escalates(self):
        m = self.setup_owner()
        events = self.feed(m, [A, B], 1, 60)
        self.assertEqual([e['message'] for e in events], ['检测到其他人员', '身后有人停留'])

    def test_facing_requires_continuous_confirmation(self):
        m = self.setup_owner()
        facing = {**B, 'facing': True}
        self.feed(m, [A, facing], 1, 17)
        self.feed(m, [A, B], 17, 20)
        self.assertNotIn('有人可能看向屏幕', [e['message'] for e in self.feed(m, [A, facing], 20, 39)])
        self.assertIn('有人可能看向屏幕', [e['message'] for e in self.feed(m, [A, facing], 39, 44)])

    def test_missing_frame_resets_facing_duration(self):
        m = self.setup_owner()
        facing = {**B, 'facing': True}
        self.feed(m, [A, facing], 1, 17)
        m.update([A], 1.7)
        events = self.feed(m, [A, facing], 18, 36)
        self.assertNotIn('有人可能看向屏幕', [e['message'] for e in events])

    def test_owner_lost_does_not_reassign_to_stranger(self):
        m = self.setup_owner()
        self.feed(m, [B], 1, 25)
        self.assertIsNone(m.owner)

    def test_sleep_gap_invalidates_calibration(self):
        m = self.setup_owner()
        tracks, events = m.update([A, B], 100)
        self.assertIsNone(m.owner)
        self.assertEqual(events, [])
        self.assertNotEqual(tracks[0].id, 1)

    def test_observation_order_does_not_change_owner(self):
        m = self.setup_owner()
        self.feed(m, [A, B], 1, 8)
        tracks, _ = m.update([B, A], .8)
        self.assertEqual(tracks[1].id, m.owner)


if __name__ == '__main__':
    unittest.main()
