"""Write the counts Appendix K prints from the audit of the literature census.

`run_audit.py` records each command's output as text, so the quotations a command found are
lines of that text and not addressable by a JSON Pointer. This reads the recorded outputs and
writes the counts. Three further counts are read from the checkout the audit ran over, at the
commit the record pins: the dated lines of the plan's log, the access records of the ledger by
level, and the process counts the study itself bound to its runs.

No quotation text is read or written: only the summary lines of each command.

    uv run --no-project --with pydantic==2.9.2 python scripts/derive_census_counts.py
"""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import re
import subprocess

from pydantic import BaseModel, ConfigDict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECORD = ROOT / "paper" / "audit" / "census_audit.json"
OUT = ROOT / "paper" / "artifacts" / "census_counts.json"
CHECKOUT = pathlib.Path.home() / ".cache" / "repo-audit-census" / "checkout"

PLAN = "experiments/02_claims_meta/PREREG.md"
LEDGER = ".results/ledger.jsonl"
BOUND = "experiments/02_claims_meta/outputs/process_counts/bound_claims_2026-10-08_with_queue_papers.json"

QUOTATION_STEPS = {
    "extraction_search": "citations.verify.extraction_search",
    "extraction_chase1": "citations.verify.extraction_chase1",
    "extraction_chase2": "citations.verify.extraction_chase2",
    "extraction_chase3": "citations.verify.extraction_chase3",
    "dataset_coding": "citations.verify.dataset_coding",
    "repository": "citations.verify.repository",
}
EXTRACTION = ("extraction_search", "extraction_chase1", "extraction_chase2", "extraction_chase3")

COUNT = r"^\s*{label}\s+([\d,]+)\b"
QUOTES = re.compile(r"^([\d,]+) quotes\s*$", re.MULTILINE)
LOG_LINE = re.compile(r"^\d{4}-\d{2}-\d{2}  ", re.MULTILINE)
FILE_OK = re.compile(r"^  ok ", re.MULTILINE)
FILE_RESEALED = re.compile(r"^  RESEALED ", re.MULTILINE)


class CensusCountsError(Exception):
    """The record or the checkout does not have the shape this reads."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Pinned(Strict):
    path: str
    sha256: str


class Quotations(Strict):
    exit: int
    quotes: int
    found: int
    not_found: int
    unchecked: int


class Counts(Strict):
    generated_by: str
    record: Pinned
    commit: str
    files_read_from_the_checkout: list[Pinned]
    quotations: dict[str, Quotations]
    extraction_quotations: int
    extraction_quotations_found: int
    quotations_all: int
    claim_files_extraction: int
    claim_files_dataset_coding: int
    claim_files_repository: int
    claim_files_all: int
    ledger_events: int
    ledger_events_by_kind: dict[str, int]
    runs: int
    recorded_files_matching: int
    recorded_files_resealed: int
    plan_log_lines: int
    access_records: int
    access_records_by_level: dict[str, int]
    manifest_assertions: int
    exits: dict[str, int]
    bound_by_the_study: dict[str, int]
    bound_by_the_study_claim_seq: dict[str, int]


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(text: str) -> int:
    return int(text.replace(",", ""))


def labelled(output: str, label: str) -> int:
    """The count on a summary line such as `  found   12,601`; a missing line is zero."""
    match = re.search(COUNT.format(label=re.escape(label)), output, re.MULTILINE)
    return number(match.group(1)) if match else 0


def quotations(step: dict) -> Quotations:
    output = step["output"]
    if not (total := QUOTES.search(output)):
        raise CensusCountsError(f"no quotation total in the output of: {step['command']}")
    return Quotations(
        exit=step["exit"],
        quotes=number(total.group(1)),
        found=labelled(output, "found"),
        not_found=labelled(output, "not found"),
        unchecked=labelled(output, "unchecked"),
    )


def main() -> None:
    record = json.loads(RECORD.read_text())
    commit = record["pin"]["commit"]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=CHECKOUT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != commit:
        raise CensusCountsError(f"the checkout is at {head}, the record pins {commit}")

    steps = record["steps"]
    declared = record["declared"]
    by_folder = {name: quotations(steps[step]) for name, step in QUOTATION_STEPS.items()}

    events = [
        json.loads(line) for line in (CHECKOUT / LEDGER).read_text().splitlines() if line.strip()
    ]
    if len(events) != declared["ledger_events"]:
        raise CensusCountsError("the ledger in the checkout is not the one the record counted")
    kinds = collections.Counter(event["event"] for event in events)
    levels = collections.Counter(event["level"] for event in events if event["event"] == "access")

    bound = json.loads((CHECKOUT / BOUND).read_text())["claims"]
    results_output = steps["results.verify"]["output"]

    counts = Counts(
        generated_by="scripts/derive_census_counts.py",
        record=Pinned(path=str(RECORD.relative_to(ROOT)), sha256=sha256(RECORD)),
        commit=commit,
        files_read_from_the_checkout=[
            Pinned(path=rel, sha256=sha256(CHECKOUT / rel)) for rel in (PLAN, LEDGER, BOUND)
        ],
        quotations=by_folder,
        extraction_quotations=sum(by_folder[name].quotes for name in EXTRACTION),
        extraction_quotations_found=sum(by_folder[name].found for name in EXTRACTION),
        quotations_all=sum(folder.quotes for folder in by_folder.values()),
        claim_files_extraction=declared["extraction_claim_files"],
        claim_files_dataset_coding=declared["dataset_coding_claim_files"],
        claim_files_repository=declared["claim_records"],
        claim_files_all=declared["extraction_claim_files"]
        + declared["dataset_coding_claim_files"]
        + declared["claim_records"],
        ledger_events=declared["ledger_events"],
        ledger_events_by_kind=dict(sorted(kinds.items())),
        runs=declared["runs"],
        recorded_files_matching=len(FILE_OK.findall(results_output)),
        recorded_files_resealed=len(FILE_RESEALED.findall(results_output)),
        plan_log_lines=len(LOG_LINE.findall((CHECKOUT / PLAN).read_text())),
        access_records=sum(levels.values()),
        access_records_by_level=dict(sorted(levels.items())),
        manifest_assertions=declared["manifest_assertions"],
        exits={name: step["exit"] for name, step in sorted(steps.items())},
        bound_by_the_study={row["count"]: row["value"] for row in bound},
        bound_by_the_study_claim_seq={row["count"]: row["claim_seq"] for row in bound},
    )
    OUT.write_text(json.dumps(counts.model_dump(), indent=2) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
