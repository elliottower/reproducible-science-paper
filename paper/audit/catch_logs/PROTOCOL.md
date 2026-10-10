# Catch log: what the toolkit caught in two projects

Written 2026-10-03, before any record was read for this purpose. Not a frozen registration: a
descriptive census with its coding rules fixed here, so that what counts as a catch is not
decided after seeing the records.

## Repositories

- `~/Documents/GitHub/knockout-epistasis-dynamics` (60 commits, 2026-07-28 to 2026-09-22)
- `~/Documents/GitHub/ecological-bias-covid` (44 commits, 2026-07-07 to 2026-10-03)

## What counts as a catch

A **catch** is a defect in a research artifact (manuscript text or number, result file, data,
analysis code, registered plan, bibliography or quotation) that

1. was surfaced by a toolkit command (`prereg`, `results`, `citations`, `repro`), by one of their
   Claude Code hooks, or by an act the toolkit requires (sealing, binding a claim, pinning a
   quotation, freezing a plan) that exposed it; and
2. has a record: a commit, a ledger event, a plan log entry, a claims file, a notebook entry or a
   session transcript line saying what was found.

A defect found by a person or an AI reviewer with no toolkit involvement is recorded separately
as a **non-tool catch**, for contrast, and never counted as a catch.

A defect in the toolkit itself, found while using it on the project, is recorded as a
**tool defect**, separately.

## Fields per catch

| field | values |
|---|---|
| id | repo-short + number |
| repo | knockout / ecological |
| found | date, from the record |
| introduced | date if the record shows it, else `unknown` |
| artifact | manuscript number, manuscript text, result file, data, code, plan, bibliography, quotation |
| class | value mismatch; stale value (correct once, later out of date); value bound to nothing; wrong reference metadata; quotation not in source; plan changed after freeze; recorded file no longer matches; check that examined nothing; ordering violation (claim after outcomes seen); other (say what) |
| caught by | the command or hook, verbatim |
| severity | **claim**: would change a reported number or conclusion; **integrity**: would read as misconduct or fabrication (a reference naming the wrong work, a silently edited plan); **record**: provenance broken but no reported number wrong; **cosmetic**: last-digit or formatting |
| fixed | yes (commit) / no / recorded only |
| evidence | one or more pointers: commit hash, ledger event seq, plan log line, file path and line, transcript file and line |
| confidence | **direct**: the record says the tool found it; **inferred**: the fix commit or transcript implies it but does not say so |

## Sources, in this order

1. `git log` with full messages, and diffs where a message is ambiguous.
2. `.results/ledger.jsonl` events, and `results verify --files` / `results coverage` output now.
3. Every `PREREG.md` log entry.
4. `claims/` and any `references.resolved.yaml` or audit output files.
5. `NOTEBOOK.md`, `docs/`, `planning/`, review files.
6. Claude Code session transcripts that mention the repo, under
   `~/.claude/projects/-Users-elliottower-Documents-GitHub-factorization-circuits/` (and the
   repo's own project folder if any). Searched for tool output strings, never read wholesale.

## Denominators, reported with the counts

Commits, ledger events, claim records and quotations, registered plans, manuscript numbers
(`results coverage`), and the period covered.

## What the log can and cannot show

It shows that the tools surfaced real defects in real work and what kinds. It undercounts,
because only fixes that left a record can be found. It is one author's work, so it says nothing
about how often published science contains these defects.
