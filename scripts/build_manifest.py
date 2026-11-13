"""Bind this paper's own reported numbers to the artifacts that produced them.

The manuscript argues that a printed value should name the address it came from. This builds the
manifest that does it for the manuscript itself, `repro.yaml` at the repository root, where
`repro verify` finds it with no argument. Each claim carries two assertions -- that the manuscript
states the sentence, and that a pinned artifact holds the value at a declared pointer.

The manuscript is named once, by the Makefile's `PAPER`, and passed in. `make manifest` runs this
after the two scripts whose output it pins:

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        --with reproducible-science==0.6.0 \
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
the claims about its tables resolve against that rendering. Every other file the manuscript
`\\input`s, at any depth, is rendered and pinned the same way, so `repro numbers` can read the
whole PDF and not the body alone.

A printed value that is a sum, a least or a greatest value of stored ones is bound with an
`aggregate` over every address, and a percentage printed from a stored fraction with
`conversion: percent`, so no derived number is transcribed. Numbers that are not this paper's
results -- another work's figures, prose counts, examples, labels -- are listed under
`set_aside` with the reason, and another work's figure names the record pinning its quotation.
`set_aside` and `conversion` need `reproducible-science` 0.5.6 or later to load the manifest, and
`origin` 0.6.0 or later.

The certified-reproductions and failure-cases appendices are bound as the
reproducible-science-codecheck repository's own manifest binds them, to its result files copied
byte for byte into `paper/artifacts/` under a `codecheck_` prefix. Counts the appendices read out
of recorded command output and catch logs, and the spread between readers in Table 6, are
written by `derive_command_counts.py`, `derive_catch_log_counts.py` and
`derive_extractor_spread.py`, each declared below with the command that regenerates it.

Every audit file, audit record and catch log is pinned, whether or not a claim points into it,
so a regenerated record breaks a pin. Four regeneration records name the commands that produce
the two renderings, the derived counts and the appendix, for `repro reproduce`.
"""

from __future__ import annotations

import argparse
import pathlib
import re

import yaml
from pydantic import BaseModel, ConfigDict
from repro import Digest
from repro.provenance import of_tree

import build_audit_appendix as appendix
from detex import COMMENT, plain

ROOT = appendix.ROOT
OUT = ROOT / "repro.yaml"
#: The two-assertion manifest Section 3's worked example runs `repro verify` on. Its paths are
#: relative to its own directory, as `repro` reads them.
EXAMPLE = ROOT / "paper" / "worked_example" / "repro.yaml"
EXAMPLE_CLAIM = "conformance-fixtures"
SCRIPTS = ROOT / "scripts"
PAPER = ROOT / "paper"
ART = PAPER / "artifacts"

#: `\input{name}` in a LaTeX source. LaTeX resolves the name against the directory it compiles
#: in, `paper/`, whichever file holds the command.
INPUT = re.compile(r"\\input\{([^}]+)\}")
#: The version suffix of an appendix file, `_v15zu`, left out of the artifact id so the id
#: stays the same when the manuscript moves to a later version of the appendix.
VERSION = re.compile(r"_v\d+[a-z]*$")

#: Certificates with at least one linked table, in register order. Their binding summaries are
#: copied byte for byte from the reproducible-science-codecheck repository.
LINKED_CERTIFICATES = ("2020-008", "2020-011", "2020-025", "2022-001", "2024-020", "2025-018")

# What a regeneration record runs for a script that imports beyond the standard library. The
# sandbox holds only the declared inputs, so the interpreter's packages are named here.
UV = ["uv", "run", "--no-project", "--with", "pyyaml==6.0.2", "--with", "pydantic==2.9.2", "python"]
#: The same, for a script that imports this module, which imports the toolkit.
UV_TOOLKIT = [*UV[:-1], "--with", "reproducible-science==0.6.0", "python"]


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
    #: `percent` where the artifact stores the fraction the manuscript prints as a percentage.
    conversion: str | None = None
    #: Where the printed value is a sum, a least or a greatest value over several stored ones:
    #: the statistic, with `pointer` unused and every (artifact, pointer) in `members`.
    statistic: str | None = None
    members: tuple[tuple[str, str], ...] = ()


def bound(
    *rows: tuple[str, ...], stated_in: str = "manuscript-text", conversion: str | None = None
) -> list[Bound]:
    names = ("id", "where", "sentence", "printed", "artifact", "pointer")
    return [
        Bound(**dict(zip(names, row, strict=True)), stated_in=stated_in, conversion=conversion)
        for row in rows
    ]


def over(
    identifier: str,
    where: str,
    sentence: str,
    printed: str,
    artifact: str,
    statistic: str,
    *members: str,
    stated_in: str = "manuscript-text",
) -> Bound:
    """A printed value that is a statistic of several stored values in one artifact."""
    return Bound(id=identifier, where=where, sentence=sentence, printed=printed, artifact=artifact,
                 pointer="", stated_in=stated_in, statistic=statistic,
                 members=tuple((artifact, member) for member in members))


def across(identifier: str, where: str, sentence: str, printed: str, statistic: str,
           members: list[tuple[str, str]], stated_in: str = "manuscript-text") -> Bound:
    """A printed value that is a statistic of stored values held in several artifacts."""
    return Bound(id=identifier, where=where, sentence=sentence, printed=printed, artifact="", pointer="",
                 stated_in=stated_in, statistic=statistic, members=tuple(members))


class Aside(BaseModel):
    """A passage whose numbers are not results of this paper, and why."""

    model_config = ConfigDict(extra="forbid")

    artifact: str
    text: str
    reason: str


def aside(artifact: str, *rows: tuple[str, str]) -> list[Aside]:
    return [Aside(artifact=artifact, text=text, reason=reason) for text, reason in rows]


TOTAL_ROW = "total | | 8 | 16 | 18 | 7 | 49"

TIMED = ("Verifying this paper's 1,062 assertions over 79 artifacts takes 1.28 seconds on a laptop and 0.55 "
         "seconds on a cloud container")
RESOLVED = ("Resolving its 203 quotations against 55 content-addressed sources takes 11.19 and 7.17 seconds "
            "when every source is read, and 1.90 and 0.94 seconds")
SELF_AUDIT = "The body binds 96 claims this way"
COVERAGE = ("Of the 1,020 numbers the PDF prints, appendices included, 533 are checked against the file "
            "they came from and the other 487 are set aside by a rule such as a year or with a stated "
            "reason")
SIX_READERS = ("Six extractors read the same 2,364 passages, quoted from fifteen published papers, out "
               "of the same pinned bytes and returned six different answers, from 2,314 down to 1,716")
RECALL = ("Over 45 capsules the benchmark states 240 values, of which 146 are located in the "
          "capsule's files without running it: a recall of 61%")
CLONE = "131 manuscript claims to 13 runs, and seven claim records"
SOURCES = "quotations: 18 against 7 sources, none checked"
CENSUS_BODY = "The model screened 43,462 abstracts and extracted 14,053 records"
SPANS_BODY = "13,989 match exactly, 27 match in two places, and 37 leave out one word"
THREE_EACH = "three each for prose anchors, two-sided correspondences and artifact availability"
TWO_EACH = "two each for a pointer and a passage"
GROUPS_OF_THREE = ("/by_group/prose_anchor", "/by_group/correspondence", "/by_group/artifact_availability")
GROUPS_OF_TWO = ("/by_group/pointer", "/by_group/passage")
MACHINE = "2 processors, 7,GB of memory"
CONTAINER = "2 processors and 4,096,MB of memory requested"
LOAD = "The laptop's load average over the previous minute was 3.37 when its runs began"
BIG_PROJECT = "the check takes 2.416 seconds and hashing alone takes 2.163"


def strength(row: str, name: str) -> list[Bound]:
    """One row of the CORE-Bench recall table: stated, located, and recall as a percentage."""
    stated, located, recall = (cell.strip().rstrip("%") for cell in row.split("|")[1:])
    base = f"/by_strength/{name}"
    return [
        *bound((f"corebench-{name}-stated", "Table 7", row, stated, "corebench-recall", f"{base}/stated"),
               (f"corebench-{name}-located", "Table 7", row, located, "corebench-recall",
                f"{base}/located")),
        *bound((f"corebench-{name}-recall", "Table 7", row, recall, "corebench-recall", f"{base}/recall"),
               conversion="percent"),
    ]


def reader_seconds(row: str, name: str, pointer: str) -> Bound:
    """The seconds cell of one row of Table 6."""
    return bound((f"reader-seconds-{name}", "Table 6", row, row.rsplit("| ", 1)[1], "reader-timings",
                  pointer))[0]


def timing_row(row: str, verify: int) -> list[Bound]:
    """One row of Table 10: assertions, bytes, and the medians of the two commands.

    `verify` is the index of the `repro verify` check in the timings record; the `sha256sum -c`
    check over the same project is the one after it.
    """
    assertions, size, seconds, hashing = (cell.strip() for cell in row.split("|"))
    name = f"timing-row-{verify}"
    return bound(
        (f"{name}-assertions", "Table 10", row, assertions.replace(",", ""), "check-timings-by-size",
         f"/checks/{verify}/size/assertions"),
        (f"{name}-bytes", "Table 10", row, size.replace(",", ""), "check-timings-by-size",
         f"/checks/{verify}/size/artifact_bytes"),
        (f"{name}-verify", "Table 10", row, seconds, "check-timings-by-size",
         f"/checks/{verify}/median_seconds"),
        (f"{name}-sha256sum", "Table 10", row, hashing, "check-timings-by-size",
         f"/checks/{verify + 1}/median_seconds"),
    )


def paper_timing(row: str, check: str, record: str) -> list[Bound]:
    """One row of the table timing this paper's own records: median, fastest and slowest run."""
    median, fastest, slowest = (cell.strip() for cell in row.split("|")[-3:])
    name = f"timing-paper-{check.replace('_', '-')}-{record.removeprefix('check-timings').strip('-') or 'laptop'}"
    return bound(
        (f"{name}-median", "Appendix D", row, median, record, f"/{check}/median_seconds"),
        (f"{name}-fastest", "Appendix D", row, fastest, record, f"/{check}/min_seconds"),
        (f"{name}-slowest", "Appendix D", row, slowest, record, f"/{check}/max_seconds"),
    )


MANUSCRIPT = [
    *bound(
        ("fixtures-worked-example", "Section 3", "Appendix states that the conformance suite holds 25",
         "25", "conformance", "/fixtures"),
        ("fixtures-example-manifest", "Section 3", "reported: '25'", "25", "conformance", "/fixtures"),
        ("fixtures-example-output", "Section 3", "metric /fixtures = 25", "25", "conformance",
         "/fixtures"),
        ("fixtures-example-report", "Section 3", "conformance_inventory.json holds 25", "25",
         "conformance", "/fixtures"),
        ("verify-timed-assertions", "Section 3", TIMED, "1062", "check-timings", "/repro_verify/assertions"),
        ("verify-timed-artifacts", "Section 3", TIMED, "79", "check-timings", "/repro_verify/artifacts"),
        ("verify-timed-median", "Section 3", TIMED, "1.28", "check-timings",
         "/repro_verify/median_seconds"),
        ("verify-timed-median-container", "Section 3", TIMED, "0.55", "check-timings-container",
         "/repro_verify/median_seconds"),
        ("citations-timed-quotations", "Section 3", RESOLVED, "203", "check-timings",
         "/citations_verify/quotations"),
        ("citations-timed-sources", "Section 3", RESOLVED, "55", "check-timings",
         "/citations_verify/sources"),
        ("citations-timed-median", "Section 3", RESOLVED, "11.19", "check-timings",
         "/citations_verify/median_seconds"),
        ("citations-timed-median-container", "Section 3", RESOLVED, "7.17", "check-timings-container",
         "/citations_verify/median_seconds"),
        ("citations-kept-median", "Section 3", RESOLVED, "1.90", "check-timings",
         "/citations_verify_with_cache/median_seconds"),
        ("citations-kept-median-container", "Section 3", RESOLVED, "0.94", "check-timings-container",
         "/citations_verify_with_cache/median_seconds"),
        ("quotation-audit-papers", "Section 3", "The fifteen papers in the quotation audit", "15",
         "corpus", "/corpus/documents"),
        ("fixtures-evaluation", "Section 4",
         "The conformance suite and the fault injections are in Appendix: 25 fixtures", "25",
         "conformance", "/fixtures"),
        ("self-audit-claims", "Section 4.1", SELF_AUDIT, "96", "body-claims", "/claims_in_body"),
        ("coverage-bound", "Section 4.1", COVERAGE, "533", "number-coverage", "/bound"),
        ("coverage-set-aside", "Section 4.1", COVERAGE, "487", "number-coverage", "/set_aside"),
        ("fixtures-self-audit", "Appendix C", "a stored figure gave nineteen where the suite holds 25",
         "25", "conformance", "/fixtures"),
        ("readers-counted", "Section 4.2", SIX_READERS, "6", "reader-timings", "/readers_counted"),
        ("readers-quotations", "Section 4.2", SIX_READERS, "2364", "corpus", "/corpus/quotations"),
        ("readers-papers", "Section 4.2", SIX_READERS, "15", "corpus", "/corpus/documents"),
        ("readers-most", "Section 4.2", SIX_READERS, "2314", "corpus", "/per_reader/poppler-flow/resolved"),
        ("readers-fewest", "Section 4.2", SIX_READERS, "1716", "corpus", "/per_reader/lopdf/resolved"),
        ("layout-unresolved", "Section 4.2", "Under poppler's layout mode 113 quotations are not found",
         "113", "corpus", "/per_reader/poppler-layout/outcomes/not found"),
        ("layout-accusations", "Section 4.2", "accused the manuscripts 113 times", "113", "corpus",
         "/per_reader/poppler-layout/outcomes/not found"),
        ("corebench-capsules", "Section 4.3", RECALL, "45", "corebench-recall", "/capsules_measured"),
        ("corebench-stated", "Section 4.3", RECALL, "240", "corebench-recall", "/values_stated"),
        ("corebench-located", "Section 4.3", RECALL, "146", "corebench-recall", "/values_located"),
        ("corebench-table-capsules", "Table 7", "Recall over 45 CORE-Bench capsules", "45",
         "corebench-recall", "/capsules_measured"),
        ("corebench-unread-records", "Table 7", "Eight capsules hold a record no reader here opened",
         "8", "corebench-recall", "/capsules_with_an_unread_record"),
        ("corebench-all-stated", "Table 7", "all | 240 | 146 | 61%", "240", "corebench-recall",
         "/values_stated"),
        ("corebench-all-located", "Table 7", "all | 240 | 146 | 61%", "146", "corebench-recall",
         "/values_located"),
    ),
    *bound(
        ("corebench-recall", "Section 4.3", RECALL, "61", "corebench-recall", "/recall"),
        ("corebench-all-recall", "Table 7", "all | 240 | 146 | 61%", "61", "corebench-recall", "/recall"),
        conversion="percent",
    ),
    # Printed as the total, bound as bound plus set aside: a number left unbound breaks the sum.
    over("coverage-numbers", "Section 4.1", COVERAGE, "1020", "number-coverage", "sum", "/bound", "/set_aside"),
    *strength("trivial | 59 | 54 | 92%", "trivial"),
    *strength("weak | 76 | 40 | 53%", "weak"),
    *strength("moderate | 44 | 15 | 34%", "moderate"),
    *strength("strong | 61 | 37 | 61%", "strong"),
    *bound(
        ("repo-registered-plans", "Section 5.2", "1,267 tracked files, three registered plans", "3",
         "audit-record-knockout", "/declared/registered_plans"),
        ("repo-runs", "Section 5.2", CLONE, "13", "audit-record-knockout", "/declared/runs"),
        ("repo-claim-records", "Section 5.2", CLONE, "7", "audit-record-knockout",
         "/declared/claim_records"),
        ("repo-table-plans", "Table 9", "three plans, each unchanged against the digest", "3",
         "audit-record-knockout", "/declared/registered_plans"),
        ("repo-table-ledger-events", "Table 9", "the chain is intact and anchored at 153 events", "153",
         "audit-record-knockout", "/declared/ledger_events"),
        ("repo-table-recorded-files", "Table 9", "8 of 12 recorded files match their digest", "12",
         "audit-record-knockout", "/declared/file_digests_recorded"),
        ("repo-table-claims-cover", "Table 9",
         "what share of the manuscript's numbers the 131 claims cover", "131", "audit-record-knockout",
         "/declared/manuscript_claims_bound"),
        ("repo-table-quotations", "Table 9", SOURCES, "18", "audit-record-knockout",
         "/declared/quotations"),
        ("repo-table-sources", "Table 9", SOURCES, "7", "audit-record-knockout",
         "/declared/pinned_sources"),
        ("repo-table-repro-exit", "Table 9", "no evidence manifest; exit 2, nothing addressed", "2",
         "audit-record-knockout", "/steps/repro.verify/exit"),
        ("repo-quotations-unchecked", "Section 5.2", "and all 18 quotations come back", "18",
         "audit-record-knockout", "/declared/quotations"),
        ("codecheck-bound-of-which", "Section 5.2", "Of the 338, 326 match the certified file", "338",
         "codecheck-counts", "/numbers_bound"),
        ("census-body-abstracts", "Section 5.2", CENSUS_BODY, "43462", "census-counts",
         "/bound_by_the_study/records_screened_all"),
        ("census-body-claim-records", "Section 5.2", CENSUS_BODY, "14053", "census-counts",
         "/bound_by_the_study/claim_records_all"),
        ("census-body-exact", "Section 5.2", SPANS_BODY, "13989", "census-counts",
         "/bound_by_the_study/claim_records_passing_the_span_check_registered_run"),
        ("census-body-twice", "Section 5.2", SPANS_BODY, "27", "census-counts",
         "/bound_by_the_study/span_failures_passage_standing_twice"),
        ("census-body-word-left-out", "Section 5.2", SPANS_BODY, "37", "census-counts",
         "/bound_by_the_study/span_failures_one_token_left_out"),
        ("quotation-audit-pdfs", "Appendix A", "of which the fifteen PDFs of the papers", "15", "corpus",
         "/corpus/documents"),
        ("layout-misquotations", "Appendix A", "have recorded all 113 as misquotations", "113", "corpus",
         "/per_reader/poppler-layout/outcomes/not found"),
        ("poppler-union-caption", "Table 6", "together reach 2,360", "2360", "unions",
         "/resolved_by_either_poppler_mode"),
        ("any-reader-union-caption", "Table 6",
         "reaching 2,362. Two quotations resolve under no extractor", "2362", "unions",
         "/resolved_by_at_least_one_reader"),
        ("no-reader-caption", "Table 6", "reaching 2,362. Two quotations resolve under no extractor", "2",
         "unions", "/resolved_by_no_reader"),
        ("readers-table-header", "Table 6", "Extractor | Resolved of 2,364 | Seconds", "2364", "corpus",
         "/corpus/quotations"),
        ("readers-table-all-six", "Table 6", "all six | 2,362 | 71.4", "6", "reader-timings",
         "/readers_counted"),
    ),
    reader_seconds("poppler, reading order | 2,314 | 6.9", "poppler-flow", "/per_reader/poppler-flow"),
    reader_seconds("poppler, layout | 2,250 | 6.9", "poppler-layout", "/per_reader/poppler-layout"),
    reader_seconds("pure-Python reader | 2,229 | 43.9", "pypdf", "/per_reader/pypdf"),
    reader_seconds("rendering-engine binding | 2,092 | 4.8", "pdfium", "/per_reader/pdfium"),
    reader_seconds("structural extractor | 1,973 | 6.2", "pdf-extract", "/per_reader/pdf-extract"),
    reader_seconds("low-level parser | 1,716 | 2.7", "lopdf", "/per_reader/lopdf"),
    reader_seconds("both poppler modes | 2,360 | 13.8", "both-poppler-modes", "/both_poppler_modes"),
    reader_seconds("all six | 2,362 | 71.4", "all-six", "/all_readers"),
    over("fixtures-three-each-least", "Appendix A", THREE_EACH, "3", "conformance", "min",
         *GROUPS_OF_THREE),
    over("fixtures-three-each-greatest", "Appendix A", THREE_EACH, "3", "conformance", "max",
         *GROUPS_OF_THREE),
    over("fixtures-two-each-least", "Appendix A", TWO_EACH, "2", "conformance", "min", *GROUPS_OF_TWO),
    over("fixtures-two-each-greatest", "Appendix A", TWO_EACH, "2", "conformance", "max",
         *GROUPS_OF_TWO),
    *bound(
        ("timing-runs", "Appendix D", "is the median of 10 runs of the command a user types", "10",
         "check-timings", "/runs_per_check"),
        ("timing-cores", "Appendix D", "6-core Intel Core i7-9750H", "6", "check-timings",
         "/machine/physical_cores"),
        ("timing-memory", "Appendix D", "16,GB of memory", "16", "check-timings", "/machine/memory_gb"),
        ("timing-macos", "Appendix D", "macOS 26.5", "26.5", "check-timings", "/machine/macos"),
        ("timing-container-processors", "Appendix D", CONTAINER, "2", "check-timings-container",
         "/machine/cpu_requested"),
        ("timing-container-memory", "Appendix D", CONTAINER, "4096", "check-timings-container",
         "/machine/memory_mb_requested"),
        ("timing-laptop-load", "Appendix D", LOAD, "3.37", "check-timings",
         "/machine/load_average_at_start/0"),
        ("timing-laptop-slowest", "Appendix D", "its slowest run reading every source took 14.287 seconds",
         "14.287", "check-timings", "/citations_verify/max_seconds"),
        ("timing-paper-runs", "Appendix D", "Seconds to check this paper's records, over 10 runs", "10",
         "check-timings", "/runs_per_check"),
        ("timing-paper-runs-container", "Appendix D", "Seconds to check this paper's records, over 10 runs",
         "10", "check-timings-container", "/runs_per_check"),
        ("timing-start", "Appendix D", "The command starts in 0.192 seconds", "0.192",
         "check-timings-by-size", "/checks/0/median_seconds"),
        ("timing-start-assertions", "Appendix D", "most of its cost up to 100 assertions", "100",
         "check-timings-by-size", "/checks/3/size/assertions"),
        ("timing-largest-verify", "Appendix D", BIG_PROJECT, "2.416", "check-timings-by-size",
         "/checks/17/median_seconds"),
        ("timing-largest-sha256sum", "Appendix D", BIG_PROJECT, "2.163", "check-timings-by-size",
         "/checks/18/median_seconds"),
        ("timing-anchor-search", "Appendix D", "past 10,000, because each text anchor", "10000",
         "check-timings-by-size", "/checks/7/size/assertions"),
        ("timing-size-runs", "Table 10", "Each time is the median of 5 runs", "5",
         "check-timings-by-size", "/runs_per_check"),
        ("timing-size-processors", "Table 10", MACHINE, "2", "check-timings-by-size",
         "/machine/cpus_usable"),
        ("timing-size-memory", "Table 10", MACHINE, "7", "check-timings-by-size",
         "/machine/memory_gb_visible"),
        ("timing-size-held-assertions", "Table 10", "hold the assertions at 100 and add pinned files",
         "100", "check-timings-by-size", "/checks/11/size/assertions"),
    ),
    *paper_timing("| laptop | 1.28 | 1.230 | 2.578", "repro_verify", "check-timings"),
    *paper_timing("| container | 0.55 | 0.545 | 0.573", "repro_verify", "check-timings-container"),
    *paper_timing("citations verify, every source read | laptop | 11.19 | 10.912 | 14.287", "citations_verify",
                  "check-timings"),
    *paper_timing("| container | 7.17 | 6.994 | 7.421", "citations_verify", "check-timings-container"),
    *paper_timing("citations verify, extracted text kept | laptop | 1.90 | 1.876 | 1.993",
                  "citations_verify_with_cache", "check-timings"),
    *paper_timing("| container | 0.94 | 0.924 | 3.098", "citations_verify_with_cache", "check-timings-container"),
    *timing_row("10 | 647 | 0.213 | 0.001", 1),
    *timing_row("100 | 6,389 | 0.238 | 0.001", 3),
    *timing_row("1,000 | 63,807 | 0.556 | 0.001", 5),
    *timing_row("10,000 | 638,009 | 6.733 | 0.002", 7),
    *timing_row("100,000 | 6,380,011 | 193.128 | 0.005", 9),
    *timing_row("100 | 1,054,965 | 0.223 | 0.002", 11),
    *timing_row("100 | 16,783,605 | 0.246 | 0.010", 13),
    *timing_row("100 | 268,441,845 | 0.372 | 0.142", 15),
    *timing_row("100 | 4,294,973,685 | 2.416 | 2.163", 17),
]

CROSS = "audit-record-cross-design"
KNOCK = "audit-record-knockout"
CROSS_ROW = "Cross-design evidence discordance | | 5 | 14 | 8 | 4 | 31"
KNOCK_ROW = "Knockout epistasis | | 3 | 2 | 10 | 3 | 18"
CROSS_ALL = "All Findings. 31: 5 claim, 14 source, 8 record, 4 cosmetic."
KNOCK_ALL = "All Findings. 18: 3 claim, 2 source, 10 record, 3 cosmetic."
CROSS_CARRIES = ("The clone carries 365 tracked files, 6 registration documents, 94 claim records, 175 "
                 "quotations and 75 bibliography entries.")
KNOCK_CARRIES = ("The clone carries 1,267 tracked files, 3 registered plans, 153 ledger events, 13 runs, "
                 "131 manuscript claims bound to a run, 7 claim records and 18 quotations.")
REVIEWERS = "Reviewer comments (4 reviewers, 6 reports)"
SEVERITIES = (("claim", "claim"), ("integrity", "source"), ("record", "record"), ("cosmetic", "cosmetic"))


def severities(audit: str, row: str, prefix: str, *printed: str) -> list[Bound]:
    """The four severity counts of one audit, as one row of Table 14 or one All Findings line
    prints them, in the order claim, source, record, cosmetic."""
    return bound(*(
        (f"{prefix}-{shown}", "Appendix E", row, value, "audit-counts",
         f"/audits/{audit}/by_severity/{key}")
        for (key, shown), value in zip(SEVERITIES, printed, strict=True)
    ), stated_in="appendix-text")


def carries(record: str, sentence: str, prefix: str, pointers: list[tuple[str, str]]) -> list[Bound]:
    """Each count in one `The clone carries` sentence of the generated appendix."""
    return bound(*(
        (f"{prefix}-{pointer.rsplit('/', 1)[1].replace('_', '-')}", "Appendix E", sentence, printed,
         record, pointer)
        for printed, pointer in pointers
    ), stated_in="appendix-text")


AUDIT_APPENDIX = [
    *bound(
        ("audits-under-review-table", "Appendix E", "a clone for the two submitted to journals", "2",
         "audit-counts", "/total/audits"),
        ("cross-design-registrations-summary", "Table 13", "4 of 6 registrations unchanged", "6", CROSS,
         "/declared/registration_documents"),
        ("cross-design-quotations-summary", "Table 13", "of 175 found", "175", CROSS,
         "/declared/quotations"),
        ("knockout-plans-summary", "Table 13", "3 of 3 plans unchanged", "3", KNOCK,
         "/declared/registered_plans"),
        ("knockout-quotations-summary", "Table 13", "18 declared, sources absent", "18", KNOCK,
         "/declared/quotations"),
        ("knockout-ledger-summary", "Table 13", "chain intact, 153 events", "153", KNOCK,
         "/declared/ledger_events"),
        ("cross-design-reviews-findings", "Appendix F", "Reviews. Of the 31 findings", "31",
         "audit-counts", "/audits/cross_design/findings"),
        ("cross-design-prereg-exit", "Appendix F", "prereg | 1 | 6 registration documents", "1", CROSS,
         "/steps/prereg.check/exit"),
        ("cross-design-prereg-documents", "Appendix F", "prereg | 1 | 6 registration documents", "6",
         CROSS, "/declared/registration_documents"),
        ("cross-design-results-exit", "Appendix F", "results | 2 | no ledger", "2", CROSS,
         "/steps/results.verify/exit"),
        ("cross-design-citations-exit", "Appendix F", "citations | 0 | 175 of 175 quotations found",
         "0", CROSS, "/steps/citations.verify/exit"),
        ("cross-design-citations-declared", "Appendix F", "of 175 quotations found in their sources",
         "175", CROSS, "/declared/quotations"),
        ("cross-design-citations-sources", "Appendix F", "67 of the 94 sources were read", "94", CROSS,
         "/declared/pinned_sources"),
        ("cross-design-audit-exit", "Appendix F", "citations audit | 0 | 75 bibliography entries", "0",
         CROSS, "/steps/citations.audit/exit"),
        ("cross-design-audit-entries", "Appendix F", "citations audit | 0 | 75 bibliography entries",
         "75", CROSS, "/declared/bibliography_entries_cited_by_the_manuscript"),
        ("cross-design-repro-exit", "Appendix F",
         "whether the entry with no identifier is correct repro | 2 | no evidence manifest", "2", CROSS,
         "/steps/repro.verify/exit"),
        ("cross-design-reviewers", "Appendix F", REVIEWERS, "4", "review-counts-cross-design",
         "/distinct_reviewers"),
        ("cross-design-reports", "Appendix F", REVIEWERS, "6", "review-counts-cross-design", "/reports"),
        ("comments-design", "Appendix F", "design and argument | 20", "20", "review-counts-cross-design",
         "/points_by_kind_total/design~1argument"),
        ("comments-reporting", "Appendix F", "reporting and presentation | 12", "12",
         "review-counts-cross-design", "/points_by_kind_total/reporting~1presentation"),
        ("comments-statistics", "Appendix F", "statistical method | 10", "10",
         "review-counts-cross-design", "/points_by_kind_total/statistical method"),
        ("comments-references", "Appendix F", "references | 1", "1", "review-counts-cross-design",
         "/points_by_kind_total/references~1sources"),
        ("comments-availability", "Appendix F", "code and data availability | 0", "0",
         "review-counts-cross-design", "/points_by_kind_total/code~1data availability"),
        ("comments-other", "Appendix F", "other | 2", "2", "review-counts-cross-design",
         "/points_by_kind_total/other"),
        ("comments-total", "Appendix F", "Total | 45", "45", "review-counts-cross-design",
         "/points_total"),
        ("cross-design-findings-total", "Appendix F", "Total | 31", "31", "audit-counts",
         "/audits/cross_design/findings"),
        ("knockout-prereg-exit", "Appendix G", "prereg | 0 | 3 plans, each unchanged", "0", KNOCK,
         "/steps/prereg.check/exit"),
        ("knockout-prereg-plans", "Appendix G", "prereg | 0 | 3 plans, each unchanged", "3", KNOCK,
         "/declared/registered_plans"),
        ("knockout-results-exit", "Appendix G", "results | 1 | chain intact and anchored at 153 events",
         "1", KNOCK, "/steps/results.verify/exit"),
        ("knockout-results-events", "Appendix G",
         "results | 1 | chain intact and anchored at 153 events", "153", KNOCK, "/declared/ledger_events"),
        ("knockout-results-recorded", "Appendix G", "8 of 12 recorded files match their digest", "12",
         KNOCK, "/declared/file_digests_recorded"),
        ("knockout-results-claims", "Appendix G", "the 131 claims cover, the manuscript not being",
         "131", KNOCK, "/declared/manuscript_claims_bound"),
        ("knockout-citations-exit", "Appendix G", "citations | 1 | 18 quotations declared against 7",
         "1", KNOCK, "/steps/citations.verify/exit"),
        ("knockout-citations-quotations", "Appendix G",
         "citations | 1 | 18 quotations declared against 7", "18", KNOCK, "/declared/quotations"),
        ("knockout-citations-sources", "Appendix G",
         "citations | 1 | 18 quotations declared against 7", "7", KNOCK, "/declared/pinned_sources"),
        ("knockout-repro-exit", "Appendix G",
         "whether any quotation occurs in its source repro | 2 | no evidence manifest", "2", KNOCK,
         "/steps/repro.verify/exit"),
        stated_in="appendix-text",
    ),
    *severities("cross_design", CROSS_ROW, "findings-row-cross-design", "5", "14", "8", "4"),
    *severities("knockout", KNOCK_ROW, "findings-row-knockout", "3", "2", "10", "3"),
    *severities("cross_design", CROSS_ALL, "all-findings-cross-design", "5", "14", "8", "4"),
    *severities("knockout", KNOCK_ALL, "all-findings-knockout", "3", "2", "10", "3"),
    *carries(CROSS, CROSS_CARRIES, "cross-design-carries", [
        ("365", "/declared/tracked_files"), ("6", "/declared/registration_documents"),
        ("94", "/declared/claim_records"), ("175", "/declared/quotations"),
        ("75", "/declared/bibliography_entries_cited_by_the_manuscript"),
    ]),
    *carries(KNOCK, KNOCK_CARRIES, "knockout-carries", [
        ("1267", "/declared/tracked_files"), ("3", "/declared/registered_plans"),
        ("153", "/declared/ledger_events"), ("13", "/declared/runs"),
        ("131", "/declared/manuscript_claims_bound"), ("7", "/declared/claim_records"),
        ("18", "/declared/quotations"),
    ]),
]

CC = "certified-reproductions-text"
CC_RESULT = "338 of the 713 numbers those tables print"
CC_SAME = "In 326 of the 338, the paper and the"
CC_OUTPUTS = "The manifests name 545 outputs, of which 419 are figures"
CC_BINDS = "Four certificates bind between 64 of 92 and 137 of 140"
CC_READ = "It reports 69 as disagreeing and does not read 15, and 72 of those 84 are the same number"
CC_UNREAD = "The 15 unread numbers, 11 of them equal to the file"
CC_MEMORY = "Three are memory measurements, 0.1% to 7.0% from the file's value"
CC_MISSES = ("the file in all 254 cases and of the paper in 240. In ten of the fourteen misses the file "
             "stores fewer digits than the paper prints, and in four the changed numeral")
CC_ARMS = "The first three rows use the 254 numbers that agree; the last three use all 338"
H2 = "/arms/h2_paper"


def coverage_row(row: str) -> list[Bound]:
    """One certificate's row of Table 12: printed and bound from the indices, the same number and
    the differences from the agreement summary. A row printing dashes binds the first two only."""
    certificate, printed, bound_, same, differ = (cell.strip() for cell in row.split("|"))
    indices = f"/per_certificate/{certificate}"
    rows = [
        (f"cc-{certificate}-printed", "Table 12", row, printed, "codecheck-indices", f"{indices}/printed"),
        (f"cc-{certificate}-bound", "Table 12", row, bound_, "codecheck-indices", f"{indices}/bound"),
    ]
    if same != "—":
        rows += [
            (f"cc-{certificate}-same", "Table 12", row, same, "codecheck-agreement",
             f"/per_certificate/{certificate}/same_number"),
            (f"cc-{certificate}-differ", "Table 12", row, differ, "codecheck-agreement",
             f"/per_certificate/{certificate}/differ"),
        ]
    return bound(*rows, stated_in=CC)


def difference(row: str, index: int, paper: bool) -> list[Bound]:
    """One row of Table 15: the file's value, and the paper's where the record stores it as a
    plain numeral. The record keeps the paper's numeral as printed, so one carrying a thousands
    separator is no number a pointer can read."""
    cells = [cell.strip() for cell in row.split("|")]
    base = f"/differences/{index}"
    rows = [(f"cc-difference-{index}-file", "Table 15", row, cells[2].replace(",", ""),
             "codecheck-agreement", f"{base}/stored")]
    if paper:
        rows.append((f"cc-difference-{index}-paper", "Table 15", row, cells[1], "codecheck-agreement",
                     f"{base}/paper"))
    else:
        rows.append((f"cc-difference-{index}-paper", "Table 15", row, cells[1].replace(",", ""),
                     "codecheck-paper-numerals", f"{base}/paper"))
    return bound(*rows, stated_in=CC)


def relative(row: str, index: int) -> list[Bound]:
    """The difference column of a row of Table 15, a percentage of the file's value."""
    return bound((f"cc-difference-{index}-relative", "Table 15", row, row.rsplit("| ", 1)[1].rstrip("%"),
                  "codecheck-agreement", f"/differences/{index}/relative_difference_from_file"),
                 stated_in=CC, conversion="percent")


def planted(row: str, arm: str) -> list[Bound]:
    """One row of Table 16: as expected, of generated."""
    as_expected, generated = row.rsplit("| ", 1)[1].split(" of ")
    return bound(
        (f"cc-planted-{arm}-as-expected", "Table 16", row, as_expected, "codecheck-indices",
         f"/arms/{arm}/as_expected"),
        (f"cc-planted-{arm}-generated", "Table 16", row, generated, "codecheck-indices",
         f"/arms/{arm}/generated"),
        stated_in=CC,
    )


# Moved from Related Work into the related-work appendix.
RELATED_APPENDIX = bound(
    ("readers-related-work", "Appendix",
     "six extractors read the same bytes and returned six results", "6", "reader-timings",
     "/readers_counted"),
    stated_in="reexecution-precedents-text",
)

CERTIFIED = [
    *bound(
        ("cc-certificates-linked", "Appendix C", "Six certificates link fifteen tables", "6",
         "codecheck-counts", "/certificates_with_a_linked_table_file"),
        ("cc-result-bound", "Appendix C", CC_RESULT, "338", "codecheck-counts", "/numbers_bound"),
        ("cc-result-printed", "Appendix C", CC_RESULT, "713", "codecheck-counts", "/numbers_printed"),
        ("cc-result-same", "Appendix C", CC_SAME, "326", "codecheck-agreement", "/all/same_number"),
        ("cc-result-same-of", "Appendix C", CC_SAME, "338", "codecheck-agreement", "/all/bound"),
        ("cc-result-differ", "Appendix C", "Twelve differ, in two certificates", "12",
         "codecheck-agreement", "/all/differ"),
        ("cc-outputs-figures", "Appendix C", CC_OUTPUTS, "419", "codecheck-eligibility",
         "/outputs_by_kind/figure"),
        ("cc-certificates-read", "Appendix C", "Six certificates name a file the toolkit reads",
         "6", "codecheck-counts", "/certificates_with_a_linked_table_file"),
        ("cc-funnel-register", "Table 11", "in the register | 133", "133", "codecheck-eligibility",
         "/certificates"),
        ("cc-funnel-table", "Table 11", "its manifest comment names a table the paper has | 6", "6",
         "codecheck-counts", "/certificates_with_a_linked_table_file"),
        ("cc-binds-2022-001", "Appendix C", CC_BINDS, "64", "codecheck-indices",
         "/per_certificate/2022-001/bound"),
        ("cc-binds-2022-001-printed", "Appendix C", CC_BINDS, "92", "codecheck-indices",
         "/per_certificate/2022-001/printed"),
        ("cc-binds-2025-018", "Appendix C", CC_BINDS, "137", "codecheck-indices",
         "/per_certificate/2025-018/bound"),
        ("cc-binds-2025-018-printed", "Appendix C", CC_BINDS, "140", "codecheck-indices",
         "/per_certificate/2025-018/printed"),
        ("cc-pooled-printed", "Table 12", "all | 713 | 338 | 326 | 12", "713", "codecheck-indices",
         "/pooled/printed"),
        ("cc-pooled-bound", "Table 12", "all | 713 | 338 | 326 | 12", "338", "codecheck-indices",
         "/pooled/bound"),
        ("cc-pooled-same", "Table 12", "all | 713 | 338 | 326 | 12", "326", "codecheck-agreement",
         "/all/same_number"),
        ("cc-pooled-differ", "Table 12", "all | 713 | 338 | 326 | 12", "12", "codecheck-agreement",
         "/all/differ"),
        ("cc-agreeing", "Appendix C", "The toolkit reports 254 of the 338 bound numbers", "254",
         "codecheck-indices", "/pooled/natural/verified"),
        ("cc-agreeing-of", "Appendix C", "The toolkit reports 254 of the 338 bound numbers",
         "338", "codecheck-indices", "/pooled/bound"),
        ("cc-disagreeing", "Appendix C", CC_READ, "69", "codecheck-indices", "/pooled/natural/mismatch"),
        ("cc-not-read", "Appendix C", CC_READ, "15", "codecheck-indices", "/pooled/natural/not_found"),
        ("cc-check-time-cells", "Appendix C", "The 30 numbers of one table of certificate", "30",
         "codecheck-mismatch-review", "/check_time_file/cells"),
        ("cc-unread", "Appendix C", CC_UNREAD, "15", "codecheck-mismatch-review", "/totals/not_read"),
        ("cc-unread-equal", "Appendix C", CC_UNREAD, "11", "codecheck-agreement", "/all/agrees"),
        ("cc-agreement-caption", "Table 14", "The 338 bound numbers, by how the paper's numeral", "338",
         "codecheck-agreement", "/all/bound"),
        ("cc-agreement-reported", "Table 14", "the check reports agreement | 254", "254",
         "codecheck-agreement", "/all/checker_agrees"),
        ("cc-agreement-truncates", "Table 14", "the paper truncates where the check rounds | 31", "31",
         "codecheck-agreement", "/all/truncation"),
        ("cc-agreement-check-time", "Table 14",
         "equal at the output file's revision at the check time | 30", "30", "codecheck-agreement",
         "/all/check-time file"),
        ("cc-agreement-separator", "Table 14", "equal once a thousands separator is removed | 11", "11",
         "codecheck-agreement", "/all/agrees"),
        ("cc-agreement-differ", "Table 14", "differ | 12 all | 338", "12", "codecheck-agreement",
         "/all/differ"),
        ("cc-agreement-all", "Table 14", "differ | 12 all | 338", "338", "codecheck-agreement",
         "/all/bound"),
        ("cc-differences-listed", "Appendix C", "Table lists the 12 numbers that differ. Five", "12",
         "codecheck-agreement", "/all/differ"),
        ("cc-differences-divisor", "Appendix C", "Table lists the 12 numbers that differ. Five", "5",
         "codecheck-agreement", "/differences_by_relation/n divisor"),
        ("cc-divisor-n", "Appendix C", "n = 1,070", "1070", "codecheck-mismatch-review",
         "/standard_deviations/rows/0/n"),
        ("cc-divisor-all", "Appendix C", "reproduces all 12 standard deviations counted in that table",
         "12", "codecheck-mismatch-review", "/standard_deviations/equal_scaled_rounded"),
        ("cc-differences-caption", "Table 15", "The 12 bound numbers that differ between the paper", "12",
         "codecheck-agreement", "/all/differ"),
        ("cc-planted-file", "Appendix C", CC_MISSES, "254", "codecheck-indices",
         "/arms/h3_output/as_expected"),
        ("cc-planted-paper", "Appendix C", CC_MISSES, "240", "codecheck-indices", f"{H2}/as_expected"),
        ("cc-planted-paper-short", "Appendix C", CC_MISSES, "10", "codecheck-indices",
         f"{H2}/observed/verified~1value_match"),
        ("cc-planted-paper-anchors", "Appendix C", CC_MISSES, "4", "codecheck-indices",
         f"{H2}/observed/not_found~1passage_absent"),
        ("cc-planted-agreeing", "Table 16", CC_ARMS, "254", "codecheck-indices",
         "/arms/h1_control/generated"),
        ("cc-planted-all", "Table 16", CC_ARMS, "338", "codecheck-indices", "/arms/h4_row/generated"),
        stated_in=CC,
    ),
    *bound(
        ("cc-memory-least", "Appendix C", CC_MEMORY, "0.1", "codecheck-agreement",
         "/differences/10/relative_difference_from_file"),
        ("cc-memory-greatest", "Appendix C", CC_MEMORY, "7.0", "codecheck-agreement",
         "/differences/9/relative_difference_from_file"),
        stated_in=CC, conversion="percent",
    ),
    over("cc-outputs", "Appendix C", CC_OUTPUTS, "545", "codecheck-eligibility", "sum",
         "/outputs_by_kind/figure", "/outputs_by_kind/value", "/outputs_by_kind/other", stated_in=CC),
    over("cc-funnel-value-outputs", "Table 11",
         "names an output in a format read as values, not marked as outside the manuscript | 13", "13",
         "codecheck-eligibility", "sum", "/by_status/candidate", "/by_status/pending", stated_in=CC),
    over("cc-same-number-not-agreeing", "Appendix C", CC_READ, "72", "codecheck-agreement", "sum",
         "/all/truncation", "/all/check-time file", "/all/agrees", stated_in=CC),
    over("cc-not-agreeing", "Appendix C", CC_READ, "84", "codecheck-mismatch-review", "sum",
         "/totals/disagree", "/totals/not_read", stated_in=CC),
    over("cc-planted-paper-misses", "Appendix C", CC_MISSES, "14", "codecheck-indices", "sum",
         f"{H2}/observed/verified~1value_match", f"{H2}/observed/not_found~1passage_absent",
         stated_in=CC),
    *coverage_row("2025-018 | 140 | 137 | 133 | 4"),
    *coverage_row("2020-025 | 90 | 86 | 86 | 0"),
    *coverage_row("2022-001 | 92 | 64 | 56 | 8"),
    *coverage_row("2024-020 | 58 | 51 | 51 | 0"),
    *coverage_row("2020-011 | 33 | 0 | — | —"),
    *coverage_row("2020-008 | 300 | 0 | — | —"),
    *difference("standard deviation | 30.33 | 30.3485", 0, paper=True),
    *difference("standard deviation | 21.80 | 21.8124", 1, paper=True),
    *difference("standard deviation | 28.20 | 28.2116", 6, paper=True),
    *difference("standard deviation | 84,154.56 | 84,193.92", 2, paper=False),
    *difference("standard deviation | 3,132.90 | 3,134.36", 4, paper=False),
    *difference("median | 4,984.44 | 4,984.4349", 5, paper=False),
    *difference("maximum | 827,067.40 | 827,067.43", 3, paper=False),
    *bound(("cc-difference-3-absolute", "Table 15", "maximum | 827,067.40 | 827,067.43 | 0.03", "0.03",
            "codecheck-paper-numerals", "/differences/3/absolute_difference"), stated_in=CC),
    *difference("run time, seconds | 12.659 | 12.658475", 8, paper=True),
    *difference("memory, megabytes | 3.1 | 2.897 | 7.0%", 9, paper=True),
    *difference("memory, megabytes | 610.8 | 611.443 | 0.1%", 10, paper=True),
    *difference("memory, megabytes | 2310.8 | 2329.968 | 0.8%", 11, paper=True),
    *relative("memory, megabytes | 3.1 | 2.897 | 7.0%", 9),
    *relative("memory, megabytes | 610.8 | 611.443 | 0.1%", 10),
    *relative("memory, megabytes | 2310.8 | 2329.968 | 0.8%", 11),
    *bound(("cc-difference-7-paper", "Table 15", "regression coefficient | 5.273 |", "5.273",
            "codecheck-agreement", "/differences/7/paper"), stated_in=CC),
    *planted("none | agreement | 254 of 254", "h1_control"),
    *planted("last printed digit of the file's value | disagreement | 254 of 254", "h3_output"),
    *planted("last printed digit of the paper's value | disagreement | 240 of 254", "h2_paper"),
    *planted("addressed row deleted | row absent | 338 of 338", "h4_row"),
    *planted("addressed column deleted | column absent | 338 of 338", "h4_column"),
    *planted("output file deleted | not checked, file missing | 338 of 338", "h4_file"),
]

CENSUS_CARRIES = ("The repository carries 1 frozen plan with 194 log lines, 233 ledger events, 40 runs, "
                  "3,508 claim records and 23,939 quotations.")
CENSUS_RESULTS = ("chain intact at 233 events; 373 of 374 recorded files match their digest and 1 "
                  "carries")
CENSUS_CITATIONS = ("13,989 of 13,989 pinned source sentences and 2,167 of 2,167 pinned sentences behind "
                    "the dataset codes found in their stored sources; 7,783 quotations")
CENSUS_SCREENING = ("90 seals of scripts and inputs and 40 recorded runs, over 43,462 abstracts screened "
                    "and 14,053 extracted records")
CENSUS_MODEL = ("A language model screens 43,462 abstracts and extracts 14,053 records from the "
                "2,363 papers it admits")
CENSUS_SPANS = ("Of the 14,053 sentences, 13,989 resolve in the stored abstract. Of the 64 that do not, 27 "
                "occur twice in the abstract and 37 leave out one word of it")
CENSUS_CODING = "assign a dataset to each of 872 dataset names in 434 papers"
CENSUS_ACCESS = "Of 26 accesses, 4 are at the level metadata only, 19 at structure seen and 3 at outcomes seen"
STUDY = "/bound_by_the_study"

CENSUS = bound(
    ("census-title", "Appendix I", "Literature census of 43,462 abstracts", "43462", "census-counts",
     f"{STUDY}/records_screened_all"),
    ("census-plan-log", "Appendix I", CENSUS_CARRIES, "194", "census-counts", "/plan_log_lines"),
    ("census-ledger-events", "Appendix I", CENSUS_CARRIES, "233", "census-counts", "/ledger_events"),
    ("census-runs", "Appendix I", CENSUS_CARRIES, "40", "census-counts", "/runs"),
    ("census-claim-records", "Appendix I", CENSUS_CARRIES, "3508", "census-counts", "/claim_files_all"),
    ("census-quotations", "Appendix I", CENSUS_CARRIES, "23939", "census-counts", "/quotations_all"),
    ("census-prereg-exit", "Table 17", "prereg | 0 | 1 plan, unchanged", "0", "census-counts",
     "/exits/prereg.check"),
    ("census-results-exit", "Table 17", "results | 1 | chain intact at 233 events", "1", "census-counts",
     "/exits/results.verify"),
    ("census-results-events", "Table 17", CENSUS_RESULTS, "233", "census-counts", "/ledger_events"),
    ("census-results-matching", "Table 17", CENSUS_RESULTS, "373", "census-counts",
     "/recorded_files_matching"),
    ("census-results-resealed", "Table 17", "and 1 carries 2 recorded digests", "1", "census-counts",
     "/recorded_files_resealed"),
    ("census-citations-exit", "Table 17", "citations | 1 | 13,989 of 13,989", "1", "census-counts",
     "/exits/citations.verify.repository"),
    ("census-citations-extraction", "Table 17", CENSUS_CITATIONS, "13989", "census-counts",
     "/extraction_quotations_found"),
    ("census-citations-coding", "Table 17", CENSUS_CITATIONS, "2167", "census-counts",
     "/quotations/dataset_coding/found"),
    ("census-citations-repository", "Table 17", CENSUS_CITATIONS, "7783", "census-counts",
     "/quotations/repository/unchecked"),
    ("census-repro-exit", "Table 17", "repro | 0 | 5 of 5 assertions verified", "0", "census-counts",
     "/exits/repro.verify"),
    ("census-repro-assertions", "Table 17", "repro | 0 | 5 of 5 assertions verified", "5",
     "census-counts", "/manifest_assertions"),
    ("census-stage-plan", "Table 18", "and 194 dated log lines under it", "194", "census-counts",
     "/plan_log_lines"),
    ("census-stage-seals", "Table 18", CENSUS_SCREENING, "90", "census-counts",
     "/ledger_events_by_kind/seal"),
    ("census-stage-runs", "Table 18", CENSUS_SCREENING, "40", "census-counts", "/runs"),
    ("census-stage-screened", "Table 18", CENSUS_SCREENING, "43462", "census-counts",
     f"{STUDY}/records_screened_all"),
    ("census-stage-extracted", "Table 18", CENSUS_SCREENING, "14053", "census-counts",
     f"{STUDY}/claim_records_all"),
    ("census-stage-verified", "Table 18", "the source sentence of each of the 14,053 extracted records",
     "14053", "census-counts", f"{STUDY}/claim_records_all"),
    ("census-stage-coding", "Table 18", "2,167 pinned sentences behind the codes for 872 dataset names",
     "2167", "census-counts", f"{STUDY}/pinned_quotations_manual_coding"),
    ("census-stage-names", "Table 18", "2,167 pinned sentences behind the codes for 872 dataset names",
     "872", "census-counts", f"{STUDY}/queue_rows"),
    ("census-stage-access", "Table 18", "26 access records, each with", "26", "census-counts",
     "/access_records"),
    ("census-model-screened", "Appendix I", CENSUS_MODEL, "43462", "census-counts",
     f"{STUDY}/records_screened_all"),
    ("census-model-extracted", "Appendix I", CENSUS_MODEL, "14053", "census-counts",
     f"{STUDY}/claim_records_all"),
    ("census-model-papers", "Appendix I", CENSUS_MODEL, "2363", "census-counts",
     f"{STUDY}/papers_extracted_all"),
    ("census-spans-sentences", "Appendix I", CENSUS_SPANS, "14053", "census-counts",
     f"{STUDY}/claim_records_all"),
    ("census-spans-resolved", "Appendix I", CENSUS_SPANS, "13989", "census-counts",
     f"{STUDY}/claim_records_passing_the_span_check_registered_run"),
    ("census-spans-failed", "Appendix I", CENSUS_SPANS, "64", "census-counts",
     f"{STUDY}/span_failures_all"),
    ("census-spans-twice", "Appendix I", CENSUS_SPANS, "27", "census-counts",
     f"{STUDY}/span_failures_passage_standing_twice"),
    ("census-spans-word", "Appendix I", CENSUS_SPANS, "37", "census-counts",
     f"{STUDY}/span_failures_one_token_left_out"),
    ("census-coding-names", "Appendix I", CENSUS_CODING, "872", "census-counts", f"{STUDY}/queue_rows"),
    ("census-coding-papers", "Appendix I", CENSUS_CODING, "434", "census-counts",
     f"{STUDY}/queue_papers"),
    ("census-access-all", "Appendix I", CENSUS_ACCESS, "26", "census-counts", "/access_records"),
    ("census-access-metadata", "Appendix I", CENSUS_ACCESS, "4", "census-counts",
     "/access_records_by_level/metadata only"),
    ("census-access-structure", "Appendix I", CENSUS_ACCESS, "19", "census-counts",
     "/access_records_by_level/structure seen"),
    ("census-access-outcomes", "Appendix I", CENSUS_ACCESS, "3", "census-counts",
     "/access_records_by_level/outcomes seen"),
    ("census-access-frozen-before", "Appendix I", "The plan was frozen before all three", "3",
     "census-counts", "/access_records_by_level/outcomes seen"),
    stated_in="literature-census-text",
) + [
    over("census-results-recorded", "Table 17", CENSUS_RESULTS, "374", "census-counts", "sum",
         "/recorded_files_matching", "/recorded_files_resealed", stated_in="literature-census-text"),
]

# Counts read out of recorded command output and catch logs by the three derivers
# `derive_command_counts.py`, `derive_catch_log_counts.py` and `derive_extractor_spread.py`.
COMMANDS = "command-counts"
CATCHES = "catch-log-counts"
CROSS_COMMANDS = "/audits/cross_design"
KNOCK_FILES_BODY = "8 of 12 recorded files match their digest, and 4 carry"
KNOCK_FILES = "8 of 12 recorded files match their digest and 4 carry"
BIB_AUDIT = "74 carrying an identifier; 64 agree with the record the identifier resolves to and 10 disagree"
CROSS_CLASSES = "/audits/cross_design/by_class_group"
CROSS_ROUNDS = "/audits/cross_design/by_round"
RESEALED_FILE = "/census/hashes_by_resealed_file/experiments~102_claims_meta~1tests~1test_classify_failed_spans.py"

# The 35 numbers left unaccounted for after the first pass: results held in another repository,
# copied here byte for byte, and counts derived from stored outcomes or from a commit of another
# repository. Each copy names the repository, commit and path it came from in COPIED_FROM, and
# its artifact carries them as `origin`, which `claims origins` compares with the pinned digest.
DEFECTS = "manuscript-text"
STORED_VALUE_ROW = "nine of ten table rows disagree with the file the row is read from"
SPLIT_ROW = "178 assertions marked verified, and no source in any commit"
STORED_ZERO = "A value printed at 0.001 is stored as exactly zero, and one printed at 0.0003 as 9.73e-7"
SPLIT = "In the fourth, a repository split carried 178 assertions"
QUOTE_AUDIT = ("The quote variant was run over an audit of sixteen claims from published papers: 2,512 quotations against "
               "125 content-addressed sources")
CAUSES = ("110 came from the mode's preservation of page geometry, which severs every sentence crossing the "
          "gutter of a two-column paper, 2 from a text layer omitting a character the passage contains, and 1 "
          "from a hyphen at a line end")
RATE = "a two-state checker therefore carries a false-accusation rate of 4.5%"
LAYOUT = "layout-failures"
AUDIT_SUMMARY = "toolkit-verify-performance"
RNA_MANIFEST = "rna-table5-manifest"
RNA_ROWS = "/claims/{}/evidence/0/reported"

CODECHECK_REPOSITORY = "https://github.com/elliottower/reproducible-science-codecheck"
CODECHECK_SOURCE_FIX_COMMIT = "22a073082c8f0faf81fbae86fefca5bc11bf6951"
CODECHECK_CERTIFICATE_COUNTS_COMMIT = "d05817df5ad04ae145db159be0f016f6b7cf33a3"
#: The binding summaries of the six linked certificates, all at one commit.
CODECHECK_BINDINGS_COMMIT = "b7f34f0398b0d7d2632c2db415247fcd648a3574"

COPIED_FROM = {
    "toolkit-verify-performance": ("https://github.com/elliottower/reproducible-science",
                                   "da879492da2afde0aa32aa7f5b92dcd2202feda4",
                                   "research/verify-performance/data/00_summary.json"),
    "rna-table5-nt": ("https://github.com/elliottower/rna-structure-audit",
                      "b700a510be529ec712cd76d68df140305906583b",
                      "results/audit/phase6_nt_20260714_082334/nt_phase6_ps.json"),
    "rna-table5-hyenadna": ("https://github.com/elliottower/rna-structure-audit",
                            "b700a510be529ec712cd76d68df140305906583b",
                            "results/audit/phase6_hyenadna_20260714_060542/hyenadna_phase6_ps.json"),
    "codecheck-indices": (CODECHECK_REPOSITORY, "e4f4576c5fd658fe15826612dccb8c40650ad7bc",
                          "results/indices.json"),
    "codecheck-eligibility": (CODECHECK_REPOSITORY, "a81aa24e5ded6311a2055b5d9dad1ba08d966fdc",
                              "data/eligibility_summary.json"),
    "codecheck-agreement": (CODECHECK_REPOSITORY, CODECHECK_SOURCE_FIX_COMMIT, "results/agreement_summary.json"),
    "codecheck-mismatch-review": (CODECHECK_REPOSITORY, CODECHECK_SOURCE_FIX_COMMIT,
                                  "results/natural_mismatch_review.json"),
    "codecheck-rw-tag-counts": (CODECHECK_REPOSITORY, CODECHECK_SOURCE_FIX_COMMIT,
                                "failure_cases/results/rw_tag_counts.json"),
    "codecheck-certificate-counts": (CODECHECK_REPOSITORY, CODECHECK_CERTIFICATE_COUNTS_COMMIT,
                                     "results/certificate_counts.json"),
    "codecheck-case-counts": (CODECHECK_REPOSITORY, "e03c00b5e582a533358ef16bc7a32373f10db78d",
                              "failure_cases/results/case_counts.json"),
    "codecheck-leaderboard": (CODECHECK_REPOSITORY, "a8af0ff782cf3ceac364589326b853593fd5b5ea",
                              "failure_cases/data/leaderboard_snapshot.json"),
    **{f"codecheck-binding-summary-{c}": (CODECHECK_REPOSITORY, CODECHECK_BINDINGS_COMMIT,
                                          f"bindings/{c}/summary.json") for c in LINKED_CERTIFICATES},
}

CLOSED = [
    *bound(
        ("defects-stored-value-mismatch", "Table 8", STORED_VALUE_ROW, "9", "figures",
         "/metric_corpus/rna-table5-mean-ps/mismatch"),
        ("defects-stored-value-rows", "Table 8", STORED_VALUE_ROW, "10", "figures",
         "/metric_corpus/rna-table5-mean-ps/assertions"),
        ("defects-split-assertions", "Table 8", SPLIT_ROW, "178", "split-repository-counts",
         "/claims_marked_verified"),
        ("defects-split-sources", "Table 8", SPLIT_ROW, "0", "split-repository-counts",
         "/sources_in_any_commit"),
        ("defects-split-assertions-text", "Section 5.1", SPLIT, "178", "split-repository-counts",
         "/claims_marked_verified"),
        ("defects-printed-nt", "Section 5.1", STORED_ZERO, "0.001", RNA_MANIFEST, RNA_ROWS.format(8)),
        ("defects-stored-nt", "Section 5.1", STORED_ZERO, "0", "rna-table5-nt", "/results/mean_best_ps"),
        ("defects-printed-hyenadna", "Section 5.1", STORED_ZERO, "0.0003", RNA_MANIFEST, RNA_ROWS.format(4)),
        ("defects-stored-hyenadna", "Section 5.1", STORED_ZERO, "9.73e-7", "rna-table5-hyenadna",
         "/results/mean_best_ps"),
        ("quote-audit-claims", "Appendix C", QUOTE_AUDIT, "16", AUDIT_SUMMARY, "/corpus/claims_files"),
        ("quote-audit-quotations", "Appendix C", QUOTE_AUDIT, "2512", AUDIT_SUMMARY,
         "/baseline_as_declared/quotations"),
        ("quote-audit-sources", "Appendix C", QUOTE_AUDIT, "125", AUDIT_SUMMARY, "/corpus/reference_pdfs"),
        ("layout-gutter", "Appendix C", CAUSES, "110", LAYOUT, "/resolved_by_reading_order"),
        ("layout-text-layer", "Appendix C", CAUSES, "2", LAYOUT, "/resolved_only_by_another_reader"),
        ("layout-hyphen", "Appendix C", CAUSES, "1", LAYOUT, "/resolved_by_no_reader"),
    ),
    *bound(("layout-false-accusation-rate", "Appendix C", RATE, "4.5", LAYOUT, "/false_accusation_rate"),
           conversion="percent"),
    over("cross-design-review-rounds", "Section 5.2",
         "In a preregistered study of drug-trial outcomes, four rounds of journal review", "4", "catch-log-counts",
         "count", *(f"/audits/cross_design/by_round/round_{n}" for n in range(1, 5))),
]


RECORDED_OUTPUT = [
    *bound(
        ("knockout-files-ok-body", "Table 9", KNOCK_FILES_BODY, "8", COMMANDS,
         "/audits/knockout/files_ok"),
        ("knockout-files-resealed-body", "Table 9", KNOCK_FILES_BODY, "4", COMMANDS,
         "/audits/knockout/files_resealed"),
        ("extractor-spread", "Table 6", "the low-level parser resolves 598 fewer passages", "598",
         "extractor-spread", "/best_minus_worst"),
    ),
    *bound(
        ("studies-audited", "Appendix E", "This appendix audits 3 preregistered studies", "3", CATCHES,
         "/studies/total"),
        ("cross-design-summary-unchanged", "Table 13", "4 of 6 registrations unchanged", "4", COMMANDS,
         f"{CROSS_COMMANDS}/reg_unchanged"),
        ("cross-design-summary-appended", "Table 13", "unchanged, 1 appended", "1", COMMANDS,
         f"{CROSS_COMMANDS}/reg_appended"),
        ("cross-design-summary-changed", "Table 13", "appended, 1 changed", "1", COMMANDS,
         f"{CROSS_COMMANDS}/reg_changed"),
        ("cross-design-summary-found", "Table 13", "175 of 175 found", "175", COMMANDS,
         f"{CROSS_COMMANDS}/cit_found"),
        ("cross-design-round-before", "Appendix F", "findings: 0 before submission", "0", CATCHES,
         f"{CROSS_ROUNDS}/before_submission"),
        ("cross-design-round-1", "Appendix F", "submission, 11 review round", "11", CATCHES,
         f"{CROSS_ROUNDS}/round_1"),
        ("cross-design-round-2", "Appendix F", "round 1, 2 review", "2", CATCHES, f"{CROSS_ROUNDS}/round_2"),
        ("cross-design-round-3", "Appendix F", "round 2, 0 review", "0", CATCHES, f"{CROSS_ROUNDS}/round_3"),
        ("cross-design-round-4", "Appendix F", "round 3, 17 review", "17", CATCHES,
         f"{CROSS_ROUNDS}/round_4"),
        ("cross-design-round-after", "Appendix F", "round 4, 1 after", "1", CATCHES,
         f"{CROSS_ROUNDS}/after_round_4"),
        ("cross-design-prereg-unchanged", "Appendix F", "in the document: 4 unchanged", "4", COMMANDS,
         f"{CROSS_COMMANDS}/reg_unchanged"),
        ("cross-design-prereg-appended", "Appendix F", "unchanged, 1 with text added", "1", COMMANDS,
         f"{CROSS_COMMANDS}/reg_appended"),
        ("cross-design-prereg-changed", "Appendix F", "and 1 changed after its freeze", "1", COMMANDS,
         f"{CROSS_COMMANDS}/reg_changed"),
        ("cross-design-citations-found", "Appendix F", "citations | 0 | 175 of 175 quotations", "175",
         COMMANDS, f"{CROSS_COMMANDS}/cit_found"),
        ("cross-design-citations-library", "Appendix F", "67 of the 94 sources were read", "67", COMMANDS,
         f"{CROSS_COMMANDS}/cit_library"),
        ("cross-design-bibliography-checked", "Appendix F", BIB_AUDIT, "74", COMMANDS,
         f"{CROSS_COMMANDS}/bib_checked"),
        ("cross-design-bibliography-agree", "Appendix F", BIB_AUDIT, "64", COMMANDS,
         f"{CROSS_COMMANDS}/bib_agree"),
        ("cross-design-bibliography-disagree", "Appendix F", BIB_AUDIT, "10", COMMANDS,
         f"{CROSS_COMMANDS}/bib_disagree"),
        ("cross-design-class-absent", "Appendix F", "value or citation absent from the cited source | 9",
         "9", CATCHES, f"{CROSS_CLASSES}/value or citation absent from the cited source"),
        ("cross-design-class-differing", "Appendix F", "value differing from its source | 6", "6", CATCHES,
         f"{CROSS_CLASSES}/value differing from its source"),
        ("cross-design-class-metadata", "Appendix F", "wrong reference metadata | 11", "11", CATCHES,
         f"{CROSS_CLASSES}/wrong reference metadata"),
        ("cross-design-class-unbound", "Appendix F", "number bound to no run | 2", "2", CATCHES,
         f"{CROSS_CLASSES}/number bound to no run"),
        ("cross-design-class-other", "Appendix F", "other record findings | 3", "3", CATCHES,
         f"{CROSS_CLASSES}/other record findings"),
        ("knockout-files-ok", "Appendix G", KNOCK_FILES, "8", COMMANDS, "/audits/knockout/files_ok"),
        ("knockout-files-resealed", "Appendix G", KNOCK_FILES, "4", COMMANDS,
         "/audits/knockout/files_resealed"),
        stated_in="appendix-text",
    ),
    *bound(
        ("census-plans", "Appendix I", "The repository carries 1 frozen plan", "1", "audit-record-census",
         "/declared/registered_plans"),
        ("census-prereg-plans", "Table 17", "prereg | 0 | 1 plan, unchanged", "1", "audit-record-census",
         "/declared/registered_plans"),
        ("census-example-hashes", "Appendix I", "with 2 different hashes", "2", COMMANDS, RESEALED_FILE),
        ("census-results-hashes", "Table 17", "and 1 carries 2 recorded digests", "2", COMMANDS,
         RESEALED_FILE),
        stated_in="literature-census-text",
    ),
]

# The certified-reproductions and failure-cases appendices, bound as the reproducible-science-
# codecheck repository's own manifest (its scripts/build_manifest.py) binds them, to the result
# files copied from it into paper/artifacts/ under a codecheck_ prefix.
CASES = "codecheck-case-counts"
RW = "codecheck-rw-tag-counts"
COUNTS = "codecheck-certificate-counts"
FC = "failure-cases-text"
DETECTED = ("printed value disagrees with the authors' own records",
            "report departs from the registered plan", "references that do not exist")
RW_GROUP = {
    "image": "image (duplication, manipulation, fabrication or concerns)",
    "error": "error stated (analysis, data, methods, results or text)",
    "missing": "original data or images not provided",
    "fabrication": "falsification or fabrication of data",
    "not-reproducible": "results not reproducible",
    "no-information": "limited or no information in the notice",
    "publication": "publication process (paper mill, peer review, rogue editor)",
}
PRINCIPAL = "the principal cause in 8 (6 detected and 2"
MOST_CITED = "nine of the ten most-cited retracted papers"
SHARES = "/share_outside_publication_process"
IN_GROUP = "/count_outside_publication_process"


def rw(group: str, key: str) -> str:
    return f"/groups/{RW_GROUP[group]}{key}"


def years(group: str) -> str:
    return f"/years_from_publication_to_retraction/{RW_GROUP[group]}/median"


def dataset_row(row: str, group: str) -> list[Bound]:
    """One row of the Retraction Watch table: retractions, share, median years."""
    _, count, share, median = (cell.strip() for cell in row.split("|"))
    return [
        *bound((f"fc-dataset-{group}-count", "Table fc-dataset", row, count.replace(",", ""), RW,
                rw(group, IN_GROUP)),
               (f"fc-dataset-{group}-years", "Table fc-dataset", row, median, RW, years(group)),
               stated_in=FC),
        *bound((f"fc-dataset-{group}-share", "Table fc-dataset", row, share.rstrip("%"), RW,
                rw(group, SHARES)), stated_in=FC, conversion="percent"),
    ]


CODECHECK = [
    across("cc-linked-tables", "Appendix C", "Six certificates link fifteen tables", "15", "sum",
           [(f"codecheck-binding-summary-{c}", "/linked_tables") for c in LINKED_CERTIFICATES],
           stated_in=CC),
    over("cc-bind-none", "Appendix C", "Two bind none: their outputs hold formatted text", "0",
         "codecheck-indices", "sum", "/per_certificate/2020-008/bound", "/per_certificate/2020-011/bound",
         stated_in=CC),
    *bound(("cc-memory-differences", "Appendix C", CC_MEMORY, "3", "codecheck-mismatch-review",
            "/by_certificate_checker_and_relation/10/count"), stated_in=CC),
    *bound(
        ("cc-differ-certificates", "Appendix C", "Twelve differ, in two certificates", "2", COUNTS,
         "/certificates_with_a_difference"),
        ("cc-funnel-in-repository", "Table 11", "that output is in the certificate's repository | 9", "9",
         COUNTS, "/funnel/output_in_repository"),
        ("cc-funnel-no-table", "Table 11", "Three certificates describe their files without naming a table",
         "3", COUNTS, "/describe_files_without_naming_a_table"),
        ("cc-funnel-file-not-held", "Table 11", "and four name a file their repository does not hold", "4",
         COUNTS, "/name_a_file_the_repository_does_not_hold"),
        ("cc-binds-certificates", "Appendix C", CC_BINDS, "4", COUNTS, "/certificates_binding_a_number"),
        ("cc-check-time-present", "Appendix C", "sixteen of 37 linked outputs exist at that commit", "16", COUNTS,
         "/linked_outputs_present_at_check_time"),
        ("cc-check-time-linked", "Appendix C", "sixteen of 37 linked outputs exist at that commit", "37", COUNTS,
         "/linked_outputs"),
        stated_in=CC,
    ),
]

FAILURE_CASES = [
    *bound(
        ("fc-body-cases", "Section 1", "Of 34 documented cases of retraction", "34", CASES, "/rows"),
        ("fc-body-detected", "Section 1", "would detect the stated problem in 6", "6", CASES,
         "/cases_under_a_detected_mode"),
    ),
    over("fc-body-unchecked", "Section 1", "evidence as unchecked in 8 more", "8", CASES, "sum",
         "/cases_under_the_mode_reported_as_unchecked", "/of_those_not_under_a_detected_mode"),
    *bound(
        ("fc-cases", "Appendix B", "we examine 34 cases of retraction", "34", CASES, "/rows"),
        ("fc-covered", "Appendix B", "cover a stated problem in 14 of the 34 cases", "14", CASES,
         "/cases_with_a_stated_problem_the_checks_cover"),
        ("fc-covered-of", "Appendix B", "cover a stated problem in 14 of the 34 cases", "34", CASES,
         "/rows"),
        ("fc-principal-detected", "Appendix B", PRINCIPAL, "6", CASES, "/cases_under_a_detected_mode"),
        ("fc-principal-unchecked", "Appendix B", PRINCIPAL, "2", CASES,
         "/cases_under_the_mode_reported_as_unchecked"),
        ("fc-missing-beside", "Appendix B", "alongside the principal cause in 6 others", "6", CASES,
         "/of_those_not_under_a_detected_mode"),
        ("fc-modes-caption", "Table fc-modes", "Failure modes among the 34 cases", "34", CASES, "/rows"),
        *(
            (f"fc-mode-{mode.split()[0]}-{mode.split()[-1]}", "Table fc-modes", f"{mode} | {printed}",
             printed, CASES, f"/by_mode/{mode}")
            for mode, printed in (
                (DETECTED[0], "3"), (DETECTED[1], "1"), (DETECTED[2], "2"),
                ("data could not be produced for audit", "2"), ("error inside the analysis", "9"),
                ("data fabricated or falsified", "8"), ("image manipulation or duplication", "4"),
                ("none of the above", "1"),
            )
        ),
        ("fc-mode-study-description", "Table fc-modes", "its description$^ $ | 4", "4", CASES,
         "/by_mode/study conducted differently from its description"),
        ("fc-modes-total", "Table fc-modes", "Total | 34", "34", CASES, "/rows"),
        ("fc-most-cited", "Appendix B", MOST_CITED, "9", CASES, "/rows_from_the_most_cited_list"),
        ("fc-added-mode", "Appendix B", "add an eleventh for four records that fit none", "4", CASES,
         "/by_mode/study conducted differently from its description"),
        ("fc-rw-retractions", "Appendix B", "which covers 67,530 retractions", "67530", RW, "/retractions"),
        ("fc-rw-publication-process", "Appendix B", "We exclude the 24,166 retractions attributed",
         "24166", RW, rw("publication", "/count")),
        ("fc-rw-remaining", "Appendix B", "group the reason tags of the remaining 43,364", "43364", RW,
         "/retractions_outside_publication_process"),
        ("fc-rw-error", "Appendix B", "Among these, 4,273 retractions (9.9%)", "4273", RW,
         rw("error", IN_GROUP)),
        ("fc-rw-missing", "Appendix B", "and 1,909 (4.4%) cite original data", "1909", RW,
         rw("missing", IN_GROUP)),
        ("fc-rw-missing-delay", "Appendix B", "median of 4.91 years, compared with 1.31 years", "4.91", RW,
         years("missing")),
        ("fc-rw-error-delay", "Appendix B", "median of 4.91 years, compared with 1.31 years", "1.31", RW,
         years("error")),
        ("fc-rw-caption", "Table fc-dataset", "by group of reason tags, among the 43,364", "43364", RW,
         "/retractions_outside_publication_process"),
        ("fc-limits-cases", "Appendix B", "The 34 cases are illustrations", "34", CASES, "/rows"),
        ("fc-limits-analyzed", "Appendix B", "occurs among 43,364 retractions", "43364", RW,
         "/retractions_outside_publication_process"),
        ("fc-limits-image-overlap", "Appendix B", "1,725 of the 2,464 retractions tagged", "1725", RW,
         f"/overlaps/{RW_GROUP['missing']}, and {RW_GROUP['image']}"),
        ("fc-limits-missing-all", "Appendix B", "1,725 of the 2,464 retractions tagged", "2464", RW,
         rw("missing", "/count")),
        stated_in=FC,
    ),
    *bound(
        ("fc-rw-error-share", "Appendix B", "Among these, 4,273 retractions (9.9%)", "9.9", RW,
         rw("error", SHARES)),
        ("fc-rw-missing-share", "Appendix B", "and 1,909 (4.4%) cite original data", "4.4", RW,
         rw("missing", SHARES)),
        ("fc-limits-no-information", "Appendix B", "27.6% of the retractions analyzed are tagged", "27.6",
         RW, rw("no-information", SHARES)),
        stated_in=FC, conversion="percent",
    ),
    *dataset_row("image duplication, manipulation, fabrication or concerns | 7,171 | 16.5% | 4.39", "image"),
    *dataset_row("error stated in analysis, data, methods, results or text | 4,273 | 9.9% | 1.31", "error"),
    *dataset_row("original data or images not provided | 1,909 | 4.4% | 4.91", "missing"),
    *dataset_row("falsification or fabrication of data | 1,659 | 3.8% | 4.27", "fabrication"),
    *dataset_row("results not reproducible | 861 | 2.0% | 2.01", "not-reproducible"),
    *dataset_row("limited or no information in the notice | 11,957 | 27.6% | 0.11", "no-information"),
    over("fc-principal", "Appendix B", PRINCIPAL, "8", CASES, "sum", "/cases_under_a_detected_mode",
         "/cases_under_the_mode_reported_as_unchecked", stated_in=FC),
    over("fc-detected-modes", "Appendix B", "The checks detect three failure modes directly", "6", CASES,
         "sum", *(f"/by_mode/{mode}" for mode in DETECTED), stated_in=FC),
    over("fc-most-cited-list", "Appendix B", MOST_CITED, "10", "codecheck-leaderboard", "count",
         *(f"/rows/{row}/rank" for row in range(10)), stated_in=FC),
    *bound(("fc-table-caption", "Table fc-cases", "Thirty-four cases, grouped by failure mode", "34", CASES,
            "/rows"), stated_in="failure-cases-table-text"),
]

# (id, where, sentence as the rendering prints it, printed value, artifact, pointer)
CLAIMS = [
    *bound(
        ("corpus-quotations", "Appendix A", "under audit carry 2,364",
         "2364", "corpus", "/corpus/quotations"),
        ("unresolved-quotations", "Appendix A", "113 quotations were not found",
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
        ("cross-design-findings", "Section 5.2", "our checks reported 31 further findings",
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
    *MANUSCRIPT,
    *AUDIT_APPENDIX,
    *CERTIFIED,
    *CENSUS,
    *RECORDED_OUTPUT,
    *CODECHECK,
    *RELATED_APPENDIX,
    *FAILURE_CASES,
    *CLOSED,
]

EXIT_CODES = ("Exit 0 is a pass, 1 a finding, and 2 nothing to read.",
              "definition of the exit codes the exit column reports")
CLAIMS_DIR = "paper/prior_art/claims"
FAILURE_CLAIMS = "failure_cases/claims"

# Passages whose numbers are not results of this paper: another work's figures, each with the
# record that pins the quotation it rests on, and prose counts, examples and labels. `repro
# numbers` counts each number here as set aside with the reason, never as bound.
SET_ASIDE = [
    *aside(
        "manuscript-text",
        ("across 863,878 attempted executions of valid notebooks, 24.11% ran without errors and 4.03% "
         "produced the results the notebook recorded",
         f"pimentel2019notebooks: counts and rates that study reports, pinned in "
         f"{CLAIMS_DIR}/pimentel2019notebooks.yaml, claim execution-and-reproduction-rates"),
        ("adduce audits a research repository against 78 rules",
         f"chudasama2026adduce: the rule count adduce's README states, pinned in "
         f"{CLAIMS_DIR}/chudasama2026adduce.yaml, claim manifest-and-rules"),
        ("A rule there returns one of five statuses",
         f"chudasama2026adduce: the five statuses adduce's README lists, pinned in "
         f"{CLAIMS_DIR}/chudasama2026adduce.yaml, claim five-statuses"),
        ("a rule author selects among five flat statuses",
         f"chudasama2026adduce: the same five statuses, pinned in {CLAIMS_DIR}/chudasama2026adduce.yaml, "
         f"claim five-statuses"),
        ("two of them, unknown and not-applicable",
         f"chudasama2026adduce: the two statuses adduce's scoring module leaves out of its score, "
         f"pinned in {CLAIMS_DIR}/chudasama2026adduce_scoring.yaml, claim unscored-statuses"),
        ("surfaced two errors", "the two defects Section 4.1 names one by one"),
        ("Three boundaries of a research project", "the three rows of Table 1, which the caption opens"),
        ("All three are decided the same way", "the three boundaries of Table 1"),
        ("the glob matched nothing, the script exited zero",
         "the exit status of the script in the narrated incident"),
        ("Three positions follow, each against a live alternative",
         "the three positions the paragraph goes on to state"),
        ("a reported 0.42 should name the pointer", "example value in the statement of the position"),
        ("with four implemented variants over a shared engine", "the four evidence kinds of Table 2"),
        ("We instantiate all three in a deployed toolkit", "the three contributions just listed"),
        ("Section 's two incidents fail differently", "the two incidents narrated in Section 1"),
        ("The three boundaries of Table share one architecture", "the three rows of Table 1"),
        ("Two of the three are decided by an evidence assertion",
         "two of the three boundaries of Table 1"),
        ("Four variants are implemented across the other two boundaries",
         "the four evidence kinds of Table 2, over two of the boundaries of Table 1"),
        ("The four implemented variants.", "caption naming the four rows of Table 2"),
        ("correspondence | two artifacts hold the same value",
         "definition of the correspondence kind, which reads two artifacts"),
        ("Three stages. A check must execute, extract, and compare, and the three fail independently",
         "the three stages, execute, extract and compare, named in the sentence"),
        ("The three stages and the flattened view derived from them",
         "caption naming the three stage columns of Table 4"),
        ("The engine therefore reports the three stages", "the three stages of Table 4"),
        ("A value is read from nine formats, such as JSON and Parquet, and a quotation from five, "
         "such as PDF",
         "how many file formats the toolkit's readers accept, a property of the software its "
         "specification lists (SPEC section 3.6), not a measurement"),
        ("The first three write declarations", "the first three rows of Table 3"),
        ("binds that sentence with two assertions",
         "the two assertions, a quote and a metric, the sentence goes on to name"),
        ("2 verified policy strict: passed (0 errors, 0 warnings)",
         "terminal output of the worked example: the two assertions of paper/worked_example/repro.yaml "
         "and the policy's error and warning counts"),
        ("With reported: '19', the stale count of Appendix, the line is marked MISS, the run exits 1, "
         "and the report reads manuscript prints 19",
         "the counterfactual of the worked example: the stale value 19 and the exit status it "
         "would produce"),
        ("and four injected faults each", "the four faults Appendix A lists one by one"),
        ("carries two assertions: that the manuscript states",
         "the two assertions the sentence goes on to name"),
        ("surfaced two defects in this paper's own numbers. Four counts in",
         "the two defects and the four counts the paragraph goes on to describe"),
        ("all four match what the manuscript prints", "the four counts named earlier in the paragraph"),
        ("the specification stated eighteen against a count of nineteen, and a stored figure gave "
         "nineteen where the suite holds 25",
         "the superseded counts the paragraph reports as the defect: eighteen as the toolkit's "
         "docs/SPEC.md stated it at reproducible-science commit 8c670c7, and nineteen as a stored figure "
         "printed it before correction (docs/provenance.md, 2026-10-14); neither is a current count"),
        ("Pinning and checking our own projects with the toolkit surfaced five defect classes",
         "the five rows of Table 8"),
        ("One of the five is a defect in a check", "one of the five rows of Table 8"),
        ("Five defect classes surfaced by running Reproducible Science",
         "caption naming the five rows of Table 8"),
        ("a glob matches nothing, the check exits zero",
         "the exit status in the description of a defect class"),
        ("Two that integrity checking cannot reach", "the two rows of Table 8 the paragraph discusses"),
        ("The four commands of Reproducible Science over a clone of the project's public repository. Two establish their result",
         "caption naming the four rows of Table 9 and the two it singles out"),
        ("27 match in two places", "the failure the sentence describes: a passage standing twice in the "
         "abstract"),
        ("three properties differ", "the three differences the paragraph goes on to list"),
        ("from which of the three stages stopped. The two compose",
         "the three stages of Table 4, and the two systems the paragraph compares"),
        ("reads 0.9489 as 0.9439", "illustrative misreading in the explanation of a trusted extractor"),
        ("those two are consistent", "the two timestamps the previous sentence names"),
        ("one engine reports all three. The three stages exist",
         "the three kinds of declaration and the three stages, named in the paragraph"),
        ("containing four commands", "the four commands the definition lists"),
        ("evaluates each assertion and reports the three stages", "the three stages of Table 4"),
        ("Four faults are injected and the reported outcome recorded",
         "the four faults the paragraph lists one by one"),
        ("The two poppler modes fail in opposite directions", "the two poppler rows of Table 6"),
        ("error 16 Session status",
         "the argument of \\needspace, a layout length detex.py keeps in the rendering; not printed"),
        ("three of the manifest's four checks verify",
         "describes the session in the screenshot of Figure 4"),
        ("with version 0.6.0 on two machines", "the two machines the sentence goes on to name"),
        ("package, whose four commands", "the four commands of Table 3, in the terms table"),
        ("version 26.04.0 on the laptop and 22.12.0 in the container",
         "the pdftotext version each timing record stores as text at /pdftotext of "
         "check_timings_laptop_2026-10-14.json and check_timings_modal_2026-10-14.json; a version, not a quantity"),
        ("2019 16-inch MacBook Pro", "the machine's model name: its screen size"),
        ("Intel Core i7-9750H at 2.6,GHz", "the nominal clock speed in the processor's model name"),
        ("over 4,GB the check takes",
         "the size label of the largest generated project, bytes-004096MB; Table 10 prints its bytes"),
        ("The last four rows hold the assertions", "the last four rows of Table 10"),
    ),
    *aside(
        "appendix-text",
        EXIT_CODES,
        ("review round 1", "label of the first review round"),
        ("review round 2", "label of the second review round"),
        ("review round 3", "label of the third review round"),
        ("review round 4", "label of the fourth review round"),
        ("after round 4", "label of the period after the fourth review round"),
    ),
    *aside(
        "related-work-text",
        ("three\nclasses form its basis",
         f"lebo2013provo: the three classes PROV-O names, pinned in {CLAIMS_DIR}/lebo2013provo.yaml, "
         f"claim entity-activity-agent"),
        ("Table sets the three standards beside the", "the three rows of the table the sentence introduces"),
        ("How three provenance standards represent ordering", "the three rows of the table the caption heads"),
        ("between two records, a registration and a run", "the two records the sentence names"),
        ("of a paper with 99 authors",
         f"hardwig1985dependence: the author count that article reports, pinned in "
         f"{CLAIMS_DIR}/hardwig1985dependence.yaml, claim ninety-nine-authors"),
        ("separates two forms of that dependence", "the two forms the sentence goes on to name"),
        ("in use on 1K to 10K domains",
         f"schemaorg2026claimreview: the usage band schema.org reports, pinned in "
         f"{CLAIMS_DIR}/schemaorg2026claimreview.yaml, claim definition-and-usage"),
        ("requires three of its\nproperties",
         f"google2026factcheck: the three required properties, pinned in "
         f"{CLAIMS_DIR}/google2026factcheck.yaml, claim required-claimreview-properties"),
        ("assertion carries all three", "the three parts of a contract the previous sentence lists"),
        ("reported with its three stages and exactly one of the five",
         "the three stages and five flattened labels of Table 4"),
        ("The invariant holds across the four kinds of", "the four kinds of Table 2"),
        ("two or more matches", "a threshold in the statement of the invariant, not a count"),
        ("so the two match after every build", "the document and the code the sentence names"),
        ("found 32,841 with",
         f"abeysooriya2021genenames: counts that study reports, pinned in "
         f"{CLAIMS_DIR}/abeysooriya2021genenames.yaml, claims supplementary-excel-prevalence and "
         f"gene-name-errors-in-excel-gene-lists"),
        ("errors appeared in 30.9% of the 11,117",
         f"abeysooriya2021genenames: the share and count that study reports, pinned in "
         f"{CLAIMS_DIR}/abeysooriya2021genenames.yaml, claim gene-name-errors-in-excel-gene-lists"),
    ),
    *aside(
        "integrations-text",
        ("3 @l", "detex.py renders the \\multicolumn{3}{@{}l} of each group heading as text; "
         "nothing is printed there"),
        ("the Claude Code plugin's five hooks",
         "how many hooks the Claude Code plugin registers, a property of the software its hook "
         "manifest lists, not a measurement"),
        ("with four numbered options",
         "the options the pull-request bot offers, a property of its design, not a measurement"),
        ("options 3 and 4 written as set_aside", "option numbers in the design just described"),
    ),
    *aside(
        "literature-census-text",
        EXIT_CODES,
        ("Across four passes of separate sessions", "a step of the study's coding procedure"),
        ("The registration rests on three records", "the three records the sentence goes on to list"),
    ),
    *aside(
        "certified-reproductions-text",
        *((certificate, "CODECHECK certificate identifier")
          for certificate in ("2025-018", "2020-025", "2022-001", "2024-020", "2020-011", "2020-008")),
        (CC_ARMS, "the first three and the last three rows of Table 16"),
    ),
    *aside(
        "failure-cases-table-text",
        ("67 trials in five medical journals",
         f"goldacre2019compare: the COMPare study's 67 trials and five journals, pinned in "
         f"{CLAIMS_DIR}/goldacre2019compare.yaml, claims sixty-seven-trials and five-journals"),
        ("two investigations",
         f"taylor_notice_2023: the two investigations the retraction notice names, pinned in "
         f"{CLAIMS_DIR}/taylor_notice_2023.yaml, claim two-investigations"),
        ("2 @l", "detex.py renders the \\multicolumn{2}{@{}l} of each group heading as text; "
         "nothing is printed there"),
        *(
            (passage, f"inside a quotation from the case's primary record, a third party's number; "
                      f"pinned in reproducible-science-codecheck, {FAILURE_CLAIMS}/{record}, claim {claim}")
            for passage, record, claim in (
                ("children ranging from 8 to 11 years old; however, the children were 3 to 5 years old",
                 "wansink_notice_2017.yaml", "case33"),
                ("365 novel outcomes were reported without declaration in total, a mean of 5.4 per trial",
                 "compare_trials.yaml", "case25"),
                ("references 1, 2, 4, 5, 8, 10, 12–18, 20–22, 33, 36, 51, 61, 75, and 79",
                 "72881.yaml", "case21"),
                ("References 2, 3, 6, 7, 8, 18, 20, and 26", "72885.yaml", "case22"),
                ("inappropriate inclusion/omission or alteration of data points in ten (10) figures",
                 "146.yaml", "case07"),
                ("Figures 6a, 6e and 6m", "10_1038_s41586_024_07653_0.yaml", "case01"),
            )
        ),
    ),
    *aside(
        "failure-cases-text",
        ("We define ten failure modes before reading any record",
         "the number of modes the taxonomy defines before any record was read "
         "(reproducible-science-codecheck, failure_cases/CATEGORIES.md, modes 1 to 10); a design fact"),
        ("fit none of the ten", "the ten modes of the same taxonomy, named again"),
        ("Three of the ten modes defined before any record was read",
         "the modes of the same taxonomy with no case among those examined: modes 2, 9 and 10, "
         "named in the sentence"),
    ),
    *aside(
        "certified-reproductions-text",
        ("counting at most 60 per table",
         "the plan's cap on numbers counted per table (reproducible-science-codecheck, PREREG.md, "
         "Measured variables); a design constant, not a result"),
        ("5.273 10^-7",
         "the file's value typeset in math mode, 5.273 x 10^-7: detex.py keeps its digits, and the "
         "number count reads mantissa, base and exponent as three numbers; the stored value is at "
         "/differences/7/stored of codecheck_agreement_summary_2026-10-14.json"),
    ),
    *aside(
        "appendix-text",
        ("found two recorded files edited since they were recorded and one that had moved",
         "the example finding, quoted from paper/audit/audits/cross_design.yaml; it describes catch-log "
         "row cross-23 (2 CHANGED and 1 MISSING), a single finding and not a count the audit makes"),
        ("a property stated for all 28 networks holds only for 27",
         "the example finding, quoted from paper/audit/audits/knockout.yaml; it describes catch-log row "
         "knockout-11 (27/28 networks), a single finding and not a count the audit makes"),
    ),
    *aside(
        "literature-census-text",
        ("the text of three evidence sentences printed by accident",
         "what one access record says was shown: the census ledger's access event seq 60, at the commit "
         "census_audit.json pins, notes 'the text of three evidence spans'; a detail of that record, not "
         "a count the audit makes"),
    ),
    *aside(
        "reexecution-precedents-text",
        ("Three do not, in the sources read", "the three design choices the sentence goes on to list"),
        ("inside an interval from three reruns",
         f"siegel2024corebench: CORE-Bench's three manual reproductions, pinned in "
         f"{CLAIMS_DIR}/siegel2024corebench_reexecution.yaml, claim "
         f"answers-inside-an-interval-from-three-reruns"),
        ("accepts a relative error of at most 5%",
         f"liu2026seerrepro: SEER-Repro's tolerance, pinned in {CLAIMS_DIR}/liu2026seerrepro.yaml, "
         f"claim tolerance"),
        ("Five outcomes are recorded for every regeneration",
         "the five regeneration states of the toolkit's specification (SPEC section 7.6)"),
        ("compares within 5%",
         f"meng2026scientistone: ScientistOne's tolerance, pinned in "
         f"{CLAIMS_DIR}/meng2026scientistone.yaml, claim numeric-sentence-tagged-with-a-log-line"),
        ("differs from it in five ways", "the five differences the paragraph numbers (1) to (5)"),
        ("two of its four checks are majority votes",
         f"meng2026scientistone: pinned in {CLAIMS_DIR}/meng2026scientistone.yaml, claim "
         f"two-of-four-checks-are-majority-votes"),
        ("every score verified on 49 target problems",
         f"nam2026scientisttwo: pinned in {CLAIMS_DIR}/nam2026scientisttwo.yaml, claim "
         f"every-score-verified-on-49-problems"),
        ("is the last of three stages", "the three stages of Table 4"),
        ("re-derive 2,190 atomic claims of 20 published cancer-registry papers from the registry data, "
         "and reproduces 77.4% of them",
         f"liu2026seerrepro: SEER-Repro's corpus and reproduction rate, pinned in "
         f"{CLAIMS_DIR}/liu2026seerrepro.yaml, claim corpus-and-reproduction-rate"),
        ("The two designs start from opposite ends", "the two designs the paragraph compares"),
        ("On 96 agent-written repositories its audit decisions agree with manual annotation for "
         "70.83%, and 28 of the 96 hold",
         f"shen2026reagent: ReAgent's evaluation, pinned in {CLAIMS_DIR}/shen2026reagent.yaml, claim "
         f"agent-audit-of-agent-written-papers"),
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


def assertion(c: Bound) -> dict:
    """The assertion beside a claim's quotation: one stored value, or a statistic of several."""
    if c.statistic:
        return {
            "kind": "aggregate",
            "name": c.id,
            "reported": c.printed,
            "statistic": c.statistic,
            "count": len(c.members),
            "members": [
                {"artifact": a, "locator": {"kind": "tree", "pointer": p}} for a, p in c.members
            ],
        }
    metric = {"kind": "metric", "artifact": c.artifact, "name": c.id, "reported": c.printed,
              "pointer": c.pointer}
    if c.conversion:
        metric["conversion"] = c.conversion
    return metric


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


def inputs(source: pathlib.Path) -> list[tuple[str, pathlib.Path]]:
    """Every file a source `\\input`s, at any depth, each with the id its artifact takes.

    `detex.py` drops the argument of `\\input`, so a rendering of the manuscript holds none of
    the appendices it pulls in; each is rendered and pinned as its own pair of artifacts. The
    generated audit appendix already is, under `appendix`.
    """
    found = []
    for name in INPUT.findall(COMMENT.sub("", source.read_text())):
        path = PAPER / f"{name}.tex"
        if path == appendix.OUT:
            continue
        stem = VERSION.sub("", path.stem).removeprefix("appendix_")
        found.append((stem.replace("_", "-"), path))
        found += inputs(path)
    return found


def build(paper: pathlib.Path) -> dict:
    audits = audit_artifacts()
    records = [a for a in audits if not a["id"].startswith("review-counts-")]
    pulled_in = inputs(paper)
    artifacts = [
        artifact("manuscript", paper, "application/x-tex"),
        artifact("manuscript-text", render(paper), "text/plain"),
        artifact("appendix", appendix.OUT, "application/x-tex"),
        artifact("appendix-text", render(appendix.OUT), "text/plain"),
        *(
            pair
            for name, source in pulled_in
            for pair in (
                artifact(name, source, "application/x-tex"),
                artifact(f"{name}-text", render(source), "text/plain"),
            )
        ),
        artifact("detex", SCRIPTS / "detex.py", "text/x-python"),
        artifact("appendix-generator", SCRIPTS / "build_audit_appendix.py", "text/x-python"),
        artifact("counts-deriver", SCRIPTS / "derive_audit_counts.py", "text/x-python"),
        artifact("unions-deriver", SCRIPTS / "derive_extractor_unions.py", "text/x-python"),
        artifact("bibliography-deriver", SCRIPTS / "derive_bibliography_audit.py", "text/x-python"),
        artifact("codecheck-deriver", SCRIPTS / "derive_codecheck_counts.py", "text/x-python"),
        artifact("corpus", ART / "real_corpus_by_reader.json", "application/json"),
        artifact("unions", ART / "extractor_unions.json", "application/json"),
        artifact("conformance", ART / "conformance_inventory.json", "application/json"),
        artifact("audit-counts", ART / "audit_counts.json", "application/json"),
        artifact("bibliography-audit", ART / "knockout_bibliography_audit.json", "application/json"),
        artifact("bibliography-audit-log", appendix.AUDIT / "knockout_repro_audit.log", "text/plain"),
        artifact("bibliography-audit-record", appendix.AUDIT / "knockout_repro_audit.json",
                 "application/json"),
        artifact("codecheck-indices", ART / "codecheck_indices.json", "application/json"),
        artifact("codecheck-eligibility", ART / "codecheck_eligibility_summary.json",
                 "application/json"),
        artifact("codecheck-counts", ART / "codecheck_counts.json", "application/json"),
        artifact("codecheck-agreement", ART / "codecheck_agreement_summary_2026-10-14.json",
                 "application/json"),
        artifact("corebench-second-run", ART / "corebench_rerun_confirm_comparison.json",
                 "application/json"),
        artifact("corebench-recall", ART / "corebench_recall.json", "application/json"),
        artifact("reader-timings", ART / "reader_timings.json", "application/json"),
        artifact("check-timings", ART / "check_timings_laptop_2026-10-14.json", "application/json"),
        artifact("check-timings-container", ART / "check_timings_modal_2026-10-14.json", "application/json"),
        artifact("check-timings-by-size", ART / "check_timings_by_size_github_runner_2026-10-08.json",
                 "application/json"),
        artifact("census-counts", ART / "census_counts.json", "application/json"),
        artifact("codecheck-mismatch-review", ART / "codecheck_mismatch_review_2026-10-14.json",
                 "application/json"),
        artifact("codecheck-case-counts", ART / "codecheck_case_counts.json", "application/json"),
        artifact("codecheck-rw-tag-counts", ART / "codecheck_rw_tag_counts_2026-10-14.json",
                 "application/json"),
        artifact("codecheck-certificate-counts", ART / "codecheck_certificate_counts_2026-10-14.json",
                 "application/json"),
        artifact("codecheck-leaderboard", ART / "codecheck_leaderboard_snapshot.json",
                 "application/json"),
        *(artifact(f"codecheck-binding-summary-{c}", ART / f"codecheck_binding_summary_{c}.json",
                   "application/json") for c in LINKED_CERTIFICATES),
        artifact("audit-record-census", appendix.AUDIT / "census_audit.json", "application/json"),
        artifact("catch-log-deriver", SCRIPTS / "derive_catch_log_counts.py", "text/x-python"),
        artifact("command-deriver", SCRIPTS / "derive_command_counts.py", "text/x-python"),
        artifact("spread-deriver", SCRIPTS / "derive_extractor_spread.py", "text/x-python"),
        artifact("catch-log-counts", ART / "catch_log_counts.json", "application/json"),
        artifact("command-counts", ART / "command_counts.json", "application/json"),
        artifact("extractor-spread", ART / "extractor_spread.json", "application/json"),
        artifact("numerals-deriver", SCRIPTS / "derive_codecheck_paper_numerals.py", "text/x-python"),
        artifact("codecheck-paper-numerals", ART / "codecheck_paper_numerals.json", "application/json"),
        artifact("figures", PAPER / "figures.json", "application/json"),
        artifact("rna-table5-manifest", ROOT / "corpus" / "manifests" / "rna_table5.yaml", "application/yaml"),
        artifact("rna-table5-nt", ART / "rna_table5_nt_phase6_ps.json", "application/json"),
        artifact("rna-table5-hyenadna", ART / "rna_table5_hyenadna_phase6_ps.json", "application/json"),
        artifact("toolkit-verify-performance", ART / "toolkit_verify_performance_summary.json",
                 "application/json"),
        artifact("layout-deriver", SCRIPTS / "derive_layout_failures.py", "text/x-python"),
        artifact("layout-failures", ART / "layout_failures.json", "application/json"),
        artifact("split-deriver", SCRIPTS / "derive_split_repository_counts.py", "text/x-python"),
        artifact("split-repository-counts", ART / "split_repository_counts.json", "application/json"),
        artifact("manifest-builder", SCRIPTS / "build_manifest.py", "text/x-python"),
        artifact("body-claims-deriver", SCRIPTS / "derive_body_claims.py", "text/x-python"),
        artifact("body-claims", ART / "body_claims.json", "application/json"),
        artifact("coverage-deriver", SCRIPTS / "derive_number_coverage.py", "text/x-python"),
        artifact("number-coverage", ART / "number_coverage.json", "application/json"),
        *audits,
    ]
    by_id = {a["id"]: a for a in artifacts}
    for identifier, (repository, commit, path) in COPIED_FROM.items():
        by_id[identifier]["origin"] = {"repository": repository, "commit": commit, "path": path}

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
                assertion(c),
            ],
        }
        for c in CLAIMS
    ]

    def detex(text: str, source: str) -> dict:
        command = ["python3", by_id["detex"]["path"], by_id[source]["path"], by_id[text]["path"]]
        return regeneration(text, command, [by_id[source], by_id["detex"]], by_id[text])

    def derived(output: str, script: str, sources: list[str]) -> dict:
        return regeneration(
            output,
            [*UV, by_id[script]["path"]],
            [by_id[script], *(by_id[source] for source in sources)],
            by_id[output],
        )

    generator = by_id["appendix-generator"]
    regenerations = [
        detex("manuscript-text", "manuscript"),
        detex("appendix-text", "appendix"),
        *(detex(f"{name}-text", name) for name, _ in pulled_in),
        regeneration(
            "audit-counts",
            [*UV, by_id["counts-deriver"]["path"]],
            [by_id["counts-deriver"], generator, *records],
            by_id["audit-counts"],
        ),
        regeneration("appendix", [*UV, generator["path"]], [generator, *audits], by_id["appendix"]),
        derived("unions", "unions-deriver", ["corpus"]),
        derived("bibliography-audit", "bibliography-deriver",
                ["bibliography-audit-log", "bibliography-audit-record"]),
        derived("codecheck-counts", "codecheck-deriver",
                ["codecheck-indices", "codecheck-eligibility"]),
        derived("catch-log-counts", "catch-log-deriver",
                ["appendix-generator", *(a["id"] for a in records)]),
        derived("command-counts", "command-deriver",
                ["appendix-generator", *(a["id"] for a in records), "audit-record-census"]),
        derived("extractor-spread", "spread-deriver", ["corpus"]),
        derived("codecheck-paper-numerals", "numerals-deriver", ["codecheck-agreement"]),
        derived("layout-failures", "layout-deriver", ["corpus", "toolkit-verify-performance"]),
        regeneration(
            "body-claims",
            [*UV_TOOLKIT, by_id["body-claims-deriver"]["path"], "--paper", paper.stem],
            [by_id["body-claims-deriver"], by_id["manifest-builder"], by_id["detex"],
             by_id["appendix-generator"], by_id["manuscript"]],
            by_id["body-claims"],
        ),
    ]

    return {
        "schema_version": "repro/1",
        "project": "machine-checkable claims (this paper, checked against its own artifacts)",
        "provenance": of_tree(ROOT, generated_by="scripts/build_manifest.py").model_dump(),
        "artifacts": artifacts,
        "claims": claims,
        "regenerations": regenerations,
        "set_aside": [a.model_dump() for a in SET_ASIDE],
    }


def worked_example(manifest: dict) -> dict:
    """The worked example's manifest: the one claim it shows, and the two artifacts it reads."""
    claim = next(c for c in manifest["claims"] if c["id"] == EXAMPLE_CLAIM)
    read = {e["artifact"] for e in claim["evidence"]}
    up = pathlib.Path(*[".."] * len(EXAMPLE.parent.relative_to(ROOT).parts))
    return {
        "schema_version": manifest["schema_version"],
        "project": "the worked example of Section 3: one claim of this paper's manifest",
        "artifacts": [
            {**a, "path": (up / a["path"]).as_posix()} for a in manifest["artifacts"] if a["id"] in read
        ],
        "claims": [claim],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write repro.yaml for one manuscript")
    parser.add_argument("--paper", required=True, help="manuscript stem under paper/, without .tex")
    args = parser.parse_args()
    manifest = build(ROOT / "paper" / f"{args.paper}.tex")
    OUT.write_text(yaml.safe_dump(manifest, sort_keys=False, width=110))
    EXAMPLE.write_text(yaml.safe_dump(worked_example(manifest), sort_keys=False, width=110))
    assertions = sum(len(c["evidence"]) for c in manifest["claims"])
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(manifest['claims'])} claims, "
          f"{assertions} assertions, {len(manifest['artifacts'])} artifacts")


if __name__ == "__main__":
    main()
