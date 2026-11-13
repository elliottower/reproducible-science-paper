"""Time the two checks the manuscript says are cheap enough to run at every commit.

Each check is run as the command a user types, in a new process, so the time includes starting
the interpreter and reading every artifact from disk. The manuscript prints the median of the
runs. The machine, the tool versions and every run's time are written with it.

    uv run --no-project --with reproducible-science==0.6.0 --with citations==0.6.0 \
        --with provenance-core==0.6.0 --with results-cli==0.6.0 --with prereg==0.6.0 \
        --with pyyaml==6.0.2 --with pydantic==2.13.4 \
        python scripts/measure_check_timings.py --out paper/artifacts/check_timings_laptop_<date>.json

The record is written to a new file and never over one that exists. It is written again after
each check, with `complete` false until the last, so a stopped run keeps what it measured.

Checks timed:
  `repro verify --policy strict` over this repository's manifest, `repro.yaml`
  `citations verify --claims paper/prior_art/claims`, the quotations this paper pins, one
  claim file per source: once with `CITATIONS_NO_CACHE=1`, so every run reads every source, and
  once as typed, where runs after the first take the text of an unchanged source from the cache

`repro verify` exits 1 while the manuscript prints a count this measurement is about to replace:
the sentence giving the timed artifacts binds the record of the previous measurement. Exit 1 is
accepted only when the structured report (`--format json`) shows that every failing assertion is
a mismatch against a check_timings file. Any other failure stops the measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAIMS = "paper/prior_art/claims"
RUNS = 10
TIMING_RECORD = re.compile(r"(^|/)check_timings[^/]*\.json$")
PACKAGES = ("reproducible-science", "claims-cli", "citations", "provenance-core", "results-cli", "prereg")


class TimingError(Exception):
    """A check did not run as the measurement assumes."""


def timed(
    command: list[str], accept: tuple[int, ...], environment: dict[str, str] | None = None
) -> tuple[list[float], str]:
    seconds, output = [], ""
    for _ in range(RUNS):
        started = time.perf_counter()
        done = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ | (environment or {}),
        )
        seconds.append(round(time.perf_counter() - started, 3))
        if done.returncode not in accept:
            raise TimingError(f"{' '.join(command)} exited {done.returncode}")
        output = done.stdout
    return seconds, output


def summary(seconds: list[float]) -> dict:
    return {
        "runs": seconds,
        "median_seconds": round(statistics.median(seconds), 2),
        "min_seconds": min(seconds),
        "max_seconds": max(seconds),
    }


def accepted_mismatches(manifest: dict) -> list[str]:
    """The failing assertions `repro verify` reports, each of which must bind a check_timings file."""
    done = subprocess.run(
        ["repro", "verify", "--policy", "strict", "--format", "json"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if done.returncode not in (0, 1):
        raise TimingError(f"repro verify --format json exited {done.returncode}\n{done.stderr}")
    report = json.loads(done.stdout)
    paths = {artifact["id"]: artifact["path"] for artifact in manifest["artifacts"]}
    decisions = {
        f"{decision['claim_id']}/{decision['kind']}": decision
        for claim in report["report"]["claims"]
        for decision in claim["decisions"]
    }
    accepted = []
    for violation in report["assessment"]["violations"]:
        decision = decisions.get(violation["subject"])
        if (
            violation["rule"] != "evidence.mismatch"
            or decision is None
            or decision["comparison"] != "mismatch"
            or not TIMING_RECORD.search(paths.get(decision["artifact_id"], ""))
        ):
            raise TimingError(f"repro verify fails on more than the timing record: {violation}")
        accepted.append(violation["detail"])
    if done.returncode == 1 and not accepted:
        raise TimingError("repro verify exited 1 with no violation in its report")
    return accepted


def output_of(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def machine(stated: dict[str, str]) -> dict:
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
    return described | stated


def version(tool: str) -> str:
    return subprocess.run([tool, "--version"], capture_output=True, text=True, check=False).stdout.strip()


def measure(out: pathlib.Path, stated: dict[str, str], after_each: Callable[[], None]) -> dict:
    if out.exists():
        raise TimingError(f"{out} exists; a measurement is written to a new file")
    manifest = yaml.safe_load((ROOT / "repro.yaml").read_text())
    mismatches = accepted_mismatches(manifest)
    result = {
        "generated_by": "scripts/measure_check_timings.py",
        "complete": False,
        "runs_per_check": RUNS,
        "each_run": "a new process, timed from start to exit",
        "machine": machine(stated),
        # The four commands are released in lockstep, so one version names all of them.
        "toolkit": version("repro"),
        "packages": {name: importlib.metadata.version(name) for name in PACKAGES},
        "pdftotext": (
            subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, check=False).stderr.splitlines()[0]
            if shutil.which("pdftotext") else "not installed"
        ),
    }

    def write() -> None:
        out.write_text(json.dumps(result, indent=2) + "\n")
        after_each()

    verify_seconds, verify_out = timed(["repro", "verify", "--policy", "strict"], accept=(0, 1) if mismatches else (0,))
    verified = re.search(r"(\d+) verified", verify_out)
    if not verified:
        raise TimingError("repro verify's output does not carry the count this records")
    result["repro_verify"] = {
        "command": "repro verify --policy strict",
        "manifest_sha256": hashlib.sha256((ROOT / "repro.yaml").read_bytes()).hexdigest(),
        "claims": len(manifest["claims"]),
        "assertions": sum(len(claim["evidence"]) for claim in manifest["claims"]),
        "assertions_verified": int(verified.group(1)),
        "mismatches_accepted": mismatches,
        "artifacts": len(manifest["artifacts"]),
        **summary(verify_seconds),
    }
    write()

    cite_seconds, cite_out = timed(
        ["citations", "verify", "--claims", CLAIMS], accept=(0,), environment={"CITATIONS_NO_CACHE": "1"}
    )
    quotes = re.search(r"(\d+) quotes", cite_out)
    found = re.search(r"found\s+(\d+)", cite_out)
    if not (quotes and found):
        raise TimingError("citations verify's output does not carry the counts this records")
    result["citations_verify"] = {
        "command": f"CITATIONS_NO_CACHE=1 citations verify --claims {CLAIMS}",
        "sources": len(list((ROOT / CLAIMS).glob("*.yaml"))),
        "quotations": int(quotes.group(1)),
        "quotations_found": int(found.group(1)),
        **summary(cite_seconds),
    }
    write()

    kept_seconds, _ = timed(["citations", "verify", "--claims", CLAIMS], accept=(0,))
    result["citations_verify_with_cache"] = {
        "command": f"citations verify --claims {CLAIMS}",
        "first_run": "reads any source whose text is not yet kept; later runs read none",
        **summary(kept_seconds),
    }
    result["complete"] = True
    write()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=pathlib.Path, required=True, help="a new file; one that exists is refused")
    parser.add_argument("--environment", nargs="*", default=[], metavar="KEY=VALUE",
                        help="facts about the machine this script cannot read, recorded with it")
    args = parser.parse_args()
    out = args.out.resolve()
    result = measure(out, dict(item.split("=", 1) for item in args.environment), after_each=lambda: None)
    for name in ("repro_verify", "citations_verify", "citations_verify_with_cache"):
        print(f"  {name:28} median {result[name]['median_seconds']}s  "
              f"({result[name]['min_seconds']} to {result[name]['max_seconds']}, {RUNS} runs)")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
