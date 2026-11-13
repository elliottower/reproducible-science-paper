# Reproducible Science: Machine-Checkable Claims from Preregistration to Publication

The manuscript, its evidence manifest, its results ledger and the artifacts they pin, for the
paper accepted at the AI for Science workshop (NeurIPS 2026). The software it describes is at
[elliottower/reproducible-science](https://github.com/elliottower/reproducible-science).

## Check the paper against its own artifacts

```
make verify
```

runs `repro verify` over `repro.yaml` under the strict policy. 531 claims in the manuscript are
bound by 1,062 assertions over 83 pinned artifacts, and the expected result is `1062 verified`.
Edit a number in `paper/artifacts/` and the check reports which claim it breaks.

## Build

```
make paper       # the manuscript and its supplement (pdflatex, bibtex)
make manifest    # rewrite the generated appendix, the derived counts and the manifest
make final       # build, and refuse while any unresolved tag remains
```

## Layout

| path | what it is |
|---|---|
| `paper/continuous_verification_v15zzn_ai4sci.tex` | the manuscript; `paper/continuous_verification_v15zzn_ai4sci.pdf` is the camera-ready PDF |
| `paper/appendix_*.tex`, `paper/generated/` | appendices the manuscript inputs; `generated/` is written by `make manifest` |
| `repro.yaml` | the evidence manifest: claims, assertions, artifact digests |
| `paper/worked_example/repro.yaml` | the one-claim manifest of the worked example in Section 3, written by `make manifest` |
| `.results/` | the results ledger: sealed inputs, recorded runs, and each manuscript sentence bound to a run |
| `paper/artifacts/` | the result files the manifest and the ledger pin |
| `paper/audit/` | the audit files, tool records and finding logs behind the audits appendix |
| `scripts/` | the scripts that wrote each artifact, the manifest and the generated appendix |
| `paper/prior_art/` | the quotations the paper pins from the work it cites, each with its source's URL and SHA-256 |
| `corpus/manifests/rna_table5.yaml` | another project's evidence manifest, read by the defect classes of Section 5.1 |
| `evaluation/` | the CORE-Bench recall measurement of Section 4.3 |

## What is not here

- The sources of the quotation corpus and of the paper's own quotations: publishers' PDFs and
  other projects' web pages. `paper/prior_art/claims/` holds each quotation with the URL its
  source was fetched from and the SHA-256 of the bytes read. Without the sources,
  `citations verify --claims paper/prior_art/claims` reports every quotation as unchecked.
- The audited repositories. Each audit names its repository and commit.
- The literature census's study repository,
  [elliottower/proteome-mr-claim-audit](https://github.com/elliottower/proteome-mr-claim-audit),
  audited at its commit `d833d00` (`62f181c` before a history rewrite, the hash the audit files
  record). The audit output over it is in `paper/audit/census_audit.*`.
- The CODECHECK study's repository. Its result files are copied into `paper/artifacts/`.

## Differences from the author's working copy

Three file paths in one finding log, `paper/audit/catch_logs/cross_design/catch_log.jsonl`, are
replaced by bracketed labels, and local paths are replaced by placeholders in the reports under
`paper/prior_art/`. No asserted value reads those fields. The manifest, and the two count files
that record the finding log's digest, `paper/artifacts/audit_counts.json` and
`paper/artifacts/catch_log_counts.json`, were regenerated here, so they pin the files as
published. The ledger was not rewritten: `results verify` reports its chain intact, and
`results verify --files` lists three files as changed since they were recorded: the finding log,
`paper/artifacts/audit_counts.json` and `repro.yaml`.
