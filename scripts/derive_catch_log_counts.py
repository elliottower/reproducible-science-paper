"""Write the catch-log counts the generated appendix prints and no addressable artifact held.

The appendix prints, for the cross-design audit, its findings by review round and by group of
defect class. Both are counts over a JSONL catch log, which a JSON Pointer cannot address, so they
are derived into an artifact here and the manifest points at that. It also prints how many studies
the appendix audits: the audits it renders, plus the ones written by hand that it counts as in
progress (`build_audit_appendix.IN_PROGRESS`).

The audits are loaded by `build_audit_appendix.load`, the rows counted are `Rendered.toolkit`, and
the class groups are `build_audit_appendix.CLASS_GROUPS`: the lists the appendix tables are
rendered from, so a count here cannot drift from the count printed.

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        python scripts/derive_catch_log_counts.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from collections import Counter

from pydantic import BaseModel, ConfigDict

import build_audit_appendix as appendix

OUT = appendix.ROOT / "paper" / "artifacts" / "catch_log_counts.json"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pinned(Strict):
    path: str
    sha256: str


class AuditCounts(Strict):
    catch_log: Pinned
    findings: int
    by_round: dict[str, int] | None
    by_class_group: dict[str, int]


class Studies(Strict):
    rendered: int
    in_progress: int
    total: int


class Counts(Strict):
    generated_by: str
    rule: str
    audit_files: list[Pinned]
    audits: dict[str, AuditCounts]
    studies: Studies


def pinned(path: pathlib.Path) -> Pinned:
    return Pinned(
        path=path.relative_to(appendix.ROOT).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def by_round(item: appendix.Rendered) -> dict[str, int] | None:
    rounds = item.audit.rounds
    if rounds is None:
        return None
    held = Counter(row[rounds.field] for row in item.toolkit)
    return {key: held[key] for key in rounds.labels}


def by_class_group(item: appendix.Rendered) -> dict[str, int]:
    classes = Counter(row["class"] for row in item.toolkit)
    grouped = {shown: sum(classes.pop(c, 0) for c in members) for shown, members in appendix.CLASS_GROUPS}
    grouped[appendix.OTHER_CLASSES] = sum(classes.values())
    return grouped


def derive() -> Counts:
    rendered = appendix.load()
    return Counts(
        generated_by="scripts/derive_catch_log_counts.py",
        rule="a finding is a catch-log row whose id the audit file does not list under excluded_ids",
        audit_files=[pinned(path) for path in sorted((appendix.AUDIT / "audits").glob("*.yaml"))],
        audits={
            item.audit.id: AuditCounts(
                catch_log=pinned(appendix.AUDIT / item.audit.catch_log),
                findings=len(item.toolkit),
                by_round=by_round(item),
                by_class_group=by_class_group(item),
            )
            for item in rendered
        },
        studies=Studies(rendered=len(rendered), in_progress=appendix.IN_PROGRESS,
                        total=len(rendered) + appendix.IN_PROGRESS),
    )


def main() -> None:
    counts = derive()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(counts.model_dump(), indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(appendix.ROOT)}")
    for name, audit in counts.audits.items():
        print(f"  {name:14} rounds {audit.by_round}  classes {audit.by_class_group}")


if __name__ == "__main__":
    main()
