"""Fail if a text file in the repo carries a personal identifier or a local path.

The guard stores no personal value, not even a hash: ID-, phone- and
home-path-shaped strings are refused by shape. (A SHA-256 of a 10- or
11-digit number can be brute-forced in seconds, so a committed digest would
still leak the value.) A legitimate string that happens to have one of these
shapes, e.g. a 10-digit OSM way ID, goes into ALLOWED with a comment.

    python scripts/check_public_tree.py          # scan the repo, exit 1 on a hit
    python scripts/check_public_tree.py --root DIR
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Shapes refused anywhere in a scanned file.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # NUS matriculation number: A + 7 digits + check letter.
    ("student-id", re.compile(r"(?<![0-9A-Za-z])A\d{7}[A-Z](?![0-9A-Za-z])")),
    # Home directories on Windows, macOS and Linux, with either slash.
    ("home-path", re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"'`]+", re.IGNORECASE)),
    ("home-path", re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z0-9_.-]+")),
    # Mobile number written 3-4-4 with dashes, dots or spaces.
    ("phone", re.compile(r"(?<!\d)\d{3}[-. ]\d{4}[-. ]\d{4}(?!\d)")),
    # Any bare run of 10 or 11 digits (mobile, QQ/WeChat-style personal numbers).
    ("long-number", re.compile(r"(?<![\d.])\d{10,11}(?![\d.])")),
)

# Exact strings that match a shape above but are not personal data.
ALLOWED: frozenset[str] = frozenset()

SCANNED_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".yml", ".yaml", ".toml",
    ".cfg", ".ini", ".csv", ".tsv", ".html", ".gitattributes", ".gitignore",
}
SCANNED_NAMES = {"LICENSE", "README", ".gitattributes", ".gitignore"}
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", ".pytest_cache"}


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if SKIP_DIRS.intersection(path.relative_to(root).parts):
            continue
        if path.suffix.lower() in SCANNED_SUFFIXES or path.name in SCANNED_NAMES:
            yield path


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, shape name) for every refused match in text.

    The matched value itself is never returned, so a failing run does not
    print the identifier it found into a public CI log.
    """
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in PATTERNS:
            for match in pattern.finditer(line):
                if match.group(0) not in ALLOWED:
                    hits.append((lineno, name))
    return hits


def scan(root: Path) -> list[str]:
    problems: list[str] = []
    for path in iter_files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, name in scan_text(text):
            problems.append(f"{path.relative_to(root).as_posix()}:{lineno}: {name}-shaped string")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    problems = scan(args.root.resolve())
    for problem in problems:
        print(f"REFUSED: {problem}", file=sys.stderr)
    if problems:
        return 1
    print("no personal-identifier or home-path shapes in the scanned files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
