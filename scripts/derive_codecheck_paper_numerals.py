"""Write each differing number of Table 15 as a plain numeral, and its distance from the file's value.

The copied `codecheck_agreement_summary_2026-10-14.json` keeps the paper's numeral as the paper prints it, so
one carrying a thousands separator is no number a pointer can read, and it stores no absolute
difference. Table 15 prints both. This removes the separator from the stored numeral and computes
|paper - file| from the two stored numerals, with no rounding; the copy is left as it is.

    uv run --no-project python scripts/derive_codecheck_paper_numerals.py
"""

import decimal
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "paper" / "artifacts" / "codecheck_agreement_summary_2026-10-14.json"
OUT = ROOT / "paper" / "artifacts" / "codecheck_paper_numerals.json"


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
        rows.append({
            "certificate": difference["certificate"],
            "claim": difference["claim"],
            "paper_as_printed": difference["paper"],
            "paper": None if paper is None else str(paper),
            "stored": difference["stored"],
            "absolute_difference": None if paper is None or stored is None else str(abs(paper - stored)),
        })
    out = {
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "differences": rows,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for index, row in enumerate(rows):
        print(f"  {index:2} {row['paper_as_printed']:>12} {row['paper']!s:>12} {row['absolute_difference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
