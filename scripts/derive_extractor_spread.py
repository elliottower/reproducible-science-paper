"""Write the spread between the best and the worst reader the manuscript quotes.

Table 6's caption says the low-level parser resolves a number of passages fewer than the best
single extractor. `real_corpus_by_reader.json` holds each reader's count; the difference was
stored nowhere. It is computed here from the stored counts, with the readers it names, so the
manuscript's number has an address.

    uv run --no-project python scripts/derive_extractor_spread.py
"""

import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "paper" / "artifacts" / "real_corpus_by_reader.json"
OUT = ROOT / "paper" / "artifacts" / "extractor_spread.json"


def main() -> int:
    resolved = {reader: held["resolved"] for reader, held in json.loads(SOURCE.read_text())["per_reader"].items()}
    best = max(resolved, key=resolved.__getitem__)
    worst = min(resolved, key=resolved.__getitem__)
    out = {
        "source": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "resolved_by_reader": resolved,
        "best_reader": best,
        "worst_reader": worst,
        "best_minus_worst": resolved[best] - resolved[worst],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for key, value in out.items():
        print(f"  {key:20} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
