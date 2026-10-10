"""Time the two checks the manuscript says are cheap enough to run at every commit.

Each check is run as the command a user types, in a new process, so the time includes starting
the interpreter and reading every artifact from disk. The manuscript prints the median of the
runs. The machine, the tool versions and every run's time are written with it.

    uv run --no-project python scripts/measure_check_timings.py

Checks timed:
  `repro verify --policy strict` over this repository's manifest, `repro.yaml`
  `citations verify --claims paper/prior_art/claims`, the quotations this paper pins, one
  claim file per source: once with `CITATIONS_NO_CACHE=1`, so every run reads every source, and
  once as typed, where runs after the first take the text of an unchanged source from the cache
"""

from __future__ import annotations

import json
import os
import pathlib
import platform
import re
import statistics
import subprocess
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "artifacts" / "check_timings.json"
CLAIMS = "paper/prior_art/claims"
RUNS = 10


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


def sysctl(name: str) -> str:
    return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=False).stdout.strip()


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
            "model": sysctl("hw.model"),
            "cpu": sysctl("machdep.cpu.brand_string"),
            "physical_cores": int(sysctl("hw.physicalcpu")),
            "memory_gb": int(sysctl("hw.memsize")) // 2**30,
            "macos": platform.mac_ver()[0],
        }
    else:
        described["cpu"] = platform.processor()
    return described


def version(tool: str) -> str:
    return subprocess.run([tool, "--version"], capture_output=True, text=True, check=False).stdout.strip()


def main() -> None:
    manifest = yaml.safe_load((ROOT / "repro.yaml").read_text())
    verify_seconds, verify_out = timed(["repro", "verify", "--policy", "strict"], accept=(0,))
    cite_seconds, cite_out = timed(
        ["citations", "verify", "--claims", CLAIMS], accept=(0,), environment={"CITATIONS_NO_CACHE": "1"}
    )
    kept_seconds, _ = timed(["citations", "verify", "--claims", CLAIMS], accept=(0,))

    verified = re.search(r"(\d+) verified", verify_out)
    quotes = re.search(r"(\d+) quotes", cite_out)
    found = re.search(r"found\s+(\d+)", cite_out)
    if not (verified and quotes and found):
        raise TimingError("a check's output does not carry the counts this records")
    result = {
        "generated_by": "scripts/measure_check_timings.py",
        "runs_per_check": RUNS,
        "each_run": "a new process, timed from start to exit",
        "machine": machine(),
        # The four commands are released in lockstep, so one version names all of them.
        "toolkit": version("repro"),
        "repro_verify": {
            "command": "repro verify --policy strict",
            "claims": len(manifest["claims"]),
            "assertions": sum(len(claim["evidence"]) for claim in manifest["claims"]),
            "assertions_verified": int(verified.group(1)),
            "artifacts": len(manifest["artifacts"]),
            **summary(verify_seconds),
        },
        "citations_verify": {
            "command": f"CITATIONS_NO_CACHE=1 citations verify --claims {CLAIMS}",
            "sources": len(list((ROOT / CLAIMS).glob("*.yaml"))),
            "quotations": int(quotes.group(1)),
            "quotations_found": int(found.group(1)),
            **summary(cite_seconds),
        },
        "citations_verify_with_cache": {
            "command": f"citations verify --claims {CLAIMS}",
            "first_run": "reads any source whose text is not yet kept; later runs read none",
            **summary(kept_seconds),
        },
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    for name in ("repro_verify", "citations_verify", "citations_verify_with_cache"):
        print(f"  {name:28} median {result[name]['median_seconds']}s  "
              f"({result[name]['min_seconds']} to {result[name]['max_seconds']}, {RUNS} runs)")
    print(f"  wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
