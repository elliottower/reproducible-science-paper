"""Recall over CORE-Bench capsules, from the run that measured it.

The manuscript reports recall against a benchmark that states the values each capsule produces.
That measurement was made in a separate repository and its output lived only there, so the
figures reached the manuscript with no artifact beside them that a reader could check. This
reads the recorded run and writes the counts the manuscript quotes.

Source: `paper/artifacts/corebench_recall.jsonl`, one record per capsule, each carrying the
benchmark's stated values and whether each was located. `evaluation/corebench_recall.py`
produced it.

    uv run --no-project python scripts/derive_corebench_recall.py [--source PATH]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "paper" / "artifacts" / "corebench_recall.jsonl"
TARGET = ROOT / "paper" / "artifacts" / "corebench_recall.json"

#: Reported in this order, weakest constraint first. A tier absent from the run is omitted
#: rather than written as zero, which would read as measured and empty.
TIERS = ("trivial", "weak", "moderate", "strong")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    args = ap.parse_args()

    raw = args.source.read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    answers = [a for row in rows for a in row["answers"]]
    located = [a for a in answers if a.get("found")]

    stated = collections.Counter(a.get("strength") for a in answers)
    hit = collections.Counter(a.get("strength") for a in located)

    # Recorded relative to the repository root where the source is inside it. An absolute path
    # names one machine, and would make this file differ between a clone and the tree it was
    # written in -- which is the digest the manifest pins.
    source = args.source.resolve()
    where = source.relative_to(ROOT) if source.is_relative_to(ROOT) else source

    out = {
        "source": {
            "path": str(where),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "records": len(rows),
        },
        "capsules_measured": len(rows),
        "values_stated": len(answers),
        "values_located": len(located),
        "recall": round(len(located) / len(answers), 5) if answers else 0,
        "capsules_with_an_unread_record": sum(1 for row in rows if row.get("unread")),
        "by_strength": {
            tier: {
                "stated": stated[tier],
                "located": hit[tier],
                "recall": round(hit[tier] / stated[tier], 5),
            }
            for tier in TIERS
            if stated.get(tier)
        },
    }
    TARGET.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"  {TARGET.relative_to(ROOT)}")
    print(f"    {out['capsules_measured']} capsules, {out['values_stated']} stated, "
          f"{out['values_located']} located, recall {out['recall']:.1%}")
    for tier, v in out["by_strength"].items():
        print(f"    {tier:<10}{v['stated']:>5}{v['located']:>6}{v['recall']:>8.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
