"""Check that every number in the READMEs comes from a file in results/.

Two ways a README may state a result:

1. A generated table between `<!-- table: NAME -->` and `<!-- /table -->`. The table is rendered
   again from results/ by tools/readme_tables.py and must match exactly.
2. An inline value followed by a marker `<!-- claim: FILE | SELECTOR | FORMAT -->`, e.g.
   `4.31x<!-- claim: 02_parallel_sum/parallel_sum.json | rows[n=100000000,method=pool_map].speedup | {:.2f}x -->`.
   SELECTOR is a dotted path; `name[key=value,...]` picks the one list item whose fields match.
   The text right before the marker must equal FORMAT applied to that value.

Any other speedup (1.23x), time in seconds (1.2 s) or percentage (12 %) outside a table or claim
is an error, unless its line ends with `<!-- earlier evidence -->` (a saved earlier output cited by path
in the same sentence).

    python tools/check_readme_claims.py            # check
    python tools/check_readme_claims.py --write    # regenerate the tables in place
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
sys.path.insert(0, str(REPO / "tools"))

CLAIM_RE = re.compile(r"<!-- claim: (?P<file>[^|]+?) \| (?P<sel>[^|]+?) \| (?P<fmt>.+?) -->")
TABLE_RE = re.compile(r"(<!-- table: (?P<name>[\w.-]+) -->\n)(?P<body>.*?)(<!-- /table -->)", re.S)
UNCLAIMED_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:x\b| ?s\b| ?%)")
EXEMPT_TAG = "<!-- earlier evidence -->"


def select(doc, selector: str):
    cur = doc
    for part in re.findall(r"[^.\[\]]+(?:\[[^\]]*\])?", selector):
        m = re.fullmatch(r"([^\[]+)(?:\[([^\]]*)\])?", part)
        key, filt = m.group(1), m.group(2)
        cur = cur[int(key)] if isinstance(cur, list) else cur[key]
        if filt:
            conds = dict(c.split("=", 1) for c in filt.split(","))
            hits = [item for item in cur if all(str(item.get(k)) == v for k, v in conds.items())]
            if len(hits) != 1:
                raise KeyError(f"{selector}: filter [{filt}] matched {len(hits)} items")
            cur = hits[0]
    return cur


def _load(path: str) -> dict:
    return json.loads((RESULTS / path.strip()).read_text(encoding="utf-8"))


def check_file(readme: Path, write: bool = False) -> list[str]:
    import readme_tables

    text = readme.read_text(encoding="utf-8")
    errors: list[str] = []
    rel = readme.relative_to(REPO) if readme.is_relative_to(REPO) else readme.name

    def render(m):
        name = m.group("name")
        try:
            fresh = readme_tables.render(name, _load) + "\n"
        except Exception as exc:  # missing results, bad table name
            errors.append(f"{rel}: table {name}: {exc}")
            return m.group(0)
        if fresh != m.group("body"):
            if not write:
                errors.append(f"{rel}: table {name} does not match results/ (run with --write)")
            return m.group(1) + fresh + m.group(4)
        return m.group(0)

    new_text = TABLE_RE.sub(render, text)
    if write and new_text != text:
        readme.write_text(new_text, encoding="utf-8")
    text = new_text

    stripped = TABLE_RE.sub("", text)
    cuts = []  # (start, end) spans of claimed values and their markers
    for m in CLAIM_RE.finditer(stripped):
        try:
            value = select(_load(m.group("file")), m.group("sel").strip())
            expected = m.group("fmt").strip().format(value)
        except Exception as exc:
            errors.append(f"{rel}: claim {m.group(0)!r}: {exc}")
            cuts.append((m.start(), m.end()))
            continue
        before = stripped[: m.start()]
        core = before.rstrip("*")
        if not core.endswith(expected):
            errors.append(f"{rel}: claim says {expected!r} but the text reads {core[-len(expected) - 10:]!r}")
        cuts.append((len(core) - len(expected), m.end()))
    no_claims, last = [], 0
    for a, b in sorted(cuts):
        no_claims.append(stripped[last:max(a, last)])
        last = b
    no_claims = "".join(no_claims) + stripped[last:]

    for line in no_claims.splitlines():
        if line.rstrip().endswith(EXEMPT_TAG) or line.lstrip().startswith(("    ", "$ ", "```")):
            continue
        for hit in UNCLAIMED_RE.findall(re.sub(r"`[^`]*`", "", line)):
            errors.append(f"{rel}: unclaimed number {hit!r} in: {line.strip()[:90]}")
    return errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    readmes = [REPO / "README.md", *sorted(REPO.glob("0*/README.md"))]
    errors = [e for r in readmes if r.exists() for e in check_file(r, args.write)]
    claims = sum(len(CLAIM_RE.findall(r.read_text(encoding="utf-8"))) for r in readmes if r.exists())
    tables = sum(len(TABLE_RE.findall(r.read_text(encoding="utf-8"))) for r in readmes if r.exists())
    for e in errors:
        print("ERROR", e)
    print(f"check_readme_claims: {len(readmes)} READMEs, {tables} tables, {claims} inline claims, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
