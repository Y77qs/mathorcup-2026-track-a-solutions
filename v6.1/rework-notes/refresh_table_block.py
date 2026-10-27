#!/usr/bin/env python3
"""refresh_table_block.py — re-inline changed table fragments into report/paper.md.

Used only after src/paper_tables.py --build regenerates a fragment: for each requested
table id, replace the existing <!-- table-begin:id sha256=... --> ... <!-- table-end:id -->
block with the CURRENT fragment bytes and the CURRENT INDEX sha256, byte-exactly.
This mirrors what `--splice` does for a `<!-- TABLE:id -->` marker (the splice tool skips
already-spliced blocks, so it cannot refresh them).

Usage: refresh_table_block.py <paper.md> <table-id> [<table-id> ...]
Exit 0 only if every block was replaced and re-verifies against INDEX + fragment bytes.
"""
import hashlib, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def main(argv):
    if len(argv) < 3:
        print(__doc__); return 2
    paper_path = pathlib.Path(argv[1])
    if not paper_path.is_absolute():
        paper_path = ROOT / paper_path
    ids = argv[2:]
    index = json.loads((ROOT / "report/tables/INDEX.json").read_text(encoding="utf-8"))
    by_tid = {k.split(" ", 1)[-1]: v for k, v in index["tables"].items()}
    text = paper_path.read_text(encoding="utf-8")
    for tid in ids:
        rec = by_tid.get(tid)
        if rec is None:
            print(f"[fail] 未知表 id：{tid}"); return 1
        frag_path = ROOT / rec["outputs"]["md"]["path"]
        frag = frag_path.read_text(encoding="utf-8")
        sha = hashlib.sha256(frag.encode("utf-8")).hexdigest()
        if sha != rec["outputs"]["md"]["sha256"]:
            print(f"[fail] {tid} 片段文件 sha 与 INDEX 不符"); return 1
        pat = re.compile(r"<!-- table-begin:%s sha256=[0-9a-f]{64} -->\n.*?\n<!-- table-end:%s -->" % (tid, tid), re.S)
        if not pat.search(text):
            print(f"[fail] {tid} 在 {paper_path} 中找不到既有表格块"); return 1
        block = "<!-- table-begin:%s sha256=%s -->\n%s\n<!-- table-end:%s -->" % (tid, sha, frag.rstrip("\n"), tid)
        text = pat.sub(lambda m: block, text, count=1)
        print(f"[ok] {tid} 已刷新 -> sha256={sha[:16]}…")
    paper_path.write_text(text, encoding="utf-8")
    # verify
    for tid in ids:
        rec = by_tid[tid]
        frag = (ROOT / rec["outputs"]["md"]["path"]).read_text(encoding="utf-8")
        m = re.search(r"<!-- table-begin:%s sha256=([0-9a-f]{64}) -->\n(.*?)\n<!-- table-end:%s -->" % (tid, tid), text, re.S)
        if not m or m.group(1) != rec["outputs"]["md"]["sha256"] or m.group(2).rstrip("\n") != frag.rstrip("\n"):
            print(f"[fail] {tid} 刷新后校验失败"); return 1
    print("refresh: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
