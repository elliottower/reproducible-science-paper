# What the sources say

Every statement in `paper/evidence_assertions_v3.tex` that attributes a fact to an outside
source, checked against a copy of that source pinned by sha256. The extractions are in
`../claims/`; the judgments are here.

Run it again with:

```console
uv run --no-project python scripts/build_claims.py
citations verify --claims paper/prior_art/claims
citations audit  --bib paper/references.bib --json paper/prior_art/audits/bib_audit.json
uv run --no-project python scripts/verification_report.py \
    paper/prior_art/claims paper/prior_art/audits/quote_verification.json
```

## Counts

| | |
|---|---|
| statements enumerated | 29 |
| verified | 15 |
| corrected — the source says something else | 10 |
| corrected — the source does not say it | 1 |
| unchecked — the source could not be obtained | 3 |
| quotations pinned | 56, all resolving |
| bibliography entries audited | 30; 24 checked against a registry, all now agreeing |

## What was corrected

| passage | was | now |
|---|---|---|
| Jupyter notebooks | over 1.4 million notebooks, a quarter executed without error and a small fraction reproduced their recorded results | of 863,878 notebooks with a declared Python version and an unambiguous execution order, 24.11% ran without error and 4.03% reproduced the results stored in the notebook |
| Fellegi–Sunter, three-way decision | match, non-match, or possible match held for clerical review; minimizes the review region | link, non-link, or possible link, the third left for expensive manual resolution; the optimal rule minimizes the probability of the third at fixed levels of the two error rates |
| Fellegi–Sunter, blocking | a comparison key too coarse to discriminate produces candidate sets that swamp the signal | 10<sup>5</sup> records against 10<sup>5</sup> runs to 10<sup>10</sup> comparisons, so the comparisons are restricted to a subspace by blocking, at a cost in error levels the paper analyzes |
| IR traceability | reports the precision-recall tradeoff at scale as a standing limitation | most evaluations stop at precision and recall over datasets of fewer than 500 artifacts, leaving whether the approach scales unanswered |
| literate programming obstacles | packaging, environment drift and documentation staleness | how software is packaged, installed and executed, and how analysis steps are documented |
| Paperclip, unsupported claims | a commit drops them | a commit marks them |
| Paperclip, OCR | PDFs are read with OCR | arXiv PDFs are read with OCR |
| Paperclip, corpus | the corpus is refetched | each corpus source carries a date on which it was last updated |
| Paperclip, digests | no digest is recorded anywhere | no digest is recorded against a claim or its source; the one content hash the documentation describes skips a duplicate upload |
| conformance suite | nineteen fixtures, enumerated as fourteen | nineteen fixtures, enumerated as nineteen |
| `references.bib`, ReScience | Stachelek, Joseph | Stachelek, Jemma |
| `references.bib`, CORE-Bench | Nagdir, Nitya | Nadgir, Nitya |

The Paperclip documentation contradicts itself on the one that matters. The Paper Repos
overview says a commit verifies each claim "(dropping unsupported ones)"; the `repo commit`
reference says "unsupported claims are flagged so you can correct or drop them", and
`repo status` renders a mark for a claim the source does not support. An unsupported claim
survives the commit, so the manuscript now says the commit marks it.

The last two rows were found by `citations audit`, not by reading: both entries carry a live
DOI resolving to the right paper with a wrong name beside it, which is the failure that check
exists for.

## What is unchecked, and why

| passage | why |
|---|---|
| the oracle problem \citep{albizri2021oracle} | *Journal of Information Systems* 35(2):1–16 is paywalled. The publisher PDF returns 403, Unpaywall reports no open location, and no repository copy was found. |
| the `adduce` run output quoted in Related Work | A quotation of the tool's output on one of the author's own repositories. No run record on disk holds it; the string appears only in the manuscript drafts. |
| CORE-Bench reported solved, December 2025 | The Holistic Agent Leaderboard paper is the official leaderboard for CORE-Bench Hard and predates the result. The claim traces to a post by one of the CORE-Bench authors. It sits in a TODO box and stays out of prose. |

Each carries a `\REVIEW{}` tag in the manuscript, counted by `make tags`.

## Two things about the sources

`citations` reads a PDF with `pdftotext -layout` and offers no way to override it, so on a
two-column page every physical line of the extracted text holds a fragment of each column side
by side. A passage spanning two lines of one column has the neighbouring column spliced into
the middle of it and cannot resolve. FEVER, SciFact, Meyer, Pimentel, Winter and Angermeir are
therefore quoted as several consecutive column-line fragments, each of which resolves alone and
which together carry the qualifiers a single short quote would drop. Eleven quotations trip the
`short` warning for this reason.

Two sources are quoted from a rendering rather than from the bytes as served. The Paperclip
documentation is a web page, and `citations` reads `.html` raw, so a quotation crossing an
element boundary does not resolve against it. Both are kept: the `.html` in `../sources/`
carries the digest of what the server sent on 2026-08-25, its sha256 is recorded in the claim
file's note, and the `.txt` beside it — produced by `scripts/render_html_source.py` and pinned
in the usual way — is what the quotations are checked against.

## Bibliographies

`paper/references.bib` is the bibliography the manuscript builds against, and the one audited
here. `paper/prior_art/references.bib` is a seventeen-entry subset left from an earlier draft;
its metadata is clean but it is missing thirteen of the works now cited, and it keys the
Sigstore paper `newman2024sigstore` for a 2022 publication. `bib_audit_prior_art_stale.json`
records its state.
