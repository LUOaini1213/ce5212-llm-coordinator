"""Semantic-intent schema.

Direction labels are the only vocabulary the decision module may emit.
Example edge IDs are public OSM way identifiers used in the course corridor
network; they are not private telemetry.
"""

from typing import Any, Mapping

# Example corridor (NUS / AYE). Override via ground_intent(mapping=...).
DIRECTION_TO_EDGE: dict[str, str] = {
    "east_to_cbd": "479165267",
    "west_to_tuas": "479165268",
    "exit_ramp": "44628826",
    "merge_ramp": "173913076",
}
EDGE_TO_DIRECTION: dict[str, str] = {v: k for k, v in DIRECTION_TO_EDGE.items()}
SEMANTIC_DIRECTIONS: tuple[str, ...] = tuple(DIRECTION_TO_EDGE.keys()) + ("none",)

EXTEND_MIN = 0
EXTEND_MAX = 25


def empty_intent(sim_time: float, source: str, rationale: str = "no action") -> dict[str, Any]:
    return {
        "congested_direction": "none",
        "extend_green_seconds": 0,
        "dispatch_av": False,
        "alert_passengers": False,
        "rationale": rationale,
        "module": "coordinator",
        "source": source,
        "sim_time": sim_time,
    }


def sanitize_intent(raw: Mapping[str, Any] | Any, sim_time: float, source: str) -> dict[str, Any]:
    """Coerce arbitrary model output into a typed intent. Unknown direction → none."""
    if not isinstance(raw, dict):
        return empty_intent(sim_time, source, rationale="non-dict response")

    direction = raw.get("congested_direction", "none")
    if direction not in SEMANTIC_DIRECTIONS:
        direction = "none"

    try:
        extend = int(raw.get("extend_green_seconds", 0))
    except (TypeError, ValueError):
        extend = 0
    extend = max(EXTEND_MIN, min(EXTEND_MAX, extend))
    if direction == "none":
        extend = 0

    return {
        "congested_direction": direction,
        "extend_green_seconds": extend,
        "dispatch_av": bool(raw.get("dispatch_av", False)),
        "alert_passengers": bool(raw.get("alert_passengers", False)),
        "rationale": str(raw.get("rationale", ""))[:200],
        "module": "coordinator",
        "source": source,
        "sim_time": sim_time,
    }
