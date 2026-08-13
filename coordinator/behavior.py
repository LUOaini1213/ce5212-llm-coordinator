"""Persona information visibility. Mode choice via LLM is optional."""

from __future__ import annotations

import random
from collections import Counter

from .snapshot import NetworkSnapshot, PassengerPersona


class BehaviorModeler:
    PERSONA_POOL = [
        {"type": "time_sensitive", "vot_sgd_hr": 25, "weight": 0.35},
        {"type": "price_sensitive", "vot_sgd_hr": 8, "weight": 0.40},
        {"type": "uninformed", "vot_sgd_hr": 15, "weight": 0.25},
    ]
    MODES = ["AV_shuttle", "conventional_bus", "walk_MRT", "grab_taxi"]
    INFO_VISIBILITY = {
        "time_sensitive": ["app_estimated_wait", "av_availability", "mrt_crowding"],
        "price_sensitive": ["bus_schedule", "walk_time"],
        "uninformed": ["bus_schedule"],
    }

    def __init__(self, rng: random.Random | None = None):
        self.trip_log: list[dict] = []
        self.agent_memories: dict[str, list] = {}
        self.rng = rng or random.Random()

    def build_local_info(self, persona: PassengerPersona, snapshot: NetworkSnapshot) -> dict:
        visible = self.INFO_VISIBILITY.get(persona.agent_type, [])
        full = {
            "app_estimated_wait": f"{int(snapshot.avg_wait_s / 60) + self.rng.randint(0, 3)} min",
            "av_availability": "available" if snapshot.av_waiting < 3 else "busy",
            "mrt_crowding": "high" if any(e.congested for e in snapshot.edges) else "normal",
            "bus_schedule": f"next bus in {self.rng.randint(4, 18)} min",
            "walk_time": f"{self.rng.randint(8, 15)} min walk to Kent Ridge MRT",
        }
        return {k: v for k, v in full.items() if k in visible}

    def sample_persona(
        self,
        agent_id: str,
        origin: str = "NUS PGP",
        destination: str = "Kent Ridge MRT",
    ) -> PassengerPersona:
        weights = [p["weight"] for p in self.PERSONA_POOL]
        pool = self.rng.choices(self.PERSONA_POOL, weights=weights, k=1)[0]
        return PassengerPersona(
            agent_id=agent_id,
            origin=origin,
            destination=destination,
            agent_type=pool["type"],
            value_of_time=pool["vot_sgd_hr"],
            memory=self.agent_memories.get(agent_id, []),
        )

    def record_decision(self, result: dict) -> None:
        if result.get("chosen_mode") not in self.MODES:
            result["chosen_mode"] = "conventional_bus"
        self.trip_log.append(result)

    def aggregate_mode_share(self) -> dict:
        if not self.trip_log:
            return {}
        counts = Counter(r["chosen_mode"] for r in self.trip_log)
        total = len(self.trip_log)
        would_switch = sum(1 for r in self.trip_log if r.get("would_change_if_informed"))
        av_aware = sum(1 for r in self.trip_log if r["chosen_mode"] == "AV_shuttle")
        return {
            "mode_share_pct": {k: round(v / total * 100, 1) for k, v in counts.items()},
            "total_trips": total,
            "av_adoption_pct": round(av_aware / total * 100, 1),
            "would_switch_if_informed_pct": round(would_switch / total * 100, 1),
        }
