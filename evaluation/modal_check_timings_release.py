"""Time this paper's two checks on Modal, beside the same measurement on the laptop.

    TOOLKIT_VERSION=0.6.1 modal run --detach evaluation/modal_check_timings_release.py \
        --record-name check_timings_modal_<date>.json
    modal volume get reproducible-science-check-timings check_timings_modal_<date>.json <destination>

The toolkit release is named by `TOOLKIT_VERSION` rather than written here, so a new release is
timed without editing a sealed script. The record names the versions the container installed.

The measurement is `scripts/measure_check_timings.py`, unchanged: this file decides only where it
runs and where its record goes. The script writes its record after each check and the volume is
committed each time, so a stopped run keeps what it measured.

The repository is copied into the image with the sources its quotations are pinned to, which
live in the ignored `paper/prior_art/reference/` folder. A source missing from the image would
make the quotation check measure nothing, so the function refuses to start without each one.
"""

from __future__ import annotations

import os
import pathlib

import modal

TOOLKIT = os.environ["TOOLKIT_VERSION"]
REPO = pathlib.Path(__file__).resolve().parent.parent
RECORDS = pathlib.Path("/record")
PAPER = pathlib.Path("/root/paper_repo")
CPU = 2.0
MEMORY_MB = 4096

app = modal.App("reproducible-science-check-timings-paper")
volume = modal.Volume.from_name("reproducible-science-check-timings", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("poppler-utils")
    .pip_install(
        *(f"{name}=={TOOLKIT}" for name in ("reproducible-science", "claims-cli", "citations",
                                            "provenance-core", "results-cli", "prereg")),
        "pyyaml==6.0.2", "pydantic==2.13.4",
    )
    .env({"PYTHONPATH": "/root/paper_repo/scripts"})
    .add_local_dir(REPO, str(PAPER),
                   # LaTeX build files at the top of paper/ only: the manifest pins an audit log.
                   ignore=[".git", "**/__pycache__", "slides", ".audit-cache", "evaluation/work",
                           "paper/*.aux", "paper/*.log", "paper/*.out"])
)

with image.imports():
    import yaml

    import measure_check_timings as timings


class MissingSourceError(Exception):
    """A quotation's source is not in the image."""


@app.function(image=image, volumes={"/record": volume}, timeout=24 * 60 * 60, cpu=CPU, memory=MEMORY_MB)
def measure(record_name: str) -> str:
    claims = PAPER / "paper" / "prior_art" / "claims"
    for path in sorted(claims.glob("*.yaml")):
        local = yaml.safe_load(path.read_text())["source"]["local"]
        if not (claims.parent / local).is_file():
            raise MissingSourceError(f"{path.name}: {local} is not in the image")
    record = RECORDS / record_name
    timings.measure(
        record,
        {"host": "Modal container", "cpu_requested": str(CPU), "memory_mb_requested": str(MEMORY_MB)},
        after_each=volume.commit,
    )
    return record.read_text()


@app.local_entrypoint()
def main(record_name: str):
    print(measure.remote(record_name))
