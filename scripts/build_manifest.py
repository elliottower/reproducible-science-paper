"""Bind this paper's own reported numbers to the artifacts that produced them.

The manuscript argues that a printed value should name the address it came from. This builds the
manifest that does it for the manuscript itself, `repro.yaml` at the repository root, where
`repro verify` finds it with no argument. Each claim carries two assertions -- that the manuscript
states the sentence, and that a pinned artifact holds the value at a declared pointer.

The manuscript is named once, by the Makefile's `PAPER`, and passed in. `make manifest` runs this
after the two scripts whose output it pins:

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        --with reproducible-science==0.5.2 \
        python scripts/build_manifest.py --paper <manuscript stem>

Two kinds of number were not assertable until they were derived into an artifact. The corpus
artifact records each reader's own count and every reader's outcome per quotation, but not the
unions the manuscript quotes; `scripts/derive_extractor_unions.py` computes them. The catch logs
are JSONL, which a pointer cannot address, and a count of findings is the rows an audit file does
not exclude; `scripts/derive_audit_counts.py` computes those. The bibliography counts of
Section 5.2 are lines of a recorded command's output; `scripts/derive_bibliography_audit.py`
reads them out.

The generated appendix is a second LaTeX file the manuscript `\\input`s. `detex.py` drops the
argument of `\\input`, so the appendix is rendered and pinned as its own pair of artifacts, and
the claims about its tables resolve against that rendering.

Every audit file, audit record and catch log is pinned, whether or not a claim points into it,
so a regenerated record breaks a pin. Four regeneration records name the commands that produce
the two renderings, the derived counts and the appendix, for `repro reproduce`.
"""

from __future__ import annotations

import argparse
import pathlib

import yaml
from pydantic import BaseModel, ConfigDict
from repro import Digest
from repro.provenance import of_tree

import build_audit_appendix as appendix
from detex import plain

ROOT = appendix.ROOT
OUT = ROOT / "repro.yaml"
SCRIPTS = ROOT / "scripts"
ART = ROOT / "paper" / "artifacts"

# What a regeneration record runs for a script that imports beyond the standard library. The
# sandbox holds only the declared inputs, so the interpreter's packages are named here.
UV = ["uv", "run", "--no-project", "--with", "pyyaml==6.0.2", "--with", "pydantic==2.9.2", "python"]


class Bound(BaseModel):
    """One printed number: the sentence that states it and the address that holds it."""

    model_config = ConfigDict(extra="forbid")

    id: str
    where: str
    sentence: str
    printed: str
    artifact: str
    pointer: str
    stated_in: str = "manuscript-text"


def bound(*rows: tuple[str, ...], stated_in: str = "manuscript-text") -> list[Bound]:
    names = ("id", "where", "sentence", "printed", "artifact", "pointer")
    return [Bound(**dict(zip(names, row, strict=True)), stated_in=stated_in) for row in rows]


TOTAL_ROW = "total | | 8 | 16 | 18 | 7 | 49"

# (id, where, sentence as the rendering prints it, printed value, artifact, pointer)
CLAIMS = [
    *bound(
        ("corpus-quotations", "Appendix A", "under audit carry 2,364",
         "2364", "corpus", "/corpus/quotations"),
        ("unresolved-quotations", "Appendix A", "113 quotations did not resolve",
         "113", "corpus", "/per_reader/poppler-layout/outcomes/not found"),
        ("poppler-reading-order", "Table 6", "poppler, reading order | 2,314",
         "2314", "corpus", "/per_reader/poppler-flow/resolved"),
        ("poppler-layout", "Table 6", "poppler, layout | 2,250",
         "2250", "corpus", "/per_reader/poppler-layout/resolved"),
        ("pure-python-reader", "Table 6", "pure-Python reader | 2,229",
         "2229", "corpus", "/per_reader/pypdf/resolved"),
        ("rendering-engine-binding", "Table 6", "rendering-engine binding | 2,092",
         "2092", "corpus", "/per_reader/pdfium/resolved"),
        ("structural-extractor", "Table 6", "structural extractor | 1,973",
         "1973", "corpus", "/per_reader/pdf-extract/resolved"),
        ("low-level-parser", "Table 6", "low-level parser | 1,716",
         "1716", "corpus", "/per_reader/lopdf/resolved"),
        ("poppler-union", "Table 6", "both poppler modes | 2,360",
         "2360", "unions", "/resolved_by_either_poppler_mode"),
        ("any-reader-union", "Table 6", "all six | 2,362",
         "2362", "unions", "/resolved_by_at_least_one_reader"),
        ("repo-tracked-files", "Section 5.2", "The clone carries 1,267 tracked files",
         "1267", "audit-record-knockout", "/declared/tracked_files"),
        ("repo-ledger-events", "Section 5.2", "a ledger of 153 events",
         "153", "audit-record-knockout", "/declared/ledger_events"),
        ("repo-claims-bound", "Section 5.2", "binding 131 manuscript claims",
         "131", "audit-record-knockout", "/declared/manuscript_claims_bound"),
        ("repo-quotations", "Section 5.2", "holding 18 quotations",
         "18", "audit-record-knockout", "/declared/quotations"),
        ("bibliography-checked", "Section 5.2, Table 9", "28 of 32 entries checked",
         "28", "bibliography-audit", "/checked"),
        ("bibliography-entries", "Section 5.2, Table 9", "28 of 32 entries checked",
         "32", "bibliography-audit", "/entries"),
        ("bibliography-differ", "Section 5.2, Table 9", "6 differ from their registry record",
         "6", "bibliography-audit", "/differ"),
        ("codecheck-certificates", "Section 5.2", "Of 133 certified",
         "133", "codecheck-counts", "/certificates_in_register"),
        ("codecheck-table-files", "Section 5.2", "6 leave a file holding one of",
         "6", "codecheck-counts", "/certificates_with_a_linked_table_file"),
        ("codecheck-bound", "Section 5.2", "(338 of 713)",
         "338", "codecheck-counts", "/numbers_bound"),
        ("codecheck-printed", "Section 5.2", "(338 of 713)",
         "713", "codecheck-counts", "/numbers_printed"),
        ("codecheck-same", "Section 5.2", "326 match the certified file",
         "326", "codecheck-agreement", "/all/same_number"),
        ("codecheck-differ", "Section 5.2", "and 12 differ",
         "12", "codecheck-agreement", "/all/differ"),
        ("corebench-second-run", "Section 4.3", "byte-identical record for all 45 capsules",
         "45", "corebench-second-run", "/identical"),
        ("conformance-fixtures", "Appendix A", "The suite holds 25 fixtures",
         "25", "conformance", "/fixtures"),
        ("conformance-table-cell", "Appendix A", "five addressing a table cell",
         "5", "conformance", "/by_group/table_cell"),
        ("conformance-value", "Appendix A", "four comparing a value",
         "4", "conformance", "/by_group/value"),
        ("cross-design-review-comments", "Section 5.2",
         "four rounds of journal review raised 45 comments",
         "45", "review-counts-cross-design", "/points_total"),
        ("cross-design-findings", "Section 5.2", "Reproducible Science reported 31 findings",
         "31", "audit-counts", "/audits/cross_design/findings"),
    ),
    *bound(
        ("findings-total", "Appendix E, Table 14", TOTAL_ROW,
         "49", "audit-counts", "/total/findings"),
        ("findings-total-claim", "Appendix E, Table 14", TOTAL_ROW,
         "8", "audit-counts", "/total/by_severity/claim"),
        ("findings-total-source", "Appendix E, Table 14", TOTAL_ROW,
         "16", "audit-counts", "/total/by_severity/integrity"),
        ("findings-total-record", "Appendix E, Table 14", TOTAL_ROW,
         "18", "audit-counts", "/total/by_severity/record"),
        ("findings-total-cosmetic", "Appendix E, Table 14", TOTAL_ROW,
         "7", "audit-counts", "/total/by_severity/cosmetic"),
        ("findings-row-cross-design", "Appendix E, Table 14",
         "Cross-design evidence discordance | | 5 | 14 | 8 | 4 | 31",
         "31", "audit-counts", "/audits/cross_design/findings"),
        ("findings-row-knockout", "Appendix E, Table 14",
         "Knockout epistasis | | 3 | 2 | 10 | 3 | 18",
         "18", "audit-counts", "/audits/knockout/findings"),
        ("all-findings-cross-design", "Appendix F",
         "All Findings. 31: 5 claim, 14 source, 8 record, 4 cosmetic.",
         "31", "audit-counts", "/audits/cross_design/findings"),
        ("all-findings-knockout", "Appendix G",
         "All Findings. 18: 3 claim, 2 source, 10 record, 3 cosmetic.",
         "18", "audit-counts", "/audits/knockout/findings"),
        stated_in="appendix-text",
    ),
]


def artifact(identifier: str, path: pathlib.Path, media_type: str) -> dict:
    return {
        "id": identifier,
        "path": path.relative_to(ROOT).as_posix(),
        "media_type": media_type,
        "digest": {"algorithm": "sha256", "value": Digest.of_file(path).value},
    }


def audit_artifacts() -> list[dict]:
    """Every audit file, and the record, catch log and review counts each one names."""
    found = []
    for path in sorted((appendix.AUDIT / "audits").glob("*.yaml")):
        audit = appendix.Audit.model_validate(yaml.safe_load(path.read_text()))
        name = audit.id.replace("_", "-")
        found.append(artifact(f"audit-file-{name}", path, "application/yaml"))
        found.append(artifact(f"audit-record-{name}", appendix.AUDIT / audit.record, "application/json"))
        found.append(artifact(f"catch-log-{name}", appendix.AUDIT / audit.catch_log, "application/x-ndjson"))
        if audit.review_counts:
            found.append(
                artifact(f"review-counts-{name}", appendix.AUDIT / audit.review_counts, "application/json")
            )
    return found


def regeneration(identifier: str, command: list[str], inputs: list[dict], output: dict) -> dict:
    # Digests are copied rather than shared, so `safe_dump` writes each out instead of an anchor.
    return {
        "id": identifier,
        "command": command,
        "inputs": [{"artifact": a["id"], "digest": dict(a["digest"])} for a in inputs],
        "output": {"artifact": output["id"], "digest": dict(output["digest"])},
    }


def render(source: pathlib.Path) -> pathlib.Path:
    target = source.with_suffix(".txt")
    target.write_text(plain(source.read_text()))
    return target


def build(paper: pathlib.Path) -> dict:
    audits = audit_artifacts()
    records = [a for a in audits if not a["id"].startswith("review-counts-")]
    artifacts = [
        artifact("manuscript", paper, "application/x-tex"),
        artifact("manuscript-text", render(paper), "text/plain"),
        artifact("appendix", appendix.OUT, "application/x-tex"),
        artifact("appendix-text", render(appendix.OUT), "text/plain"),
        artifact("detex", SCRIPTS / "detex.py", "text/x-python"),
        artifact("appendix-generator", SCRIPTS / "build_audit_appendix.py", "text/x-python"),
        artifact("counts-deriver", SCRIPTS / "derive_audit_counts.py", "text/x-python"),
        artifact("corpus", ART / "real_corpus_by_reader.json", "application/json"),
        artifact("unions", ART / "extractor_unions.json", "application/json"),
        artifact("conformance", ART / "conformance_inventory.json", "application/json"),
        artifact("audit-counts", ART / "audit_counts.json", "application/json"),
        artifact("bibliography-audit", ART / "knockout_bibliography_audit.json", "application/json"),
        artifact("bibliography-audit-log", appendix.AUDIT / "knockout_repro_audit.log", "text/plain"),
        artifact("codecheck-indices", ART / "codecheck_indices.json", "application/json"),
        artifact("codecheck-eligibility", ART / "codecheck_eligibility_summary.json",
                 "application/json"),
        artifact("codecheck-counts", ART / "codecheck_counts.json", "application/json"),
        artifact("codecheck-agreement", ART / "codecheck_agreement_summary.json",
                 "application/json"),
        artifact("corebench-second-run", ART / "corebench_rerun_confirm_comparison.json",
                 "application/json"),
        *audits,
    ]
    by_id = {a["id"]: a for a in artifacts}

    claims = [
        # Not a registered prediction. Each is an exhaustive count over a declared corpus,
        # reporting every result produced; no outcome was chosen from alternatives, so there
        # was nothing for a plan to fix in advance.
        {
            "id": c.id,
            "registration": "not_applicable",
            "registration_note": "exhaustive deterministic count over pinned inputs",
            "where": c.where,
            "text": f"The manuscript states {c.printed} for {c.id}.",
            "evidence": [
                {"kind": "quote", "artifact": c.stated_in, "text": c.sentence},
                {"kind": "metric", "artifact": c.artifact, "name": c.id,
                 "reported": c.printed, "pointer": c.pointer},
            ],
        }
        for c in CLAIMS
    ]

    def detex(text: str, source: str) -> dict:
        command = ["python3", by_id["detex"]["path"], by_id[source]["path"], by_id[text]["path"]]
        return regeneration(text, command, [by_id[source], by_id["detex"]], by_id[text])

    generator = by_id["appendix-generator"]
    regenerations = [
        detex("manuscript-text", "manuscript"),
        detex("appendix-text", "appendix"),
        regeneration(
            "audit-counts",
            [*UV, by_id["counts-deriver"]["path"]],
            [by_id["counts-deriver"], generator, *records],
            by_id["audit-counts"],
        ),
        regeneration("appendix", [*UV, generator["path"]], [generator, *audits], by_id["appendix"]),
    ]

    return {
        "schema_version": "repro/1",
        "project": "machine-checkable claims (this paper, checked against its own artifacts)",
        "provenance": of_tree(ROOT, generated_by="scripts/build_manifest.py").model_dump(),
        "artifacts": artifacts,
        "claims": claims,
        "regenerations": regenerations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write repro.yaml for one manuscript")
    parser.add_argument("--paper", required=True, help="manuscript stem under paper/, without .tex")
    args = parser.parse_args()
    manifest = build(ROOT / "paper" / f"{args.paper}.tex")
    OUT.write_text(yaml.safe_dump(manifest, sort_keys=False, width=110))
    assertions = sum(len(c["evidence"]) for c in manifest["claims"])
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(manifest['claims'])} claims, "
          f"{assertions} assertions, {len(manifest['artifacts'])} artifacts")


if __name__ == "__main__":
    main()
