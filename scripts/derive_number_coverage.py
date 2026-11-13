"""Write how many of the numbers the manuscript prints the manifest accounts for, and how.

Section 4.1 states, over every rendering the manifest pins, how many numbers are bound to a file,
how many are set aside, and how many neither. `repro numbers` counts them and writes nothing, so
its JSON report is read here and the counts are written to a file the manifest pins. Every
rendering is passed with `--text`: by default the command reads only the renderings a claim
quotes, which leaves out an appendix whose numbers are all set aside.

The manifest pins this file, so the count reads the manifest that pins the previous one. Only the
pin differs between the two, and no count depends on a pin, so `make manifest` builds the
manifest, runs this, and builds the manifest again.

    uv run --no-project --with pyyaml==6.0.2 python scripts/derive_number_coverage.py
"""

from __future__ import annotations

import collections
import json
import pathlib
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "repro.yaml"
OUT = ROOT / "paper" / "artifacts" / "number_coverage.json"
STANDINGS = ("bound", "set_aside_by_rule", "set_aside_with_a_reason", "unbound")


class UnknownStanding(Exception):
    """`repro numbers` gave a number a standing this count does not know."""


def main() -> int:
    texts = [a["id"] for a in yaml.safe_load(MANIFEST.read_text())["artifacts"] if a["id"].endswith("-text")]
    command = ["repro", "numbers", "--format", "json", *(f"--text={t}" for t in texts), MANIFEST.name]
    report = json.loads(subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    per_text = {}
    total = collections.Counter()
    for text in report["texts"]:
        counted = collections.Counter(n["standing"] for n in text["numbers"])
        if set(counted) - set(STANDINGS):
            raise UnknownStanding(", ".join(sorted(set(counted) - set(STANDINGS))))
        per_text[text["artifact"]] = {s: counted[s] for s in STANDINGS}
        total += counted
    numbers = sum(total.values())
    out = {
        "command": " ".join(command),
        "texts": len(per_text),
        "numbers": numbers,
        **{s: total[s] for s in STANDINGS},
        "set_aside": total["set_aside_by_rule"] + total["set_aside_with_a_reason"],
        "per_text": per_text,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for key, value in out.items():
        if key != "per_text":
            print(f"  {key:25} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
