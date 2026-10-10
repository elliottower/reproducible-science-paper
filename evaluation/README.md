# Recall against a benchmark that states its own answers

The measurement Section 4.3 of the manuscript reports: how many of the values a CORE-Bench
capsule says it produces can be located in that capsule's artifact by reading it, without
executing anything.

Every other corpus in the paper lacks ground truth. When a printed value is not found, nobody
can say whether the artifact lacks the value or the reader missed it, so a located value is
evidence of an occurrence and a decoy estimate bounds how much of that is coincidence. Each
CORE-Bench capsule names the values its analysis produces, authored by the benchmark rather
than here, so a miss is unambiguous and recall is measured against a stated answer set.

Over 45 capsules the benchmark states 240 values, of which 146 are located. Eight capsules hold
a record no reader here opened; their misses are `unchecked` rather than `absent`, because the
value may sit in the record that was not read.

## Files

| path | what it is |
|---|---|
| `corebench_recall.py` | downloads, indexes and deletes one capsule at a time, appending a record per capsule |
| `confirm_numbers.py` | builds the value index over an artifact and assigns a strength tier |
| `artifact_readers.py` | readers for pickle, R serialization, compressed and spreadsheet formats |
| `tests/test_artifact_readers.py` | properties the readers must hold, including that no artifact executes |
| `recall.log` | the run's console output |
| `../paper/artifacts/corebench_tasks.json` | the benchmark's task file: capsule ids and the values each states |
| `../paper/artifacts/corebench_recall.jsonl` | the recorded run, one JSON object per capsule |

## Reading binary artifacts without executing them

Two formats worth reading execute code when opened the ordinary way. `pickle.load` imports the
modules a stream names and calls `__reduce__`; a pickle is a program. R serialization carries
promises and closures, and `Rscript -e 'readRDS(...)'` pointed at an untrusted file is a remote
code execution primitive.

Neither is opened that way. `pickletools.genops` walks the opcode stream and yields each opcode
with its literal argument, resolving no names and calling nothing. R serialization is parsed
directly: a documented header, then objects whose flags word carries a type, whose real vectors
are a length and that many big-endian doubles. No function, promise, closure or environment type
is modelled, so nothing in the parser can evaluate. Both readers report whether they understood
the whole file, and a partial read makes a miss `unchecked`.

`tests/test_artifact_readers.py` guards this, including against a pickle whose `__reduce__` runs
a shell command: the test asserts the command did not run.

    python -m pytest evaluation/tests

## Reproducing

`paper/artifacts/corebench_recall.jsonl` is the run the manuscript reports, and
`scripts/derive_corebench_recall.py` writes the counts Table 7 prints from it:

    uv run --no-project python scripts/derive_corebench_recall.py

Re-running the measurement itself downloads 45 capsules at roughly 39 MB each from
`corebench.cs.princeton.edu`, indexes each and deletes it before the next:

    pip install -r evaluation/requirements.txt
    python evaluation/corebench_recall.py --limit 45

Results append, so an interrupted run keeps the capsules it already measured and a second run
resumes. Delete `paper/artifacts/corebench_recall.jsonl` to measure from the start.

## Scope

This is the recall arm only. The census arm it was built beside measures coverage over a
publication frame, is not reported in the manuscript, and is not included here.
