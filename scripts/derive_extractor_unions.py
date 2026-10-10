"""Write the union figures the paper reports and the artifact did not hold.

`real_corpus_by_reader.json` records, per reader, how many of the corpus's passage checks
resolved, and records the outcome of every reader on every quotation. It does not record the
unions the manuscript quotes: how many resolve under either poppler mode, how many under at least
one reader, how many under none, and how many the lowest-scoring reader alone adds.

Those four were computed correctly and stored nowhere, so nothing could re-check them. That is the
defect class this paper calls a reported figure no recorded computation states. Deriving them into
an artifact is what makes them assertable.

    uv run --no-project python scripts/derive_extractor_unions.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "paper" / "artifacts" / "real_corpus_by_reader.json"
OUT = ROOT / "paper" / "artifacts" / "extractor_unions.json"

POPPLER = ("poppler-layout", "poppler-flow")


def main() -> int:
    data = json.loads(SOURCE.read_text())
    per_quote = data["per_quote"]
    rows = per_quote if isinstance(per_quote, list) else list(per_quote.values())

    found = lambda row, reader: row.get(reader) == "found"
    both_poppler = sum(1 for r in rows if any(found(r, p) for p in POPPLER))
    any_reader = sum(1 for r in rows if any(v == "found" for v in r.values()))
    no_reader = sum(1 for r in rows if not any(v == "found" for v in r.values()))
    lopdf_extends = sum(1 for r in rows
                        if found(r, "lopdf") and not any(found(r, p) for p in POPPLER))

    out = {
        "source": SOURCE.name,
        "corpus_quotations": len(rows),
        "resolved_by_either_poppler_mode": both_poppler,
        "resolved_by_at_least_one_reader": any_reader,
        "resolved_by_no_reader": no_reader,
        "added_to_the_poppler_union_by_lopdf_alone": lopdf_extends,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for k, v in out.items():
        print(f"  {k:44} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
