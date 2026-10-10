"""Time the checks over several projects on Modal, away from a laptop doing other work.

    modal run evaluation/modal_check_timings.py --runs 1 --record-name trial.jsonl   # as a check
    modal run --detach evaluation/modal_check_timings.py                             # the measurement
    modal volume get reproducible-science-check-timings check_timings_by_project.jsonl <destination>

The measurement is `scripts/measure_check_timings_by_project.py`, unchanged: this file decides
only where it runs and where its record goes. The record gains one line per check and the volume
is committed after each, so a stopped run keeps what it measured and a second run starts at the
first check the record does not hold.

The certificates are read from a checkout of the reproducible-science-codecheck repository beside
this one. No model runs and nothing is fetched.
"""

from __future__ import annotations

import pathlib

import modal

REPO = pathlib.Path(__file__).resolve().parent.parent
CERTIFICATES = REPO.parent / "reproducible-science-codecheck" / "bindings"
RECORDS = pathlib.Path("/record")
CPU = 2.0
MEMORY_MB = 4096

app = modal.App("reproducible-science-check-timings")
volume = modal.Volume.from_name("reproducible-science-check-timings", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("poppler-utils")
    .pip_install("reproducible-science==0.5.0", "pyyaml==6.0.2")
    .env({"PYTHONPATH": "/root/paper_repo/scripts"})
    .add_local_dir(REPO, "/root/paper_repo",
                   ignore=[".git", "**/__pycache__", "slides", ".audit-cache", "evaluation/work",
                           "*.aux", "*.log", "*.out"])
    .add_local_dir(CERTIFICATES, "/root/certificates", ignore=["views"])
)

with image.imports():
    import measure_check_timings_by_project as timings


@app.function(image=image, volumes={"/record": volume}, timeout=24 * 60 * 60, cpu=CPU, memory=MEMORY_MB)
def measure(runs: int, record_name: str) -> str:
    record = RECORDS / record_name
    timings.measure(
        pathlib.Path("/root/paper_repo"), pathlib.Path("/root/certificates"), None, record, runs,
        environment={"host": "Modal container", "cpu_requested": CPU, "memory_mb_requested": MEMORY_MB},
        after_each=volume.commit,
    )
    return record.read_text()


@app.local_entrypoint()
def main(runs: int = 10, record_name: str = "check_timings_by_project.jsonl"):
    print(measure.remote(runs, record_name))
