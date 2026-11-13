"""Write what the split of evaluation-warrant-paper carried: claims marked verified, and sources.

Table 8 and Section 5.1 give the assertions a repository split carried with their verified marks
and without their sources. The repository is evaluation-warrant-paper, split from its working
material at commit 2b36d9b; no file stored the counts. They are read here from that commit of a
local clone with `git`, and every source a claim file names is looked up in every commit on every
branch.

    uv run --no-project --with pyyaml==6.0.2 python scripts/derive_split_repository_counts.py \\
        --clone ~/Documents/GitHub/evaluation-warrant-paper --commit 2b36d9b
"""

import argparse
import json
import pathlib
import subprocess

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "artifacts" / "split_repository_counts.json"
REPOSITORY = "https://github.com/elliottower/evaluation-warrant-paper"


def git(clone: pathlib.Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Count what a repository split carried")
    parser.add_argument("--clone", type=pathlib.Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    clone = args.clone.expanduser()
    commit = git(clone, "rev-parse", args.commit).strip()
    files = [f for f in git(clone, "ls-tree", "--name-only", commit, "claims/").split() if f.endswith(".yaml")]
    claims = verified = 0
    sources = {}
    for name in files:
        document = yaml.safe_load(git(clone, "show", f"{commit}:{name}"))
        local = document["source"]["local"]
        sources[local] = bool(git(clone, "log", "--all", "--format=%h", "--", local).strip())
        for claim in document["claims"].values():
            claims += 1
            verified += claim.get("verified") is True
    out = {
        "repository": REPOSITORY,
        "commit": commit,
        "claim_files": len(files),
        "claims": claims,
        "claims_marked_verified": verified,
        "sources_named": len(sources),
        "sources_in_any_commit": sum(sources.values()),
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for key, value in out.items():
        print(f"  {key:25} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
