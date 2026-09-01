"""Dump questions needing review in a compact reviewable form, for the §5.3 fact-check pass.

    python3 tools/review_dump.py --subject Pathology --limit 40
    python3 tools/review_dump.py --priority          # subjects ordered by pending x blueprint
    python3 tools/review_dump.py --unsigned --source pyq --paper FMGE_2024JAN

Two different populations can need review, and they are selected differently:
  default      verified == "N"  -- questions self-labelled as needing review
  --unsigned   no verified_by   -- questions inherited as verified="Y" from schema v1, where
                                   that flag meant "came from a trusted source" rather than
                                   "a person read this". Nobody ever read these.
"""
import argparse
import collections
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")
BP = {"Medicine": 39, "Pathology": 28, "Obstetrics & Gynaecology": 25, "PSM (Community Medicine)": 25,
      "Microbiology": 23, "Pharmacology": 23, "Surgery": 18, "Pediatrics": 18, "Physiology": 17,
      "Biochemistry": 17, "Anatomy": 15, "ENT": 11, "Forensic Medicine (FMT)": 11, "Psychiatry": 7,
      "Anaesthesia": 6, "Ophthalmology": 5, "Dermatology": 5, "Radiology": 5, "Orthopedics": 4}


# A stem that promises a picture the bank does not hold cannot be answered as printed. Recalls
# scraped from exam papers are the main source of these, so they are worth isolating first.
IMG_PROMISE = re.compile(
    r"\b(this image|the image|image below|images? shown|shown below|shown in the|figure|photograph|"
    r"given below|arrow|marked|video|as depicted|identify the)\b", re.I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--topic")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--priority", action="store_true")
    ap.add_argument("--unsigned", action="store_true",
                    help="select questions carrying no verified_by instead of verified=='N'")
    ap.add_argument("--source", choices=["pyq", "authored", "ai"],
                    help="restrict to one provenance")
    ap.add_argument("--paper", help="restrict to one source_ref paper token, e.g. FMGE_2024JAN")
    ap.add_argument("--flagged", action="store_true",
                    help="only questions whose stem promises an image that is not attached")
    ap.add_argument("--decisions", action="store_true",
                    help="emit a pre-filled 'id | ok |' decision file for the scope")
    args = ap.parse_args()

    qs = json.load(open(BANK))["questions"]
    if args.unsigned:
        unver = [q for q in qs if not q.get("verified_by")]
    else:
        unver = [q for q in qs if q.get("verified") == "N"]
    if args.source:
        unver = [q for q in unver if q.get("source") == args.source]
    if args.paper:
        unver = [q for q in unver if args.paper in str(q.get("source_ref", ""))]
    if args.flagged:
        unver = [q for q in unver if IMG_PROMISE.search(q["stem"]) and not q.get("image")]

    if args.priority:
        c = collections.Counter(q["subject"] for q in unver)
        rows = sorted(((n * BP.get(s, 1), s, n) for s, n in c.items()), reverse=True)
        print(f"{'subject':<28}{'unver':>6}{'bp':>5}{'score':>8}")
        for score, s, n in rows:
            print(f"{s:<28}{n:>6}{BP.get(s,1):>5}{score:>8}")
        print(f"\ntotal pending {len(unver)}")
        return

    if args.subject:
        unver = [q for q in unver if q["subject"] == args.subject]
    if args.topic:
        unver = [q for q in unver if args.topic.lower() in q["topic"].lower()]
    unver.sort(key=lambda q: (q["topic"], q["id"]))
    sel = unver[args.offset:args.offset + args.limit] if args.limit else unver[args.offset:]

    if args.decisions:
        for q in sel:
            print(f"{q['id']} | ok |")
        return

    topic = None
    for q in sel:
        if q["topic"] != topic:
            topic = q["topic"]
            print(f"\n=== {q['subject']} / {topic}")
        star = "ABCD"[q["correct"]]
        print(f"{q['id']} [{q['difficulty']}] {q['stem']}")
        for i, o in enumerate(q["options"]):
            print(f"   {'*' if i == q['correct'] else ' '}{'ABCD'[i]}. {o}")
        print(f"   key={star} ref={q.get('reference','-')}")
        print(f"   concept: {q.get('concept','-')}")
    print(f"\n[{len(sel)} shown of {len(unver)} pending in scope]")


if __name__ == "__main__":
    main()
