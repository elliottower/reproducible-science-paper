"""Re-run the CORE-Bench recall measurement on Modal.

    modal run evaluation/modal_corebench_recall.py --limit 1      # one capsule, as a check
    modal run --detach evaluation/modal_corebench_recall.py       # every capsule not yet recorded
    modal run --detach evaluation/modal_corebench_recall.py --record-name NAME.jsonl   # a separate record
    modal volume get reproducible-science-corebench corebench_recall.jsonl <destination>

The measurement is `corebench_recall.py`, unchanged: this file decides only where it runs and
where its record goes. Capsules are downloaded, indexed and deleted one at a time, as there. Each
capsule's record is appended to a file on a volume and the volume is committed before the next
capsule begins, so a run that is stopped keeps every capsule it measured, and a second run starts
at the first capsule the record does not hold.

The request header names the study and no person.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import time
from datetime import UTC, datetime

import modal

HERE = pathlib.Path(__file__).resolve().parent
RECORDS = pathlib.Path("/record")
WORK = pathlib.Path("/tmp/work")

app = modal.App("reproducible-science-corebench-recall")
volume = modal.Volume.from_name("reproducible-science-corebench", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("certifi==2026.7.22")
    .env({"PYTHONPATH": "/root/evaluation"})
    .add_local_dir(HERE, "/root/evaluation", ignore=["work", "tests", "__pycache__", "*.log"])
    .add_local_file(HERE.parent / "paper" / "artifacts" / "corebench_tasks.json",
                    "/root/paper/artifacts/corebench_tasks.json")
)

with image.imports():
    import corebench_recall as recall


# One capsule indexes more than twenty million values; the job asks for memory to hold its index.
@app.function(image=image, volumes={"/record": volume}, timeout=24 * 60 * 60, memory=8192)
def rerun(limit: int, record_name: str) -> dict:
    record_path = RECORDS / record_name
    recall.USER_AGENT = "reproducible-science-corebench-recall/1.0 (research)"
    tasks = json.loads(recall.TASKS.read_text())
    done = set()
    if record_path.exists():
        done = {json.loads(line)["capsule_id"] for line in record_path.read_text().splitlines() if line}
    todo = [task for task in tasks if task["capsule_id"] not in done][:limit]

    for at, task in enumerate(todo, start=1):
        capsule = WORK / task["capsule_id"]
        shutil.rmtree(capsule, ignore_errors=True)
        started = time.time()
        if recall.download(task["capsule_id"], capsule):
            record = {"status": "measured", **recall.measure(task, capsule)}
        else:
            record = {"capsule_id": task["capsule_id"], "status": "not retrieved"}
        shutil.rmtree(capsule, ignore_errors=True)

        with record_path.open("a") as handle:
            handle.write(json.dumps(record) + "\n")
        volume.commit()

        answers = record.get("answers", [])
        print(f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}  [{at:2}/{len(todo)}] {task['capsule_id']}  "
              f"{record['status']:<14}  {sum(1 for a in answers if a['found'])}/{len(answers)} found  "
              f"{time.time() - started:.0f}s", flush=True)

    return {"recorded_before": len(done), "recorded_now": len(todo), "tasks": len(tasks)}


@app.local_entrypoint()
def main(limit: int = 45, record_name: str = "corebench_recall.jsonl"):
    print(rerun.remote(limit, record_name))
