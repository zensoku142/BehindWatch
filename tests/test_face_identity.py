import sys
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.face_identity import FaceAlerts, best_match, delete_template, load_template, save_template
from core.vision import Detector


class FaceIdentityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI test')
    def test_template_roundtrip_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'owner.json'
            feature = np.zeros(128, dtype=np.float32)
            feature[0] = 1
            save_template([feature] * 5, path)
            np.testing.assert_allclose(load_template(path), feature)
            delete_template(path)
            self.assertIsNone(load_template(path))

    def test_requires_clear_unique_match(self):
        owner = np.zeros(128, dtype=np.float32)
        owner[0] = 1
        other = np.zeros(128, dtype=np.float32)
        other[1] = 1
        self.assertEqual(best_match(owner, {3: owner, 4: other}), 3)
        self.assertIsNone(best_match(owner, {4: other}))
        self.assertIsNone(best_match(owner, {3: owner, 4: owner}))

    def test_invalid_template_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'owner.json'
            path.write_bytes(b'invalid protected data')
            self.assertIsNone(load_template(path))

    def test_two_faces_inside_one_body_remain_separate(self):
        detector = Detector.__new__(Detector)
        detector.identify = True
        detector.timestamp = 0
        detector.mp = SimpleNamespace(ImageFormat=SimpleNamespace(SRGB=1), Image=lambda **kwargs: None)
        detector.recognizer = SimpleNamespace(
            alignCrop=lambda frame, row: row,
            feature=lambda row: np.eye(128, dtype=np.float32)[0 if row[0, 0] < 250 else 1][None])
        detector.people = SimpleNamespace(detect=lambda frame: [{'box': (0., 0., 1., 1.), 'facing': False}])
        def face(x):
            points = [SimpleNamespace(x=x, y=.3) for _ in range(292)]
            points[0] = SimpleNamespace(x=x-.08, y=.2)
            points[2] = SimpleNamespace(x=x+.08, y=.5)
            return points
        detector.faces = SimpleNamespace(detect_for_video=lambda *args: SimpleNamespace(
            face_landmarks=[face(.3), face(.7)], facial_transformation_matrixes=[np.eye(4), np.eye(4)]))
        observations = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertEqual(len(observations), 2)
        self.assertTrue(all(observation['face'] for observation in observations))
        self.assertEqual(len(observations[0]['appearance']), 72)
        self.assertAlmostEqual(sum(observations[0]['appearance']), 1.0)
        self.assertTrue(all('feature' in observation for observation in observations))
        self.assertNotEqual(int(np.argmax(observations[0]['feature'])), int(np.argmax(observations[1]['feature'])))

    def test_unregistered_requires_two_faces_and_ignores_body_tracks(self):
        alerts = FaceAlerts()
        self.assertIsNone(alerts.update(False, set(), None, 0))
        self.assertIsNone(alerts.update(False, {1}, None, .1))
        self.assertIsNone(alerts.update(False, {1, 2}, None, .2))
        self.assertEqual(alerts.update(False, {1, 2}, None, .3)['message'], '检测到两张及以上人脸')
        self.assertIsNone(alerts.update(False, {1, 2}, None, .4))
        self.assertIsNone(alerts.update(False, {1}, None, .5))

    def test_registered_alerts_on_one_other_face_only(self):
        alerts = FaceAlerts()
        self.assertIsNone(alerts.update(True, {1}, 1, 0))
        self.assertIsNone(alerts.update(True, {1, 2}, 1, .1))
        self.assertEqual(alerts.update(True, {1, 2}, 1, .2)['message'], '检测到未注册人脸')
        self.assertIsNone(alerts.update(True, set(), None, .3))
        self.assertIsNone(alerts.update(True, {3}, None, 11))
        self.assertEqual(alerts.update(True, {3}, None, 11.1)['id'], 3)

    def test_switching_registration_mode_resets_confirmation(self):
        alerts = FaceAlerts()
        self.assertIsNone(alerts.update(False, {1, 2}, None, 0))
        self.assertIsNone(alerts.update(True, {1, 2}, 1, .1))
        self.assertEqual(alerts.update(True, {1, 2}, 1, .2)['message'], '检测到未注册人脸')
        self.assertIsNone(alerts.update(False, {1}, None, .3))
