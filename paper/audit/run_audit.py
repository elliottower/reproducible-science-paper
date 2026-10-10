"""Run prereg, results, citations and repro over one repository at a pinned revision.

Point it at a target file; the target names the repository, the commit, the commands to run
and where the repository keeps the files worth counting:

    uv run --with pyyaml python paper/audit/run_audit.py --target paper/audit/target.yaml
    uv run --with pyyaml python paper/audit/run_audit.py --target paper/audit/self_target.yaml

The record and the log are written beside the target and named after it, so two audits in one
repository do not overwrite each other. Every number reported from an audit is read from the
record; nothing is typed by hand.

The repository is cloned at the commit the target pins, so the audit runs against the bytes
that commit names rather than against a working tree. A tree digest that disagrees with the
pin is recorded and the run continues, because a moved repository is a finding and not a
reason to report nothing.

Requires citations, results-cli, prereg and reproducible-science on PATH.
"""

from __future__ import annotations

import argparse
import pathlib

from audit_lib import run

HERE = pathlib.Path(__file__).resolve().parent


def main(target: str, offline: bool = False, commit: str = "") -> int:
    path = pathlib.Path(target)
    if not path.is_absolute():
        path = (pathlib.Path.cwd() / path).resolve()
    stem = path.stem.removesuffix("_target") or path.stem
    name = "repo_audit" if stem in ("target", "repo") else f"{stem}_audit"
    return run(
        target_path=path,
        # One cache per target, so two audits do not share a checkout of different repositories.
        cache=pathlib.Path.home() / ".cache" / f"repo-audit-{stem}",
        record_path=path.parent / f"{name}.json",
        log_path=path.parent / f"{name}.log",
        offline=offline,
        commit=commit,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=str(HERE / "target.yaml"), help="the target file to audit")
    ap.add_argument("--offline", action="store_true", help="skip steps that reach a registry")
    ap.add_argument("--commit", default="", help="audit this revision instead of the pinned one")
    raise SystemExit(main(**vars(ap.parse_args())))
