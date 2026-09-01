#!/usr/bin/env python3
"""Compact authoring format -> a schema-v2 batch JSON ready for merge_batch.py.

The JSON boilerplate (subject, part, source, verified_*, reference) is identical for every
question in a topic, so it is declared once in a topic header and the questions themselves are
written one per line. This keeps an authoring session readable and diffable.

    @ Subject ~ Topic ~ IDPREFIX ~ Default reference
    E ~ stem ~ option A ~ option B ~ option C ~ option D ~ B ~ concept [~ reference override]

  - difficulty is E / M / H
  - the key is the letter A-D of the correct option
  - blank lines and lines starting with '#' are ignored
  - ids are IDPREFIX_001.. , continuing past anything already in qbank.json

    python3 tools/author.py drafts/medicine_a.txt -o content/batches/medicine_a.json
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_qbank import parse_taxonomy

# part is a legacy label and a fixed function of subject (plan §4)
PART_A = {"Anatomy", "Physiology", "Biochemistry", "Pathology", "Microbiology",
          "Pharmacology", "Forensic Medicine (FMT)"}
DATE = "2026-09-01"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--date", default=DATE)
    args = ap.parse_args()

    taxonomy = parse_taxonomy()
    bank = json.load(open(BANK))["questions"]
    used_ids = {q["id"] for q in bank}
    # highest suffix already taken per prefix, so a re-run never collides
    counters = collections.Counter()
    for qid in used_ids:
        m = re.fullmatch(r"Q_(.+)_(\d+)", qid)
        if m:
            counters[m.group(1)] = max(counters[m.group(1)], int(m.group(2)))

    out, errors = [], []
    subject = topic = prefix = ref = None
    for lineno, raw in enumerate(open(args.src), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@"):
            parts = [p.strip() for p in line[1:].split("~")]
            if len(parts) != 4:
                errors.append(f"line {lineno}: header needs 4 fields, got {len(parts)}")
                continue
            subject, topic, prefix, ref = parts
            if subject not in taxonomy:
                errors.append(f"line {lineno}: unknown subject {subject!r}")
            elif topic not in taxonomy[subject]:
                errors.append(f"line {lineno}: {topic!r} is not a {subject} topic")
            continue
        if subject is None:
            errors.append(f"line {lineno}: question before any @ header")
            continue
        f = [p.strip() for p in line.split("~")]
        if len(f) not in (8, 9):
            errors.append(f"line {lineno}: needs 8 or 9 fields, got {len(f)}")
            continue
        diff, stem, o1, o2, o3, o4, key, concept = f[:8]
        if diff not in ("E", "M", "H"):
            errors.append(f"line {lineno}: difficulty {diff!r}")
            continue
        if key.upper() not in "ABCD" or len(key) != 1:
            errors.append(f"line {lineno}: key {key!r}")
            continue
        counters[prefix] += 1
        qid = f"Q_{prefix}_{counters[prefix]:03d}"
        out.append({
            "id": qid,
            "part": "A" if subject in PART_A else "B",
            "subject": subject,
            "source": "ai",
            # Authoring is NOT verification. A freshly written question has had its answer,
            # topic and reference checked by nobody, so it enters the bank unverified and must
            # be picked up by a later audit pass (tools/verify.py) like any other question.
            "verified": "N",
            "topic": topic,
            "difficulty": diff,
            "stem": stem,
            "options": [o1, o2, o3, o4],
            "correct": "ABCD".index(key.upper()),
            "concept": concept,
            "reference": f[8] if len(f) == 9 else ref,
        })

    if errors:
        print(f"✗ {len(errors)} error(s):")
        for e in errors[:30]:
            print("   ", e)
        return 1

    json.dump({"questions": out}, open(args.out, "w"), ensure_ascii=False, indent=1)
    mix = collections.Counter(q["difficulty"] for q in out)
    n = len(out)
    print(f"✓ {n} questions -> {args.out}")
    print(f"  difficulty  E {mix['E']} ({mix['E']*100//n}%)  M {mix['M']} ({mix['M']*100//n}%)  H {mix['H']} ({mix['H']*100//n}%)")
    print(f"  topics      {len({(q['subject'], q['topic']) for q in out})}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
