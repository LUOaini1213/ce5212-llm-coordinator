"""Two arms through the same grounding layer, no SUMO / no Ollama.

Arm 1 (output/mock_compare.json): the deterministic rule coordinator on three
ticks. Arm 2 (output/mock_model_replies.json): hand-written model-style
replies -- not real model output -- pushed through parse -> sanitize ->
ground, the path an LLM reply takes. It shows what the grounding boundary does
with a placeholder ID, a string flag, a reversed think tag and plain prose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coordinator.grounding import ground_intent
from coordinator.parse import parse_json
from coordinator.rule_coord import RuleBasedCoordinator
from coordinator.schema import sanitize_intent
from coordinator.snapshot import EdgeState, NetworkSnapshot


def snapshot_at(sim_time: float, peak: float) -> NetworkSnapshot:
    """peak in [0, 1]. Occupancy scales so t=1350 crosses the 0.7 trigger."""
    return NetworkSnapshot(
        sim_time=sim_time,
        edges=[
            EdgeState("479165267", 0.40 + 0.50 * peak, (90 - 40 * peak) / 3.6, int(8 * peak), 80),
            EdgeState("479165268", 0.30 + 0.25 * peak, (70 - 30 * peak) / 3.6, int(5 * peak), 30),
            EdgeState("44628826", 0.45 + 0.20 * peak, (80 - 35 * peak) / 3.6, int(6 * peak), 50),
            EdgeState("173913076", 0.20 + 0.15 * peak, (50 - 20 * peak) / 3.6, int(3 * peak), 20),
        ],
        av_waiting=int(5 * peak),
        avg_wait_s=30 + 60 * peak,
        incident="debris" if peak >= 0.99 else None,
    )


def run_ticks() -> list[dict]:
    coord = RuleBasedCoordinator(call_interval=60)
    rows = []
    for t, peak in ((0.0, 0.0), (1350.0, 1.0), (2700.0, 0.0)):
        snap = snapshot_at(t, peak)
        intent = coord.run(snap)
        applied = ground_intent(intent)
        rows.append({"t": t, "peak": peak, "intent": intent, "applied": applied})
    return rows


# (tick, label, reply). Hand-written to exercise the boundary; none of these
# came from a model run.
CANNED_REPLIES: tuple[tuple[float, str, str], ...] = (
    (
        0.0,
        "off-peak, think block and explicit none",
        '<think>occupancy is low everywhere</think>{"congested_direction":"none",'
        '"extend_green_seconds":0,"dispatch_av":false,"alert_passengers":false,'
        '"rationale":"quiet"}',
    ),
    (
        1350.0,
        "peak, fenced JSON with integer text and a string false flag",
        '```json\n{"congested_direction":"east_to_cbd","extend_green_seconds":"20",'
        '"dispatch_av":true,"alert_passengers":"false",'
        '"rationale":"east approach above 0.7 occupancy"}\n```',
    ),
    (
        1350.0,
        "peak, placeholder tokens instead of a direction",
        '{"edge_id":"str","congested_direction":"str","extend_green_seconds":"str",'
        '"dispatch_av":"str"}',
    ),
    (
        1350.0,
        "peak, stray close tag before an unclosed think tag",
        '{"congested_direction":"east_to_cbd","extend_green_seconds":15} </think> stray <think>',
    ),
    (2700.0, "off-peak, prose with no JSON", "The network looks fine, no action needed."),
)


def run_canned_replies() -> list[dict]:
    rows = []
    for t, label, reply in CANNED_REPLIES:
        parsed = parse_json(reply, None)
        intent = sanitize_intent(parsed, t, "canned-reply")
        applied = ground_intent(intent)
        rows.append({"t": t, "case": label, "reply": reply, "intent": intent, "applied": applied})
    return rows


def main() -> Path:
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    rows = run_ticks()
    path = out_dir / "mock_compare.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {path}  (rule coordinator)")
    for row in rows:
        a = row["applied"]
        print(
            f"t={row['t']:.0f} dir={a['direction']} "
            f"edge={a['edge_id']} ext={a['extend_applied']} skip={a['skipped_reason']}"
        )
    canned = run_canned_replies()
    canned_path = out_dir / "mock_model_replies.json"
    canned_path.write_text(json.dumps(canned, indent=2), encoding="utf-8")
    print(f"wrote {canned_path}  (hand-written model-style replies)")
    for row in canned:
        a = row["applied"]
        print(
            f"t={row['t']:.0f} dir={a['direction']} edge={a['edge_id']} "
            f"ext={a['extend_applied']} dispatch={a['dispatch_av']} "
            f"alert={a['alert_issued']} skip={a['skipped_reason']}  [{row['case']}]"
        )
    return path


if __name__ == "__main__":
    main()
