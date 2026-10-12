# Prior art

The sources the paper's related-work section is checked against.

| file | what it holds |
|---|---|
| `claims/` | one file per source: the pinned artifact, its sha256, and the passages quoted from it |
| `audits/` | the verdict on each of the manuscript's attributed statements, and the reports behind it |
| `reference/` | every source the claims are pinned to: publisher PDFs, and web pages as served with the date in the filename — **not committed** |
| `audits/bib_audit.json` | the last `citations audit`: every entry, and what its identifier resolved to |
| `prior_art_dois.json` | DOI, title, and authors for each entry, resolved from Crossref |
| `prior_art_arxiv.json` | arXiv identifiers, resolved from the arXiv API |
| `references.bib` | a seventeen-entry subset from an earlier draft; the manuscript builds against `paper/references.bib` |

`reference/` and `.audit-cache/` are gitignored. The PDFs are publisher copies and this
repository is public, so they stay on disk; every claims file carries the URL its source was
fetched from and the sha256 of the bytes that were read, which is enough to fetch them again
and confirm the same bytes came back.

Every identifier here was resolved by title and author against Crossref or DataCite rather
than constructed. Two DOIs guessed during an early draft resolved to real but unrelated
papers, which is the failure this repository's own tooling exists to catch.

## Checking it

```console
uv run --no-project python scripts/build_claims.py          # rewrite claims/, digests computed
citations verify --claims paper/prior_art/claims            # do the quotations resolve?
citations audit  --bib paper/references.bib --json paper/prior_art/audits/bib_audit.json
uv run --no-project python scripts/verification_report.py \
    paper/prior_art/claims paper/prior_art/audits/quote_verification.json
```

`audits/SUMMARY.md` is the readable version: what was checked, what was corrected, and what
could not be obtained.

## The registration

The bibliography and claims paths are registered under `reproducible-science` in
`$CITATIONS_HOME/papers.yaml`, which is what `citations build` reads. The registration pins
absolute paths, so moving or splitting the repository orphans it silently: every command still
exits clean while `build` records zero entries. `citations build --scan` reports an orphaned
path as *configured but not on disk* and writes nothing.

The registration names `paper/references.bib`. Registering the seventeen-entry subset instead
leaves the other thirteen references outside every check, which is the state it was in.

`audit` is the check that reads registry records rather than the paper: a wrong author list on
a correct DOI passes a link checker and everything else. It caught `Nagdir` for `Nadgir` in
CORE-Bench and `Joseph` for `Jemma` Stachelek among the forty-five ReScience authors. Six
entries carry no DOI or PMID --- a W3C Recommendation, a specification, a product page and two
tools --- and are reported unchecked rather than passed.

Claims and audits are kept apart on purpose. A claims file records what a source says and
nothing about whether the manuscript used it well; an audit record carries that judgment and
points back at the claim. Someone who rejects every verdict here can still use the extraction.
