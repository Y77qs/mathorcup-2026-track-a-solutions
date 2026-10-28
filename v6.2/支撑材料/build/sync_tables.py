#!/usr/bin/env python3
"""sync_tables.py — make build/tables/ the single source of truth for paper tables.

For every ``<!-- table-begin:<id> sha256=... --> ... <!-- table-end:<id> -->``
block in the paper source, this script:

  1. re-reads ``build/tables/<id>.md`` (the fragment),
  2. rewrites the inlined block body to the fragment bytes,
  3. rewrites the header sha256 to the fragment's sha256,
  4. regenerates ``build/tables/INDEX.json`` with project-relative paths.

It never edits the fragment itself: a table is changed by editing the fragment
(or by a generator script that writes the fragment), then re-running this.

Usage:
    python FINAL_SUBMISSION_v6.2/build/sync_tables.py            # rewrite in place
    python FINAL_SUBMISSION_v6.2/build/sync_tables.py --check    # verify only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
SUBMISSION_DIR = BUILD_DIR.parent
PROJECT_DIR = SUBMISSION_DIR.parent
TABLES_DIR = BUILD_DIR / "tables"
SOURCE = BUILD_DIR / "paper_final.md"

BLOCK_RE = re.compile(
    r"<!-- table-begin:(?P<id>\S+) sha256=(?P<sha>[0-9a-f]{64}) -->\n"
    r"(?P<body>.*?)\n"
    r"<!-- table-end:(?P=id) -->",
    re.S,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def rel(path: Path) -> str:
    """Table fragment paths are stored relative to the submission directory, which is
    the root build_final.py resolves them against (so the tree works both in the
    original project layout and in the stand-alone support-materials copy)."""
    return path.resolve().relative_to(SUBMISSION_DIR.resolve()).as_posix()


def sync(check: bool) -> int:
    source_text = SOURCE.read_text(encoding="utf-8")
    problems: list[str] = []
    changed: list[str] = []
    used: list[str] = []

    def replace(match: re.Match) -> str:
        tid = match.group("id")
        used.append(tid)
        frag_path = TABLES_DIR / f"{tid}.md"
        if not frag_path.exists():
            problems.append(f"{tid}: fragment {rel(frag_path)} is missing")
            return match.group(0)
        frag = frag_path.read_text(encoding="utf-8")
        body = frag.rstrip("\n")
        new_sha = sha256_text(frag)
        if check:
            if match.group("sha") != new_sha:
                problems.append(f"{tid}: header sha256 {match.group('sha')[:12]} "
                                f"!= fragment {new_sha[:12]}")
            if match.group("body") != body:
                problems.append(f"{tid}: inlined body differs from fragment bytes")
            return match.group(0)
        if match.group("sha") != new_sha or match.group("body") != body:
            changed.append(tid)
        return (f"<!-- table-begin:{tid} sha256={new_sha} -->\n"
                f"{body}\n<!-- table-end:{tid} -->")

    new_text = BLOCK_RE.sub(replace, source_text)
    if problems:
        print("== table sync problems ==")
        for line in problems:
            print("  [FAIL] " + line)
        return 2

    if not check and new_text != source_text:
        SOURCE.write_text(new_text, encoding="utf-8")
        print(f"[OK] rewrote {len(changed)} table block(s) in {rel(SOURCE)}: {', '.join(changed)}")
    elif not check:
        print("[OK] all table blocks already match their fragments")

    # regenerate INDEX.json from the fragments actually referenced by the paper
    seen: set[str] = set()
    tables = []
    for tid in used:
        if tid in seen:
            continue
        seen.add(tid)
        frag_path = TABLES_DIR / f"{tid}.md"
        if not frag_path.exists():
            continue
        frag = frag_path.read_text(encoding="utf-8")
        csv_path = TABLES_DIR / f"{tid}.csv"
        entry = {
            "id": tid,
            "key": tid,
            "title": "",
            "status": "COMPLETE",
            "complete": True,
            "reason": None,
            "inputs": [],
            "outputs": {
                "md": {"path": rel(frag_path), "sha256": sha256_text(frag)},
            },
        }
        if csv_path.exists():
            entry["outputs"]["csv"] = {
                "path": rel(csv_path),
                "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            }
        tables.append(entry)
    index = {
        "kind": "paper-tables-index",
        "generatedBy": "FINAL_SUBMISSION_v6.2/build/sync_tables.py",
        "note": "plugin-free index: fragments under build/tables are the single source of truth",
        "tables": {f"T{i + 1} {entry['id']}": entry for i, entry in enumerate(tables)},
    }
    if not check:
        (TABLES_DIR / "INDEX.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[OK] INDEX.json: {len(tables)} table(s)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return sync(args.check)


if __name__ == "__main__":
    sys.exit(main())
