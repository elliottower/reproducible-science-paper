"""Write the layout-mode failures of the quotation audit, grouped by the readers that resolve them.

Section 4.2 and Appendix C give the 113 quotations poppler's layout mode does not resolve, how
many of them reading order resolves, how many only another reader resolves and how many no
reader resolves, and the false-accusation rate a two-state checker would carry over the audit's
quotations. `real_corpus_by_reader.json` holds every quotation's outcome under each reader, and
the toolkit's verify-performance summary holds the audit's quotation count; neither holds the
groups or the rate. They are computed here from the stored outcomes.

    uv run --no-project python scripts/derive_layout_failures.py
"""

import collections
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "paper" / "artifacts"
CORPUS = ART / "real_corpus_by_reader.json"
AUDIT = ART / "toolkit_verify_performance_summary.json"
OUT = ART / "layout_failures.json"
LAYOUT = "poppler-layout"
FLOW = "poppler-flow"


def digest(path: pathlib.Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> int:
    outcomes = json.loads(CORPUS.read_text())["per_quote"]
    quotations = json.loads(AUDIT.read_text())["baseline_as_declared"]["quotations"]
    groups = collections.Counter()
    for readers in outcomes.values():
        if readers[LAYOUT] != "not found":
            continue
        resolving = {reader for reader, outcome in readers.items() if outcome == "found"}
        if FLOW in resolving:
            groups["resolved_by_reading_order"] += 1
        elif resolving:
            groups["resolved_only_by_another_reader"] += 1
        else:
            groups["resolved_by_no_reader"] += 1
    failures = sum(groups.values())
    out = {
        "sources": [digest(CORPUS), digest(AUDIT)],
        "layout_mode_not_found": failures,
        **{name: groups[name] for name in
           ("resolved_by_reading_order", "resolved_only_by_another_reader", "resolved_by_no_reader")},
        "quotations_audited": quotations,
        "false_accusation_rate": str(failures / quotations),
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for key, value in out.items():
        if key != "sources":
            print(f"  {key:35} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
