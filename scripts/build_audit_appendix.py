"""Render the audit appendices from one YAML file per audited paper.

Each file under `paper/audit/audits/` names an audit record written by `paper/audit/run_audit.py`
and a catch log coded under `paper/audit/catch_logs/PROTOCOL.md`. Every audit is rendered under
the same headings, and every number printed is read from the record at a declared pointer,
extracted from a recorded command's output by a declared pattern, or counted from the catch log.
A placeholder that does not resolve, an example naming a catch the log does not hold, or a
severity outside the protocol's vocabulary stops the build.

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \
        python scripts/build_audit_appendix.py
"""

from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

import yaml
from pydantic import BaseModel, ConfigDict, Field

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT = ROOT / "paper" / "audit"
OUT = ROOT / "paper" / "generated" / "audit_appendix.tex"

# The protocol's severity vocabulary, in the order the tables print it, with the column label.
SEVERITIES = (("claim", "claim"), ("integrity", "source"), ("record", "record"), ("cosmetic", "cosmetic"))

# The protocol's defect classes, grouped for the comparison against review.
CLASS_GROUPS = (
    ("value or citation absent from the cited source", ("quotation not in source",)),
    ("value differing from its source", ("value mismatch",)),
    ("wrong reference metadata", ("wrong reference metadata",)),
    ("number bound to no run", ("value bound to nothing",)),
)
OTHER_CLASSES = "other record findings"

REVIEW_KINDS = (
    ("design and argument", "design/argument"),
    ("reporting and presentation", "reporting/presentation"),
    ("statistical method", "statistical method"),
    ("references", "references/sources"),
    ("code and data availability", "code/data availability"),
    ("other", "other"),
)

WIDE = (
    r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.13\textwidth}r"
    r">{\raggedright\arraybackslash}p{0.39\textwidth}>{\raggedright\arraybackslash}p{0.34\textwidth}@{}}"
)


class AuditError(Exception):
    """An audit file that cannot be rendered as written."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Carried(Strict):
    what: str
    pointer: str
    one: str | None = None


class Count(Strict):
    pointer: str | None = None
    step: str | None = None
    lines: str | None = None
    value: str | None = None


class Check(Strict):
    command: str
    step: str
    found: str
    could_not: str


class Example(Strict):
    catch: str
    text: str


class Summary(Strict):
    plans: str
    quotations: str
    ledger: str


class Rounds(Strict):
    field: str
    labels: dict[str, str]


class Audit(Strict):
    id: str
    order: int
    title: str
    citation: str
    description: str
    repository: str
    record: str
    catch_log: str
    excluded_ids: list[str] = Field(default_factory=list)
    review_counts: str | None = None
    summary: Summary
    carries: list[Carried]
    counts: dict[str, Count] = Field(default_factory=dict)
    checks: list[Check]
    rounds: Rounds | None = None
    examples: list[Example] = Field(default_factory=list)


def at(record: dict, pointer: str) -> object:
    """Resolve an RFC 6901 pointer; a pointer that does not resolve is an error."""
    node: object = record
    for part in pointer.lstrip("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or key not in node:
            raise AuditError(f"pointer {pointer} does not resolve at {key!r}")
        node = node[key]
    return node


def number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditError(f"expected an integer, found {value!r}")
    return f"{value:,}".replace(",", "{,}")


def tex(text: str) -> str:
    """Plain text to LaTeX: backticks mark code, and the characters TeX reserves are escaped."""
    def code(match: re.Match[str]) -> str:
        return r"\code{" + match.group(1).replace("--", "-{}-").replace("_", r"\_") + "}"

    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append(code(re.match(r"`([^`]+)`", part)))
        else:
            out.append(re.sub(r"([&%#_])", r"\\\1", part))
    return "".join(out)


class Rendered:
    """One audit, with its record and catch log loaded and its counts resolved."""

    def __init__(self, audit: Audit) -> None:
        self.audit = audit
        self.record = json.loads((AUDIT / audit.record).read_text())
        self.catches = [json.loads(line) for line in (AUDIT / audit.catch_log).read_text().splitlines() if line.strip()]
        known = {row["id"] for row in self.catches}
        for missing in [i for i in audit.excluded_ids if i not in known] + [e.catch for e in audit.examples if e.catch not in known]:
            raise AuditError(f"{audit.id}: the catch log holds no row {missing}")
        allowed = {severity for severity, _ in SEVERITIES}
        for row in self.catches:
            if row["severity"] not in allowed:
                raise AuditError(f"{audit.id}: {row['id']} carries severity {row['severity']!r}")
        self.values = {name: self.count(name, spec) for name, spec in audit.counts.items()}

    def output(self, step: str) -> str:
        return str(at(self.record, f"/steps/{step}/output"))

    def count(self, name: str, spec: Count) -> int:
        if spec.pointer:
            found = at(self.record, spec.pointer)
        elif spec.step and spec.lines:
            found = len(re.findall(spec.lines, self.output(spec.step), flags=re.M))
        elif spec.step and spec.value:
            match = re.search(spec.value, self.output(spec.step), flags=re.M)
            if not match:
                raise AuditError(f"{self.audit.id}: count {name} matches nothing in {spec.step}")
            found = int(match.group(1))
        else:
            raise AuditError(f"{self.audit.id}: count {name} names neither a pointer nor a pattern")
        if isinstance(found, bool) or not isinstance(found, int):
            raise AuditError(f"{self.audit.id}: count {name} is not an integer")
        return found

    def fill(self, text: str) -> str:
        def resolve(match: re.Match[str]) -> str:
            name = match.group(1)
            if name.startswith("/"):
                return number(at(self.record, name))
            if name not in self.values:
                raise AuditError(f"{self.audit.id}: no count named {name}")
            return number(self.values[name])

        return re.sub(r"\{([^{}]+)\}", resolve, tex(text).replace(r"\_", "_")).replace("_", r"\_") if "{" in text else tex(text)

    @property
    def toolkit(self) -> list[dict]:
        return [row for row in self.catches if row["id"] not in self.audit.excluded_ids]

    @property
    def label(self) -> str:
        return "sec:audit-" + self.audit.id.replace("_", "-")

    def section(self) -> str:
        audit = self.audit
        commit = str(at(self.record, "/pin/commit"))[:7]
        carried = []
        for c in audit.carries:
            held = at(self.record, c.pointer)
            carried.append(f"{number(held)} {tex(c.one if held == 1 and c.one else c.what)}")
        lines = [
            rf"\section{{Audit: {tex(audit.title)}}}",
            rf"\label{{{self.label}}}",
            "",
            rf"\paragraph{{Description.}} {audit.description} \citep{{{audit.citation}}}."
            rf"\footnote{{\url{{{audit.repository}}}, commit \code{{{commit}}}.}}",
            "The clone carries " + ", ".join(carried[:-1]) + " and " + carried[-1] + ".",
            "",
        ]
        toolkit = Counter(r["severity"] for r in self.toolkit)
        split = ", ".join(f"{number(toolkit[severity])} {shown}" for severity, shown in SEVERITIES)
        lines += [rf"\paragraph{{All Findings.}} {number(len(self.toolkit))}: {split}.", ""]

        if audit.examples:
            lines += [r"\paragraph{Example Finding.} " + " ".join(tex(e.text) for e in audit.examples), ""]
        if audit.rounds:
            by_round = Counter(row[audit.rounds.field] for row in self.toolkit)
            unknown = set(by_round) - set(audit.rounds.labels)
            if unknown:
                raise AuditError(f"{audit.id}: rounds {sorted(unknown)} have no label")
            cells = ", ".join(f"{number(by_round[key])} {shown}" for key, shown in audit.rounds.labels.items())
            lines += [rf"\paragraph{{Reviews.}} Of the {number(len(self.toolkit))} findings: {cells}.", ""]

        lines += [
            r"\begin{table}[!ht]",
            r"\centering",
            r"\small",
            rf"\caption{{{tex(audit.title)}: what each command found in a clone at the pinned commit, and "
            r"what it could not establish. Exit 0 is a pass, 1 a finding, and 2 nothing to read.}",
            rf"\label{{tab:{self.label[4:]}-clone}}",
            WIDE,
            r"\toprule",
            r"command & exit & what it found & what it could not establish \\",
            r"\midrule",
        ]
        for check in audit.checks:
            code = number(at(self.record, f"/steps/{check.step}/exit"))
            lines.append(rf"\code{{{check.command}}} & {code} & {self.fill(check.found)} & {self.fill(check.could_not)} \\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]

        if audit.review_counts:
            lines += self.review() + [""]
        return "\n".join(lines)

    def review(self) -> list[str]:
        review = json.loads((AUDIT / self.audit.review_counts).read_text())
        kinds = [(shown, review["points_by_kind_total"][key]) for shown, key in REVIEW_KINDS]
        if sum(n for _, n in kinds) != review["points_total"]:
            raise AuditError(f"{self.audit.id}: review points by kind do not sum to the total")
        classes = Counter(row["class"] for row in self.toolkit)
        grouped = [(shown, sum(classes.pop(c, 0) for c in members)) for shown, members in CLASS_GROUPS]
        grouped.append((OTHER_CLASSES, sum(classes.values())))
        def half(header: str, unit: str, cells: list[tuple[str, int]], total: int) -> list[str]:
            return [
                r"\begin{tabular}[t]{@{}lr@{}}",
                r"\toprule",
                rf"{header} & {unit} \\",
                r"\midrule",
                *[rf"{name} & {number(count)} \\" for name, count in cells],
                r"\midrule",
                rf"Total & {number(total)} \\",
                r"\bottomrule",
                r"\end{tabular}",
            ]

        lines = [
            r"\begin{table}[!ht]",
            r"\centering",
            r"\small",
            rf"\caption{{Reviewer comments ({number(review['distinct_reviewers'])} reviewers, "
            rf"{number(review['reports'])} reports) and findings for the cross-design study, by kind.}}",
            rf"\label{{tab:{self.label[4:]}-review}}",
            *half("Reviewer comments", "Count", kinds, review["points_total"]),
            r"\hspace{3em}",
            *half("Findings", "Count", grouped, len(self.toolkit)),
            r"\end{table}",
        ]
        return lines


#: Audits written by hand and not rendered from paper/audit/audits: the literature census, in
#: paper/appendix_literature_census.tex, whose study is still running.
IN_PROGRESS = 1

SPELLED = {1: "one", 2: "two", 3: "three"}


def spelled(count: int) -> str:
    return SPELLED[count]


def summary(rendered: list[Rendered]) -> str:
    lines = [
        r"\section{Reproducible Science Audits}",
        r"\label{sec:catches}",
        "",
        "This appendix audits " + number(len(rendered) + IN_PROGRESS) + " preregistered studies conducted with Reproducible Science:",
        spelled(len(rendered)) + " under journal review and " + spelled(IN_PROGRESS) + " in progress. Each audit gives a",
        "description of the study, an example finding, what each command found in its repository,",
        r"and the findings made while it was written. Table~\ref{tab:audits-clone} gives the result from",
        r"a clone for the " + spelled(len(rendered)) + r" under review, and Table~\ref{tab:catches} their findings.",
        "",
        r"\begin{table}[!ht]",
        r"\centering",
        r"\small",
        r"\caption{What Reproducible Science established from a clone of each project, at the pinned commit.}",
        r"\label{tab:audits-clone}",
        r"\begin{tabular}{@{}>{\raggedright\arraybackslash}p{0.19\textwidth}c>{\raggedright\arraybackslash}p{0.25\textwidth}>{\raggedright\arraybackslash}p{0.17\textwidth}>{\raggedright\arraybackslash}p{0.16\textwidth}@{}}",
        r"\toprule",
        r"project & appendix & registered plans & quotations & ledger \\",
        r"\midrule",
        *[rf"{tex(i.audit.title)} & \ref{{{i.label}}} & {i.fill(i.audit.summary.plans)} & {i.fill(i.audit.summary.quotations)} & {i.fill(i.audit.summary.ledger)} \\" for i in rendered],
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
        "",
        "Findings are coded from each project's records: commits, ledger events, plan logs, claim files and",
        "session transcripts. A finding counts",
        "when a command, a script that performed the same check before the command existed, a hook, or an act",
        "Reproducible Science requires (sealing an input, binding a number, pinning a",
        "quotation) exposed it and a record says so. The coding rules were fixed before the records were read.",
        "Defects found by a person or raised in review are not counted as findings.",
        "",
        r"\begin{table}[!ht]",
        r"\centering",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\caption{Findings, by project and severity. A \emph{claim} finding would change a",
        r"reported number or conclusion. A \emph{source} finding is a value or reference attributed to a work",
        r"that does not contain it. A \emph{record} finding is a break in provenance that leaves every reported number",
        r"correct.}",
        r"\label{tab:catches}",
        r"\begin{tabular}{@{}lcrrrrr@{}}",
        r"\toprule",
        "project & appendix & " + " & ".join(shown for _, shown in SEVERITIES) + r" & total \\",
        r"\midrule",
    ]
    for item in rendered:
        by = Counter(row["severity"] for row in item.toolkit)
        cells = " & ".join(number(by[severity]) for severity, _ in SEVERITIES)
        lines.append(rf"{tex(item.audit.title)} & \ref{{{item.label}}} & {cells} & {number(len(item.toolkit))} \\")
    every = Counter(row["severity"] for item in rendered for row in item.toolkit)
    totals = " & ".join(number(every[severity]) for severity, _ in SEVERITIES)
    lines += [r"\midrule", rf"total & & {totals} & {number(sum(every.values()))} \\"]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    return "\n".join(lines)


def load() -> list[Rendered]:
    audits = [Audit.model_validate(yaml.safe_load(path.read_text())) for path in sorted((AUDIT / "audits").glob("*.yaml"))]
    if not audits:
        raise AuditError("no audit files under paper/audit/audits")
    return [Rendered(audit) for audit in sorted(audits, key=lambda a: a.order)]


def build() -> str:
    rendered = load()
    head = "% Generated by scripts/build_audit_appendix.py from paper/audit/audits/*.yaml. Do not edit.\n"
    return head + summary(rendered) + "".join("\n\\clearpage\n" + item.section() for item in rendered)


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(build())
    print(f"  wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
