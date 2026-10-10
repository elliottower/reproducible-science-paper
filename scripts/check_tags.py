"""Every unresolved item in the manuscript is tagged, and this finds them.

A placeholder written as prose reads as finished text and ships. Tags do not: they render in
red or orange in the PDF, and this refuses a final build while any remain.

    uv run --no-project python scripts/check_tags.py            # the files that ship
    uv run --no-project python scripts/check_tags.py --all      # every draft in paper/
    uv run --no-project python scripts/check_tags.py --final    # exit 1 if any remain

Only the files a submission carries are checked by default. Globbing `paper/*.tex` counts
superseded drafts, so `--final` refused every build on tags in versions nobody will read, and a
gate that always refuses is switched off by whoever it obstructs.

TODO    something that must be done before submission
FILL-IN a number or table that does not exist yet
REVIEW  something written but unverified, or a decision the author owes
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
KINDS = ("TODO", "FILLIN", "REVIEW")

# What a submission carries. Superseded drafts stay in paper/ as the record of what they said,
# and their tags are not defects in anything anyone will read. Named here so a new version means
# changing one line; a stale entry here means the gate passes against a file nobody submits.
# Beside the manuscript the Makefile names with --paper: the appendix it inputs and the supplement
# built with it.
SHIPPING = (
    "generated/audit_appendix.tex",
    "supplement_defects.tex",
)
# The macro name, then a brace-balanced first argument. No variable-length context on both
# sides: that pattern backtracks exponentially and has hung this machine for hours.
TAG = re.compile(r"\\(" + "|".join(KINDS) + r")\{")


def first_argument(text: str, start: int) -> str:
    """Return the brace-balanced argument beginning at the opening brace at `start`."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return text[start + 1 : start + 80]


def find(path: pathlib.Path) -> list[dict]:
    text = path.read_text()
    found = []
    for m in TAG.finditer(text):
        # A definition is not an occurrence.
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start:].startswith("\\newcommand"):
            continue
        body = first_argument(text, m.end() - 1)
        found.append(
            {
                "file": str(path.relative_to(ROOT)),
                "line": text.count("\n", 0, m.start()) + 1,
                "kind": m.group(1),
                "text": " ".join(body.split())[:100],
            }
        )
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="exit 1 while any tag remains")
    ap.add_argument("--paper", required=True, help="stem of the manuscript that ships")
    ap.add_argument("--all", action="store_true",
                    help="scan every draft in paper/, not only the files that ship")
    args = ap.parse_args()

    if args.all:
        paths = sorted(ROOT.glob("paper/*.tex"))
    else:
        paths = [ROOT / "paper" / name for name in (f"{args.paper}.tex", *SHIPPING)]
        missing = [p.name for p in paths if not p.exists()]
        if missing:
            raise SystemExit(f"SHIPPING names files that are not in paper/: {missing}")

    tags: list[dict] = []
    for tex in paths:
        tags.extend(find(tex))

    out = ROOT / "paper" / "tags.json"
    out.write_text(json.dumps({"count": len(tags), "tags": tags}, indent=2) + "\n")

    by_kind = {k: [t for t in tags if t["kind"] == k] for k in KINDS}
    for kind in KINDS:
        for t in by_kind[kind]:
            print(f"  {kind:<7} {t['file']}:{t['line']}  {t['text']}")
    counts = "  ".join(f"{k}={len(by_kind[k])}" for k in KINDS)
    print(f"\n  {counts}   written to {out.relative_to(ROOT)}")

    if args.final and tags:
        print(f"\n  REFUSING a final build: {len(tags)} unresolved tags remain")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
