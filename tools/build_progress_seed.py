"""
One-time (repeatable) conversion: pulls the real subject->chapter->topic syllabus and the
real completed-cycle attempt data out of a temporary `fmge-study` clone (the private
authoring/scoring engine behind this app) and writes two static files this app ships with:

  syllabus.json       {subject: {chapters: [{name, topics: [{id, name}]}]}}
  history_seed.json   [ {date, name, kind, score, total, pct, bySub, byTopic}, ... ]

`fmge-study` keeps no persistent clone by its own convention (see its README), so this script
takes the clone path as an argument -- clone it somewhere temporary, run this, then delete the
clone again. Safe to re-run whenever a new cycle (5+) needs folding in the same way.

Usage:
    python3 build_progress_seed.py /path/to/fmge-study
"""
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing pyyaml. Run: pip3 install pyyaml")

APP_DIR = Path(__file__).resolve().parent.parent

CYCLES = [
    ("2026-07-04_c1", 1, "2026-07-04"),
    ("2026-07-06_c2", 2, "2026-07-06"),
    ("2026-07-07_c3", 3, "2026-07-07"),
]


def build_syllabus(study_dir):
    data = yaml.safe_load((study_dir / "fmge_syllabus.yaml").read_text())
    out = {}
    topic_lookup = {}  # topic_id -> (subject, topic_name)
    for subj in data["subjects"]:
        name = subj["name"]
        chapters = []
        for ch in subj["chapters"]:
            topics = [{"id": t["id"], "name": t["name"]} for t in ch["topics"]]
            for t in ch["topics"]:
                topic_lookup[t["id"]] = (name, t["name"])
            chapters.append({"name": ch["name"], "topics": topics})
        out[name] = {"chapters": chapters}
    return out, topic_lookup


def build_history(study_dir, topic_lookup):
    records = []
    for token, cycle_no, date in CYCLES:
        path = study_dir / "cycles" / f"attempts_{token}.json"
        d = json.loads(path.read_text())
        by_sub = {}
        by_topic = {}
        for row in d["rows"]:
            subj = row["subject"]
            ok = bool(row["is_correct"])
            s = by_sub.setdefault(subj, {"c": 0, "t": 0})
            s["t"] += 1
            if ok:
                s["c"] += 1

            tid = row.get("topic_id")
            topic_name = topic_lookup.get(tid, (subj, tid))[1] if tid else None
            if topic_name:
                t = by_topic.setdefault(topic_name, {"c": 0, "t": 0, "subject": subj})
                t["t"] += 1
                if ok:
                    t["c"] += 1

        wrong_qids = [
            {"qid": row["qid"], "choice": row["choice"], "correct": row["correct"]}
            for row in d["rows"] if not row["is_correct"]
        ]

        total = d["summary"]["total"]
        correct = d["summary"]["correct"]
        records.append(dict(
            date=date + "T00:00:00.000Z",
            name=f"Cycle {cycle_no}",
            kind="grand",
            score=correct,
            total=total,
            pct=round(100 * correct / total, 1),
            bySub=by_sub,
            byTopic=by_topic,
            wrongQids=wrong_qids,
        ))
    return records


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    study_dir = Path(sys.argv[1]).expanduser().resolve()
    if not study_dir.is_dir():
        sys.exit(f"Not a directory: {study_dir}")

    syllabus, topic_lookup = build_syllabus(study_dir)
    (APP_DIR / "syllabus.json").write_text(json.dumps(syllabus, indent=2, ensure_ascii=False))
    print(f"Wrote syllabus.json ({len(syllabus)} subjects, {len(topic_lookup)} topics)")

    history = build_history(study_dir, topic_lookup)
    (APP_DIR / "history_seed.json").write_text(json.dumps(history, indent=2, ensure_ascii=False))
    print(f"Wrote history_seed.json ({len(history)} cycles)")
    for r in history:
        print(f"  {r['name']}: {r['score']}/{r['total']} ({r['pct']}%)")


if __name__ == "__main__":
    main()
