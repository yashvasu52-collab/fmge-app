#!/usr/bin/env python3
"""Validate a content batch and merge it into qbank.json.

A batch is a JSON file: {"questions": [ ... ]} using schema v2.
Nothing merges unless the batch is clean against the plan taxonomy AND against the bank
(no id collisions, no duplicate stems, no near-duplicates inside a topic).

    python3 tools/merge_batch.py content/batches/medicine_01.json          # dry run
    python3 tools/merge_batch.py content/batches/medicine_01.json --commit
"""
import argparse
import collections
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_qbank import parse_taxonomy, validate, near_duplicates, normalise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--dup-threshold", type=float, default=0.75)
    args = ap.parse_args()

    taxonomy = parse_taxonomy()
    bank = json.load(open(args.bank))
    existing = bank["questions"]
    incoming = json.load(open(args.batch))["questions"]

    print(f"batch  : {os.path.basename(args.batch)} — {len(incoming)} questions")
    print(f"bank   : {len(existing)} questions\n")

    errors = []

    # 1. batch is internally valid, and strict: new content must carry schema v2
    fails, warns, _ = validate(incoming, taxonomy, strict=True)
    errors += fails

    # 2. no id collision with the bank
    have_ids = {q["id"] for q in existing}
    for q in incoming:
        if q.get("id") in have_ids:
            errors.append(f"{q['id']}: id already exists in the bank")

    # 3. no duplicate stem against the bank
    have_stems = {str(q.get("stem", "")).strip(): q["id"] for q in existing}
    for q in incoming:
        clash = have_stems.get(str(q.get("stem", "")).strip())
        if clash:
            errors.append(f"{q['id']}: stem duplicates bank question {clash}")

    # 4. near-duplicates against the bank, within the same topic
    by_topic = collections.defaultdict(list)
    for q in existing:
        by_topic[(q.get("subject"), q.get("topic"))].append(q)
    near = []
    for q in incoming:
        sig = normalise(q.get("stem", ""))
        if not sig:
            continue
        for other in by_topic[(q.get("subject"), q.get("topic"))]:
            osig = normalise(other.get("stem", ""))
            union = len(sig | osig)
            if union and len(sig & osig) / union >= args.dup_threshold:
                near.append(f"{q['id']} ≈ bank {other['id']} ({len(sig & osig)/union:.2f})")
    near += [f"{a} ≈ {b} ({sim}) [within batch]"
             for _, _, a, b, sim in near_duplicates(incoming, args.dup_threshold)]

    if errors:
        print(f"✗ {len(errors)} hard failure(s) — nothing merged:")
        for e in errors[:40]:
            print(f"    {e}")
        if len(errors) > 40:
            print(f"    … and {len(errors)-40} more")
        return 1

    print("✓ batch is valid")
    if near:
        print(f"! {len(near)} near-duplicate(s) — review before committing:")
        for n in near[:20]:
            print(f"    {n}")
    if warns:
        print(f"! {len(warns)} warning(s) (first 10):")
        for w in warns[:10]:
            print(f"    {w}")

    added = collections.Counter((q["subject"], q["topic"]) for q in incoming)
    print(f"\nwould add {len(incoming)} questions to {len(added)} topics:")
    for (s, t), n in sorted(added.items()):
        before = len(by_topic[(s, t)])
        print(f"    {s:<26} {t[:46]:<48} {before:>3} → {before+n}")

    if not args.commit:
        print("\ndry run — pass --commit to write qbank.json")
        return 0

    shutil.copy(args.bank, args.bank + ".bak")
    merged = existing + incoming
    json.dump({"count": len(merged), "questions": merged},
              open(args.bank, "w"), ensure_ascii=False, indent=1)
    print(f"\n✓ merged. bank {len(existing)} → {len(merged)}  (backup at qbank.json.bak)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
