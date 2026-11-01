"""Untrusted JSON field types must not turn refused flags into actions."""
import json
from pathlib import Path
import unittest

from coordinator.grounding import ground_intent
from coordinator.parse import parse_json
from coordinator.schema import sanitize_intent
from scripts.mock_compare import run_ticks

ROOT = Path(__file__).resolve().parents[1]


class IntentTypeTests(unittest.TestCase):
    def flow(self, **changes):
        raw = {"congested_direction": "east_to_cbd", "extend_green_seconds": 5,
               "dispatch_av": False, "alert_passengers": False, **changes}
        intent = sanitize_intent(raw, 1350, "offline-fixture")
        return intent, ground_intent(intent)

    def test_string_false_does_not_dispatch_or_alert_through_real_json_flow(self):
        raw = parse_json('{"congested_direction":"east_to_cbd","extend_green_seconds":5,'
                         '"dispatch_av":"false","alert_passengers":"false"}', {})
        intent = sanitize_intent(raw, 1350, "offline-fixture")
        result = ground_intent(intent)
        self.assertFalse(intent["dispatch_av"])
        self.assertFalse(intent["alert_passengers"])
        self.assertFalse(result["dispatch_av"])
        self.assertFalse(result["alert_issued"])
        self.assertTrue(result["signal_extended"])

    def test_native_and_explicit_boolean_text_semantics(self):
        for value, expected in [(True, True), (False, False), ("true", True), (" TRUE ", True),
                                ("false", False), (" False ", False)]:
            with self.subTest(value=value):
                intent, result = self.flow(dispatch_av=value, alert_passengers=value)
                self.assertEqual(intent["dispatch_av"], expected)
                self.assertEqual(result["dispatch_av"], expected)
                self.assertEqual(result["alert_issued"], expected)

    def test_malformed_flag_types_fail_closed(self):
        for value in ["yes", "0", "1", "unknown", "", 1, 0, -1, [], [False], {}, {"false": False}, None]:
            with self.subTest(value=value):
                intent, result = self.flow(dispatch_av=value, alert_passengers=value)
                self.assertFalse(intent["dispatch_av"])
                self.assertFalse(result["dispatch_av"])
                self.assertFalse(result["alert_issued"])

    def test_nonfinite_and_invalid_seconds_fail_closed_without_overflow(self):
        for value in [float("inf"), float("-inf"), float("nan"), "Infinity", "NaN", "1e400",
                      True, False, None, [], {}, "2.5"]:
            with self.subTest(value=value):
                intent, result = self.flow(extend_green_seconds=value)
                self.assertEqual(intent["extend_green_seconds"], 0)
                self.assertFalse(result["signal_extended"])
                self.assertEqual(result["extend_applied"], 0)
                self.assertEqual(result["skipped_reason"], "zero_extend")

    def test_nonstandard_json_infinite_number_cannot_crash_the_apply_flow(self):
        # Python's permissive JSON loader can produce a float infinity from 1e400.
        raw = parse_json('{"congested_direction":"east_to_cbd","extend_green_seconds":1e400}', {})
        result = ground_intent(sanitize_intent(raw, 1350, "offline-fixture"))
        self.assertEqual(result["extend_applied"], 0)

    def test_existing_numeric_coercion_and_clamp_are_preserved(self):
        for value, expected in [(5, 5), (5.9, 5), (" 5 ", 5), ("+5", 5), (99, 25), (-5, 0),
                                (10 ** 400, 25), (1e308, 25)]:
            with self.subTest(value=value):
                intent, result = self.flow(extend_green_seconds=value)
                self.assertEqual(intent["extend_green_seconds"], expected)
                self.assertEqual(result["extend_applied"], expected)

    def test_direct_grounding_reuses_typed_bounds_and_flags(self):
        result = ground_intent({"congested_direction": "east_to_cbd", "extend_green_seconds": 999,
                                "dispatch_av": "false", "alert_passengers": "false"})
        self.assertEqual(result["extend_applied"], 25)
        self.assertFalse(result["dispatch_av"])
        self.assertFalse(result["alert_issued"])
        result = ground_intent({"congested_direction": [], "extend_green_seconds": float("inf")})
        self.assertEqual(result["skipped_reason"], "unknown_direction")
        self.assertFalse(result["signal_extended"])

    def test_no_direction_and_other_independent_actions_keep_existing_semantics(self):
        intent, result = self.flow(congested_direction="none", dispatch_av=True, alert_passengers=True)
        self.assertEqual(intent["extend_green_seconds"], 0)
        self.assertEqual(result["skipped_reason"], "no_direction")
        self.assertTrue(result["dispatch_av"])
        self.assertTrue(result["alert_issued"])

    def test_committed_three_tick_example_unchanged(self):
        expected = json.loads((ROOT / "examples/mock_compare.json").read_text(encoding="utf-8"))
        self.assertEqual(run_ticks(), expected)


if __name__ == "__main__":
    unittest.main()
