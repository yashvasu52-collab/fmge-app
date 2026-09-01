#!/usr/bin/env python3
"""Even out the answer-key distribution by permuting option order.

A generator that favours one option letter is a pattern a candidate can exploit, so the key
should be near 25% per letter. Swapping two options changes the position of the correct answer
without altering a single word of medical content.

Questions whose options carry an intrinsic order - numeric values, comparatives, sequences -
are skipped, because reordering them would read wrongly.

    python3 tools/rebalance_keys.py --filter-verified-by model-review          # dry run
    python3 tools/rebalance_keys.py --filter-verified-by model-review --commit
"""
import argparse
import collections
import json
import os
import random
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")

# Options with an inherent ordering must not be shuffled.
ORDERED = re.compile(
    r"^\s*(less than|more than|above|below|greater than|under|up to|at least)\b"
    r"|^\s*[<>]"
    r"|^\s*\d+(\.\d+)?\s*(mmhg|mg|ml|g|mmol|meq|fl|per|years?|weeks?|days?|hours?|minutes?|%|$)",
    re.I)


# A concept that argues by option letter ("option A describes...", "(B) is wrong") becomes
# nonsense if the options are permuted, so such questions must never be shuffled.
LETTER_REF = re.compile(r"\boption[s]?\s+[A-D]\b|\b[A-D]\)|\([A-D]\)|\b[A-D]\s+(?:is|are|describes|wrongly|reverses)\b")


def is_orderable(options, concept=""):
    """True when the options can safely be permuted."""
    if LETTER_REF.search(str(concept)):
        return False
    if any(ORDERED.match(str(o)) for o in options):
        return False
    # a set of pure numbers, e.g. ["1","2","3","4"]
    if all(re.fullmatch(r"[\d.,\s]+", str(o)) for o in options):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--filter-verified-by")
    ap.add_argument("--ids-from", nargs="*", default=[],
                    help="batch JSON file(s); restrict rebalancing to the ids they contain")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--seed", type=int, default=31)
    args = ap.parse_args()

    bank = json.load(open(args.bank))
    questions = bank["questions"]
    scope_ids = set()
    for path in args.ids_from:
        scope_ids |= {q["id"] for q in json.load(open(path))["questions"]}
    pool = [q for q in questions
            if (not args.filter_verified_by or q.get("verified_by") == args.filter_verified_by)
            and (not scope_ids or q["id"] in scope_ids)]

    before = collections.Counter(q["correct"] for q in pool)
    print(f"scope: {len(pool)} questions"
          + (f" with verified_by={args.filter_verified_by}" if args.filter_verified_by else ""))
    print(f"before : A{before[0]} B{before[1]} C{before[2]} D{before[3]}")

    rng = random.Random(args.seed)
    movable = [q for q in pool if is_orderable(q["options"], q.get("concept", ""))]
    skipped = len(pool) - len(movable)
    rng.shuffle(movable)

    # Deal target letters round-robin so the final distribution is as even as possible.
    target_seq = [0, 1, 2, 3] * (len(movable) // 4 + 1)
    changed = 0
    for q, target in zip(movable, target_seq):
        cur = q["correct"]
        if cur == target:
            continue
        opts = list(q["options"])
        opts[cur], opts[target] = opts[target], opts[cur]
        q["options"] = opts
        q["correct"] = target
        changed += 1

    after = collections.Counter(q["correct"] for q in pool)
    print(f"after  : A{after[0]} B{after[1]} C{after[2]} D{after[3]}")
    print(f"swapped {changed} questions, skipped {skipped} with ordered options or letter-referencing concepts")

    if not args.commit:
        print("\ndry run - pass --commit to write qbank.json")
        return
    shutil.copy(args.bank, args.bank + ".bak")
    json.dump({"count": len(questions), "questions": questions},
              open(args.bank, "w"), ensure_ascii=False, indent=1)
    print("\n✓ written (backup at qbank.json.bak)")


if __name__ == "__main__":
    main()
