"""Semantic-intent schema.

Direction labels are the only vocabulary the decision module may emit.
Example edge IDs are public OSM way identifiers used in the course corridor
network; they are not private telemetry.
"""

import math
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


def parse_bool_flag(value: Any) -> bool:
    """Accept JSON booleans or explicit true/false text; never arbitrary truthiness."""
    if type(value) is bool:
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def parse_extend_seconds(value: Any) -> int:
    """Retain finite numeric/integer-text coercion, clamp to the actuator bounds."""
    if type(value) not in (int, float, str):
        return 0
    if type(value) is float and not math.isfinite(value):
        return 0
    try:
        extend = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(EXTEND_MIN, min(EXTEND_MAX, extend))


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

    extend = parse_extend_seconds(raw.get("extend_green_seconds", 0))
    if direction == "none":
        extend = 0

    return {
        "congested_direction": direction,
        "extend_green_seconds": extend,
        "dispatch_av": parse_bool_flag(raw.get("dispatch_av", False)),
        "alert_passengers": parse_bool_flag(raw.get("alert_passengers", False)),
        "rationale": str(raw.get("rationale", ""))[:200],
        "module": "coordinator",
        "source": source,
        "sim_time": sim_time,
    }
