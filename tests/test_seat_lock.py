"""Lock timing and cancellation without touching the real Windows desktop."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.seat_lock import LockDecision


class LockDecisionTests(unittest.TestCase):
    def test_absence_input_and_warning_must_all_hold(self):
        decision = LockDecision()
        self.assertIsNone(decision.update(0, False, 0, 0, True))
        self.assertIsNone(decision.update(59, False, 59, 0, True))
        self.assertEqual(decision.update(60, False, 60, 0, True), 5)
        self.assertEqual(decision.update(64, False, 64, 0, True), 1)
        self.assertIsNone(decision.update(64.5, True, 64.5, 0, True))
        self.assertIsNone(decision.update(124, False, 60, 0, True))
        self.assertEqual(decision.update(184, False, 60, 0, True), 5)
        self.assertEqual(decision.update(189, False, 65, 0, True), 0)

    def test_unknown_capture_or_input_cancels_warning(self):
        decision = LockDecision()
        decision.update(0, False, 100, 0, True)
        self.assertEqual(decision.update(60, False, 100, 0, True), 5)
        self.assertIsNone(decision.update(62, None, 100, 0, False))
        self.assertIsNone(decision.update(63, False, None, 0, True))
        self.assertIsNone(decision.update(64, False, 100, 0, True))
        self.assertEqual(decision.update(124, False, 100, 0, True), 5)


if __name__ == '__main__':
    unittest.main()
