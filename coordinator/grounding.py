"""Ground a semantic intent to an executable edge action.

This is the isolation layer: decision modules never emit TraCI/OSM IDs.
"""

from __future__ import annotations

from typing import Any, Mapping

from .schema import DIRECTION_TO_EDGE


def ground_intent(
    intent: Mapping[str, Any],
    mapping: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Translate direction + magnitude into an apply record.

    Does not call SUMO. A runner may use edge_id to touch TraCI.
    """
    table = mapping if mapping is not None else DIRECTION_TO_EDGE
    direction = intent.get("congested_direction", "none")
    try:
        extend = int(intent.get("extend_green_seconds", 0))
    except (TypeError, ValueError):
        extend = 0

    if direction in (None, "none", ""):
        skipped = "no_direction"
        edge_id = None
    else:
        edge_id = table.get(direction)
        if not edge_id:
            skipped = "unknown_direction"
            edge_id = None
        elif extend <= 0:
            skipped = "zero_extend"
        else:
            skipped = None

    applied = skipped is None
    return {
        "sim_time": intent.get("sim_time"),
        "source": intent.get("source"),
        "direction": direction,
        "edge_id": edge_id,
        "extend_applied": extend if applied else 0,
        "signal_extended": applied,
        "dispatch_av": bool(intent.get("dispatch_av", False)),
        "alert_issued": bool(intent.get("alert_passengers", False)),
        "skipped_reason": skipped,
    }
