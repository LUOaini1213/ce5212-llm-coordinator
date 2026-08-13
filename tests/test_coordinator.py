"""Tests hit shipped coordinator functions, not a reimplementation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coordinator.behavior import BehaviorModeler
from coordinator.grounding import ground_intent
from coordinator.parse import extract_json_text, parse_json
from coordinator.policy import PolicyOptimizer
from coordinator.rule_coord import RuleBasedCoordinator
from coordinator.schema import DIRECTION_TO_EDGE, sanitize_intent
from coordinator.snapshot import EdgeState, NetworkSnapshot
from scripts import mock_compare


def _snap(**kwargs) -> NetworkSnapshot:
    edges = kwargs.pop(
        "edges",
        [EdgeState("479165267", 0.4, 20.0, 0, 10)],
    )
    return NetworkSnapshot(
        sim_time=kwargs.get("sim_time", 60.0),
        edges=edges,
        av_waiting=kwargs.get("av_waiting", 0),
        avg_wait_s=kwargs.get("avg_wait_s", 10.0),
        incident=kwargs.get("incident"),
    )


class SanitizeTests(unittest.TestCase):
    def test_unknown_direction_becomes_none_and_zero_extend(self):
        out = sanitize_intent(
            {"congested_direction": "str", "extend_green_seconds": 20},
            sim_time=10.0,
            source="llm",
        )
        self.assertEqual(out["congested_direction"], "none")
        self.assertEqual(out["extend_green_seconds"], 0)

    def test_extend_clamped_and_none_forces_zero(self):
        hi = sanitize_intent(
            {"congested_direction": "exit_ramp", "extend_green_seconds": 99},
            0.0,
            "llm",
        )
        self.assertEqual(hi["extend_green_seconds"], 25)
        none = sanitize_intent(
            {"congested_direction": "none", "extend_green_seconds": 15},
            0.0,
            "llm",
        )
        self.assertEqual(none["extend_green_seconds"], 0)

    def test_non_dict_fallback(self):
        out = sanitize_intent(["not", "a", "dict"], 1.0, "llm")
        self.assertEqual(out["source"], "llm")
        self.assertEqual(out["congested_direction"], "none")


class ParseTests(unittest.TestCase):
    def test_extracts_object_from_fence_and_think(self):
        raw = '<think>nope</think>\n```json\n{"congested_direction":"exit_ramp"}\n```'
        self.assertEqual(extract_json_text(raw), '{"congested_direction":"exit_ramp"}')
        self.assertEqual(parse_json(raw, {})["congested_direction"], "exit_ramp")

    def test_bad_text_returns_fallback(self):
        self.assertEqual(parse_json("not json at all", {"ok": 1}), {"ok": 1})


class RuleCoordTests(unittest.TestCase):
    def test_high_occupancy_picks_worst_direction_and_scales_extend(self):
        snap = _snap(
            edges=[
                EdgeState("479165267", 0.85, 5.0, 2, 40),
                EdgeState("479165268", 0.40, 15.0, 0, 10),
            ],
            av_waiting=5,
            incident="stall",
        )
        intent = RuleBasedCoordinator().run(snap)
        self.assertEqual(intent["source"], "rule")
        self.assertEqual(intent["congested_direction"], "east_to_cbd")
        expected = int(10 + (0.85 - 0.7) / 0.3 * 15)
        self.assertEqual(intent["extend_green_seconds"], expected)
        self.assertTrue(intent["dispatch_av"])
        self.assertTrue(intent["alert_passengers"])

    def test_below_threshold_is_idle(self):
        intent = RuleBasedCoordinator().run(_snap())
        self.assertEqual(intent["congested_direction"], "none")
        self.assertEqual(intent["extend_green_seconds"], 0)
        self.assertFalse(intent["dispatch_av"])


class GroundingTests(unittest.TestCase):
    def test_known_direction_maps_to_example_edge(self):
        rec = ground_intent(
            {"congested_direction": "exit_ramp", "extend_green_seconds": 12, "source": "rule"}
        )
        self.assertTrue(rec["signal_extended"])
        self.assertEqual(rec["edge_id"], DIRECTION_TO_EDGE["exit_ramp"])
        self.assertEqual(rec["extend_applied"], 12)
        self.assertIsNone(rec["skipped_reason"])

    def test_unknown_direction_does_not_invent_an_edge(self):
        rec = ground_intent({"congested_direction": "hallucinated_id", "extend_green_seconds": 20})
        self.assertFalse(rec["signal_extended"])
        self.assertIsNone(rec["edge_id"])
        self.assertEqual(rec["skipped_reason"], "unknown_direction")
        self.assertEqual(rec["extend_applied"], 0)

    def test_custom_mapping_override(self):
        rec = ground_intent(
            {"congested_direction": "exit_ramp", "extend_green_seconds": 8},
            mapping={"exit_ramp": "EDGE_A"},
        )
        self.assertEqual(rec["edge_id"], "EDGE_A")


class PolicyTests(unittest.TestCase):
    def test_propose_next_steps_fleet_from_best_history(self):
        opt = PolicyOptimizer(max_iterations=4)
        opt.ingest_result(opt.fallback_scenarios(1)[0], 50.0, 40.0, 5.0)
        nxt = opt.propose_next()
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt["av_fleet_size"], 4)
        self.assertEqual(nxt["av_frequency_min"], 13)
        rec = opt.final_recommendation()
        self.assertEqual(rec["baseline_travel_min"], 50.0)

    def test_propose_next_empty_history(self):
        self.assertIsNone(PolicyOptimizer().propose_next())


class BehaviorTests(unittest.TestCase):
    def test_uninformed_only_sees_bus_schedule(self):
        rng = __import__("random").Random(0)
        model = BehaviorModeler(rng=rng)
        persona = model.sample_persona("a1")
        persona.agent_type = "uninformed"
        info = model.build_local_info(persona, _snap(avg_wait_s=90, av_waiting=4))
        self.assertEqual(set(info), {"bus_schedule"})
        self.assertNotIn("av_availability", info)

    def test_aggregate_uses_recorded_modes(self):
        model = BehaviorModeler()
        model.record_decision({"chosen_mode": "AV_shuttle", "would_change_if_informed": False})
        model.record_decision({"chosen_mode": "not_a_mode", "would_change_if_informed": True})
        share = model.aggregate_mode_share()
        self.assertEqual(share["total_trips"], 2)
        self.assertEqual(share["av_adoption_pct"], 50.0)
        self.assertIn("conventional_bus", share["mode_share_pct"])


class SanitizeRepoTests(unittest.TestCase):
    FORBIDDEN = (
        "A033" + "1290N",
        "C:/" + "Users/LW",
        "C:\\" + "Users\\LW",
        "183-" + "1949-6086",
        "29795" + "70847",
    )

    def test_public_tree_has_no_student_id_or_home_path(self):
        hits = []
        for path in ROOT.rglob("*"):
            if path.suffix.lower() not in {".py", ".md", ".txt"}:
                continue
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for token in self.FORBIDDEN:
                if token in text:
                    hits.append(f"{path.relative_to(ROOT)}:{token}")
        self.assertEqual(hits, [])


class MockCompareScriptTests(unittest.TestCase):
    def test_script_writes_peak_apply_and_offpeak_skip(self):
        path = mock_compare.main()
        self.assertTrue(path.is_file())
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 3)
        peak = rows[1]
        self.assertEqual(peak["t"], 1350.0)
        self.assertEqual(peak["intent"]["congested_direction"], "east_to_cbd")
        self.assertEqual(peak["applied"]["edge_id"], DIRECTION_TO_EDGE["east_to_cbd"])
        self.assertTrue(peak["applied"]["signal_extended"])
        idle = rows[0]
        self.assertEqual(idle["applied"]["skipped_reason"], "no_direction")
        self.assertFalse(idle["applied"]["signal_extended"])


if __name__ == "__main__":
    unittest.main()
