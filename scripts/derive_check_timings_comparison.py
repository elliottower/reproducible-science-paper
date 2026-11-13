"""Write the laptop and Modal timings of this paper's checks side by side.

Both records are written by `scripts/measure_check_timings.py` over the same manifest and
quotations, one on the laptop and one in a Modal container. This reads each measure's median and
range from both and the ratio of the medians, with the digest of each record it read.

    uv run --no-project --with pydantic==2.9.2 python scripts/derive_check_timings_comparison.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib

from pydantic import BaseModel, ConfigDict

ROOT = pathlib.Path(__file__).resolve().parent.parent
ART = ROOT / "paper" / "artifacts"
RECORDS = {
    "laptop": ART / "check_timings_laptop_2026-10-14.json",
    "modal": ART / "check_timings_modal_2026-10-14.json",
}
OUT = ART / "check_timings_comparison_2026-10-14.json"
MEASURES = ("repro_verify", "citations_verify", "citations_verify_with_cache")


class ComparisonError(Exception):
    """The two records do not time the same thing."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Timed(Strict):
    median_seconds: float
    min_seconds: float
    max_seconds: float


class Measure(Strict):
    command: str
    laptop: Timed
    modal: Timed
    modal_median_over_laptop_median: float


class Comparison(Strict):
    generated_by: str
    records: dict[str, dict[str, str]]
    machines: dict[str, dict]
    toolkit: dict[str, str]
    manifest_sha256: str
    measures: dict[str, Measure]


def derive() -> Comparison:
    held = {name: json.loads(path.read_text()) for name, path in RECORDS.items()}
    for name, record in held.items():
        if not record["complete"]:
            raise ComparisonError(f"the {name} record is incomplete")
    manifests = {record["repro_verify"]["manifest_sha256"] for record in held.values()}
    if len(manifests) != 1:
        raise ComparisonError("the two records timed different manifests")
    measures = {}
    for measure in MEASURES:
        laptop, modal = held["laptop"][measure], held["modal"][measure]
        if laptop["command"] != modal["command"]:
            raise ComparisonError(f"{measure}: the two records ran different commands")
        measures[measure] = Measure(
            command=laptop["command"],
            laptop=Timed.model_validate({k: laptop[k] for k in Timed.model_fields}),
            modal=Timed.model_validate({k: modal[k] for k in Timed.model_fields}),
            modal_median_over_laptop_median=round(modal["median_seconds"] / laptop["median_seconds"], 2),
        )
    return Comparison(
        generated_by="scripts/derive_check_timings_comparison.py",
        records={
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for name, path in RECORDS.items()
        },
        machines={name: record["machine"] for name, record in held.items()},
        toolkit={name: record["toolkit"] for name, record in held.items()},
        manifest_sha256=manifests.pop(),
        measures=measures,
    )


def main() -> None:
    if OUT.exists():
        raise ComparisonError(f"{OUT} exists; the comparison is written to a new file")
    comparison = derive()
    OUT.write_text(json.dumps(comparison.model_dump(), indent=2) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    for name, measure in comparison.measures.items():
        print(f"  {name:28} laptop {measure.laptop.median_seconds}s  modal {measure.modal.median_seconds}s  "
              f"ratio {measure.modal_median_over_laptop_median}")


if __name__ == "__main__":
    main()
