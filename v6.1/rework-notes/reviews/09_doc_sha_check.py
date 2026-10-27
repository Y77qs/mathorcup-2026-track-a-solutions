#!/usr/bin/env python
"""Verify every (path, sha256) pair declared in DELIVERY-NOTES.md against disk."""
import hashlib
import os
import re

doc = open("DELIVERY-NOTES.md", encoding="utf-8").read()
pairs = set()
for m in re.finditer(r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`", doc):
    pairs.add((m.group(1), m.group(2)))
for m in re.finditer(r"`([\w./\-]+\.(?:png|md|json|py|tex|pdf))`[^\n]*?`([0-9a-f]{64})`", doc):
    pairs.add((m.group(1), m.group(2)))

ok, bad = 0, []
for path, want in sorted(pairs):
    if not os.path.exists(path):
        bad.append((path, "MISSING", want[:12]))
        continue
    disk = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if disk == want:
        ok += 1
    else:
        bad.append((path, disk[:12], want[:12]))

print("declared path/sha pairs:", len(pairs), "| match:", ok)
print("mismatch/missing:", bad if bad else "none")

bi = hashlib.sha256(open("report/BUILD-INPUTS.json", "rb").read()).hexdigest()
print("BUILD-INPUTS declared fd2804fa… -> disk", bi[:12], "match:", bi.startswith("fd2804fa"))

import json
refs = json.load(open("report/rendered.refs.json"))
n = len(refs) if isinstance(refs, list) else len(refs.get("refs", refs))
print("rendered.refs.json entries:", n, "| doc claims 91:", n == 91)
