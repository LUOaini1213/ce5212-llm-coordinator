"""Recount the coordination log shipped in data/, standard library only.

Every approval number quoted in README.md comes out of this script. `--check`
re-derives them from the log and compares them against the README text, so a
number edited in the README without the log backing it fails CI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "data" / "course_run_B_s42.jsonl"
README = ROOT / "README.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coordinator.approval import parse_approvals  # noqa: E402

# The fenced block in README.md that must equal this script's stdout verbatim.
BLOCK_RE = re.compile(
    r"```text\n(recount of data/course_run_B_s42\.jsonl\n.*?)```",
    re.DOTALL,
)

# Prose claims in README.md, each mapped to the recount fields it asserts.
PROSE_CLAIMS = (
    (
        re.compile(
            r"proposed \*\*(?P<candidates>\d+)\*\* candidate actions "
            r"across the (?P<ticks>\d+) coordination ticks"
        ),
        ("candidates", "ticks"),
    ),
    (
        re.compile(
            r"\*\*(?P<no_candidate>\d+) of the (?P<ticks>\d+) ticks "
            r"\((?P<no_candidate_pct_rounded>\d+)%\)"
        ),
        ("no_candidate", "ticks", "no_candidate_pct_rounded"),
    ),
    (
        re.compile(r"approved all (?P<approved>\d+), rejected (?P<rejected>\d+)"),
        ("approved", "rejected"),
    ),
    (
        re.compile(r"all (?P<candidates>\d+) candidates in this run are `vms`"),
        ("candidates",),
    ),
    (
        re.compile(
            r"re-parses all (?P<replies_replayed>\d+) logged replies"
        ),
        ("replies_replayed",),
    ),
)


def recount(log_path: Path) -> dict:
    """Walk the log once and count ticks, candidates and approvals."""
    ticks = candidates = approved = rejected = no_candidate = model_calls = 0
    replayed = replay_mismatch = inconsistent = 0
    by_key: dict[str, int] = {}
    for lineno, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - corrupt log
            raise SystemExit(f"{log_path}:{lineno}: {exc}") from exc
        ticks += 1
        candidates += int(row.get("n_candidates", 0))
        if int(row.get("n_candidates", 0)) == 0:
            no_candidate += 1
        if row.get("llm_called"):
            model_calls += 1
        # A tick reaches the model exactly when the rule layer proposed
        # something, and n_candidates agrees with the candidate list.
        n_listed = len(row.get("candidates", []))
        if bool(row.get("llm_called")) != (n_listed > 0) or n_listed != int(
            row.get("n_candidates", 0)
        ):
            inconsistent += 1
        # Replay the shipped reply parser over every logged model reply: it
        # must give back the logged verdicts and the logged parsed keys.
        if "raw" in row:
            keys = [str(c.get("key", "?")) for c in row.get("candidates", [])]
            got_approvals, got_keys = parse_approvals(row["raw"], keys)
            if got_approvals == row.get("approvals") and got_keys == row.get("parsed_keys"):
                replayed += 1
            else:
                replay_mismatch += 1
        for candidate in row.get("candidates", []):
            key = str(candidate.get("key", "?"))
            by_key[key] = by_key.get(key, 0) + 1
        # "approvals" is a dict keyed by candidate ({"vms": true}), empty on a
        # tick with no candidate -- not a list.
        for _key, verdict in row.get("approvals", {}).items():
            if verdict is True:
                approved += 1
            else:
                rejected += 1
    pct = round(no_candidate / ticks * 100, 1) if ticks else 0.0
    return {
        "log": log_path.name,
        "ticks": ticks,
        "candidates": candidates,
        "approved": approved,
        "rejected": rejected,
        "no_candidate": no_candidate,
        "no_candidate_pct": pct,
        "no_candidate_pct_rounded": int(round(pct)),
        "model_calls": model_calls,
        "by_key": dict(sorted(by_key.items())),
        "replies_replayed": replayed,
        "replay_mismatch": replay_mismatch,
        "inconsistent_rows": inconsistent,
    }


def render(counts: dict) -> str:
    """Fixed-width report; README.md embeds this verbatim."""
    rows = (
        ("coordination ticks", counts["ticks"]),
        ("candidate actions proposed", counts["candidates"]),
        ("approved by the model", counts["approved"]),
        ("rejected by the model", counts["rejected"]),
        ("ticks with no candidate", counts["no_candidate"]),
        ("no-candidate share", f"{counts['no_candidate_pct']}%"),
        ("ticks that called the model", counts["model_calls"]),
        (
            "candidates by action type",
            ", ".join(f"{key} {n}" for key, n in counts["by_key"].items()) or "none",
        ),
        (
            "logged replies re-parsed",
            f"{counts['replies_replayed']} of "
            f"{counts['replies_replayed'] + counts['replay_mismatch']}",
        ),
        ("inconsistent rows", counts["inconsistent_rows"]),
    )
    lines = [f"recount of data/{counts['log']}"]
    lines += [f"{label:<28}{value}" for label, value in rows]
    return "\n".join(lines) + "\n"


def check_readme(counts: dict, readme: Path) -> list[str]:
    """Return a list of mismatches between the README and the recount."""
    text = readme.read_text(encoding="utf-8")
    problems: list[str] = []

    match = BLOCK_RE.search(text)
    if match is None:
        problems.append("README.md has no ```text recount block")
    elif match.group(1) != render(counts):
        problems.append(
            "README.md recount block is stale:\n--- README ---\n"
            f"{match.group(1)}--- recount ---\n{render(counts)}"
        )

    # Every occurrence is checked, so a summary line near the top and the
    # longer paragraph further down cannot drift apart.
    for pattern, fields in PROSE_CLAIMS:
        matches = list(pattern.finditer(text))
        if not matches:
            problems.append(f"README.md no longer contains the claim /{pattern.pattern}/")
            continue
        for found in matches:
            for field in fields:
                quoted = int(found.group(field))
                if quoted != counts[field]:
                    problems.append(
                        f"README.md says {field}={quoted}, the log gives {counts[field]}"
                    )
    if counts["replay_mismatch"] or counts["inconsistent_rows"]:
        problems.append(
            f"log replay: {counts['replay_mismatch']} reply/verdict mismatches, "
            f"{counts['inconsistent_rows']} inconsistent rows"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--json", action="store_true", help="print the counts as JSON")
    parser.add_argument(
        "--check",
        action="store_true",
        help="also verify README.md quotes these numbers, exit 1 if it does not",
    )
    args = parser.parse_args(argv)

    counts = recount(args.log)
    sys.stdout.write(json.dumps(counts, indent=2) + "\n" if args.json else render(counts))

    if args.check:
        problems = check_readme(counts, README)
        if problems:
            for problem in problems:
                print(f"MISMATCH: {problem}", file=sys.stderr)
            return 1
        print("README.md matches the recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
