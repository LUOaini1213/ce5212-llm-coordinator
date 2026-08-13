"""Policy search loop: ingest scores, propose next fleet config.

LLM scenario generation is optional; fallback and propose_next are deterministic.
"""

from __future__ import annotations

from typing import Any, Optional

AV_STOPS = [
    "stop_kent_ridge_mrt",
    "stop_nus_central",
    "stop_nus_pgp",
    "stop_one_north",
]


class PolicyOptimizer:
    BASE_CONFIG = {
        "av_fleet_size": 3,
        "av_frequency_min": 15,
        "av_stops": ["stop_kent_ridge_mrt", "stop_nus_central"],
        "av_capacity": 8,
        "signal_offset_s": 0,
    }

    def __init__(self, max_iterations: int = 5, target_travel_min: float = 45.0):
        self.max_iter = max_iterations
        self.target_min = target_travel_min
        self.history: list[dict[str, Any]] = []
        self.best_config: dict[str, Any] = {}
        self.best_score: float = 999.0

    def ingest_result(
        self,
        scenario: dict,
        avg_travel_min: float,
        avg_wait_s: float,
        mode_shift_pct: float,
    ) -> dict:
        result = {
            **scenario,
            "avg_travel_min": avg_travel_min,
            "avg_wait_s": avg_wait_s,
            "mode_shift_pct": mode_shift_pct,
            "gap_to_target": avg_travel_min - self.target_min,
        }
        self.history.append(result)
        if avg_travel_min < self.best_score:
            self.best_score = avg_travel_min
            self.best_config = scenario.copy()
        return result

    def propose_next(self) -> Optional[dict]:
        if len(self.history) >= self.max_iter or not self.history:
            return None
        best = min(self.history, key=lambda x: x.get("avg_travel_min", 999))
        current_stops = best.get("av_stops", AV_STOPS[:2])
        new_stops = AV_STOPS if len(current_stops) < len(AV_STOPS) else current_stops
        new_fleet = min(10, int(best.get("av_fleet_size", 5)) + 1)
        new_freq = max(5, int(best.get("av_frequency_min", 10)) - 2)
        new_capacity = min(12, int(best.get("av_capacity", 8)) + 2)
        return {
            "scenario_id": f"S{len(self.history) + 1}",
            "label": f"iteration_{len(self.history) + 1}",
            "av_fleet_size": new_fleet,
            "av_frequency_min": new_freq,
            "av_stops": new_stops,
            "av_capacity": new_capacity,
            "signal_offset_s": 3,
            "hypothesis": (
                f"Increase fleet to {new_fleet}, freq {new_freq}min, "
                f"{len(new_stops)} stops, capacity {new_capacity}"
            ),
        }

    def fallback_scenarios(self, n: int = 3) -> list[dict]:
        rows = [
            ("conservative", 3, 15, "Low cost baseline"),
            ("moderate", 5, 10, "Balanced fleet"),
            ("aggressive", 8, 5, "Maximum coverage"),
        ]
        return [
            {
                "scenario_id": f"S{i + 1}",
                "label": label,
                "av_fleet_size": fs,
                "av_frequency_min": fr,
                "av_stops": AV_STOPS[:2],
                "av_capacity": 8,
                "signal_offset_s": 0,
                "hypothesis": h,
            }
            for i, (label, fs, fr, h) in enumerate(rows[:n])
        ]

    def final_recommendation(self) -> dict:
        if not self.history:
            return {"error": "no runs completed"}
        baseline = self.history[0]
        best = min(self.history, key=lambda x: x.get("avg_travel_min", 999))
        saving = baseline["avg_travel_min"] - best["avg_travel_min"]
        pct = saving / baseline["avg_travel_min"] * 100 if baseline["avg_travel_min"] else 0.0
        return {
            "best_config": self.best_config,
            "time_saving_min": round(saving, 1),
            "vs_baseline_pct": round(pct, 1),
            "all_scenarios_tested": len(self.history),
            "baseline_travel_min": baseline["avg_travel_min"],
            "best_travel_min": best["avg_travel_min"],
        }
