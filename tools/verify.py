"""Apply a fact-check decision list to qbank.json (plan §5.3).

A decision file has one line per reviewed question:

    Q_c1_001 | ok                                  | reviewed, no change
    Q_c1_002 | key=2                                | Robbins gives caseous, not fibrinoid
    Q_c1_003 | opt1=Sickle cell anaemia; key=1      | distractor was implausible filler
    Q_c1_004 | concept=<text>                       | concept restated the answer
    Q_c1_005 | del                                  | two defensible answers, unsalvageable

Everything not deleted comes out with verified="Y", verified_by, verified_on and, where the
third column is non-empty, verify_note - so a question queried later carries its own history.

Ops: ok | del | key=<0-3> | opt<i>=<text> | stem=<text> | concept=<text> | ref=<text> | diff=<E|M|H>
     source=<pyq|authored|ai> | srcref=<paper token> | topic=<exact plan topic name>
Multiple ops are separated by ';;' - a doubled delimiter, because replacement text
routinely contains ordinary semicolons.

    python3 tools/verify.py drafts/verify_path.txt              # dry run
    python3 tools/verify.py drafts/verify_path.txt --commit
    python3 tools/verify.py --backfill-source --commit           # plan §10: source on every question
"""
import argparse
import collections
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")
WHO = "model-review"
DATE = "2026-09-01"


def backfill_source(questions):
    """plan §10 wants 'source' on every question; for legacy content it is derivable."""
    n = 0
    for q in questions:
        if q.get("source"):
            continue
        m = re.match(r"Q_PYQ_(\w+)_\d+$", q["id"])
        if m:
            q["source"], q["source_ref"] = "pyq", m.group(1)
        else:
            q["source"] = "ai"
        n += 1
    return n


def apply_ops(q, ops):
    """Mutate q in place. Returns a list of human-readable changes."""
    changed = []
    for op in [o.strip() for o in ops.split(";;") if o.strip()]:
        if op == "ok":
            continue
        m = re.fullmatch(r"(key|stem|concept|ref|diff|source|srcref|topic|opt([0-3]))=(.*)", op, re.S)
        if not m:
            raise ValueError(f"unparsable op {op!r}")
        field, idx, val = m.group(1), m.group(2), m.group(3).strip()
        if field == "key":
            if val not in "0123" or len(val) != 1:
                raise ValueError(f"key must be 0-3, got {val!r}")
            changed.append(f"key {q['correct']}->{val}")
            q["correct"] = int(val)
        elif field == "topic":
            # Refiling a question. The topic must already exist in the plan taxonomy, which
            # validate_qbank.py checks, so a typo here surfaces as a hard failure rather than
            # silently creating a new topic.
            changed.append(f"topic {q.get('topic')!r} -> {val!r}")
            q["topic"] = val
        elif field == "source":
            # A question rewritten to a new fact is no longer the exam recall it was scraped from,
            # so it must stop claiming that provenance. Dropping source_ref with it prevents an
            # invented question being attributed to a real paper.
            changed.append(f"source {q.get('source')} -> {val}")
            q["source"] = val
            if val != "pyq":
                q.pop("source_ref", None)
        elif field == "srcref":
            changed.append("source_ref set")
            q["source_ref"] = val
        elif field.startswith("opt"):
            i = int(idx)
            changed.append(f"opt{i} rewritten")
            q["options"][i] = val
        elif field == "diff":
            if val not in ("E", "M", "H"):
                raise ValueError(f"diff must be E/M/H, got {val!r}")
            changed.append(f"diff {q['difficulty']}->{val}")
            q["difficulty"] = val
        else:
            changed.append({"stem": "stem", "concept": "concept", "ref": "reference"}[field] + " rewritten")
            q[{"stem": "stem", "concept": "concept", "ref": "reference"}[field]] = val
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions", nargs="?")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--backfill-source", action="store_true")
    ap.add_argument("--who", default="model-audit",
                    help="value written to verified_by; 'model-audit' marks a question as having been read against the plan's §5.3 checklist, which is the only thing that counts as verified")
    ap.add_argument("--date", default=DATE)
    args = ap.parse_args()

    bank = json.load(open(BANK))
    questions = bank["questions"]
    index = {q["id"]: q for q in questions}

    if args.backfill_source:
        n = backfill_source(questions)
        print(f"source backfilled on {n} questions")

    kept, fixed, deleted, errors = 0, 0, [], []
    if args.decisions:
        for lineno, raw in enumerate(open(args.decisions), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                errors.append(f"line {lineno}: needs at least 'id | ops'")
                continue
            qid, ops = parts[0], parts[1]
            note = parts[2] if len(parts) > 2 else ""
            q = index.get(qid)
            if q is None:
                errors.append(f"line {lineno}: {qid} not in the bank")
                continue
            if ops == "del":
                deleted.append((qid, note))
                continue
            try:
                changes = apply_ops(q, ops)
            except ValueError as e:
                errors.append(f"line {lineno}: {qid}: {e}")
                continue
            q["verified"] = "Y"
            q["verified_by"] = args.who
            q["verified_on"] = args.date
            if note:
                q["verify_note"] = note
            if changes:
                fixed += 1
            else:
                kept += 1

    if errors:
        print(f"✗ {len(errors)} error(s) — nothing written:")
        for e in errors[:30]:
            print("   ", e)
        return 1

    drop = {qid for qid, _ in deleted}
    remaining = [q for q in questions if q["id"] not in drop]

    print(f"verified unchanged : {kept}")
    print(f"verified with fix  : {fixed}")
    print(f"deleted            : {len(deleted)}")
    for qid, why in deleted:
        print(f"    {qid}  {why}")
    unver = sum(1 for q in remaining if q.get("verified") == "N")
    print(f"\nbank {len(questions)} -> {len(remaining)} | unverified remaining {unver}")

    if not args.commit:
        print("\ndry run — pass --commit to write qbank.json")
        return 0
    shutil.copy(BANK, BANK + ".bak")
    json.dump({"count": len(remaining), "questions": remaining},
              open(BANK, "w"), ensure_ascii=False, indent=1)
    print("✓ written (backup at qbank.json.bak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
