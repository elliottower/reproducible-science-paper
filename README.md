# Reproducible Science: Machine-Checkable Claims from Preregistration to Publication

The manuscript, its evidence manifest, its results ledger and the artifacts they pin, for the
paper accepted at the AI for Science workshop (NeurIPS 2026). The software it describes is at
[elliottower/reproducible-science](https://github.com/elliottower/reproducible-science).

## Check the paper against its own artifacts

```
make verify
```

runs `repro verify` over `repro.yaml` under the strict policy. 38 claims in the manuscript are
bound by 76 assertions over 25 pinned artifacts, and the expected result is `76 verified`. Edit a
number in `paper/artifacts/` and the check reports which claim it breaks.

## Build

```
make paper       # the manuscript and its supplement (pdflatex, bibtex)
make manifest    # rewrite the generated appendix, the derived counts and the manifest
make final       # build, and refuse while any unresolved tag remains
```

## Layout

| path | what it is |
|---|---|
| `paper/continuous_verification_v15zu_site_ai4sci.tex` | the manuscript |
| `paper/appendix_*.tex`, `paper/generated/` | appendices the manuscript inputs; `generated/` is written by `make manifest` |
| `repro.yaml` | the evidence manifest: claims, assertions, artifact digests |
| `.results/` | the results ledger: sealed inputs, recorded runs, and each manuscript sentence bound to a run |
| `paper/artifacts/` | the result files the manifest and the ledger pin |
| `paper/audit/` | the audit files, tool records and finding logs behind the audits appendix |
| `scripts/` | the scripts that wrote each artifact, the manifest and the generated appendix |
| `paper/prior_art/` | the quotations the paper pins from the work it cites, each with its source's URL and SHA-256 |
| `evaluation/` | the CORE-Bench recall measurement of Section 4.3 |

## What is not here

- The sources of the quotation corpus and of the paper's own quotations: publishers' PDFs and
  other projects' web pages. `paper/prior_art/claims/` holds each quotation with the URL its
  source was fetched from and the SHA-256 of the bytes read.
- The audited repositories. Each audit names its repository and commit.
- The literature census's study repository, which is not yet public. The audit output over it
  is in `paper/audit/census_audit.*`.
- The CODECHECK study's repository. Its result files are copied into `paper/artifacts/`.

## Differences from the author's working copy

Three file paths in one finding log, `paper/audit/catch_logs/cross_design/catch_log.jsonl`, are
replaced by bracketed labels, and local paths are replaced by placeholders in the reports under
`paper/prior_art/`. No asserted value reads those fields. The manifest was regenerated here, so
it pins the files as published. The ledger was not rewritten: `results verify` reports its chain
intact, and `results verify --files` lists that finding log as changed, together with files that
were recorded again after a later run or regenerated after they were first sealed.
