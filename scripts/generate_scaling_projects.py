"""Write projects of chosen sizes, so the time of a check can be read against size.

Each project has the form of a CODECHECK certificate's binding: a text standing for the paper, a
CSV standing for the regenerated output, and a manifest in which every claim says one number in
the text and one cell of the CSV hold the same value. Every claim agrees at the printed
precision. Nothing is drawn at random, so two runs write the same bytes.

Two series are written:

  assertions-N   N claims over one text and one CSV
  bytes-N        100 claims, plus declared files of filler that bring the artifacts to N bytes

    python scripts/generate_scaling_projects.py --out /tmp/scaling \
        --assertions 10 100 1000 --megabytes 1 16
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib

import yaml

FIXED_ASSERTIONS = 100
CHUNK = 64 * 2**20
FILLER_LINE = b"filler, read only to be hashed\n"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(2**20):
            digest.update(block)
    return digest.hexdigest()


def write_filler(path: pathlib.Path, size: int) -> None:
    block = FILLER_LINE * (2**20 // len(FILLER_LINE))
    with path.open("wb") as handle:
        left = size
        while left > 0:
            handle.write(block[:left])
            left -= len(block)


def write_project(directory: pathlib.Path, assertions: int, filler_bytes: int) -> None:
    artifacts = directory / "artifacts"
    artifacts.mkdir(parents=True)
    prose, rows, claims = [], ["name,value"], []
    for at in range(assertions):
        printed = (at * 7919 % 100000) / 1000
        prose.append(f"Row r{at:07d} reports {printed:.3f} units{at:07d}.")
        rows.append(f"r{at:07d},{printed + 0.000217:.9f}")
        claims.append({
            "id": f"n{at:07d}",
            "text": f"row r{at:07d}",
            "evidence": [{
                "kind": "correspondence",
                "name": f"n{at:07d}",
                "sides": [
                    {"name": "paper", "artifact": "paper",
                     "locator": {"kind": "prose", "before": f"r{at:07d} reports",
                                 "after": f"units{at:07d}", "form": "decimal"}},
                    {"name": "output", "artifact": "output",
                     "locator": {"kind": "table", "column": "value", "where": {"name": f"r{at:07d}"}}},
                ],
            }],
        })
    (artifacts / "paper.txt").write_text("\n".join(prose) + "\n")
    (artifacts / "output.csv").write_text("\n".join(rows) + "\n")

    files = {"paper": "paper.txt", "output": "output.csv"}
    left, part = filler_bytes, 0
    while left > 0:
        name = f"filler_{part:03d}.txt"
        write_filler(artifacts / name, min(left, CHUNK))
        files[f"filler-{part:03d}"] = name
        left -= CHUNK
        part += 1

    manifest = {
        "schema_version": "repro/1",
        "project": directory.name,
        "artifacts": [
            {"id": key, "path": f"artifacts/{name}",
             "digest": {"algorithm": "sha256", "value": sha256(artifacts / name)}}
            for key, name in files.items()
        ],
        "claims": claims,
    }
    (directory / "repro.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--assertions", type=int, nargs="*", default=[])
    parser.add_argument("--megabytes", type=int, nargs="*", default=[])
    args = parser.parse_args()
    for count in args.assertions:
        write_project(args.out / f"assertions-{count:07d}", count, 0)
        print(f"  wrote assertions-{count:07d}", flush=True)
    for megabytes in args.megabytes:
        write_project(args.out / f"bytes-{megabytes:06d}MB", FIXED_ASSERTIONS, megabytes * 2**20)
        print(f"  wrote bytes-{megabytes:06d}MB", flush=True)


if __name__ == "__main__":
    main()
