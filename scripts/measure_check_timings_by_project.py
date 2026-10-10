"""Time each check over several projects of different sizes, on whatever machine runs this.

`measure_check_timings.py` times two checks over this paper on one machine. This times every
check that needs no network over this paper, and `repro verify` over each CODECHECK certificate
whose manifest binds at least one number, and over each project `generate_scaling_projects.py`
wrote, so the time can be read against the number of assertions and the bytes of the artifacts
a check reads. Beside each `repro verify` it times hashing the same artifacts and comparing the
digests, which is the least any check of those files can cost.

Each check is run as the command a user types, in a new process, so the time includes starting
the interpreter and reading every artifact from disk. One line is appended to the record after
each check, and a check the record already holds is not run again, so a stopped run keeps what
it measured.

    python scripts/measure_check_timings_by_project.py measure \
        --paper-repo . --certificates ../reproducible-science-codecheck/bindings \
        --generated /tmp/scaling --record paper/artifacts/check_timings_by_project.jsonl
    python scripts/measure_check_timings_by_project.py assemble \
        --record paper/artifacts/check_timings_by_project.jsonl \
        --out paper/artifacts/check_timings_by_project.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import statistics
import subprocess
import time
from collections.abc import Callable

import yaml
from pydantic import BaseModel, ConfigDict

RUNS = 10
QUOTATIONS = "paper/prior_art/claims"


class TimingError(Exception):
    """A check did not run as the measurement assumes."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(Strict):
    project: str
    command: list[str]
    cwd: str
    accept: tuple[int, ...]
    size: dict[str, int]
    inputs: dict[str, str]
    # What the record calls the command, where the command itself names a path on this machine.
    label: str = ""


class Measured(Strict):
    kind: str = "check"
    project: str
    command: str
    size: dict[str, int]
    inputs: dict[str, str]
    exit_code: int
    last_line: str
    runs: list[float]
    median_seconds: float
    min_seconds: float
    max_seconds: float


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_check(project: str, directory: pathlib.Path, policy: list[str], accept: tuple[int, ...]) -> Check:
    path = directory / "repro.yaml"
    manifest = yaml.safe_load(path.read_text())
    claims = manifest.get("claims") or []
    return Check(
        project=project,
        command=["repro", "verify", *policy],
        cwd=str(directory),
        accept=accept,
        size={
            "claims": len(claims),
            "assertions": sum(len(claim["evidence"]) for claim in claims),
            "artifacts": len(manifest["artifacts"]),
            "artifact_bytes": sum((directory / a["path"]).stat().st_size for a in manifest["artifacts"]),
        },
        inputs={"repro.yaml": sha256(path)},
    )


def quotation_check(repo: pathlib.Path) -> Check:
    files = sorted((repo / QUOTATIONS).glob("*.yaml"))
    records = [yaml.safe_load(file.read_text()) for file in files]
    return Check(
        project="this paper",
        command=["citations", "verify", "--claims", QUOTATIONS],
        cwd=str(repo),
        accept=(0,),
        size={
            "sources": len(files),
            "quotations": sum(len(claim["quotes"]) for record in records for claim in record["claims"].values()),
        },
        inputs={file.name: sha256(file) for file in files},
    )


def ledger_check(repo: pathlib.Path) -> Check:
    ledger = repo / ".results" / "ledger.jsonl"
    return Check(
        project="this paper",
        command=["results", "verify", "--files"],
        cwd=str(repo),
        # A file sealed more than once is reported and the command exits 1; the chain is still read.
        accept=(0, 1),
        size={"events": len(ledger.read_text().splitlines())},
        inputs={"ledger.jsonl": sha256(ledger)},
    )


def digest_check(project: str, directory: pathlib.Path, sums: pathlib.Path) -> Check:
    """The lower bound: hash the manifest's artifacts and compare, with no claim read."""
    manifest = yaml.safe_load((directory / "repro.yaml").read_text())
    sums.write_text("".join(f"{a['digest']['value']}  {a['path']}\n" for a in manifest["artifacts"]))
    tool = ["shasum", "-a", "256", "-c"] if platform.system() == "Darwin" else ["sha256sum", "-c"]
    full = manifest_check(project, directory, [], accept=(0,))
    return Check(project=project, command=[*tool, str(sums)], cwd=str(directory), accept=(0,),
                 size=full.size, inputs=full.inputs, label=f"{' '.join(tool)} <the manifest's digests>")


def checks(repo: pathlib.Path | None, certificates: pathlib.Path | None,
           generated: pathlib.Path | None, sums: pathlib.Path) -> list[Check]:
    # Starting the command and nothing else, so a check's time can be read against it.
    planned = [Check(project="no project", command=["repro", "--version"], cwd=str(sums.parent),
                     accept=(0,), size={}, inputs={})]
    manifests: list[tuple[str, pathlib.Path, list[str], tuple[int, ...]]] = []
    if repo:
        manifests.append(("this paper", repo, ["--policy", "strict"], (0,)))
        planned += [quotation_check(repo), ledger_check(repo)]
    if certificates:
        # A certificate's numbers disagree with its file in places, and the command then exits 1.
        manifests += [(f"certificate {d.name}", d, [], (0, 1)) for d in sorted(certificates.glob("2*"))]
    if generated:
        manifests += [(f"generated {d.name}", d, [], (0,)) for d in sorted(generated.iterdir())]
    for project, directory, policy, accept in manifests:
        check = manifest_check(project, directory, policy, accept)
        if check.size["assertions"]:
            planned += [check, digest_check(project, directory, sums.with_name(f"{directory.name}.sha256"))]
    return planned


def timed(check: Check, runs: int) -> Measured:
    seconds, done = [], None
    for _ in range(runs):
        started = time.perf_counter()
        done = subprocess.run(check.command, cwd=check.cwd, capture_output=True, text=True, check=False)
        seconds.append(round(time.perf_counter() - started, 3))
        if done.returncode not in check.accept:
            raise TimingError(f"{check.project}: {' '.join(check.command)} exited {done.returncode}\n{done.stderr}")
    lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
    return Measured(
        project=check.project,
        command=check.label or " ".join(check.command),
        size=check.size,
        inputs=check.inputs,
        exit_code=done.returncode,
        last_line=lines[-1] if lines else "",
        runs=seconds,
        median_seconds=round(statistics.median(seconds), 3),
        min_seconds=min(seconds),
        max_seconds=max(seconds),
    )


def output_of(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def machine() -> dict:
    """The hardware the times were taken on. No host name, no serial number."""
    described = {
        "system": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "load_average_at_start": [round(value, 2) for value in os.getloadavg()],
    }
    if platform.system() == "Darwin":
        described |= {
            "model": output_of(["sysctl", "-n", "hw.model"]),
            "cpu": output_of(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "physical_cores": int(output_of(["sysctl", "-n", "hw.physicalcpu"])),
            "memory_gb": int(output_of(["sysctl", "-n", "hw.memsize"])) // 2**30,
            "macos": platform.mac_ver()[0],
        }
    else:
        cpuinfo = pathlib.Path("/proc/cpuinfo").read_text()
        meminfo = pathlib.Path("/proc/meminfo").read_text()
        described |= {
            "cpu": re.search(r"model name\s*:\s*(.+)", cpuinfo).group(1),
            "cpus_usable": len(os.sched_getaffinity(0)),
            "memory_gb_visible": int(re.search(r"MemTotal:\s*(\d+)", meminfo).group(1)) // 2**20,
        }
    return described


def measure(repo: pathlib.Path | None, certificates: pathlib.Path | None, generated: pathlib.Path | None,
            record: pathlib.Path, runs: int, environment: dict, after_each: Callable[[], None]) -> None:
    held = [json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
    done = {(line["project"], line["command"]) for line in held if line["kind"] == "check"}
    if not held:
        header = {
            "kind": "machine",
            "machine": machine() | environment,
            "toolkit": output_of(["repro", "--version"]),
            # The quotation check is the one that runs it; the others never do.
            "pdftotext": (
                subprocess.run(["pdftotext", "-v"], capture_output=True, text=True,
                               check=False).stderr.splitlines()[0]
                if shutil.which("pdftotext") else "not installed"
            ),
            "runs_per_check": runs,
            "each_run": "a new process, timed from start to exit",
        }
        record.write_text(json.dumps(header) + "\n")
        after_each()
    for check in checks(repo, certificates, generated, record.with_suffix(".sums")):
        if (check.project, check.label or " ".join(check.command)) in done:
            continue
        measured = timed(check, runs)
        with record.open("a") as handle:
            handle.write(measured.model_dump_json() + "\n")
        after_each()
        print(f"  {measured.project:<22} {measured.command:<46} median {measured.median_seconds}s  "
              f"({measured.min_seconds} to {measured.max_seconds})  exit {measured.exit_code}", flush=True)


def assemble(record: pathlib.Path) -> dict:
    lines = [json.loads(line) for line in record.read_text().splitlines()]
    header = next(line for line in lines if line["kind"] == "machine")
    measured = [Measured(**line).model_dump(exclude={"kind"}) for line in lines if line["kind"] == "check"]
    return {
        "generated_by": "scripts/measure_check_timings_by_project.py",
        **{key: value for key, value in header.items() if key != "kind"},
        "record_sha256": sha256(record),
        "checks": measured,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("measure")
    run.add_argument("--paper-repo", type=pathlib.Path)
    run.add_argument("--certificates", type=pathlib.Path)
    run.add_argument("--generated", type=pathlib.Path)
    run.add_argument("--record", type=pathlib.Path, required=True)
    run.add_argument("--runs", type=int, default=RUNS)
    run.add_argument("--environment", nargs="*", default=[], metavar="KEY=VALUE",
                     help="facts about the machine this script cannot read, recorded with it")
    build = commands.add_parser("assemble")
    build.add_argument("--record", type=pathlib.Path, required=True)
    build.add_argument("--out", type=pathlib.Path, required=True)
    args = parser.parse_args()

    if args.action == "measure":
        given = [path.resolve() if path else None
                 for path in (args.paper_repo, args.certificates, args.generated)]
        stated = dict(item.split("=", 1) for item in args.environment)
        measure(*given, args.record.resolve(), args.runs, environment=stated, after_each=lambda: None)
    else:
        args.out.write_text(json.dumps(assemble(args.record), indent=2) + "\n")
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
