"""Write the certificate counts the manuscript prints from the CODECHECK study's results.

The study's results file holds one object per certificate that reaches the last condition of the
appendix's first table, and no field counting them. This counts the objects, and copies the
register's size and the pooled counts beside the count so one artifact holds the sentence's
four numbers.

Sources, both copied from the reproducible-science-codecheck repository and pinned here:
`paper/artifacts/codecheck_indices.json` (its `results/indices.json`) and
`paper/artifacts/codecheck_eligibility_summary.json` (its `data/eligibility_summary.json`).

    uv run --no-project python scripts/derive_codecheck_counts.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "paper" / "artifacts"
INDICES = ART / "codecheck_indices.json"
ELIGIBILITY = ART / "codecheck_eligibility_summary.json"
OUT = ART / "codecheck_counts.json"


def pinned(path: pathlib.Path) -> dict[str, str]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    indices = json.loads(INDICES.read_text())
    eligibility = json.loads(ELIGIBILITY.read_text())
    counts = {
        "generated_by": "scripts/derive_codecheck_counts.py",
        "sources": [pinned(INDICES), pinned(ELIGIBILITY)],
        "certificates_in_register": eligibility["certificates"],
        "certificates_with_a_linked_table_file": len(indices["per_certificate"]),
        "numbers_printed": indices["pooled"]["printed"],
        "numbers_bound": indices["pooled"]["bound"],
    }
    OUT.write_text(json.dumps(counts, indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}: {counts['certificates_with_a_linked_table_file']} of "
          f"{counts['certificates_in_register']} certificates, {counts['numbers_bound']} of "
          f"{counts['numbers_printed']} numbers")


if __name__ == "__main__":
    main()
