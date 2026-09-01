"""Compact dump of questions still lacking verified_by, for the §5.3 reading pass.

    python3 tools/review_compact.py --subject Medicine --limit 60 --offset 0

Deliberately terser than review_dump.py: stem, options with the key marked, and only the
opening of the concept. The full concept is rarely what decides whether an item is sound,
but its first clause is where a previous author's own hedging ("NOTE: ...") shows up.
"""
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ids the topic screen thought might be filed in the wrong topic; shown as a "<<TOPIC?" marker
# so the reader gives the filing a second look. Advisory only.
try:
    FLAGS = set(json.load(open(os.path.join(ROOT, "drafts", "topic_flag_ids.json"))))
except Exception:
    FLAGS = set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--concept", type=int, default=110, help="chars of concept to show")
    ap.add_argument("--pending-only", action="store_true",
                    help="only questions not yet read against the checklist")
    args = ap.parse_args()

    qs = json.load(open(os.path.join(ROOT, "qbank.json")))["questions"]
    sel = [q for q in qs if q.get("verified_by") != "model-audit"] if True else qs
    if args.subject:
        sel = [q for q in sel if q["subject"] == args.subject]
    sel.sort(key=lambda q: (q["topic"], q["id"]))
    total = len(sel)
    if args.limit:
        sel = sel[args.offset:args.offset + args.limit]

    topic = None
    for q in sel:
        if q["topic"] != topic:
            topic = q["topic"]
            print(f"\n== {topic}")
        print(f"{q['id']} [{q['difficulty']}] {q['stem']}")
        print("    " + " | ".join(("*" if i == q["correct"] else "") + str(o)
                                  for i, o in enumerate(q["options"])))
        c = str(q.get("concept", ""))
        if c:
            print(f"    c: {c[:args.concept]}")
        mark = " <<TOPIC?" if q["id"] in FLAGS else ""
        print(f"    r: {q.get('reference','-')}{mark}")
    print(f"\n[{len(sel)} shown, offset {args.offset}, of {total} unsigned in scope]")


if __name__ == "__main__":
    main()
