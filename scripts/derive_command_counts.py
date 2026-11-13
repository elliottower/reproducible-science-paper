"""Write the counts the appendices read out of recorded command output.

`run_audit.py` records each command's output as text. The generated appendix prints counts taken
from that text by the patterns each audit file declares under `counts` (registrations unchanged,
quotations found, bibliography entries that agree, recorded files that match), and the census
appendix prints how many hashes the one resealed file was recorded with. A line of text is not
addressable by a JSON Pointer, so the counts are derived into an artifact here and the manifest
points at that.

The generated appendix's counts are `Rendered.values`, resolved by `build_audit_appendix` with the
patterns the audit files declare, so a count here is the count printed. The census count is read
from the `results verify` output of `paper/audit/census_audit.json` by `RESEALED`.

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        python scripts/derive_command_counts.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

from pydantic import BaseModel, ConfigDict

import build_audit_appendix as appendix

OUT = appendix.ROOT / "paper" / "artifacts" / "command_counts.json"
CENSUS = appendix.AUDIT / "census_audit.json"

#: A resealed path in `results verify` output, and the line under it giving its hash count.
RESEALED = re.compile(r"^  RESEALED +(\S+)\n +recorded (\d+) different hashes", re.M)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pinned(Strict):
    path: str
    sha256: str


class Census(Strict):
    record: Pinned
    hashes_by_resealed_file: dict[str, int]


class Counts(Strict):
    generated_by: str
    records: list[Pinned]
    audits: dict[str, dict[str, int]]
    census: Census


def pinned(path: pathlib.Path) -> Pinned:
    return Pinned(
        path=path.relative_to(appendix.ROOT).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def derive() -> Counts:
    rendered = appendix.load()
    output = str(appendix.at(json.loads(CENSUS.read_text()), "/steps/results.verify/output"))
    return Counts(
        generated_by="scripts/derive_command_counts.py",
        records=[pinned(appendix.AUDIT / item.audit.record) for item in rendered],
        audits={item.audit.id: item.values for item in rendered},
        census=Census(
            record=pinned(CENSUS),
            hashes_by_resealed_file={path: int(n) for path, n in RESEALED.findall(output)},
        ),
    )


def main() -> None:
    counts = derive()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(counts.model_dump(), indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(appendix.ROOT)}")
    for name, values in counts.audits.items():
        print(f"  {name:14} {values}")
    print(f"  {'census':14} {counts.census.hashes_by_resealed_file}")


if __name__ == "__main__":
    main()
