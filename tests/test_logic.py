import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.logic import Monitor

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

    def test_fixed_coworker_does_not_alert(self):
        m = self.setup_owner()
        self.assertEqual(self.feed(m, [A, B], 1, 80), [])

    def test_walking_person_without_face_alerts(self):
        m = self.setup_owner()
        events = []
        for tick in range(1, 20):
            x = .50 + tick*.006
            _, new = m.update([A, {'box': (x,.1,x+.15,.7), 'facing': False}], tick/10)
            events.extend(new)
        self.assertEqual([e['message'] for e in events], ['检测到人员走动'])

    def test_selected_coworker_is_ignored_until_unmarked(self):
        m = self.setup_owner()
        m.update([A, B], .1)
        self.assertTrue(m.toggle_ignore(2))
        events = []
        for tick in range(2, 22):
            x = .65 - tick*.006
            tracks, new = m.update([A, {'box': (x,.1,x+.2,.7)}], tick/10)
            events.extend(new)
        self.assertEqual(events, [])
        self.assertTrue(tracks[1].ignored)
        self.assertTrue(m.toggle_ignore(2))
        events = []
        for tick in range(22, 42):
            x = .55 - (tick-22)*.008
            _, new = m.update([A, {'box': (x,.1,x+.2,.7)}], tick/10)
            events.extend(new)
        self.assertEqual([e['message'] for e in events], ['检测到人员走动'])

    def test_facing_and_small_jitter_do_not_alert(self):
        m = self.setup_owner()
        events = []
        for tick in range(1, 40):
            x = .65 + (.005 if tick % 2 else 0)
            _, new = m.update([A, {'box': (x,.1,x+.2,.7), 'facing': True}], tick/10)
            events.extend(new)
        self.assertEqual(events, [])

    def test_missing_frame_resets_motion_history(self):
        m = self.setup_owner()
        m.update([A, B], .1)
        m.update([A], 1.7)
        tracks, events = m.update([A, {'box': (.55,.1,.75,.7)}], 1.8)
        self.assertEqual(events, [])
        self.assertFalse(tracks[1].moving)

    def test_single_box_jump_does_not_trigger_movement_or_alert(self):
        m = self.setup_owner()
        for tick in range(1, 50):
            x = .55 if tick < 20 else .65
            tracks, events = m.update([A, {'box': (x, .1, x+.2, .7)}], tick/10)
            self.assertFalse(tracks[1].moving)
            self.assertEqual(events, [])

    def test_seated_sway_does_not_trigger_movement(self):
        import math
        m = self.setup_owner()
        for tick in range(1, 100):
            x = .65 + .035*math.sin(tick*.3)
            tracks, events = m.update([A, {'box': (x, .1, x+.2, .7)}], tick/10)
            self.assertFalse(tracks[1].moving)
            self.assertEqual(events, [])

    def test_body_resize_with_fixed_face_does_not_trigger_movement(self):
        m = self.setup_owner()
        face = (.7, .15, .78, .25)
        for tick in range(1, 60):
            bottom = .45 + .004*tick
            tracks, events = m.update([A, {'box': (.65, .1, .85, bottom), 'face_box': face}], tick/10)
            self.assertEqual(tracks[1].id, 2)
            self.assertFalse(tracks[1].moving)
            self.assertEqual(events, [])

    def test_ignore_survives_face_body_switches(self):
        m = self.setup_owner()
        face = (.7, .15, .78, .25)
        m.update([A, {**B, 'face_box': face, 'appearance': (1., 0.)}], .1)
        m.toggle_ignore(2)
        for tick in range(2, 50):
            observation = {'box': face, 'face_box': face} if tick % 2 else {
                **B, 'face_box': face, 'appearance': (1., 0.)}
            tracks, events = m.update([A, observation], tick/10)
            self.assertEqual(tracks[1].id, 2)
            self.assertTrue(tracks[1].ignored)
            self.assertFalse(tracks[1].moving)
            self.assertEqual(events, [])

    def test_face_matching_does_not_override_changed_appearance(self):
        m = self.setup_owner()
        face = (.7, .15, .78, .25)
        m.update([A, {**B, 'face_box': face, 'appearance': (1., 0.)}], .1)
        m.toggle_ignore(2)
        tracks, _ = m.update([A, {**B, 'face_box': face, 'appearance': (0., 1.)}], .2)
        self.assertFalse(tracks[1].ignored)

    def test_face_walking_still_alerts_and_stopping_clears_motion(self):
        m = self.setup_owner()
        alerts = []
        for tick in range(1, 50):
            x = .5 + min(tick, 25)*.008
            tracks, events = m.update([A, {'box': (x, .1, x+.15, .7),
                                          'face_box': (x+.03, .12, x+.10, .22)}], tick/10)
            alerts.extend(events)
        self.assertEqual(len(alerts), 1)
        self.assertFalse(tracks[1].moving)

    def test_ignore_expires_after_tracking_gap(self):
        m = self.setup_owner()
        m.update([A, B], .1)
        self.assertTrue(m.toggle_ignore(2))
        m.update([A], .2)
        tracks, _ = m.update([A, B], .7)
        self.assertFalse(tracks[1].ignored)

    def test_ignored_coworker_rejoins_after_brief_detection_loss(self):
        m = self.setup_owner()
        coworker = {**B, 'appearance': (1.0, 0.0)}
        m.update([A, coworker], .1)
        self.assertTrue(m.toggle_ignore(2))
        for tick in range(2, 16):
            m.update([A], tick/10)
        # The changed box has low IoU, but remains in the same place with matching appearance.
        changed = {'box': (.69, .32, .81, .52), 'appearance': (1.0, 0.0)}
        tracks, _ = m.update([A, changed], 1.6)
        self.assertEqual(tracks[1].id, 2)
        self.assertTrue(tracks[1].ignored)

    def test_new_person_in_same_seat_does_not_inherit_ignore(self):
        m = self.setup_owner()
        m.update([A, {**B, 'appearance': (1.0, 0.0)}], .1)
        self.assertTrue(m.toggle_ignore(2))
        m.update([A], .2)
        tracks, _ = m.update([A, {**B, 'appearance': (0.0, 1.0)}], .3)
        self.assertNotEqual(tracks[1].id, 2)
        self.assertFalse(tracks[1].ignored)

    def test_temporary_duplicate_id_returns_to_ignored_track(self):
        m = self.setup_owner()
        m.update([A, {**B, 'appearance': (1.0, 0.0)}], .1)
        self.assertTrue(m.toggle_ignore(2))
        tracks, _ = m.update([A, {**B, 'appearance': (0.0, 1.0)}], .2)
        self.assertNotEqual(tracks[1].id, 2)
        tracks, _ = m.update([A, {**B, 'appearance': (1.0, 0.0)}], .3)
        self.assertEqual(tracks[1].id, 2)
        self.assertTrue(tracks[1].ignored)

    def test_owner_lost_does_not_reassign_to_stranger(self):
        m = self.setup_owner()
        self.feed(m, [B], 1, 35)
        self.assertIsNone(m.owner)

    def test_slow_inference_does_not_clear_selected_tracks(self):
        m = Monitor()
        owner = {**A, 'appearance': (1., 0.)}
        coworker = {**B, 'appearance': (0., 1.)}
        m.update([owner, coworker], 0)
        m.calibrate(1)
        m.toggle_ignore(2)
        for at in (1.2, 2.4, 3.6):
            tracks, _ = m.update([owner, coworker], at)
            self.assertEqual(m.owner, tracks[0].id)
            self.assertTrue(tracks[1].ignored)

    def test_selections_recover_after_ids_expire(self):
        m = Monitor()
        first, second = [1.] + [0.]*127, [0., 1.] + [0.]*126
        owner, coworker = {**A, 'feature': first}, {**B, 'feature': second}
        m.update([owner, coworker], 0)
        m.calibrate(1)
        m.toggle_ignore(2)
        for tick in range(1, 41):
            m.update([], tick/10)
        self.assertIsNone(m.owner)
        for tick in range(41, 44):
            tracks, _ = m.update([owner, coworker], tick/10)
        self.assertNotEqual(tracks[0].id, 1)
        self.assertEqual(m.owner, tracks[0].id)
        self.assertTrue(tracks[1].ignored)
        # 取消恢复后的标记必须同时删除会话选择，否则下一帧会自动忽略回来。
        m.toggle_ignore(tracks[1].id)
        for tick in range(44, 49):
            tracks, _ = m.update([owner, coworker], tick/10)
            self.assertFalse(tracks[1].ignored)

    def test_camera_reset_requires_face_confirmation_to_restore(self):
        m = Monitor()
        owner = {**A, 'feature': [1.] + [0.]*127}
        m.update([owner], 0)
        m.calibrate(1)
        m.reset_tracking()
        self.assertIsNone(m.owner)
        m.update([owner], 1)
        self.assertIsNone(m.owner)
        m.update([owner], 1.1)
        self.assertIsNone(m.owner)
        tracks, _ = m.update([owner], 1.2)
        self.assertEqual(m.owner, tracks[0].id)

    def test_stranger_in_same_box_does_not_inherit_selected_owner(self):
        m = Monitor()
        m.update([{**A, 'feature': [1.] + [0.]*127}], 0)
        m.calibrate(1)
        for tick in range(1, 6):
            m.update([{**A, 'feature': [0., 1.] + [0.]*126}], tick/10)
            self.assertIsNone(m.owner)

    def test_two_matching_faces_do_not_restore_selection(self):
        m = Monitor()
        feature = [1.] + [0.]*127
        m.update([{**A, 'feature': feature}], 0)
        m.calibrate(1)
        m.reset_tracking()
        for tick in range(1, 6):
            m.update([{**A, 'feature': feature}, {**B, 'feature': feature}], tick/10)
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
