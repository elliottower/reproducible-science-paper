"""Write each differing number's distance from the file's value, as a share of the file's value.

Appendix C and Table 15 print how far three memory measurements in a certified paper are from
the value its regenerated file stores, as a percentage of the file's value. The copied
`codecheck_agreement_summary.json` stores `relative_difference` as a share of the paper's value,
so it holds the distance but not the percentage printed. The copy is left as the
reproducible-science-codecheck repository wrote it; this computes the share of the file's value
from the paper's and the file's numerals it stores, with no rounding.

    uv run --no-project python scripts/derive_relative_to_file.py
"""

from __future__ import annotations

import decimal
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "paper" / "artifacts" / "codecheck_agreement_summary.json"
OUT = ROOT / "paper" / "artifacts" / "codecheck_relative_to_file.json"


def number(numeral: str) -> decimal.Decimal | None:
    try:
        return decimal.Decimal(numeral.replace(",", ""))
    except decimal.InvalidOperation:
        return None


def main() -> int:
    decimal.getcontext().prec = 40
    rows = []
    for difference in json.loads(SOURCE.read_text())["differences"]:
        paper, stored = number(difference["paper"]), number(difference["stored"])
        share = None if paper is None or stored is None or stored == 0 else abs(paper - stored) / abs(stored)
        rows.append({
            "certificate": difference["certificate"],
            "claim": difference["claim"],
            "paper": difference["paper"],
            "stored": difference["stored"],
            "relative_to_file": None if share is None else str(share),
        })
    out = {
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "definition": "|paper - stored| / |stored|, from the numerals the source stores",
        "differences": rows,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for index, row in enumerate(rows):
        print(f"  {index:2} {row['paper']:>12} {row['stored']:>14} {row['relative_to_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
