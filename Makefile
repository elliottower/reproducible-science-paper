# The manuscript `make paper` builds and `make manifest` pins. This is the one place the draft is
# named: the manifest generator takes it as an argument.
PAPER ?= continuous_verification_v15zu_site_ai4sci

# Every standalone supplement. Each is built by `make supplement`, and `make paper` builds them
# alongside the manuscript, so a supplement cannot go stale while the paper is rebuilt.
SUPPLEMENTS := supplement_defects

# Versions are pinned so a rebuild resolves the packages the last one did.
PY := uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2

.PHONY: paper manifest verify supplement tags final clean

# The generated appendix, the counts derived from the catch logs, then the manifest that pins
# both. In that order: the manifest records the digest of each file as it finds it.
manifest:
	@$(PY) python scripts/build_audit_appendix.py
	@$(PY) python scripts/derive_audit_counts.py
	@$(PY) python scripts/derive_bibliography_audit.py
	@$(PY) python scripts/derive_codecheck_counts.py
	@$(PY) --with reproducible-science==0.5.2 python scripts/build_manifest.py --paper $(PAPER)

# Every declared claim against the artifact it names, from the manifest at the repository root.
# Add `--regenerate` to run the commands the manifest records for its generated files.
verify:
	repro verify --policy strict

# Three passes plus bibtex: references resolve on the second, page numbers settle on the third.
# The supplement cites nothing, so two passes settle its cross-references and it needs no bibtex.
# `manifest` runs first, so the PDF is never built from an appendix older than its records.
paper: manifest
	cd paper && pdflatex -interaction=nonstopmode -halt-on-error $(PAPER).tex >/dev/null
	cd paper && bibtex $(PAPER) >/dev/null
	cd paper && pdflatex -interaction=nonstopmode $(PAPER).tex >/dev/null
	cd paper && pdflatex -interaction=nonstopmode $(PAPER).tex >/dev/null
	@$(MAKE) --no-print-directory supplement
	@cd paper && grep -c "undefined" $(PAPER).log | sed 's/^/  undefined refs, paper: /'
	@ls -l paper/$(PAPER).pdf | awk '{print "  pdf:", $$5, "bytes"}'

# Standalone; no bibliography, so two passes settle the cross-references.
supplement:
	@for s in $(SUPPLEMENTS); do \
	  cd paper && pdflatex -interaction=nonstopmode -halt-on-error $$s.tex >/dev/null && \
	  pdflatex -interaction=nonstopmode -halt-on-error $$s.tex >/dev/null && cd ..; \
	  echo "  $$s: $$(grep -c undefined paper/$$s.log) undefined refs, \
$$(ls -l paper/$$s.pdf | awk '{print $$5}') bytes"; \
	done

# Every unresolved item is a tag, never a sentence. A placeholder written as prose ships.
# The checker globs paper/*.tex, so the supplement's tags are counted with the paper's.
tags:
	@uv run --no-project python scripts/check_tags.py --paper $(PAPER)

# Refuses while any tag remains.
final: paper
	@uv run --no-project python scripts/check_tags.py --paper $(PAPER) --final

clean:
	cd paper && rm -f *.aux *.bbl *.blg *.log *.out *.toc
