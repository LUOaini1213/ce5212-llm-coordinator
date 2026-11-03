"""Turn a model's yes/no reply into per-candidate approvals.

This is the reply-parsing half of the approval gate behind the logged course
run (data/course_run_B_s42.jsonl). It was written for this repo on 2026-11-03
and is replayed against every logged reply in tests; the course loop's own
parser and the rule trigger that proposed the candidates are not shipped.

Default deny: a candidate is approved only when the reply carries its key with
a JSON ``true`` or the text ``"true"``. A missing key, ``"false"``, a number,
or a reply that is not a JSON object leaves the candidate unapproved.
"""

from __future__ import annotations

from typing import Any, Iterable

from .parse import parse_json
from .schema import parse_bool_flag


def parse_approvals(raw: str, candidate_keys: Iterable[str]) -> tuple[dict[str, bool], list[str]]:
    """Return (approvals keyed by candidate, keys the reply carried)."""
    reply: Any = parse_json(raw, None)
    if not isinstance(reply, dict):
        return {key: False for key in candidate_keys}, []
    approvals = {key: parse_bool_flag(reply.get(key, False)) for key in candidate_keys}
    return approvals, [str(key) for key in reply]
