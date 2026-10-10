"""Compare a re-run of the CORE-Bench recall measurement with the record the paper reports.

    uv run --no-project python scripts/compare_corebench_rerun.py --rerun PATH

The paper's record is `paper/artifacts/corebench_recall.jsonl`, one object per capsule. A re-run
writes the same shape. Two records agree when they are equal as JSON; where they are not, the
fields that differ are named and the located-value counts of both are given. The comparison is
written to `paper/artifacts/corebench_rerun_comparison.json` with the digests of both inputs, so
the file says which two records it compared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORDED = ROOT / "paper" / "artifacts" / "corebench_recall.jsonl"
TARGET = ROOT / "paper" / "artifacts" / "corebench_rerun_comparison.json"


class ComparisonError(Exception):
    """A record that cannot be compared as given."""


def load(path: pathlib.Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    by_id = {row["capsule_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ComparisonError(f"{path} records a capsule more than once")
    return by_id


def located(row: dict) -> tuple[int, int]:
    answers = row.get("answers", [])
    return sum(1 for answer in answers if answer["found"]), len(answers)


def compare(recorded: dict[str, dict], rerun: dict[str, dict]) -> dict:
    differing = []
    for capsule in sorted(set(recorded) & set(rerun)):
        old, new = recorded[capsule], rerun[capsule]
        if old != new:
            differing.append({
                "capsule_id": capsule,
                "fields": sorted(key for key in set(old) | set(new) if old.get(key) != new.get(key)),
                "recorded_located": list(located(old)),
                "rerun_located": list(located(new)),
            })
    totals = {name: [sum(located(row)[i] for row in rows.values()) for i in (0, 1)]
              for name, rows in (("recorded", recorded), ("rerun", rerun))}
    return {
        "capsules_recorded": len(recorded),
        "capsules_rerun": len(rerun),
        "only_in_recorded": sorted(set(recorded) - set(rerun)),
        "only_in_rerun": sorted(set(rerun) - set(recorded)),
        "identical": len(set(recorded) & set(rerun)) - len(differing),
        "differing": differing,
        "located_of_stated": {name: {"located": found, "stated": stated} for name, (found, stated) in totals.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rerun", type=pathlib.Path, required=True)
    parser.add_argument("--target", type=pathlib.Path, default=TARGET,
                        help="where the comparison is written; one file per re-run compared")
    args = parser.parse_args()
    result = {
        "generated_by": "scripts/compare_corebench_rerun.py",
        "recorded": {"path": str(RECORDED.relative_to(ROOT)), "sha256": hashlib.sha256(RECORDED.read_bytes()).hexdigest()},
        "rerun": {"path": str(args.rerun), "sha256": hashlib.sha256(args.rerun.read_bytes()).hexdigest()},
        **compare(load(RECORDED), load(args.rerun)),
    }
    args.target.write_text(json.dumps(result, indent=2) + "\n")
    print(f"  wrote {args.target}: {result['identical']} identical, "
          f"{len(result['differing'])} differing, of {result['capsules_recorded']} recorded")


if __name__ == "__main__":
    main()
