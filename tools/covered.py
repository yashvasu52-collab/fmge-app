"""Ask whether a fact is already covered somewhere in the bank, BEFORE writing a replacement.

Every duplicate I created while rewriting came from choosing a replacement fact without
checking the rest of the bank first: the topic I could see was clear, but the same fact
already sat in a neighbouring topic or another subject. This closes that gap.

    python3 tools/covered.py "Richter transformation"
    python3 tools/covered.py "zinc deficiency" --subject Medicine
    python3 tools/covered.py --answer "Strongyloides stercoralis"
"""
import argparse, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("terms", nargs="*", help="words that must all appear in stem/options/concept")
    ap.add_argument("--answer", help="match against the correct option only")
    ap.add_argument("--subject", help="restrict to one subject")
    ap.add_argument("--limit", type=int, default=25)
    # NOTE: assertion-reason items all share the same four grading phrases as their options, so
    # matching on answer text alone makes every such pair look identical. Compare their stems.
    args = ap.parse_args()

    qs = json.load(open(os.path.join(ROOT, "qbank.json")))["questions"]
    if args.subject:
        qs = [q for q in qs if q["subject"] == args.subject]

    hits = []
    for q in qs:
        if args.answer:
            hay = str(q["options"][q["correct"]]).lower()
            if args.answer.lower() in hay:
                hits.append(q)
            continue
        hay = " ".join([q["stem"], " ".join(map(str, q["options"])),
                        str(q.get("concept", ""))]).lower()
        if all(t.lower() in hay for t in args.terms):
            hits.append(q)

    print(f"{len(hits)} question(s) already cover this")
    for q in hits[:args.limit]:
        state = "audited" if q.get("verified_by") == "model-audit" else "pending"
        print(f"  {q['id']:27s} {state:8s} {q['subject'][:12]:14s} {q['topic'][:34]}")
        print(f"      {q['stem'][:100]}")
        print(f"      *{str(q['options'][q['correct']])[:88]}")


if __name__ == "__main__":
    main()
