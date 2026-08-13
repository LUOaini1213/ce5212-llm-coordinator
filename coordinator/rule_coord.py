"""Deterministic coordinator. Same intent schema as the LLM path."""

from __future__ import annotations

from .schema import EDGE_TO_DIRECTION
from .snapshot import NetworkSnapshot


class RuleBasedCoordinator:
    """Hard-coded triggers that mirror the LLM prompt rules."""

    OCC_THRESH = 0.7
    HALT_THRESH = 10

    def __init__(self, call_interval: int = 60):
        self.interval = call_interval
        self.last_call_t = -call_interval
        self.call_count = 0

    def should_call(self, sim_time: float) -> bool:
        return (sim_time - self.last_call_t) >= self.interval

    def run(self, snapshot: NetworkSnapshot) -> dict:
        self.last_call_t = snapshot.sim_time
        self.call_count += 1

        worst_dir = "none"
        worst_occ = self.OCC_THRESH
        for e in snapshot.edges:
            label = EDGE_TO_DIRECTION.get(e.edge_id)
            if label is None:
                continue
            if e.occupancy > worst_occ:
                worst_occ = e.occupancy
                worst_dir = label
            elif worst_dir == "none" and e.halting_count > self.HALT_THRESH:
                worst_dir = label

        if worst_dir != "none":
            extend = int(10 + max(0, worst_occ - self.OCC_THRESH) / 0.3 * 15)
            extend = max(10, min(25, extend))
        else:
            extend = 0

        return {
            "congested_direction": worst_dir,
            "extend_green_seconds": extend,
            "dispatch_av": snapshot.av_waiting > 3,
            "alert_passengers": snapshot.incident is not None,
            "rationale": f"rule: worst_occ={worst_occ:.2f} av_wait={snapshot.av_waiting}",
            "module": "coordinator",
            "source": "rule",
            "sim_time": snapshot.sim_time,
        }
