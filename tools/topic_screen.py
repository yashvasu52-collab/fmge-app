"""Screen for questions that look filed under the wrong topic.

Topic names in the plan are descriptive ("Adrenal disorders: Cushing's, Conn's, Addison's"),
so a question's own words usually overlap its topic name. This scores each question against
every topic name WITHIN ITS SUBJECT and reports the cases where some other topic scores
clearly better, plus the cases that match their own topic not at all.

It is a screen, not a verdict: a question can legitimately sit in a topic whose name it never
echoes. Everything it prints still has to be read.

    python3 tools/topic_screen.py --subject Physiology
    python3 tools/topic_screen.py --pending-only --min-margin 2
"""
import argparse, json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")

STOP = set("""a an the of in to for and or is are was were which what with on at by as from that this
these those be been not no most commonly common cause causes caused following all except best
patient man woman child year old years boy girl presents presenting has have had after before during
due level levels his her their its it they them there here also more than then when where who whom
disease disorder syndrome test tests normal abnormal high low increased decreased raised reduced
diagnosis management treatment drug drugs therapy features feature finding findings basics general
approach principles types type role use used using""".split())


def toks(s):
    return {w for w in re.findall(r"[a-z]+", str(s).lower()) if w not in STOP and len(w) > 3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject")
    ap.add_argument("--pending-only", action="store_true")
    ap.add_argument("--min-margin", type=int, default=2,
                    help="how many more topic-name words another topic must match to be flagged")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    qs = json.load(open(BANK))["questions"]
    topics_by_subject = collections.defaultdict(set)
    for q in qs:
        topics_by_subject[q["subject"]].add(q["topic"])
    tt = {(s, t): toks(t) for s in topics_by_subject for t in topics_by_subject[s]}

    sel = qs
    if args.subject:
        sel = [q for q in sel if q["subject"] == args.subject]
    if args.pending_only:
        sel = [q for q in sel if q.get("verified_by") != "model-audit"]

    flagged, orphan = [], []
    for q in sel:
        body = toks(q["stem"]) | toks(" ".join(map(str, q["options"]))) | toks(q.get("concept", ""))
        own = len(body & tt[(q["subject"], q["topic"])])
        best_t, best_n = None, -1
        for t in topics_by_subject[q["subject"]]:
            if t == q["topic"]:
                continue
            n = len(body & tt[(q["subject"], t)])
            if n > best_n:
                best_t, best_n = t, n
        if own == 0 and best_n >= 2:
            orphan.append((best_n, q, best_t))
        elif best_n - own >= args.min_margin:
            flagged.append((best_n - own, q, best_t, own, best_n))

    flagged.sort(key=lambda r: -r[0])
    orphan.sort(key=lambda r: -r[0])

    print(f"scope: {len(sel)} questions\n")
    print(f"=== A. matches its own topic on NOTHING, but matches another: {len(orphan)} ===")
    for n, q, t in orphan[:args.limit or len(orphan)]:
        print(f"  {q['id']:26s} {q['subject'][:11]:13s}")
        print(f"      filed : {q['topic']}")
        print(f"      better: {t}  (+{n})")
        print(f"      stem  : {q['stem'][:96]}")
    print(f"\n=== B. another topic matches better by >= {args.min_margin}: {len(flagged)} ===")
    for d, q, t, own, best in flagged[:args.limit or len(flagged)]:
        print(f"  {q['id']:26s} {q['subject'][:11]:13s} own={own} other={best}")
        print(f"      filed : {q['topic']}")
        print(f"      better: {t}")
        print(f"      stem  : {q['stem'][:96]}")


if __name__ == "__main__":
    main()
