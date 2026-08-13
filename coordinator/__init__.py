"""CE5212 semantic-intent coordinator.

Course project: LLM proposes direction+magnitude; code grounds to edge IDs.
Not a vehicle-side planner, VLA, or world model.
"""

from .schema import (
    DIRECTION_TO_EDGE,
    EDGE_TO_DIRECTION,
    SEMANTIC_DIRECTIONS,
    empty_intent,
    sanitize_intent,
)
from .snapshot import EdgeState, NetworkSnapshot, PassengerPersona
from .parse import extract_json_text, parse_json
from .grounding import ground_intent
from .rule_coord import RuleBasedCoordinator
from .policy import PolicyOptimizer
from .behavior import BehaviorModeler

__all__ = [
    "DIRECTION_TO_EDGE",
    "EDGE_TO_DIRECTION",
    "SEMANTIC_DIRECTIONS",
    "empty_intent",
    "sanitize_intent",
    "EdgeState",
    "NetworkSnapshot",
    "PassengerPersona",
    "extract_json_text",
    "parse_json",
    "ground_intent",
    "RuleBasedCoordinator",
    "PolicyOptimizer",
    "BehaviorModeler",
]
