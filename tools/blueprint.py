#!/usr/bin/env python3
"""Regenerate the FMGE bank blueprint from qbank.json alone.

The subject weighting is not guessed from a syllabus document - it is measured from the
real-exam PYQ recalls already sitting in the bank (ids prefixed Q_PYQ_FMGE_*). Add more
recalls and the blueprint self-corrects.

Usage:  python3 tools/blueprint.py [--depth 20] [--csv]
"""
import argparse
import collections
import json
import os
import sys

# Target bank depth: questions authored per blueprint-question of the 300-mark exam.
# 20 -> ~6,040-question bank. This is the single knob that sizes the whole content phase.
DEPTH = 20

PYQ_PREFIX = "Q_PYQ_FMGE"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path=None):
    with open(path or os.path.join(ROOT, "qbank.json")) as fh:
        return json.load(fh)["questions"]


def blueprint(questions, depth=DEPTH):
    """-> list of per-subject rows, widest gap first."""
    pyq = [q for q in questions if q["id"].startswith(PYQ_PREFIX)]
    if not pyq:
        sys.exit(f"no {PYQ_PREFIX}_* questions found - cannot derive a blueprint")

    weight = collections.Counter(q["subject"] for q in pyq)
    have = collections.Counter(q["subject"] for q in questions)
    topics = collections.defaultdict(set)
    verified = collections.Counter()
    for q in questions:
        topics[q["subject"]].add(q.get("topic"))
        if q.get("verified") == "Y":
            verified[q["subject"]] += 1

    rows = []
    for subject, n in weight.most_common():
        bp = round(300 * n / len(pyq))          # marks out of 300
        target = bp * depth
        rows.append({
            "subject": subject,
            "pyq_n": n,
            "blueprint_300": bp,
            "target": target,
            "have": have[subject],
            "gap": target - have[subject],
            "topics": len(topics[subject]),
            "verified": verified[subject],
            "unverified": have[subject] - verified[subject],
        })
    # subjects present in the bank but never seen in a real paper get no blueprint weight
    for subject in set(have) - set(weight):
        rows.append({"subject": subject, "pyq_n": 0, "blueprint_300": 0, "target": 0,
                     "have": have[subject], "gap": -have[subject], "topics": len(topics[subject]),
                     "verified": verified[subject], "unverified": have[subject] - verified[subject]})
    return sorted(rows, key=lambda r: -r["gap"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", type=int, default=DEPTH)
    ap.add_argument("--csv", action="store_true")
    ap.add_argument("--bank", default=None)
    args = ap.parse_args()

    questions = load(args.bank)
    rows = blueprint(questions, args.depth)
    cols = ["subject", "blueprint_300", "target", "have", "gap", "topics", "unverified"]

    if args.csv:
        print(",".join(cols))
        for r in rows:
            print(",".join(str(r[c]) for c in cols))
    else:
        print(f"depth = {args.depth}x   bank = {len(questions)} questions\n")
        print(f"{'subject':<28}{'bp/300':>7}{'target':>8}{'have':>6}{'gap':>7}{'topics':>7}{'unver':>7}")
        for r in rows:
            print(f"{r['subject']:<28}{r['blueprint_300']:>7}{r['target']:>8}"
                  f"{r['have']:>6}{r['gap']:>+7}{r['topics']:>7}{r['unverified']:>7}")
        tot = lambda k: sum(r[k] for r in rows)
        print(f"\n{'TOTAL':<28}{tot('blueprint_300'):>7}{tot('target'):>8}"
              f"{tot('have'):>6}{tot('gap'):>+7}{tot('topics'):>7}{tot('unverified'):>7}")


if __name__ == "__main__":
    main()
