"""Write the bibliography counts the manuscript prints from the audit of the knockout repository.

`repro audit` records each command's output as text. The counts of bibliography entries that
agree and differ are lines of that text, and which fields differ is stated per entry, so neither
is addressable by a JSON Pointer. This reads the `citations audit` section of the recorded log
and writes the counts Table 6 prints.

An entry is counted once per kind of difference, however many of its fields differ: an entry
with three surnames out of order is one entry whose author list differs.

    uv run --no-project --with pydantic==2.9.2 python scripts/derive_bibliography_audit.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re

from pydantic import BaseModel, ConfigDict

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "paper" / "audit" / "knockout_repro_audit.log"
RECORD = ROOT / "paper" / "audit" / "knockout_repro_audit.json"
OUT = ROOT / "paper" / "artifacts" / "knockout_bibliography_audit.json"

SECTION = re.compile(r"^\$ citations audit .*?(?=^\$ |\Z)", re.MULTILINE | re.DOTALL)
ENTRY = re.compile(r"^  mismatch +(\S+)", re.MULTILINE)
COUNT = r"^\s*{label}\s+(\d+)\b"


class BibliographyAuditError(Exception):
    """The recorded log does not have the shape this reads."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pinned(Strict):
    path: str
    sha256: str


class Counts(Strict):
    generated_by: str
    log: Pinned
    record: Pinned
    commit: str
    entries: int
    checked: int
    agree: int
    differ: int
    not_found: int
    differ_in_year: int
    differ_in_author_list: int
    differ_in_title: int
    entries_that_differ: dict[str, list[str]]


def pinned(path: pathlib.Path) -> Pinned:
    return Pinned(
        path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )


def count(section: str, label: str) -> int:
    found = re.search(COUNT.format(label=re.escape(label)), section, re.MULTILINE)
    if found is None:
        raise BibliographyAuditError(f"{LOG.name}: no `{label}` count in the citations audit section")
    return int(found.group(1))


def kinds(lines: list[str]) -> list[str]:
    """Which kinds of difference one entry's indented lines report."""
    found = []
    for kind, starts in (("year", ("year:",)), ("author_list", ("author",)), ("title", ("title:",))):
        if any(line.strip().startswith(starts) for line in lines):
            found.append(kind)
    return found


def derive() -> Counts:
    sections = SECTION.findall(LOG.read_text())
    if len(sections) != 1:
        raise BibliographyAuditError(f"{LOG.name}: {len(sections)} citations audit sections, expected one")
    section = sections[0]

    differing: dict[str, list[str]] = {}
    matches = list(ENTRY.finditer(section))
    for at, match in enumerate(matches):
        end = matches[at + 1].start() if at + 1 < len(matches) else section.index("\n\n", match.end())
        differing[match.group(1)] = kinds(section[match.end() : end].splitlines()[1:])

    counts = Counts(
        generated_by="scripts/derive_bibliography_audit.py",
        log=pinned(LOG),
        record=pinned(RECORD),
        commit=json.loads(RECORD.read_text())["pin"]["commit"],
        entries=int(re.search(r"^(\d+) entries$", section, re.MULTILINE).group(1)),
        checked=count(section, "checked"),
        agree=count(section, "agree"),
        differ=count(section, "disagree"),
        not_found=count(section, "not found"),
        differ_in_year=sum("year" in found for found in differing.values()),
        differ_in_author_list=sum("author_list" in found for found in differing.values()),
        differ_in_title=sum("title" in found for found in differing.values()),
        entries_that_differ=differing,
    )
    if len(differing) != counts.differ:
        raise BibliographyAuditError(
            f"{LOG.name}: {len(differing)} entries listed as differing, the summary says {counts.differ}"
        )
    if counts.agree + counts.differ != counts.checked:
        raise BibliographyAuditError(f"{LOG.name}: agree and disagree do not sum to checked")
    return counts


def main() -> None:
    counts = derive()
    OUT.write_text(json.dumps(counts.model_dump(), indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    print(f"  {counts.checked} of {counts.entries} checked: {counts.agree} agree, {counts.differ} differ "
          f"({counts.differ_in_year} year, {counts.differ_in_author_list} author list, "
          f"{counts.differ_in_title} title); {counts.not_found} not found")


if __name__ == "__main__":
    main()
