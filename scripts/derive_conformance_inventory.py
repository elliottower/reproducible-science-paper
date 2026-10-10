"""Record what the conformance suite contains, so the manuscript's count is checkable.

The manuscript states 25 fixtures and gives their breakdown by what each addresses. The
count lived only in the directory listing, so nothing could re-check it, and an older stored figure
said nineteen. This writes the inventory the manuscript's sentence is asserted against.

    uv run --no-project python scripts/derive_conformance_inventory.py <suite-dir>
"""

import argparse
import json
import pathlib

GROUPS = {
    "table_cell": ("table_cell_match", "table_cell_mismatch", "table_column_absent",
                   "table_row_absent", "table_row_ambiguous"),
    "value": ("value_match", "value_match_printed_precision", "value_mismatch",
              "value_not_numeric"),
    "prose_anchor": ("prose_anchors_ambiguous", "prose_number_as_word", "prose_value_match"),
    "correspondence": ("correspondence_match", "correspondence_mismatch",
                       "correspondence_side_absent"),
    "artifact_availability": ("artifact_missing", "artifact_undeclared", "artifact_unreadable"),
    "pointer": ("pointer_absent", "pointer_escaped_key"),
    "passage": ("passage_absent", "passage_present"),
    "unpinned_artifact": ("unpinned_artifact",),
    "broken_pin": ("broken_pin",),
    "no_evidence_offered": ("no_evidence_offered",),
}

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "artifacts" / "conformance_inventory.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", type=pathlib.Path, help="the conformance cases/ directory")
    cases = sorted(p.name for p in ap.parse_args().suite.iterdir() if p.is_dir())

    grouped = {g: sorted(set(names) & set(cases)) for g, names in GROUPS.items()}
    ungrouped = sorted(set(cases) - {n for names in GROUPS.values() for n in names})

    out = {
        "fixtures": len(cases),
        "by_group": {g: len(v) for g, v in grouped.items()},
        "cases": cases,
        "ungrouped": ungrouped,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"  fixtures {out['fixtures']}")
    for g, n in out["by_group"].items():
        print(f"    {g:24} {n}")
    if ungrouped:
        print(f"  UNGROUPED (the manuscript's breakdown misses these): {ungrouped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
