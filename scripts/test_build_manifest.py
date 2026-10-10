"""What the manifest must notice.

Each tamper test copies the manifest and every file it pins into a fresh directory, changes one
file, and requires the report to change. A check that cannot fail is not a check.

    uv run --no-project --with pytest==8.3.3 --with pyyaml==6.0.2 --with pydantic==2.9.2 \\
        --with reproducible-science==0.5.2 python -m pytest scripts
"""

from __future__ import annotations

import json
import pathlib
import shutil

import yaml
from repro import load, verify
from repro.models import Outcome, Validity

import build_manifest as m


def declared() -> dict:
    return yaml.safe_load(m.OUT.read_text())


def paths() -> dict[str, str]:
    return {a["id"]: a["path"] for a in declared()["artifacts"]}


def tree(tmp_path: pathlib.Path) -> pathlib.Path:
    # A fresh directory per verification. `citations.verify.extract` caches on the path, so a
    # second run against a file edited in between reads the text the first run extracted.
    root = tmp_path / "repo"
    for relative in [m.OUT.name, *paths().values()]:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(m.ROOT / relative, root / relative)
    return root


def report_for(root: pathlib.Path):
    return verify(load(root / m.OUT.name))


def mismatched(report, kind: str) -> list[str]:
    return [
        d.claim_id
        for c in report.claims
        for d in c.decisions
        if d.kind == kind and d.outcome is Outcome.MISMATCH
    ]


def broken(report) -> list[str]:
    return [a.artifact_id for a in report.artifacts if a.validity is Validity.BROKEN_PIN]


def test_every_declared_sentence_resolves_in_the_rendering_it_names():
    rendered = {
        name: " ".join((m.ROOT / paths()[name]).read_text().split()).lower()
        for name in ("manuscript-text", "appendix-text")
    }
    missing = [c.id for c in m.CLAIMS if c.sentence.lower() not in rendered[c.stated_in]]
    assert missing == []


def test_the_manifest_on_disk_declares_every_claim_the_script_lists():
    assert [c["id"] for c in declared()["claims"]] == [c.id for c in m.CLAIMS]


def test_the_manifest_verifies_against_the_files_it_pins(tmp_path):
    report = report_for(tree(tmp_path))
    outcomes = [d.outcome for c in report.claims for d in c.decisions]
    assert len(outcomes) == 2 * len(m.CLAIMS)
    assert set(outcomes) == {Outcome.VERIFIED}
    assert {a.validity for a in report.artifacts} == {Validity.AUTHORITATIVE}


def test_an_edited_manuscript_breaks_its_pin(tmp_path):
    root = tree(tmp_path)
    source = root / paths()["manuscript"]
    source.write_text(source.read_text().replace("raised 45 comments", "raised 46 comments"))
    assert broken(report_for(root)) == ["manuscript"]


def test_a_number_changed_in_the_rendering_is_reported_absent(tmp_path):
    root = tree(tmp_path)
    rendered = root / paths()["manuscript-text"]
    rendered.write_text(rendered.read_text().replace("raised 45 comments", "raised 46 comments"))
    assert mismatched(report_for(root), "quote") == ["cross-design-review-comments"]


def test_a_changed_count_is_reported_as_a_disagreement(tmp_path):
    root = tree(tmp_path)
    counts = root / paths()["audit-counts"]
    document = json.loads(counts.read_text())
    document["audits"]["cross_design"]["findings"] = 30
    counts.write_text(json.dumps(document, indent=2) + "\n")
    report = report_for(root)
    assert broken(report) == ["audit-counts"]
    assert mismatched(report, "metric") == [
        "cross-design-findings",
        "findings-row-cross-design",
        "all-findings-cross-design",
    ]


def test_a_regenerated_audit_record_breaks_its_pin(tmp_path):
    root = tree(tmp_path)
    record = root / paths()["audit-record-knockout"]
    document = json.loads(record.read_text())
    document["generated"] = "a later run"
    record.write_text(json.dumps(document, indent=2) + "\n")
    assert broken(report_for(root)) == ["audit-record-knockout"]
