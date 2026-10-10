"""Record what each reader cost, and what the combinations in Table 6 cost together.

`real_corpus_by_reader.json` holds each reader's own seconds. Table 6 prints those and two
combined rows -- both poppler modes, and all six -- which are sums of them and are recorded
nowhere. A number the manuscript prints and no artifact states is the paper's own defect class
`a reported figure no recorded computation states`, and the way to make it assertable is to
compute it into an artifact first, as `derive_extractor_unions.py` already does for the union
counts.

    uv run --no-project python scripts/derive_reader_timings.py
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "paper" / "artifacts" / "real_corpus_by_reader.json"
TARGET = ROOT / "paper" / "artifacts" / "reader_timings.json"

#: The two rows of Table 6 that are combinations rather than single readers.
POPPLER_MODES = ("poppler-layout", "poppler-flow")


def main() -> int:
    corpus = json.loads(SOURCE.read_text())
    per_reader = {name: reader["seconds"] for name, reader in corpus["per_reader"].items()}

    derived = {
        "source": SOURCE.name,
        "unit": "seconds of wall clock to read every document in the corpus once",
        "per_reader": per_reader,
        "both_poppler_modes": round(sum(per_reader[name] for name in POPPLER_MODES), 2),
        "all_readers": round(sum(per_reader.values()), 2),
        "readers_counted": len(per_reader),
    }
    TARGET.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n")
    print(f"  {TARGET.relative_to(ROOT)}")
    for name, seconds in sorted(per_reader.items()):
        print(f"    {name:<18} {seconds}")
    print(f"    both poppler modes {derived['both_poppler_modes']}")
    print(f"    all {derived['readers_counted']} readers    {derived['all_readers']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
