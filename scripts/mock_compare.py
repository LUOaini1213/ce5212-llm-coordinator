"""Deterministic rule coordinator vs grounding, no SUMO / no Ollama."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coordinator.grounding import ground_intent
from coordinator.rule_coord import RuleBasedCoordinator
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


def main() -> Path:
    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    rows = run_ticks()
    path = out_dir / "mock_compare.json"
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"wrote {path}")
    for row in rows:
        a = row["applied"]
        print(
            f"t={row['t']:.0f} dir={a['direction']} "
            f"edge={a['edge_id']} ext={a['extend_applied']} skip={a['skipped_reason']}"
        )
    return path


if __name__ == "__main__":
    main()
