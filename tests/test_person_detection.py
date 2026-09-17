import unittest

import numpy as np

from core.logic import Monitor
from core.person_detection import PersonDetector, PersonTracker


class PersonDetectionTests(unittest.TestCase):
    def test_coordinates_restore_after_letterbox(self):
        from types import SimpleNamespace
        detector = PersonDetector.__new__(PersonDetector)
        detector.model = SimpleNamespace(infer=lambda image: np.array([
            [160, 80, 160, 160, .8, 0], [0, 0, 20, 20, .9, 2]]))
        result = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
        self.assertEqual(len(result), 1)
        np.testing.assert_allclose(result[0]['box'], (.25, 1/6, .5, .5))

    def test_bytetrack_keeps_id_through_low_scores_and_misses(self):
        tracker = PersonTracker()
        original = None
        for tick in range(20):
            x = .5+tick*.002
            observations = [] if tick in (6, 7) else [{'box': (x, .2, x+.06, .4),
                                                       'confidence': .2 if 3 <= tick <= 5 else .8}]
            tracked = tracker.update(observations)
            if tick in (6, 7):
                self.assertEqual(tracked, [])
            else:
                self.assertEqual(len(tracked), 1)
                original = original or tracked[0]['tracker_id']
                self.assertEqual(tracked[0]['tracker_id'], original)
        self.assertEqual(PersonTracker().update([{'box': (.5, .2, .6, .4), 'confidence': .2}]), [])

    def test_distant_walker_at_two_fps_alerts_with_bytetrack(self):
        tracker, monitor = PersonTracker(), Monitor()
        events = []
        for tick in range(12):
            x = .6+tick*.012
            observations = [{'box': (.05, .3, .4, .95), 'confidence': .9},
                            {'box': (x, .15, x+.05, .3), 'confidence': .8}]
            tracks, new = monitor.update(tracker.update(observations), tick*.5)
            if tick == 0:
                monitor.calibrate(tracks[0].id)
            events.extend(new)
        self.assertEqual(len(events), 1)

    def test_stationary_background_jitter_stays_quiet(self):
        tracker, monitor = PersonTracker(), Monitor()
        for tick in range(30):
            x = .6 + (.001 if tick % 2 else -.001)
            tracks, events = monitor.update(tracker.update([
                {'box': (.05, .3, .4, .95), 'confidence': .9},
                {'box': (x, .15, x+.05, .3), 'confidence': .8}]), tick*.25)
            if tick == 0:
                monitor.calibrate(tracks[0].id)
            self.assertEqual(events, [])
            self.assertFalse(tracks[1].moving)
