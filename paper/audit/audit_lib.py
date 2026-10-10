"""Run the four tools over a repository at a pinned revision, and record what they said.

The mechanics only. Which repository, which commands and which of its files to count are
declared in a target file and passed in, because two audits of two repositories differed in
nothing else and were kept as two scripts that drifted apart.

A count is reported only where the target declares where to find it. A repository that
declares no ledger gets no `ledger_events` key rather than a zero: nothing was examined, which
is a different fact from nothing being there, and it is the distinction the audited tools
exist to preserve.
"""

from __future__ import annotations

import importlib.metadata
import json
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone

import yaml

TIMEOUT = 600


class Step:
    """One command, its exit code, and everything it printed."""

    def __init__(self, name: str, argv: list[str], cwd: pathlib.Path, note: str = "") -> None:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT)
        self.name = name
        self.argv = argv
        self.note = note
        self.exit = proc.returncode
        self.out = (proc.stdout + proc.stderr).rstrip("\n")

    def as_dict(self) -> dict:
        return {"command": " ".join(self.argv), "exit": self.exit, "note": self.note,
                "output": self.out}


def git(root: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def checkout(repository: str, commit: str, cache: pathlib.Path) -> pathlib.Path:
    """The repository at the pinned commit, cloned under `cache` if not already there.

    The clone goes outside any repository. `repro verify` and `prereg check` walk upwards for
    a manifest and a plan, so a checkout placed inside the auditing repository binds to *its*
    manifest and reports those assertions as the audited repository's. That happened, and the
    location is the fix.
    """
    into = cache / "checkout"
    if not (into / ".git").is_dir():
        into.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--quiet", repository, str(into)], check=True,
                       timeout=TIMEOUT)
    # A local path clone is reached again for revisions made after it was cached.
    subprocess.run(["git", "fetch", "--quiet", "--all"], cwd=into, timeout=TIMEOUT)
    subprocess.run(["git", "checkout", "--quiet", "--force", commit], cwd=into, check=True,
                   timeout=TIMEOUT)
    return into


def pin_of(root: pathlib.Path, target: dict) -> dict:
    """The revision actually checked out, against the one the target names."""
    pin = {
        "commit": git(root, "rev-parse", "HEAD"),
        "tree": git(root, "rev-parse", "HEAD^{tree}"),
        "dirty": bool(git(root, "status", "--porcelain")),
    }
    pin["commit_matches_pin"] = pin["commit"] == target["commit"]
    pin["tree_matches_pin"] = pin["tree"] == target.get("tree")
    return pin


#: The command each tool is reached by, and the distribution that provides it.
TOOLS = {
    "citations": "citations",
    "results": "results-cli",
    "prereg": "prereg",
    "repro": "reproducible-science",
}


def tool_versions() -> dict[str, str]:
    """What is installed, read from each tool rather than declared in the target.

    A hand-typed version is a second artifact recording the same fact as the installed
    distribution, and the two drift silently: this audit ran twice over identical bytes and
    returned different verdicts, because `citations` had begun enforcing the `extract_cmd`
    allowlist in between, while both records went on reporting the version somebody typed.

    Each tool is installed in its own environment, so the version is read from the interpreter
    that tool's entry point names rather than from this process, which has none of them.
    """
    out = {}
    for command, distribution in TOOLS.items():
        out[distribution] = "not installed"
        if not (binary := shutil.which(command)):
            continue
        try:
            shebang = pathlib.Path(binary).read_text(errors="replace").splitlines()[0]
        except (OSError, IndexError):
            continue
        interpreter = shebang[2:].strip() if shebang.startswith("#!") else ""
        if not interpreter:
            continue
        got = subprocess.run(
            [interpreter, "-c",
             f"import importlib.metadata as m; print(m.version({distribution!r}))"],
            capture_output=True, text=True, timeout=60,
        )
        if got.returncode == 0 and got.stdout.strip():
            out[distribution] = got.stdout.strip()
    return out


def bib_entries(bib: pathlib.Path) -> int:
    text = bib.read_text()
    return text.count("\n@") + int(text.startswith("@"))


def declared(root: pathlib.Path, layout: dict) -> dict:
    """What the repository offers for checking, counted from its own files.

    Read here rather than taken from any tool's summary: a count derived from a verification
    report cannot distinguish a declaration nothing examined from one that was examined and
    passed.

    Every entry is conditional on the target declaring where to look. Keys are absent, never
    zero, for a layout that does not name them.
    """
    out: dict = {
        "tracked_files": len(git(root, "ls-files").splitlines()),
        "registered_plans": len(list(root.glob("**/PREREG.md"))),
        "evidence_manifests": len(list(root.glob("**/repro.yaml"))),
        "results_ledgers": len(list(root.glob("**/.results/ledger.jsonl"))),
    }

    if (claims_dir := layout.get("claims")) and (root / claims_dir).is_dir():
        files = sorted((root / claims_dir).glob("*.yaml"))
        claims = quotes = 0
        sources: dict[str, str] = {}
        for f in files:
            doc = yaml.safe_load(f.read_text()) or {}
            src = doc.get("source", {}) or {}
            sources[src.get("local", "")] = src.get("sha256", "") or ""
            for claim in (doc.get("claims", {}) or {}).values():
                claims += 1
                quotes += len(claim.get("quotes", []) or [])
        out |= {
            "claim_records": len(files),
            "claims": claims,
            "quotations": quotes,
            "pinned_sources": len(sources),
            "sources_carrying_a_digest": sum(1 for v in sources.values() if v),
        }

    for name, rel in (layout.get("bibliographies") or {}).items():
        if (root / rel).is_file():
            out[f"bibliography_entries_{name}"] = bib_entries(root / rel)

    if (rel := layout.get("manifest")) and (root / rel).is_file():
        manifest = yaml.safe_load((root / rel).read_text()) or {}
        evidence = [e for c in manifest.get("claims", []) for e in c.get("evidence", [])]
        kinds = sorted({e["kind"] for e in evidence})
        out |= {
            "manifest_artifacts": len(manifest.get("artifacts", [])),
            "manifest_claims": len(manifest.get("claims", [])),
            "manifest_assertions": len(evidence),
            "manifest_assertions_by_kind": {
                k: sum(1 for e in evidence if e["kind"] == k) for k in kinds
            },
            "manifest_regenerations": len(manifest.get("regenerations", [])),
        }

    if (rel := layout.get("tags")) and (root / rel).is_file():
        tags = json.loads((root / rel).read_text())
        out["unresolved_manuscript_tags"] = tags["count"]
        out["unresolved_manuscript_tags_by_kind"] = {
            kind: sum(1 for t in tags["tags"] if t["kind"] == kind)
            for kind in sorted({t["kind"] for t in tags["tags"]})
        }

    if (rel := layout.get("ledger")) and (root / rel).is_file():
        events = [json.loads(l) for l in (root / rel).read_text().splitlines() if l.strip()]
        digests = {f["path"] for e in events for f in (e.get("files", []) + e.get("outputs", []))}
        out |= {
            "ledger_events": len(events),
            "runs": len({e["run_id"] for e in events if "run_id" in e}),
            "file_digests_recorded": len(digests),
            "manuscript_claims_bound": sum(1 for e in events if e["event"] == "claim"),
            "confirmatory_claims": sum(
                1 for e in events if e["event"] == "claim" and e.get("confirmatory")
            ),
        }

    # A name may take several patterns: "manuscripts" is `.tex` plus the drafts beside them,
    # and splitting that into two keys would report a count nobody states.
    for name, patterns in (layout.get("globs") or {}).items():
        if isinstance(patterns, str):
            patterns = [patterns]
        out[name] = sum(len(list(root.glob(p))) for p in patterns)

    return out


def run(target_path: pathlib.Path, cache: pathlib.Path, record_path: pathlib.Path,
        log_path: pathlib.Path, offline: bool = False, commit: str = "") -> int:
    """Audit the repository the target names, and write the record and the log."""
    target = yaml.safe_load(target_path.read_text())
    root = checkout(target["repository"], commit or target["commit"], cache)
    pin = pin_of(root, target)

    steps = []
    for spec in target["steps"]:
        if spec.get("network") and offline:
            continue
        argv = [str(a).replace("{cache}", str(cache / "audit-cache")) for a in spec["argv"]]
        steps.append(Step(spec["name"], argv, root, spec.get("note", "")))

    record = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": target,
        "pin": pin,
        "tool_versions": tool_versions(),
        "declared": declared(root, target.get("layout") or {}),
        "steps": {s.name: s.as_dict() for s in steps},
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    lines = [
        f"# audit of {target['repository']}, {record['generated']}",
        f"# commit {pin['commit']}",
        f"# tree   {pin['tree']}  matches pin: {pin['tree_matches_pin']}  dirty: {pin['dirty']}",
        "",
    ]
    for s in steps:
        lines += [f"$ {' '.join(s.argv)}", s.out, f"[exit {s.exit}]", ""]
    log_path.write_text("\n".join(lines))

    print(f"wrote {record_path.name} and {log_path.name}")
    for s in steps:
        print(f"  {s.name:<32} exit {s.exit}")
    return 0
