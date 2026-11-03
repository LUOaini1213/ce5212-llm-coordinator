"""Tests hit shipped coordinator functions, not a reimplementation."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coordinator.approval import parse_approvals
from coordinator.behavior import BehaviorModeler
from coordinator.grounding import ground_intent
from coordinator.parse import extract_json_text, parse_json
from coordinator.policy import PolicyOptimizer
from coordinator.rule_coord import RuleBasedCoordinator
from coordinator.schema import DIRECTION_TO_EDGE, sanitize_intent
from coordinator.snapshot import EdgeState, NetworkSnapshot
from scripts import check_public_tree, mock_compare, recount_approvals


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

    def _parse_in_subprocess(self, raw: str):
        """Run parse_json in a child process with a time bound, so a regression
        to the old infinite loop fails this test instead of hanging the suite."""
        code = (
            "import json, sys; from coordinator.parse import parse_json; "
            "print(json.dumps(parse_json(sys.argv[1], None)))"
        )
        done = subprocess.run(
            [sys.executable, "-c", code, raw],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_close_tag_before_open_tag_terminates(self):
        self.assertEqual(self._parse_in_subprocess('{"a":1} </think> stray <think>'), {"a": 1})

    def test_unclosed_think_tag_terminates(self):
        self.assertEqual(self._parse_in_subprocess('{"a":1} <think> never closed'), {"a": 1})

    def test_every_ordered_think_pair_is_removed(self):
        raw = '<think>{"no":1}</think> <think>[9]</think>{"a":1}'
        self.assertEqual(extract_json_text(raw), '{"a":1}')


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
    """No student ID, phone number, long personal number or home path in the tree.

    The guard refuses these by shape (scripts/check_public_tree.py) and stores
    no personal value, not even a hash.
    """

    def test_public_tree_has_no_personal_identifier_or_home_path(self):
        self.assertEqual(check_public_tree.scan(ROOT), [])

    def test_guard_refuses_each_shape(self):
        # Made-up values with the shapes the guard must refuse.
        samples = {
            "student-id": "id A" + "0000000" + "X here",
            "home-path": "see " + "C:" + "\\Users" + "\\someone\\repo",
            "phone": "call 100" + "-0000-" + "0000",
            "long-number": "number 0" + "123456789 end",
        }
        for shape, text in samples.items():
            with self.subTest(shape=shape):
                self.assertIn(shape, [name for _line, name in check_public_tree.scan_text(text)])
        posix_home = "/" + "home/someone/repo"
        self.assertTrue(check_public_tree.scan_text(posix_home))
        self.assertEqual(check_public_tree.scan_text("edge 479165267, t=1350.0, A12"), [])

    def test_planted_value_in_a_scratch_file_turns_the_scan_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "notes.md").write_text("contact 100" + "-0000-" + "0000\n", encoding="utf-8")
            problems = check_public_tree.scan(Path(tmp))
        self.assertEqual(problems, ["notes.md:1: phone-shaped string"])


class RecountTests(unittest.TestCase):
    """The approval numbers quoted in the README are recounted from the log."""

    def test_recount_matches_the_logged_run(self):
        counts = recount_approvals.recount(recount_approvals.DEFAULT_LOG)
        self.assertEqual(counts["ticks"], 180)
        self.assertEqual(counts["candidates"], 43)
        self.assertEqual(counts["approved"], 43)
        self.assertEqual(counts["rejected"], 0)
        self.assertEqual(counts["no_candidate"], 137)
        self.assertEqual(counts["model_calls"], 43)
        self.assertEqual(counts["no_candidate_pct"], 76.1)

    def test_readme_quotes_only_numbers_the_log_supports(self):
        counts = recount_approvals.recount(recount_approvals.DEFAULT_LOG)
        self.assertEqual(recount_approvals.check_readme(counts, recount_approvals.README), [])

    def test_reply_parser_replays_every_logged_verdict(self):
        counts = recount_approvals.recount(recount_approvals.DEFAULT_LOG)
        self.assertEqual(counts["replies_replayed"], 43)
        self.assertEqual(counts["replay_mismatch"], 0)
        self.assertEqual(counts["inconsistent_rows"], 0)

    def test_a_tampered_verdict_is_caught_by_the_replay(self):
        rows = recount_approvals.DEFAULT_LOG.read_text(encoding="utf-8").splitlines()
        target = next(i for i, line in enumerate(rows) if '"llm_called": true' in line)
        tampered = rows[target].replace('"approvals": {"vms": true}', '"approvals": {"vms": false}')
        self.assertNotEqual(tampered, rows[target])
        rows[target] = tampered
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp, "tampered.jsonl")
            log.write_text("\n".join(rows) + "\n", encoding="utf-8")
            counts = recount_approvals.recount(log)
        self.assertEqual(counts["replay_mismatch"], 1)

    def test_readme_test_count_matches_the_suite(self):
        suite = unittest.TestLoader().discover(str(ROOT / "tests"))
        readme = recount_approvals.README.read_text(encoding="utf-8")
        quoted = [int(n) for n in re.findall(r"#\s*(\d+) tests", readme)]
        self.assertTrue(quoted, "README.md no longer quotes the test count")
        self.assertEqual(set(quoted), {suite.countTestCases()})


class ApprovalParseTests(unittest.TestCase):
    def test_true_approves_and_reports_reply_keys(self):
        self.assertEqual(
            parse_approvals('{"vms":true,"rationale":"x"}', ["vms"]),
            ({"vms": True}, ["vms", "rationale"]),
        )

    def test_default_deny(self):
        cases = {
            '{"vms":false}': {"vms": False},
            '{"vms":"false"}': {"vms": False},
            '{"vms":1}': {"vms": False},
            '{"rationale":"forgot the key"}': {"vms": False},
            "sure, go ahead": {"vms": False},
            "[true]": {"vms": False},
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_approvals(raw, ["vms"])[0], expected)

    def test_each_candidate_is_judged_separately(self):
        approvals, _keys = parse_approvals(
            '<think>hm</think>{"vms":"TRUE","dispatch":false}', ["vms", "dispatch"]
        )
        self.assertEqual(approvals, {"vms": True, "dispatch": False})


class MockCompareScriptTests(unittest.TestCase):
    def test_canned_replies_match_the_committed_example(self):
        example = ROOT / "examples" / "mock_model_replies.json"
        committed = json.loads(example.read_text(encoding="utf-8"))
        self.assertEqual(mock_compare.run_canned_replies(), committed)

    def test_placeholder_reply_never_reaches_an_edge(self):
        rows = {row["case"]: row for row in mock_compare.run_canned_replies()}
        placeholder = rows["peak, placeholder tokens instead of a direction"]["applied"]
        self.assertIsNone(placeholder["edge_id"])
        self.assertFalse(placeholder["dispatch_av"])
        flagged = rows["peak, fenced JSON with integer text and a string false flag"]["applied"]
        self.assertEqual(flagged["edge_id"], DIRECTION_TO_EDGE["east_to_cbd"])
        self.assertFalse(flagged["alert_issued"])

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
