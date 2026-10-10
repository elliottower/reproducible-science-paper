"""Write the finding counts the manuscript prints and no addressable artifact held.

The catch logs under `paper/audit/catch_logs/` are JSONL, which a JSON Pointer cannot address,
and a count of findings is derived: the rows of a log whose id the audit file does not list under
`excluded_ids`. The manuscript prints those counts in Section 5.2 and in the generated appendix,
so they are derived into an artifact here and the manifest points at that.

The audits are loaded by `build_audit_appendix.load`, and the rows counted are
`Rendered.toolkit`, the same list the appendix tables are rendered from. The exclusion rule is
stated once, there.

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        python scripts/derive_audit_counts.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from collections import Counter

from pydantic import BaseModel, ConfigDict

import build_audit_appendix as appendix

OUT = appendix.ROOT / "paper" / "artifacts" / "audit_counts.json"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pinned(Strict):
    path: str
    sha256: str


class AuditCounts(Strict):
    title: str
    catch_log: Pinned
    catch_log_rows: int
    excluded: int
    findings: int
    by_severity: dict[str, int]


class Total(Strict):
    audits: int
    findings: int
    by_severity: dict[str, int]


class Counts(Strict):
    generated_by: str
    rule: str
    severity_printed_as: dict[str, str]
    audit_files: list[Pinned]
    audits: dict[str, AuditCounts]
    total: Total


def pinned(path: pathlib.Path) -> Pinned:
    return Pinned(
        path=path.relative_to(appendix.ROOT).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def by_severity(rows: list[dict]) -> dict[str, int]:
    held = Counter(row["severity"] for row in rows)
    return {severity: held[severity] for severity, _ in appendix.SEVERITIES}


def derive() -> Counts:
    rendered = appendix.load()
    audits = {
        item.audit.id: AuditCounts(
            title=item.audit.title,
            catch_log=pinned(appendix.AUDIT / item.audit.catch_log),
            catch_log_rows=len(item.catches),
            excluded=len(item.catches) - len(item.toolkit),
            findings=len(item.toolkit),
            by_severity=by_severity(item.toolkit),
        )
        for item in rendered
    }
    every = [row for item in rendered for row in item.toolkit]
    return Counts(
        generated_by="scripts/derive_audit_counts.py",
        rule="a finding is a catch-log row whose id the audit file does not list under excluded_ids",
        severity_printed_as=dict(appendix.SEVERITIES),
        audit_files=[pinned(path) for path in sorted((appendix.AUDIT / "audits").glob("*.yaml"))],
        audits=audits,
        total=Total(audits=len(rendered), findings=len(every), by_severity=by_severity(every)),
    )


def main() -> None:
    counts = derive()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(counts.model_dump(), indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(appendix.ROOT)}")
    for name, audit in counts.audits.items():
        print(f"  {name:14} {audit.findings} findings of {audit.catch_log_rows} rows")
    print(f"  {'total':14} {counts.total.findings} findings")


if __name__ == "__main__":
    main()
