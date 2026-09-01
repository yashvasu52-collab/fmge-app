#!/usr/bin/env python3
"""Validate qbank.json against docs/QBANK_PLAN.md.

The taxonomy is parsed out of the plan document itself, so the doc is the single source of
truth and cannot silently drift from the bank.

Usage:
    python3 tools/validate_qbank.py                  # audit the bank as it stands
    python3 tools/validate_qbank.py --strict          # also enforce schema v2 (for new batches)
    python3 tools/validate_qbank.py --subject Medicine
    python3 tools/validate_qbank.py --quiet           # exit code only
Exit code 1 if any hard failure is present.
"""
import argparse
import collections
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "docs", "QBANK_PLAN.md")
BANK = os.path.join(ROOT, "qbank.json")

DIFFICULTIES = {"E", "M", "H"}
SOURCES = {"pyq", "authored", "ai"}
# Substring matches - long enough that they cannot collide with real content.
PLACEHOLDERS = [
    "first option", "second option", "third option", "fourth option",
    "explanation coming soon", "lorem ipsum",
    "which statement is most accurate?",
]
# Short tokens need word boundaries: "TBD" collides with real assay names such as
# GenoType MTBDRplus / MTBDRsl, which are legitimate TB content. "XXX" likewise collides
# with karyotypes (47,XXX), so it must not be preceded by a comma or digit.
PLACEHOLDER_WORDS = re.compile(r"\btbd\b|\btodo\b|\bfixme\b|\bplaceholder\b|(?<![,\d])\bxxx+\b", re.I)
# §6.3 difficulty mix, and the tolerance band a topic may sit in
DIFF_TARGET = {"E": 0.30, "M": 0.50, "H": 0.20}
DIFF_TOLERANCE = 0.15
STOPWORDS = set("""a an the of in on for with to and or is are was were which what following
most likely best next step true false not except cause causes caused patient year old man woman
male female presents presenting history shows show showing following statement about""".split())


def parse_taxonomy(path=PLAN):
    """-> {subject: {topic, ...}} from the '**Subject — N topics · N Q**' blocks in the plan."""
    if not os.path.exists(path):
        sys.exit(f"cannot find the plan document at {path}")
    tax, subject = collections.defaultdict(set), None
    head = re.compile(r"^\*\*(.+?) — \d+ topics? · \d+ Q\*\*$")
    item = re.compile(r"^\d+\. (?:✓|＋) (.+?)\s*$")
    for line in open(path):
        line = line.rstrip("\n")
        m = head.match(line)
        if m:
            subject = m.group(1).strip()
            tax[subject] = set()
            continue
        m = item.match(line)
        if m and subject:
            tax[subject].add(m.group(1).strip())
    if not tax:
        sys.exit("parsed no taxonomy out of the plan - has the '**Subject — N topics · N Q**' heading format changed?")
    return dict(tax)


def normalise(stem):
    words = re.findall(r"[a-z0-9]+", stem.lower())
    return frozenset(w for w in words if w not in STOPWORDS and len(w) > 2)


def near_duplicates(questions, threshold=0.75):
    """Jaccard similarity on content words, compared only within a topic."""
    by_topic = collections.defaultdict(list)
    for q in questions:
        by_topic[(q.get("subject"), q.get("topic"))].append(q)
    hits = []
    for (subject, topic), group in by_topic.items():
        sigs = [(q, normalise(q.get("stem", ""))) for q in group]
        for i in range(len(sigs)):
            qa, sa = sigs[i]
            if not sa:
                continue
            for j in range(i + 1, len(sigs)):
                qb, sb = sigs[j]
                if not sb:
                    continue
                union = len(sa | sb)
                if union and len(sa & sb) / union >= threshold:
                    hits.append((subject, topic, qa["id"], qb["id"],
                                 round(len(sa & sb) / union, 2)))
    return sorted(hits, key=lambda h: -h[4])


def validate(questions, taxonomy, strict=False):
    fails, warns = [], []
    F, W = fails.append, warns.append

    seen_ids, stems = set(), collections.defaultdict(list)
    for q in questions:
        qid = q.get("id", "<no id>")

        for field in ("id", "subject", "topic", "stem", "options", "correct", "difficulty", "verified"):
            if field not in q:
                F(f"{qid}: missing required field '{field}'")

        if qid in seen_ids:
            F(f"{qid}: duplicate id")
        seen_ids.add(qid)

        subject, topic = q.get("subject"), q.get("topic")
        if subject not in taxonomy:
            F(f"{qid}: subject {subject!r} is not in the plan taxonomy")
        elif topic not in taxonomy[subject]:
            F(f"{qid}: topic {topic!r} is not a {subject} topic in the plan taxonomy")

        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) != 4:
            F(f"{qid}: needs exactly 4 options, got {len(opts) if isinstance(opts, list) else type(opts).__name__}")
        else:
            if any(not str(o).strip() for o in opts):
                F(f"{qid}: has an empty option")
            if len({str(o).strip().lower() for o in opts}) != 4:
                F(f"{qid}: options are not all distinct")

        correct = q.get("correct")
        if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct <= 3:
            F(f"{qid}: 'correct' must be an int 0-3, got {correct!r}")

        if q.get("difficulty") not in DIFFICULTIES:
            F(f"{qid}: difficulty {q.get('difficulty')!r} not in E/M/H")
        if q.get("verified") not in {"Y", "N"}:
            F(f"{qid}: verified {q.get('verified')!r} not in Y/N")

        blob = " ".join([str(q.get("stem", ""))] + [str(o) for o in (opts or [])]
                        + [str(q.get("concept", ""))]).lower()
        hit = next((ph for ph in PLACEHOLDERS if ph in blob), None)
        if hit is None:
            m = PLACEHOLDER_WORDS.search(blob)
            hit = m.group(0) if m else None
        if hit:
            F(f"{qid}: contains placeholder text {hit!r}")

        if q.get("stem"):
            stems[str(q["stem"]).strip()].append(qid)

        if q.get("verified") == "Y" and not str(q.get("reference", "")).strip():
            F(f"{qid}: verified 'Y' with no reference")

        # ---- schema v2 ----
        if "source" in q and q["source"] not in SOURCES:
            F(f"{qid}: source {q['source']!r} not in {sorted(SOURCES)}")
        if "image" in q:
            if not str(q["image"]).strip():
                F(f"{qid}: empty image path")
        if strict:
            # 'source' is required from the first batch; structured 'explanation' is a P4
            # deliverable, so it is only a warning here.
            if not q.get("source"):
                F(f"{qid}: --strict requires 'source'")
            if not str(q.get("concept", "")).strip():
                F(f"{qid}: --strict requires a non-empty 'concept'")
            if not q.get("explanation"):
                W(f"{qid}: no structured 'explanation' yet (P4)")
            if q.get("verified") == "Y":
                for field in ("verified_by", "verified_on"):
                    if not q.get(field):
                        F(f"{qid}: --strict requires '{field}' on a verified question")

    for stem, ids in stems.items():
        if len(ids) > 1:
            F(f"duplicate stem shared by {', '.join(ids)}: {stem[:70]}…")

    # ---- warnings ----
    by_subject = collections.defaultdict(list)
    for q in questions:
        by_subject[q.get("subject")].append(q)

    for subject, group in sorted(by_subject.items()):
        keys = collections.Counter(q.get("correct") for q in group)
        n = len(group)
        for k in range(4):
            share = keys[k] / n if n else 0
            if n >= 40 and (share > 0.40 or share < 0.10):
                W(f"{subject}: answer key skewed - option {'ABCD'[k]} is {share:.0%} of {n} questions")

    by_topic = collections.defaultdict(list)
    for q in questions:
        by_topic[(q.get("subject"), q.get("topic"))].append(q)
    for (subject, topic), group in sorted(by_topic.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")):
        n = len(group)
        if n < 8:
            W(f"{subject} / {topic}: only {n} questions")
        mix = collections.Counter(q.get("difficulty") for q in group)
        for d, target in DIFF_TARGET.items():
            share = mix[d] / n if n else 0
            if n >= 15 and abs(share - target) > DIFF_TOLERANCE:
                W(f"{subject} / {topic}: difficulty {d} is {share:.0%}, target {target:.0%} (n={n})")

    missing_topics = []
    for subject, topics in taxonomy.items():
        present = {q.get("topic") for q in by_subject.get(subject, [])}
        for topic in sorted(topics - present):
            missing_topics.append(f"{subject} / {topic}")

    return fails, warns, missing_topics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--plan", default=PLAN)
    ap.add_argument("--subject")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--dup-threshold", type=float, default=0.75)
    ap.add_argument("--max-show", type=int, default=25)
    args = ap.parse_args()

    taxonomy = parse_taxonomy(args.plan)
    questions = json.load(open(args.bank))["questions"]
    if args.subject:
        questions = [q for q in questions if q.get("subject") == args.subject]

    fails, warns, missing = validate(questions, taxonomy, args.strict)
    dups = near_duplicates(questions, args.dup_threshold)

    if not args.quiet:
        planned_topics = sum(len(v) for v in taxonomy.values())
        print(f"bank: {len(questions)} questions | plan taxonomy: "
              f"{len(taxonomy)} subjects, {planned_topics} topics"
              f"{'  [--strict]' if args.strict else ''}\n")

        def block(title, items, marker):
            print(f"{marker} {title}: {len(items)}")
            for line in items[:args.max_show]:
                print(f"    {line}")
            if len(items) > args.max_show:
                print(f"    … and {len(items) - args.max_show} more")
            print()

        block("HARD FAILURES", fails, "✗" if fails else "✓")
        block("near-duplicate pairs (same topic)",
              [f"{s} / {t}: {a} ≈ {b} ({sim})" for s, t, a, b, sim in dups], "!")
        block("warnings", warns, "!")
        block("taxonomy topics with no questions yet", missing, "·")

        # "verified" alone overstates the bank's state: it was historically set at authoring time.

        # Report who actually read each question instead of one aggregate percentage.

        audited = sum(1 for q in questions if q.get("verified_by") == "model-audit")

        authored_unchecked = sum(1 for q in questions if q.get("verified_by") == "authored-unchecked")

        never_read = sum(1 for q in questions if not q.get("verified_by"))

        verified = audited
        v2 = sum(1 for q in questions if "source" in q)
        n = max(len(questions), 1)
        print(f"audited    {audited}/{len(questions)} ({100*audited//n}%) read against the §5.3 checklist")
        print(f"pending    {authored_unchecked + never_read}/{len(questions)} "
              f"({authored_unchecked} authored-unchecked, {never_read} never read)")
        print(f"schema v2  {v2}/{len(questions)} carry 'source'")
        print(f"coverage   {len(questions) - 0} questions across "
              f"{len({(q.get('subject'), q.get('topic')) for q in questions})} of {planned_topics} planned topics")

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
