"""Write how many of the manifest's claims the manuscript's body states.

Section 4.1 gives the count of claims the body binds. The manifest's claims are listed in
`build_manifest.py`, each with the sentence it quotes and the rendering it quotes it from; which
of them stand in the body and which in an appendix was stored nowhere. The body is the
manuscript up to `\\appendix`, rendered by `detex.py` as the manifest's rendering is. A claim
quoting the manuscript's rendering is counted in the body when its sentence occurs in the body's
rendering, and every such claim must occur in the body or in the rest, so the count cannot pass
by missing a sentence.

    uv run --no-project --with pyyaml==6.0.2 --with pydantic==2.9.2 \\
        --with reproducible-science==0.6.0 python scripts/derive_body_claims.py \\
        --paper <manuscript stem>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re

import build_manifest as m
from detex import plain

OUT = m.ART / "body_claims.json"
APPENDIX = "\\appendix"
SPACE = re.compile(r"\s+")


class UnplacedClaim(Exception):
    """A claim quoting the manuscript whose sentence occurs in neither part of its rendering."""


def folded(text: str) -> str:
    return SPACE.sub(" ", text).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Count the manifest's claims stated in the body")
    parser.add_argument("--paper", required=True, help="manuscript stem under paper/, without .tex")
    args = parser.parse_args()
    source = m.PAPER / f"{args.paper}.tex"
    head, tail = source.read_text().split(APPENDIX, 1)
    body, rest = folded(plain(head)), folded(plain(tail))
    quoting = [c for c in m.CLAIMS if c.stated_in == "manuscript-text"]
    in_body = [c.id for c in quoting if folded(c.sentence) in body]
    unplaced = [c.id for c in quoting if c.id not in in_body and folded(c.sentence) not in rest]
    if unplaced:
        raise UnplacedClaim(", ".join(unplaced))
    out = {
        "source": {
            "path": source.relative_to(m.ROOT).as_posix(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "body_ends_at": APPENDIX,
        "claims_in_manifest": len(m.CLAIMS),
        "claims_quoting_the_manuscript": len(quoting),
        "claims_in_body": len(in_body),
        "claims_in_body_ids": in_body,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    for key, value in out.items():
        if key != "claims_in_body_ids":
            print(f"  {key:30} {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
